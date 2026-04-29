"""
Data Provider — unified data layer for OHLCV, fundamentals, news, earnings.

Routes most fetches to Finnhub (primary). Two narrow exceptions stay on
yfinance: analyst events (price target + upgrade/downgrade timeline) and
short interest — endpoints not on the current Finnhub tier.

Public functions are the only sanctioned data-access surface. Pipeline
modules (ingest, signals, features) MUST NOT call requests/yfinance directly.

Behaviour:
  - Rate-limited to 50 Finnhub calls / 60 s (paid tier headroom under 60/min).
  - Disk-cached responses in data/finnhub_cache/ keyed per endpoint+symbol.
  - On any Finnhub failure (HTTP error, timeout, malformed body): logs,
    sends one Telegram alert per (endpoint, symbol) per hour, falls back to
    last cached payload. Never raises out of the public fetchers.
  - Per-call status persisted to data/datasource_status.json for the
    /api/portfolio/datasource endpoint.
  - Finnhub /stock/candle returns split-adjusted but not dividend-adjusted
    prices. fetch_ohlcv applies a backward multiplicative adjustment using
    /stock/dividend2 so output matches yfinance(auto_adjust=True).
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

from src.config import CFG
from src.utils import ensure_dir, get_logger

log = get_logger("data_provider")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FINNHUB_BASE = "https://finnhub.io/api/v1"
FINNHUB_RATE_LIMIT_PER_MIN = 50      # paid tier; conservative cap below 60
FINNHUB_TIMEOUT_S = 20
ALERT_THROTTLE_SECONDS = 3600        # one Telegram alert per (endpoint,symbol) per hour

CACHE_DIR = CFG.data_dir / "finnhub_cache"
STATUS_PATH = CFG.data_dir / "datasource_status.json"

# Map Finnhub symbol -> yfinance symbol (only when they differ).
# Finnhub accepts ^VIX, BRK-B, and standard ETF tickers natively, so empty.
SYMBOL_MAP: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# SEC concept mappings (financials-reported -> yfinance line items)
# ---------------------------------------------------------------------------

SEC_REVENUE_CONCEPTS = [
    "us-gaap_Revenues",
    "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap_RevenueFromContractWithCustomerIncludingAssessedTax",
    "us-gaap_SalesRevenueNet",
    "us-gaap_SalesRevenueGoodsNet",
]
SEC_NET_INCOME = ["us-gaap_NetIncomeLoss", "us-gaap_ProfitLoss"]
SEC_OPERATING_INCOME = ["us-gaap_OperatingIncomeLoss"]
SEC_GROSS_PROFIT = ["us-gaap_GrossProfit"]
SEC_EQUITY = [
    "us-gaap_StockholdersEquity",
    "us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
SEC_TOTAL_ASSETS = ["us-gaap_Assets"]
SEC_CASH = [
    "us-gaap_CashAndCashEquivalentsAtCarryingValue",
    "us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "us-gaap_Cash",
]
SEC_CURRENT_ASSETS = ["us-gaap_AssetsCurrent"]
SEC_CURRENT_LIAB = ["us-gaap_LiabilitiesCurrent"]
SEC_OP_CASHFLOW = ["us-gaap_NetCashProvidedByUsedInOperatingActivities"]
SEC_CAPEX = ["us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"]
SEC_DEBT_COMPONENTS = [
    "us-gaap_LongTermDebtCurrent",
    "us-gaap_LongTermDebtNoncurrent",
    "us-gaap_CommercialPaper",
    "us-gaap_ShortTermBorrowings",
    "us-gaap_DebtCurrent",
]
# Single-field aggregates (used as fallback when component sum is empty).
# Order matters: most-specific first.
SEC_DEBT_AGGREGATES = [
    "us-gaap_LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
    "us-gaap_LongTermDebtAndCapitalLeaseObligations",
    "us-gaap_DebtAndCapitalLeaseObligations",
]
# Substring patterns for company-specific debt tags (e.g. tsla_LongTermDebtAndFinanceLeases*).
# Matched independent of namespace prefix; current+noncurrent are summed.
SEC_DEBT_PATTERNS = [
    "LongTermDebtAndFinanceLeasesCurrent",
    "LongTermDebtAndFinanceLeasesNoncurrent",
]


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

@dataclass
class _SourceStatus:
    last_success: Optional[str] = None       # ISO timestamp UTC
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
    success_count: int = 0
    error_count: int = 0


_STATUS_LOCK = Lock()
_STATUS: Dict[str, _SourceStatus] = {
    "finnhub": _SourceStatus(),
    "yfinance": _SourceStatus(),
}
_LAST_ALERT_AT: Dict[str, float] = {}    # (endpoint,symbol) -> unix ts


def _record_success(provider: str) -> None:
    with _STATUS_LOCK:
        s = _STATUS[provider]
        s.last_success = datetime.now(timezone.utc).isoformat()
        s.success_count += 1


def _record_error(provider: str, msg: str) -> None:
    with _STATUS_LOCK:
        s = _STATUS[provider]
        s.last_error = msg[:300]
        s.last_error_at = datetime.now(timezone.utc).isoformat()
        s.error_count += 1


def get_status() -> Dict[str, Any]:
    """Return current per-provider status snapshot."""
    with _STATUS_LOCK:
        return {
            "finnhub": _STATUS["finnhub"].__dict__.copy(),
            "yfinance": _STATUS["yfinance"].__dict__.copy(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "routing": {
                "ohlcv": "finnhub",
                "quarterly_financials": "finnhub",
                "company_news": "finnhub",
                "earnings_calendar": "finnhub",
                "recommendation_trends": "finnhub",
                "analyst_events": "yfinance",
                "short_interest": "yfinance",
            },
        }


def write_status() -> None:
    """Persist status to disk so the API container can read it."""
    try:
        ensure_dir(CFG.data_dir)
        with open(STATUS_PATH, "w") as fh:
            json.dump(get_status(), fh, indent=2)
    except Exception as exc:
        log.warning("Could not write datasource_status.json: %s", exc)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_CALL_TIMES: deque = deque()
_RATE_LOCK = Lock()


def _throttle() -> None:
    """Block until under FINNHUB_RATE_LIMIT_PER_MIN calls in the last 60s."""
    with _RATE_LOCK:
        now = time.monotonic()
        # Drop entries older than 60s
        while _CALL_TIMES and now - _CALL_TIMES[0] > 60:
            _CALL_TIMES.popleft()
        if len(_CALL_TIMES) >= FINNHUB_RATE_LIMIT_PER_MIN:
            sleep_for = 60 - (now - _CALL_TIMES[0]) + 0.1
            log.info("Rate limit reached — sleeping %.1fs", sleep_for)
            time.sleep(max(0.0, sleep_for))
        _CALL_TIMES.append(time.monotonic())


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path(key: str) -> Path:
    safe = key.replace("/", "_").replace(":", "_").replace("?", "_").replace("&", "_").replace("=", "_")
    return CACHE_DIR / f"{safe}.json"


def _cache_write(key: str, payload: Any) -> None:
    try:
        ensure_dir(CACHE_DIR)
        with open(_cache_path(key), "w") as fh:
            json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "data": payload}, fh)
    except Exception as exc:
        log.warning("Cache write failed for %s: %s", key, exc)


def _cache_read(key: str) -> Optional[Any]:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        with open(p) as fh:
            return json.load(fh).get("data")
    except Exception as exc:
        log.warning("Cache read failed for %s: %s", key, exc)
        return None


# ---------------------------------------------------------------------------
# Telegram alert (throttled)
# ---------------------------------------------------------------------------

def _alert(endpoint: str, symbol: str, msg: str) -> None:
    key = f"{endpoint}:{symbol}"
    now = time.time()
    last = _LAST_ALERT_AT.get(key, 0.0)
    if now - last < ALERT_THROTTLE_SECONDS:
        return
    _LAST_ALERT_AT[key] = now
    try:
        from src.notifications import notify_error
        notify_error("data_provider", f"{endpoint}({symbol}): {msg[:200]}")
    except Exception as exc:
        log.warning("Could not send Telegram alert: %s", exc)


# ---------------------------------------------------------------------------
# Finnhub HTTP wrapper
# ---------------------------------------------------------------------------

def _api_key() -> str:
    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FINNHUB_API_KEY missing in environment")
    return key


def _finnhub_get(endpoint: str, params: Dict[str, Any], cache_key: str) -> Optional[Any]:
    """
    Fetch endpoint with rate limiting, status tracking, caching, and fallback.
    Returns parsed JSON on success or last-cached payload on failure.
    Returns None only when no cache exists for a hard failure.
    """
    _throttle()
    full_params = {**params, "token": _api_key()}
    try:
        r = requests.get(f"{FINNHUB_BASE}{endpoint}", params=full_params, timeout=FINNHUB_TIMEOUT_S)
        if r.status_code != 200:
            raise requests.HTTPError(f"{r.status_code}: {(r.text or '')[:200]}")
        data = r.json()
    except Exception as exc:
        msg = str(exc)
        log.error("Finnhub %s failed: %s", endpoint, msg)
        _record_error("finnhub", f"{endpoint}: {msg}")
        _alert(endpoint, params.get("symbol", "-"), msg)
        cached = _cache_read(cache_key)
        if cached is not None:
            log.warning("Falling back to cached payload for %s", cache_key)
            return cached
        return None

    _record_success("finnhub")
    _cache_write(cache_key, data)
    return data


# ---------------------------------------------------------------------------
# OHLCV — with dividend back-adjustment
# ---------------------------------------------------------------------------

def _to_unix(date_str: str) -> int:
    return int(pd.Timestamp(date_str).timestamp())


def _fetch_dividends(symbol: str, start: str, end: str) -> List[Dict[str, Any]]:
    """Return list of {exDate, amount} dicts within [start, end]."""
    cache_key = f"dividend2_{symbol}"
    payload = _finnhub_get(
        "/stock/dividend2",
        {"symbol": symbol, "from": start, "to": end},
        cache_key,
    )
    if not payload:
        return []
    return payload.get("data", []) or []


def _apply_dividend_adjustment(df: pd.DataFrame, dividends: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Apply yfinance auto_adjust=True equivalent backward multiplicative
    adjustment using dividend records.

    For each ex-dividend date d with amount D and prior close P_d:
        factor = (P_d - D) / P_d
        all rows with date < d: open/high/low/close *= factor

    Process from most recent dividend backward so each prior_close already
    reflects all later dividend factors.
    """
    if df.empty or not dividends:
        return df

    df = df.sort_values("date").reset_index(drop=True).copy()
    valid = []
    for d in dividends:
        ex = d.get("exDate")
        amt = d.get("amount")
        if ex is None or amt is None:
            continue
        try:
            ex_ts = pd.Timestamp(ex).normalize()
            amt_f = float(amt)
        except Exception:
            continue
        if amt_f <= 0:
            continue
        valid.append((ex_ts, amt_f))

    valid.sort(key=lambda x: x[0], reverse=True)  # most recent first

    for ex_ts, amt in valid:
        mask = df["date"] < ex_ts
        if not mask.any():
            continue
        prior_close = float(df.loc[mask, "close"].iloc[-1])
        if prior_close <= 0:
            continue
        factor = (prior_close - amt) / prior_close
        if factor <= 0 or factor >= 1.5:    # sanity guard
            continue
        df.loc[mask, ["open", "high", "low", "close"]] *= factor

    return df


def fetch_ohlcv(symbol: str, start: str, end: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV for *symbol* between *start* and *end* (inclusive of
    start, exclusive of end — same convention as yfinance).

    Returns a DataFrame with columns: date, open, high, low, close, volume,
    ticker. Empty DataFrame if no data is available even from cache.

    Prices are split-adjusted by Finnhub by default and dividend-adjusted
    here, matching yfinance(auto_adjust=True).
    """
    fh_symbol = SYMBOL_MAP.get(symbol, symbol)
    cache_key = f"candle_{fh_symbol}_{start}_{end}"
    payload = _finnhub_get(
        "/stock/candle",
        {
            "symbol": fh_symbol,
            "resolution": "D",
            "from": _to_unix(start),
            "to": _to_unix(end),
        },
        cache_key,
    )
    if not payload or payload.get("s") != "ok":
        log.warning("No candle data for %s [%s -> %s]", symbol, start, end)
        return pd.DataFrame()

    df = pd.DataFrame({
        "date": pd.to_datetime(payload["t"], unit="s").normalize(),
        "open": payload["o"],
        "high": payload["h"],
        "low": payload["l"],
        "close": payload["c"],
        "volume": payload["v"],
    })
    df["ticker"] = symbol

    # Skip dividend adjustment for VIX (no dividends)
    if symbol != "^VIX":
        divs = _fetch_dividends(fh_symbol, start, end)
        df = _apply_dividend_adjustment(df, divs)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Quarterly fundamentals
# ---------------------------------------------------------------------------

def _find_concept(entries: List[Dict[str, Any]], candidates: List[str]) -> Optional[float]:
    """First non-null match from candidates in entries. Returns float or None."""
    for cand in candidates:
        for entry in entries:
            if entry.get("concept") == cand:
                v = entry.get("value")
                if v is None:
                    continue
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
    return None


def _compute_total_debt(bs: List[Dict[str, Any]]) -> Optional[float]:
    """Resolve total debt across the wide variation in SEC debt reporting.

    Strategy:
      1. Sum standard us-gaap component concepts (most companies).
      2. Single-field aggregates (XOM, BRK-B style) — use directly; if the
         aggregate is the JPM-style "IncludingCurrentMaturities" variant,
         add ShortTermBorrowings/DebtCurrent on top.
      3. Pattern-match company-specific debt tags (TSLA's tsla_LongTermDebt*),
         summing current + noncurrent variants.
    """
    parts = [_find_concept(bs, [c]) for c in SEC_DEBT_COMPONENTS]
    parts = [p for p in parts if p is not None]
    if parts:
        return sum(parts)

    for cand in SEC_DEBT_AGGREGATES:
        agg = _find_concept(bs, [cand])
        if agg is None:
            continue
        if cand.endswith("IncludingCurrentMaturities"):
            short = _find_concept(bs, ["us-gaap_ShortTermBorrowings", "us-gaap_DebtCurrent"]) or 0.0
            return agg + short
        return agg

    matched: List[float] = []
    for entry in bs:
        concept = entry.get("concept", "")
        if any(pat in concept for pat in SEC_DEBT_PATTERNS):
            v = entry.get("value")
            if v is None:
                continue
            try:
                matched.append(float(v))
            except (TypeError, ValueError):
                continue
    if matched:
        return sum(matched)

    return None


def fetch_quarterly_financials(ticker: str) -> pd.DataFrame:
    """
    Fetch quarterly financials and return a DataFrame matching the schema
    of the legacy yfinance _fetch_quarterly_fundamentals output:
        date, f_profit_margin, f_gross_margin,
        f_revenue_growth_qoq, f_revenue_growth_yoy,
        f_debt_to_equity, f_roe,
        f_cash_to_debt, f_debt_to_assets, f_fcf_margin
    """
    cache_key = f"financials_{ticker}"
    payload = _finnhub_get(
        "/stock/financials-reported",
        {"symbol": ticker, "freq": "quarterly"},
        cache_key,
    )
    if not payload:
        return pd.DataFrame()

    reports = payload.get("data", []) or []
    if not reports:
        return pd.DataFrame()

    # Sort ascending by endDate so QoQ/YoY indexing matches the legacy code
    def _end(r: Dict[str, Any]) -> pd.Timestamp:
        return pd.Timestamp(r.get("endDate")).normalize()

    reports = sorted(reports, key=_end)

    records: List[Dict[str, Any]] = []
    for i, rpt in enumerate(reports):
        rep = rpt.get("report", {}) or {}
        ic = rep.get("ic", []) or []
        bs = rep.get("bs", []) or []
        cf = rep.get("cf", []) or []

        revenue = _find_concept(ic, SEC_REVENUE_CONCEPTS)
        net_income = _find_concept(ic, SEC_NET_INCOME)
        gross_profit = _find_concept(ic, SEC_GROSS_PROFIT)

        row: Dict[str, Any] = {"date": _end(rpt)}
        row["f_profit_margin"] = (net_income / revenue) if (revenue and net_income is not None) else np.nan
        row["f_gross_margin"] = (gross_profit / revenue) if (revenue and gross_profit is not None) else np.nan

        if i > 0 and revenue is not None:
            prev_ic = (reports[i - 1].get("report", {}) or {}).get("ic", []) or []
            prev_rev = _find_concept(prev_ic, SEC_REVENUE_CONCEPTS)
            row["f_revenue_growth_qoq"] = (revenue / prev_rev - 1) if prev_rev else np.nan
        else:
            row["f_revenue_growth_qoq"] = np.nan

        if i >= 4 and revenue is not None:
            yoy_ic = (reports[i - 4].get("report", {}) or {}).get("ic", []) or []
            yoy_rev = _find_concept(yoy_ic, SEC_REVENUE_CONCEPTS)
            row["f_revenue_growth_yoy"] = (revenue / yoy_rev - 1) if yoy_rev else np.nan
        else:
            row["f_revenue_growth_yoy"] = np.nan

        debt = _compute_total_debt(bs)
        equity = _find_concept(bs, SEC_EQUITY)
        assets = _find_concept(bs, SEC_TOTAL_ASSETS)
        cash = _find_concept(bs, SEC_CASH)

        row["f_debt_to_equity"] = (debt / equity) if (equity and debt is not None) else np.nan
        row["f_roe"] = (net_income / equity) if (equity and net_income is not None) else np.nan
        row["f_cash_to_debt"] = (cash / debt) if (debt and cash is not None) else np.nan
        row["f_debt_to_assets"] = (debt / assets) if (assets and debt is not None) else np.nan

        op_cf = _find_concept(cf, SEC_OP_CASHFLOW)
        capex = _find_concept(cf, SEC_CAPEX)
        # SEC reports capex as a positive payment; legacy yfinance code stored
        # it as negative. FCF = op_cf - capex preserves the same sign result.
        if op_cf is not None and capex is not None and revenue:
            row["f_fcf_margin"] = (op_cf - capex) / revenue
        else:
            row["f_fcf_margin"] = np.nan

        records.append(row)

    if not records:
        return pd.DataFrame()

    fund_df = pd.DataFrame(records)
    fund_df["date"] = pd.to_datetime(fund_df["date"]).dt.tz_localize(None)
    return fund_df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# News, earnings, recommendation trends (used by P3/P4/P6)
# ---------------------------------------------------------------------------

def fetch_company_news(ticker: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
    cache_key = f"news_{ticker}_{from_date}_{to_date}"
    payload = _finnhub_get(
        "/company-news",
        {"symbol": ticker, "from": from_date, "to": to_date},
        cache_key,
    )
    return payload or []


def fetch_earnings_calendar(
    ticker: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {}
    if ticker:
        params["symbol"] = ticker
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    cache_key = f"earnings_{ticker or 'all'}_{from_date or '-'}_{to_date or '-'}"
    payload = _finnhub_get("/calendar/earnings", params, cache_key)
    if not payload:
        return []
    return payload.get("earningsCalendar", []) or []


def fetch_recommendation_trends(ticker: str) -> List[Dict[str, Any]]:
    cache_key = f"recommendation_{ticker}"
    payload = _finnhub_get(
        "/stock/recommendation",
        {"symbol": ticker},
        cache_key,
    )
    return payload or []


# ---------------------------------------------------------------------------
# yfinance-backed (analyst events + short interest) — kept here for status
# tracking and central provenance.
# ---------------------------------------------------------------------------

def fetch_analyst_events(ticker: str) -> pd.DataFrame:
    """
    Return analyst upgrades/downgrades with timestamped price targets.
    yfinance fallback — Finnhub's /stock/upgrade-downgrade and
    /stock/price-target are not on the current tier.

    Output columns: date, analyst_target, action_score
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        ud = t.upgrades_downgrades
    except Exception as exc:
        _record_error("yfinance", f"upgrades_downgrades({ticker}): {exc}")
        log.warning("yfinance analyst events failed for %s: %s", ticker, exc)
        return pd.DataFrame()

    if ud is None or ud.empty:
        _record_success("yfinance")
        return pd.DataFrame()

    ud = ud.copy()
    ud.index = pd.to_datetime(ud.index).tz_localize(None)
    ud = ud.reset_index().rename(columns={"GradeDate": "date"})
    ud["analyst_target"] = pd.to_numeric(ud.get("currentPriceTarget"), errors="coerce").fillna(0)
    action_map = {"up": 1, "down": -1, "main": 0, "init": 0, "reit": 0}
    ud["action_score"] = (
        ud["Action"].astype(str).str.lower().map(action_map).fillna(0).astype(int)
    )
    _record_success("yfinance")
    return ud[["date", "analyst_target", "action_score"]].sort_values("date").reset_index(drop=True)


def fetch_short_interest(ticker: str) -> Dict[str, float]:
    """yfinance fallback — no Finnhub equivalent on current tier."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        shares_short = info.get("sharesShort", 0) or 0
        shares_prior = info.get("sharesShortPriorMonth", 0) or 0
        float_shares = info.get("floatShares", 0) or 0
        pct = info.get("shortPercentOfFloat", 0) or 0
        change = (shares_short - shares_prior) / float_shares if float_shares > 0 else 0.0
        _record_success("yfinance")
        return {"short_interest_pct": pct, "short_interest_change": change}
    except Exception as exc:
        _record_error("yfinance", f"short_interest({ticker}): {exc}")
        log.warning("yfinance short interest failed for %s: %s", ticker, exc)
        return {}


# ---------------------------------------------------------------------------
# Diagnostic
# ---------------------------------------------------------------------------

def call_count_in_last_minute() -> int:
    with _RATE_LOCK:
        now = time.monotonic()
        while _CALL_TIMES and now - _CALL_TIMES[0] > 60:
            _CALL_TIMES.popleft()
        return len(_CALL_TIMES)
