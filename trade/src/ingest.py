"""
Phase 1: Data Ingestion
=======================
Downloads OHLCV data for each ticker in ``CFG.tickers`` via ``yfinance``
and concatenates them into a single ``data/combined.csv``.
"""

from __future__ import annotations

import pandas as pd
import yfinance as yf

from src.config import CFG
from src.utils import ensure_dir, get_logger, save_csv

log = get_logger("ingest")


def fetch_ticker(ticker: str) -> pd.DataFrame:
    """Download OHLCV history for *ticker* and attach a ``ticker`` column."""
    end = CFG.end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
    log.info("Fetching %s (%s -> %s)", ticker, CFG.start_date, end)
    df = yf.download(
        ticker,
        start=CFG.start_date,
        end=end,
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        log.warning("No data returned for %s — skipping.", ticker)
        return pd.DataFrame()
    df = df.reset_index()
    # yfinance may return MultiIndex columns for single tickers — flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).lower() for c in df.columns]
    df["ticker"] = ticker
    return df


def fetch_market_data() -> pd.DataFrame:
    """Download VIX and SPY as market regime indicators."""
    frames = []
    for symbol, name in [("^VIX", "vix"), ("SPY", "spy")]:
        end = CFG.end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
        log.info("Fetching market data: %s (%s -> %s)", symbol, CFG.start_date, end)
        df = yf.download(
            symbol,
            start=CFG.start_date,
            end=end,
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            log.warning("No market data for %s.", symbol)
            continue
        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df.columns = [str(c).lower() for c in df.columns]
        # Keep only date and close, renamed
        df = df[["date", "close"]].rename(columns={"close": f"{name}_close"})
        frames.append(df)

    if len(frames) == 2:
        return frames[0].merge(frames[1], on="date", how="outer")
    elif frames:
        return frames[0]
    return pd.DataFrame()


def run() -> None:
    """Entry point called by ``main.py --phase 1``."""
    ensure_dir(CFG.data_dir)
    frames = []
    for ticker in CFG.tickers:
        df = fetch_ticker(ticker)
        if not df.empty:
            frames.append(df)

    if not frames:
        raise RuntimeError("No data downloaded — check tickers and date range.")

    combined = pd.concat(frames, ignore_index=True)
    out_path = CFG.data_dir / "combined.csv"
    save_csv(combined, out_path, index=False)
    log.info("Saved %s rows to %s", f"{len(combined):,}", out_path)

    # Download market regime data (VIX + SPY)
    market = fetch_market_data()
    if not market.empty:
        market_path = CFG.data_dir / "market.csv"
        save_csv(market, market_path, index=False)
        log.info("Saved %d market rows to %s", len(market), market_path)
