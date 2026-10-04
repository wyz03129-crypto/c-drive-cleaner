"""Create and close the real Qt window without entering the event loop."""

from __future__ import annotations

import argparse
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QTabWidget

from cdrive_cleaner.analysis import FastScanner, StorageAnalyzer
from cdrive_cleaner.ui import main_window
from cdrive_cleaner.windows import KnownFolders, discover_known_folders


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previews", type=Path)
    args = parser.parse_args()
    confined = Path(__file__).resolve().parents[1] / "tests/.tmp"
    confined.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=confined) as directory:
        root = Path(directory)
        main_window.discover_known_folders = lambda: KnownFolders(  # type: ignore[attr-defined]
            root / "Windows",
            root / "User",
            root / "Local",
            root / "Roaming",
            root / "ProgramData",
        )
        app = QApplication([])
        if args.previews is not None and os.name == "nt":
            # The offscreen Qt backend does not discover Windows fallback fonts.
            fonts = discover_known_folders().windows / "Fonts"
            for name in ("msyh.ttc", "msyhbd.ttc"):
                QFontDatabase.addApplicationFont(str(fonts / name))
            app.setFont(QFont("Microsoft YaHei", 9))
        with patch("cdrive_cleaner.ui.main_window.load_history", return_value=()):
            window = main_window.MainWindow()
        assert window.windowTitle() == "C Drive Cleaner"
        assert window.centralWidget() is not None
        if args.previews is not None:
            args.previews.mkdir(parents=True, exist_ok=True)
            for name in ("资料/视频示例.mp4", "软件/安装镜像.iso", "Local/Temp/旧缓存.tmp"):
                item = root / name
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(b"fixture" * 1024)
                old = time.time() - 8 * 86400
                os.utime(item, (old, old))
            window._scan_done(FastScanner(window._registry).scan())
            window._analysis_done(StorageAnalyzer(top_n=1000).analyze(root))
            window.show()
            tabs = window.centralWidget()
            assert isinstance(tabs, QTabWidget)
            for index, name in (
                (1, "quick-clean"),
                (2, "analysis"),
                (4, "advanced"),
                (6, "recovery"),
            ):
                tabs.setCurrentIndex(index)
                app.processEvents()
                assert window.grab().save(str(args.previews / f"{name}.png"))
        window.close()
        app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
