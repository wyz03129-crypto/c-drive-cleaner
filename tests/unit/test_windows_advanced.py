from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cdrive_cleaner.analysis import WindowsAdvancedInspector
from cdrive_cleaner.domain import AdvancedAction
from cdrive_cleaner.domain.errors import SafetyDeniedError, UnsupportedPlatformError
from cdrive_cleaner.executors import WindowsAdvancedExecutor
from cdrive_cleaner.windows import KnownFolders


def test_executor_uses_only_allowlisted_argv() -> None:
    calls: list[tuple[tuple[str, ...], int]] = []

    def runner(argv: object, timeout: int) -> subprocess.CompletedProcess[str]:
        values = tuple(argv)  # type: ignore[arg-type]
        calls.append((values, timeout))
        return subprocess.CompletedProcess(values, 0, "ok", "")

    executor = WindowsAdvancedExecutor(
        runner=runner, elevated_checker=lambda: True, platform_name="nt"
    )
    result = executor.execute(AdvancedAction.ANALYZE_COMPONENT_STORE)
    assert result.succeeded
    assert calls[0][0] == (
        "dism.exe",
        "/Online",
        "/Cleanup-Image",
        "/AnalyzeComponentStore",
    )
    assert all("ResetBase" not in value for value in calls[0][0])


def test_mutating_actions_require_exact_confirmation_and_elevation() -> None:
    def runner(argv: object, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, "", "")  # type: ignore[arg-type]

    executor = WindowsAdvancedExecutor(runner=runner, platform_name="nt")
    with pytest.raises(SafetyDeniedError):
        executor.execute(AdvancedAction.CLEAN_COMPONENT_STORE)
    with pytest.raises(SafetyDeniedError):
        executor.execute(AdvancedAction.CLEAN_COMPONENT_STORE, confirmation="CLEAN COMPONENT STORE")


def test_advanced_executor_rejects_non_windows() -> None:
    with pytest.raises(UnsupportedPlatformError):
        WindowsAdvancedExecutor(platform_name="posix").execute(
            AdvancedAction.ANALYZE_COMPONENT_STORE
        )


def test_inspector_finds_only_known_large_consumers(tmp_path: Path) -> None:
    local = tmp_path / "Local"
    wsl = local / "Packages/Ubuntu/LocalState/ext4.vhdx"
    docker = local / "Docker/wsl/data/docker_data.vhdx"
    wsl.parent.mkdir(parents=True)
    docker.parent.mkdir(parents=True)
    wsl.write_bytes(b"x" * 20)
    docker.write_bytes(b"x" * 10)
    (tmp_path / "hiberfil.sys").write_bytes(b"x" * 30)
    folders = KnownFolders(tmp_path / "Windows", tmp_path, local, tmp_path, tmp_path)
    findings = WindowsAdvancedInspector().inspect(folders)
    assert [item.category for item in findings] == ["hibernation", "wsl", "docker"]
