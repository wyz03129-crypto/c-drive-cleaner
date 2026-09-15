"""Read-only disk and large-directory analysis."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .cache_rules import RiskLevel
from .safety import FILE_ATTRIBUTE_REPARSE_POINT


@dataclass(frozen=True)
class DiskUsageInfo:
    total: int
    used: int
    free: int


@dataclass(frozen=True)
class DirectoryUsage:
    path: Path
    size: int
    file_count: int
    owner_hint: str
    risk: RiskLevel
    error_count: int = 0


def get_disk_usage(root: Path) -> DiskUsageInfo:
    """Return total, used, and free bytes for the selected drive."""

    usage = shutil.disk_usage(root)
    return DiskUsageInfo(usage.total, usage.used, usage.free)


def _owner_hint(path: Path) -> str:
    name = path.name.casefold()
    if name == "windows":
        return "Windows 系统"
    if name in {"program files", "program files (x86)"}:
        return "已安装软件"
    if name == "users":
        return "用户资料（仅审计）"
    if name == "programdata":
        return "软件共享数据"
    if name == "windows.old":
        return "旧版 Windows"
    return "未知/需人工判断"


def measure_directory(root: Path) -> DirectoryUsage:
    """Measure a directory without following symlinks or reparse points."""

    total = 0
    files = 0
    errors = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = os.scandir(current)
        except (PermissionError, FileNotFoundError, OSError):
            errors += 1
            continue
        with entries:
            for entry in entries:
                try:
                    details = entry.stat(follow_symlinks=False)
                    attrs = getattr(details, "st_file_attributes", 0)
                    if entry.is_symlink() or attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        total += details.st_size
                        files += 1
                except (PermissionError, FileNotFoundError, OSError):
                    errors += 1
    return DirectoryUsage(
        root,
        total,
        files,
        _owner_hint(root),
        RiskLevel.MANUAL,
        errors,
    )


def analyze_top_directories(root: Path, limit: int = 20) -> list[DirectoryUsage]:
    """Measure top-level directories for reporting only."""

    results: list[DirectoryUsage] = []
    try:
        entries = list(os.scandir(root))
    except (PermissionError, FileNotFoundError, OSError):
        return results
    for entry in entries:
        try:
            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                continue
            results.append(measure_directory(Path(entry.path)))
        except (PermissionError, FileNotFoundError, OSError):
            continue
    return sorted(results, key=lambda item: item.size, reverse=True)[:limit]
