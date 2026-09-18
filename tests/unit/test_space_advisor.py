from pathlib import Path

import pytest

from cdrive_cleaner.analysis import advise_path
from cdrive_cleaner.domain import RiskLevel


@pytest.mark.parametrize(
    ("relative", "risk"),
    [
        ("hiberfil.sys", RiskLevel.SYSTEM),
        ("Windows/WinSxS/payload.bin", RiskLevel.PROTECTED),
        ("$WinREAgent/Scratch/update.wim", RiskLevel.SYSTEM),
        ("Users/Alice/Downloads/archive.zip", RiskLevel.MANUAL),
        ("Program Files/App/app.exe", RiskLevel.MANUAL),
        ("Users/Alice/project/.venv/lib.dll", RiskLevel.MANUAL),
        ("Users/Alice/AppData/Roaming/App/data.bin", RiskLevel.MANUAL),
        ("unknown.bin", RiskLevel.MANUAL),
    ],
)
def test_advice_never_authorizes_large_paths(relative: str, risk: RiskLevel) -> None:
    root = Path("C:/")
    advice = advise_path(
        root / relative,
        system_drive=root,
        profile=root / "Users/Alice",
    )
    assert advice.risk is risk


def test_virtual_disk_is_system_managed() -> None:
    advice = advise_path(
        Path("C:/Users/Alice/AppData/Local/Docker/data.vhdx"),
        system_drive=Path("C:/"),
        profile=Path("C:/Users/Alice"),
    )
    assert advice.risk is RiskLevel.SYSTEM
