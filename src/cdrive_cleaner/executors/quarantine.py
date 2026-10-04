"""Cross-volume verified backups. No original deletion before a durable manifest.

Payloads are plaintext; manifests are DPAPI-protected for the current Windows user.
Recovery never overwrites a destination, never creates missing parent directories,
and retains its backup. This is a cache recovery mechanism, not a general backup tool.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from cdrive_cleaner.analysis.fast_scan import CancellationToken
from cdrive_cleaner.domain import ActionKind, FileIdentity, PlannedAction
from cdrive_cleaner.rules import RuleRegistry
from cdrive_cleaner.safety import SafetyPolicy, capture_identity
from cdrive_cleaner.safety.path_policy import normalize_path
from cdrive_cleaner.safety.reparse import chain_contains_reparse, same_or_within
from cdrive_cleaner.windows.data_streams import require_unnamed_data_only
from cdrive_cleaner.windows.file_identity import file_reference
from cdrive_cleaner.windows.processes import ProcessGuard
from cdrive_cleaner.windows.protected_data import protect

from .direct_file import DirectFileDeleteExecutor
from .handle_delete import delete_verified_file
from .models import ExecutionResult, ExecutionStatus

_ID = re.compile(r"[a-f0-9]{32}\Z")
_RESERVE = 16 * 1024**2


@dataclass(frozen=True)
class RecoveryEntry:
    entry_id: str
    original: str
    size: int
    created: str
    state: str


def _safe(path: Path) -> None:
    normalize_path(path)
    if chain_contains_reparse(path, Path(path.anchor)):
        raise OSError("链接或不可读的隔离路径：拒绝操作")


def _sync_write(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _digest(path: Path, token: CancellationToken | None = None) -> str:
    _safe(path)
    before = capture_identity(path)
    with path.open("rb") as stream:
        hasher = hashlib.sha256()
        while chunk := stream.read(1024**2):
            if token is not None and token.cancelled:
                raise OSError("恢复已取消，备份保留")
            hasher.update(chunk)
        digest = hasher.hexdigest()
    if capture_identity(path) != before:
        raise OSError("备份在校验期间发生变化")
    return digest


class QuarantineStore:
    """An explicitly selected, current-user vault on another local volume."""

    def __init__(self, root: Path, *, max_bytes: int = 10 * 1024**3) -> None:
        self.root = normalize_path(root).absolute
        if self.root.name != "CDriveCleaner-Quarantine" or max_bytes < 1:
            raise ValueError("请选择专用 CDriveCleaner-Quarantine 目录")
        self.max_bytes = max_bytes

    def initialize(self) -> None:
        _safe(self.root.parent)
        self.root.mkdir(exist_ok=True)
        _safe(self.root)
        owner = self.root / "owner.bin"
        if not owner.exists():
            if any(self.root.iterdir()):
                raise OSError("隔离目录不是空目录，无法初始化")
            _sync_write(owner, protect(b"CDriveCleaner recovery v1"))
        self._owner()

    def _owner(self) -> None:
        _safe(self.root)
        owner = self.root / "owner.bin"
        _safe(owner)
        if (
            owner.stat().st_size > 65536
            or protect(owner.read_bytes(), decrypt=True) != b"CDriveCleaner recovery v1"
        ):
            raise OSError("隔离区不属于当前 Windows 用户或已损坏")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        import msvcrt

        self._owner()
        lock_path = self.root / "vault.lock"
        if os.path.lexists(lock_path):
            _safe(lock_path)
        with lock_path.open("a+b") as lock:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def _directory(self, entry_id: str) -> Path:
        self._owner()
        if not _ID.fullmatch(entry_id):
            raise ValueError("无效备份编号")
        directory = self.root / entry_id
        _safe(directory)
        return directory

    def _record(self, entry_id: str) -> dict[str, str | int]:
        directory = self._directory(entry_id)
        path = directory / "manifest.bin"
        _safe(path)
        if path.stat().st_size > 65536:
            raise OSError("备份记录过大")
        record = json.loads(protect(path.read_bytes(), decrypt=True))
        if (
            not isinstance(record, dict)
            or record.get("id") != entry_id
            or record.get("schema") != 1
        ):
            raise ValueError("备份记录不匹配")
        for key in ("original", "scope", "rule", "version", "created", "sha256"):
            if not isinstance(record.get(key), str):
                raise ValueError("备份记录字段无效")
        for key in ("size", "modified_ns", "volume"):
            if type(record.get(key)) is not int or record[key] < 0:
                raise ValueError("备份记录数值无效")
        return record

    def entries(self) -> tuple[RecoveryEntry, ...]:
        self._owner()
        entries: list[RecoveryEntry] = []
        for directory in self.root.iterdir():
            if not _ID.fullmatch(directory.name):
                continue
            if len(entries) >= 10000:
                raise OSError("备份条目超过上限，请先人工检查隔离区")
            try:
                record = self._record(directory.name)
                source = Path(str(record["original"]))
                state = "原路径存在（不覆盖）" if os.path.lexists(source) else "待恢复"
                entries.append(
                    RecoveryEntry(
                        directory.name,
                        str(source),
                        int(record["size"]),
                        str(record["created"]),
                        state,
                    )
                )
            except (OSError, ValueError, TypeError):
                entries.append(
                    RecoveryEntry(directory.name, "", 0, "", "未完成或记录损坏；不会自动恢复")
                )
        return tuple(sorted(entries, key=lambda entry: entry.created, reverse=True))

    def _capacity(self, size: int) -> None:
        used = 0
        for entry in self.root.iterdir():
            if _ID.fullmatch(entry.name):
                _safe(entry)
                payload = entry / "payload.bin"
                if payload.exists():
                    _safe(payload)
                    used += payload.stat().st_size
        if used + size > self.max_bytes:
            raise OSError("隔离区达到 10 GB 配额；不会删除原文件")
        if shutil.disk_usage(self.root).free < size + _RESERVE:
            raise OSError("隔离盘空间不足；不会删除原文件")

    def capture(self, action: PlannedAction, source: BinaryIO, token: CancellationToken) -> str:
        """Called only while the executor holds the vault lock through source deletion."""
        self._owner()
        finding = action.finding
        require_unnamed_data_only(finding.path)
        if file_reference(self.root).volume == finding.identity.device:
            raise OSError("隔离区必须位于另一卷；同盘移动不能释放空间")
        if same_or_within(self.root, finding.scope_root) or same_or_within(
            finding.scope_root, self.root
        ):
            raise OSError("隔离区不能与清理目录重叠")
        self._capacity(finding.identity.size)
        entry_id = uuid.uuid4().hex
        directory = self.root / entry_id
        directory.mkdir()
        _safe(directory)
        payload = directory / "payload.bin"
        digest = hashlib.sha256()
        size = 0
        with payload.open("xb") as output:
            while chunk := source.read(1024**2):
                if token.cancelled:
                    raise OSError("备份已取消，原文件保留")
                digest.update(chunk)
                size += len(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if size != finding.identity.size or _digest(payload) != digest.hexdigest():
            raise OSError("备份校验失败，原文件保留")
        record = {
            "schema": 1,
            "id": entry_id,
            "original": str(finding.path),
            "scope": str(finding.scope_root),
            "rule": finding.rule_id,
            "version": finding.rule_version,
            "created": datetime.now(UTC).isoformat(),
            "size": size,
            "modified_ns": finding.identity.modified_ns,
            "volume": finding.identity.device,
            "sha256": digest.hexdigest(),
        }
        _sync_write(directory / "manifest.bin", protect(json.dumps(record).encode("utf-8")))
        # Read back the persisted manifest before authorizing source deletion.
        if self._record(entry_id) != record or token.cancelled:
            raise OSError("备份记录未就绪或已取消，原文件保留")
        return entry_id

    def restore(
        self,
        entry_id: str,
        registry: RuleRegistry,
        policy: SafetyPolicy,
        *,
        token: CancellationToken | None = None,
    ) -> Path:
        with self._locked():
            return self._restore(entry_id, registry, policy, token or CancellationToken())

    def _restore(
        self, entry_id: str, registry: RuleRegistry, policy: SafetyPolicy, token: CancellationToken
    ) -> Path:
        record = self._record(entry_id)
        rule = registry.resolve(str(record["rule"]), str(record["version"]))
        target = normalize_path(str(record["original"])).absolute
        scope = normalize_path(str(record["scope"])).absolute
        if (
            rule is None
            or scope not in rule.roots
            or rule.requires_elevation
            or rule.action_kind is not ActionKind.DIRECT_FILE_DELETE
        ):
            raise OSError("原规则已变更或需要管理员，拒绝恢复")
        if ProcessGuard()(rule.blocking_processes):
            raise OSError("请先退出相关应用再恢复")
        policy.authorize_restore(target, scope_root=scope)
        if file_reference(target.parent).volume != record["volume"]:
            raise OSError("原磁盘卷已变化，拒绝恢复")
        payload = self._directory(entry_id) / "payload.bin"
        if _digest(payload, token) != record["sha256"] or payload.stat().st_size != record["size"]:
            raise OSError("备份内容损坏，拒绝恢复")
        if shutil.disk_usage(target.parent).free < int(record["size"]) + _RESERVE:
            raise OSError("原磁盘空间不足")
        temporary = target.parent / f".cdrive-restore-{uuid.uuid4().hex}.tmp"
        try:
            digest = hashlib.sha256()
            with payload.open("rb") as source, temporary.open("xb") as output:
                while chunk := source.read(1024**2):
                    if token.cancelled:
                        raise OSError("恢复已取消，备份保留")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != record["sha256"]:
                raise OSError("恢复写入校验失败")
            if _digest(temporary, token) != record["sha256"]:
                raise OSError("恢复文件读回校验失败")
            os.utime(temporary, ns=(int(record["modified_ns"]), int(record["modified_ns"])))
            policy.authorize_restore(target, scope_root=scope)
            if token.cancelled:
                raise OSError("恢复已取消，备份保留")
            if ProcessGuard()(rule.blocking_processes):
                raise OSError("应用已启动，取消恢复")
            if os.name != "nt":
                raise OSError("恢复只支持 Windows 的不覆盖重命名语义")
            temporary.rename(target)  # Windows refuses an existing destination.
        finally:
            if temporary.exists():
                delete_verified_file(temporary, capture_identity(temporary))
        return target  # Keep the backup until the user explicitly purges it.

    def purge(self, entry_id: str, *, confirmation: str) -> None:
        if confirmation != "DELETE BACKUP":
            raise ValueError("删除备份需要独立确认")
        with self._locked():
            self._purge(entry_id)

    def _purge(self, entry_id: str) -> None:
        directory = self._directory(entry_id)
        children = list(directory.iterdir())
        if any(path.name not in {"payload.bin", "manifest.bin"} for path in children):
            raise OSError("隔离记录包含未知文件，拒绝删除")
        for path in children:
            _safe(path)
            delete_verified_file(path, capture_identity(path))
        directory.rmdir()


class QuarantineExecutor:
    def __init__(
        self,
        store: QuarantineStore,
        policy: SafetyPolicy,
        registry: RuleRegistry,
        *,
        token: CancellationToken | None = None,
    ) -> None:
        self.store, self.policy, self.registry = store, policy, registry
        self.token = token or CancellationToken()

    def execute(self, action: PlannedAction, *, dry_run: bool) -> ExecutionResult:
        error: list[str] = []
        recovery_ids: list[str] = []

        def prepare(stream: BinaryIO) -> None:
            recovery_ids.append(self.store.capture(action, stream, self.token))

        def backup_delete(path: Path, identity: FileIdentity) -> None:
            try:
                with self.store._locked():
                    delete_verified_file(
                        path,
                        identity,
                        before_delete=prepare,
                    )
            except (OSError, ValueError) as failure:
                error.append(str(failure))
                raise OSError("backup_not_completed") from failure

        executor = DirectFileDeleteExecutor(
            self.policy, registry=self.registry, verified_delete=backup_delete
        )
        result = executor.execute(action, dry_run=dry_run)
        if error:
            return ExecutionResult(
                ExecutionStatus.SKIPPED,
                bytes_attempted=action.finding.identity.size,
                error_code="backup_not_completed",
            )
        if result.status is ExecutionStatus.DELETED:
            return replace(result, status=ExecutionStatus.QUARANTINED, recovery_id=recovery_ids[0])
        return result
