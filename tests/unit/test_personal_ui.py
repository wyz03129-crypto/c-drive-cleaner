"""Real Qt widget checks using only confined fixtures and read-only rendering."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from cdrive_cleaner.analysis import StorageAnalyzer
from cdrive_cleaner.ui.storage_browser import StorageBrowser


def test_lazy_tree_and_file_filters(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    nested = tmp_path / "folder/child"
    nested.mkdir(parents=True)
    (nested / "large.iso").write_bytes(b"x" * 10)
    (nested / "other.bin").write_bytes(b"a" * 4)
    snapshot = StorageAnalyzer(top_n=1000).analyze(tmp_path)
    widget = StorageBrowser(tmp_path, tmp_path)
    widget.show_snapshot(snapshot)
    root = widget.tree.topLevelItem(0)
    assert root.childCount() == 1
    folder = root.child(0)
    assert folder.childCount() == 0
    widget._expand(folder)
    assert folder.childCount() == 1
    assert widget.files.rowCount() == 2
    widget.search.setText(".iso")
    assert widget.files.rowCount() == 1
    widget.risk.setCurrentText("SYSTEM")
    assert widget.files.rowCount() == 0
    widget.tree.setCurrentItem(folder)
    assert str(folder.data(0, Qt.ItemDataRole.UserRole)) in widget.details.text()
    widget.close()
    assert app is not None


def test_worker_completion_is_delivered_on_gui_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtCore import QEventLoop, QThread, QTimer
    from PySide6.QtGui import QCloseEvent

    from cdrive_cleaner.analysis import CancellationToken
    from cdrive_cleaner.ui import main_window
    from cdrive_cleaner.windows import KnownFolders

    folders = KnownFolders(*(tmp_path / item for item in ("Win", "User", "Local", "Roam", "Data")))
    monkeypatch.setattr(main_window, "discover_known_folders", lambda: folders)
    monkeypatch.setattr(main_window, "load_history", lambda: ())
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args: None)
    app = QApplication.instance() or QApplication([])
    loop = QEventLoop()
    delivered: list[QThread] = []

    class CheckedWindow(main_window.MainWindow):
        def _scan_done(self, value: object) -> None:
            delivered.append(QThread.currentThread())
            super()._scan_done(value)
            loop.quit()

    window = CheckedWindow()
    token = CancellationToken()
    window._token = token
    window._set_busy(True)
    event = QCloseEvent()
    window.closeEvent(event)
    assert token.cancelled and not event.isAccepted()
    window._set_busy(False)
    window._start_quick_scan()
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    assert delivered == [app.thread()]
    assert not window._busy
    window.close()


def test_window_busy_manual_rows_and_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cdrive_cleaner.analysis import CancellationToken, FastScanner
    from cdrive_cleaner.ui import main_window
    from cdrive_cleaner.windows import KnownFolders

    folders = KnownFolders(
        tmp_path / "Windows",
        tmp_path / "User",
        tmp_path / "Local",
        tmp_path / "Roaming",
        tmp_path / "Data",
    )
    monkeypatch.setattr(main_window, "discover_known_folders", lambda: folders)
    monkeypatch.setattr(main_window, "load_history", lambda: ())
    app = QApplication.instance() or QApplication([])
    window = main_window.MainWindow()
    office = folders.local_app_data / "Microsoft/Office/16.0/OfficeFileCache/pending.bin"
    office.parent.mkdir(parents=True)
    office.write_bytes(b"pending")
    snapshot = FastScanner(window._registry).scan()
    window._scan_done(snapshot)
    assert window.quick_table.rowCount() == 1
    item = window.quick_table.item(0, 0)
    assert not item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert not window._selected_rules()
    token = CancellationToken()
    window._token = token
    window._set_busy(True)
    assert not window.scan_button.isEnabled()
    assert not window.analysis_button.isEnabled()
    window._start_quick_scan()
    assert window._token is token  # Busy task cannot be replaced by a second scan.
    window._cancel()
    assert token.cancelled
    window._worker_finished(None)
    assert window.scan_button.isEnabled()
    window.close()
    assert app is not None
