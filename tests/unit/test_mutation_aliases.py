from pathlib import Path

from scripts.check_mutation_gate import find_violations


def test_gate_catches_aliases_instances_and_native_delete(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.py"
    source.write_text(
        "from os import unlink as erase\n"
        "erase(target)\n"
        "target.unlink()\n"
        "kernel.DeleteFileW(target)\n"
        "kernel.SetFileInformationByHandle(handle, 4, data, 1)\n",
        encoding="utf-8",
    )
    assert len(find_violations(tmp_path)) == 4
