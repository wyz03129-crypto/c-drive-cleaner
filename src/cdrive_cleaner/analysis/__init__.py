"""Bounded, cancellable filesystem analysis."""

from .fast_scan import CancellationToken, FastScanner

__all__ = ["CancellationToken", "FastScanner"]
