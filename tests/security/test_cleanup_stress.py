from pathlib import Path

from cdrive_cleaner.domain import ActionKind, Finding, PlannedAction, RiskLevel
from cdrive_cleaner.executors import DirectFileDeleteExecutor, ExecutionStatus
from cdrive_cleaner.safety import SafetyPolicy, capture_identity


def test_twenty_cleanup_cycles_remain_confined_to_allowlisted_cache(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    protected = tmp_path / "keep.txt"
    protected.write_text("keep", encoding="utf-8")
    executor = DirectFileDeleteExecutor(SafetyPolicy([scope], [protected.parent / "protected"]))

    for cycle in range(20):
        target = scope / f"cycle-{cycle}.tmp"
        target.write_bytes(b"x" * 4096)
        action = PlannedAction(
            Finding(
                "stress_temp",
                "1.0.0",
                target,
                scope,
                RiskLevel.SAFE,
                ActionKind.DIRECT_FILE_DELETE,
                capture_identity(target),
            )
        )
        result = executor.execute(action, dry_run=False)
        assert result.status is ExecutionStatus.DELETED
        assert not target.exists()
        assert protected.read_text(encoding="utf-8") == "keep"
