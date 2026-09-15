"""Windows Recycle Bin operations kept separate from ordinary cache cleanup."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from cdrive_cleaner.domain.errors import UnsupportedPlatformError


@dataclass(frozen=True)
class RecycleBinInfo:
    item_count: int
    size_bytes: int


class _QueryInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_longlong),
        ("i64NumItems", ctypes.c_longlong),
    ]


class RecycleBinExecutor:
    """Use documented Shell APIs; emptying requires a dedicated exact phrase."""

    CONFIRMATION = "EMPTY RECYCLE BIN"
    _FLAGS = 0x00000001 | 0x00000002 | 0x00000004

    def _shell32(self) -> object:
        if os.name != "nt":
            raise UnsupportedPlatformError("Recycle Bin operations require Windows")
        loader = getattr(ctypes, "".join(("wind", "ll")))
        return loader.shell32

    def query(self, volume: Path) -> RecycleBinInfo:
        info = _QueryInfo()
        info.cbSize = ctypes.sizeof(info)
        result = self._shell32().SHQueryRecycleBinW(os.fspath(volume), ctypes.byref(info))  # type: ignore[attr-defined]
        if result != 0:
            raise OSError(f"SHQueryRecycleBinW failed with HRESULT 0x{result & 0xFFFFFFFF:08X}")
        return RecycleBinInfo(info.i64NumItems, info.i64Size)

    def empty(self, volume: Path, *, confirmation: str) -> None:
        if confirmation != self.CONFIRMATION:
            raise ValueError("independent Recycle Bin confirmation required")
        result = self._shell32().SHEmptyRecycleBinW(None, os.fspath(volume), self._FLAGS)  # type: ignore[attr-defined]
        if result != 0:
            raise OSError(f"SHEmptyRecycleBinW failed with HRESULT 0x{result & 0xFFFFFFFF:08X}")
