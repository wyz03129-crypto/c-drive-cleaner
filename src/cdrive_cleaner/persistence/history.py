"""Privacy-preserving aggregate cleanup history."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cdrive_cleaner.domain import CleanupReceipt
from cdrive_cleaner.executors.models import ExecutionStatus


@dataclass(frozen=True)
class CleanupHistoryEntry:
    plan_id: str
    finished_at: str
    dry_run: bool
    estimated_bytes: int
    processed_bytes: int
    observed_freed_bytes: int
    succeeded: int
    skipped_or_failed: int
    attempted_bytes: int = 0
    skipped_bytes: int = 0
    unattempted_bytes: int = 0
    cancelled: bool = False

    @classmethod
    def from_receipt(cls, receipt: CleanupReceipt) -> CleanupHistoryEntry:
        succeeded = sum(
            result.status in {ExecutionStatus.DELETED, ExecutionStatus.SIMULATED}
            for result in receipt.results
        )
        return cls(
            receipt.plan_id,
            receipt.finished_at.isoformat(),
            receipt.dry_run,
            receipt.estimated_bytes,
            receipt.processed_bytes,
            receipt.observed_freed_bytes,
            succeeded,
            len(receipt.results) - succeeded,
            receipt.attempted_bytes,
            receipt.skipped_bytes,
            receipt.unattempted_bytes,
            receipt.cancelled,
        )


def default_history_path() -> Path:
    return Path.home() / ".c-drive-cleaner" / "cleanup-history.jsonl"


def append_history(receipt: CleanupReceipt, destination: Path | None = None) -> None:
    path = destination or default_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = CleanupHistoryEntry.from_receipt(receipt)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")


def load_history(
    source: Path | None = None, *, limit: int = 100
) -> tuple[CleanupHistoryEntry, ...]:
    path = source or default_history_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    entries: list[CleanupHistoryEntry] = []
    for line in reversed(lines[-limit:]):
        try:
            entries.append(CleanupHistoryEntry(**json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue
    return tuple(entries)
