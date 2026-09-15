"""Build protected roots from trusted Windows known-folder results."""

from __future__ import annotations

from pathlib import Path

from cdrive_cleaner.windows import KnownFolders


def build_default_deny_roots(folders: KnownFolders) -> tuple[Path, ...]:
    """Return system and user-data roots that always override cleanup rules."""

    drive = folders.system_drive
    windows = folders.windows
    profile = folders.profile
    return (
        windows / "System32",
        windows / "SysWOW64",
        windows / "WinSxS",
        windows / "Installer",
        windows / "SystemApps",
        drive / "Program Files",
        drive / "Program Files (x86)",
        drive / "ProgramData" / "Microsoft" / "Windows" / "Start Menu",
        drive / "WindowsApps",
        drive / "System Volume Information",
        drive / "Recovery",
        drive / "Boot",
        drive / "EFI",
        profile / "Desktop",
        profile / "Documents",
        profile / "Downloads",
        profile / "Pictures",
        profile / "Videos",
        profile / "Music",
        profile / "OneDrive",
    )
