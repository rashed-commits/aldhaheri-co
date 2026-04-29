"""
Diagnostic probe — checks which Finnhub endpoints are accessible on the
configured FINNHUB_API_KEY tier. Read-only, ~7 calls total.

Run from repo root:
    python trade/scripts/probe_finnhub.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

API_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
if not API_KEY:
    sys.exit("FINNHUB_API_KEY not set in .env")

BASE = "https://finnhub.io/api/v1"
TICKER = "AAPL"
NOW = int(time.time())
ONE_YEAR_AGO = int((datetime.now() - timedelta(days=365)).timestamp())
THREE_YEARS_AGO = int((datetime.now() - timedelta(days=365 * 3)).timestamp())


def probe(label: str, path: str, params: dict) -> None:
    params = {**params, "token": API_KEY}
    try:
        r = requests.get(f"{BASE}{path}", params=params, timeout=15)
    except Exception as exc:
        print(f"[{label}] ERROR: {exc}")
        return

    status = r.status_code
    body_preview = (r.text or "")[:200].replace("\n", " ")
    if status == 200:
        try:
            data = r.json()
            if isinstance(data, dict):
                empty = not data or all(
                    (v in (None, [], {}, 0, "no_data")) for v in data.values()
                )
                summary = f"keys={list(data.keys())[:6]} empty={empty}"
            elif isinstance(data, list):
                summary = f"list_len={len(data)}"
            else:
                summary = f"type={type(data).__name__}"
        except Exception:
            summary = f"non-json: {body_preview}"
        print(f"[{label}] 200 OK   {summary}")
    else:
        print(f"[{label}] {status}     {body_preview}")


def main() -> None:
    print(f"Probing Finnhub with key={API_KEY[:6]}...{API_KEY[-4:]}")
    print(f"Ticker={TICKER}\n")

    probe("quote",                 "/quote",                  {"symbol": TICKER})
    probe("candle (1y daily)",     "/stock/candle",           {"symbol": TICKER, "resolution": "D", "from": ONE_YEAR_AGO, "to": NOW})
    probe("candle (3y daily)",     "/stock/candle",           {"symbol": TICKER, "resolution": "D", "from": THREE_YEARS_AGO, "to": NOW})
    probe("financials-reported",   "/stock/financials-reported", {"symbol": TICKER, "freq": "quarterly"})
    probe("recommendation",        "/stock/recommendation",   {"symbol": TICKER})
    probe("price-target",          "/stock/price-target",     {"symbol": TICKER})
    probe("upgrade-downgrade",     "/stock/upgrade-downgrade",{"symbol": TICKER, "from": "2024-01-01", "to": "2026-04-29"})
    probe("earnings calendar",     "/calendar/earnings",      {"from": "2026-04-29", "to": "2026-06-01", "symbol": TICKER})
    probe("company news",          "/company-news",           {"symbol": TICKER, "from": "2026-04-22", "to": "2026-04-29"})
    probe("metric (basic financials)", "/stock/metric",       {"symbol": TICKER, "metric": "all"})
    probe("insider sentiment",     "/stock/insider-sentiment",{"symbol": TICKER, "from": "2026-01-01", "to": "2026-04-29"})


if __name__ == "__main__":
    main()
