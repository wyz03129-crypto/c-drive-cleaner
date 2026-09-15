from pathlib import Path

import pytest

from cdrive_cleaner.domain.errors import UnsupportedPlatformError
from cdrive_cleaner.executors import RecycleBinExecutor


def test_recycle_bin_requires_windows_and_independent_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cdrive_cleaner.executors.recycle_bin.os.name", "posix")
    executor = RecycleBinExecutor()
    with pytest.raises(UnsupportedPlatformError):
        executor.query(Path("C:/"))
    with pytest.raises(ValueError):
        executor.empty(Path("C:/"), confirmation="CLEAN")


def test_recycle_bin_uses_separate_query_and_empty_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeShell:
        emptied = False

        def SHQueryRecycleBinW(self, _volume: str, pointer: object) -> int:
            info = pointer._obj  # type: ignore[attr-defined]
            info.i64NumItems = 4
            info.i64Size = 4096
            return 0

        def SHEmptyRecycleBinW(self, _window: object, _volume: str, _flags: int) -> int:
            self.emptied = True
            return 0

    shell = FakeShell()
    executor = RecycleBinExecutor()
    monkeypatch.setattr(executor, "_shell32", lambda: shell)
    info = executor.query(Path("C:/"))
    executor.empty(Path("C:/"), confirmation=executor.CONFIRMATION)
    assert (info.item_count, info.size_bytes) == (4, 4096)
    assert shell.emptied
