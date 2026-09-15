"""Small utilities shared by CLI, logs, and reports."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "audit_top_level": True,
    "top_directory_limit": 20,
    "large_directory_thresholds_mb": [500, 1024, 5120],
    "enabled_rule_ids": [],
    "show_paths_in_console": False,
}
_CONFIG_KEYS = frozenset(DEFAULT_CONFIG)


def application_root() -> Path:
    """Return the writable application directory in source and frozen builds."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def load_config(path: Path) -> dict[str, Any]:
    """Load display/scan preferences; ignore all unknown authorization fields."""

    result = dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, UnicodeError, json.JSONDecodeError, OSError):
        return result
    if not isinstance(raw, dict):
        return result
    for key in _CONFIG_KEYS:
        if key in raw:
            result[key] = raw[key]
    if not isinstance(result["enabled_rule_ids"], list):
        result["enabled_rule_ids"] = []
    try:
        result["top_directory_limit"] = max(
            1, min(100, int(result["top_directory_limit"]))
        )
    except (TypeError, ValueError):
        result["top_directory_limit"] = 20
    result["audit_top_level"] = bool(result["audit_top_level"])
    result["show_paths_in_console"] = bool(result["show_paths_in_console"])
    return result


def format_bytes(value: int) -> str:
    """Format a byte count for a nontechnical user."""

    amount = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.2f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.2f} TB"


def is_admin() -> bool:
    """Return whether the process is elevated, without requesting elevation."""

    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def system_description() -> str:
    """Return a concise OS description for audit logs."""

    return f"{platform.system()} {platform.release()} {platform.version()}"
