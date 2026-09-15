"""Disk free-space observations used for cleanup verification."""

from __future__ import annotations

import shutil
from pathlib import Path


def free_bytes(path: Path) -> int:
    """Return currently observable free bytes for the volume containing path."""

    return shutil.disk_usage(path).free
