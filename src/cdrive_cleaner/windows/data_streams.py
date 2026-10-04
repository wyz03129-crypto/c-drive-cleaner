"""Reject cache files whose named NTFS streams would be lost in a plain backup."""

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class _Stream(ctypes.Structure):
    _fields_ = [("size", ctypes.c_longlong), ("name", wintypes.WCHAR * 296)]


def require_unnamed_data_only(path: Path) -> None:
    if os.name != "nt":
        raise OSError("stream inspection requires Windows")
    if getattr(path.stat(), "st_file_attributes", 0) & 0x4000:
        raise OSError("encrypted files are not supported by cache recovery")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.FindFirstStreamW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(_Stream),
        wintypes.DWORD,
    ]
    api.FindFirstStreamW.restype = wintypes.HANDLE
    api.FindNextStreamW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Stream)]
    api.FindNextStreamW.restype = wintypes.BOOL
    api.FindClose.argtypes = [wintypes.HANDLE]
    result = _Stream()
    handle = api.FindFirstStreamW(str(path), 0, ctypes.byref(result), 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        while True:
            if result.name != "::$DATA":
                raise OSError("named data streams are not supported by cache recovery")
            if not api.FindNextStreamW(handle, ctypes.byref(result)):
                if ctypes.get_last_error() != 38:
                    raise ctypes.WinError(ctypes.get_last_error())
                return
    finally:
        api.FindClose(handle)
