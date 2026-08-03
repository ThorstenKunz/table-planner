"""Application logging configuration with Docker-friendly ANSI colors."""

from __future__ import annotations

import copy
import logging
import os
import sys
from typing import TextIO

_RESET = "\x1b[0m"
_LOGGER_COLOR = "\x1b[35m"
_LEVEL_COLORS = {
    logging.DEBUG: "\x1b[36m",
    logging.INFO: "\x1b[34m",
    logging.WARNING: "\x1b[33m",
    logging.ERROR: "\x1b[31m",
    logging.CRITICAL: "\x1b[1;31m",
}
_LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColorFormatter(logging.Formatter):
    """Color level names and logger names without mutating shared records."""

    def __init__(self, use_color: bool) -> None:
        super().__init__(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_color:
            return super().format(record)

        colored_record = copy.copy(record)
        level_color = _LEVEL_COLORS.get(record.levelno, "")
        if level_color:
            colored_record.levelname = f"{level_color}{record.levelname}{_RESET}"
        colored_record.name = f"{_LOGGER_COLOR}{record.name}{_RESET}"
        return super().format(colored_record)


def _colors_enabled(mode: str, stream: TextIO) -> bool:
    normalized = mode.strip().lower()
    if normalized in {"never", "no", "false", "0", "off"}:
        return False
    if normalized == "auto":
        return bool(getattr(stream, "isatty", lambda: False)())
    return True


def configure_logging() -> None:
    """Configure the single application handler used by app and Discord logs.

    LOG_COLOR defaults to ``always`` so colors survive ``docker logs``. Set it
    to ``never`` for collectors that should receive plain text, or ``auto`` to
    color only interactive terminals.
    """
    stream = sys.stderr
    color_mode = os.getenv("LOG_COLOR", "always")
    handler = logging.StreamHandler(stream)
    handler.setFormatter(ColorFormatter(use_color=_colors_enabled(color_mode, stream)))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
