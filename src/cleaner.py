"""Cleanup orchestration; actual deletes remain inside SafetyGuard."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

from .safety import DeleteResult, DeleteStatus, SafetyGuard
from .scanner import FileCandidate


@dataclass
class CleanupSummary:
    """Aggregate outcomes for one cleanup run."""

    dry_run: bool
    results: list[DeleteResult] = field(default_factory=list)

    @property
    def deleted_count(self) -> int:
        return sum(item.status is DeleteStatus.DELETED for item in self.results)

    @property
    def simulated_count(self) -> int:
        return sum(
            item.status is DeleteStatus.SIMULATED_DELETE for item in self.results
        )

    @property
    def failed_or_skipped_count(self) -> int:
        return sum(
            item.status in {DeleteStatus.DENIED, DeleteStatus.SKIPPED}
            for item in self.results
        )

    @property
    def bytes_affected(self) -> int:
        return sum(item.bytes_affected for item in self.results)


def clean_candidates(
    candidates: Iterable[FileCandidate],
    guard: SafetyGuard,
    *,
    dry_run: bool,
    logger: logging.Logger | None = None,
) -> CleanupSummary:
    """Process each candidate independently so one failure cannot abort a run."""

    summary = CleanupSummary(dry_run=dry_run)
    for candidate in candidates:
        result = guard.delete_file(
            candidate.path,
            scope_root=candidate.scope_root,
            risk=candidate.risk,
            expected_identity=candidate.identity,
            dry_run=dry_run,
        )
        summary.results.append(result)
        if logger:
            logger.info(
                "%s | %s | bytes=%d | %s",
                result.status.value,
                result.path,
                result.bytes_affected,
                result.reason,
            )
    return summary
