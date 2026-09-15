from __future__ import annotations

import os
from pathlib import Path

import pytest

from cdrive_cleaner.analysis import CancellationToken, StorageAnalyzer


def test_analyzer_builds_drilldown_and_top_lists(tmp_path: Path) -> None:
    first = tmp_path / "Users" / "Alice"
    second = tmp_path / "Windows" / "Temp"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "video.bin").write_bytes(b"x" * 20)
    (second / "log.bin").write_bytes(b"x" * 5)

    snapshot = StorageAnalyzer(top_n=2).analyze(tmp_path)

    assert snapshot.total_logical_bytes == 25
    assert snapshot.total_files == 2
    assert snapshot.top_files[0].path.name == "video.bin"
    assert snapshot.top_directories[0].path == tmp_path / "Users"
    assert {item.path.name for item in snapshot.children_of(tmp_path)} == {"Users", "Windows"}
    assert snapshot.coverage.directory_ratio == 1.0


def test_hard_links_are_not_double_counted(tmp_path: Path) -> None:
    original = tmp_path / "one.bin"
    linked = tmp_path / "two.bin"
    original.write_bytes(b"123456")
    try:
        os.link(original, linked)
    except OSError:
        pytest.skip("hard links unavailable")

    snapshot = StorageAnalyzer().analyze(tmp_path)

    assert snapshot.total_logical_bytes == 6
    assert snapshot.total_files == 1
    assert snapshot.coverage.duplicate_hardlink_bytes == 6


def test_reparse_or_symlink_is_skipped(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    root = tmp_path / "root"
    outside.mkdir()
    root.mkdir()
    (outside / "large.bin").write_bytes(b"x" * 100)
    try:
        os.symlink(outside, root / "linked", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    snapshot = StorageAnalyzer().analyze(root)

    assert snapshot.total_logical_bytes == 0
    assert snapshot.coverage.skipped_reparse_points == 1


def test_cancelled_analysis_returns_partial_snapshot(tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    snapshot = StorageAnalyzer().analyze(tmp_path, token=token)
    assert snapshot.cancelled
    assert snapshot.total_files == 0


@pytest.mark.parametrize("top_n", [0, 1001])
def test_top_n_is_bounded(top_n: int) -> None:
    with pytest.raises(ValueError):
        StorageAnalyzer(top_n=top_n)
