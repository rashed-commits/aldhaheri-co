"""
Phase 5: Alpaca Paper Trading Execution
=========================================
Reads today's signal file, manages open positions (stop-loss / take-profit
checks), and submits new market orders for BUY signals.

The ML model controls 100% of the portfolio budget.

Design principles
-----------------
* **Idempotent** -- can be re-run on the same day without doubling up.
* **Fail-safe**  -- any order error is logged and skipped; the rest of the
  run continues.
* **Dry-run**    -- pass ``dry_run=True`` to walk through all logic without
  hitting the Alpaca API or writing files.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.config import CFG
from src.execution.alpaca import get_api
from src.notifications import (
    notify_no_trade,
    notify_portfolio_summary,
    notify_position_exit,
    notify_trade,
)
from src.utils import ensure_dir, get_logger

log = get_logger("executor")


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Position = Dict[str, Any]      # one open position record
Signal   = Dict[str, Any]      # one signal record from signals_*.json


# ---------------------------------------------------------------------------
# Signal loading
# ---------------------------------------------------------------------------

def load_signals(run_date: str, signal_dir: Path) -> List[Signal]:
    """Load the signal file for *run_date* from *signal_dir*."""
    path = signal_dir / f"signals_{run_date}.json"
    if not path.exists():
        log.warning("Signal file not found: %s", path)
        return []
    with open(path) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Position persistence
# ---------------------------------------------------------------------------

def load_positions(positions_path: Path) -> List[Position]:
    """Load open positions from *positions_path*."""
    if not positions_path.exists():
        return []
    with open(positions_path) as fh:
        return json.load(fh)


def save_positions(positions: List[Position], positions_path: Path) -> None:
    """Persist *positions* to *positions_path* as JSON."""
    ensure_dir(positions_path.parent)
    with open(positions_path, "w") as fh:
        json.dump(positions, fh, indent=2)
    log.info("Saved %d open positions to %s", len(positions), positions_path)


# ---------------------------------------------------------------------------
# Inception tracking (for overall P&L)
# ---------------------------------------------------------------------------

def _inception_path() -> Path:
    return CFG.output_dir / "portfolio_inception.json"


def load_inception_equity() -> Optional[float]:
    """Return the equity recorded on the very first run, or ``None``."""
    p = _inception_path()
    if not p.exists():
        return None
    with open(p) as fh:
        return json.load(fh).get("initial_equity")


def save_inception_equity(equity: float) -> None:
    """Record starting equity on the first live run (never overwrites)."""
    p = _inception_path()
    if p.exists():
        return
    ensure_dir(p.parent)
    with open(p, "w") as fh:
        json.dump(
            {
                "initial_equity": round(equity, 2),
                "inception_date": date.today().isoformat(),
            },
            fh,
            indent=2,
        )
    log.info("Recorded inception equity $%.2f", equity)


# ---------------------------------------------------------------------------
# Alpaca account helpers
# ---------------------------------------------------------------------------

def get_account_equity(api) -> float:
    """Return the current portfolio equity from the Alpaca account."""
    try:
        account = api.get_account()
        return float(account.equity)
    except Exception as exc:
        log.warning("Could not fetch account equity: %s -- using $100 000.", exc)
        return 100_000.0


def get_account_details(api) -> dict:
    """Return equity, last_equity, and cash from the Alpaca account."""
    try:
        account = api.get_account()
        return {
            "equity": float(account.equity),
            "last_equity": float(account.last_equity),
            "cash": float(account.cash),
        }
    except Exception as exc:
        log.warning("Could not fetch account details: %s", exc)
        return {"equity": 100_000.0, "last_equity": 100_000.0, "cash": 100_000.0}


def _alpaca_symbol(ticker: str) -> str:
    """Map yfinance ticker to Alpaca symbol (e.g. BRK-B → BRK.B)."""
    return CFG.alpaca_symbol_map.get(ticker, ticker)


def get_current_price(api, ticker: str) -> Optional[float]:
    """Return the latest trade price for *ticker*, or ``None`` on failure."""
    try:
        trade = api.get_latest_trade(_alpaca_symbol(ticker))
        return float(trade.price)
    except Exception as exc:
        log.warning("Could not fetch price for %s: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Position management
# ---------------------------------------------------------------------------

def check_exit_conditions(
    position: Position,
    current_price: float,
) -> Tuple[bool, str]:
    """Evaluate stop-loss and take-profit rules for *position*."""
    entry = float(position["entry_price"])
    pnl_pct = (current_price - entry) / entry

    if pnl_pct <= -CFG.stop_loss_pct:
        return True, f"stop-loss ({pnl_pct:.2%})"
    if pnl_pct >= CFG.take_profit_pct:
        return True, f"take-profit ({pnl_pct:.2%})"
    return False, ""


def close_position(
    api,
    position: Position,
    reason: str,
    dry_run: bool = False,
) -> bool:
    """Submit a market sell order to close *position*."""
    ticker = position["ticker"]
    qty = int(position["qty"])
    log.info("Closing %s x%d | reason: %s (dry_run=%s)", ticker, qty, reason, dry_run)
    if dry_run:
        return True
    try:
        api.submit_order(
            symbol=_alpaca_symbol(ticker), qty=qty, side="sell",
            type="market", time_in_force="day",
        )
        return True
    except Exception as exc:
        log.error("Failed to close %s: %s", ticker, exc, exc_info=True)
        return False


def manage_open_positions(
    api,
    positions: List[Position],
    dry_run: bool = False,
) -> List[Position]:
    """Check exit conditions on all open positions and close as needed."""
    remaining: List[Position] = []
    for pos in positions:
        ticker = pos["ticker"]
        price = get_current_price(api, ticker)
        if price is None:
            log.warning("Keeping %s: could not fetch current price.", ticker)
            remaining.append(pos)
            continue

        should_exit, reason = check_exit_conditions(pos, price)
        if should_exit:
            closed = close_position(api, pos, reason, dry_run=dry_run)
            if closed:
                notify_position_exit(
                    ticker, int(pos["qty"]),
                    float(pos["entry_price"]), price, reason,
                )
            else:
                remaining.append(pos)   # keep if close failed
        else:
            remaining.append(pos)

    return remaining


def process_sell_signals(
    api,
    signals: List[Signal],
    positions: List[Position],
    dry_run: bool = False,
) -> List[Position]:
    """Close positions that have a SELL signal."""
    remaining: List[Position] = []
    for pos in positions:
        ticker = pos["ticker"]
        has_sell = any(
            s["ticker"] == ticker and s["signal"] == "SELL" for s in signals
        )
        if not has_sell:
            remaining.append(pos)
            continue

        price = get_current_price(api, ticker) if api else float(pos["entry_price"])
        if price is None:
            price = float(pos["entry_price"])

        closed = close_position(api, pos, "SELL signal", dry_run=dry_run)
        if closed:
            notify_position_exit(
                ticker, int(pos["qty"]),
                float(pos["entry_price"]), price, "SELL signal",
            )
        else:
            remaining.append(pos)

    return remaining


# ---------------------------------------------------------------------------
# Order submission
# ---------------------------------------------------------------------------

def already_invested(ticker: str, positions: List[Position]) -> bool:
    """Return ``True`` if *ticker* already has an open position."""
    return any(p["ticker"] == ticker for p in positions)


def compute_order_qty(
    available_cash: float,
    price: float,
    num_signals: int,
    equity: float = 0.0,
) -> int:
    """Split *available_cash* equally across *num_signals*; cap at max_position_size."""
    if price <= 0 or num_signals <= 0:
        return 1
    cash_per_signal = available_cash / num_signals
    # Enforce max position size (default 10% of portfolio)
    if equity > 0:
        max_cash = equity * CFG.max_position_size
        cash_per_signal = min(cash_per_signal, max_cash)
    return max(1, int(cash_per_signal / price))


def submit_buy_order(
    api,
    ticker: str,
    qty: int,
    entry_price: float,
    dry_run: bool = False,
) -> Optional[Position]:
    """Submit a market buy order for *ticker* and return a new position dict."""
    log.info(
        "BUY %s x%d @ ~$%.2f (dry_run=%s)", ticker, qty, entry_price, dry_run
    )
    if dry_run:
        return {
            "ticker": ticker,
            "qty": qty,
            "entry_price": round(entry_price, 4),
            "entry_date": date.today().isoformat(),
        }
    try:
        api.submit_order(
            symbol=_alpaca_symbol(ticker), qty=qty, side="buy",
            type="market", time_in_force="day",
        )
        return {
            "ticker": ticker,
            "qty": qty,
            "entry_price": round(entry_price, 4),
            "entry_date": date.today().isoformat(),
        }
    except Exception as exc:
        log.error("Failed to buy %s: %s", ticker, exc, exc_info=True)
        return None


def process_buy_signals(
    api,
    signals: List[Signal],
    positions: List[Position],
    equity: float,
    dry_run: bool = False,
) -> List[Position]:
    """Process BUY signals — 100% of portfolio is ML budget."""
    updated = list(positions)

    existing_value = 0.0
    for pos in updated:
        price = (
            get_current_price(api, pos["ticker"])
            if api else float(pos["entry_price"])
        )
        if price:
            existing_value += int(pos["qty"]) * price

    available_cash = max(0.0, equity - existing_value)
    log.info(
        "Budget=$%.0f  existing=$%.0f  available=$%.0f",
        equity, existing_value, available_cash,
    )

    eligible: List[Signal] = []
    for sig in signals:
        if sig["signal"] != "BUY":
            continue
        ticker = sig["ticker"]
        if already_invested(ticker, updated):
            log.info("Skipping %s: already holding.", ticker)
            continue
        if api is not None and api.has_pending_order(ticker):
            log.info("Skipping %s: pending order exists.", ticker)
            continue
        if len(updated) >= CFG.max_open_positions:
            log.info("Max positions (%d) reached.", CFG.max_open_positions)
            break
        eligible.append(sig)

    if not eligible or available_cash < 10:
        log.info("No eligible BUY signals or insufficient cash ($%.2f).", available_cash)
        return updated

    log.info(
        "Splitting $%.0f across %d eligible signals.", available_cash, len(eligible),
    )
    for sig in eligible:
        ticker = sig["ticker"]
        price = sig.get("close") if api is None else get_current_price(api, ticker)
        if price is None:
            continue

        qty = compute_order_qty(available_cash, price, len(eligible), equity=equity)
        new_pos = submit_buy_order(api, ticker, qty, price, dry_run=dry_run)
        if new_pos:
            updated.append(new_pos)
            notify_trade("BUY", ticker, qty, price)

    return updated


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

def build_portfolio_summary(
    api,
    equity: float,
    positions: List[Position],
    dry_run: bool = False,
) -> dict:
    """Collect data for the end-of-run Telegram summary."""
    if api is not None and not dry_run:
        details = get_account_details(api)
    else:
        details = {"equity": equity, "last_equity": equity, "cash": equity}

    current_equity = details["equity"]
    last_equity = details["last_equity"]
    cash = details["cash"]

    daily_pnl = current_equity - last_equity
    daily_pct = (daily_pnl / last_equity * 100) if last_equity else 0.0

    initial_equity = load_inception_equity()
    if initial_equity:
        overall_pnl = current_equity - initial_equity
        overall_pct = overall_pnl / initial_equity * 100
    else:
        overall_pnl = 0.0
        overall_pct = 0.0

    pos_details = []
    for pos in positions:
        ticker = pos["ticker"]
        price = get_current_price(api, ticker) if api else float(pos["entry_price"])
        entry = float(pos["entry_price"])
        qty = int(pos["qty"])
        mkt_val = qty * price if price else qty * entry
        pnl_pct = ((price - entry) / entry * 100) if price and entry else 0.0
        pos_details.append({
            "ticker": ticker,
            "qty": qty,
            "entry_price": entry,
            "current_price": price or entry,
            "market_value": mkt_val,
            "pnl_pct": pnl_pct,
        })

    return {
        "equity": current_equity,
        "cash": cash,
        "daily_pnl": daily_pnl,
        "daily_pct": daily_pct,
        "overall_pnl": overall_pnl,
        "overall_pct": overall_pct,
        "positions": pos_details,
    }


# ---------------------------------------------------------------------------
# Drawdown circuit breaker
# ---------------------------------------------------------------------------

_DRAWDOWN_HALT_FILE = "drawdown_halt.json"
_DRAWDOWN_THRESHOLD = 0.08   # 8% drawdown from peak triggers halt
_HALT_DAYS = 5               # pause new buys for 5 trading days


def _load_peak_equity() -> dict:
    """Load peak equity tracker from disk."""
    path = CFG.output_dir / _DRAWDOWN_HALT_FILE
    if not path.exists():
        return {"peak_equity": 0.0, "halt_until": None}
    with open(path) as fh:
        return json.load(fh)


def _save_peak_equity(data: dict) -> None:
    """Persist peak equity tracker."""
    path = CFG.output_dir / _DRAWDOWN_HALT_FILE
    ensure_dir(path.parent)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)


def check_drawdown_halt(equity: float, run_date: str) -> bool:
    """
    Check if new buys should be halted due to drawdown.

    Updates peak equity if current equity is a new high.
    Returns True if buying should be paused.
    """
    data = _load_peak_equity()
    peak = data.get("peak_equity", 0.0)
    halt_until = data.get("halt_until")

    # Check if we're still in a halt period
    if halt_until and run_date <= halt_until:
        log.warning(
            "DRAWDOWN HALT active until %s (peak=$%.0f, current=$%.0f). "
            "No new buys.",
            halt_until, peak, equity,
        )
        return True

    # Update peak
    if equity > peak:
        peak = equity

    # Check drawdown
    if peak > 0:
        drawdown = (peak - equity) / peak
        if drawdown >= _DRAWDOWN_THRESHOLD:
            # Calculate halt end date (5 trading days ≈ 7 calendar days)
            from datetime import timedelta
            halt_end = (
                date.fromisoformat(run_date) + timedelta(days=7)
            ).isoformat()
            data["peak_equity"] = peak
            data["halt_until"] = halt_end
            _save_peak_equity(data)
            log.warning(
                "DRAWDOWN CIRCUIT BREAKER triggered: %.1f%% drawdown "
                "(peak=$%.0f, current=$%.0f). Halting new buys until %s.",
                drawdown * 100, peak, equity, halt_end,
            )
            from src.notifications import _send_message
            _send_message(
                f"\U0001f6a8 *Drawdown Circuit Breaker*\n"
                f"Drawdown: {drawdown:.1%} (peak ${peak:,.0f} → ${equity:,.0f})\n"
                f"New buys halted until {halt_end}"
            )
            return True

    # No halt — save updated peak
    data["peak_equity"] = peak
    data["halt_until"] = None
    _save_peak_equity(data)
    return False


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> None:
    """
    Entry point called by ``main.py --phase 5 [--dry-run]``.

    Workflow
    --------
    1. Load today's signals.
    2. Connect to Alpaca, get equity.
    3. Check drawdown circuit breaker.
    4. Load positions from disk.
    5. Manage existing positions (stop-loss / take-profit).
    6. Process SELL signals.
    7. Process BUY signals (if not halted by circuit breaker).
    8. Persist positions to disk.
    9. Send portfolio summary to Telegram.
    """
    run_date = date.today().isoformat()
    log.info("=== Phase 5: Execution  date=%s  dry_run=%s ===", run_date, dry_run)

    # 1. Signals
    signals = load_signals(run_date, CFG.output_dir)
    if not signals:
        log.warning("No signals for %s -- nothing to execute.", run_date)
        notify_no_trade(f"no signal file for {run_date}")
        return
    log.info("Loaded %d signals.", len(signals))

    # 2. Alpaca connection
    if dry_run:
        api = None
        equity = 100_000.0
        log.info("Dry-run: using simulated equity $%.2f.", equity)
    else:
        api = get_api()
        equity = get_account_equity(api)
        log.info("Account equity: $%.2f", equity)
        save_inception_equity(equity)

    # 3. Drawdown circuit breaker
    halt_buys = check_drawdown_halt(equity, run_date) if not dry_run else False

    # 4. Positions
    positions_path = CFG.output_dir / "open_positions.json"
    positions = load_positions(positions_path)
    log.info("Loaded %d positions.", len(positions))

    # 5. Stop-loss / take-profit (always runs, even during halt)
    if positions:
        positions = manage_open_positions(api, positions, dry_run=dry_run)
        log.info("%d positions remain after exit checks.", len(positions))

    # 6. SELL signals (always runs, even during halt)
    positions = process_sell_signals(api, signals, positions, dry_run=dry_run)
    log.info("%d positions remain after SELL signals.", len(positions))

    # 7. BUY signals (skipped if circuit breaker is active)
    if halt_buys:
        log.info("Skipping BUY signals — drawdown circuit breaker active.")
    else:
        positions = process_buy_signals(
            api, signals, positions, equity, dry_run=dry_run,
        )

    # 8. Persist
    if dry_run:
        log.info("Dry-run: skipping positions file write.")
    else:
        save_positions(positions, positions_path)

    # 9. Portfolio summary
    summary = build_portfolio_summary(api, equity, positions, dry_run=dry_run)
    notify_portfolio_summary(summary)

    log.info("Phase 5 complete.  Positions: %d.", len(positions))
