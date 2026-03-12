"""
Alpaca broker integration — credential loading and client factory.

Uses the ``alpaca-py`` SDK (``alpaca.trading`` and ``alpaca.data``).
"""

from __future__ import annotations

import os

from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from src.config import CFG
from src.utils import get_logger

log = get_logger("alpaca")


# ---------------------------------------------------------------------------
# Credential validation
# ---------------------------------------------------------------------------

def _require_env(var: str) -> str:
    """Return the value of environment variable *var*, or raise."""
    value = os.environ.get(var, "")
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{var}' is not set.\n"
            "Set it in your shell or in a .env file and re-run."
        )
    return value


# ---------------------------------------------------------------------------
# Thin wrapper that mimics the interface executor.py expects
# ---------------------------------------------------------------------------

class AlpacaAPI:
    """Adapter around ``alpaca-py`` that exposes the methods used by
    ``executor.py``: ``get_account``, ``get_latest_trade``, and
    ``submit_order``."""

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self._trading = TradingClient(api_key, secret_key, paper=paper)
        self._data = StockHistoricalDataClient(api_key, secret_key)

    # -- account --------------------------------------------------------------
    def get_account(self):
        return self._trading.get_account()

    # -- market data ----------------------------------------------------------
    def get_latest_trade(self, symbol: str):
        req = StockLatestTradeRequest(symbol_or_symbols=symbol)
        trades = self._data.get_stock_latest_trade(req)
        return trades[symbol]

    # -- positions ------------------------------------------------------------
    def get_position(self, symbol: str):
        """Return the open position for *symbol*, or ``None`` if not held."""
        try:
            return self._trading.get_open_position(symbol)
        except Exception:
            return None

    def has_pending_order(self, symbol: str) -> bool:
        """Return ``True`` if there is an open/pending order for *symbol*."""
        try:
            req = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                symbols=[symbol],
            )
            orders = self._trading.get_orders(req)
            return len(orders) > 0
        except Exception:
            return False

    # -- orders ---------------------------------------------------------------
    def submit_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        type: str = "market",
        time_in_force: str = "day",
    ):
        order_req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self._trading.submit_order(order_req)


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def get_api() -> AlpacaAPI:
    """Build and return an authenticated Alpaca client."""
    api_key = _require_env("ALPACA_API_KEY")
    secret_key = _require_env("ALPACA_SECRET_KEY")
    paper = "paper" in CFG.alpaca_base_url

    log.info("Connecting to Alpaca (paper=%s)", paper)
    return AlpacaAPI(api_key, secret_key, paper=paper)
