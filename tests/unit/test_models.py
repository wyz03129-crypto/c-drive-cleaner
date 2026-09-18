from __future__ import annotations

from datetime import UTC
from pathlib import Path

from cdrive_cleaner.domain import (
    ActionKind,
    ActionPlan,
    FileIdentity,
    Finding,
    PlannedAction,
    ProductStage,
    RiskLevel,
)
from cdrive_cleaner.domain.errors import CleanerError, SafetyDeniedError, UnsupportedPlatformError


def test_risk_levels_are_ordered_without_implying_permission() -> None:
    assert list(RiskLevel) == [
        RiskLevel.SAFE,
        RiskLevel.CAUTION,
        RiskLevel.MANUAL,
        RiskLevel.SYSTEM,
        RiskLevel.PROTECTED,
    ]
    assert RiskLevel.RECOMMENDED is RiskLevel.CAUTION


def test_m0_and_closed_action_vocabulary() -> None:
    assert ProductStage.ENGINEERING_SKELETON == "M0"
    assert ActionKind.ADVISORY_ONLY == "advisory_only"


def test_expected_failures_share_one_public_base_error() -> None:
    assert issubclass(SafetyDeniedError, CleanerError)
    assert issubclass(UnsupportedPlatformError, CleanerError)


def test_action_plan_is_immutable_and_sums_estimates() -> None:
    identity = FileIdentity(1, 2, 123, 4, 5)
    finding = Finding(
        "temp",
        "1.0.0",
        Path("/cache/a.tmp"),
        Path("/cache"),
        RiskLevel.SAFE,
        ActionKind.DIRECT_FILE_DELETE,
        identity,
    )
    plan = ActionPlan.create(
        plan_id="abc", policy_version="2.0.0", actions=(PlannedAction(finding),)
    )
    assert plan.estimated_bytes == 123
    assert plan.created_at.tzinfo is UTC
