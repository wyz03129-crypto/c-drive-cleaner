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

__all__ = [
    "ActionKind",
    "ActionPlan",
    "CleanupReceipt",
    "FileIdentity",
    "Finding",
    "PlannedAction",
    "ProductStage",
    "RiskLevel",
    "ScanError",
    "ScanSnapshot",
]
