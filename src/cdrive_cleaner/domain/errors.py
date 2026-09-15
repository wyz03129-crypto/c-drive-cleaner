"""Domain-level errors that do not expose platform exception details to the UI."""

from __future__ import annotations


class CleanerError(Exception):
    """Base class for expected application failures."""


class UnsupportedPlatformError(CleanerError):
    """Raised when a Windows-only operation is requested elsewhere."""


class SafetyDeniedError(CleanerError):
    """Raised when an action cannot satisfy the safety policy."""
