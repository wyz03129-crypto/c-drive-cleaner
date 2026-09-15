"""Read-only storage-analysis result models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class DirectoryUsage:
    path: Path
    logical_bytes: int
    file_count: int
    directory_count: int


@dataclass(frozen=True)
class LargeFile:
    path: Path
    logical_bytes: int
    modified_at: datetime


@dataclass(frozen=True)
class AnalysisCoverage:
    scanned_directories: int
    unreadable_directories: int
    unreadable_entries: int
    skipped_reparse_points: int
    duplicate_hardlink_bytes: int

    @property
    def directory_ratio(self) -> float:
        total = self.scanned_directories + self.unreadable_directories
        return self.scanned_directories / total if total else 1.0


@dataclass(frozen=True)
class StorageSnapshot:
    root: Path
    started_at: datetime
    finished_at: datetime
    total_logical_bytes: int
    total_files: int
    directories: tuple[DirectoryUsage, ...]
    top_directories: tuple[DirectoryUsage, ...]
    top_files: tuple[LargeFile, ...]
    coverage: AnalysisCoverage
    cancelled: bool

    def children_of(self, parent: Path) -> tuple[DirectoryUsage, ...]:
        """Return direct children for UI/CLI drill-down without rescanning."""

        return tuple(item for item in self.directories if item.path.parent == parent)
