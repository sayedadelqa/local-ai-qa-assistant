"""Rotating file logging. Message contents are never logged, only sizes/status."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.config import data_dir


def setup_logging() -> Path:
    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "assistant.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        if getattr(h, "_qa_assistant", False):
            root.removeHandler(h)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    fh._qa_assistant = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    if sys.stderr is not None:  # pythonw.exe has no stderr
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        sh._qa_assistant = True  # type: ignore[attr-defined]
        root.addHandler(sh)
    return log_file
