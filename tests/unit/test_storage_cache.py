from datetime import UTC, datetime
from pathlib import Path

from cdrive_cleaner.domain import AnalysisCoverage, DirectoryUsage, LargeFile, StorageSnapshot
from cdrive_cleaner.persistence import StorageSnapshotCache


def snapshot(root: Path) -> StorageSnapshot:
    now = datetime.now(UTC)
    directory = DirectoryUsage(root / "Users", 100, 2, 1)
    return StorageSnapshot(
        root,
        now,
        now,
        100,
        2,
        (directory,),
        (directory,),
        (LargeFile(root / "large.bin", 80, now),),
        AnalysisCoverage(2, 1, 3, 1, 10),
        False,
    )


def test_snapshot_cache_round_trip_and_root_binding(tmp_path: Path) -> None:
    cache = StorageSnapshotCache(tmp_path / "cache" / "storage.json")
    expected = snapshot(tmp_path)
    cache.save(expected)
    loaded = cache.load(expected_root=tmp_path)
    assert loaded == expected
    assert cache.load(expected_root=tmp_path / "other") is None


def test_invalid_or_old_cache_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "storage.json"
    path.write_text('{"schema": 999}', encoding="utf-8")
    assert StorageSnapshotCache(path).load(expected_root=tmp_path) is None
    path.write_text("broken", encoding="utf-8")
    assert StorageSnapshotCache(path).load(expected_root=tmp_path) is None
