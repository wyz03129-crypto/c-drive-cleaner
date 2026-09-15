"""Common executor contract used by cleanup orchestration."""

from __future__ import annotations

from typing import Protocol

from cdrive_cleaner.domain import PlannedAction

from .models import ExecutionResult


class ActionExecutor(Protocol):
    """Every executor consumes one immutable action and returns structured data."""

    def execute(self, action: PlannedAction, *, dry_run: bool) -> ExecutionResult: ...
