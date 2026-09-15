"""Closed vocabulary for Windows advanced operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AdvancedAction(StrEnum):
    ANALYZE_COMPONENT_STORE = "analyze_component_store"
    CLEAN_COMPONENT_STORE = "clean_component_store"
    DISABLE_HIBERNATION = "disable_hibernation"
    ENABLE_HIBERNATION = "enable_hibernation"
    LIST_SHADOWS = "list_shadows"
    OPEN_STORAGE_SETTINGS = "open_storage_settings"


@dataclass(frozen=True)
class CommandResult:
    action: AdvancedAction
    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0
