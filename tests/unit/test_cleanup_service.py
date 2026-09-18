from pathlib import Path

from cdrive_cleaner.analysis import CancellationToken, FastScanner
from cdrive_cleaner.app import CleanupCoordinator, CleanupPlanner
from cdrive_cleaner.domain import ActionKind, ActionPlan, RiskLevel
from cdrive_cleaner.executors import DirectFileDeleteExecutor, ExecutionStatus
from cdrive_cleaner.rules import RuleRegistry, RuleSpec
from cdrive_cleaner.safety import SafetyPolicy


def setup_plan(tmp_path: Path) -> tuple[Path, ActionPlan, RuleRegistry]:
    root = tmp_path / "cache"
    root.mkdir()
    target = root / "safe.tmp"
    target.write_bytes(b"1234")
    rule = RuleSpec(
        "cache", "1.0.0", "Cache", RiskLevel.SAFE, ActionKind.DIRECT_FILE_DELETE, (root,)
    )
    registry = RuleRegistry((rule,))
    return target, CleanupPlanner(registry).build(FastScanner(registry).scan().findings), registry


def test_cleanup_receipt_separates_three_byte_counts(tmp_path: Path) -> None:
    target, plan, registry = setup_plan(tmp_path)
    observations = iter((100, 103))
    service = CleanupCoordinator(
        DirectFileDeleteExecutor(SafetyPolicy(registry.all()[0].roots, ())),
        free_space_reader=lambda _path: next(observations),
    )
    receipt = service.execute(plan, volume=tmp_path, dry_run=False)
    assert (receipt.estimated_bytes, receipt.processed_bytes, receipt.observed_freed_bytes) == (
        4,
        4,
        3,
    )
    assert receipt.results[0].status is ExecutionStatus.DELETED
    assert receipt.attempted_bytes == 4
    assert receipt.skipped_bytes == 0
    assert not target.exists()


def test_dry_run_receipt_does_not_mutate(tmp_path: Path) -> None:
    target, plan, registry = setup_plan(tmp_path)
    service = CleanupCoordinator(
        DirectFileDeleteExecutor(SafetyPolicy(registry.all()[0].roots, ())),
        free_space_reader=lambda _path: 100,
    )
    receipt = service.execute(plan, volume=tmp_path, dry_run=True)
    assert receipt.dry_run and receipt.observed_freed_bytes == 0
    assert target.exists()


def test_cleanup_cancel_stops_between_atomic_file_actions(tmp_path: Path) -> None:
    target, plan, registry = setup_plan(tmp_path)
    token = CancellationToken()
    token.cancel()
    service = CleanupCoordinator(
        DirectFileDeleteExecutor(SafetyPolicy(registry.all()[0].roots, ())),
        free_space_reader=lambda _path: 100,
    )

    receipt = service.execute(plan, volume=tmp_path, dry_run=False, token=token)

    assert receipt.cancelled
    assert receipt.unattempted_bytes == 4
    assert not receipt.results
    assert target.exists()
