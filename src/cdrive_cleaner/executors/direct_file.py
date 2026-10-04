"""Direct-file executor with mandatory execution-time reauthorization."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cdrive_cleaner.domain import ActionKind, FileIdentity, PlannedAction
from cdrive_cleaner.rules import RuleRegistry
from cdrive_cleaner.rules.predicates import matches_file
from cdrive_cleaner.safety import AuthorizationCode, SafetyPolicy, capture_identity
from cdrive_cleaner.windows.processes import ProcessGuard

from .handle_delete import delete_verified_file
from .models import ExecutionResult, ExecutionStatus


class DirectFileDeleteExecutor:
    def __init__(
        self,
        policy: SafetyPolicy,
        *,
        elevated_checker: Callable[[], bool] | None = None,
        registry: RuleRegistry | None = None,
        process_checker: Callable[[tuple[str, ...]], bool] | None = None,
        verified_delete: Callable[[Path, FileIdentity], None] = delete_verified_file,
    ) -> None:
        self._policy = policy
        self._elevated_checker = elevated_checker or (lambda: False)
        self._registry = registry
        self._process_checker = process_checker or ProcessGuard()
        self._verified_delete = verified_delete

    def execute(self, action: PlannedAction, *, dry_run: bool) -> ExecutionResult:
        finding = action.finding
        attempted = finding.identity.size
        if self._registry is not None:
            rule = self._registry.resolve(finding.rule_id, finding.rule_version)
            if rule is None or (
                finding.scope_root not in rule.roots
                or finding.risk != rule.risk
                or finding.action_kind != rule.action_kind
                or action.requires_elevation != rule.requires_elevation
                or action.include_patterns != rule.include_patterns
                or action.min_age_days != rule.min_age_days
                or action.blocking_processes != rule.blocking_processes
            ):
                return ExecutionResult(
                    ExecutionStatus.DENIED, bytes_attempted=attempted, error_code="rule_changed"
                )
        if not matches_file(
            finding.path, finding.identity, action.include_patterns, action.min_age_days
        ):
            return ExecutionResult(
                ExecutionStatus.DENIED, bytes_attempted=attempted, error_code="rule_predicate"
            )
        try:
            if self._process_checker(action.blocking_processes):
                return ExecutionResult(
                    ExecutionStatus.SKIPPED,
                    bytes_attempted=attempted,
                    error_code="application_running",
                )
        except OSError:
            return ExecutionResult(
                ExecutionStatus.SKIPPED,
                bytes_attempted=attempted,
                error_code="process_state_unknown",
            )
        if action.requires_elevation and not self._elevated_checker():
            return ExecutionResult(
                ExecutionStatus.DENIED,
                bytes_attempted=attempted,
                error_code="elevation_required",
            )
        if finding.action_kind is not ActionKind.DIRECT_FILE_DELETE:
            return ExecutionResult(
                ExecutionStatus.DENIED,
                bytes_attempted=attempted,
                authorization_code=AuthorizationCode.RISK_NOT_DIRECT,
            )
        decision = self._policy.authorize(
            finding.path,
            scope_root=finding.scope_root,
            risk=finding.risk,
            expected_identity=finding.identity,
        )
        if not decision.allowed or decision.normalized is None:
            return ExecutionResult(
                ExecutionStatus.DENIED,
                bytes_attempted=attempted,
                authorization_code=decision.code,
            )
        try:
            final_identity = capture_identity(decision.normalized.absolute)
            if final_identity != finding.identity:
                return ExecutionResult(
                    ExecutionStatus.DENIED,
                    bytes_attempted=attempted,
                    authorization_code=AuthorizationCode.IDENTITY_CHANGED,
                )
            if dry_run:
                return ExecutionResult(
                    ExecutionStatus.SIMULATED,
                    final_identity.size,
                    final_identity.size,
                )
            self._verified_delete(decision.normalized.absolute, final_identity)
            return ExecutionResult(
                ExecutionStatus.DELETED,
                final_identity.size,
                final_identity.size,
            )
        except FileNotFoundError:
            return ExecutionResult(
                ExecutionStatus.SKIPPED, bytes_attempted=attempted, error_code="not_found"
            )
        except PermissionError as error:
            return ExecutionResult(
                ExecutionStatus.SKIPPED,
                bytes_attempted=attempted,
                error_code="file_in_use"
                if getattr(error, "winerror", None) in (32, 33)
                else "permission_denied",
            )
        except OSError as error:
            return ExecutionResult(
                ExecutionStatus.SKIPPED,
                bytes_attempted=attempted,
                error_code="file_in_use"
                if getattr(error, "winerror", None) in (32, 33)
                else "os_error",
            )
