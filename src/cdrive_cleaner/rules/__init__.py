"""Versioned cleanup-rule registry."""

from .catalog import build_m2_registry
from .registry import RuleRegistry, RuleSpec

__all__ = ["RuleRegistry", "RuleSpec", "build_m2_registry"]
