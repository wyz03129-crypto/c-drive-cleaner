"""Fail-closed authorization primitives."""

from .authorization import AuthorizationCode, SafetyDecision, SafetyPolicy
from .defaults import build_default_deny_roots
from .identity import capture_identity
from .path_policy import NormalizedPath, normalize_path

__all__ = [
    "AuthorizationCode",
    "NormalizedPath",
    "SafetyDecision",
    "SafetyPolicy",
    "build_default_deny_roots",
    "capture_identity",
    "normalize_path",
]
