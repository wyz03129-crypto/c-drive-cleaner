"""Create and close the real Qt window without entering the event loop."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from cdrive_cleaner.ui.main_window import MainWindow


def main() -> int:
    app = QApplication([])
    window = MainWindow()
    assert window.windowTitle() == "C Drive Cleaner"
    assert window.centralWidget() is not None
    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
