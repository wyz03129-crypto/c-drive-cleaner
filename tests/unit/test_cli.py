from __future__ import annotations

from cdrive_cleaner import __version__
from cdrive_cleaner.cli import main


def test_status_is_explicitly_non_operational(capsys: object) -> None:
    assert main(["status"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "M0" in output
    assert "尚未启用" in output


def test_package_version_matches_alpha_line() -> None:
    assert __version__ == "2.0.0a0"


def test_no_command_prints_help_without_filesystem_work(capsys: object) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "usage:" in output
