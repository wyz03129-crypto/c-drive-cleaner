"""Command-line shell for the v2 application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__
from .analysis import FastScanner
from .app import CleanupCoordinator, CleanupPlanner
from .domain.errors import UnsupportedPlatformError
from .executors import DirectFileDeleteExecutor, RecycleBinExecutor
from .rules import RuleRegistry, build_m2_registry
from .safety import SafetyPolicy
from .safety.defaults import build_default_deny_roots
from .windows import KnownFolders, discover_known_folders
from .windows.disk_space import free_bytes
from .windows.elevation import is_process_elevated


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI without performing filesystem work."""

    parser = argparse.ArgumentParser(
        prog="c-drive-cleaner",
        description="Windows C 盘空间分析与安全清理工具（v2 工程阶段）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("status", help="显示当前工程阶段")
    subcommands.add_parser("scan", help="快速扫描已验证的缓存根（只读）")
    clean = subcommands.add_parser("clean", help="清理明确选择的规则")
    clean.add_argument("--rule", action="append", required=True, help="选择规则 ID，可重复")
    clean.add_argument("--execute", action="store_true", help="执行真实清理；省略时为 Dry Run")
    clean.add_argument("--confirm", help="真实清理必须精确输入 CLEAN")
    recycle = subcommands.add_parser("recycle-bin", help="独立查询或清空 C 盘回收站")
    recycle.add_argument("--empty", action="store_true", help="清空回收站；省略时只查询")
    recycle.add_argument("--confirm", help="清空时必须精确输入 EMPTY RECYCLE BIN")
    return parser


def _format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    raise AssertionError("unreachable")


def _runtime() -> tuple[KnownFolders, RuleRegistry, SafetyPolicy]:
    folders = discover_known_folders()
    registry = build_m2_registry(folders)
    policy = SafetyPolicy(
        (root for rule in registry.all() for root in rule.roots),
        build_default_deny_roots(folders),
    )
    return folders, registry, policy


def main(argv: Sequence[str] | None = None) -> int:
    """Run the M2 CLI with explicit selection and confirmation for mutation."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        print("C Drive Cleaner v2：M2 快速扫描与安全清理 MVP 已启用。")
        return 0
    if args.command == "recycle-bin":
        try:
            volume = discover_known_folders().system_drive
            recycle = RecycleBinExecutor()
            if args.empty:
                recycle.empty(volume, confirmation=args.confirm or "")
                print("回收站已清空。")
            else:
                info = recycle.query(volume)
                print(f"回收站：{info.item_count} 项，{_format_bytes(info.size_bytes)}")
            return 0
        except (UnsupportedPlatformError, ValueError, OSError) as error:
            parser.error(str(error))
    if args.command in {"scan", "clean"}:
        try:
            folders, registry, policy = _runtime()
        except UnsupportedPlatformError as error:
            parser.error(str(error))
        snapshot = FastScanner(registry).scan()
        if args.command == "scan":
            estimate = _format_bytes(snapshot.estimated_bytes)
            print(f"发现 {len(snapshot.findings)} 个文件，预计可处理 {estimate}")
            for rule in registry.all():
                size = sum(
                    finding.identity.size
                    for finding in snapshot.findings
                    if finding.rule_id == rule.rule_id
                )
                if size:
                    print(f"{rule.rule_id}: {_format_bytes(size)}")
            if snapshot.errors:
                print(f"有 {len(snapshot.errors)} 个位置无法读取，结果可能不完整。")
            return 0
        selected = set(args.rule)
        known = {rule.rule_id for rule in registry.all()}
        unknown = selected - known
        if unknown:
            parser.error(f"未知规则: {', '.join(sorted(unknown))}")
        if args.execute and args.confirm != "CLEAN":
            parser.error("真实清理需要 --confirm CLEAN")
        plan = CleanupPlanner(registry).build(
            finding for finding in snapshot.findings if finding.rule_id in selected
        )
        receipt = CleanupCoordinator(
            DirectFileDeleteExecutor(policy, elevated_checker=is_process_elevated),
            free_space_reader=free_bytes,
        ).execute(plan, volume=folders.system_drive, dry_run=not args.execute)
        mode = "Dry Run" if receipt.dry_run else "真实清理"
        estimate = _format_bytes(receipt.estimated_bytes)
        processed = _format_bytes(receipt.processed_bytes)
        print(f"{mode}：预计 {estimate}，处理 {processed}")
        print(f"观测可用空间增加：{_format_bytes(receipt.observed_freed_bytes)}")
        return 0
    parser.print_help()
    return 0
