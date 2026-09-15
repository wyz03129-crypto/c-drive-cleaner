"""M2 rule catalog containing only narrowly scoped, rebuildable cache roots."""

from __future__ import annotations

from pathlib import Path

from cdrive_cleaner.domain import ActionKind, RiskLevel
from cdrive_cleaner.safety.reparse import is_reparse_point
from cdrive_cleaner.windows import KnownFolders

from .registry import RuleRegistry, RuleSpec


def _direct(
    rule_id: str,
    title: str,
    roots: tuple[Path, ...],
    *,
    risk: RiskLevel = RiskLevel.SAFE,
    elevated: bool = False,
    include_patterns: tuple[str, ...] = (),
) -> RuleSpec:
    return RuleSpec(
        rule_id,
        "1.0.0",
        title,
        risk,
        ActionKind.DIRECT_FILE_DELETE,
        roots,
        elevated,
        include_patterns,
    )


def _firefox_cache_roots(local: Path) -> tuple[Path, ...]:
    """Discover only named Firefox cache children; profile data never becomes a root."""

    profiles = local / "Mozilla/Firefox/Profiles"
    try:
        return tuple(
            child / cache_name
            for child in profiles.iterdir()
            if child.is_dir() and not child.is_symlink() and not is_reparse_point(child)
            for cache_name in ("cache2", "startupCache")
        ) or (profiles / "__no_profile__/cache2",)
    except OSError:
        return (profiles / "__unreadable__/cache2",)


def build_m2_registry(folders: KnownFolders) -> RuleRegistry:
    """Build immutable rules from trusted Known Folder paths, never environment input."""

    local = folders.local_app_data
    roaming = folders.roaming_app_data
    windows = folders.windows
    profile = folders.profile
    rules = (
        _direct("user_temp", "用户临时文件", (local / "Temp",)),
        _direct("windows_temp", "Windows 临时文件", (windows / "Temp",), elevated=True),
        _direct(
            "chromium_cache",
            "Chrome 可再生缓存",
            (
                local / "Google/Chrome/User Data/Default/Cache/Cache_Data",
                local / "Google/Chrome/User Data/Default/Code Cache",
                local / "Google/Chrome/User Data/Default/GPUCache",
            ),
            risk=RiskLevel.RECOMMENDED,
        ),
        _direct(
            "edge_cache",
            "Edge 可再生缓存",
            (
                local / "Microsoft/Edge/User Data/Default/Cache/Cache_Data",
                local / "Microsoft/Edge/User Data/Default/Code Cache",
                local / "Microsoft/Edge/User Data/Default/GPUCache",
            ),
            risk=RiskLevel.RECOMMENDED,
        ),
        _direct(
            "firefox_cache",
            "Firefox 可再生缓存",
            _firefox_cache_roots(local),
            risk=RiskLevel.RECOMMENDED,
        ),
        _direct(
            "thumbnail_cache",
            "缩略图缓存",
            (local / "Microsoft/Windows/Explorer",),
            include_patterns=("thumbcache_*.db", "iconcache_*.db"),
        ),
        _direct("directx_shader", "DirectX 着色器缓存", (local / "D3DSCache",)),
        _direct("crash_dumps", "应用崩溃转储", (local / "CrashDumps",)),
        _direct(
            "error_reports",
            "Windows 错误报告归档",
            (folders.program_data / "Microsoft/Windows/WER/ReportArchive",),
            elevated=True,
        ),
        _direct("pip_cache", "pip 可重建缓存", (local / "pip/Cache",)),
        _direct("npm_cache", "npm 可重建缓存", (local / "npm-cache",)),
        _direct("nuget_cache", "NuGet 可重建缓存", (profile / ".nuget/packages",)),
        _direct("gradle_cache", "Gradle 可重建缓存", (profile / ".gradle/caches",)),
        _direct("maven_cache", "Maven 可重建缓存", (profile / ".m2/repository",)),
        _direct(
            "office_cache",
            "Office 文档缓存",
            (local / "Microsoft/Office/16.0/OfficeFileCache",),
            risk=RiskLevel.RECOMMENDED,
        ),
        _direct(
            "wps_cache",
            "WPS 可再生缓存",
            (roaming / "kingsoft/office6/cache", local / "Kingsoft/WPS Office/cache"),
            risk=RiskLevel.RECOMMENDED,
        ),
    )
    return RuleRegistry(rules)
