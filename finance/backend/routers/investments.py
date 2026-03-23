import logging
import time
from datetime import datetime, timezone

import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import InvestmentPosition, InvestmentPositionCreate, InvestmentPositionOut
from backend.routers.transactions import verify_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investments", tags=["investments"])

USD_AED_RATE = 3.6725

# In-memory price cache: {ticker: {"data": {...}, "fetched_at": timestamp}}
_price_cache: dict[str, dict] = {}
CACHE_TTL = 300  # 5 minutes

SEED_POSITIONS = [
    {"ticker": "VOO", "shares": 15, "cost_per_share": 617.45, "entry_date": "03/17/2026", "currency": "USD"},
    {"ticker": "VOO", "shares": 28, "cost_per_share": 614.75, "entry_date": "03/18/2026", "currency": "USD"},
    {"ticker": "VOO", "shares": 1, "cost_per_share": 614.53, "entry_date": "03/18/2026", "currency": "USD"},
]


async def seed_positions(db: AsyncSession) -> None:
    """Insert initial positions if the table is empty."""
    result = await db.execute(select(InvestmentPosition.id).limit(1))
    if result.scalar_one_or_none() is not None:
        return
    for s in SEED_POSITIONS:
        db.add(InvestmentPosition(**s))
    await db.commit()
    logger.info("Seeded %d initial investment positions", len(SEED_POSITIONS))


def _parse_date(date_str: str) -> datetime:
    """Parse MM/DD/YYYY to datetime."""
    return datetime.strptime(date_str, "%m/%d/%Y")


def _fetch_ticker_data(ticker: str, start: str) -> dict:
    """Fetch current price and historical data from yfinance (cached 5 min).

    Args:
        ticker: Stock ticker symbol.
        start: Start date in YYYY-MM-DD format.

    Returns:
        Dict with 'current_price' and 'history' (list of {date, close}).
    """
    cache_key = f"{ticker}:{start}"
    now = time.time()

    # Return cached data if fresh
    if cache_key in _price_cache:
        entry = _price_cache[cache_key]
        if now - entry["fetched_at"] < CACHE_TTL:
            logger.info("Cache hit for %s", cache_key)
            return entry["data"]

    t = yf.Ticker(ticker)
    hist = t.history(start=start, interval="1d")

    if hist.empty:
        logger.warning("yfinance returned empty history for %s (start=%s)", ticker, start)
        # Return stale cache if available
        if cache_key in _price_cache:
            logger.info("Returning stale cache for %s", cache_key)
            return _price_cache[cache_key]["data"]
        return {"current_price": 0.0, "history": []}

    history = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(row["Close"], 2)}
        for idx, row in hist.iterrows()
    ]
    current_price = history[-1]["close"] if history else 0.0

    result = {"current_price": current_price, "history": history}

    # Cache the result
    _price_cache[cache_key] = {"data": result, "fetched_at": now}
    logger.info("Fetched and cached %s: %d data points, price=$%.2f", ticker, len(history), current_price)

    return result


@router.get("/positions", response_model=list[InvestmentPositionOut])
async def list_positions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> list[InvestmentPositionOut]:
    result = await db.execute(
        select(InvestmentPosition)
        .where(InvestmentPosition.deleted == False)
        .order_by(InvestmentPosition.entry_date.asc())
    )
    rows = result.scalars().all()
    return [InvestmentPositionOut.model_validate(r) for r in rows]


@router.post("/positions", response_model=InvestmentPositionOut)
async def add_position(
    body: InvestmentPositionCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> InvestmentPositionOut:
    pos = InvestmentPosition(
        ticker=body.ticker.upper(),
        shares=body.shares,
        cost_per_share=body.cost_per_share,
        entry_date=body.entry_date,
        currency=body.currency,
    )
    db.add(pos)
    await db.commit()
    await db.refresh(pos)
    return InvestmentPositionOut.model_validate(pos)


@router.delete("/positions/{pos_id}")
async def delete_position(
    pos_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> dict:
    result = await db.execute(
        select(InvestmentPosition).where(
            InvestmentPosition.id == pos_id,
            InvestmentPosition.deleted == False,
        )
    )
    pos = result.scalar_one_or_none()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    pos.deleted = True
    await db.commit()
    return {"status": "ok", "message": f"Position #{pos_id} deleted"}


@router.get("/portfolio")
async def get_portfolio(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> dict:
    """Full portfolio summary with live prices, P&L, and historical data."""
    result = await db.execute(
        select(InvestmentPosition)
        .where(InvestmentPosition.deleted == False)
        .order_by(InvestmentPosition.entry_date.asc())
    )
    positions = result.scalars().all()

    if not positions:
        return {
            "positions": [],
            "summary": {
                "total_cost_usd": 0, "total_value_usd": 0, "total_pnl_usd": 0,
                "total_pnl_pct": 0, "total_cost_aed": 0, "total_value_aed": 0,
                "total_pnl_aed": 0, "total_shares": 0, "daily_change_pct": 0,
                "daily_change_usd": 0, "usd_aed_rate": USD_AED_RATE,
            },
            "history": [],
        }

    # Group positions by ticker
    tickers: dict[str, list] = {}
    for p in positions:
        tickers.setdefault(p.ticker, []).append(p)

    # Find earliest entry date across all positions
    earliest = min(
        _parse_date(p.entry_date) for p in positions
    ).strftime("%Y-%m-%d")

    # Fetch price data per ticker (cached, with stale fallback)
    ticker_data: dict[str, dict] = {}
    for ticker in tickers:
        try:
            ticker_data[ticker] = _fetch_ticker_data(ticker, earliest)
        except Exception as e:
            logger.error("Failed to fetch data for %s: %s", ticker, e)
            # Try stale cache
            cache_key = f"{ticker}:{earliest}"
            if cache_key in _price_cache:
                logger.info("Using stale cache for %s after error", ticker)
                ticker_data[ticker] = _price_cache[cache_key]["data"]
            else:
                ticker_data[ticker] = {"current_price": 0.0, "history": []}

    # Build per-lot position details
    total_cost_usd = 0.0
    total_value_usd = 0.0
    total_shares = 0.0
    pos_details = []

    for p in positions:
        data = ticker_data.get(p.ticker, {"current_price": 0.0})
        current_price = data["current_price"]
        cost = p.shares * p.cost_per_share
        value = p.shares * current_price
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0

        total_cost_usd += cost
        total_value_usd += value
        total_shares += p.shares

        pos_details.append({
            "id": p.id,
            "ticker": p.ticker,
            "shares": p.shares,
            "cost_per_share": p.cost_per_share,
            "current_price": current_price,
            "entry_date": p.entry_date,
            "cost_usd": round(cost, 2),
            "value_usd": round(value, 2),
            "pnl_usd": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "cost_aed": round(cost * USD_AED_RATE, 2),
            "value_aed": round(value * USD_AED_RATE, 2),
            "pnl_aed": round(pnl * USD_AED_RATE, 2),
        })

    # Total P&L
    total_pnl_usd = total_value_usd - total_cost_usd
    total_pnl_pct = (total_pnl_usd / total_cost_usd * 100) if total_cost_usd else 0

    # Daily change: compare last two data points from the first ticker's history
    daily_change_pct = 0.0
    daily_change_usd = 0.0
    # Use the ticker with the most shares for daily change
    primary_ticker = max(tickers.keys(), key=lambda t: sum(p.shares for p in tickers[t]))
    primary_hist = ticker_data.get(primary_ticker, {}).get("history", [])
    if len(primary_hist) >= 2:
        prev_close = primary_hist[-2]["close"]
        curr_close = primary_hist[-1]["close"]
        if prev_close:
            daily_change_pct = (curr_close - prev_close) / prev_close * 100
            daily_change_usd = (curr_close - prev_close) * total_shares

    # Build portfolio value history (daily total value across all positions)
    # For each date in history, sum up value of positions that existed at that date
    all_dates = set()
    for data in ticker_data.values():
        for point in data["history"]:
            all_dates.add(point["date"])
    sorted_dates = sorted(all_dates)

    # Build price lookup: ticker -> date -> close
    price_lookup: dict[str, dict[str, float]] = {}
    for ticker, data in ticker_data.items():
        price_lookup[ticker] = {p["date"]: p["close"] for p in data["history"]}

    history = []
    for date_str in sorted_dates:
        day_value_usd = 0.0
        day_cost_usd = 0.0
        for p in positions:
            entry_iso = _parse_date(p.entry_date).strftime("%Y-%m-%d")
            if date_str < entry_iso:
                continue
            prices = price_lookup.get(p.ticker, {})
            # Use the price for this date, or find the most recent prior price
            price = prices.get(date_str)
            if price is None:
                prior = [v for d, v in sorted(prices.items()) if d <= date_str]
                price = prior[-1] if prior else p.cost_per_share
            day_value_usd += p.shares * price
            day_cost_usd += p.shares * p.cost_per_share

        history.append({
            "date": date_str,
            "value_usd": round(day_value_usd, 2),
            "value_aed": round(day_value_usd * USD_AED_RATE, 2),
            "cost_usd": round(day_cost_usd, 2),
            "cost_aed": round(day_cost_usd * USD_AED_RATE, 2),
        })

    return {
        "positions": pos_details,
        "summary": {
            "total_cost_usd": round(total_cost_usd, 2),
            "total_value_usd": round(total_value_usd, 2),
            "total_pnl_usd": round(total_pnl_usd, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "total_cost_aed": round(total_cost_usd * USD_AED_RATE, 2),
            "total_value_aed": round(total_value_usd * USD_AED_RATE, 2),
            "total_pnl_aed": round(total_pnl_usd * USD_AED_RATE, 2),
            "total_shares": total_shares,
            "daily_change_pct": round(daily_change_pct, 2),
            "daily_change_usd": round(daily_change_usd, 2),
            "daily_change_aed": round(daily_change_usd * USD_AED_RATE, 2),
            "usd_aed_rate": USD_AED_RATE,
        },
        "history": history,
    }
