"""Direct-file executor with mandatory execution-time reauthorization."""

from __future__ import annotations

import os

from cdrive_cleaner.domain import ActionKind, PlannedAction
from cdrive_cleaner.safety import AuthorizationCode, SafetyPolicy, capture_identity

from .models import ExecutionResult, ExecutionStatus


class DirectFileDeleteExecutor:
    def __init__(self, policy: SafetyPolicy) -> None:
        self._policy = policy

    def execute(self, action: PlannedAction, *, dry_run: bool) -> ExecutionResult:
        finding = action.finding
        if finding.action_kind is not ActionKind.DIRECT_FILE_DELETE:
            return ExecutionResult(
                ExecutionStatus.DENIED,
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
                authorization_code=decision.code,
            )
        try:
            final_identity = capture_identity(decision.normalized.absolute)
            if final_identity != finding.identity:
                return ExecutionResult(
                    ExecutionStatus.DENIED,
                    authorization_code=AuthorizationCode.IDENTITY_CHANGED,
                )
            if dry_run:
                return ExecutionResult(ExecutionStatus.SIMULATED, final_identity.size)
            os.remove(decision.normalized.absolute)
            return ExecutionResult(ExecutionStatus.DELETED, final_identity.size)
        except FileNotFoundError:
            return ExecutionResult(ExecutionStatus.SKIPPED, error_code="not_found")
        except PermissionError:
            return ExecutionResult(ExecutionStatus.SKIPPED, error_code="permission_denied")
        except OSError:
            return ExecutionResult(ExecutionStatus.SKIPPED, error_code="os_error")
