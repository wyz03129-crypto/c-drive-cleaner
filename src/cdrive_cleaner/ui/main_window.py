"""Consumer-facing Windows GUI for scan, clean, analysis, and advanced guidance."""

from __future__ import annotations

import shutil
import sys
from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cdrive_cleaner.analysis import CancellationToken, FastScanner, StorageAnalyzer
from cdrive_cleaner.analysis.duplicates import DuplicateAnalyzer, DuplicateSnapshot
from cdrive_cleaner.analysis.windows_advanced import WindowsAdvancedInspector
from cdrive_cleaner.app import CleanupCoordinator, CleanupPlanner
from cdrive_cleaner.app.result_summary import failure_summary
from cdrive_cleaner.domain import (
    AdvancedAction,
    CleanupReceipt,
    RiskLevel,
    ScanSnapshot,
    StorageSnapshot,
)
from cdrive_cleaner.executors import (
    DirectFileDeleteExecutor,
    RecycleBinExecutor,
    WindowsAdvancedExecutor,
)
from cdrive_cleaner.executors.quarantine import QuarantineExecutor, QuarantineStore, RecoveryEntry
from cdrive_cleaner.persistence import append_history, export_diagnostics, load_history
from cdrive_cleaner.rules import build_m2_registry
from cdrive_cleaner.safety import SafetyPolicy
from cdrive_cleaner.safety.defaults import build_default_deny_roots
from cdrive_cleaner.windows import discover_known_folders
from cdrive_cleaner.windows.disk_space import free_bytes
from cdrive_cleaner.windows.elevation import is_process_elevated, relaunch_elevated

from .storage_browser import StorageBrowser
from .workers import FunctionWorker


def _size(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return "0 B"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("C Drive Cleaner")
        self.resize(980, 680)
        self._pool = QThreadPool.globalInstance()
        self._token: CancellationToken | None = None
        self._snapshot: ScanSnapshot | None = None
        self._workers: set[FunctionWorker] = set()
        self._busy = False
        self._progress = (0, 0)
        self._vault_root: Path | None = None
        self._folders = discover_known_folders()
        self._registry = build_m2_registry(self._folders)
        self._policy = SafetyPolicy(
            (root for rule in self._registry.all() for root in rule.roots),
            build_default_deny_roots(self._folders),
        )
        self.setCentralWidget(self._build_tabs())
        self._refresh_disk()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._show_progress)
        self._timer.start(250)

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._dashboard(), "概览")
        tabs.addTab(self._quick_clean(), "快速清理")
        tabs.addTab(self._analysis(), "空间分析")
        tabs.addTab(self._duplicates(), "重复文件")
        tabs.addTab(self._advanced(), "高级优化")
        tabs.addTab(self._history(), "清理历史")
        tabs.addTab(self._recovery(), "隔离与恢复")
        return tabs

    def _recovery(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(
            "选择其他磁盘上的私人文件夹作为隔离区。恢复记录绑定本机 Windows 用户；"
            "备份内容未加密，请勿放入共享/同步文件夹。默认总配额 10 GB，不自动过期删除。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.vault_label = QLabel("尚未选择隔离区")
        self.vault_label.setWordWrap(True)
        layout.addWidget(self.vault_label)
        buttons = QHBoxLayout()
        for label, callback in (
            ("选择/打开隔离区", self._choose_vault),
            ("刷新记录", self._load_recovery),
            ("恢复所选备份", self._restore_recovery),
            ("永久删除所选备份", self._purge_recovery),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.recovery_cancel = QPushButton("取消恢复（保留备份）")
        self.recovery_cancel.setEnabled(False)
        self.recovery_cancel.clicked.connect(self._cancel)
        layout.addWidget(self.recovery_cancel)
        self.recovery_table = QTableWidget(0, 4)
        self.recovery_table.setHorizontalHeaderLabels(("原文件", "大小", "状态", "备份时间"))
        self.recovery_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recovery_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recovery_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recovery_table.setColumnWidth(0, 350)
        self.recovery_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.recovery_table)
        return page

    def _choose_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择其他盘的私人文件夹或已有隔离区")
        if not folder:
            return
        root = Path(folder)
        if root.name != "CDriveCleaner-Quarantine":
            root /= "CDriveCleaner-Quarantine"
        self._vault_root = root
        self.vault_label.setText(str(root))

        def initialize() -> tuple[RecoveryEntry, ...]:
            store = QuarantineStore(root)
            store.initialize()
            return store.entries()

        self._run(initialize, self._recovery_loaded)

    def _load_recovery(self) -> None:
        if self._vault_root is not None:
            root = self._vault_root
            self._run(lambda: QuarantineStore(root).entries(), self._recovery_loaded)

    def _recovery_loaded(self, entries: Any) -> None:
        self.recovery_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for col, value in enumerate(
                (entry.original or entry.entry_id, _size(entry.size), entry.state, entry.created)
            ):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, entry.entry_id)
                cell.setToolTip(value)
                self.recovery_table.setItem(row, col, cell)

    def _recovery_selection(self) -> tuple[QuarantineStore, str] | None:
        row = self.recovery_table.currentRow()
        cell = self.recovery_table.item(row, 0)
        if self._vault_root is None or cell is None:
            QMessageBox.information(self, "未选择备份", "请先打开隔离区并选择一条记录。")
            return None
        return QuarantineStore(self._vault_root), str(cell.data(Qt.ItemDataRole.UserRole))

    def _restore_recovery(self) -> None:
        selected = self._recovery_selection()
        if selected is None:
            return
        answer = QMessageBox.question(
            self,
            "确认恢复",
            "恢复到原路径，不覆盖已有文件；会重新占用原磁盘空间。请先关闭相关应用。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        store, entry_id = selected
        token = CancellationToken()
        self._token = token
        self.recovery_cancel.setEnabled(True)

        def restore() -> tuple[RecoveryEntry, ...]:
            store.restore(entry_id, self._registry, self._policy, token=token)
            return store.entries()

        self._run(restore, self._recovery_loaded)

    def _purge_recovery(self) -> None:
        selected = self._recovery_selection()
        if selected is None:
            return
        phrase, accepted = QInputDialog.getText(
            self, "永久删除备份", "本操作只删除所选备份，之后不能用它恢复原文件。请输入：删除备份"
        )
        if not accepted or phrase != "删除备份":
            return
        store, entry_id = selected

        def purge() -> tuple[RecoveryEntry, ...]:
            store.purge(entry_id, confirmation="DELETE BACKUP")
            return store.entries()

        self._run(purge, self._recovery_loaded)

    def _duplicates(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        note = QLabel(
            "选择文件夹，比对 ≥ 1 MB 文件的完整内容（SHA-256）。硬链接不算重复。"
            "最多检查 10 万个文件；仅分析，不自动删除任何副本。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        start = QPushButton("选择文件夹并查找重复文件")
        start.clicked.connect(self._start_duplicates)
        self.duplicate_cancel = QPushButton("取消重复文件分析")
        self.duplicate_cancel.setEnabled(False)
        self.duplicate_cancel.clicked.connect(self._cancel)
        layout.addWidget(start)
        layout.addWidget(self.duplicate_cancel)
        self.duplicate_output = QTextEdit()
        self.duplicate_output.setReadOnly(True)
        layout.addWidget(self.duplicate_output)
        page.setLayout(layout)
        return page

    def _start_duplicates(self) -> None:
        if self._busy:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择需要分析的文件夹")
        if not folder:
            return
        token = CancellationToken()
        self._token = token
        self.duplicate_cancel.setEnabled(True)
        self.duplicate_output.setPlainText("正在读取并比对文件内容，大文件可能耗时较长……")
        self._run(
            lambda: DuplicateAnalyzer().analyze(Path(folder), token=token), self._duplicates_done
        )

    def _duplicates_done(self, value: object) -> None:
        if not isinstance(value, DuplicateSnapshot):
            return
        lines = [
            f"检查 {value.scanned_files:,} 个文件，跳过 {value.skipped} 项。"
            f"{'已取消。' if value.cancelled else ''}"
            f"{'达到数量上限，结果不完整。' if value.limit_reached else ''}",
            f"发现 {len(value.groups)} 组内容相同文件。结果只是扫描时的观察，"
            "副本可能分别被项目引用；不代表可以安全删除。",
        ]
        for group in value.groups[:500]:
            lines.append(f"\n每份 {_size(group.size)}，{len(group.paths)} 份：")
            lines.extend(str(path) for path in group.paths[:100])
            if len(group.paths) > 100:
                lines.append("该组仅显示前 100 条路径。")
        if len(value.groups) > 500:
            lines.append("仅显示前 500 组；请缩小扫描文件夹。")
        self.duplicate_output.setPlainText("\n".join(lines))

    def _dashboard(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        self.disk_label = QLabel()
        self.disk_label.setStyleSheet("font-size: 22px; font-weight: 600; padding: 24px;")
        layout.addWidget(self.disk_label)
        explanation = QLabel(
            "先扫描，再选择需要清理的类别。程序不会自动删除用户文档或系统核心文件。"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        diagnostic_button = QPushButton("导出隐私安全诊断包")
        diagnostic_button.clicked.connect(self._export_diagnostics)
        layout.addWidget(diagnostic_button)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def _quick_clean(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        buttons = QHBoxLayout()
        self.scan_button = QPushButton("开始扫描")
        self.cancel_button = QPushButton("取消")
        self.clean_button = QPushButton("清理已选项目")
        self.cancel_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self.scan_button.clicked.connect(self._start_quick_scan)
        self.cancel_button.clicked.connect(self._cancel)
        self.clean_button.clicked.connect(self._confirm_clean)
        for button in (self.scan_button, self.cancel_button, self.clean_button):
            buttons.addWidget(button)
        self.quick_status = QLabel("尚未扫描")
        self.quick_table = QTableWidget(0, 5)
        self.quick_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.quick_table.setHorizontalHeaderLabels(("选择", "类别", "风险", "预计空间", "说明"))
        self.quick_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.quick_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addLayout(buttons)
        self.cleanup_mode = QComboBox()
        self.cleanup_mode.addItems(("备份后清理（可恢复，需其他盘隔离区）", "永久清理（不可恢复）"))
        layout.addWidget(self.cleanup_mode)
        layout.addWidget(self.quick_status)
        layout.addWidget(self.quick_table)
        self.cleanup_details = QTextEdit()
        self.cleanup_details.setReadOnly(True)
        self.cleanup_details.setMaximumHeight(140)
        layout.addWidget(self.cleanup_details)
        page.setLayout(layout)
        return page

    def _analysis(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        buttons = QHBoxLayout()
        self.analysis_button = QPushButton("分析系统盘")
        self.analysis_cancel = QPushButton("取消")
        self.large_file_threshold = QComboBox()
        self.large_file_threshold.addItem("大文件 ≥ 100 MB", 100 * 1024**2)
        self.large_file_threshold.addItem("大文件 ≥ 500 MB", 500 * 1024**2)
        self.large_file_threshold.addItem("大文件 ≥ 1 GB", 1024**3)
        self.large_file_threshold.addItem("大文件 ≥ 5 GB", 5 * 1024**3)
        self.analysis_cancel.setEnabled(False)
        self.analysis_button.clicked.connect(self._start_analysis)
        self.analysis_cancel.clicked.connect(self._cancel)
        buttons.addWidget(self.analysis_button)
        buttons.addWidget(self.large_file_threshold)
        buttons.addWidget(self.analysis_cancel)
        self.analysis_output = QLabel("尚未分析")
        self.storage_browser = StorageBrowser(self._folders.profile, self._folders.system_drive)
        layout.addLayout(buttons)
        layout.addWidget(self.analysis_output)
        layout.addWidget(self.storage_browser)
        page.setLayout(layout)
        return page

    def _advanced(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        note = QLabel(
            "高级操作只调用 Windows 官方工具，不直接删除 WinSxS、休眠文件、分页文件或虚拟磁盘。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QGridLayout()
        inspect_button = QPushButton("检查高级空间占用")
        component_button = QPushButton("分析组件存储")
        clean_component_button = QPushButton("清理组件存储")
        enable_hibernation_button = QPushButton("恢复休眠")
        hibernation_button = QPushButton("关闭休眠并释放空间")
        settings_button = QPushButton("打开存储设置")
        recycle_button = QPushButton("检查回收站")
        empty_recycle_button = QPushButton("清空回收站")
        inspect_button.clicked.connect(self._inspect_advanced)
        component_button.clicked.connect(
            lambda: self._run_advanced(AdvancedAction.ANALYZE_COMPONENT_STORE)
        )
        clean_component_button.clicked.connect(self._confirm_component_cleanup)
        enable_hibernation_button.clicked.connect(self._confirm_enable_hibernation)
        hibernation_button.clicked.connect(self._confirm_disable_hibernation)
        settings_button.clicked.connect(
            lambda: self._run_advanced(AdvancedAction.OPEN_STORAGE_SETTINGS)
        )
        recycle_button.clicked.connect(self._inspect_recycle_bin)
        empty_recycle_button.clicked.connect(self._confirm_empty_recycle_bin)
        for index, button in enumerate(
            (
                inspect_button,
                component_button,
                clean_component_button,
                enable_hibernation_button,
                hibernation_button,
                settings_button,
                recycle_button,
                empty_recycle_button,
            )
        ):
            buttons.addWidget(button, index // 4, index % 4)
        self.advanced_output = QTextEdit()
        self.advanced_output.setReadOnly(True)
        layout.addLayout(buttons)
        layout.addWidget(self.advanced_output)
        page.setLayout(layout)
        return page

    def _history(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        refresh = QPushButton("刷新清理历史")
        refresh.clicked.connect(self._refresh_history)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ("完成时间", "预计", "已处理", "实际增加", "结果")
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(refresh)
        layout.addWidget(self.history_table)
        page.setLayout(layout)
        self._refresh_history()
        return page

    def _refresh_disk(self) -> None:
        disk = shutil.disk_usage(self._folders.system_drive)
        self.disk_label.setText(
            f"系统盘 {self._folders.system_drive}  总容量 {_size(disk.total)}\n"
            f"已使用 {_size(disk.used)}  ·  剩余 {_size(disk.free)}"
        )

    def _run(self, operation: Any, completed: Any) -> None:
        if self._busy:
            return
        self._set_busy(True)
        worker = FunctionWorker(operation)
        self._workers.add(worker)
        worker.signals.completed.connect(self._worker_finished)
        worker.signals.completed.connect(completed)
        worker.signals.completed.connect(lambda _value, item=worker: self._workers.discard(item))
        worker.signals.failed.connect(self._worker_finished)
        worker.signals.failed.connect(self._failed)
        worker.signals.failed.connect(lambda _value, item=worker: self._workers.discard(item))
        self._pool.start(worker)

    def _start_quick_scan(self) -> None:
        if self._busy:
            return
        self._snapshot = None
        self.clean_button.setEnabled(False)
        self._token = CancellationToken()
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.quick_status.setText("正在扫描安全缓存……")
        token = self._token
        self._run(lambda: FastScanner(self._registry).scan(token=token), self._scan_done)

    def _scan_done(self, value: object) -> None:
        snapshot = value
        if not isinstance(snapshot, ScanSnapshot):
            return
        self._snapshot = snapshot
        grouped: dict[str, int] = defaultdict(int)
        for finding in snapshot.findings:
            grouped[finding.rule_id] += finding.identity.size
        self.quick_table.setRowCount(0)
        for rule in self._registry.all():
            if not grouped[rule.rule_id]:
                continue
            row = self.quick_table.rowCount()
            self.quick_table.insertRow(row)
            choice = QTableWidgetItem()
            # Large application-managed caches require a separate, deliberate opt-in.
            checked = rule.default_selected
            choice.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            if rule.risk >= RiskLevel.MANUAL:
                choice.setFlags(Qt.ItemFlag.ItemIsEnabled)
            choice.setData(Qt.ItemDataRole.UserRole, rule.rule_id)
            self.quick_table.setItem(row, 0, choice)
            self.quick_table.setItem(row, 1, QTableWidgetItem(rule.title))
            self.quick_table.setItem(row, 2, QTableWidgetItem(rule.risk.name))
            self.quick_table.setItem(row, 3, QTableWidgetItem(_size(grouped[rule.rule_id])))
            details = rule.description
            if rule.blocking_processes:
                details += "；请先退出：" + ", ".join(rule.blocking_processes)
            if rule.min_age_days:
                details += f"；保留最近 {rule.min_age_days} 天"
            self.quick_table.setItem(row, 4, QTableWidgetItem(details))
        self.quick_status.setText(
            f"{'部分结果（已取消）' if snapshot.cancelled else '扫描完成'}："
            f"发现 {len(snapshot.findings)} 个文件，识别总量 {_size(snapshot.estimated_bytes)}"
            f"（包含仅分析项）；读取错误 {len(snapshot.errors)}"
        )
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.clean_button.setEnabled(bool(snapshot.findings))

    def _selected_rules(self) -> set[str]:
        return {
            str(item.data(Qt.ItemDataRole.UserRole))
            for row in range(self.quick_table.rowCount())
            if (item := self.quick_table.item(row, 0)) is not None
            and item.checkState() == Qt.CheckState.Checked
        }

    def _confirm_clean(self) -> None:
        if self._busy:
            return
        if self._snapshot is None or not (selected := self._selected_rules()):
            QMessageBox.information(self, "没有选择", "请选择至少一个清理类别。")
            return
        chosen = [r for r in self._registry.all() if r.rule_id in selected]
        recoverable = self.cleanup_mode.currentIndex() == 0
        if recoverable and self._vault_root is None:
            QMessageBox.information(
                self, "需要隔离区", "请先在“隔离与恢复”页选择其他磁盘上的私人文件夹。"
            )
            return
        if recoverable and any(rule.requires_elevation for rule in chosen):
            QMessageBox.information(
                self,
                "不支持该备份类别",
                "可恢复模式暂不处理需要管理员的类别。请取消勾选，或明确改用永久清理模式。",
            )
            return
        if any(r.requires_elevation for r in chosen) and not self._ensure_elevated():
            return
        estimate = sum(f.identity.size for f in self._snapshot.findings if f.rule_id in selected)
        answer = QMessageBox.question(
            self,
            "确认清理",
            f"选择 {len(chosen)} 类，预计 {_size(estimate)}。\n"
            + "\n".join(f"{r.title}：{r.description}" for r in chosen)
            + (
                "\n先备份到其他卷并校验，再清理原文件；可在隔离页恢复。"
                if recoverable
                else "\n将永久删除所选缓存，不能撤销。"
            )
            + "运行中的应用、占用或复核失败的文件会跳过。继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for rule in self._registry.all():
            if rule.rule_id not in selected or not rule.requires_confirmation:
                continue
            phrase, accepted = QInputDialog.getText(
                self,
                f"专项确认：{rule.title}",
                f"{rule.description}\n建议：{rule.recommended_action}\n请输入：{rule.confirmation_phrase}",
            )
            if not accepted or phrase.strip() != rule.confirmation_phrase:
                QMessageBox.information(self, "已取消", "专项确认不匹配，未开始清理。")
                return
        plan = CleanupPlanner(self._registry).build(
            finding for finding in self._snapshot.findings if finding.rule_id in selected
        )
        self.clean_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self._token = CancellationToken()
        token = self._token
        executor = (
            QuarantineExecutor(
                QuarantineStore(self._vault_root), self._policy, self._registry, token=token
            )
            if recoverable and self._vault_root is not None
            else DirectFileDeleteExecutor(
                self._policy, elevated_checker=is_process_elevated, registry=self._registry
            )
        )
        service = CleanupCoordinator(executor, free_space_reader=free_bytes)
        self.quick_status.setText("正在清理……")
        self._run(
            lambda: service.execute(
                plan,
                volume=self._folders.system_drive,
                dry_run=False,
                token=token,
            ),
            self._clean_done,
        )

    def _clean_done(self, receipt: object) -> None:
        if not isinstance(receipt, CleanupReceipt):
            return
        observed = getattr(receipt, "observed_freed_bytes", 0)
        processed = getattr(receipt, "processed_bytes", 0)
        with suppress(OSError):
            append_history(receipt)
        state = "（用户已取消，剩余项目未处理）" if receipt.cancelled else ""
        self.quick_status.setText(
            f"尝试 {_size(receipt.attempted_bytes)}，成功处理 {_size(processed)}，"
            f"跳过/失败 {_size(receipt.skipped_bytes)}，实际可用空间增加 {_size(observed)}{state}"
        )
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._snapshot = None
        self.clean_button.setEnabled(False)
        self.cleanup_details.setPlainText(
            (failure_summary(receipt) or "所尝试项目均已处理。")
            + f"\n未尝试 {_size(receipt.unattempted_bytes)}。重试请重新扫描，重新选择并确认。"
        )
        self._refresh_disk()
        self._refresh_history()

    def _start_analysis(self) -> None:
        if self._busy:
            return
        self._token = CancellationToken()
        self.analysis_button.setEnabled(False)
        self.analysis_cancel.setEnabled(True)
        self.analysis_output.setText("正在分析系统盘……")
        self._progress = (0, 0)
        token = self._token
        threshold = int(self.large_file_threshold.currentData())
        self._run(
            lambda: StorageAnalyzer(
                top_n=1000,
                large_file_threshold=threshold,
            ).analyze(self._folders.system_drive, token=token, progress=self._analysis_progress),
            self._analysis_done,
        )

    def _analysis_done(self, value: object) -> None:
        if not isinstance(value, StorageSnapshot):
            return
        self.storage_browser.show_snapshot(value)
        self.analysis_output.setText(
            "分析已取消（保留部分结果）" if value.cancelled else "分析完成"
        )
        self.analysis_button.setEnabled(True)
        self.analysis_cancel.setEnabled(False)

    def _inspect_advanced(self) -> None:
        self._run(
            lambda: WindowsAdvancedInspector().inspect(self._folders), self._advanced_inspected
        )

    def _advanced_inspected(self, findings: Any) -> None:
        if not findings:
            self.advanced_output.setPlainText("未发现可报告的休眠、分页或虚拟磁盘占用。")
            return
        self.advanced_output.setPlainText(
            "\n".join(
                f"{_size(item.size_bytes):>10}  {item.category}\n"
                f"{item.path}\n建议：{item.guidance}\n影响：{item.impact}\n"
                f"需要管理员：{'是' if item.requires_admin else '否'}；"
                f"可逆：{'是' if item.reversible else '否'}\n"
                for item in findings
            )
        )

    def _inspect_recycle_bin(self) -> None:
        self._run(
            lambda: RecycleBinExecutor().query(self._folders.system_drive),
            self._recycle_bin_inspected,
        )

    def _recycle_bin_inspected(self, value: object) -> None:
        item_count = int(getattr(value, "item_count", 0))
        size_bytes = int(getattr(value, "size_bytes", 0))
        self.advanced_output.setPlainText(
            f"系统盘回收站：{item_count} 项，共 {_size(size_bytes)}。\n"
            "回收站可能包含用户仍想恢复的文件，绝不并入一键缓存清理。"
        )

    def _confirm_empty_recycle_bin(self) -> None:
        phrase, accepted = QInputDialog.getText(
            self,
            "独立确认：清空回收站",
            "此操作会永久清空系统盘回收站，文件将不能从回收站恢复。\n请输入：清空回收站",
        )
        if not accepted or phrase.strip() != "清空回收站":
            return

        def empty() -> tuple[int, int]:
            before = free_bytes(self._folders.system_drive)
            RecycleBinExecutor().empty(
                self._folders.system_drive,
                confirmation=RecycleBinExecutor.CONFIRMATION,
            )
            return before, free_bytes(self._folders.system_drive)

        self._run(empty, self._recycle_bin_emptied)

    def _recycle_bin_emptied(self, value: object) -> None:
        before, after = value if isinstance(value, tuple) else (0, 0)
        self.advanced_output.setPlainText(
            f"回收站已清空；观测可用空间增加 {_size(max(0, after - before))}。"
        )
        self._refresh_disk()

    def _ensure_elevated(self) -> bool:
        if is_process_elevated():
            return True
        answer = QMessageBox.question(
            self,
            "需要管理员权限",
            "此 Windows 官方操作需要管理员权限。是否现在弹出系统授权窗口并重新启动程序？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        if relaunch_elevated():
            QApplication.quit()
        else:
            QMessageBox.critical(
                self,
                "提权失败",
                "无法启动管理员进程，请右键程序并选择以管理员身份运行。",
            )
        return False

    def _confirm_disable_hibernation(self) -> None:
        answer = QMessageBox.warning(
            self,
            "关闭 Windows 休眠",
            "关闭休眠可释放 hiberfil.sys 占用的空间，但会禁用休眠，并可能关闭快速启动。"
            "这不是普通缓存清理。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run_advanced(
                AdvancedAction.DISABLE_HIBERNATION,
                confirmation="DISABLE HIBERNATION",
            )

    def _run_advanced(self, action: AdvancedAction, *, confirmation: str = "") -> None:
        if (
            action
            in {
                AdvancedAction.ANALYZE_COMPONENT_STORE,
                AdvancedAction.CLEAN_COMPONENT_STORE,
                AdvancedAction.DISABLE_HIBERNATION,
                AdvancedAction.ENABLE_HIBERNATION,
                AdvancedAction.LIST_SHADOWS,
            }
            and not self._ensure_elevated()
        ):
            return
        self.advanced_output.setPlainText("正在调用 Windows 官方工具……")
        self._run(
            lambda: WindowsAdvancedExecutor().execute(action, confirmation=confirmation),
            self._advanced_done,
        )

    def _advanced_done(self, value: object) -> None:
        code = getattr(value, "return_code", -1)
        output = "\n".join(
            filter(None, (getattr(value, "stdout", ""), getattr(value, "stderr", "")))
        )
        status = "操作成功" if code == 0 else ("完成，需要重启" if code == 3010 else "操作失败")
        self.advanced_output.setPlainText(f"{status}（退出码 {code}）\n{output}")
        self._refresh_disk()

    def _confirm_component_cleanup(self) -> None:
        phrase, accepted = QInputDialog.getText(
            self,
            "Windows 组件存储清理",
            "由 DISM 清理被取代的组件，可能耗时较长。"
            "执行中请勿关闭程序。不会使用 ResetBase。\n请输入：清理组件存储",
        )
        if accepted and phrase == "清理组件存储":
            self._run_advanced(
                AdvancedAction.CLEAN_COMPONENT_STORE, confirmation="CLEAN COMPONENT STORE"
            )

    def _confirm_enable_hibernation(self) -> None:
        answer = QMessageBox.question(self, "恢复休眠", "恢复休眠会重新占用系统盘空间。是否继续？")
        if answer == QMessageBox.StandardButton.Yes:
            self._run_advanced(AdvancedAction.ENABLE_HIBERNATION, confirmation="ENABLE HIBERNATION")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for button in self.findChildren(QPushButton):
            if button not in (
                self.cancel_button,
                self.analysis_cancel,
                self.duplicate_cancel,
                self.recovery_cancel,
            ):
                button.setEnabled(not busy)
        self.quick_table.setEnabled(not busy)
        self.cleanup_mode.setEnabled(not busy)
        self.clean_button.setEnabled(not busy and self._snapshot is not None)

    def _worker_finished(self, _value: object) -> None:
        self._set_busy(False)
        self.cancel_button.setEnabled(False)
        self.analysis_cancel.setEnabled(False)
        self.duplicate_cancel.setEnabled(False)
        self.recovery_cancel.setEnabled(False)

    def _analysis_progress(self, count: int, size: int) -> None:
        self._progress = (count, size)

    def _show_progress(self) -> None:
        if self._busy and self.analysis_cancel.isEnabled():
            count, size = self._progress
            self.analysis_output.setText(f"已分析 {count:,} 个文件，{_size(size)}……")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            self._cancel()
            QMessageBox.information(self, "任务正在结束", "已请求取消，请等待当前操作结束后关闭。")
            event.ignore()
        else:
            event.accept()

    def _refresh_history(self) -> None:
        entries = load_history()
        self.history_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            finished = (
                datetime.fromisoformat(entry.finished_at).astimezone().strftime("%Y-%m-%d %H:%M")
            )
            result = f"成功 {entry.succeeded}，跳过/失败 {entry.skipped_or_failed}"
            if entry.quarantined:
                result += f"（备份后清理 {entry.quarantined}）"
            if entry.cancelled:
                result += "（已取消）"
            values = (
                finished,
                _size(entry.estimated_bytes),
                _size(entry.processed_bytes),
                _size(entry.observed_freed_bytes),
                result,
            )
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setToolTip(entry.failure_details)
                self.history_table.setItem(row, column, cell)

    def _cancel(self) -> None:
        if self._token is not None:
            self._token.cancel()

    def _failed(self, message: str) -> None:
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.analysis_button.setEnabled(True)
        self.analysis_cancel.setEnabled(False)
        QMessageBox.critical(self, "操作失败", message)

    def _export_diagnostics(self) -> None:
        destination, _ = QFileDialog.getSaveFileName(
            self, "保存诊断包", "CDriveCleaner-diagnostics.zip", "ZIP 文件 (*.zip)"
        )
        if not destination:
            return
        try:
            export_diagnostics(Path(destination))
            QMessageBox.information(self, "导出完成", "诊断包不包含用户名或文件路径。")
        except OSError as error:
            QMessageBox.critical(self, "导出失败", str(error))


def run_gui(*, smoke_test: bool = False) -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("C Drive Cleaner")
    window = MainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(200, app.quit)
    return int(app.exec())
