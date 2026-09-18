"""Read-only, bounded-memory directory and large-file analysis."""

from __future__ import annotations

import heapq
import os
import stat
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cdrive_cleaner.domain import AnalysisCoverage, DirectoryUsage, LargeFile, StorageSnapshot
from cdrive_cleaner.windows.file_identity import file_reference

from .fast_scan import CancellationToken


@dataclass
class _Usage:
    logical_bytes: int = 0
    file_count: int = 0
    directory_count: int = 0


class StorageAnalyzer:
    """Analyze one volume without following links or granting cleanup permission."""

    def __init__(self, *, top_n: int = 20, large_file_threshold: int = 0) -> None:
        if not 1 <= top_n <= 1000:
            raise ValueError("top_n must be between 1 and 1000")
        if large_file_threshold < 0:
            raise ValueError("large_file_threshold cannot be negative")
        self._top_n = top_n
        self._large_file_threshold = large_file_threshold

    def analyze(self, root: Path, *, token: CancellationToken | None = None) -> StorageSnapshot:
        started = datetime.now(UTC)
        cancellation = token or CancellationToken()
        root = root.resolve(strict=True)
        usage: dict[Path, _Usage] = defaultdict(_Usage)
        pending = [root]
        seen_files: set[tuple[int, int]] = set()
        largest: list[tuple[int, int, Path, int]] = []
        scanned_dirs = unreadable_dirs = unreadable_entries = skipped_reparse = 0
        duplicate_bytes = total_bytes = total_files = sequence = 0

        while pending and not cancellation.cancelled:
            directory = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    scanned_dirs += 1
                    for entry in entries:
                        if cancellation.cancelled:
                            break
                        path = Path(entry.path)
                        try:
                            info = entry.stat(follow_symlinks=False)
                            attributes = getattr(info, "st_file_attributes", 0)
                            if entry.is_symlink() or attributes & 0x400:
                                skipped_reparse += 1
                                continue
                            if stat.S_ISDIR(info.st_mode):
                                pending.append(path)
                                self._add_directory(usage, path, root)
                                continue
                            if not stat.S_ISREG(info.st_mode):
                                continue
                            reference = file_reference(path, info)
                            if reference.link_count > 1:
                                identity = (reference.volume, reference.index)
                                if identity in seen_files:
                                    duplicate_bytes += info.st_size
                                    continue
                                seen_files.add(identity)
                            total_bytes += info.st_size
                            total_files += 1
                            self._add_file(usage, path.parent, root, info.st_size)
                            if info.st_size >= self._large_file_threshold:
                                sequence += 1
                                item = (info.st_size, sequence, path, info.st_mtime_ns)
                                if len(largest) < self._top_n:
                                    heapq.heappush(largest, item)
                                elif item[:2] > largest[0][:2]:
                                    heapq.heapreplace(largest, item)
                        except OSError:
                            unreadable_entries += 1
            except OSError:
                unreadable_dirs += 1

        directories = tuple(
            sorted(
                (
                    DirectoryUsage(path, item.logical_bytes, item.file_count, item.directory_count)
                    for path, item in usage.items()
                    if path != root
                ),
                key=lambda item: (-item.logical_bytes, os.fspath(item.path).casefold()),
            )
        )
        files = tuple(
            LargeFile(path, size, datetime.fromtimestamp(modified / 1_000_000_000, UTC))
            for size, _, path, modified in sorted(largest, reverse=True)
        )
        return StorageSnapshot(
            root,
            started,
            datetime.now(UTC),
            total_bytes,
            total_files,
            directories,
            directories[: self._top_n],
            files,
            AnalysisCoverage(
                scanned_dirs,
                unreadable_dirs,
                unreadable_entries,
                skipped_reparse,
                duplicate_bytes,
            ),
            cancellation.cancelled,
        )

    @staticmethod
    def _ancestors(directory: Path, root: Path) -> list[Path]:
        values: list[Path] = []
        current = directory
        while current == root or root in current.parents:
            values.append(current)
            if current == root:
                break
            current = current.parent
        return values

    @classmethod
    def _add_file(cls, usage: dict[Path, _Usage], directory: Path, root: Path, size: int) -> None:
        for ancestor in cls._ancestors(directory, root):
            usage[ancestor].logical_bytes += size
            usage[ancestor].file_count += 1

    @classmethod
    def _add_directory(cls, usage: dict[Path, _Usage], directory: Path, root: Path) -> None:
        usage[directory]
        for ancestor in cls._ancestors(directory.parent, root):
            usage[ancestor].directory_count += 1
