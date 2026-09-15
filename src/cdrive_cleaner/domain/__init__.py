"""Domain types with no dependency on UI or Windows infrastructure."""

from .advanced import AdvancedAction, CommandResult
from .models import (
    ActionKind,
    ActionPlan,
    CleanupReceipt,
    FileIdentity,
    Finding,
    PlannedAction,
    ProductStage,
    RiskLevel,
    ScanError,
    ScanSnapshot,
)
from .storage import AnalysisCoverage, DirectoryUsage, LargeFile, StorageSnapshot

__all__ = [
    "ActionKind",
    "ActionPlan",
    "AdvancedAction",
    "AnalysisCoverage",
    "CleanupReceipt",
    "CommandResult",
    "DirectoryUsage",
    "FileIdentity",
    "Finding",
    "LargeFile",
    "PlannedAction",
    "ProductStage",
    "RiskLevel",
    "ScanError",
    "ScanSnapshot",
    "StorageSnapshot",
]
