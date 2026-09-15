"""Stable domain vocabulary for the v2 architecture."""

from __future__ import annotations

from enum import IntEnum, StrEnum


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
