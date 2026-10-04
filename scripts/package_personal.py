"""Package the verified personal EXE with source, notices, evidence and checksums."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

from cdrive_cleaner import __version__

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    executable = ROOT / "dist/CDriveCleaner.exe"
    checksum = executable.with_suffix(".exe.sha256")
    actual = hashlib.sha256(executable.read_bytes()).hexdigest()
    if checksum.read_text(encoding="ascii").split()[0] != actual:
        raise ValueError("EXE checksum missing or stale; run build_exe.ps1 first")
    target = ROOT / f"dist/CDriveCleaner-{__version__}-personal-windows-x64.zip"
    files = (
        subprocess.check_output(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT)
        .decode("utf-8")
        .split("\0")
    )
    versions = {
        name: importlib.metadata.version(name)
        for name in ("PySide6-Essentials", "shiboken6", "PyInstaller")
    }
    info = {
        "app_version": __version__,
        "python": platform.python_version(),
        "dependencies": versions,
    }
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in (
            executable,
            checksum,
            ROOT / "LICENSE.txt",
            ROOT / "dist/personal-acceptance.json",
        ):
            archive.write(path, path.name)
        for name in (
            "PERSONAL_QUICKSTART.md",
            "PERSONAL_2_1_ACCEPTANCE.md",
            "PERSONAL_2_2_ACCEPTANCE.md",
            "THIRD_PARTY_NOTICES.md",
        ):
            archive.write(ROOT / "docs" / name, name)
        for name in sorted(set(filter(None, files))):
            archive.write(ROOT / name, f"source/{name}")
        archive.writestr("BUILD_INFO.json", json.dumps(info, indent=2))
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
        if python_license.is_file():
            archive.write(python_license, "licenses/Python-LICENSE.txt")
        for name in versions:
            distribution = importlib.metadata.distribution(name)
            for file in distribution.files or ():
                if "license" in str(file).casefold() or str(file).endswith("COPYING.txt"):
                    path = Path(str(distribution.locate_file(file)))
                    if path.is_file() and path.suffix.casefold() in (".txt", ".md", ""):
                        archive.write(path, f"licenses/{name}/{file.name}")
        for license_file in (ROOT / "packaging/licenses").glob("*.txt"):
            archive.write(license_file, f"licenses/{license_file.name}")
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n", encoding="ascii")
    print(f"Verified {target.name}: {target.stat().st_size:,} bytes; SHA256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
