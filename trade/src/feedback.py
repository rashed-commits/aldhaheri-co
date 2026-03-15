"""
Prediction Feedback Loop
=========================
Evaluates past signal predictions against actual 5-day forward returns.
Called at the end of Phase 4 to track model accuracy over time.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import yfinance as yf

from src.config import CFG
from src.utils import get_logger

log = get_logger("feedback")


def _get_signal_file(signal_date: str) -> Optional[Path]:
    """Return the signal file path for *signal_date*, or None."""
    path = CFG.output_dir / f"signals_{signal_date}.json"
    return path if path.exists() else None


def _get_actual_return(ticker: str, signal_date: str, horizon: int = 5) -> Optional[float]:
    """
    Compute the actual forward return for *ticker* over *horizon* trading days
    starting from *signal_date*.
    """
    try:
        start = signal_date
        # Fetch extra days to account for weekends/holidays
        end_dt = date.fromisoformat(signal_date) + timedelta(days=horizon + 10)
        df = yf.download(
            ticker, start=start, end=end_dt.isoformat(),
            progress=False, auto_adjust=True,
        )
        if df.empty or len(df) < horizon + 1:
            return None
        close_start = float(df["Close"].iloc[0])
        close_end = float(df["Close"].iloc[horizon])
        if close_start <= 0:
            return None
        return (close_end - close_start) / close_start
    except Exception:
        return None


def evaluate_predictions(
    horizon: int = CFG.target_horizon,
) -> Optional[Dict[str, Any]]:
    """
    Look back *horizon* + buffer trading days, find the signal file from that
    date, and compare predictions to actual returns.

    Returns a dict with accuracy stats, or None if no evaluable signals exist.
    """
    # Look for signal files from ~7-10 calendar days ago (5 trading days + weekends)
    today = date.today()
    evaluable_date = None
    signal_path = None

    for days_back in range(horizon + 2, horizon + 12):
        check_date = (today - timedelta(days=days_back)).isoformat()
        path = _get_signal_file(check_date)
        if path is not None:
            evaluable_date = check_date
            signal_path = path
            break

    if signal_path is None or evaluable_date is None:
        log.info("No signal file found for evaluation (checked %d-%d days back).",
                 horizon + 2, horizon + 11)
        return None

    with open(signal_path) as fh:
        signals = json.load(fh)

    if not signals:
        return None

    log.info("Evaluating signals from %s (%d signals).", evaluable_date, len(signals))

    total = 0
    correct = 0
    details = []

    for sig in signals:
        ticker = sig["ticker"]
        predicted_signal = sig["signal"]
        prob_up = sig["prob_up"]

        actual_return = _get_actual_return(ticker, evaluable_date, horizon)
        if actual_return is None:
            log.warning("Could not fetch actual return for %s on %s.", ticker, evaluable_date)
            continue

        total += 1
        # BUY correct if return > 0, SELL correct if return < 0, HOLD always "correct"
        if predicted_signal == "BUY":
            was_correct = actual_return > 0
        elif predicted_signal == "SELL":
            was_correct = actual_return < 0
        else:
            was_correct = True  # HOLD is neutral

        if was_correct:
            correct += 1

        details.append({
            "ticker": ticker,
            "signal": predicted_signal,
            "prob_up": prob_up,
            "actual_return": round(actual_return * 100, 2),
            "correct": was_correct,
        })

        log.info(
            "  %s  signal=%s  prob=%.4f  actual=%.2f%%  %s",
            ticker, predicted_signal, prob_up,
            actual_return * 100,
            "CORRECT" if was_correct else "WRONG",
        )

    if total == 0:
        return None

    accuracy = correct / total

    # Save feedback history
    _save_feedback_record(evaluable_date, total, correct, accuracy, details)

    log.info("Feedback: %d/%d correct (%.1f%%) for signals from %s.",
             correct, total, accuracy * 100, evaluable_date)

    return {
        "signal_date": evaluable_date,
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "horizon": horizon,
        "details": details,
    }


def _save_feedback_record(
    signal_date: str,
    total: int,
    correct: int,
    accuracy: float,
    details: list,
) -> None:
    """Append feedback to a rolling history file."""
    history_path = CFG.output_dir / "feedback_history.json"

    history = []
    if history_path.exists():
        with open(history_path) as fh:
            try:
                history = json.load(fh)
            except json.JSONDecodeError:
                history = []

    # Don't duplicate entries for the same signal_date
    if any(r["signal_date"] == signal_date for r in history):
        return

    history.append({
        "signal_date": signal_date,
        "evaluated_on": date.today().isoformat(),
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "details": details,
    })

    # Keep last 90 days
    history = history[-90:]

    with open(history_path, "w") as fh:
        json.dump(history, fh, indent=2)
