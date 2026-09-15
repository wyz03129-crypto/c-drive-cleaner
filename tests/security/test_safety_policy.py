from __future__ import annotations

from pathlib import Path

import pytest

from cdrive_cleaner.domain import RiskLevel
from cdrive_cleaner.safety import AuthorizationCode, SafetyPolicy, capture_identity, normalize_path
from cdrive_cleaner.safety.path_policy import has_forbidden_namespace


def _policy(scope: Path, *denied: Path) -> SafetyPolicy:
    return SafetyPolicy([scope], denied)


def test_authorizes_unchanged_regular_file(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "old.tmp"
    target.write_bytes(b"cache")
    decision = _policy(scope).authorize(
        target,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(target),
    )
    assert decision.allowed
    assert decision.code is AuthorizationCode.ALLOWED


def test_rejects_relative_and_network_namespaces(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute"):
        normalize_path("relative/file.tmp")
    assert has_forbidden_namespace(r"\\server\share\file.tmp")
    assert has_forbidden_namespace(r"\\.\PhysicalDrive0")
    assert has_forbidden_namespace(r"\\?\GLOBALROOT\Device\HarddiskVolume1")
    assert not has_forbidden_namespace(r"\\?\C:\very-long\cache.tmp")


def test_rejects_unknown_scope_and_scope_escape(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    other = tmp_path / "other"
    scope.mkdir()
    other.mkdir()
    target = other / "escape.tmp"
    target.write_text("x")
    identity = capture_identity(target)
    policy = _policy(scope)
    unknown = policy.authorize(
        target, scope_root=other, risk=RiskLevel.SAFE, expected_identity=identity
    )
    escaped = policy.authorize(
        target, scope_root=scope, risk=RiskLevel.SAFE, expected_identity=identity
    )
    assert unknown.code is AuthorizationCode.UNKNOWN_SCOPE
    assert escaped.code is AuthorizationCode.OUTSIDE_SCOPE


def test_denylist_wins_over_allowlist(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    denied = scope / "protected"
    denied.mkdir(parents=True)
    target = denied / "x.tmp"
    target.write_text("x")
    decision = _policy(scope, denied).authorize(
        target,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(target),
    )
    assert decision.code is AuthorizationCode.DENYLISTED


@pytest.mark.parametrize("name", ["report.docx", "state.db", "Cookies", "Login Data"])
def test_protected_user_data_names_are_denied(tmp_path: Path, name: str) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / name
    target.write_text("keep")
    decision = _policy(scope).authorize(
        target,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(target),
    )
    assert decision.code is AuthorizationCode.PROTECTED_NAME


def test_project_tree_is_denied_without_blocking_sibling_cache(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    project = scope / "project"
    sibling = scope / "ordinary"
    project.mkdir(parents=True)
    sibling.mkdir()
    (project / "pyproject.toml").write_text("[project]")
    source_cache = project / "artifact.tmp"
    normal_cache = sibling / "artifact.tmp"
    source_cache.write_text("x")
    normal_cache.write_text("x")
    policy = _policy(scope)
    denied = policy.authorize(
        source_cache,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(source_cache),
    )
    allowed = policy.authorize(
        normal_cache,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(normal_cache),
    )
    assert denied.code is AuthorizationCode.PROJECT_TREE
    assert allowed.allowed


def test_identity_change_is_denied(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "changing.tmp"
    target.write_text("before")
    identity = capture_identity(target)
    target.write_text("a different size")
    decision = _policy(scope).authorize(
        target, scope_root=scope, risk=RiskLevel.SAFE, expected_identity=identity
    )
    assert decision.code is AuthorizationCode.IDENTITY_CHANGED


def test_review_risk_never_reaches_direct_authorization(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    target = scope / "review.tmp"
    target.write_text("x")
    decision = _policy(scope).authorize(
        target,
        scope_root=scope,
        risk=RiskLevel.REVIEW,
        expected_identity=capture_identity(target),
    )
    assert decision.code is AuthorizationCode.RISK_NOT_DIRECT


def test_symlink_is_denied_and_external_target_survives(tmp_path: Path) -> None:
    scope = tmp_path / "cache"
    scope.mkdir()
    outside = tmp_path / "outside.tmp"
    outside.write_text("keep")
    link = scope / "link.tmp"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation unavailable")
    decision = _policy(scope).authorize(
        link,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(link),
    )
    assert not decision.allowed
    assert outside.exists()


def test_shell_cache_database_exception_is_narrow(tmp_path: Path) -> None:
    scope = tmp_path / "Explorer"
    scope.mkdir()
    thumbnail = scope / "thumbcache_256.db"
    unrelated = scope / "important.db"
    thumbnail.write_bytes(b"cache")
    unrelated.write_bytes(b"data")
    policy = _policy(scope)
    allowed = policy.authorize(
        thumbnail,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(thumbnail),
    )
    denied = policy.authorize(
        unrelated,
        scope_root=scope,
        risk=RiskLevel.SAFE,
        expected_identity=capture_identity(unrelated),
    )
    assert allowed.allowed
    assert denied.code is AuthorizationCode.PROTECTED_NAME


def test_package_markers_inside_known_package_cache_are_not_projects(tmp_path: Path) -> None:
    scope = tmp_path / ".nuget" / "packages"
    package = scope / "demo"
    package.mkdir(parents=True)
    (package / "package.json").write_text("{}")
    target = package / "artifact.bin"
    target.write_bytes(b"cache")
    decision = _policy(scope).authorize(
        target,
        scope_root=scope,
        risk=RiskLevel.RECOMMENDED,
        expected_identity=capture_identity(target),
    )
    assert decision.allowed
