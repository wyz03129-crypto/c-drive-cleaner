from __future__ import annotations

from pathlib import Path

from cdrive_cleaner.domain import ActionKind, Finding, PlannedAction, RiskLevel
from cdrive_cleaner.executors import DirectFileDeleteExecutor, ExecutionStatus
from cdrive_cleaner.safety import SafetyPolicy, capture_identity


def _action(target: Path, scope: Path) -> PlannedAction:
    return PlannedAction(
        Finding(
            "temp",
            "1.0.0",
            target,
            scope,
            RiskLevel.SAFE,
            ActionKind.DIRECT_FILE_DELETE,
            capture_identity(target),
        )
    )


def test_dry_run_uses_full_policy_but_does_not_delete(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "dry.tmp"
    target.write_bytes(b"1234")
    result = DirectFileDeleteExecutor(SafetyPolicy([scope], [])).execute(
        _action(target, scope), dry_run=True
    )
    assert result.status is ExecutionStatus.SIMULATED
    assert result.bytes_processed == 4
    assert target.exists()


def test_real_execution_deletes_only_authorized_fixture(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "delete.tmp"
    target.write_bytes(b"1234")
    result = DirectFileDeleteExecutor(SafetyPolicy([scope], [])).execute(
        _action(target, scope), dry_run=False
    )
    assert result.status is ExecutionStatus.DELETED
    assert result.bytes_processed == 4
    assert not target.exists()


def test_changed_target_is_not_deleted(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "changed.tmp"
    target.write_text("before")
    action = _action(target, scope)
    target.write_text("different content")
    result = DirectFileDeleteExecutor(SafetyPolicy([scope], [])).execute(action, dry_run=False)
    assert result.status is ExecutionStatus.DENIED
    assert target.exists()


def test_elevated_action_requires_explicit_elevated_context(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "admin.tmp"
    target.write_text("x")
    base = _action(target, scope)
    action = PlannedAction(base.finding, requires_elevation=True)
    denied = DirectFileDeleteExecutor(SafetyPolicy([scope], [])).execute(action, dry_run=False)
    allowed = DirectFileDeleteExecutor(
        SafetyPolicy([scope], []), elevated_checker=lambda: True
    ).execute(action, dry_run=False)
    assert denied.error_code == "elevation_required"
    assert allowed.status is ExecutionStatus.DELETED
