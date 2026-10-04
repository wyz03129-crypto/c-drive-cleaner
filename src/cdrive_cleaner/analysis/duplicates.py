"""Read-only duplicate discovery with bounded file counts and hard-link exclusion."""

from __future__ import annotations

import hashlib
import os
import stat
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from cdrive_cleaner.safety import capture_identity
from cdrive_cleaner.safety.reparse import chain_contains_reparse, is_reparse_point

from .fast_scan import CancellationToken


@dataclass(frozen=True)
class DuplicateGroup:
    paths: tuple[Path, ...]
    size: int

    @property
    def redundant_bytes(self) -> int:
        return (len(self.paths) - 1) * self.size


@dataclass(frozen=True)
class DuplicateSnapshot:
    groups: tuple[DuplicateGroup, ...]
    scanned_files: int
    skipped: int
    cancelled: bool
    limit_reached: bool


class DuplicateAnalyzer:
    """Compare size, edge sample, then full SHA-256. Never choose a copy to delete."""

    def __init__(self, *, min_bytes: int = 1024**2, max_files: int = 100_000) -> None:
        if min_bytes < 1 or max_files < 1:
            raise ValueError("positive limits required")
        self.min_bytes = min_bytes
        self.max_files = max_files

    @staticmethod
    def _digest(
        path: Path, *, sample: bool, token: CancellationToken, expected_size: int | None = None
    ) -> str | None:
        if chain_contains_reparse(path, Path(path.anchor)):
            return None
        before = capture_identity(path)
        if not stat.S_ISREG(before.mode):
            return None
        if expected_size is not None and before.size != expected_size:
            return None
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            # fstat checks the opened object, not just the pathname checked above.
            opened = os.fstat(stream.fileno())
            if (opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                before.inode,
                before.size,
                before.modified_ns,
            ):
                return None
            if sample:
                digest.update(stream.read(65536))
                stream.seek(max(0, before.size - 65536))
                digest.update(stream.read(65536))
            else:
                while not token.cancelled:
                    chunk = stream.read(1024**2)
                    if not chunk:
                        break
                    digest.update(chunk)
            after_handle = os.fstat(stream.fileno())
            if (opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                after_handle.st_ino,
                after_handle.st_size,
                after_handle.st_mtime_ns,
            ):
                return None
        if token.cancelled or capture_identity(path) != before:
            return None
        return digest.hexdigest()

    def analyze(self, root: Path, *, token: CancellationToken | None = None) -> DuplicateSnapshot:
        token = token or CancellationToken()
        root = root.absolute()
        if chain_contains_reparse(root, Path(root.anchor)):
            raise ValueError("重复文件分析根目录包含链接或不可读路径")
        pending = [root]
        sizes: dict[int, list[Path]] = defaultdict(list)
        identities: set[tuple[int, int]] = set()
        scanned = skipped = 0
        while pending and not token.cancelled and scanned < self.max_files:
            directory = pending.pop()
            try:
                if chain_contains_reparse(directory, root):
                    skipped += 1
                    continue
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if token.cancelled or scanned >= self.max_files:
                            break
                        path = Path(entry.path)
                        try:
                            if is_reparse_point(path):
                                skipped += 1
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                pending.append(path)
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            scanned += 1
                            info = entry.stat(follow_symlinks=False)
                            if info.st_size < self.min_bytes:
                                continue
                            identity = capture_identity(path)
                            key = (identity.device, identity.inode)
                            if key in identities:
                                continue
                            identities.add(key)
                            sizes[identity.size].append(path)
                        except OSError:
                            skipped += 1
            except OSError:
                skipped += 1
        groups: list[DuplicateGroup] = []
        for size, paths in sizes.items():
            if token.cancelled:
                break
            if len(paths) < 2:
                continue
            candidates = [paths]
            for sample in (True, False):
                partitions: list[list[Path]] = []
                for candidate in candidates:
                    hashes: dict[str, list[Path]] = defaultdict(list)
                    for path in candidate:
                        if token.cancelled:
                            break
                        try:
                            value = self._digest(
                                path, sample=sample, token=token, expected_size=size
                            )
                            if value is not None:
                                hashes[value].append(path)
                            else:
                                skipped += 1
                        except OSError:
                            skipped += 1
                    partitions.extend(group for group in hashes.values() if len(group) > 1)
                candidates = partitions
            groups.extend(DuplicateGroup(tuple(group), size) for group in candidates)
        groups.sort(key=lambda item: item.redundant_bytes, reverse=True)
        return DuplicateSnapshot(
            tuple(groups), scanned, skipped, token.cancelled, scanned >= self.max_files
        )
