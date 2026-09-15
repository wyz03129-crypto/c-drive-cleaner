from __future__ import annotations

import json
from pathlib import Path

from cdrive_cleaner.persistence import AuditEvent, JsonAuditLog, redact_path


def test_path_redaction_is_stable_and_salted(tmp_path: Path) -> None:
    path = tmp_path / "User Name" / "secret-file.tmp"
    first = redact_path(path, salt=b"one")
    assert first == redact_path(path, salt=b"one")
    assert first != redact_path(path, salt=b"two")
    assert "User Name" not in first
    assert "secret-file" not in first


def test_json_audit_log_never_writes_raw_path(tmp_path: Path) -> None:
    sensitive = tmp_path / "Alice" / "private.tmp"
    event = AuditEvent.create(
        event="delete", rule_id="temp", result_code="allowed", path=sensitive, salt=b"salt"
    )
    log_path = tmp_path / "logs" / "audit.jsonl"
    JsonAuditLog(log_path).append(event)
    raw = log_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["path_token"].startswith("path:")
    assert "Alice" not in raw
    assert "private.tmp" not in raw
