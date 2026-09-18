"""Immutable rule definitions; configuration cannot create authorization roots."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from cdrive_cleaner.domain import ActionKind, RiskLevel

_VERSION = re.compile(r"^[1-9]\d*\.\d+\.\d+$")


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    version: str
    title: str
    risk: RiskLevel
    action_kind: ActionKind
    roots: tuple[Path, ...]
    requires_elevation: bool = False
    include_patterns: tuple[str, ...] = ()
    category: str = "application_cache"
    description: str = "可由系统或应用重新生成的数据"
    scan_strategy: str = "recursive_files"
    recommended_action: str = "关闭相关应用后清理"
    requires_confirmation: bool = False
    confirmation_phrase: str = ""
    default_selected: bool = True

    def __post_init__(self) -> None:
        if not self.rule_id or not self.rule_id.replace("_", "").isalnum():
            raise ValueError("rule_id must contain letters, digits, or underscores")
        if not _VERSION.fullmatch(self.version):
            raise ValueError("rule version must be semantic major.minor.patch")
        if not self.roots:
            raise ValueError("a rule must declare at least one root")
        if any(not root.is_absolute() for root in self.roots):
            raise ValueError("rule roots must be absolute")
        if self.action_kind is ActionKind.DIRECT_FILE_DELETE and self.risk not in {
            RiskLevel.SAFE,
            RiskLevel.CAUTION,
        }:
            raise ValueError("direct deletion is limited to SAFE or RECOMMENDED rules")
        if self.requires_confirmation and not self.confirmation_phrase:
            raise ValueError("confirmation rules require a non-empty phrase")
        if self.risk >= RiskLevel.MANUAL and self.default_selected:
            raise ValueError("MANUAL, SYSTEM, and PROTECTED rules cannot be selected by default")


class RuleRegistry:
    """Read-only lookup of code-owned rules."""

    def __init__(self, rules: Iterable[RuleSpec]) -> None:
        values = tuple(rules)
        keys = [(rule.rule_id, rule.version) for rule in values]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate rule id and version")
        self._rules = {key: rule for key, rule in zip(keys, values, strict=True)}

    def resolve(self, rule_id: str, version: str) -> RuleSpec | None:
        return self._rules.get((rule_id, version))

    def all(self) -> tuple[RuleSpec, ...]:
        return tuple(self._rules.values())
