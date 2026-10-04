"""Graphical application entry point."""

from __future__ import annotations

import os
import sys


def main() -> int:
    smoke_test = "--smoke-test" in sys.argv[1:]
    if smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from cdrive_cleaner.ui.main_window import run_gui

    return run_gui(smoke_test=smoke_test)


if __name__ == "__main__":
    raise SystemExit(main())
