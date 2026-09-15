"""Filesystem scanner that never follows links and never mutates files."""

from __future__ import annotations

import fnmatch
import os
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .cache_rules import CacheRule, RiskLevel
from .safety import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    FileIdentity,
    SafetyGuard,
    is_reparse_point,
)


@dataclass(frozen=True)
class FileCandidate:
    """A scanned SAFE file; deletion still requires guard authorization."""

    rule_id: str
    display_name: str
    risk: RiskLevel
    path: Path
    scope_root: Path
    size: int
    identity: FileIdentity


@dataclass
class RuleScanResult:
    """Aggregated scan result for one built-in rule."""

    rule_id: str
    display_name: str
    risk: RiskLevel
    total_bytes: int = 0
    file_count: int = 0
    skipped_count: int = 0
    roots_found: int = 0
    candidates: list[FileCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recommendation: str = ""


_NEVER_TRAVERSE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "site-packages",
    "backup",
    "backups",
    "autorecovery",
    "recovery",
    "cloud",
    "clouddocs",
}
_PROJECT_MARKER_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "cargo.toml",
}
_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go", ".rs"}


def _matches(name: str, patterns: tuple[str, ...]) -> bool:
    folded = name.casefold()
    return any(fnmatch.fnmatch(folded, pattern.casefold()) for pattern in patterns)


def _entry_is_reparse(entry: os.DirEntry[str]) -> bool:
    try:
        details = entry.stat(follow_symlinks=False)
        attributes = getattr(details, "st_file_attributes", 0)
        return entry.is_symlink() or bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except (FileNotFoundError, PermissionError, OSError):
        return True


def _scan_scope(rule: CacheRule, scope: Path, result: RuleScanResult) -> None:
    if not scope.exists():
        return
    if is_reparse_point(scope):
        result.skipped_count += 1
        result.errors.append(f"跳过链接/重解析根目录: {scope}")
        return
    result.roots_found += 1
    stack = [scope]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except (PermissionError, FileNotFoundError, OSError) as exc:
            result.skipped_count += 1
            result.errors.append(f"无法扫描 {directory}: {exc}")
            continue
        if directory != scope:
            names = {entry.name.casefold() for entry in entries}
            contains_source = any(
                Path(entry.name).suffix.casefold() in _SOURCE_EXTENSIONS
                for entry in entries
            )
            if names & _PROJECT_MARKER_NAMES or contains_source:
                result.skipped_count += 1
                continue
        for entry in entries:
            try:
                if _entry_is_reparse(entry):
                    result.skipped_count += 1
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.casefold() in _NEVER_TRAVERSE_DIR_NAMES:
                        result.skipped_count += 1
                        continue
                    stack.append(Path(entry.path))
                    continue
                # On Windows, DirEntry.stat() can expose zero st_dev/st_ino while
                # os.stat(path) returns the stable file identity used later.
                details = os.stat(entry.path, follow_symlinks=False)
                if not stat.S_ISREG(details.st_mode):
                    result.skipped_count += 1
                    continue
                if not _matches(entry.name, rule.file_patterns):
                    continue
                if SafetyGuard.filename_is_protected(entry.name):
                    result.skipped_count += 1
                    continue
                if rule.minimum_age_days:
                    cutoff = time.time() - rule.minimum_age_days * 86400
                    if details.st_mtime > cutoff:
                        result.skipped_count += 1
                        continue
                result.file_count += 1
                result.total_bytes += details.st_size
                if rule.can_delete:
                    result.candidates.append(
                        FileCandidate(
                            rule.rule_id,
                            rule.display_name,
                            rule.risk,
                            Path(entry.path),
                            scope,
                            details.st_size,
                            FileIdentity.from_stat(details),
                        )
                    )
            except (PermissionError, FileNotFoundError, OSError) as exc:
                result.skipped_count += 1
                result.errors.append(f"跳过 {entry.path}: {exc}")


def scan_rule(rule: CacheRule) -> RuleScanResult:
    """Scan one rule without following links or changing the filesystem."""

    result = RuleScanResult(
        rule.rule_id,
        rule.display_name,
        rule.risk,
        recommendation=rule.recommendation,
    )
    for scope in rule.roots:
        _scan_scope(rule, scope, result)
    return result


def scan_rules(rules: Iterable[CacheRule]) -> list[RuleScanResult]:
    """Scan all enabled built-in rules."""

    return [scan_rule(rule) for rule in rules]
