"""Link, junction, mount, and reparse-point checks."""

from __future__ import annotations

import os
from pathlib import Path

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def is_reparse_point(path: Path) -> bool:
    """Treat unreadable path metadata as unsafe."""

    try:
        if path.is_symlink():
            return True
        is_junction = getattr(os.path, "isjunction", None)
        if is_junction is not None and is_junction(path):
            return True
        details = os.stat(path, follow_symlinks=False)
        attributes = getattr(details, "st_file_attributes", 0)
        return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True


def chain_contains_reparse(target: Path, scope: Path) -> bool:
    """Check every component from target through its authorized scope."""

    current = target
    while True:
        if is_reparse_point(current):
            return True
        if same_path(current, scope):
            return False
        parent = current.parent
        if parent == current or not same_or_within(parent, scope):
            return True
        current = parent


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.path.realpath(os.fspath(path))))


def same_path(left: Path, right: Path) -> bool:
    return path_key(left) == path_key(right)


def same_or_within(child: Path, parent: Path) -> bool:
    child_key = path_key(child)
    parent_key = path_key(parent)
    try:
        return os.path.commonpath((child_key, parent_key)) == parent_key
    except ValueError:
        return False


def strictly_within(child: Path, parent: Path) -> bool:
    return not same_path(child, parent) and same_or_within(child, parent)
