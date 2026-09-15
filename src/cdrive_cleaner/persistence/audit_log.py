"""JSON-lines audit records with path redaction by default."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


def redact_path(path: Path, *, salt: bytes) -> str:
    """Return a stable local hash without retaining a username or filename."""

    digest = hashlib.sha256(salt + os.fspath(path).encode("utf-8", "surrogatepass")).hexdigest()
    return f"path:{digest[:16]}"


@dataclass(frozen=True)
class AuditEvent:
    event: str
    rule_id: str
    result_code: str
    path_token: str
    timestamp: str

    @classmethod
    def create(
        cls, *, event: str, rule_id: str, result_code: str, path: Path, salt: bytes
    ) -> AuditEvent:
        return cls(
            event=event,
            rule_id=rule_id,
            result_code=result_code,
            path_token=redact_path(path, salt=salt),
            timestamp=datetime.now(UTC).isoformat(),
        )


class JsonAuditLog:
    """Append-only local audit log; callers choose an application-data path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, event: AuditEvent) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")
