from __future__ import annotations

from pathlib import Path

from cdrive_cleaner.safety import build_default_deny_roots
from cdrive_cleaner.windows import KnownFolders


def test_default_denies_cover_system_and_user_data() -> None:
    folders = KnownFolders(
        windows=Path("C:/Windows"),
        profile=Path("C:/Users/Alice"),
        local_app_data=Path("C:/Users/Alice/AppData/Local"),
        roaming_app_data=Path("C:/Users/Alice/AppData/Roaming"),
        program_data=Path("C:/ProgramData"),
    )
    rendered = {str(path).replace("\\", "/") for path in build_default_deny_roots(folders)}
    assert "C:/Windows/System32" in rendered
    assert "C:/Windows/WinSxS" in rendered
    assert "C:/Users/Alice/Documents" in rendered
    assert "C:/Users/Alice/OneDrive" in rendered
