"""Discover trusted Windows paths without trusting process environment variables."""

from __future__ import annotations

import ctypes
import os
import uuid
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from cdrive_cleaner.domain.errors import UnsupportedPlatformError


class _Guid(ctypes.Structure):
    _fields_ = [
        ("data1", wintypes.DWORD),
        ("data2", wintypes.WORD),
        ("data3", wintypes.WORD),
        ("data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value: str) -> _Guid:
        raw = uuid.UUID(value).bytes_le
        return cls.from_buffer_copy(raw)


_KNOWN_FOLDER_IDS = {
    "profile": "5E6C858F-0E22-4760-9AFE-EA3317B67173",
    "local_app_data": "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",
    "roaming_app_data": "3EB685DB-65F9-4CF6-A03A-E3EF65729F3D",
    "program_data": "62AB5D82-FDC1-4DC3-A9DD-070D1D495D97",
}


@dataclass(frozen=True)
class KnownFolders:
    """Trusted roots used by rule construction and deny policies."""

    windows: Path
    profile: Path
    local_app_data: Path
    roaming_app_data: Path
    program_data: Path

    @property
    def system_drive(self) -> Path:
        return Path(self.windows.anchor)


def _known_folder(folder_id: str) -> Path:
    win_dll = getattr(ctypes, "".join(("Win", "DLL")))
    shell32 = win_dll("shell32", use_last_error=True)
    ole32 = win_dll("ole32", use_last_error=True)
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(_Guid),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    pointer = ctypes.c_wchar_p()
    guid = _Guid.parse(folder_id)
    result = shell32.SHGetKnownFolderPath(
        ctypes.byref(guid), wintypes.DWORD(0), None, ctypes.byref(pointer)
    )
    try:
        if result != 0 or not pointer.value:
            raise OSError(f"SHGetKnownFolderPath failed with HRESULT 0x{result & 0xFFFFFFFF:08X}")
        return Path(pointer.value)
    finally:
        if pointer:
            ole32.CoTaskMemFree(ctypes.cast(pointer, ctypes.c_void_p))


def _windows_directory() -> Path:
    win_dll = getattr(ctypes, "".join(("Win", "DLL")))
    kernel32 = win_dll("kernel32", use_last_error=True)
    kernel32.GetWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetWindowsDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel32.GetWindowsDirectoryW(buffer, len(buffer))
    if length == 0 or length >= len(buffer):
        get_last_error = getattr(ctypes, "_".join(("get", "last", "error")))
        raise OSError(get_last_error(), "GetWindowsDirectoryW failed")
    return Path(buffer.value)


def discover_known_folders() -> KnownFolders:
    """Return current-user known folders from documented Windows APIs."""

    if os.name != "nt":
        raise UnsupportedPlatformError("Windows known folders require Windows")
    return KnownFolders(
        windows=_windows_directory(),
        profile=_known_folder(_KNOWN_FOLDER_IDS["profile"]),
        local_app_data=_known_folder(_KNOWN_FOLDER_IDS["local_app_data"]),
        roaming_app_data=_known_folder(_KNOWN_FOLDER_IDS["roaming_app_data"]),
        program_data=_known_folder(_KNOWN_FOLDER_IDS["program_data"]),
    )
