"""Stable domain vocabulary for the v2 architecture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cdrive_cleaner.executors.models import ExecutionResult


class ProductStage(StrEnum):
    """Externally visible implementation stage."""

    ENGINEERING_SKELETON = "M0"
    SAFETY_KERNEL = "M1"
    QUICK_CLEAN = "M2"
    STORAGE_ANALYZER = "M3"
    ADVANCED_WINDOWS = "M4"
    RELEASE = "M5"


class RiskLevel(IntEnum):
    """Ordered policy levels; a larger number never implies authorization.

    The first four names are the user-facing safety model.  ``PROTECTED`` is
    an internal deny class rather than a cleanup choice.  The old names remain
    aliases so stored plans and third-party callers do not break during beta.
    """

    SAFE = 1
    CAUTION = 2
    MANUAL = 3
    SYSTEM = 4
    PROTECTED = 5

    RECOMMENDED = CAUTION
    REVIEW = MANUAL
    ADVANCED = SYSTEM


class ActionKind(StrEnum):
    """Closed set of execution strategies accepted by the planner."""

    DIRECT_FILE_DELETE = "direct_file_delete"
    WINDOWS_API = "windows_api"
    OFFICIAL_COMMAND = "official_command"
    APPLICATION_COMMAND = "application_command"
    ADVISORY_ONLY = "advisory_only"


@dataclass(frozen=True)
class FileIdentity:
    """Filesystem identity captured during discovery and checked again before execution."""

    device: int
    inode: int
    size: int
    modified_ns: int
    mode: int


@dataclass(frozen=True)
class Finding:
    """A scan observation. A finding is never deletion authorization."""

    rule_id: str
    rule_version: str
    path: Path
    scope_root: Path
    risk: RiskLevel
    action_kind: ActionKind
    identity: FileIdentity


@dataclass(frozen=True)
class ScanError:
    """A redaction-friendly scan failure attached to a rule, not a raw path."""

    rule_id: str
    code: str


@dataclass(frozen=True)
class ScanSnapshot:
    """Immutable quick-scan output, including partial-result diagnostics."""

    started_at: datetime
    finished_at: datetime
    findings: tuple[Finding, ...]
    errors: tuple[ScanError, ...]
    cancelled: bool = False

    @property
    def estimated_bytes(self) -> int:
        return sum(item.identity.size for item in self.findings)


@dataclass(frozen=True)
class PlannedAction:
    """An immutable action request that must still be reauthorized by an executor."""

    finding: Finding
    requires_elevation: bool = False


@dataclass(frozen=True)
class ActionPlan:
    """Immutable, versioned collection of actions selected by a user."""

    plan_id: str
    policy_version: str
    created_at: datetime
    actions: tuple[PlannedAction, ...]

    @classmethod
    def create(
        cls,
        *,
        plan_id: str,
        policy_version: str,
        actions: tuple[PlannedAction, ...],
    ) -> ActionPlan:
        return cls(plan_id, policy_version, datetime.now(UTC), actions)

    @property
    def estimated_bytes(self) -> int:
        return sum(action.finding.identity.size for action in self.actions)


@dataclass(frozen=True)
class CleanupReceipt:
    """Separates estimated work, processed bytes, and observed free-space change."""

    plan_id: str
    dry_run: bool
    started_at: datetime
    finished_at: datetime
    estimated_bytes: int
    processed_bytes: int
    free_bytes_before: int
    free_bytes_after: int
    results: tuple[ExecutionResult, ...]
    cancelled: bool = False

    @property
    def observed_freed_bytes(self) -> int:
        return max(0, self.free_bytes_after - self.free_bytes_before)

    @property
    def attempted_bytes(self) -> int:
        return sum(item.bytes_attempted for item in self.results)

    @property
    def skipped_bytes(self) -> int:
        return sum(
            item.bytes_attempted
            for item in self.results
            if item.status.value in {"skipped", "denied"}
        )

    @property
    def failed_count(self) -> int:
        return sum(item.status.value in {"skipped", "denied"} for item in self.results)

    @property
    def unattempted_bytes(self) -> int:
        return max(0, self.estimated_bytes - self.attempted_bytes)
