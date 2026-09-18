"""Execute immutable plans and produce verifiable aggregate receipts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from cdrive_cleaner.domain import ActionPlan, CleanupReceipt
from cdrive_cleaner.executors import DirectFileDeleteExecutor

FreeSpaceReader = Callable[[Path], int]


class CancellationSignal(Protocol):
    """Minimal structural interface accepted from scan/UI cancellation tokens."""

    @property
    def cancelled(self) -> bool: ...


class CleanupCoordinator:
    def __init__(
        self,
        executor: DirectFileDeleteExecutor,
        *,
        free_space_reader: FreeSpaceReader,
    ) -> None:
        self._executor = executor
        self._free_space_reader = free_space_reader

    def execute(
        self,
        plan: ActionPlan,
        *,
        volume: Path,
        dry_run: bool,
        token: CancellationSignal | None = None,
    ) -> CleanupReceipt:
        started = datetime.now(UTC)
        before = self._free_space_reader(volume)
        outcomes = []
        for action in plan.actions:
            if token is not None and token.cancelled:
                break
            outcomes.append(self._executor.execute(action, dry_run=dry_run))
        results = tuple(outcomes)
        after = self._free_space_reader(volume)
        return CleanupReceipt(
            plan.plan_id,
            dry_run,
            started,
            datetime.now(UTC),
            plan.estimated_bytes,
            sum(result.bytes_processed for result in results),
            before,
            after,
            results,
            token.cancelled if token is not None else False,
        )
