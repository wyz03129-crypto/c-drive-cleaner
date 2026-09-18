from pathlib import Path

from cdrive_cleaner.domain import RiskLevel
from cdrive_cleaner.rules import build_m2_registry
from cdrive_cleaner.windows import KnownFolders


def test_catalog_uses_known_folders_and_narrow_browser_roots(tmp_path: Path) -> None:
    local, profile = tmp_path / "Local", tmp_path / "User"
    firefox = local / "Mozilla/Firefox/Profiles/demo.default"
    firefox.mkdir(parents=True)
    folders = KnownFolders(
        tmp_path / "Windows", profile, local, tmp_path / "Roaming", tmp_path / "Data"
    )
    registry = build_m2_registry(folders)
    firefox_rule = registry.resolve("firefox_cache", "1.0.0")
    thumbnail_rule = registry.resolve("thumbnail_cache", "1.0.0")
    assert firefox_rule is not None and firefox / "cache2" in firefox_rule.roots
    assert firefox not in firefox_rule.roots
    assert thumbnail_rule is not None
    assert thumbnail_rule.include_patterns == ("thumbcache_*.db", "iconcache_*.db")
    assert len(registry.all()) == 20
    baidu = registry.resolve("baidu_accelerate_cache", "1.0.0")
    assert baidu is not None
    assert not baidu.default_selected
    assert baidu.confirmation_phrase == "清理百度缓存"
    vscode = registry.resolve("vscode_cache", "1.0.0")
    assert vscode is not None
    assert not vscode.default_selected
    assert all("User" not in root.name for root in vscode.roots)


def test_catalog_discovers_all_ordinary_chromium_profiles(tmp_path: Path) -> None:
    local = tmp_path / "Local"
    user_data = local / "Microsoft/Edge/User Data"
    for name in ("Default", "Profile 1", "Guest Profile", "System Profile"):
        (user_data / name).mkdir(parents=True)
    folders = KnownFolders(tmp_path / "Windows", tmp_path, local, tmp_path, tmp_path)

    edge = build_m2_registry(folders).resolve("edge_cache", "1.0.0")

    assert edge is not None
    assert user_data / "Default/Service Worker/CacheStorage" in edge.roots
    assert user_data / "Profile 1/Cache/Cache_Data" in edge.roots
    assert user_data / "Guest Profile/GPUCache" in edge.roots
    assert all("System Profile" not in str(root) for root in edge.roots)


def test_catalog_includes_narrow_baidu_acceleration_cache(tmp_path: Path) -> None:
    local, roaming = tmp_path / "Local", tmp_path / "Roaming"
    folders = KnownFolders(tmp_path / "Windows", tmp_path, local, roaming, tmp_path)

    rule = build_m2_registry(folders).resolve("baidu_accelerate_cache", "1.0.0")

    assert rule is not None
    assert rule.roots == (roaming / "baidu/BaiduYunKernel/.accelerate",)
    assert rule.risk is RiskLevel.RECOMMENDED
