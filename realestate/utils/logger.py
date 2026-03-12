"""
Centralised logger for the UAE Real Estate Monitor Bot.
Outputs structured JSON to stderr and rotating log file.
"""

import json
import logging
import logging.handlers
import sys
from pathlib import Path

from config import LOG_DIR

_logger_cache: dict[str, logging.Logger] = {}


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "ts":      self.formatTime(record, self.datefmt),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            log_obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def get_logger(name: str = "realestate_bot") -> logging.Logger:
    """Return (or create) a named logger with JSON + rotating file handlers."""
    if name in _logger_cache:
        return _logger_cache[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    fmt = _JsonFormatter()

    # ── stderr handler (INFO+) ──────────────────────────────────────
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # ── rotating file handler (DEBUG+) ──────────────────────────────
    log_file = LOG_DIR / "bot.log"
    fh = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    _logger_cache[name] = logger
    return logger
