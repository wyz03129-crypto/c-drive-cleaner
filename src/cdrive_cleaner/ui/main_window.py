"""Consumer-facing Windows GUI for scan, clean, analysis, and advanced guidance."""

from __future__ import annotations

import shutil
import sys
from collections import defaultdict
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
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

from cdrive_cleaner.analysis import CancellationToken, FastScanner, StorageAnalyzer, advise_path
from cdrive_cleaner.analysis.windows_advanced import WindowsAdvancedInspector
from cdrive_cleaner.app import CleanupCoordinator, CleanupPlanner
from cdrive_cleaner.domain import AdvancedAction, CleanupReceipt, ScanSnapshot, StorageSnapshot
from cdrive_cleaner.executors import (
    DirectFileDeleteExecutor,
    RecycleBinExecutor,
    WindowsAdvancedExecutor,
)
from cdrive_cleaner.persistence import append_history, export_diagnostics, load_history
from cdrive_cleaner.rules import build_m2_registry
from cdrive_cleaner.safety import SafetyPolicy
from cdrive_cleaner.safety.defaults import build_default_deny_roots
from cdrive_cleaner.windows import discover_known_folders
from cdrive_cleaner.windows.disk_space import free_bytes
from cdrive_cleaner.windows.elevation import is_process_elevated, relaunch_elevated

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
        self._folders = discover_known_folders()
        self._registry = build_m2_registry(self._folders)
        self._policy = SafetyPolicy(
            (root for rule in self._registry.all() for root in rule.roots),
            build_default_deny_roots(self._folders),
        )
        self.setCentralWidget(self._build_tabs())
        self._refresh_disk()

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()
        tabs.addTab(self._dashboard(), "概览")
        tabs.addTab(self._quick_clean(), "快速清理")
        tabs.addTab(self._analysis(), "空间分析")
        tabs.addTab(self._advanced(), "高级优化")
        tabs.addTab(self._history(), "清理历史")
        return tabs

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
        self.quick_table.setHorizontalHeaderLabels(("选择", "类别", "风险", "预计空间", "说明"))
        self.quick_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.quick_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        layout.addLayout(buttons)
        layout.addWidget(self.quick_status)
        layout.addWidget(self.quick_table)
        page.setLayout(layout)
        return page

    def _analysis(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        buttons = QHBoxLayout()
        self.analysis_button = QPushButton("分析系统盘")
        self.analysis_cancel = QPushButton("取消")
        self.large_file_threshold = QComboBox()
        self.large_file_threshold.addItem("大文件 ≥ 500 MB", 500 * 1024**2)
        self.large_file_threshold.addItem("大文件 ≥ 1 GB", 1024**3)
        self.large_file_threshold.addItem("大文件 ≥ 5 GB", 5 * 1024**3)
        self.analysis_cancel.setEnabled(False)
        self.analysis_button.clicked.connect(self._start_analysis)
        self.analysis_cancel.clicked.connect(self._cancel)
        buttons.addWidget(self.analysis_button)
        buttons.addWidget(self.large_file_threshold)
        buttons.addWidget(self.analysis_cancel)
        self.analysis_output = QTextEdit()
        self.analysis_output.setReadOnly(True)
        layout.addLayout(buttons)
        layout.addWidget(self.analysis_output)
        page.setLayout(layout)
        return page

    def _advanced(self) -> QWidget:
        page, layout = QWidget(), QVBoxLayout()
        note = QLabel(
            "高级操作只调用 Windows 官方工具，不直接删除 WinSxS、休眠文件、分页文件或虚拟磁盘。"
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        inspect_button = QPushButton("检查高级空间占用")
        component_button = QPushButton("分析组件存储")
        hibernation_button = QPushButton("关闭休眠并释放空间")
        settings_button = QPushButton("打开存储设置")
        recycle_button = QPushButton("检查回收站")
        empty_recycle_button = QPushButton("清空回收站")
        inspect_button.clicked.connect(self._inspect_advanced)
        component_button.clicked.connect(
            lambda: self._run_advanced(AdvancedAction.ANALYZE_COMPONENT_STORE)
        )
        hibernation_button.clicked.connect(self._confirm_disable_hibernation)
        settings_button.clicked.connect(
            lambda: self._run_advanced(AdvancedAction.OPEN_STORAGE_SETTINGS)
        )
        recycle_button.clicked.connect(self._inspect_recycle_bin)
        empty_recycle_button.clicked.connect(self._confirm_empty_recycle_bin)
        for button in (
            inspect_button,
            component_button,
            hibernation_button,
            settings_button,
            recycle_button,
            empty_recycle_button,
        ):
            buttons.addWidget(button)
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
        worker = FunctionWorker(operation)
        self._workers.add(worker)
        worker.signals.completed.connect(completed)
        worker.signals.completed.connect(lambda _value, item=worker: self._workers.discard(item))
        worker.signals.failed.connect(self._failed)
        worker.signals.failed.connect(lambda _value, item=worker: self._workers.discard(item))
        self._pool.start(worker)

    def _start_quick_scan(self) -> None:
        self._token = CancellationToken()
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.quick_status.setText("正在扫描安全缓存……")
        self._run(lambda: FastScanner(self._registry).scan(token=self._token), self._scan_done)

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
            choice.setData(Qt.ItemDataRole.UserRole, rule.rule_id)
            self.quick_table.setItem(row, 0, choice)
            self.quick_table.setItem(row, 1, QTableWidgetItem(rule.title))
            self.quick_table.setItem(row, 2, QTableWidgetItem(rule.risk.name))
            self.quick_table.setItem(row, 3, QTableWidgetItem(_size(grouped[rule.rule_id])))
            self.quick_table.setItem(row, 4, QTableWidgetItem(rule.description))
        self.quick_status.setText(
            f"发现 {len(snapshot.findings)} 个文件，预计可清理 {_size(snapshot.estimated_bytes)}"
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
        if self._snapshot is None or not (selected := self._selected_rules()):
            QMessageBox.information(self, "没有选择", "请选择至少一个清理类别。")
            return
        answer = QMessageBox.question(
            self,
            "确认清理",
            "将真实删除所选的可再生缓存。被占用或复核失败的文件会安全跳过。是否继续？",
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
        service = CleanupCoordinator(
            DirectFileDeleteExecutor(self._policy, elevated_checker=is_process_elevated),
            free_space_reader=free_bytes,
        )
        self.clean_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self._token = CancellationToken()
        self.quick_status.setText("正在清理……")
        self._run(
            lambda: service.execute(
                plan,
                volume=self._folders.system_drive,
                dry_run=False,
                token=self._token,
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
        self._refresh_disk()
        self._refresh_history()

    def _start_analysis(self) -> None:
        self._token = CancellationToken()
        self.analysis_button.setEnabled(False)
        self.analysis_cancel.setEnabled(True)
        self.analysis_output.setPlainText("正在分析系统盘……")
        threshold = int(self.large_file_threshold.currentData())
        self._run(
            lambda: StorageAnalyzer(
                top_n=25,
                large_file_threshold=threshold,
            ).analyze(self._folders.system_drive, token=self._token),
            self._analysis_done,
        )

    def _analysis_done(self, value: object) -> None:
        if not isinstance(value, StorageSnapshot):
            return
        lines = [
            f"已统计：{_size(value.total_logical_bytes)}，{value.total_files} 个文件",
            f"目录覆盖率：{value.coverage.directory_ratio:.1%}",
            "",
            "最大目录：",
        ]
        for directory_item in value.top_directories:
            advice = advise_path(
                directory_item.path,
                system_drive=self._folders.system_drive,
                profile=self._folders.profile,
            )
            lines.append(
                f"{_size(directory_item.logical_bytes):>10}  {directory_item.path}\n"
                f"            [{advice.risk.name}] {advice.label}：{advice.action}"
            )
        lines.extend(("", "达到所选阈值的最大文件："))
        for file_item in value.top_files:
            advice = advise_path(
                file_item.path,
                system_drive=self._folders.system_drive,
                profile=self._folders.profile,
            )
            lines.append(
                f"{_size(file_item.logical_bytes):>10}  {file_item.path}\n"
                f"            [{advice.risk.name}] {advice.action}"
            )
        self.analysis_output.setPlainText("\n".join(lines))
        self.analysis_button.setEnabled(True)
        self.analysis_cancel.setEnabled(False)

    def _inspect_advanced(self) -> None:
        findings = WindowsAdvancedInspector().inspect(self._folders)
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
        output = getattr(value, "stdout", "") or getattr(value, "stderr", "")
        self.advanced_output.setPlainText(str(output) or "操作已完成。")

    def _refresh_history(self) -> None:
        entries = load_history()
        self.history_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            finished = (
                datetime.fromisoformat(entry.finished_at).astimezone().strftime("%Y-%m-%d %H:%M")
            )
            result = f"成功 {entry.succeeded}，跳过/失败 {entry.skipped_or_failed}"
            values = (
                finished,
                _size(entry.estimated_bytes),
                _size(entry.processed_bytes),
                _size(entry.observed_freed_bytes),
                result,
            )
            for column, text in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(text))

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


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("C Drive Cleaner")
    window = MainWindow()
    window.show()
    return int(app.exec())
