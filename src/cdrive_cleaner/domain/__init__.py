"""Domain types with no dependency on UI or Windows infrastructure."""

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
    "AnalysisCoverage",
    "CleanupReceipt",
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
