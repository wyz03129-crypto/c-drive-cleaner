"""Windows current-user DPAPI protection for local recovery manifests."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.c_void_p)]


def protect(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise OSError("recovery manifests require Windows DPAPI")
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    method = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    method.argtypes = [
        ctypes.POINTER(_Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_Blob),
    ]
    method.restype = wintypes.BOOL
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    result = _Blob()
    if not method(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)
