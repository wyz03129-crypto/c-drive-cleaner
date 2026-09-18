"""Static release checks that complement tests and Windows packaging jobs."""

from __future__ import annotations

import re
from pathlib import Path

from cdrive_cleaner import __version__

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    "config.json",
    "requirements.txt",
    "src/main.py",
    "src/safety.py",
    "docs/LEGACY_MIGRATION.md",
)


def main() -> int:
    failures = [f"obsolete file remains: {item}" for item in FORBIDDEN if (ROOT / item).exists()]
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', project, re.MULTILINE)
    if match is None or match.group(1) != __version__:
        failures.append("package and runtime versions do not match")
    for required in (
        "AGENTS.md",
        "CHANGELOG.md",
        "PRIVACY.md",
        "KNOWN_LIMITATIONS.md",
        "SECURITY.md",
    ):
        if not (ROOT / required).is_file():
            failures.append(f"release document missing: {required}")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Release gate passed for {__version__}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
