"""Repeatable Windows acceptance. Mutations are confined to tests/.tmp fixtures."""

from __future__ import annotations

import argparse
import json
import os
import platform
import tempfile
import time
from pathlib import Path

from cdrive_cleaner import __version__
from cdrive_cleaner.analysis import FastScanner, StorageAnalyzer
from cdrive_cleaner.analysis.duplicates import DuplicateAnalyzer
from cdrive_cleaner.app import CleanupPlanner
from cdrive_cleaner.domain import ActionKind, RiskLevel
from cdrive_cleaner.executors import DirectFileDeleteExecutor, ExecutionStatus
from cdrive_cleaner.rules import RuleRegistry, RuleSpec, build_m2_registry
from cdrive_cleaner.safety import SafetyPolicy
from cdrive_cleaner.windows import discover_known_folders
from cdrive_cleaner.windows.processes import process_names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=10000)
    parser.add_argument("--read-only-system-scan", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.files <= 100000:
        parser.error("--files must be 1..100000")
    project = Path(__file__).resolve().parents[1]
    confined = project / "tests/.tmp"
    confined.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "version": __version__,
        "platform": platform.platform(),
        "real_system_deletions": 0,
    }
    with tempfile.TemporaryDirectory(prefix="acceptance-", dir=confined) as directory:
        root = Path(directory)
        fixture = root / "analysis"
        fixture.mkdir()
        for index in range(args.files):
            parent = fixture / f"group-{index % 100}"
            parent.mkdir(exist_ok=True)
            (parent / f"file-{index}.bin").write_bytes(index.to_bytes(8, "little"))
        started = time.perf_counter()
        snapshot = StorageAnalyzer(top_n=1000).analyze(fixture)
        elapsed = time.perf_counter() - started
        assert snapshot.total_files == args.files
        assert snapshot.total_logical_bytes == args.files * 8
        report["analysis_fixture_files"] = args.files
        report["analysis_seconds"] = round(elapsed, 3)
        duplicate_root = root / "duplicates"
        duplicate_root.mkdir()
        for name in ("one.bin", "two.bin"):
            (duplicate_root / name).write_bytes(b"same" * 1024)
        duplicate_result = DuplicateAnalyzer(min_bytes=1).analyze(duplicate_root)
        assert len(duplicate_result.groups) == 1
        report["duplicates_fixture"] = "passed"
        cache = root / "cache"
        cache.mkdir()
        rule = RuleSpec(
            "fixture",
            "1.0.0",
            "Fixture",
            RiskLevel.SAFE,
            ActionKind.DIRECT_FILE_DELETE,
            (cache,),
            min_age_days=7,
        )
        registry = RuleRegistry([rule])
        executor = DirectFileDeleteExecutor(SafetyPolicy((cache,), ()), registry=registry)
        for cycle in range(20):
            target = cache / f"old-{cycle}.tmp"
            target.write_bytes(b"fixture")
            old = time.time() - 8 * 86400
            os.utime(target, (old, old))
            plan = CleanupPlanner(registry).build(FastScanner(registry).scan().findings)
            assert len(plan.actions) == 1
            assert (
                executor.execute(plan.actions[0], dry_run=True).status is ExecutionStatus.SIMULATED
            )
            assert target.exists()
            assert (
                executor.execute(plan.actions[0], dry_run=False).status is ExecutionStatus.DELETED
            )
            assert not target.exists()
        report["confined_real_cleanup_cycles"] = 20
    if os.name == "nt":
        report["process_inventory_count"] = len(process_names())
    if args.read_only_system_scan:
        folders = discover_known_folders()
        catalog = build_m2_registry(folders)
        started = time.perf_counter()
        scan = FastScanner(catalog).scan()
        report["read_only_scan_seconds"] = round(time.perf_counter() - started, 3)
        report["read_only_scan_files"] = len(scan.findings)
        report["read_only_scan_errors"] = len(scan.errors)
        report["read_only_rules_with_data"] = sorted({f.rule_id for f in scan.findings})
    output = project / "dist/personal-acceptance.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
