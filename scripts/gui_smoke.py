"""Create and close the real Qt window without entering the event loop."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from cdrive_cleaner.ui import main_window
from cdrive_cleaner.windows import KnownFolders


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        if os.name != "nt":
            root = Path(directory)
            main_window.discover_known_folders = lambda: KnownFolders(  # type: ignore[attr-defined]
                root / "Windows",
                root / "User",
                root / "Local",
                root / "Roaming",
                root / "ProgramData",
            )
        app = QApplication([])
        window = main_window.MainWindow()
        assert window.windowTitle() == "C Drive Cleaner"
        assert window.centralWidget() is not None
        window.close()
        app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
