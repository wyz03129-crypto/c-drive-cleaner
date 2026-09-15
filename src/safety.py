"""Central deletion authorization and the only production delete gateway."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .cache_rules import RiskLevel
from .paths import (
    NormalizedPath,
    is_same_or_within,
    is_unc_path,
    is_within,
    normalize_path,
    path_key,
    get_shell_folder,
    get_windows_directory,
)

CSIDL_PROFILE = 0x0028

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


class DeleteStatus(str, Enum):
    """Outcome of one guarded deletion request."""

    DELETED = "DELETED"
    SIMULATED_DELETE = "SIMULATED_DELETE"
    DENIED = "DENIED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class FileIdentity:
    """Best-effort identity snapshot used to detect post-scan changes."""

    device: int
    inode: int
    size: int
    modified_ns: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> "FileIdentity":
        return cls(value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


@dataclass(frozen=True)
class Authorization:
    """A transparent authorization decision."""

    allowed: bool
    reason: str
    normalized: NormalizedPath | None = None


@dataclass(frozen=True)
class DeleteResult:
    """Result recorded for an individual file."""

    path: str
    status: DeleteStatus
    bytes_affected: int = 0
    reason: str = ""


def is_reparse_point(path: str | os.PathLike[str]) -> bool:
    """Detect symlinks, junctions, mounts, and Windows reparse attributes."""

    value = os.fspath(path)
    try:
        if os.path.islink(value):
            return True
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(value):
            return True
        attributes = getattr(os.lstat(value), "st_file_attributes", 0)
        return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except (FileNotFoundError, PermissionError, OSError):
        return True


class SafetyGuard:
    """Authorize and execute single-file deletes under strict invariants."""

    _PROTECTED_PARTS = {
        "desktop",
        "documents",
        "downloads",
        "pictures",
        "videos",
        "music",
        "recovery",
        "boot",
        "efi",
        "windowsapps",
        "system volume information",
        "backup",
        "backups",
        "autorecovery",
        "recoveryfiles",
        "cloudfiles",
        "clouddocs",
    }
    _PROTECTED_NAMES = {
        "pagefile.sys",
        "hiberfil.sys",
        "swapfile.sys",
        "bookmarks",
        "history",
        "cookies",
        "login data",
        "web data",
        "local state",
        "preferences",
    }
    _PROJECT_MARKERS = {
        ".git",
        ".hg",
        ".svn",
        "pyproject.toml",
        "setup.py",
        "package.json",
        "cargo.toml",
    }
    _PROTECTED_EXTENSIONS = {
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".pdf",
        ".txt",
        ".rtf",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".heic",
        ".mp3",
        ".wav",
        ".flac",
        ".mp4",
        ".mov",
        ".mkv",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".cs",
        ".go",
        ".rs",
        ".sql",
        ".sqlite",
        ".sqlite3",
        ".mdb",
        ".accdb",
        ".db",
    }

    def __init__(
        self,
        allow_roots: Iterable[str | os.PathLike[str]],
        *,
        env: Mapping[str, str] | None = None,
        extra_deny_roots: Iterable[str | os.PathLike[str]] = (),
    ) -> None:
        source = os.environ if env is None else env
        self._allow_roots = {
            path_key(normalize_path(root).real): normalize_path(root)
            for root in allow_roots
        }
        self._deny_roots = tuple(
            normalize_path(root)
            for root in (
                *self._default_deny_roots(source, trusted=env is None),
                *extra_deny_roots,
            )
        )

    @staticmethod
    def _default_deny_roots(
        source: Mapping[str, str], *, trusted: bool
    ) -> tuple[Path, ...]:
        trusted_windows = get_windows_directory() if trusted else None
        drive = (
            trusted_windows.drive
            if trusted_windows and trusted_windows.drive
            else source.get("SystemDrive", "C:")
        )
        root = Path(drive + "\\") if drive.endswith(":") else Path(drive)
        windows = trusted_windows or Path(
            source.get("SystemRoot", os.fspath(root / "Windows"))
        )
        trusted_profile = get_shell_folder(CSIDL_PROFILE) if trusted else None
        user_profile = trusted_profile or (
            Path(source["USERPROFILE"]) if source.get("USERPROFILE") else None
        )
        values = [
            windows / "System32",
            windows / "SysWOW64",
            windows / "WinSxS",
            windows / "Installer",
            windows / "SystemApps",
            root / "Program Files",
            root / "Program Files (x86)",
            root / "ProgramData/Microsoft/Windows/Start Menu",
            root / "WindowsApps",
            root / "System Volume Information",
            root / "Recovery",
            root / "Boot",
            root / "EFI",
        ]
        if user_profile:
            profile = Path(user_profile)
            values.extend(
                profile / name
                for name in (
                    "Desktop",
                    "Documents",
                    "Downloads",
                    "Pictures",
                    "Videos",
                    "Music",
                    "OneDrive",
                )
            )
        return tuple(values)

    def _known_scope(self, scope: NormalizedPath) -> bool:
        return path_key(scope.real) in self._allow_roots

    def _hits_denylist(self, candidate: NormalizedPath) -> bool:
        for denied in self._deny_roots:
            if is_same_or_within(candidate.absolute, denied.absolute):
                return True
            if is_same_or_within(candidate.real, denied.real):
                return True
        return False

    @classmethod
    def _has_protected_name(cls, candidate: NormalizedPath) -> bool:
        parts = [part.casefold() for part in Path(candidate.absolute).parts]
        if any(part in cls._PROTECTED_PARTS for part in parts):
            return True
        if any(part.startswith("onedrive") for part in parts):
            return True
        if not parts:
            return False
        name = parts[-1]
        if name in cls._PROTECTED_NAMES:
            return True
        suffix = Path(name).suffix.casefold()
        if suffix in cls._PROTECTED_EXTENSIONS:
            return not name.startswith(("thumbcache_", "iconcache_"))
        return False

    @classmethod
    def filename_is_protected(cls, name: str) -> bool:
        """Expose the conservative filename filter for pre-scan exclusion."""

        normalized = NormalizedPath(name, name, name, name)
        return cls._has_protected_name(normalized)

    @classmethod
    def _contains_project_marker(cls, target: Path, scope: Path) -> bool:
        current = target.parent
        scope_key = path_key(scope)
        while is_same_or_within(current, scope):
            for marker in cls._PROJECT_MARKERS:
                try:
                    if (current / marker).exists():
                        return True
                except (PermissionError, OSError):
                    return True
            if path_key(current) == scope_key:
                return False
            parent = current.parent
            if parent == current:
                break
            current = parent
        return False

    @staticmethod
    def _chain_has_reparse(target: Path, scope: Path) -> bool:
        current = target
        scope_key = path_key(scope)
        while True:
            if is_reparse_point(current):
                return True
            if path_key(current) == scope_key:
                return False
            parent = current.parent
            if parent == current or not is_same_or_within(parent, scope):
                return True
            current = parent

    def authorize_delete(
        self,
        path: str | os.PathLike[str],
        *,
        scope_root: str | os.PathLike[str],
        risk: RiskLevel,
        expected_identity: FileIdentity | None = None,
    ) -> Authorization:
        """Revalidate a single file and return a reasoned authorization."""

        raw = os.path.expanduser(os.path.expandvars(os.fspath(path)))
        if not os.path.isabs(raw):
            return Authorization(False, "路径不是绝对路径")
        if is_unc_path(raw):
            return Authorization(False, "拒绝 UNC/网络路径")
        if risk is not RiskLevel.SAFE:
            return Authorization(False, "仅 SAFE 风险级别允许删除")

        candidate = normalize_path(raw)
        scope = normalize_path(scope_root)
        if not self._known_scope(scope):
            return Authorization(False, "清理范围不在代码内置白名单", candidate)
        if not is_within(candidate.absolute, scope.absolute):
            return Authorization(False, "路径不在白名单范围内", candidate)
        if not is_within(candidate.real, scope.real):
            return Authorization(False, "真实路径逃逸白名单范围", candidate)
        if self._hits_denylist(candidate):
            return Authorization(False, "路径命中系统/用户数据保护列表", candidate)
        if self._has_protected_name(candidate):
            return Authorization(False, "路径包含受保护名称", candidate)
        if not os.path.lexists(candidate.absolute):
            return Authorization(False, "文件已不存在", candidate)
        if self._chain_has_reparse(Path(candidate.absolute), Path(scope.absolute)):
            return Authorization(False, "路径链包含链接、挂载点或重解析点", candidate)
        if self._contains_project_marker(Path(candidate.absolute), Path(scope.absolute)):
            return Authorization(False, "路径位于源码或版本库中", candidate)

        try:
            details = os.stat(candidate.absolute, follow_symlinks=False)
        except FileNotFoundError:
            return Authorization(False, "文件已不存在", candidate)
        except (PermissionError, OSError) as exc:
            return Authorization(False, f"无法安全读取文件属性: {exc}", candidate)
        if not stat.S_ISREG(details.st_mode):
            return Authorization(False, "目标不是普通文件", candidate)
        if expected_identity and FileIdentity.from_stat(details) != expected_identity:
            return Authorization(False, "文件自扫描后已发生变化", candidate)
        return Authorization(True, "授权通过", candidate)

    def delete_file(
        self,
        path: str | os.PathLike[str],
        *,
        scope_root: str | os.PathLike[str],
        risk: RiskLevel,
        expected_identity: FileIdentity | None = None,
        dry_run: bool,
    ) -> DeleteResult:
        """Delete one file, or simulate it, after a fresh authorization check."""

        decision = self.authorize_delete(
            path,
            scope_root=scope_root,
            risk=risk,
            expected_identity=expected_identity,
        )
        if not decision.allowed or decision.normalized is None:
            return DeleteResult(os.fspath(path), DeleteStatus.DENIED, reason=decision.reason)
        try:
            final_stat = os.stat(decision.normalized.absolute, follow_symlinks=False)
            if expected_identity and FileIdentity.from_stat(final_stat) != expected_identity:
                return DeleteResult(
                    decision.normalized.absolute,
                    DeleteStatus.DENIED,
                    reason="删除前最终复核发现文件已变化",
                )
            size = final_stat.st_size
            if dry_run:
                return DeleteResult(
                    decision.normalized.absolute,
                    DeleteStatus.SIMULATED_DELETE,
                    bytes_affected=size,
                    reason="DRY RUN",
                )
            os.remove(decision.normalized.absolute)
            return DeleteResult(
                decision.normalized.absolute,
                DeleteStatus.DELETED,
                bytes_affected=size,
            )
        except FileNotFoundError:
            return DeleteResult(os.fspath(path), DeleteStatus.SKIPPED, reason="文件已不存在")
        except (
            PermissionError,
            IsADirectoryError,
            NotADirectoryError,
            OSError,
        ) as exc:
            return DeleteResult(
                os.fspath(path), DeleteStatus.SKIPPED, reason=f"跳过: {exc}"
            )
