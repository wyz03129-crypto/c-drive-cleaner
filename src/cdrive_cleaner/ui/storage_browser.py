"""Lazy directory drill-down and a filtered, bounded large-file view."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from cdrive_cleaner.analysis import advise_path
from cdrive_cleaner.domain import DirectoryUsage, StorageSnapshot


def size_text(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(amount) < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return "0 B"


class StorageBrowser(QWidget):
    def __init__(self, profile: Path, system_drive: Path) -> None:
        super().__init__()
        self._profile = profile
        self._drive = system_drive
        self._snapshot: StorageSnapshot | None = None
        self._children: dict[Path, list[DirectoryUsage]] = defaultdict(list)
        layout = QVBoxLayout(self)
        self.summary = QLabel("扫描后可逐层展开目录。大文件列表仅提供分析与建议。")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(("目录", "逻辑大小", "文件数", "风险 / 建议"))
        self.tree.setColumnWidth(0, 300)
        self.tree.itemExpanded.connect(self._expand)
        self.tree.itemSelectionChanged.connect(self._directory_selected)
        layout.addWidget(self.tree, 2)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("筛选大文件：路径、应用目录名或扩展名，如 .iso")
        self.risk = QComboBox()
        self.risk.addItems(("全部风险", "MANUAL", "SYSTEM", "PROTECTED"))
        self.search.textChanged.connect(self._filter)
        self.risk.currentTextChanged.connect(self._filter)
        filters.addWidget(self.search)
        filters.addWidget(self.risk)
        layout.addLayout(filters)
        self.files = QTableWidget(0, 4)
        self.files.setHorizontalHeaderLabels(("大文件路径", "逻辑大小", "风险", "处理建议"))
        self.files.setColumnWidth(0, 400)
        self.files.horizontalHeader().setStretchLastSection(True)
        self.files.currentCellChanged.connect(self._file_selected)
        self.files.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.files, 2)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.details)

    def show_snapshot(self, snapshot: StorageSnapshot) -> None:
        self._snapshot = snapshot
        self._children.clear()
        for entry in snapshot.directories:
            self._children[entry.path.parent].append(entry)
        self.tree.clear()
        root = QTreeWidgetItem(
            [
                str(snapshot.root),
                size_text(snapshot.total_logical_bytes),
                str(snapshot.total_files),
                "仅分析",
            ]
        )
        root.setData(0, Qt.ItemDataRole.UserRole, snapshot.root)
        self.tree.addTopLevelItem(root)
        self._expand(root)
        root.setExpanded(True)
        state = "已取消，以下为部分结果" if snapshot.cancelled else "扫描完成"
        coverage = snapshot.coverage
        self.summary.setText(
            f"{state}：{snapshot.total_files:,} 个文件，{size_text(snapshot.total_logical_bytes)}。"
            f"不可读目录 {coverage.unreadable_directories}，"
            f"不可读条目 {coverage.unreadable_entries}，"
            f"跳过链接 {coverage.skipped_reparse_points}。"
            "逻辑大小不是实际可释放空间；硬链接计入首次遇到的目录。"
        )
        self.summary.setToolTip("\n".join(map(str, snapshot.unreadable_paths)))
        self._filter()

    def _expand(self, item: QTreeWidgetItem) -> None:
        if item.data(0, Qt.ItemDataRole.UserRole + 1):
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        for entry in self._children.get(path, ()):
            advice = advise_path(entry.path, system_drive=self._drive, profile=self._profile)
            child = QTreeWidgetItem(
                [
                    entry.path.name,
                    size_text(entry.logical_bytes),
                    str(entry.file_count),
                    f"{advice.risk.name} · {advice.action}",
                ]
            )
            child.setData(0, Qt.ItemDataRole.UserRole, entry.path)
            child.setToolTip(0, str(entry.path))
            if self._children.get(entry.path):
                child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            item.addChild(child)

    def _directory_selected(self) -> None:
        items = self.tree.selectedItems()
        if items:
            path = items[0].data(0, Qt.ItemDataRole.UserRole)
            advice = advise_path(path, system_drive=self._drive, profile=self._profile)
            self.details.setText(f"{path}\n{advice.label}：{advice.action}")

    def _filter(self) -> None:
        self.files.setRowCount(0)
        if self._snapshot is None:
            return
        query = self.search.text().casefold().strip()
        risk = self.risk.currentText()
        for entry in self._snapshot.top_files:
            advice = advise_path(entry.path, system_drive=self._drive, profile=self._profile)
            if query not in str(entry.path).casefold():
                continue
            if risk != "全部风险" and risk != advice.risk.name:
                continue
            row = self.files.rowCount()
            self.files.insertRow(row)
            for col, value in enumerate(
                (str(entry.path), size_text(entry.logical_bytes), advice.risk.name, advice.action)
            ):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.files.setItem(row, col, cell)
        self.details.setText(
            f"显示 {self.files.rowCount()} / {len(self._snapshot.top_files)} 项；"
            "筛选范围是达到阈值的前 1000 个大文件。目录树不产生删除授权。"
        )

    def _file_selected(
        self, row: int, _column: int, _previous_row: int, _previous_col: int
    ) -> None:
        cell = self.files.item(row, 0)
        if cell is None:
            return
        path = Path(cell.text())
        advice = advise_path(path, system_drive=self._drive, profile=self._profile)
        self.details.setText(f"{path}\n{advice.label}：{advice.action}")
