from __future__ import annotations

from cdrive_cleaner.domain import ActionKind, ProductStage, RiskLevel
from cdrive_cleaner.domain.errors import CleanerError, SafetyDeniedError, UnsupportedPlatformError


def test_risk_levels_are_ordered_without_implying_permission() -> None:
    assert list(RiskLevel) == [
        RiskLevel.SAFE,
        RiskLevel.RECOMMENDED,
        RiskLevel.REVIEW,
        RiskLevel.ADVANCED,
        RiskLevel.PROTECTED,
    ]


def test_m0_and_closed_action_vocabulary() -> None:
    assert ProductStage.ENGINEERING_SKELETON == "M0"
    assert ActionKind.ADVISORY_ONLY == "advisory_only"


def test_expected_failures_share_one_public_base_error() -> None:
    assert issubclass(SafetyDeniedError, CleanerError)
    assert issubclass(UnsupportedPlatformError, CleanerError)
