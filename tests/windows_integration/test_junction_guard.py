from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from cdrive_cleaner.domain import RiskLevel
from cdrive_cleaner.safety import SafetyPolicy, capture_identity

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows junction test")


def test_junction_escape_is_denied(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    outside = tmp_path / "outside"
    scope.mkdir()
    outside.mkdir()
    target = outside / "keep.tmp"
    target.write_text("keep")
    junction = scope / "junction"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        check=False,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip(f"junction creation unavailable: {created.stderr}")
    try:
        through_junction = junction / target.name
        decision = SafetyPolicy([scope], []).authorize(
            through_junction,
            scope_root=scope,
            risk=RiskLevel.SAFE,
            expected_identity=capture_identity(through_junction),
        )
        assert not decision.allowed
        assert target.exists()
    finally:
        os.rmdir(junction)
