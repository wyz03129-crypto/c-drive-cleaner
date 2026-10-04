"""Read-only process discovery. Unknown state blocks application-specific cleanup."""

from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def process_names() -> frozenset[str]:
    """Use Toolhelp without invoking a shell or collecting command lines."""
    if os.name != "nt":
        raise OSError("process inspection requires Windows")
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        method = getattr(api, name)
        method.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        method.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        if not api.Process32FirstW(snapshot, ctypes.byref(entry)):
            raise ctypes.WinError(ctypes.get_last_error())
        names = set()
        while True:
            if entry.th32ProcessID != os.getpid():
                names.add(entry.szExeFile.casefold())
            if not api.Process32NextW(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise ctypes.WinError(ctypes.get_last_error())
                break
        return frozenset(names)
    finally:
        api.CloseHandle(snapshot)


class ProcessGuard:
    """Refresh at most once per second; file-handle checks still run for every file."""

    def __init__(self) -> None:
        self._names: frozenset[str] = frozenset()
        self._until = 0.0
        self._lock = threading.Lock()

    def __call__(self, names: tuple[str, ...]) -> bool:
        if not names:
            return False
        with self._lock:
            if time.monotonic() >= self._until:
                self._names = process_names()
                self._until = time.monotonic() + 1.0
            return bool(self._names.intersection(name.casefold() for name in names))
