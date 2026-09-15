from __future__ import annotations

from cdrive_cleaner.windows.elevation import relaunch_elevated


def test_relaunch_elevated_uses_run_as_with_quoted_arguments() -> None:
    calls: list[tuple[str, str]] = []

    def shell_execute(path: str, parameters: str) -> int:
        calls.append((path, parameters))
        return 42

    launched = relaunch_elevated(
        executable=r"C:\Program Files\Cleaner\CDriveCleaner.exe",
        arguments=("--example", "value with spaces"),
        shell_execute=shell_execute,
    )

    assert launched
    assert calls == [
        (r"C:\Program Files\Cleaner\CDriveCleaner.exe", '--example "value with spaces"')
    ]


def test_relaunch_elevated_reports_shell_failure() -> None:
    launched = relaunch_elevated(
        executable="cleaner.exe",
        arguments=(),
        shell_execute=lambda _path, _parameters: 5,
    )

    assert not launched
