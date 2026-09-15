"""Structured executor outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from cdrive_cleaner.safety import AuthorizationCode


class ExecutionStatus(StrEnum):
    DELETED = "deleted"
    SIMULATED = "simulated"
    DENIED = "denied"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    bytes_processed: int = 0
    authorization_code: AuthorizationCode | None = None
    error_code: str | None = None
