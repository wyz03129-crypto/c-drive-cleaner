from pathlib import Path

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
    assert len(registry.all()) == 16
