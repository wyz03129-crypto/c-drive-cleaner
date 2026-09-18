from datetime import UTC, datetime
from pathlib import Path

from cdrive_cleaner.domain import CleanupReceipt
from cdrive_cleaner.executors.models import ExecutionResult, ExecutionStatus
from cdrive_cleaner.persistence import append_history, load_history


def test_history_round_trip_uses_only_aggregate_values(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    receipt = CleanupReceipt(
        "plan-1",
        False,
        now,
        now,
        100,
        80,
        1_000,
        1_060,
        (ExecutionResult(ExecutionStatus.DELETED, bytes_processed=80, bytes_attempted=80),),
    )
    path = tmp_path / "history.jsonl"

    append_history(receipt, path)

    entries = load_history(path)
    assert entries[0].observed_freed_bytes == 60
    assert entries[0].succeeded == 1
    assert entries[0].attempted_bytes == 80
    assert "path" not in path.read_text(encoding="utf-8")


def test_history_skips_invalid_lines(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    assert load_history(path) == ()
