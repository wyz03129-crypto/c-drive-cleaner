"""Build immutable plans from findings without granting execution authority."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from cdrive_cleaner.domain import ActionKind, ActionPlan, Finding, PlannedAction
from cdrive_cleaner.rules import RuleRegistry
from cdrive_cleaner.safety.authorization import SafetyPolicy


class CleanupPlanner:
    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    def build(self, findings: Iterable[Finding]) -> ActionPlan:
        actions: list[PlannedAction] = []
        for finding in findings:
            rule = self._registry.resolve(finding.rule_id, finding.rule_version)
            if rule is None:
                continue
            if (
                finding.risk is not rule.risk
                or finding.action_kind is not rule.action_kind
                or finding.scope_root not in rule.roots
            ):
                continue
            if finding.action_kind is ActionKind.DIRECT_FILE_DELETE:
                actions.append(PlannedAction(finding, rule.requires_elevation))
        return ActionPlan.create(
            plan_id=uuid.uuid4().hex,
            policy_version=SafetyPolicy.POLICY_VERSION,
            actions=tuple(actions),
        )
