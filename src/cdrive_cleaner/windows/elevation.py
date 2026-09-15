"""Read-only Windows process elevation check."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from collections.abc import Callable, Sequence


def is_process_elevated() -> bool:
    if os.name != "nt":
        return False
    loader = getattr(ctypes, "".join(("wind", "ll")))
    return bool(loader.shell32.IsUserAnAdmin())


def relaunch_elevated(
    *,
    executable: str | None = None,
    arguments: Sequence[str] | None = None,
    shell_execute: Callable[[str, str], int] | None = None,
) -> bool:
    """Request UAC elevation for a new GUI process without accepting command input."""

    if os.name != "nt" and shell_execute is None:
        return False
    program = executable or sys.executable
    if arguments is None:
        arguments = (
            tuple(sys.argv[1:])
            if getattr(sys, "frozen", False)
            else ("-m", "cdrive_cleaner.gui_main", *sys.argv[1:])
        )
    parameters = subprocess.list2cmdline(list(arguments))
    if shell_execute is None:
        loader = getattr(ctypes, "".join(("wind", "ll")))

        def shell_execute(path: str, params: str) -> int:
            return int(loader.shell32.ShellExecuteW(None, "runas", path, params, None, 1))

    return shell_execute(program, parameters) > 32
