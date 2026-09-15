"""Code-owned cleanup rules.  Configuration cannot add deletion locations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from .paths import (
    deduplicate_paths,
    env_path,
    get_shell_folder,
    get_windows_directory,
    is_same_or_within,
)

CSIDL_APPDATA = 0x001A
CSIDL_LOCAL_APPDATA = 0x001C
CSIDL_COMMON_APPDATA = 0x0023
CSIDL_PROFILE = 0x0028


class RiskLevel(str, Enum):
    """Risk classification used throughout the application."""

    SAFE = "SAFE"
    CAUTION = "CAUTION"
    MANUAL = "MANUAL"
    NEVER_DELETE = "NEVER_DELETE"


@dataclass(frozen=True)
class CacheRule:
    """A built-in audit/cleanup rule."""

    rule_id: str
    display_name: str
    risk: RiskLevel
    roots: tuple[Path, ...]
    file_patterns: tuple[str, ...] = ("*",)
    recommendation: str = ""
    minimum_age_days: int = 0

    @property
    def can_delete(self) -> bool:
        """Only SAFE rules can ever reach the guarded deletion path."""

        return self.risk is RiskLevel.SAFE


def _present(values: Iterable[Path | None]) -> list[Path]:
    return [value for value in values if value is not None]


def _browser_cache_roots(user_data: Path | None) -> list[Path]:
    """Discover cache subdirectories without authorizing a whole profile."""

    if user_data is None or not user_data.is_dir():
        return []
    roots: list[Path] = []
    try:
        profiles = [
            entry
            for entry in user_data.iterdir()
            if entry.is_dir()
            and (
                entry.name == "Default"
                or entry.name in {"Guest Profile", "System Profile"}
                or entry.name.startswith("Profile ")
            )
        ]
    except OSError:
        return []
    for profile in profiles:
        roots.extend(
            profile / cache_name
            for cache_name in ("Cache", "Code Cache", "GPUCache", "ShaderCache")
        )
    return roots


def build_rules(
    *,
    env: Mapping[str, str] | None = None,
    system_drive: str | None = None,
) -> tuple[CacheRule, ...]:
    """Build immutable rules from trusted code and the current Windows layout."""

    source = os.environ if env is None else env
    if env is None:
        system_root = get_windows_directory() or Path(source.get("SystemRoot", "C:\\Windows"))
        inferred_drive = system_root.drive or source.get("SystemDrive", "C:")
        drive = system_drive or inferred_drive
        drive_root = Path(drive + "\\") if drive.endswith(":") else Path(drive)
        local = get_shell_folder(CSIDL_LOCAL_APPDATA)
        roaming = get_shell_folder(CSIDL_APPDATA)
        profile = get_shell_folder(CSIDL_PROFILE)
        program_data = get_shell_folder(CSIDL_COMMON_APPDATA) or (drive_root / "ProgramData")
        temp_candidate = env_path("TEMP", env=source)
        temp = None
        if temp_candidate and temp_candidate.name.casefold() in {"temp", "tmp"}:
            if (local and is_same_or_within(temp_candidate, local)) or (
                profile and is_same_or_within(temp_candidate, profile)
            ):
                temp = temp_candidate
    else:
        drive = system_drive or source.get("SystemDrive", "C:")
        drive_root = Path(drive + "\\") if drive.endswith(":") else Path(drive)
        local = env_path("LOCALAPPDATA", env=source)
        roaming = env_path("APPDATA", env=source)
        profile = env_path("USERPROFILE", env=source)
        temp = env_path("TEMP", env=source)
        system_root = env_path("SystemRoot", env=source) or (drive_root / "Windows")
        program_data = env_path("ProgramData", env=source) or (drive_root / "ProgramData")

    chrome = local / "Google/Chrome/User Data" if local else None
    edge = local / "Microsoft/Edge/User Data" if local else None

    rules = (
        CacheRule(
            "user_temp",
            "用户临时文件",
            RiskLevel.SAFE,
            deduplicate_paths(
                _present((temp, local / "Temp" if local else None))
            ),
            recommendation="仅处理最后修改时间超过 7 天的普通缓存文件。",
            minimum_age_days=7,
        ),
        CacheRule(
            "windows_temp",
            "Windows Temp",
            RiskLevel.SAFE,
            (system_root / "Temp",),
            recommendation="仅处理超过 7 天的文件；权限不足时跳过且不提权。",
            minimum_age_days=7,
        ),
        CacheRule(
            "chrome_cache",
            "Chrome 缓存",
            RiskLevel.SAFE,
            deduplicate_paths(_browser_cache_roots(chrome)),
        ),
        CacheRule(
            "edge_cache",
            "Edge 缓存",
            RiskLevel.SAFE,
            deduplicate_paths(_browser_cache_roots(edge)),
        ),
        CacheRule(
            "wps_safe_cache",
            "WPS 明确缓存",
            RiskLevel.SAFE,
            deduplicate_paths(
                _present(
                    (
                        local / "Kingsoft/WPS Office/cache" if local else None,
                    )
                )
            ),
            recommendation="备份、恢复、云文档及历史版本不在白名单中。",
            minimum_age_days=1,
        ),
        CacheRule(
            "wps_review",
            "WPS 临时/日志/崩溃目录",
            RiskLevel.MANUAL,
            deduplicate_paths(
                _present(
                    (
                        local / "Kingsoft/WPS Office/temp" if local else None,
                        local / "Kingsoft/WPS Office/logs" if local else None,
                        local / "Kingsoft/WPS Office/crash" if local else None,
                        local / "Kingsoft/WPS Office/Download Cache" if local else None,
                        local / "Kingsoft/WPS Office/Update Cache" if local else None,
                    )
                )
            ),
            recommendation="目录语义随版本变化且可能涉及恢复数据，v1.0.0 仅报告。",
        ),
        CacheRule(
            "office_cache",
            "Microsoft Office 文件缓存",
            RiskLevel.MANUAL,
            deduplicate_paths(
                _present(
                    (
                        local / "Microsoft/Office/16.0/OfficeFileCache" if local else None,
                        local / "Microsoft/Office/OfficeFileCache" if local else None,
                    )
                )
            ),
            recommendation="可能包含同步/离线状态，v1.0.0 仅报告。",
        ),
        CacheRule(
            "pip_cache",
            "pip 缓存",
            RiskLevel.SAFE,
            deduplicate_paths(
                _present((local / "pip/Cache" if local else None,))
            ),
        ),
        CacheRule(
            "npm_cache",
            "npm 缓存",
            RiskLevel.SAFE,
            deduplicate_paths(
                _present(
                    (
                        roaming / "npm-cache" if roaming else None,
                        local / "npm-cache" if local else None,
                        profile / ".npm/_cacache" if profile else None,
                        profile / ".npm/_logs" if profile else None,
                    )
                )
            ),
            recommendation="node_modules 和项目目录不在白名单中。",
        ),
        CacheRule(
            "shader_cache",
            "显卡 Shader Cache",
            RiskLevel.SAFE,
            deduplicate_paths(
                _present(
                    (
                        local / "D3DSCache" if local else None,
                        local / "NVIDIA/DXCache" if local else None,
                        local / "NVIDIA/GLCache" if local else None,
                        local / "AMD/DxCache" if local else None,
                        local / "AMD/VkCache" if local else None,
                        local / "Intel/ShaderCache" if local else None,
                    )
                )
            ),
        ),
        CacheRule(
            "crash_dumps",
            "用户 Crash Dump",
            RiskLevel.CAUTION,
            deduplicate_paths(
                _present((local / "CrashDumps" if local else None,))
            ),
            file_patterns=("*.dmp",),
            recommendation="可能用于故障诊断，v1.0.0 仅报告。",
        ),
        CacheRule(
            "thumbnail_cache",
            "Windows 缩略图缓存",
            RiskLevel.SAFE,
            deduplicate_paths(
                _present(
                    (local / "Microsoft/Windows/Explorer" if local else None,)
                )
            ),
            file_patterns=("thumbcache_*.db", "iconcache_*.db"),
        ),
        CacheRule(
            "windows_error_reporting",
            "Windows 错误报告历史",
            RiskLevel.CAUTION,
            (program_data / "Microsoft/Windows/WER/ReportArchive",),
            recommendation="v1.0.0 仅报告；待处理报告不清理。",
        ),
        CacheRule(
            "windows_update",
            "Windows Update Cache",
            RiskLevel.MANUAL,
            (system_root / "SoftwareDistribution/Download",),
            recommendation="请使用 设置 → 系统 → 存储 → 临时文件。",
        ),
        CacheRule(
            "windows_old",
            "Windows.old",
            RiskLevel.MANUAL,
            (drive_root / "Windows.old",),
            recommendation="请使用 Windows 官方磁盘清理/存储清理。",
        ),
        CacheRule(
            "recycle_bin",
            "回收站",
            RiskLevel.CAUTION,
            (drive_root / "$Recycle.Bin",),
            recommendation="保守模式不清空；请在回收站中自行确认。",
        ),
    )
    return rules


def safe_allow_roots(rules: Iterable[CacheRule]) -> tuple[Path, ...]:
    """Return code-built roots that are eligible for SAFE authorization."""

    return deduplicate_paths(
        [root for rule in rules if rule.can_delete for root in rule.roots]
    )
