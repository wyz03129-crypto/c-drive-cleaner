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
    impact: str = ""
    requires_admin: bool = False
    reversible: bool = True


class WindowsAdvancedInspector:
    """Inspect fixed system files and known VHD locations without broad recursive search."""

    def inspect(self, folders: KnownFolders) -> tuple[AdvancedFinding, ...]:
        candidates = [
            (
                "hibernation",
                folders.windows.parent / "hiberfil.sys",
                "使用 powercfg 关闭；绝不直接删除",
                "将禁用休眠，并可能禁用快速启动",
                True,
                True,
            ),
            (
                "pagefile",
                folders.windows.parent / "pagefile.sys",
                "仅在 Windows 设置中管理",
                "改小可能导致内存不足或崩溃转储不可用",
                True,
                True,
            ),
            (
                "swapfile",
                folders.windows.parent / "swapfile.sys",
                "由 Windows 自动管理",
                "不建议更改",
                True,
                False,
            ),
            (
                "docker",
                folders.local_app_data / "Docker/wsl/data/docker_data.vhdx",
                "使用 Docker 清理和受支持的虚拟磁盘压缩",
                "错误操作可能丢失容器或镜像数据",
                False,
                False,
            ),
        ]
        packages = folders.local_app_data / "Packages"
        with suppress(OSError):
            candidates.extend(
                (
                    "wsl",
                    path,
                    "先关闭 WSL，再使用受支持的虚拟磁盘压缩",
                    "错误操作可能丢失 Linux 环境数据",
                    False,
                    False,
                )
                for path in packages.glob("*/LocalState/ext4.vhdx")
            )
        findings: list[AdvancedFinding] = []
        for category, path, guidance, impact, requires_admin, reversible in candidates:
            try:
                if path.is_file() and not path.is_symlink():
                    findings.append(
                        AdvancedFinding(
                            category,
                            path,
                            path.stat().st_size,
                            guidance,
                            impact,
                            requires_admin,
                            reversible,
                        )
                    )
            except OSError:
                continue
        return tuple(sorted(findings, key=lambda item: item.size_bytes, reverse=True))
