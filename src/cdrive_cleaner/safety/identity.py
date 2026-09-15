"""Filesystem identity capture shared by scanners, planners, and executors."""

from __future__ import annotations

import os
from pathlib import Path

from cdrive_cleaner.domain import FileIdentity
from cdrive_cleaner.windows.file_identity import file_reference


def capture_identity(path: Path) -> FileIdentity:
    """Capture identity without following a final symbolic link."""

    details = os.stat(path, follow_symlinks=False)
    reference = file_reference(path, details)
    return FileIdentity(
        device=reference.volume,
        inode=reference.index,
        size=details.st_size,
        modified_ns=details.st_mtime_ns,
        mode=details.st_mode,
    )
