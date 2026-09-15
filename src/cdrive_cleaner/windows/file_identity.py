"""Stable file references backed by Windows handle metadata."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileReference:
    volume: int
    index: int
    link_count: int


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


def file_reference(path: Path, details: os.stat_result | None = None) -> FileReference:
    """Return a stable volume/file-index pair without following final reparse points."""

    if os.name != "nt":
        info = details or os.stat(path, follow_symlinks=False)
        return FileReference(info.st_dev, info.st_ino, info.st_nlink)
    win_dll = getattr(ctypes, "".join(("Win", "DLL")))
    kernel32 = win_dll("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateFileW(os.fspath(path), 0, 7, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError("CreateFileW failed while reading file identity")
    try:
        handle_info = _ByHandleFileInformation()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(handle_info)):
            raise OSError("GetFileInformationByHandle failed")
        index = (handle_info.nFileIndexHigh << 32) | handle_info.nFileIndexLow
        return FileReference(handle_info.dwVolumeSerialNumber, index, handle_info.nNumberOfLinks)
    finally:
        kernel32.CloseHandle(handle)
