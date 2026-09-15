from __future__ import annotations

from pathlib import Path

import pytest

from cdrive_cleaner import __version__
from cdrive_cleaner.cli import main
from cdrive_cleaner.domain import ActionKind, RiskLevel
from cdrive_cleaner.executors import RecycleBinInfo
from cdrive_cleaner.rules import RuleRegistry, RuleSpec
from cdrive_cleaner.safety import SafetyPolicy
from cdrive_cleaner.windows import KnownFolders


def test_status_reports_m2(capsys: object) -> None:
    assert main(["status"]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "M3" in output
    assert "已启用" in output


def test_package_version_matches_alpha_line() -> None:
    assert __version__ == "2.0.0a0"


def test_no_command_prints_help_without_filesystem_work(capsys: object) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "usage:" in output


def fake_runtime(tmp_path: Path) -> tuple[KnownFolders, RuleRegistry, SafetyPolicy]:
    cache = tmp_path / "cache"
    cache.mkdir()
    rule = RuleSpec(
        "test_cache",
        "1.0.0",
        "Test cache",
        RiskLevel.SAFE,
        ActionKind.DIRECT_FILE_DELETE,
        (cache,),
    )
    registry = RuleRegistry((rule,))
    folders = KnownFolders(tmp_path, tmp_path, tmp_path, tmp_path, tmp_path)
    return folders, registry, SafetyPolicy((cache,), ())


def test_scan_and_dry_run_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: object
) -> None:
    folders, registry, policy = fake_runtime(tmp_path)
    (registry.all()[0].roots[0] / "item.tmp").write_bytes(b"123")
    monkeypatch.setattr("cdrive_cleaner.cli._runtime", lambda: (folders, registry, policy))
    assert main(["scan"]) == 0
    assert "test_cache" in capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(["clean", "--rule", "test_cache"]) == 0
    assert "Dry Run" in capsys.readouterr().out  # type: ignore[attr-defined]


def test_real_clean_requires_confirmation_and_deletes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folders, registry, policy = fake_runtime(tmp_path)
    target = registry.all()[0].roots[0] / "item.tmp"
    target.write_bytes(b"123")
    monkeypatch.setattr("cdrive_cleaner.cli._runtime", lambda: (folders, registry, policy))
    with pytest.raises(SystemExit):
        main(["clean", "--rule", "test_cache", "--execute"])
    assert target.exists()
    assert main(["clean", "--rule", "test_cache", "--execute", "--confirm", "CLEAN"]) == 0
    assert not target.exists()


def test_unknown_rule_is_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runtime = fake_runtime(tmp_path)
    monkeypatch.setattr("cdrive_cleaner.cli._runtime", lambda: runtime)
    with pytest.raises(SystemExit):
        main(["clean", "--rule", "made_up"])


def test_recycle_bin_has_independent_query_and_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: object
) -> None:
    folders, _, _ = fake_runtime(tmp_path)

    class FakeRecycleBin:
        emptied = False

        def query(self, _volume: Path) -> RecycleBinInfo:
            return RecycleBinInfo(2, 2048)

        def empty(self, _volume: Path, *, confirmation: str) -> None:
            assert confirmation == "EMPTY RECYCLE BIN"
            self.emptied = True

    fake = FakeRecycleBin()
    monkeypatch.setattr("cdrive_cleaner.cli.discover_known_folders", lambda: folders)
    monkeypatch.setattr("cdrive_cleaner.cli.RecycleBinExecutor", lambda: fake)
    assert main(["recycle-bin"]) == 0
    assert "2 项" in capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(["recycle-bin", "--empty", "--confirm", "EMPTY RECYCLE BIN"]) == 0
    assert fake.emptied


def test_analyze_and_cached_result_are_read_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: object
) -> None:
    class AnalysisFolders:
        system_drive = tmp_path
        local_app_data = tmp_path / "Local"

    folders = AnalysisFolders()
    data = tmp_path / "Users" / "Alice"
    data.mkdir(parents=True)
    target = data / "large.bin"
    target.write_bytes(b"x" * 32)
    monkeypatch.setattr("cdrive_cleaner.cli.discover_known_folders", lambda: folders)
    assert main(["analyze", "--top", "2"]) == 0
    assert "最大目录" in capsys.readouterr().out  # type: ignore[attr-defined]
    assert target.exists()
    assert main(["analyze", "--cached"]) == 0
    assert "缓存快照时间" in capsys.readouterr().out  # type: ignore[attr-defined]
