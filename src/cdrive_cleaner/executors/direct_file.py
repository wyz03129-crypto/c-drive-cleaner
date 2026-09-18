"""Direct-file executor with mandatory execution-time reauthorization."""

from __future__ import annotations

import os
from collections.abc import Callable

from cdrive_cleaner.domain import ActionKind, PlannedAction
from cdrive_cleaner.safety import AuthorizationCode, SafetyPolicy, capture_identity

from .models import ExecutionResult, ExecutionStatus


class DirectFileDeleteExecutor:
    def __init__(
        self, policy: SafetyPolicy, *, elevated_checker: Callable[[], bool] | None = None
    ) -> None:
        self._policy = policy
        self._elevated_checker = elevated_checker or (lambda: False)

    def execute(self, action: PlannedAction, *, dry_run: bool) -> ExecutionResult:
        finding = action.finding
        attempted = finding.identity.size
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
            os.remove(decision.normalized.absolute)
            return ExecutionResult(
                ExecutionStatus.DELETED,
                final_identity.size,
                final_identity.size,
            )
        except FileNotFoundError:
            return ExecutionResult(
                ExecutionStatus.SKIPPED, bytes_attempted=attempted, error_code="not_found"
            )
        except PermissionError:
            return ExecutionResult(
                ExecutionStatus.SKIPPED,
                bytes_attempted=attempted,
                error_code="permission_denied",
            )
        except OSError:
            return ExecutionResult(
                ExecutionStatus.SKIPPED, bytes_attempted=attempted, error_code="os_error"
            )
