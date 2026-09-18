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
    category: str = "应用缓存",
    description: str = "可由应用重新生成的缓存文件",
    recommended_action: str = "关闭相关应用后清理",
    confirmation_phrase: str = "",
    default_selected: bool = True,
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
        category,
        description,
        "recursive_files",
        recommended_action,
        bool(confirmation_phrase),
        confirmation_phrase,
        default_selected,
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


def _chromium_cache_roots(user_data: Path) -> tuple[Path, ...]:
    """Discover cache-only children for every ordinary Chromium profile."""

    profile_names = {"default", "guest profile"}
    try:
        profiles = tuple(
            child
            for child in user_data.iterdir()
            if child.is_dir()
            and not child.is_symlink()
            and not is_reparse_point(child)
            and (
                child.name.casefold() in profile_names
                or child.name.casefold().startswith("profile ")
            )
        )
    except OSError:
        profiles = ()
    if not profiles:
        profiles = (user_data / "Default",)
    cache_children = (
        Path("Cache/Cache_Data"),
        Path("Code Cache"),
        Path("GPUCache"),
        Path("DawnCache"),
        Path("GraphiteDawnCache"),
        Path("Service Worker/CacheStorage"),
    )
    return tuple(profile / child for profile in profiles for child in cache_children)


def build_m2_registry(folders: KnownFolders) -> RuleRegistry:
    """Build immutable rules from trusted Known Folder paths, never environment input."""

    local = folders.local_app_data
    roaming = folders.roaming_app_data
    windows = folders.windows
    profile = folders.profile
    rules = (
        _direct(
            "user_temp",
            "用户临时文件",
            (local / "Temp",),
            category="临时文件",
            description="当前用户的临时工作文件；占用中的文件会跳过",
        ),
        _direct(
            "windows_temp",
            "Windows 临时文件",
            (windows / "Temp",),
            elevated=True,
            category="Windows 缓存",
            description="Windows 公共临时目录；需要管理员权限",
        ),
        _direct(
            "chromium_cache",
            "Chrome 可再生缓存",
            _chromium_cache_roots(local / "Google/Chrome/User Data"),
            risk=RiskLevel.CAUTION,
            category="浏览器缓存",
            description="网页资源缓存，不包含密码、书签、Cookie 或浏览历史",
        ),
        _direct(
            "edge_cache",
            "Edge 可再生缓存",
            _chromium_cache_roots(local / "Microsoft/Edge/User Data"),
            risk=RiskLevel.CAUTION,
            category="浏览器缓存",
            description="网页资源缓存，不包含密码、书签、Cookie 或浏览历史",
        ),
        _direct(
            "firefox_cache",
            "Firefox 可再生缓存",
            _firefox_cache_roots(local),
            risk=RiskLevel.CAUTION,
            category="浏览器缓存",
            description="网页资源缓存，不包含密码、书签、Cookie 或浏览历史",
        ),
        _direct(
            "thumbnail_cache",
            "缩略图缓存",
            (local / "Microsoft/Windows/Explorer",),
            include_patterns=("thumbcache_*.db", "iconcache_*.db"),
            category="Windows 缓存",
            description="资源管理器可重新生成的图片和图标预览",
        ),
        _direct(
            "directx_shader",
            "DirectX 着色器缓存",
            (local / "D3DSCache",),
            category="Windows 缓存",
        ),
        _direct(
            "crash_dumps",
            "应用崩溃转储",
            (local / "CrashDumps",),
            category="日志与崩溃文件",
            description="仅用于故障诊断的应用崩溃转储",
        ),
        _direct(
            "error_reports",
            "Windows 错误报告归档",
            (folders.program_data / "Microsoft/Windows/WER/ReportArchive",),
            elevated=True,
            category="日志与崩溃文件",
            description="Windows 已归档的错误报告",
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
            risk=RiskLevel.CAUTION,
            category="Office 缓存",
            description="Office 文档缓存；不包含用户文档",
        ),
        _direct(
            "wps_cache",
            "WPS 可再生缓存",
            (roaming / "kingsoft/office6/cache", local / "Kingsoft/WPS Office/cache"),
            risk=RiskLevel.CAUTION,
            category="Office 缓存",
            description="WPS 明确命名的缓存目录；不包含用户文档或备份",
        ),
        _direct(
            "baidu_accelerate_cache",
            "百度网盘加速缓存（需关闭百度网盘）",
            (roaming / "baidu/BaiduYunKernel/.accelerate",),
            risk=RiskLevel.CAUTION,
            description="百度网盘可重新生成的加速缓存；不包含云端文件",
            confirmation_phrase="清理百度缓存",
            default_selected=False,
        ),
        _direct(
            "vscode_cache",
            "VS Code 可再生缓存",
            tuple(
                roaming / "Code" / name
                for name in ("Cache", "CachedData", "Code Cache", "GPUCache", "DawnCache")
            ),
            risk=RiskLevel.CAUTION,
            category="开发工具缓存",
            description="编辑器可重建缓存；不包含设置、扩展或项目",
            default_selected=False,
        ),
        _direct(
            "discord_cache",
            "Discord 可再生缓存",
            tuple(
                roaming / "discord" / name
                for name in ("Cache", "Code Cache", "GPUCache", "DawnCache")
            ),
            risk=RiskLevel.CAUTION,
            description="Discord 界面资源缓存；不包含账号和聊天数据",
            default_selected=False,
        ),
        _direct(
            "teams_classic_cache",
            "Teams 经典版可再生缓存",
            tuple(
                roaming / "Microsoft/Teams" / name for name in ("Cache", "Code Cache", "GPUCache")
            ),
            risk=RiskLevel.CAUTION,
            description="Teams 经典版界面缓存；不包含下载文件或账号配置",
            default_selected=False,
        ),
    )
    return RuleRegistry(rules)
