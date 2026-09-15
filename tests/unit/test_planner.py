from __future__ import annotations

from pathlib import Path

from cdrive_cleaner.app import CleanupPlanner
from cdrive_cleaner.domain import ActionKind, Finding, RiskLevel
from cdrive_cleaner.rules import RuleRegistry, RuleSpec
from cdrive_cleaner.safety import capture_identity


def test_planner_accepts_only_exact_registered_finding(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "old.tmp"
    target.write_bytes(b"123")
    rule = RuleSpec(
        "temp",
        "1.0.0",
        "Temp",
        RiskLevel.SAFE,
        ActionKind.DIRECT_FILE_DELETE,
        (scope,),
    )
    exact = Finding(
        rule.rule_id,
        rule.version,
        target,
        scope,
        rule.risk,
        rule.action_kind,
        capture_identity(target),
    )
    wrong_version = Finding(
        rule.rule_id,
        "2.0.0",
        target,
        scope,
        rule.risk,
        rule.action_kind,
        capture_identity(target),
    )
    plan = CleanupPlanner(RuleRegistry([rule])).build([exact, wrong_version])
    assert len(plan.actions) == 1
    assert plan.actions[0].finding == exact
    assert plan.estimated_bytes == 3
