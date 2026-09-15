"""Central fail-closed policy used immediately before direct file actions."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cdrive_cleaner.domain import FileIdentity, RiskLevel

from .identity import capture_identity
from .path_policy import NormalizedPath, normalize_path
from .reparse import chain_contains_reparse, path_key, same_or_within, strictly_within


class AuthorizationCode(StrEnum):
    ALLOWED = "allowed"
    INVALID_PATH = "invalid_path"
    RISK_NOT_DIRECT = "risk_not_direct"
    UNKNOWN_SCOPE = "unknown_scope"
    OUTSIDE_SCOPE = "outside_scope"
    DIFFERENT_VOLUME = "different_volume"
    DENYLISTED = "denylisted"
    PROTECTED_NAME = "protected_name"
    REPARSE_POINT = "reparse_point"
    PROJECT_TREE = "project_tree"
    NOT_FOUND = "not_found"
    NOT_REGULAR_FILE = "not_regular_file"
    IDENTITY_CHANGED = "identity_changed"
    METADATA_ERROR = "metadata_error"


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    code: AuthorizationCode
    normalized: NormalizedPath | None = None


class SafetyPolicy:
    """Authorize direct file actions under immutable allow and deny roots."""

    POLICY_VERSION = "2.0.0"
    _DIRECT_RISKS = frozenset({RiskLevel.SAFE, RiskLevel.RECOMMENDED})
    _PROTECTED_PARTS = frozenset(
        {
            "desktop",
            "documents",
            "downloads",
            "pictures",
            "videos",
            "music",
            "onedrive",
            "recovery",
            "boot",
            "efi",
            "windowsapps",
            "system volume information",
            "backup",
            "backups",
            "autorecovery",
            "recoveryfiles",
            "cloudfiles",
            "clouddocs",
        }
    )
    _PROTECTED_NAMES = frozenset(
        {
            "pagefile.sys",
            "hiberfil.sys",
            "swapfile.sys",
            "bookmarks",
            "history",
            "cookies",
            "login data",
            "web data",
            "local state",
            "preferences",
        }
    )
    _PROTECTED_EXTENSIONS = frozenset(
        {
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".pdf",
            ".rtf",
            ".sqlite",
            ".sqlite3",
            ".mdb",
            ".accdb",
            ".db",
        }
    )
    _PROJECT_MARKERS = frozenset(
        {".git", ".hg", ".svn", "pyproject.toml", "package.json", "cargo.toml"}
    )

    def __init__(self, allow_roots: Iterable[Path], deny_roots: Iterable[Path]) -> None:
        self._allow_roots = {path_key(normalize_path(root).canonical) for root in allow_roots}
        self._deny_roots = tuple(normalize_path(root) for root in deny_roots)

    def _protected_name(self, path: Path, scope: Path) -> bool:
        parts = [part.casefold() for part in path.parts]
        if any(part in self._PROTECTED_PARTS or part.startswith("onedrive") for part in parts):
            return True
        if path.name.casefold() in self._PROTECTED_NAMES:
            return True
        # Windows thumbnail/icon databases are rebuildable shell caches. The
        # exception is constrained to an allowlisted Explorer scope.
        name = path.name.casefold()
        shell_cache = scope.name.casefold() == "explorer" and (
            name.startswith("thumbcache_") or name.startswith("iconcache_")
        )
        return path.suffix.casefold() in self._PROTECTED_EXTENSIONS and not shell_cache

    def _denylisted(self, candidate: NormalizedPath) -> bool:
        return any(
            same_or_within(candidate.absolute, denied.absolute)
            or same_or_within(candidate.canonical, denied.canonical)
            for denied in self._deny_roots
        )

    def _project_tree(self, target: Path, scope: Path) -> bool:
        scope_key = (scope.parent.name.casefold(), scope.name.casefold())
        package_cache_scopes = {
            (".nuget", "packages"),
            (".gradle", "caches"),
            (".m2", "repository"),
            ("pip", "cache"),
        }
        if scope.name.casefold() == "npm-cache" or scope_key in package_cache_scopes:
            return False
        current = target.parent
        while same_or_within(current, scope):
            try:
                if any((current / marker).exists() for marker in self._PROJECT_MARKERS):
                    return True
            except OSError:
                return True
            if path_key(current) == path_key(scope):
                return False
            current = current.parent
        return True

    def authorize(
        self,
        path: Path,
        *,
        scope_root: Path,
        risk: RiskLevel,
        expected_identity: FileIdentity,
    ) -> SafetyDecision:
        """Return a stable decision code without exposing sensitive paths."""

        if risk not in self._DIRECT_RISKS:
            return SafetyDecision(False, AuthorizationCode.RISK_NOT_DIRECT)
        try:
            candidate = normalize_path(path)
            scope = normalize_path(scope_root)
        except (OSError, ValueError):
            return SafetyDecision(False, AuthorizationCode.INVALID_PATH)
        if path_key(scope.canonical) not in self._allow_roots:
            return SafetyDecision(False, AuthorizationCode.UNKNOWN_SCOPE, candidate)
        if not strictly_within(candidate.absolute, scope.absolute) or not strictly_within(
            candidate.canonical, scope.canonical
        ):
            return SafetyDecision(False, AuthorizationCode.OUTSIDE_SCOPE, candidate)
        if self._denylisted(candidate):
            return SafetyDecision(False, AuthorizationCode.DENYLISTED, candidate)
        if self._protected_name(candidate.absolute, scope.absolute):
            return SafetyDecision(False, AuthorizationCode.PROTECTED_NAME, candidate)
        if not os.path.lexists(candidate.absolute):
            return SafetyDecision(False, AuthorizationCode.NOT_FOUND, candidate)
        if chain_contains_reparse(candidate.absolute, scope.absolute):
            return SafetyDecision(False, AuthorizationCode.REPARSE_POINT, candidate)
        if self._project_tree(candidate.absolute, scope.absolute):
            return SafetyDecision(False, AuthorizationCode.PROJECT_TREE, candidate)
        try:
            current = capture_identity(candidate.absolute)
            scope_device = os.stat(scope.absolute, follow_symlinks=False).st_dev
        except FileNotFoundError:
            return SafetyDecision(False, AuthorizationCode.NOT_FOUND, candidate)
        except OSError:
            return SafetyDecision(False, AuthorizationCode.METADATA_ERROR, candidate)
        if current.device != scope_device:
            return SafetyDecision(False, AuthorizationCode.DIFFERENT_VOLUME, candidate)
        if not stat.S_ISREG(current.mode):
            return SafetyDecision(False, AuthorizationCode.NOT_REGULAR_FILE, candidate)
        if current != expected_identity:
            return SafetyDecision(False, AuthorizationCode.IDENTITY_CHANGED, candidate)
        return SafetyDecision(True, AuthorizationCode.ALLOWED, candidate)
