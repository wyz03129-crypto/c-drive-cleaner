"""Command-line shell for the v2 application."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI without performing filesystem work."""

    parser = argparse.ArgumentParser(
        prog="c-drive-cleaner",
        description="Windows C 盘空间分析与安全清理工具（v2 工程阶段）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("status", help="显示当前工程阶段，不扫描或修改文件")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the M0 CLI. No command in this milestone mutates the filesystem."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        print("C Drive Cleaner v2：M0 工程骨架已就绪，真实扫描和清理尚未启用。")
        return 0
    parser.print_help()
    return 0
