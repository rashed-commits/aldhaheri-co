"""
Shared utilities for Trade-Bot.
================================
Reusable helpers consumed by multiple pipeline modules.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a logger that writes to *stdout* with a consistent format.

    Calling this function multiple times with the same *name* always returns
    the same logger (standard Python logging behaviour), so it is safe to call
    at module level.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:          # avoid duplicate handlers on re-import
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: Path) -> Path:
    """Create *path* (and parents) if it does not exist; return *path*."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    """
    Load a CSV from *path* and raise a descriptive ``FileNotFoundError`` if
    the file is missing rather than the default pandas message.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Expected data file not found: {path}\n"
            "Run the preceding pipeline phase first."
        )
    df = pd.read_csv(path, **kwargs)
    return df


def save_csv(df: pd.DataFrame, path: Path, **kwargs) -> None:
    """Save *df* to *path*, creating parent directories as needed."""
    ensure_dir(path.parent)
    df.to_csv(path, **kwargs)


# ---------------------------------------------------------------------------
# DataFrame validation
# ---------------------------------------------------------------------------

def check_required_columns(
    df: pd.DataFrame,
    required: list[str],
    context: str = "",
) -> None:
    """
    Raise ``ValueError`` if any column in *required* is absent from *df*.

    Parameters
    ----------
    df:
        DataFrame to validate.
    required:
        Column names that must be present.
    context:
        Human-readable label included in the error message (e.g. the file
        name or the pipeline phase).
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        prefix = f"[{context}] " if context else ""
        raise ValueError(
            f"{prefix}DataFrame is missing required columns: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )


def drop_na_rows(
    df: pd.DataFrame,
    subset: Optional[list[str]] = None,
    context: str = "",
) -> pd.DataFrame:
    """
    Drop rows with NaN values and log a warning when any are removed.

    Parameters
    ----------
    df:
        Input DataFrame.
    subset:
        Column names to check for NaN (default: all columns).
    context:
        Label for the warning message.

    Returns
    -------
    pd.DataFrame
        DataFrame with NaN rows removed.
    """
    log = get_logger("utils")
    before = len(df)
    df = df.dropna(subset=subset)
    removed = before - len(df)
    if removed:
        prefix = f"[{context}] " if context else ""
        log.warning("%sDropped %d rows containing NaN values.", prefix, removed)
    return df


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_date(date_str: str) -> pd.Timestamp:
    """
    Parse an ISO-8601 date string (``YYYY-MM-DD``) into a ``pd.Timestamp``.

    Raises
    ------
    ValueError
        If *date_str* cannot be parsed.
    """
    try:
        return pd.Timestamp(date_str)
    except Exception as exc:
        raise ValueError(
            f"Cannot parse date string '{date_str}'. "
            "Expected format: YYYY-MM-DD."
        ) from exc


def trading_days_between(start: str, end: str) -> int:
    """
    Return the approximate number of NYSE trading days between two ISO-8601
    date strings (inclusive of *start*, exclusive of *end*).

    Uses ``pd.bdate_range`` which counts Mon–Fri business days.  Public
    holidays are **not** excluded (close enough for sizing purposes).
    """
    return len(pd.bdate_range(start=start, end=end))


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def safe_divide(
    numerator: float,
    denominator: float,
    fallback: float = 0.0,
) -> float:
    """
    Divide *numerator* by *denominator*; return *fallback* on zero-division.
    """
    if denominator == 0:
        return fallback
    return numerator / denominator


def pct_change(old_value: float, new_value: float) -> float:
    """Return the percentage change from *old_value* to *new_value*."""
    return safe_divide(new_value - old_value, abs(old_value), fallback=0.0) * 100
