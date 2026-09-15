from __future__ import annotations

import os
from pathlib import Path

import pytest

from cdrive_cleaner.analysis import CancellationToken, FastScanner
from cdrive_cleaner.domain import ActionKind, RiskLevel
from cdrive_cleaner.rules import RuleRegistry, RuleSpec


def registry(root: Path, patterns: tuple[str, ...] = ()) -> RuleRegistry:
    return RuleRegistry(
        [
            RuleSpec(
                "fixture_cache",
                "1.0.0",
                "Fixture",
                RiskLevel.SAFE,
                ActionKind.DIRECT_FILE_DELETE,
                (root,),
                include_patterns=patterns,
            )
        ]
    )


def test_scan_streams_regular_files_and_applies_patterns(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "thumbcache_1.db").write_bytes(b"123")
    (nested / "keep.txt").write_bytes(b"ignored")
    snapshot = FastScanner(registry(root, ("thumbcache_*.db",))).scan()
    assert [item.path.name for item in snapshot.findings] == ["thumbcache_1.db"]
    assert snapshot.estimated_bytes == 3
    assert snapshot.errors == ()


def test_scan_does_not_follow_symlink(tmp_path: Path) -> None:
    root, outside = tmp_path / "cache", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "private.tmp").write_text("secret", encoding="utf-8")
    try:
        os.symlink(outside, root / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert FastScanner(registry(root)).scan().findings == ()


def test_pre_cancelled_scan_returns_cancelled_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    (root / "file.tmp").write_text("x", encoding="utf-8")
    token = CancellationToken()
    token.cancel()
    snapshot = FastScanner(registry(root)).scan(token=token)
    assert snapshot.cancelled
    assert snapshot.findings == ()


@pytest.mark.parametrize("count", [0, 17])
def test_worker_count_is_bounded(tmp_path: Path, count: int) -> None:
    with pytest.raises(ValueError):
        FastScanner(registry(tmp_path), max_workers=count)
