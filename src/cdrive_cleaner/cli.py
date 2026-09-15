"""Command-line shell for the v2 application."""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Sequence
from contextlib import suppress

from . import __version__
from .analysis import FastScanner, StorageAnalyzer, WindowsAdvancedInspector
from .app import CleanupCoordinator, CleanupPlanner
from .domain import AdvancedAction
from .domain.errors import SafetyDeniedError, UnsupportedPlatformError
from .executors import DirectFileDeleteExecutor, RecycleBinExecutor, WindowsAdvancedExecutor
from .persistence import StorageSnapshotCache
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
    analyze = subcommands.add_parser("analyze", help="只读分析 C 盘空间占用")
    analyze.add_argument("--top", type=int, default=20, help="显示前 N 项（1-1000）")
    analyze.add_argument("--cached", action="store_true", help="立即显示上次结果，不重新扫描")
    clean = subcommands.add_parser("clean", help="清理明确选择的规则")
    clean.add_argument("--rule", action="append", required=True, help="选择规则 ID，可重复")
    clean.add_argument("--execute", action="store_true", help="执行真实清理；省略时为 Dry Run")
    clean.add_argument("--confirm", help="真实清理必须精确输入 CLEAN")
    recycle = subcommands.add_parser("recycle-bin", help="独立查询或清空 C 盘回收站")
    recycle.add_argument("--empty", action="store_true", help="清空回收站；省略时只查询")
    recycle.add_argument("--confirm", help="清空时必须精确输入 EMPTY RECYCLE BIN")
    advanced = subcommands.add_parser("advanced", help="分析或执行 Windows 官方高级操作")
    advanced_sub = advanced.add_subparsers(dest="advanced_command", required=True)
    advanced_sub.add_parser("inspect", help="只读检查休眠、分页和虚拟磁盘")
    run = advanced_sub.add_parser("run", help="运行一个固定的官方操作")
    run.add_argument("action", choices=[action.value for action in AdvancedAction])
    run.add_argument("--confirm", default="", help="变更操作所需的专用确认词")
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
        print("C Drive Cleaner v2：M3 只读空间分析器与 M2 安全清理已启用。")
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
    if args.command == "advanced":
        try:
            if args.advanced_command == "inspect":
                findings = WindowsAdvancedInspector().inspect(discover_known_folders())
                if not findings:
                    print("未发现受支持的高级空间项目。")
                for finding in findings:
                    print(
                        f"{finding.category}: {_format_bytes(finding.size_bytes)}  "
                        f"{finding.path}（{finding.guidance}）"
                    )
                return 0
            result = WindowsAdvancedExecutor().execute(
                AdvancedAction(args.action), confirmation=args.confirm
            )
            if result.stdout:
                print(result.stdout.rstrip())
            if result.stderr:
                print(result.stderr.rstrip())
            return result.return_code
        except (UnsupportedPlatformError, SafetyDeniedError, OSError) as error:
            parser.error(str(error))
    if args.command == "analyze":
        try:
            folders = discover_known_folders()
            root = folders.system_drive
            disk = shutil.disk_usage(root)
            cache = StorageSnapshotCache(
                folders.local_app_data / "CDriveCleaner/cache/storage.json"
            )
            storage_snapshot = cache.load(expected_root=root) if args.cached else None
            if storage_snapshot is None:
                storage_snapshot = StorageAnalyzer(top_n=args.top).analyze(root)
                with suppress(OSError):
                    cache.save(storage_snapshot)
        except (UnsupportedPlatformError, OSError, ValueError) as error:
            parser.error(str(error))
        print(
            f"C 盘：总计 {_format_bytes(disk.total)}，"
            f"已用 {_format_bytes(disk.used)}，可用 {_format_bytes(disk.free)}"
        )
        print(
            f"已统计 {_format_bytes(storage_snapshot.total_logical_bytes)} / "
            f"{storage_snapshot.total_files} 个文件；目录覆盖率 "
            f"{storage_snapshot.coverage.directory_ratio:.1%}"
        )
        if args.cached:
            print(f"缓存快照时间：{storage_snapshot.finished_at.isoformat()}（仅供显示）")
        print("最大目录：")
        for directory_item in storage_snapshot.top_directories:
            print(f"{_format_bytes(directory_item.logical_bytes):>10}  {directory_item.path}")
        print("最大文件：")
        for file_item in storage_snapshot.top_files:
            print(f"{_format_bytes(file_item.logical_bytes):>10}  {file_item.path}")
        if (
            storage_snapshot.coverage.unreadable_directories
            or storage_snapshot.coverage.unreadable_entries
        ):
            print("部分位置无法读取，以上统计不完整。")
        return 0
    if args.command in {"scan", "clean"}:
        try:
            folders, registry, policy = _runtime()
        except UnsupportedPlatformError as error:
            parser.error(str(error))
        quick_snapshot = FastScanner(registry).scan()
        if args.command == "scan":
            estimate = _format_bytes(quick_snapshot.estimated_bytes)
            print(f"发现 {len(quick_snapshot.findings)} 个文件，预计可处理 {estimate}")
            for rule in registry.all():
                size = sum(
                    finding.identity.size
                    for finding in quick_snapshot.findings
                    if finding.rule_id == rule.rule_id
                )
                if size:
                    print(f"{rule.rule_id}: {_format_bytes(size)}")
            if quick_snapshot.errors:
                print(f"有 {len(quick_snapshot.errors)} 个位置无法读取，结果可能不完整。")
            return 0
        selected = set(args.rule)
        known = {rule.rule_id for rule in registry.all()}
        unknown = selected - known
        if unknown:
            parser.error(f"未知规则: {', '.join(sorted(unknown))}")
        if args.execute and args.confirm != "CLEAN":
            parser.error("真实清理需要 --confirm CLEAN")
        plan = CleanupPlanner(registry).build(
            finding for finding in quick_snapshot.findings if finding.rule_id in selected
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
