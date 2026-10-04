"""All destructive recovery fixtures remain under tests/.tmp on the workspace volume."""

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from cdrive_cleaner.analysis import CancellationToken, FastScanner
from cdrive_cleaner.app import CleanupPlanner
from cdrive_cleaner.domain import ActionKind, RiskLevel
from cdrive_cleaner.executors import ExecutionStatus, quarantine
from cdrive_cleaner.executors.quarantine import QuarantineExecutor, QuarantineStore
from cdrive_cleaner.rules import RuleRegistry, RuleSpec
from cdrive_cleaner.safety import SafetyPolicy
from cdrive_cleaner.windows.protected_data import protect

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Native Windows recovery")


@pytest.fixture
def vault(tmp_path, monkeypatch):
    source = tmp_path / "cache"
    source.mkdir()
    file = source / "old.tmp"
    file.write_bytes(b"precious cache content" * 100)
    registry = RuleRegistry(
        [
            RuleSpec(
                "test", "1.0.0", "Test", RiskLevel.CAUTION, ActionKind.DIRECT_FILE_DELETE, (source,)
            )
        ]
    )
    policy = SafetyPolicy((source,), ())
    store = QuarantineStore(tmp_path / "CDriveCleaner-Quarantine")
    store.initialize()
    # Only the volume-comparison seam is mocked: all copies, DPAPI, fsync and
    # handle-based source deletions really execute on the confined E: fixture.
    actual_reference = quarantine.file_reference
    monkeypatch.setattr(
        quarantine,
        "file_reference",
        lambda path: (
            replace(actual_reference(path), volume=actual_reference(path).volume ^ 1)
            if path == store.root
            else actual_reference(path)
        ),
    )
    action = CleanupPlanner(registry).build(FastScanner(registry).scan().findings).actions[0]
    return SimpleNamespace(file=file, registry=registry, policy=policy, store=store, action=action)


def execute(vault, token=None):
    return QuarantineExecutor(vault.store, vault.policy, vault.registry, token=token).execute(
        vault.action, dry_run=False
    )


def test_round_trip_retains_verified_backup(vault):
    content = vault.file.read_bytes()
    modified = vault.file.stat().st_mtime_ns
    result = execute(vault)
    assert result.status is ExecutionStatus.QUARANTINED
    assert not vault.file.exists()
    entry = vault.store.entries()[0]
    assert result.recovery_id == entry.entry_id
    assert entry.state == "待恢复"
    reopened = QuarantineStore(vault.store.root)
    assert reopened.restore(entry.entry_id, vault.registry, vault.policy) == vault.file
    assert vault.file.read_bytes() == content
    assert vault.file.stat().st_mtime_ns == modified
    assert (vault.store.root / entry.entry_id / "payload.bin").exists()
    assert vault.store.entries()[0].state == "原路径存在（不覆盖）"


def test_same_volume_is_rejected(vault, monkeypatch):
    from cdrive_cleaner.windows.file_identity import file_reference

    monkeypatch.setattr(quarantine, "file_reference", file_reference)
    assert execute(vault).error_code == "backup_not_completed"
    assert vault.file.exists() and not vault.store.entries()


@pytest.mark.parametrize("failure", ["full", "quota", "cancel", "manifest", "verify"])
def test_backup_failure_never_deletes_original(vault, monkeypatch, failure):
    token = CancellationToken()
    if failure == "full":
        monkeypatch.setattr(quarantine.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    elif failure == "quota":
        vault.store.max_bytes = 1
    elif failure == "cancel":
        token.cancel()
    elif failure == "manifest":
        monkeypatch.setattr(
            quarantine,
            "_sync_write",
            lambda *args: (_ for _ in ()).throw(OSError("injected flush failure")),
        )
    else:
        monkeypatch.setattr(quarantine, "_digest", lambda path: "bad digest")
    content = vault.file.read_bytes()
    assert execute(vault, token).status is ExecutionStatus.SKIPPED
    assert vault.file.read_bytes() == content


@pytest.mark.parametrize(
    "corruption", ["payload", "manifest", "missing_parent", "changed_rule", "protected_target"]
)
def test_restore_fails_closed(vault, corruption):
    assert execute(vault).status is ExecutionStatus.QUARANTINED
    entry = vault.store.entries()[0]
    directory = vault.store.root / entry.entry_id
    registry = vault.registry
    if corruption == "payload":
        (directory / "payload.bin").write_bytes(b"tampered")
    elif corruption == "manifest":
        (directory / "manifest.bin").write_bytes(b"forged")
    elif corruption == "missing_parent":
        vault.file.parent.rmdir()
    elif corruption == "changed_rule":
        registry = RuleRegistry([])
    else:
        record = vault.store._record(entry.entry_id)
        record["original"] = str(vault.file.with_suffix(".docx"))
        (directory / "manifest.bin").write_bytes(protect(json.dumps(record).encode()))
    with pytest.raises((OSError, ValueError)):
        vault.store.restore(entry.entry_id, registry, vault.policy)
    assert not vault.file.exists()


def test_restore_never_overwrites_new_file(vault):
    execute(vault)
    entry = vault.store.entries()[0]
    vault.file.write_bytes(b"new user data")
    with pytest.raises(OSError):
        vault.store.restore(entry.entry_id, vault.registry, vault.policy)
    assert vault.file.read_bytes() == b"new user data"


def test_interrupted_copy_is_visible_and_can_be_purged(vault):
    token = CancellationToken()
    token.cancel()
    execute(vault, token)
    entry = vault.store.entries()[0]
    assert "未完成" in entry.state
    with pytest.raises(ValueError):
        vault.store.purge(entry.entry_id, confirmation="")
    vault.store.purge(entry.entry_id, confirmation="DELETE BACKUP")
    assert not vault.store.entries() and vault.file.exists()


def test_purge_never_touches_original_and_rejects_unknown_children(vault):
    execute(vault)
    entry = vault.store.entries()[0]
    vault.store.restore(entry.entry_id, vault.registry, vault.policy)
    unknown = vault.store.root / entry.entry_id / "user.txt"
    unknown.write_text("keep")
    with pytest.raises(OSError):
        vault.store.purge(entry.entry_id, confirmation="DELETE BACKUP")
    assert unknown.read_text() == "keep" and vault.file.exists()
    unknown.unlink()
    vault.store.purge(entry.entry_id, confirmation="DELETE BACKUP")
    assert vault.file.exists() and not vault.store.entries()


def test_record_traversal_and_directory_rebinding_rejected(vault):
    with pytest.raises(ValueError):
        vault.store.restore("../cache", vault.registry, vault.policy)
    execute(vault)
    entry = vault.store.entries()[0]
    (vault.store.root / entry.entry_id).rename(vault.store.root / ("a" * 32))
    with pytest.raises(ValueError):
        vault.store.restore("a" * 32, vault.registry, vault.policy)


def test_vault_lock_refuses_parallel_writer(vault):
    with vault.store._locked():
        assert execute(vault).status is ExecutionStatus.SKIPPED
    assert vault.file.exists()


def test_named_stream_rejected_without_losing_data(vault):
    with Path(str(vault.file) + ":private").open("wb") as stream:
        stream.write(b"alternate data")
    vault.action = (
        CleanupPlanner(vault.registry).build(FastScanner(vault.registry).scan().findings).actions[0]
    )
    assert execute(vault).status is ExecutionStatus.SKIPPED
    assert Path(str(vault.file) + ":private").read_bytes() == b"alternate data"


def test_dpapi_tamper_is_detected():
    protected = protect(b"recovery-test")
    assert protect(protected, decrypt=True) == b"recovery-test"
    with pytest.raises(OSError):
        protect(protected[:-1] + bytes([protected[-1] ^ 1]), decrypt=True)


def test_restore_cancel_and_low_space_preserve_backup(vault, monkeypatch):
    execute(vault)
    entry = vault.store.entries()[0]
    token = CancellationToken()
    token.cancel()
    with pytest.raises(OSError, match="取消"):
        vault.store.restore(entry.entry_id, vault.registry, vault.policy, token=token)
    monkeypatch.setattr(quarantine.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(OSError, match="空间不足"):
        vault.store.restore(entry.entry_id, vault.registry, vault.policy)
    assert not vault.file.exists()
    assert (vault.store.root / entry.entry_id / "payload.bin").exists()


def test_backup_holds_source_and_vault_lock_until_delete(vault, monkeypatch):
    original_write = quarantine._sync_write

    def inspected_write(path, data):
        with pytest.raises(OSError), vault.file.open("wb"):
            pass
        with pytest.raises(OSError), vault.store._locked():
            pass
        original_write(path, data)

    monkeypatch.setattr(quarantine, "_sync_write", inspected_write)
    assert execute(vault).status is ExecutionStatus.QUARANTINED


def test_failed_final_delete_keeps_durable_backup_and_original(vault, monkeypatch):
    def fail_after_backup(path, identity, *, before_delete):
        with path.open("rb") as stream:
            before_delete(stream)
        raise OSError("simulated final disposition failure")

    monkeypatch.setattr(quarantine, "delete_verified_file", fail_after_backup)
    assert execute(vault).status is ExecutionStatus.SKIPPED
    assert vault.file.exists()
    assert vault.store.entries()[0].state == "原路径存在（不覆盖）"


def test_cli_confirmation_and_listing(vault, monkeypatch, capsys):
    from cdrive_cleaner import cli

    root = str(vault.store.root)
    assert cli.main(["recovery", "list", "--root", root]) == 0
    execute(vault)
    entry_id = vault.store.entries()[0].entry_id
    with pytest.raises(SystemExit):
        cli.main(["recovery", "restore", "--root", root, "--id", entry_id])
    assert not vault.file.exists()
    monkeypatch.setattr(cli, "_runtime", lambda: (None, vault.registry, vault.policy))
    assert (
        cli.main(["recovery", "restore", "--root", root, "--id", entry_id, "--confirm", "RESTORE"])
        == 0
    )
    assert vault.file.exists()
    assert entry_id in capsys.readouterr().out


def test_cli_initialize_and_purge(vault):
    from cdrive_cleaner import cli

    root = str(vault.store.root)
    with pytest.raises(SystemExit):
        cli.main(["recovery", "init", "--root", root])
    assert cli.main(["recovery", "init", "--root", root, "--confirm", "INIT BACKUP"]) == 0
    execute(vault)
    entry_id = vault.store.entries()[0].entry_id
    with pytest.raises(SystemExit):
        cli.main(["recovery", "purge", "--root", root, "--id", entry_id])
    assert (
        cli.main(
            ["recovery", "purge", "--root", root, "--id", entry_id, "--confirm", "DELETE BACKUP"]
        )
        == 0
    )
    assert not vault.store.entries()
