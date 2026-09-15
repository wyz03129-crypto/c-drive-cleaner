"""Graphical application entry point."""

from __future__ import annotations


def main() -> int:
    from cdrive_cleaner.ui.main_window import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
