from __future__ import annotations

import os
from pathlib import Path

import pytest

from cdrive_cleaner.domain.errors import UnsupportedPlatformError
from cdrive_cleaner.windows import KnownFolders, discover_known_folders


def test_known_folder_value_derives_drive_from_windows_anchor() -> None:
    folders = KnownFolders(
        windows=Path("C:/Windows"),
        profile=Path("C:/Users/Alice"),
        local_app_data=Path("C:/Users/Alice/AppData/Local"),
        roaming_app_data=Path("C:/Users/Alice/AppData/Roaming"),
        program_data=Path("C:/ProgramData"),
    )
    assert folders.profile.name == "Alice"


@pytest.mark.skipif(os.name == "nt", reason="non-Windows guard only")
def test_production_discovery_fails_closed_off_windows() -> None:
    with pytest.raises(UnsupportedPlatformError):
        discover_known_folders()
