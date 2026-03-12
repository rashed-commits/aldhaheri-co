"""
Generate synthetic OHLCV data for unit / integration testing.

Produces 3 tickers x ~1 350 trading days of GBM (Geometric Brownian
Motion) price data covering 2021-01-04 → 2026-02-25 — enough for
the full pipeline (features + model training + signals) to run without
a live internet connection.

Usage
-----
    python scripts/generate_sample_data.py

Output
------
    data/combined.csv   (created / overwritten)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import CFG
from src.utils import ensure_dir, get_logger, save_csv

log = get_logger("generate_sample_data")

_TICKERS = ["AAPL", "MSFT", "GOOGL"]
_START   = "2021-01-04"
_END     = "2026-02-25"
_SEED    = 42


def _gbm_prices(
    n: int,
    s0: float = 100.0,
    mu: float = 0.0003,
    sigma: float = 0.015,
    rng: np.random.Generator = None,
) -> np.ndarray:
    """
    Simulate *n* daily closing prices using Geometric Brownian Motion.

    Parameters
    ----------
    n     : number of periods
    s0    : initial price
    mu    : daily drift
    sigma : daily volatility
    rng   : numpy random generator (uses global seed if None)
    """
    if rng is None:
        rng = np.random.default_rng(_SEED)
    dt = 1.0
    z  = rng.standard_normal(n)
    log_returns = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z
    prices = s0 * np.exp(np.cumsum(log_returns))
    return prices


def _build_ohlcv(
    ticker: str,
    dates: pd.DatetimeIndex,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Build a realistic OHLCV DataFrame for *ticker* over *dates*."""
    n = len(dates)
    close = _gbm_prices(n, s0=150.0 + rng.uniform(0, 100), rng=rng)
    noise = rng.uniform(0.001, 0.02, size=n)
    high  = close * (1 + noise)
    low   = close * (1 - noise)
    open_ = low + rng.uniform(0, 1, size=n) * (high - low)
    volume = (rng.integers(500_000, 5_000_000, size=n)).astype(float)

    return pd.DataFrame({
        "date":   dates,
        "open":   open_.round(4),
        "high":   high.round(4),
        "low":    low.round(4),
        "close":  close.round(4),
        "volume": volume,
        "ticker": ticker,
    })


def generate() -> pd.DataFrame:
    """Generate combined OHLCV data for all sample tickers and save to disk."""
    dates = pd.bdate_range(start=_START, end=_END)   # business days only
    rng   = np.random.default_rng(_SEED)

    frames = [_build_ohlcv(t, dates, rng) for t in _TICKERS]
    df = pd.concat(frames, ignore_index=True)

    ensure_dir(CFG.data_dir)
    output = CFG.data_dir / "combined.csv"
    save_csv(df, output, index=False)
    log.info(
        "Generated %s: %s rows, %d tickers",
        output, f"{len(df):,}", df["ticker"].nunique(),
    )
    return df


if __name__ == "__main__":
    generate()
