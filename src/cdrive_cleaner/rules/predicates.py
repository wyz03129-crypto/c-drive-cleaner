"""Shared discovery and execution predicates; never trust an old scan alone."""

from fnmatch import fnmatchcase
from pathlib import Path
from time import time_ns

from cdrive_cleaner.domain import FileIdentity


def matches_file(
    path: Path,
    identity: FileIdentity,
    patterns: tuple[str, ...],
    min_age_days: int,
) -> bool:
    if patterns and not any(fnmatchcase(path.name.casefold(), p.casefold()) for p in patterns):
        return False
    return identity.modified_ns <= time_ns() - min_age_days * 86_400 * 1_000_000_000
