"""
Phase 1: Data Ingestion
=======================
Downloads OHLCV data for each ticker in ``CFG.tickers`` via the unified
``data_provider`` (Finnhub primary, with dividend-adjusted prices) and
concatenates them into a single ``data/combined.csv``.
"""

from __future__ import annotations

import pandas as pd

from src.config import CFG
from src.data_provider import fetch_ohlcv, write_status
from src.utils import ensure_dir, get_logger, save_csv

log = get_logger("ingest")


def fetch_ticker(ticker: str) -> pd.DataFrame:
    """Download dividend-adjusted OHLCV history for *ticker*."""
    end = CFG.end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
    log.info("Fetching %s (%s -> %s)", ticker, CFG.start_date, end)
    df = fetch_ohlcv(ticker, CFG.start_date, end)
    if df.empty:
        log.warning("No data returned for %s — skipping.", ticker)
    return df


def fetch_market_data() -> pd.DataFrame:
    """Download VIX, SPY, and sector ETFs as market regime indicators."""
    end = CFG.end_date or pd.Timestamp.today().strftime("%Y-%m-%d")
    symbols = [("^VIX", "vix"), ("SPY", "spy")]
    for etf in CFG.sector_etfs:
        symbols.append((etf, etf.lower()))

    frames = []
    for symbol, name in symbols:
        log.info("Fetching market data: %s (%s -> %s)", symbol, CFG.start_date, end)
        df = fetch_ohlcv(symbol, CFG.start_date, end)
        if df.empty:
            log.warning("No market data for %s.", symbol)
            continue
        df = df[["date", "close"]].rename(columns={"close": f"{name}_close"})
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    result = frames[0]
    for f in frames[1:]:
        result = result.merge(f, on="date", how="outer")
    return result


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

    market = fetch_market_data()
    if not market.empty:
        market_path = CFG.data_dir / "market.csv"
        save_csv(market, market_path, index=False)
        log.info("Saved %d market rows to %s", len(market), market_path)

    sentiment_path = CFG.data_dir / "sentiment.csv"
    if sentiment_path.exists():
        log.info("Sentiment file exists: %s", sentiment_path)
    else:
        log.info("No sentiment.csv found — sentiment features will be neutral.")

    write_status()
