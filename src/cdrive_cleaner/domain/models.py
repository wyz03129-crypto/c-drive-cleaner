"""Stable domain vocabulary for the v2 architecture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path


class ProductStage(StrEnum):
    """Externally visible implementation stage."""

    ENGINEERING_SKELETON = "M0"
    SAFETY_KERNEL = "M1"
    QUICK_CLEAN = "M2"
    STORAGE_ANALYZER = "M3"
    ADVANCED_WINDOWS = "M4"
    RELEASE = "M5"


class RiskLevel(IntEnum):
    """Ordered risk levels; a larger number never implies authorization."""

    SAFE = 1
    RECOMMENDED = 2
    REVIEW = 3
    ADVANCED = 4
    PROTECTED = 5


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
