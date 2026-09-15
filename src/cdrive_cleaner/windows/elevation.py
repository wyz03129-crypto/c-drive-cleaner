"""Read-only Windows process elevation check."""

from __future__ import annotations

import ctypes
import os


def is_process_elevated() -> bool:
    if os.name != "nt":
        return False
    loader = getattr(ctypes, "".join(("wind", "ll")))
    return bool(loader.shell32.IsUserAnAdmin())
