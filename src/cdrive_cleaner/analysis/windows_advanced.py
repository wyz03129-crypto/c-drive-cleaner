"""Read-only discovery for large Windows-managed storage consumers."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from cdrive_cleaner.windows import KnownFolders


@dataclass(frozen=True)
class AdvancedFinding:
    category: str
    path: Path
    size_bytes: int
    guidance: str


class WindowsAdvancedInspector:
    """Inspect fixed system files and known VHD locations without broad recursive search."""

    def inspect(self, folders: KnownFolders) -> tuple[AdvancedFinding, ...]:
        candidates = [
            ("hibernation", folders.windows.parent / "hiberfil.sys", "use powercfg; never delete"),
            ("pagefile", folders.windows.parent / "pagefile.sys", "manage in Windows settings"),
            ("swapfile", folders.windows.parent / "swapfile.sys", "managed by Windows"),
            (
                "docker",
                folders.local_app_data / "Docker/wsl/data/docker_data.vhdx",
                "use Docker cleanup and supported VHD optimization",
            ),
        ]
        packages = folders.local_app_data / "Packages"
        with suppress(OSError):
            candidates.extend(
                ("wsl", path, "shut down WSL and use supported VHD optimization")
                for path in packages.glob("*/LocalState/ext4.vhdx")
            )
        findings: list[AdvancedFinding] = []
        for category, path, guidance in candidates:
            try:
                if path.is_file() and not path.is_symlink():
                    findings.append(AdvancedFinding(category, path, path.stat().st_size, guidance))
            except OSError:
                continue
        return tuple(sorted(findings, key=lambda item: item.size_bytes, reverse=True))
