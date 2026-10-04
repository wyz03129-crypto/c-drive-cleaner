"""Allowlisted Windows system commands with explicit risk and elevation gates."""

from __future__ import annotations

import ctypes
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import ClassVar

from cdrive_cleaner.domain import AdvancedAction, CommandResult
from cdrive_cleaner.domain.errors import SafetyDeniedError, UnsupportedPlatformError
from cdrive_cleaner.windows.elevation import is_process_elevated

CommandRunner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]


def _run(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    # Elevated operations must never resolve executables from the working directory or PATH.
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetSystemDirectoryW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    api.GetSystemDirectoryW.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    length = api.GetSystemDirectoryW(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError("cannot discover trusted Windows system directory")
    system = Path(buffer.value)
    command = [str(system / argv[0]), *argv[1:]]
    if argv[0] == "vssadmin.exe":
        command[-1] = f"/for={system.drive}"
    return subprocess.run(
        command,
        shell=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class WindowsAdvancedExecutor:
    """Execute only code-owned argv arrays; callers can never supply a command string."""

    _COMMANDS: ClassVar[Mapping[AdvancedAction, tuple[str, ...]]] = {
        AdvancedAction.ANALYZE_COMPONENT_STORE: (
            "dism.exe",
            "/Online",
            "/Cleanup-Image",
            "/AnalyzeComponentStore",
        ),
        AdvancedAction.CLEAN_COMPONENT_STORE: (
            "dism.exe",
            "/Online",
            "/Cleanup-Image",
            "/StartComponentCleanup",
        ),
        AdvancedAction.DISABLE_HIBERNATION: ("powercfg.exe", "/hibernate", "off"),
        AdvancedAction.ENABLE_HIBERNATION: ("powercfg.exe", "/hibernate", "on"),
        AdvancedAction.LIST_SHADOWS: ("vssadmin.exe", "list", "shadows", "/for=C:"),
        AdvancedAction.OPEN_STORAGE_SETTINGS: (
            "cmd.exe",
            "/d",
            "/c",
            "start",
            "",
            "ms-settings:storagesense",
        ),
    }
    _MUTATING = frozenset(
        {
            AdvancedAction.CLEAN_COMPONENT_STORE,
            AdvancedAction.DISABLE_HIBERNATION,
            AdvancedAction.ENABLE_HIBERNATION,
        }
    )
    _CONFIRMATIONS: ClassVar[Mapping[AdvancedAction, str]] = {
        AdvancedAction.CLEAN_COMPONENT_STORE: "CLEAN COMPONENT STORE",
        AdvancedAction.DISABLE_HIBERNATION: "DISABLE HIBERNATION",
        AdvancedAction.ENABLE_HIBERNATION: "ENABLE HIBERNATION",
    }

    def __init__(
        self,
        *,
        runner: CommandRunner = _run,
        elevated_checker: Callable[[], bool] = is_process_elevated,
        platform_name: str = os.name,
    ) -> None:
        self._runner = runner
        self._elevated_checker = elevated_checker
        self._platform_name = platform_name

    def execute(self, action: AdvancedAction, *, confirmation: str = "") -> CommandResult:
        if self._platform_name != "nt":
            raise UnsupportedPlatformError("advanced operations require Windows")
        if action in self._MUTATING:
            if confirmation != self._CONFIRMATIONS[action]:
                raise SafetyDeniedError("exact action-specific confirmation required")
            if not self._elevated_checker():
                raise SafetyDeniedError("administrator elevation required")
        completed = self._runner(self._COMMANDS[action], 1800)
        return CommandResult(action, completed.returncode, completed.stdout, completed.stderr)
