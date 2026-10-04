import os

import pytest

from cdrive_cleaner.windows import processes


def test_guard_refreshes_and_matches_case_insensitively(monkeypatch: pytest.MonkeyPatch) -> None:
    names = frozenset({"app.exe"})
    now = 1.0
    monkeypatch.setattr(processes, "process_names", lambda: names)
    monkeypatch.setattr(processes.time, "monotonic", lambda: now)
    guard = processes.ProcessGuard()
    assert not guard(())
    assert guard(("APP.EXE",))
    names = frozenset()
    assert guard(("app.exe",))
    now = 2.1
    assert not guard(("app.exe",))


def test_process_failure_does_not_cache_safe_state(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail():
        raise OSError("cannot enumerate")

    monkeypatch.setattr(processes, "process_names", fail)
    with pytest.raises(OSError):
        processes.ProcessGuard()(("app.exe",))


@pytest.mark.skipif(os.name != "nt", reason="Windows Toolhelp API")
def test_real_process_inventory_contains_system_processes() -> None:
    names = processes.process_names()
    assert names and all(name == name.casefold() for name in names)
    assert "system" in names
