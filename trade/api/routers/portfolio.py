"""
Portfolio API routes — serves trading data to the dashboard.

Data sources:
  - output/open_positions.json        — current positions
  - output/signals_YYYY-MM-DD.json    — daily signals (glob)
  - output/portfolio_inception.json   — initial equity
  - model/saved/metrics.json          — model performance
  - model/saved/feature_importance.json — feature importances
  - Alpaca API (optional)             — live account data
"""

import glob
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends

from routers.auth import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

# ---------------------------------------------------------------------------
# Path helpers — volumes are mounted at /app/output and /app/model/saved
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/app/model/saved"))


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file, returning None on failure."""
    try:
        with open(path) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Alpaca helpers (optional — graceful fallback if unavailable)
# ---------------------------------------------------------------------------

def _get_alpaca_client():
    """Try to create an Alpaca client from env vars. Returns None on failure."""
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    if not api_key or not secret_key:
        return None
    try:
        from alpaca.trading.client import TradingClient
        paper = "paper" in base_url
        return TradingClient(api_key, secret_key, paper=paper)
    except Exception:
        return None


def _get_alpaca_account_details() -> Optional[Dict]:
    """Fetch live account details from Alpaca. Returns None on failure."""
    client = _get_alpaca_client()
    if client is None:
        return None
    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "last_equity": float(account.last_equity),
            "cash": float(account.cash),
        }
    except Exception:
        return None


def _get_alpaca_positions() -> Optional[List[Dict]]:
    """Fetch live positions from Alpaca. Returns None on failure."""
    client = _get_alpaca_client()
    if client is None:
        return None
    try:
        positions = client.get_all_positions()
        return [
            {
                "ticker": p.symbol,
                "qty": int(p.qty),
                "entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "entry_date": None,  # Alpaca doesn't return entry date directly
            }
            for p in positions
        ]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary")
def portfolio_summary():
    """Current portfolio value, total P&L, daily P&L, number of positions."""
    # Try Alpaca first
    account = _get_alpaca_account_details()
    if account:
        equity = account["equity"]
        last_equity = account["last_equity"]
        cash = account["cash"]
        daily_pnl = equity - last_equity
        daily_pct = (daily_pnl / last_equity * 100) if last_equity else 0.0
    else:
        equity = 100_000.0
        cash = 100_000.0
        daily_pnl = 0.0
        daily_pct = 0.0

    # Total P&L from inception
    inception = _read_json(OUTPUT_DIR / "portfolio_inception.json")
    if inception and "initial_equity" in inception:
        initial_equity = inception["initial_equity"]
        total_pnl = equity - initial_equity
        total_pct = (total_pnl / initial_equity * 100) if initial_equity else 0.0
    else:
        initial_equity = equity
        total_pnl = 0.0
        total_pct = 0.0

    # Position count
    alpaca_positions = _get_alpaca_positions()
    if alpaca_positions is not None:
        num_positions = len(alpaca_positions)
    else:
        positions_data = _read_json(OUTPUT_DIR / "open_positions.json")
        num_positions = len(positions_data) if positions_data else 0

    return {
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "initial_equity": round(initial_equity, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pct": round(total_pct, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_pct": round(daily_pct, 2),
        "num_positions": num_positions,
    }


@router.get("/positions")
def portfolio_positions():
    """Open positions with current price, unrealized P&L, entry date."""
    # Try Alpaca first
    alpaca_positions = _get_alpaca_positions()
    if alpaca_positions is not None:
        # Merge entry_date from local file if available
        local = _read_json(OUTPUT_DIR / "open_positions.json") or []
        local_map = {p["ticker"]: p for p in local}
        for pos in alpaca_positions:
            local_pos = local_map.get(pos["ticker"], {})
            pos["entry_date"] = local_pos.get("entry_date")
        return {"positions": alpaca_positions}

    # Fallback to local file
    positions = _read_json(OUTPUT_DIR / "open_positions.json") or []
    result = []
    for pos in positions:
        entry_price = float(pos.get("entry_price", 0))
        current_price = entry_price  # no live price available
        qty = int(pos.get("qty", 0))
        unrealized_pl = (current_price - entry_price) * qty
        result.append({
            "ticker": pos.get("ticker", ""),
            "qty": qty,
            "entry_price": entry_price,
            "current_price": current_price,
            "market_value": current_price * qty,
            "unrealized_pl": unrealized_pl,
            "unrealized_plpc": 0.0,
            "entry_date": pos.get("entry_date"),
        })
    return {"positions": result}


@router.get("/signals")
def portfolio_signals():
    """Recent signals (last 30 days)."""
    signals = []
    today = date.today()
    pattern = str(OUTPUT_DIR / "signals_*.json")
    files = sorted(glob.glob(pattern), reverse=True)

    cutoff = today - timedelta(days=30)
    for fpath in files:
        # Extract date from filename: signals_YYYY-MM-DD.json
        fname = Path(fpath).stem  # signals_YYYY-MM-DD
        try:
            date_str = fname.replace("signals_", "")
            file_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        if file_date < cutoff:
            break
        data = _read_json(Path(fpath))
        if data:
            signals.append({"date": date_str, "signals": data})

    return {"signals": signals}


@router.get("/signals/latest")
def portfolio_signals_latest():
    """Today's signals (or most recent available)."""
    pattern = str(OUTPUT_DIR / "signals_*.json")
    files = sorted(glob.glob(pattern), reverse=True)
    if not files:
        return {"date": None, "signals": []}

    latest_file = files[0]
    fname = Path(latest_file).stem
    date_str = fname.replace("signals_", "")
    data = _read_json(Path(latest_file)) or []
    return {"date": date_str, "signals": data}


@router.get("/performance")
def portfolio_performance():
    """Model metrics — accuracy, ROC-AUC, F1."""
    metrics = _read_json(MODEL_DIR / "metrics.json")
    if metrics is None:
        return {"metrics": None, "message": "No model metrics available."}
    return {"metrics": metrics}


@router.get("/features")
def portfolio_features():
    """Top feature importances from the trained model."""
    data = _read_json(MODEL_DIR / "feature_importance.json")
    if data is None:
        return {"features": None, "message": "No feature importance data available."}
    # Return top 15 features sorted by importance
    if isinstance(data, list):
        features = sorted(data, key=lambda x: x.get("importance", 0), reverse=True)[:15]
    elif isinstance(data, dict):
        features = sorted(
            [{"feature": k, "importance": v} for k, v in data.items()],
            key=lambda x: x["importance"],
            reverse=True,
        )[:15]
    else:
        features = []
    return {"features": features}


@router.get("/history")
def portfolio_history():
    """Portfolio equity history over time from Alpaca REST API."""
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    if not api_key or not secret_key:
        return {"history": [], "message": "Alpaca credentials not configured."}
    try:
        import requests as req

        url = f"{base_url}/v2/account/portfolio/history?period=3M&timeframe=1D"
        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
        resp = req.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        result = []
        for ts, eq in zip(data.get("timestamp", []), data.get("equity", [])):
            if eq and float(eq) > 0:
                date_str = datetime.fromtimestamp(ts, tz=None).strftime("%Y-%m-%d")
                result.append({"date": date_str, "equity": round(float(eq), 2)})

        return {"history": result}
    except Exception as e:
        return {"history": [], "message": f"Failed to fetch history: {str(e)}"}
