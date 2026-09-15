"""Centralized path normalization and containment helpers."""

from __future__ import annotations

import os
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class NormalizedPath:
    """The path forms used by the safety decision."""

    original: str
    expanded: str
    absolute: str
    real: str


def get_windows_directory() -> Path | None:
    """Read the Windows directory from the OS API instead of process variables."""

    if os.name != "nt":
        return None
    buffer = ctypes.create_unicode_buffer(32768)
    try:
        length = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
    except (AttributeError, OSError):
        return None
    return Path(buffer.value) if 0 < length < len(buffer) else None


def get_shell_folder(csidl: int) -> Path | None:
    """Read a Windows shell folder by CSIDL without trusting environment text."""

    if os.name != "nt":
        return None
    buffer = ctypes.create_unicode_buffer(32768)
    try:
        result = ctypes.windll.shell32.SHGetFolderPathW(
            None, csidl, None, 0, buffer
        )
    except (AttributeError, OSError):
        return None
    return Path(buffer.value) if result == 0 and buffer.value else None


def _long_path_name(value: str) -> str:
    """Expand an existing Windows 8.3 short path when the API can resolve it."""

    if os.name != "nt" or not os.path.exists(value):
        return value
    needed = ctypes.windll.kernel32.GetLongPathNameW(value, None, 0)
    if not needed:
        return value
    buffer = ctypes.create_unicode_buffer(needed)
    written = ctypes.windll.kernel32.GetLongPathNameW(value, buffer, needed)
    return buffer.value if written else value


def normalize_path(value: str | os.PathLike[str]) -> NormalizedPath:
    """Return expanded, absolute, and canonical forms without modifying disk."""

    original = os.fspath(value)
    expanded = os.path.expanduser(os.path.expandvars(original))
    absolute = os.path.abspath(os.path.normpath(expanded))
    absolute = _long_path_name(absolute)
    real = os.path.realpath(absolute)
    return NormalizedPath(original, expanded, absolute, real)


def path_key(value: str | os.PathLike[str]) -> str:
    """Return a case-normalized canonical key suitable for Windows comparison."""

    return os.path.normcase(os.path.normpath(os.path.realpath(os.fspath(value))))


def is_within(child: str | os.PathLike[str], parent: str | os.PathLike[str]) -> bool:
    """Return whether *child* is strictly below *parent*."""

    child_key = path_key(child)
    parent_key = path_key(parent)
    if child_key == parent_key:
        return False
    try:
        return os.path.commonpath((child_key, parent_key)) == parent_key
    except ValueError:
        return False


def is_same_or_within(
    child: str | os.PathLike[str], parent: str | os.PathLike[str]
) -> bool:
    """Return whether *child* equals or is below *parent*."""

    child_key = path_key(child)
    parent_key = path_key(parent)
    if child_key == parent_key:
        return True
    try:
        return os.path.commonpath((child_key, parent_key)) == parent_key
    except ValueError:
        return False


def is_unc_path(value: str | os.PathLike[str]) -> bool:
    """Return whether a path is UNC or uses the Windows extended UNC prefix."""

    text = os.fspath(value).replace("/", "\\")
    return text.startswith("\\\\")


def env_path(
    name: str,
    suffix: str = "",
    *,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    """Resolve a directory from an environment mapping, if it is defined."""

    source = os.environ if env is None else env
    raw = source.get(name)
    if not raw:
        return None
    base = Path(os.path.expandvars(os.path.expanduser(raw)))
    return base / suffix if suffix else base


def deduplicate_paths(paths: list[Path]) -> tuple[Path, ...]:
    """Deduplicate paths with Windows-compatible case normalization."""

    seen: set[str] = set()
    result: list[Path] = []
    for item in paths:
        key = os.path.normcase(os.path.abspath(os.fspath(item)))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return tuple(result)
