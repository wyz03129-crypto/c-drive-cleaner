"""Plain-text audit report generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from .cache_rules import RiskLevel
from .disk_analyzer import DirectoryUsage, DiskUsageInfo
from .scanner import RuleScanResult
from .utils import format_bytes


def _risk_heading(risk: RiskLevel) -> str:
    return {
        RiskLevel.SAFE: "可安全清理（仍需确认）",
        RiskLevel.CAUTION: "需要谨慎确认（v1.0.0 仅报告）",
        RiskLevel.MANUAL: "仅报告/人工处理",
        RiskLevel.NEVER_DELETE: "系统保护/禁止删除",
    }[risk]


def render_scan_report(
    disk: DiskUsageInfo,
    top_directories: Iterable[DirectoryUsage],
    scans: Iterable[RuleScanResult],
) -> str:
    """Render a transparent, local-only scan report."""

    lines = [
        "C Drive Safe Cleaner v1.0.0 扫描报告",
        f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        "本报告只依据内置规则分类；目录很大不代表可以删除。",
        "",
        "【磁盘空间】",
        f"总容量：{format_bytes(disk.total)}",
        f"已使用：{format_bytes(disk.used)}",
        f"剩余：{format_bytes(disk.free)}",
        "",
        "【顶层目录占用 TOP 20（只审计）】",
    ]
    top_list = list(top_directories)
    if not top_list:
        lines.append("未执行或未获得顶层目录分析。")
    for item in top_list:
        lines.append(
            f"{item.path} | {format_bytes(item.size)} | 文件 {item.file_count} | "
            f"{item.owner_hint} | MANUAL | 读取错误 {item.error_count}"
        )

    scan_list = list(scans)
    for risk in RiskLevel:
        lines.extend(("", f"【{_risk_heading(risk)}】"))
        matching = [item for item in scan_list if item.risk is risk]
        if not matching:
            lines.append("无")
        for item in matching:
            lines.append(
                f"{item.display_name} | {format_bytes(item.total_bytes)} | "
                f"文件 {item.file_count} | 跳过 {item.skipped_count} | {item.risk.value}"
            )
            if item.recommendation:
                lines.append(f"  建议：{item.recommendation}")
            for error in item.errors[:20]:
                lines.append(f"  扫描提示：{error}")
            if len(item.errors) > 20:
                lines.append(f"  另有 {len(item.errors) - 20} 条提示，已省略。")

    lines.extend(
        (
            "",
            "【系统保护摘要】",
            "Windows 核心目录、Program Files、WindowsApps、恢复/启动区域、",
            "用户桌面/文档/下载/图片/视频/音乐/OneDrive、浏览器账号与凭据、",
            "WPS 备份/恢复/云文档、源码仓库和数据库均不属于自动清理对象。",
            "",
            "【推荐操作】",
            "1. 第一次使用先执行 Dry Run。",
            "2. MANUAL 项目使用 Windows 官方存储清理或由专业人员判断。",
            "3. 缓存正在使用或权限不足时，程序会跳过；不要强制改权限。",
            "4. 本程序完全离线，不上传报告或文件。",
        )
    )
    return "\n".join(lines) + "\n"


def write_scan_reports(report_dir: Path, content: str) -> tuple[Path, Path]:
    """Write both timestamped and latest scan reports."""

    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dated = report_dir / f"scan_report_{stamp}.txt"
    latest = report_dir / "latest_scan_report.txt"
    dated.write_text(content, encoding="utf-8")
    latest.write_text(content, encoding="utf-8")
    return latest, dated
