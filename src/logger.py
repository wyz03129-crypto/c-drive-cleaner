"""Privacy-conscious per-run file logging."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from . import __version__
from .utils import is_admin, system_description


def create_run_logger(log_dir: Path, operation: str, *, dry_run: bool) -> logging.Logger:
    """Create a new UTF-8 log for a scan or cleanup run."""

    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = log_dir / f"{operation}_{stamp}.log"
    logger = logging.getLogger(f"c_drive_safe_cleaner.{operation}.{stamp}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    logger.info("version=%s", __version__)
    logger.info("windows=%s", system_description())
    logger.info("mode=%s", "DRY RUN" if dry_run else operation.upper())
    logger.info("administrator=%s", is_admin())
    return logger
