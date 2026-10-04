"""Windows deletion through the same validated handle, with no pathname fallback."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from cdrive_cleaner.domain import FileIdentity
from cdrive_cleaner.safety.reparse import chain_contains_reparse
from cdrive_cleaner.windows.file_identity import _ByHandleFileInformation


class _Disposition(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BOOL)]


def delete_verified_file(path: Path, expected: FileIdentity) -> None:
    """Reject writers, links, replacement identities and unexpected final paths.

    Ancestor revalidation reduces parent-directory races but is not a proof against
    a hostile administrator. We never fall back to path deletion on Windows errors.
    """
    if os.name != "nt":
        os.remove(path)
        return
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    api.CreateFileW.restype = wintypes.HANDLE
    api.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    api.GetFileInformationByHandle.restype = wintypes.BOOL
    api.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    api.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    api.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    api.SetFileInformationByHandle.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    # DELETE | FILE_READ_ATTRIBUTES; share-read only, OPEN_EXISTING,
    # FILE_FLAG_OPEN_REPARSE_POINT. A concurrent writer makes the open fail.
    handle = api.CreateFileW(str(path), 0x10080, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = _ByHandleFileInformation()
        if not api.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        modified = (
            (info.ftLastWriteTime.dwHighDateTime << 32) | info.ftLastWriteTime.dwLowDateTime
        ) * 100 - 11644473600000000000
        if (
            info.dwFileAttributes & (0x400 | 0x10)
            or info.nNumberOfLinks != 1
            or info.dwVolumeSerialNumber != expected.device
            or (info.nFileIndexHigh << 32) | info.nFileIndexLow != expected.inode
            or (info.nFileSizeHigh << 32) | info.nFileSizeLow != expected.size
            or modified != expected.modified_ns
        ):
            raise OSError("handle_identity_changed_or_hardlink")
        buffer = ctypes.create_unicode_buffer(32768)
        length = api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not 0 < length < len(buffer):
            raise OSError("handle_path_unavailable")
        actual = buffer.value.removeprefix("\\\\?\\")
        if os.path.normcase(actual) != os.path.normcase(os.path.abspath(path)):
            raise OSError("handle_path_changed")
        if chain_contains_reparse(path, Path(path.anchor)):
            raise OSError("path_chain_changed")
        disposition = _Disposition(True)
        if not api.SetFileInformationByHandle(
            handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        api.CloseHandle(handle)
