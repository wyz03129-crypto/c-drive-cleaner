"""Create a minimal, path-free diagnostic archive on explicit user request."""

from __future__ import annotations

import json
import platform
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from cdrive_cleaner import __version__


def export_diagnostics(destination: Path, *, recent_result_codes: tuple[str, ...] = ()) -> Path:
    payload = {
        "application_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "recent_result_codes": list(recent_result_codes[-100:]),
        "privacy": "No usernames or filesystem paths are included.",
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.json", json.dumps(payload, ensure_ascii=False, indent=2))
    return destination
