"""Tkinter GUI for scan-first, confirm-before-clean workflows."""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from . import __version__
from .cache_rules import RiskLevel, build_rules, safe_allow_roots
from .cleaner import CleanupSummary, clean_candidates
from .disk_analyzer import DirectoryUsage, DiskUsageInfo, get_disk_usage
from .logger import create_run_logger
from .reporting import render_scan_report, write_scan_reports
from .safety import SafetyGuard
from .scanner import FileCandidate, RuleScanResult, scan_rules
from .utils import application_root, format_bytes, is_admin, load_config


@dataclass(frozen=True)
class ScanBundle:
    disk: DiskUsageInfo
    scans: list[RuleScanResult]
    report_path: Path


class CleanerGui:
    """Small desktop shell around the existing safe scanner and cleaner."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.app_root = application_root()
        self.bundle: ScanBundle | None = None
        self.guard: SafetyGuard | None = None
        self.rule_vars: dict[str, tk.BooleanVar] = {}
        self.safe_scan_by_id: dict[str, RuleScanResult] = {}
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()

        root.title(f"C Drive Safe Cleaner v{__version__}")
        root.geometry("920x620")
        root.minsize(820, 520)

        self.status = tk.StringVar(value="准备扫描。不会自动删除任何文件。")
        self.summary = tk.StringVar(value="")
        self.confirm_text = tk.StringVar(value="")

        self._build_layout()
        self._set_busy(False)
        self.start_scan()

    def _build_layout(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text=f"Windows C盘安全清理工具 v{__version__}",
            font=("", 14, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="重新扫描", command=self.start_scan).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(frame, textvariable=self.summary).grid(row=1, column=0, sticky="ew", pady=(10, 8))

        notebook = ttk.Notebook(frame)
        notebook.grid(row=2, column=0, sticky="nsew")
        self.safe_frame = ttk.Frame(notebook, padding=10)
        self.review_frame = ttk.Frame(notebook, padding=10)
        notebook.add(self.safe_frame, text="可勾选清理")
        notebook.add(self.review_frame, text="只读建议")
        self.safe_frame.columnconfigure(0, weight=1)
        self.review_frame.columnconfigure(0, weight=1)
        self.safe_frame.rowconfigure(0, weight=1)
        self.review_frame.rowconfigure(0, weight=1)

        self.safe_canvas = tk.Canvas(self.safe_frame, highlightthickness=0)
        self.safe_scroll = ttk.Scrollbar(self.safe_frame, orient="vertical", command=self.safe_canvas.yview)
        self.safe_list = ttk.Frame(self.safe_canvas)
        self.safe_canvas.create_window((0, 0), window=self.safe_list, anchor="nw")
        self.safe_canvas.configure(yscrollcommand=self.safe_scroll.set)
        self.safe_canvas.grid(row=0, column=0, sticky="nsew")
        self.safe_scroll.grid(row=0, column=1, sticky="ns")
        self.safe_list.bind("<Configure>", lambda _event: self.safe_canvas.configure(scrollregion=self.safe_canvas.bbox("all")))

        columns = ("risk", "name", "size", "files", "skipped", "recommendation")
        self.review = ttk.Treeview(self.review_frame, columns=columns, show="headings", height=12)
        for column, title, width in (
            ("risk", "等级", 90),
            ("name", "项目", 180),
            ("size", "大小", 100),
            ("files", "文件", 70),
            ("skipped", "跳过", 70),
            ("recommendation", "建议", 360),
        ):
            self.review.heading(column, text=title)
            self.review.column(column, width=width, anchor="w")
        self.review.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(self.review_frame, orient="vertical", command=self.review.yview).grid(row=0, column=1, sticky="ns")

        footer = ttk.Frame(frame)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(1, weight=1)
        ttk.Label(footer, text="输入 CLEAN 确认真清理：").grid(row=0, column=0, sticky="w")
        ttk.Entry(footer, textvariable=self.confirm_text, width=12).grid(row=0, column=1, sticky="w", padx=(6, 14))
        self.dry_run_button = ttk.Button(footer, text="模拟所选项", command=self.dry_run_selected)
        self.dry_run_button.grid(row=0, column=2, padx=(0, 8))
        self.clean_button = ttk.Button(footer, text="清理已勾选 SAFE 项", command=self.clean_selected)
        self.clean_button.grid(row=0, column=3)
        ttk.Label(frame, textvariable=self.status).grid(row=4, column=0, sticky="ew", pady=(8, 0))

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.clean_button.configure(state=state)
        self.dry_run_button.configure(state=state)

    def start_scan(self) -> None:
        self._set_busy(True)
        self.status.set("正在扫描内置安全规则。这个过程只读，不会删除文件。")
        self.summary.set("")
        self._clear_results()
        threading.Thread(target=self._scan_worker, daemon=True).start()
        self.root.after(120, self._drain_events)

    def _scan_worker(self) -> None:
        try:
            config = load_config(self.app_root / "config.json")
            logger = create_run_logger(self.app_root / "logs", "scan", dry_run=False)
            disk = get_disk_usage(_system_root())
            rules = build_rules()
            enabled = set(config["enabled_rule_ids"])
            selected_rules = [rule for rule in rules if not enabled or rule.rule_id in enabled]
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
            report = render_scan_report(disk, [], scans)
            latest, _dated = write_scan_reports(self.app_root / "reports", report)
            self.events.put(("scan_done", ScanBundle(disk, scans, latest)))
        except Exception as exc:  # noqa: BLE001 - show unexpected GUI errors.
            self.events.put(("error", exc))

    def _drain_events(self) -> None:
        try:
            while True:
                name, payload = self.events.get_nowait()
                if name == "scan_done":
                    self._show_scan(payload)  # type: ignore[arg-type]
                elif name == "clean_done":
                    summary, dry_run = payload  # type: ignore[misc]
                    self._show_cleanup(summary, dry_run)
                elif name == "error":
                    self._set_busy(False)
                    self.status.set("操作失败。")
                    messagebox.showerror("操作失败", str(payload))
        except queue.Empty:
            pass
        if self.clean_button["state"] == "disabled":
            self.root.after(120, self._drain_events)

    def _clear_results(self) -> None:
        for child in self.safe_list.winfo_children():
            child.destroy()
        for item in self.review.get_children():
            self.review.delete(item)
        self.rule_vars.clear()
        self.safe_scan_by_id.clear()

    def _show_scan(self, bundle: ScanBundle) -> None:
        self.bundle = bundle
        self.guard = SafetyGuard(safe_allow_roots(build_rules()))
        safe_total = sum(item.total_bytes for item in bundle.scans if item.risk is RiskLevel.SAFE)
        self.summary.set(
            f"C盘容量 {format_bytes(bundle.disk.total)}，已用 {format_bytes(bundle.disk.used)}，"
            f"剩余 {format_bytes(bundle.disk.free)}。预计可安全清理 {format_bytes(safe_total)}。"
        )
        self._populate_safe(bundle.scans)
        self._populate_review(bundle.scans)
        self.status.set(f"扫描完成。报告：{bundle.report_path}。管理员权限：{'是' if is_admin() else '否'}。")
        self._set_busy(False)

    def _populate_safe(self, scans: list[RuleScanResult]) -> None:
        safe_scans = [item for item in scans if item.risk is RiskLevel.SAFE and item.file_count]
        if not safe_scans:
            ttk.Label(self.safe_list, text="没有发现可清理的 SAFE 项。").grid(row=0, column=0, sticky="w")
            return
        for row, item in enumerate(safe_scans):
            variable = tk.BooleanVar(value=True)
            self.rule_vars[item.rule_id] = variable
            self.safe_scan_by_id[item.rule_id] = item
            text = (
                f"{item.display_name}   {format_bytes(item.total_bytes)}   "
                f"{item.file_count} 个文件，跳过 {item.skipped_count}"
            )
            ttk.Checkbutton(self.safe_list, text=text, variable=variable).grid(row=row, column=0, sticky="w", pady=3)
            if item.recommendation:
                ttk.Label(self.safe_list, text=item.recommendation, foreground="#555555").grid(row=row, column=1, sticky="w", padx=(14, 0))

    def _populate_review(self, scans: list[RuleScanResult]) -> None:
        for item in scans:
            if item.risk is RiskLevel.SAFE:
                continue
            self.review.insert(
                "",
                "end",
                values=(
                    item.risk.value,
                    item.display_name,
                    format_bytes(item.total_bytes),
                    str(item.file_count),
                    str(item.skipped_count),
                    item.recommendation,
                ),
            )

    def selected_candidates(self) -> list[FileCandidate]:
        chosen: list[FileCandidate] = []
        for rule_id, variable in self.rule_vars.items():
            if variable.get():
                chosen.extend(self.safe_scan_by_id[rule_id].candidates)
        return chosen

    def dry_run_selected(self) -> None:
        self._start_cleanup(dry_run=True)

    def clean_selected(self) -> None:
        if self.confirm_text.get().strip() != "CLEAN":
            messagebox.showwarning("需要确认", "请输入大写 CLEAN 后，才会真实清理已勾选的 SAFE 项。")
            return
        count = len(self.selected_candidates())
        if not count:
            messagebox.showinfo("没有可清理项目", "请至少勾选一个 SAFE 项。")
            return
        if not messagebox.askyesno("确认真实清理", f"即将真实删除 {count} 个 SAFE 缓存文件。是否继续？"):
            return
        self._start_cleanup(dry_run=False)

    def _start_cleanup(self, *, dry_run: bool) -> None:
        if self.guard is None:
            return
        candidates = self.selected_candidates()
        if not candidates:
            messagebox.showinfo("没有可处理项目", "请至少勾选一个 SAFE 项。")
            return
        self._set_busy(True)
        self.status.set("正在模拟清理。" if dry_run else "正在真实清理已勾选 SAFE 项。")
        threading.Thread(
            target=self._clean_worker,
            args=(candidates, self.guard, dry_run),
            daemon=True,
        ).start()
        self.root.after(120, self._drain_events)

    def _clean_worker(self, candidates: list[FileCandidate], guard: SafetyGuard, dry_run: bool) -> None:
        try:
            logger = create_run_logger(self.app_root / "logs", "clean", dry_run=dry_run)
            summary = clean_candidates(candidates, guard, dry_run=dry_run, logger=logger)
            self.events.put(("clean_done", (summary, dry_run)))
        except Exception as exc:  # noqa: BLE001 - show unexpected GUI errors.
            self.events.put(("error", exc))

    def _show_cleanup(self, summary: CleanupSummary, dry_run: bool) -> None:
        self._set_busy(False)
        action = "模拟删除" if dry_run else "成功删除"
        count = summary.simulated_count if dry_run else summary.deleted_count
        self.status.set(
            f"{action} {count} 个文件，影响 {format_bytes(summary.bytes_affected)}；"
            f"拒绝或跳过 {summary.failed_or_skipped_count} 个。"
        )
        if dry_run:
            messagebox.showinfo("模拟完成", self.status.get())
            return
        messagebox.showinfo("清理完成", self.status.get())
        self.confirm_text.set("")
        self.start_scan()


def _system_root() -> Path:
    drive = os.environ.get("SystemDrive", "C:")
    return Path(drive + "\\") if drive.endswith(":") else Path(drive)


def run_gui() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    CleanerGui(root)
    root.mainloop()
