"""User-friendly command line entry point for C Drive Safe Cleaner."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream is not None and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

if __package__ in {None, ""}:
    sys.path.insert(0, os.fspath(Path(__file__).resolve().parent.parent))
    from src import __version__
    from src.cache_rules import RiskLevel, build_rules, safe_allow_roots
    from src.cleaner import CleanupSummary, clean_candidates
    from src.disk_analyzer import (
        DirectoryUsage,
        DiskUsageInfo,
        analyze_top_directories,
        get_disk_usage,
    )
    from src.logger import create_run_logger
    from src.reporting import render_scan_report, write_scan_reports
    from src.safety import SafetyGuard
    from src.scanner import FileCandidate, RuleScanResult, scan_rules
    from src.utils import application_root, format_bytes, is_admin, load_config
else:
    from . import __version__
    from .cache_rules import RiskLevel, build_rules, safe_allow_roots
    from .cleaner import CleanupSummary, clean_candidates
    from .disk_analyzer import (
        DirectoryUsage,
        DiskUsageInfo,
        analyze_top_directories,
        get_disk_usage,
    )
    from .logger import create_run_logger
    from .reporting import render_scan_report, write_scan_reports
    from .safety import SafetyGuard
    from .scanner import FileCandidate, RuleScanResult, scan_rules
    from .utils import application_root, format_bytes, is_admin, load_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="保守型 Windows C 盘空间审计与安全缓存清理工具"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="完整模拟 SAFE 清理流程，但不修改任何文件",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="扫描、生成报告后退出，不进入菜单",
    )
    parser.add_argument(
        "--skip-disk-audit",
        action="store_true",
        help="跳过耗时的 C 盘顶层目录 TOP 20 审计",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动图形界面：先扫描，再由用户勾选 SAFE 项并确认清理",
    )
    return parser


def _system_root() -> Path:
    drive = os.environ.get("SystemDrive", "C:")
    return Path(drive + "\\") if drive.endswith(":") else Path(drive)


def _print_banner(disk: DiskUsageInfo) -> None:
    print("=" * 56)
    print(f" Windows C盘安全清理工具 v{__version__}")
    print("=" * 56)
    print(f"C盘容量：{format_bytes(disk.total)}")
    print(f"已使用：  {format_bytes(disk.used)}")
    print(f"剩余：    {format_bytes(disk.free)}")
    print(f"管理员权限：{'是' if is_admin() else '否（这是正常且推荐的）'}")


def _print_scan_summary(scans: Iterable[RuleScanResult]) -> None:
    values = list(scans)
    headings = (
        (RiskLevel.SAFE, "可安全清理（仍需确认）"),
        (RiskLevel.CAUTION, "需要谨慎确认（本版仅报告）"),
        (RiskLevel.MANUAL, "仅报告，不自动处理"),
        (RiskLevel.NEVER_DELETE, "禁止删除"),
    )
    for risk, heading in headings:
        print(f"\n【{heading}】")
        matches = [value for value in values if value.risk is risk]
        if not matches:
            print("无")
        for value in matches:
            print(
                f"{value.display_name:<24} {format_bytes(value.total_bytes):>12}  "
                f"文件 {value.file_count}  跳过 {value.skipped_count}"
            )
    safe_total = sum(value.total_bytes for value in values if value.risk is RiskLevel.SAFE)
    print(f"\n预计最多可安全释放：{format_bytes(safe_total)}")


def _safe_candidates(scans: Iterable[RuleScanResult]) -> list[FileCandidate]:
    return [candidate for scan in scans for candidate in scan.candidates]


def _show_plan(candidates: Iterable[FileCandidate]) -> list[FileCandidate]:
    values = list(candidates)
    grouped: dict[str, tuple[int, int]] = {}
    for item in values:
        count, size = grouped.get(item.display_name, (0, 0))
        grouped[item.display_name] = (count + 1, size + item.size)
    print("\n即将处理的 SAFE 项目：")
    for name, (count, size) in grouped.items():
        print(f"- {name}: {count} 个文件，{format_bytes(size)}")
    print(f"合计：{len(values)} 个文件，{format_bytes(sum(x.size for x in values))}")
    return values


def _run_cleanup(
    candidates: Iterable[FileCandidate],
    guard: SafetyGuard,
    *,
    dry_run: bool,
    logger: logging.Logger,
) -> CleanupSummary:
    values = _show_plan(candidates)
    if not values:
        print("没有可处理的 SAFE 文件。")
        return CleanupSummary(dry_run=dry_run)
    if not dry_run:
        print("\n只有输入大写 CLEAN 才会执行。输入其他任何内容都会取消。")
        if input("确认：").strip() != "CLEAN":
            print("已取消，没有删除任何文件。")
            return CleanupSummary(dry_run=False)
    before_free = get_disk_usage(_system_root()).free
    summary = clean_candidates(values, guard, dry_run=dry_run, logger=logger)
    after_free = get_disk_usage(_system_root()).free
    label = "模拟删除" if dry_run else "成功删除"
    count = summary.simulated_count if dry_run else summary.deleted_count
    print(f"\n{label}：{count} 个文件，{format_bytes(summary.bytes_affected)}")
    print(f"拒绝或跳过：{summary.failed_or_skipped_count} 个文件")
    logger.info("free_before=%d free_after=%d delta=%d", before_free, after_free, after_free - before_free)
    if dry_run:
        print("DRY RUN 完成：实际删除文件数量 = 0")
    return summary


def _custom_candidates(scans: list[RuleScanResult]) -> list[FileCandidate]:
    safe = [item for item in scans if item.risk is RiskLevel.SAFE and item.file_count]
    if not safe:
        return []
    print("\n可选 SAFE 项目：")
    for index, item in enumerate(safe, 1):
        print(f"{index}. {item.display_name} ({format_bytes(item.total_bytes)})")
    raw = input("输入编号（多个用英文逗号分隔，直接回车取消）：").strip()
    if not raw:
        return []
    try:
        selected = {int(value.strip()) for value in raw.split(",")}
    except ValueError:
        print("输入无效，已取消。")
        return []
    chosen = [item for index, item in enumerate(safe, 1) if index in selected]
    return [candidate for item in chosen for candidate in item.candidates]


def _interactive_menu(
    scans: list[RuleScanResult],
    guard: SafetyGuard,
    log_dir: Path,
    latest_report: Path,
) -> None:
    while True:
        print(
            "\n菜单：\n"
            "1 保守安全清理\n"
            "2 自定义选择 SAFE 项目\n"
            "3 查看详细扫描结果\n"
            "4 显示空间分析报告位置\n"
            "5 仅进行 Dry Run\n"
            "0 退出"
        )
        choice = input("请选择：").strip()
        if choice == "0":
            print("已退出。")
            return
        if choice == "1":
            clean_logger = create_run_logger(log_dir, "clean", dry_run=False)
            _run_cleanup(_safe_candidates(scans), guard, dry_run=False, logger=clean_logger)
        elif choice == "2":
            chosen = _custom_candidates(scans)
            if chosen:
                clean_logger = create_run_logger(log_dir, "clean", dry_run=False)
                _run_cleanup(chosen, guard, dry_run=False, logger=clean_logger)
        elif choice == "3":
            for item in scans:
                print(
                    f"{item.risk.value:<13} {item.display_name}: "
                    f"{item.file_count} 文件 / {format_bytes(item.total_bytes)} / "
                    f"跳过 {item.skipped_count}"
                )
                if item.recommendation:
                    print(f"  {item.recommendation}")
        elif choice == "4":
            print(f"报告：{latest_report}")
        elif choice == "5":
            clean_logger = create_run_logger(log_dir, "clean", dry_run=True)
            _run_cleanup(_safe_candidates(scans), guard, dry_run=True, logger=clean_logger)
        else:
            print("无法识别该选项，请重试。")


def run(argv: list[str] | None = None) -> int:
    """Run one scan and optionally a guarded cleanup."""

    args = _parser().parse_args(argv)
    if args.gui:
        if __package__ in {None, ""}:
            from src.gui import run_gui
        else:
            from .gui import run_gui

        run_gui()
        return 0

    root = application_root()
    config = load_config(root / "config.json")
    logger = create_run_logger(root / "logs", "scan", dry_run=args.dry_run)
    drive_root = _system_root()
    disk = get_disk_usage(drive_root)
    _print_banner(disk)

    rules = build_rules()
    enabled = set(config["enabled_rule_ids"])
    selected_rules = [rule for rule in rules if not enabled or rule.rule_id in enabled]
    print("\n正在扫描内置安全规则（不会删除文件）……")
    scans = scan_rules(selected_rules)
    for item in scans:
        logger.info(
            "scan rule=%s risk=%s roots=%d files=%d bytes=%d skipped=%d",
            item.rule_id,
            item.risk.value,
            item.roots_found,
            item.file_count,
            item.total_bytes,
            item.skipped_count,
        )

    top: list[DirectoryUsage] = []
    if config["audit_top_level"] and not args.skip_disk_audit:
        print("正在进行 C 盘顶层目录只读审计，这可能需要一些时间……")
        top = analyze_top_directories(drive_root, config["top_directory_limit"])
    report = render_scan_report(disk, top, scans)
    latest, dated = write_scan_reports(root / "reports", report)
    logger.info("reports=%s;%s", latest, dated)
    print("\n安全扫描完成。")
    _print_scan_summary(scans)
    print(f"\n报告已生成：{latest}")

    guard = SafetyGuard(safe_allow_roots(selected_rules))
    if args.dry_run:
        clean_logger = create_run_logger(root / "logs", "clean", dry_run=True)
        summary = _run_cleanup(
            _safe_candidates(scans), guard, dry_run=True, logger=clean_logger
        )
        return 0 if summary.deleted_count == 0 else 3
    if args.scan_only or not sys.stdin.isatty():
        print("仅扫描模式结束，没有删除任何文件。")
        return 0
    _interactive_menu(scans, guard, root / "logs", latest)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
