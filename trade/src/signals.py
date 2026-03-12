"""
Phase 4: Daily Signal Generator
================================
Fetches today's OHLCV bar for each configured ticker, engineers the same
features used during training, loads the persisted model + scaler, and
writes a ranked list of buy / sell / hold signals to
``output/signals_YYYY-MM-DD.json``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd
import yfinance as yf

from src.config import CFG
from src.features import build_features, _fetch_quarterly_fundamentals
from src.notifications import notify_feedback, notify_no_trade, notify_signals
from src.utils import ensure_dir, get_logger

log = get_logger("signals")

_LOOKBACK_DAYS = 120   # calendar days — must exceed indicator warmup (~50 trading days)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_recent(ticker: str, lookback: int = _LOOKBACK_DAYS) -> pd.DataFrame:
    """
    Download the most recent *lookback* calendar days of OHLCV data for
    *ticker* via yfinance.

    Returns
    -------
    pd.DataFrame
        Columns: date, open, high, low, close, volume, ticker.
        Empty DataFrame if no data is returned.
    """
    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=lookback)
    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        log.warning("No recent data for %s.", ticker)
        return pd.DataFrame()
    df = df.reset_index()
    # yfinance may return MultiIndex columns for single tickers — flatten
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [str(c).lower() for c in df.columns]
    df["ticker"] = ticker
    return df


# ---------------------------------------------------------------------------
# Artefact loading
# ---------------------------------------------------------------------------

def load_model_artefacts(
    model_dir: Path,
) -> tuple[Any, Any, List[str]]:
    """
    Load and return the trained model, scaler, and feature name list from
    *model_dir*.

    Raises
    ------
    FileNotFoundError
        If any expected artefact file is missing.
    """
    model_path = model_dir / "model.joblib"
    scaler_path = model_dir / "scaler.joblib"
    features_path = model_dir / "feature_names.json"

    for p in (model_path, scaler_path, features_path):
        if not p.exists():
            raise FileNotFoundError(
                f"Model artefact not found: {p}\n"
                "Run 'python main.py --phase 3' first."
            )

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    with open(features_path) as fh:
        feature_names: List[str] = json.load(fh)

    log.info("Loaded model artefacts from %s", model_dir)
    return model, scaler, feature_names


# ---------------------------------------------------------------------------
# Signal computation
# ---------------------------------------------------------------------------

def fetch_market_recent(lookback: int = _LOOKBACK_DAYS) -> pd.DataFrame:
    """Download recent VIX + SPY data for market regime features."""
    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=lookback)
    frames = []
    for symbol, name in [("^VIX", "vix"), ("SPY", "spy")]:
        df = yf.download(
            symbol,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            continue
        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        df.columns = [str(c).lower() for c in df.columns]
        df = df[["date", "close"]].rename(columns={"close": f"{name}_close"})
        frames.append(df)

    if len(frames) == 2:
        return frames[0].merge(frames[1], on="date", how="outer")
    elif frames:
        return frames[0]
    return pd.DataFrame()


def compute_signal(
    ticker: str,
    model: Any,
    scaler: Any,
    feature_names: List[str],
    market_df: pd.DataFrame | None = None,
) -> Dict[str, Any] | None:
    """
    Fetch recent data, engineer features, and return a signal dict for
    *ticker*, or ``None`` if insufficient data is available.

    The returned dict contains:
    ``ticker``, ``date``, ``close``, ``prob_up``, ``signal``.
    """
    df = fetch_recent(ticker)
    if df.empty or len(df) < 30:
        log.warning("Insufficient data for %s — skipping.", ticker)
        return None

    # Fetch fundamentals for this ticker
    try:
        fund_df = _fetch_quarterly_fundamentals(ticker)
    except Exception:
        fund_df = pd.DataFrame()

    try:
        features_df = build_features(df, market_df=market_df, fund_df=fund_df)
    except Exception as exc:
        log.error("Feature engineering failed for %s: %s", ticker, exc, exc_info=True)
        return None

    if features_df.empty:
        log.warning("Empty features for %s after NaN drop — skipping.", ticker)
        return None

    # Use the most-recent row
    latest = features_df.iloc[-1]
    close_price = float(latest["close"])
    row_date = str(latest["date"])[:10]

    # Align feature vector with training feature names
    missing = [f for f in feature_names if f not in features_df.columns]
    if missing:
        log.error(
            "Ticker %s is missing features: %s — skipping.", ticker, missing
        )
        return None

    x = latest[feature_names].values.reshape(1, -1).astype(float)
    if np.isnan(x).any():
        log.warning("NaN in feature vector for %s — skipping.", ticker)
        return None

    x_scaled = scaler.transform(x)
    prob_up = float(model.predict_proba(x_scaled)[0, 1])

    if prob_up >= CFG.signal_threshold_buy:
        signal = "BUY"
    elif prob_up <= CFG.signal_threshold_sell:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "ticker": ticker,
        "date": row_date,
        "close": round(close_price, 4),
        "prob_up": round(prob_up, 4),
        "signal": signal,
    }


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def rank_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort signals by conviction: BUY signals descending by ``prob_up``,
    then HOLD signals, then SELL signals ascending by ``prob_up``.
    Return only the top ``CFG.top_n_signals`` entries.
    """
    buys = sorted(
        [s for s in signals if s["signal"] == "BUY"],
        key=lambda s: s["prob_up"],
        reverse=True,
    )
    holds = [s for s in signals if s["signal"] == "HOLD"]
    sells = sorted(
        [s for s in signals if s["signal"] == "SELL"],
        key=lambda s: s["prob_up"],
    )
    ranked = buys + holds + sells
    return ranked[: CFG.top_n_signals]


def write_signals(
    signals: List[Dict[str, Any]],
    out_dir: Path,
    run_date: str,
) -> Path:
    """
    Serialise *signals* to ``out_dir/signals_YYYY-MM-DD.json``.

    Returns the path of the written file.
    """
    ensure_dir(out_dir)
    out_path = out_dir / f"signals_{run_date}.json"
    with open(out_path, "w") as fh:
        json.dump(signals, fh, indent=2)
    log.info("Wrote %d signals to %s", len(signals), out_path)
    return out_path


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> None:
    """
    Entry point called by ``main.py --phase 4 [--dry-run]``.

    Parameters
    ----------
    dry_run:
        If ``True``, compute signals but do not write the output JSON file.
    """
    model, scaler, feature_names = load_model_artefacts(CFG.model_dir)
    run_date = date.today().isoformat()

    log.info(
        "Generating signals for %d tickers on %s (dry_run=%s) ...",
        len(CFG.tickers), run_date, dry_run,
    )

    # Fetch market regime data (VIX + SPY) once for all tickers
    log.info("Fetching market regime data (VIX + SPY) ...")
    try:
        market_df = fetch_market_recent()
        log.info("Market data: %d rows.", len(market_df) if not market_df.empty else 0)
    except Exception as exc:
        log.warning("Market data fetch failed (non-fatal): %s", exc)
        market_df = None

    raw_signals: List[Dict[str, Any]] = []
    for ticker in CFG.tickers:
        result = compute_signal(ticker, model, scaler, feature_names, market_df=market_df)
        if result is not None:
            raw_signals.append(result)
            log.info(
                "%s  close=%.2f  prob_up=%.4f  signal=%s",
                ticker, result["close"], result["prob_up"], result["signal"],
            )

    if not raw_signals:
        log.warning("No signals generated.")
        notify_no_trade("no tickers produced a valid signal")
        return

    signals = rank_signals(raw_signals)
    log.info(
        "Top %d signals: %s",
        len(signals),
        [f"{s['ticker']}({s['signal']})" for s in signals],
    )
    notify_signals(signals)

    if dry_run:
        log.info("Dry-run mode: skipping signal file write.")
    else:
        write_signals(signals, CFG.output_dir, run_date)

    # --- Feedback loop: evaluate past predictions ---
    try:
        from src.feedback import evaluate_predictions

        result = evaluate_predictions()
        if result:
            notify_feedback(result)
    except Exception as exc:
        log.warning("Feedback evaluation failed (non-fatal): %s", exc)
