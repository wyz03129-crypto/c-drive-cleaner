"""Versioned local snapshot cache for instant display while a fresh scan runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cdrive_cleaner.domain import (
    AnalysisCoverage,
    DirectoryUsage,
    LargeFile,
    StorageSnapshot,
)


class StorageSnapshotCache:
    """Persist analysis facts only; cached data never grants cleanup permission."""

    SCHEMA_VERSION = 1

    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, snapshot: StorageSnapshot) -> None:
        payload = {
            "schema": self.SCHEMA_VERSION,
            "root": str(snapshot.root),
            "started_at": snapshot.started_at.isoformat(),
            "finished_at": snapshot.finished_at.isoformat(),
            "total_logical_bytes": snapshot.total_logical_bytes,
            "total_files": snapshot.total_files,
            "directories": [
                [str(item.path), item.logical_bytes, item.file_count, item.directory_count]
                for item in snapshot.directories
            ],
            "top_directories": [str(item.path) for item in snapshot.top_directories],
            "top_files": [
                [str(item.path), item.logical_bytes, item.modified_at.isoformat()]
                for item in snapshot.top_files
            ],
            "coverage": [
                snapshot.coverage.scanned_directories,
                snapshot.coverage.unreadable_directories,
                snapshot.coverage.unreadable_entries,
                snapshot.coverage.skipped_reparse_points,
                snapshot.coverage.duplicate_hardlink_bytes,
            ],
            "cancelled": snapshot.cancelled,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self._path)

    def load(self, *, expected_root: Path) -> StorageSnapshot | None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if payload.get("schema") != self.SCHEMA_VERSION:
                return None
            root = Path(payload["root"])
            if root != expected_root:
                return None
            directories = tuple(
                DirectoryUsage(Path(path), size, files, child_dirs)
                for path, size, files, child_dirs in payload["directories"]
            )
            by_path = {item.path: item for item in directories}
            top_directories = tuple(
                by_path[Path(path)] for path in payload["top_directories"] if Path(path) in by_path
            )
            files = tuple(
                LargeFile(Path(path), size, datetime.fromisoformat(modified).astimezone(UTC))
                for path, size, modified in payload["top_files"]
            )
            coverage = AnalysisCoverage(*payload["coverage"])
            return StorageSnapshot(
                root,
                datetime.fromisoformat(payload["started_at"]).astimezone(UTC),
                datetime.fromisoformat(payload["finished_at"]).astimezone(UTC),
                payload["total_logical_bytes"],
                payload["total_files"],
                directories,
                top_directories,
                files,
                coverage,
                bool(payload["cancelled"]),
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None
