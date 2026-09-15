"""Streaming quick scanner for code-owned cache roots."""

from __future__ import annotations

import os
import stat
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

from cdrive_cleaner.domain import Finding, ScanError, ScanSnapshot
from cdrive_cleaner.rules import RuleRegistry, RuleSpec
from cdrive_cleaner.safety import capture_identity
from cdrive_cleaner.safety.reparse import is_reparse_point

ProgressCallback = Callable[[str, int], None]


@dataclass
class CancellationToken:
    """Thread-safe cooperative cancellation shared by scan workers."""

    _event: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class FastScanner:
    """Scan trusted roots with bounded parallelism and no reparse traversal."""

    def __init__(self, registry: RuleRegistry, *, max_workers: int = 4) -> None:
        if not 1 <= max_workers <= 16:
            raise ValueError("max_workers must be between 1 and 16")
        self._registry = registry
        self._max_workers = max_workers

    def scan(
        self,
        *,
        token: CancellationToken | None = None,
        progress: ProgressCallback | None = None,
    ) -> ScanSnapshot:
        started = datetime.now(UTC)
        cancellation = token or CancellationToken()
        findings: list[Finding] = []
        errors: list[ScanError] = []
        jobs = [(rule, root) for rule in self._registry.all() for root in rule.roots]
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._scan_root, rule, root, cancellation, progress): rule
                for rule, root in jobs
            }
            for future in as_completed(futures):
                rule = futures[future]
                try:
                    root_findings, root_errors = future.result()
                    findings.extend(root_findings)
                    errors.extend(root_errors)
                except OSError:
                    errors.append(ScanError(rule.rule_id, "metadata_error"))
        findings.sort(key=lambda item: (item.rule_id, os.fspath(item.path).casefold()))
        return ScanSnapshot(
            started,
            datetime.now(UTC),
            tuple(findings),
            tuple(errors),
            cancellation.cancelled,
        )

    @staticmethod
    def _scan_root(
        rule: RuleSpec,
        root: Path,
        token: CancellationToken,
        progress: ProgressCallback | None,
    ) -> tuple[list[Finding], list[ScanError]]:
        findings: list[Finding] = []
        errors: list[ScanError] = []
        if not root.exists() or is_reparse_point(root):
            return findings, errors
        pending = [root]
        visited = 0
        while pending and not token.cancelled:
            directory = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if token.cancelled:
                            break
                        try:
                            info = entry.stat(follow_symlinks=False)
                            path = Path(entry.path)
                            if entry.is_symlink() or is_reparse_point(path):
                                continue
                            if stat.S_ISDIR(info.st_mode):
                                pending.append(path)
                            elif stat.S_ISREG(info.st_mode):
                                if rule.include_patterns and not any(
                                    fnmatch(entry.name.casefold(), pattern.casefold())
                                    for pattern in rule.include_patterns
                                ):
                                    continue
                                findings.append(
                                    Finding(
                                        rule.rule_id,
                                        rule.version,
                                        path,
                                        root,
                                        rule.risk,
                                        rule.action_kind,
                                        capture_identity(path),
                                    )
                                )
                                visited += 1
                                if progress is not None and visited % 256 == 0:
                                    progress(rule.rule_id, visited)
                        except OSError:
                            errors.append(ScanError(rule.rule_id, "entry_unreadable"))
            except OSError:
                errors.append(ScanError(rule.rule_id, "directory_unreadable"))
        return findings, errors
