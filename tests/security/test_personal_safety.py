from __future__ import annotations

import os
import time
from dataclasses import replace
from pathlib import Path

import pytest

from cdrive_cleaner.analysis import FastScanner
from cdrive_cleaner.app import CleanupPlanner
from cdrive_cleaner.domain import ActionKind, Finding, PlannedAction, RiskLevel
from cdrive_cleaner.executors import DirectFileDeleteExecutor, ExecutionStatus
from cdrive_cleaner.rules import RuleRegistry, RuleSpec, build_m2_registry
from cdrive_cleaner.safety import SafetyPolicy, capture_identity
from cdrive_cleaner.windows import KnownFolders


def setup_rule(tmp_path: Path, **changes: object) -> tuple[Path, RuleSpec]:
    root = tmp_path / "cache"
    root.mkdir()
    target = root / "cache.tmp"
    target.write_bytes(b"cache")
    rule = RuleSpec("test", "1.0.0", "Test", RiskLevel.SAFE, ActionKind.DIRECT_FILE_DELETE, (root,))
    return target, replace(rule, **changes)


def finding(target: Path, rule: RuleSpec) -> Finding:
    return Finding(
        rule.rule_id,
        rule.version,
        target,
        rule.roots[0],
        rule.risk,
        rule.action_kind,
        capture_identity(target),
    )


def test_recent_temp_is_rejected_by_scan_plan_and_executor(tmp_path: Path) -> None:
    target, rule = setup_rule(tmp_path, min_age_days=7)
    registry = RuleRegistry([rule])
    assert not FastScanner(registry).scan().findings
    assert not CleanupPlanner(registry).build([finding(target, rule)]).actions
    action = PlannedAction(finding(target, rule), min_age_days=7)
    result = DirectFileDeleteExecutor(SafetyPolicy(rule.roots, ())).execute(action, dry_run=False)
    assert result.error_code == "rule_predicate"
    assert target.read_bytes() == b"cache"


def test_old_temp_can_be_cleaned_through_production_registry(tmp_path: Path) -> None:
    target, rule = setup_rule(tmp_path, min_age_days=7)
    old = time.time() - 8 * 86400
    os.utime(target, (old, old))
    registry = RuleRegistry([rule])
    plan = CleanupPlanner(registry).build(FastScanner(registry).scan().findings)
    assert len(plan.actions) == 1
    result = DirectFileDeleteExecutor(SafetyPolicy(rule.roots, ()), registry=registry).execute(
        plan.actions[0], dry_run=False
    )
    assert result.status is ExecutionStatus.DELETED
    assert not target.exists()


@pytest.mark.parametrize("mode", ["running", "unknown", "closed"])
def test_application_state_is_enforced_at_execution(tmp_path: Path, mode: str) -> None:
    target, rule = setup_rule(tmp_path, blocking_processes=("app.exe",))
    registry = RuleRegistry([rule])
    action = CleanupPlanner(registry).build([finding(target, rule)]).actions[0]

    def processes(names: tuple[str, ...]) -> bool:
        assert names == ("app.exe",)
        if mode == "unknown":
            raise OSError("unavailable")
        return mode == "running"

    result = DirectFileDeleteExecutor(
        SafetyPolicy(rule.roots, ()), registry=registry, process_checker=processes
    ).execute(action, dry_run=False)
    assert target.exists() == (mode != "closed")
    assert result.status is (
        ExecutionStatus.DELETED if mode == "closed" else ExecutionStatus.SKIPPED
    )


def test_forged_action_cannot_remove_rule_constraints(tmp_path: Path) -> None:
    target, rule = setup_rule(tmp_path, blocking_processes=("app.exe",))
    registry = RuleRegistry([rule])
    action = PlannedAction(finding(target, rule))
    result = DirectFileDeleteExecutor(SafetyPolicy(rule.roots, ()), registry=registry).execute(
        action, dry_run=False
    )
    assert result.error_code == "rule_changed"
    assert target.exists()


def test_name_predicate_applies_even_to_handmade_findings(tmp_path: Path) -> None:
    target, rule = setup_rule(tmp_path, include_patterns=("thumbcache_*.db",))
    registry = RuleRegistry([rule])
    assert not CleanupPlanner(registry).build([finding(target, rule)]).actions
    action = PlannedAction(finding(target, rule), include_patterns=rule.include_patterns)
    result = DirectFileDeleteExecutor(SafetyPolicy(rule.roots, ())).execute(action, dry_run=False)
    assert result.error_code == "rule_predicate"
    assert target.exists()


def test_office_and_maven_are_analysis_only(tmp_path: Path) -> None:
    folders = KnownFolders(
        tmp_path / "Windows",
        tmp_path / "User",
        tmp_path / "Local",
        tmp_path / "Roaming",
        tmp_path / "ProgramData",
    )
    registry = build_m2_registry(folders)
    for name in ("office_cache", "maven_cache"):
        rule = registry.resolve(name, "2.0.0")
        assert rule is not None and rule.risk is RiskLevel.MANUAL
        target = rule.roots[0] / "unsynced.bin"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"irreplaceable")
        assert not CleanupPlanner(registry).build([finding(target, rule)]).actions
    assert all(not r.default_selected for r in registry.all() if r.risk >= RiskLevel.CAUTION)


def test_epic_scope_excludes_games_and_saves(tmp_path: Path) -> None:
    folders = KnownFolders(
        tmp_path / "Windows",
        tmp_path / "User",
        tmp_path / "Local",
        tmp_path / "Roaming",
        tmp_path / "ProgramData",
    )
    rule = build_m2_registry(folders).resolve("epic_webcache", "2.0.0")
    assert rule is not None
    assert {p.name for p in rule.roots} == {"webcache", "webcache_4147", "webcache_4430"}
    assert not rule.default_selected and rule.blocking_processes


@pytest.mark.skipif(os.name != "nt", reason="Windows handle API")
def test_handle_delete_rejects_last_moment_replacement(tmp_path: Path) -> None:
    from cdrive_cleaner.executors.handle_delete import delete_verified_file

    target, _ = setup_rule(tmp_path)
    identity = capture_identity(target)
    target.rename(target.with_suffix(".saved"))
    target.write_bytes(b"replacement")
    with pytest.raises(OSError):
        delete_verified_file(target, identity)
    assert target.read_bytes() == b"replacement"


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing and hard-link semantics")
def test_handle_delete_rejects_live_writer_and_hardlinks(tmp_path: Path) -> None:
    from cdrive_cleaner.executors.handle_delete import delete_verified_file

    target, _ = setup_rule(tmp_path)
    identity = capture_identity(target)
    with target.open("r+b"), pytest.raises(OSError):
        delete_verified_file(target, identity)
    link = target.with_suffix(".linked")
    os.link(target, link)
    with pytest.raises(OSError):
        delete_verified_file(target, identity)
    assert target.exists() and link.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics")
def test_executor_explains_writer_lock_as_in_use(tmp_path: Path) -> None:
    target, rule = setup_rule(tmp_path)
    registry = RuleRegistry([rule])
    action = CleanupPlanner(registry).build([finding(target, rule)]).actions[0]
    with target.open("r+b"):
        result = DirectFileDeleteExecutor(SafetyPolicy(rule.roots, ()), registry=registry).execute(
            action, dry_run=False
        )
    assert result.error_code == "file_in_use"
    assert target.exists()
