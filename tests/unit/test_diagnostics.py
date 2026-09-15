import json
import zipfile
from pathlib import Path

from cdrive_cleaner.persistence import export_diagnostics


def test_diagnostic_export_has_no_paths_or_usernames(tmp_path: Path) -> None:
    destination = tmp_path / "diagnostics.zip"
    export_diagnostics(destination, recent_result_codes=("allowed", "permission_denied"))
    with zipfile.ZipFile(destination) as archive:
        payload = json.loads(archive.read("diagnostics.json"))
    assert payload["recent_result_codes"] == ["allowed", "permission_denied"]
    assert "filesystem paths" in payload["privacy"]
    assert str(tmp_path) not in json.dumps(payload)
