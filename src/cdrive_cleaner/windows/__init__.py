"""Narrow wrappers around documented Windows APIs."""

from .known_folders import KnownFolders, discover_known_folders

__all__ = ["KnownFolders", "discover_known_folders"]
