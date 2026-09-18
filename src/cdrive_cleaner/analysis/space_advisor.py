"""Conservative, read-only explanations for large storage consumers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cdrive_cleaner.domain import RiskLevel


@dataclass(frozen=True)
class SpaceAdvice:
    risk: RiskLevel
    label: str
    explanation: str
    action: str


def advise_path(path: Path, *, system_drive: Path, profile: Path) -> SpaceAdvice:
    """Classify a path for display; this function never authorizes deletion."""

    value = os.fspath(path).replace("/", "\\").casefold()
    root = os.fspath(system_drive).replace("/", "\\").rstrip("\\").casefold()
    user = os.fspath(profile).replace("/", "\\").rstrip("\\").casefold()
    name = path.name.casefold()

    if name in {"hiberfil.sys", "pagefile.sys", "swapfile.sys"}:
        return SpaceAdvice(
            RiskLevel.SYSTEM,
            "Windows 系统空间",
            "由 Windows 管理，不能直接删除。",
            "在高级优化中使用 Windows 官方机制评估。",
        )
    if name.endswith((".vhd", ".vhdx")):
        return SpaceAdvice(
            RiskLevel.SYSTEM,
            "虚拟磁盘",
            "可能属于 WSL、Docker 或虚拟机，直接删除会丢失环境数据。",
            "先在对应应用内清理，再使用受支持的压缩流程。",
        )
    if any(
        marker in value
        for marker in ("\\windows\\winsxs", "\\windows\\system32", "\\windows\\installer")
    ):
        return SpaceAdvice(
            RiskLevel.PROTECTED,
            "受保护的 Windows 内容",
            "直接删除可能破坏 Windows、更新或软件修复。",
            "只使用 Windows 官方维护工具；本程序不会直接删除。",
        )
    if value.startswith(f"{root}\\$winreagent"):
        return SpaceAdvice(
            RiskLevel.SYSTEM,
            "Windows 更新恢复文件",
            "通常与 Windows 更新或回滚相关，不能按普通文件处理。",
            "先完成更新并使用 Windows 存储设置复核。",
        )
    if value.startswith(f"{user}\\downloads") or value.startswith(f"{user}\\desktop"):
        return SpaceAdvice(
            RiskLevel.MANUAL,
            "用户文件",
            "可能是下载、安装包或个人文件。",
            "按文件逐项检查；程序不会自动删除。",
        )
    if "\\program files" in value:
        return SpaceAdvice(
            RiskLevel.MANUAL,
            "已安装应用",
            "这是程序安装内容，不是缓存。",
            "如不再使用，请从 Windows“已安装的应用”卸载。",
        )
    if any(marker in value for marker in ("\\node_modules", "\\.venv", "\\site-packages")):
        return SpaceAdvice(
            RiskLevel.MANUAL,
            "开发环境",
            "依赖可重新安装，但可能属于正在使用的项目。",
            "确认项目不再需要后，用包管理器或删除整个废弃环境。",
        )
    if name.endswith((".iso", ".zip", ".7z", ".rar", ".exe", ".msi")):
        return SpaceAdvice(
            RiskLevel.MANUAL,
            "大文件或安装包",
            "可能是用户主动保存的文件。",
            "确认不再需要后由用户手动删除或移动到其他磁盘。",
        )
    if "\\appdata\\" in value:
        return SpaceAdvice(
            RiskLevel.MANUAL,
            "应用数据",
            "AppData 同时包含缓存、配置和重要应用数据。",
            "仅使用快速清理中已验证的缓存规则；不要删除整个目录。",
        )
    return SpaceAdvice(
        RiskLevel.MANUAL,
        "空间占用",
        "仅凭目录大小无法证明它是垃圾。",
        "展开检查或通过对应应用管理，不自动删除。",
    )
