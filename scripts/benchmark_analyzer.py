"""Build a reproducible synthetic tree and measure M3 time and peak Python memory."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

from cdrive_cleaner.analysis import StorageAnalyzer


def build_fixture(root: Path, file_count: int) -> None:
    for index in range(file_count):
        directory = root / f"group-{index % 100:03d}" / f"bucket-{index % 1000:04d}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"file-{index:07d}.bin").write_bytes(b"x")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=500_000)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    if args.files < 1:
        parser.error("--files must be positive")
    with tempfile.TemporaryDirectory(prefix="cdrive-m3-benchmark-") as temporary:
        root = Path(temporary)
        fixture_started = time.perf_counter()
        build_fixture(root, args.files)
        fixture_elapsed = time.perf_counter() - fixture_started
        tracemalloc.start()
        scan_started = time.perf_counter()
        result = StorageAnalyzer(top_n=args.top).analyze(root)
        elapsed = time.perf_counter() - scan_started
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(
            json.dumps(
                {
                    "fixture_files": args.files,
                    "fixture_seconds": fixture_elapsed,
                    "scan_seconds": elapsed,
                    "peak_python_bytes": peak,
                    "observed_files": result.total_files,
                    "coverage": result.coverage.directory_ratio,
                },
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
