"""Path normalization with explicit rejection of network and device namespaces."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NormalizedPath:
    original: str
    absolute: Path
    canonical: Path


def has_forbidden_namespace(value: str) -> bool:
    """Reject UNC and device namespaces; permit local Win32 long-path syntax."""

    windows = value.replace("/", "\\")
    folded = windows.casefold()
    if folded.startswith(("\\\\.\\", "\\??\\", "\\device\\")):
        return True
    if folded.startswith("\\\\?\\globalroot") or folded.startswith("\\\\?\\unc\\"):
        return True
    return folded.startswith("\\\\") and not folded.startswith("\\\\?\\")


def normalize_path(value: str | os.PathLike[str]) -> NormalizedPath:
    """Normalize a fully qualified local path without authorizing it."""

    raw = os.fspath(value)
    if not raw or "\x00" in raw:
        raise ValueError("empty path or NUL byte")
    if has_forbidden_namespace(raw):
        raise ValueError("network or device namespace is forbidden")
    if not os.path.isabs(raw):
        raise ValueError("path must be absolute")
    absolute = Path(os.path.abspath(os.path.normpath(raw)))
    canonical = Path(os.path.realpath(absolute))
    return NormalizedPath(raw, absolute, canonical)
