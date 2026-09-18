from __future__ import annotations

from pathlib import Path

import pytest

from cdrive_cleaner.domain import ActionKind, RiskLevel
from cdrive_cleaner.rules import RuleRegistry, RuleSpec


def _rule(root: Path, *, version: str = "1.0.0", risk: RiskLevel = RiskLevel.SAFE) -> RuleSpec:
    return RuleSpec(
        "user_temp",
        version,
        "User temp",
        risk,
        ActionKind.DIRECT_FILE_DELETE,
        (root,),
    )


def test_registry_resolves_exact_version(tmp_path: Path) -> None:
    rule = _rule(tmp_path)
    registry = RuleRegistry([rule])
    assert registry.resolve("user_temp", "1.0.0") is rule
    assert registry.resolve("user_temp", "2.0.0") is None
    assert registry.all() == (rule,)


@pytest.mark.parametrize("version", ["", "1", "1.0", "v1.0.0", "0.1.0"])
def test_rule_rejects_invalid_versions(tmp_path: Path, version: str) -> None:
    with pytest.raises(ValueError):
        _rule(tmp_path, version=version)


def test_registry_rejects_duplicate_rule_version(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        RuleRegistry([_rule(tmp_path), _rule(tmp_path)])


def test_direct_delete_rejects_review_risk(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="direct deletion"):
        _rule(tmp_path, risk=RiskLevel.REVIEW)


def test_rule_requires_absolute_roots() -> None:
    with pytest.raises(ValueError, match="absolute"):
        _rule(Path("relative"))


def test_special_confirmation_requires_phrase(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="confirmation"):
        RuleSpec(
            "cache",
            "1.0.0",
            "Cache",
            RiskLevel.CAUTION,
            ActionKind.DIRECT_FILE_DELETE,
            (tmp_path,),
            requires_confirmation=True,
        )
