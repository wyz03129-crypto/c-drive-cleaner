import os
from pathlib import Path

import pytest

from cdrive_cleaner.analysis import CancellationToken
from cdrive_cleaner.analysis.duplicates import DuplicateAnalyzer


def test_full_hash_distinguishes_same_size_and_matching_edges(tmp_path: Path) -> None:
    shared = b"a" * 65536
    data = shared + b"b" + shared
    (tmp_path / "a.bin").write_bytes(data)
    (tmp_path / "b.bin").write_bytes(data)
    (tmp_path / "different.bin").write_bytes(shared + b"c" + shared)
    (tmp_path / "small.bin").write_bytes(b"x")
    result = DuplicateAnalyzer(min_bytes=2).analyze(tmp_path)
    assert len(result.groups) == 1
    assert {p.name for p in result.groups[0].paths} == {"a.bin", "b.bin"}
    assert result.groups[0].redundant_bytes == len(data)
    assert result.scanned_files == 4
    assert len(list(tmp_path.iterdir())) == 4


def test_hardlinks_are_one_object_not_duplicate_copies(tmp_path: Path) -> None:
    target = tmp_path / "a.bin"
    target.write_bytes(b"abc")
    os.link(target, tmp_path / "b.bin")
    assert not DuplicateAnalyzer(min_bytes=1).analyze(tmp_path).groups


def test_duplicates_cancel_and_cap(tmp_path: Path) -> None:
    for index in range(4):
        (tmp_path / f"{index}.bin").write_bytes(b"abc")
    token = CancellationToken()
    token.cancel()
    result = DuplicateAnalyzer(min_bytes=1).analyze(tmp_path, token=token)
    assert result.cancelled and result.scanned_files == 0
    limited = DuplicateAnalyzer(min_bytes=1, max_files=2).analyze(tmp_path)
    assert limited.limit_reached and limited.scanned_files == 2


def test_changed_file_is_discarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cdrive_cleaner.analysis import duplicates

    target = tmp_path / "file.bin"
    target.write_bytes(b"abc")
    original = duplicates.capture_identity
    calls = 0

    def capture(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            path.write_bytes(b"changed")
        return original(path)

    monkeypatch.setattr(duplicates, "capture_identity", capture)
    assert DuplicateAnalyzer._digest(target, sample=False, token=CancellationToken()) is None


def test_hash_error_skips_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("a", "b"):
        (tmp_path / name).write_bytes(b"abc")

    def fail(*args, **kwargs):
        raise PermissionError()

    monkeypatch.setattr(DuplicateAnalyzer, "_digest", fail)
    result = DuplicateAnalyzer(min_bytes=1).analyze(tmp_path)
    assert result.skipped == 2 and not result.groups


@pytest.mark.parametrize("kwargs", [{"min_bytes": 0}, {"max_files": 0}])
def test_invalid_limits(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        DuplicateAnalyzer(**kwargs)
