"""
Centralised configuration for Trade-Bot.
=========================================
All tuneable hyper-parameters, paths, and environment-variable bindings
live here.  Import ``CFG`` from any module instead of hard-coding values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class Config:
    # ------------------------------------------------------------------ paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def model_dir(self) -> Path:
        return self.base_dir / "model" / "saved"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "output"

    # --------------------------------------------------------------- universe
    tickers: List[str] = field(
        default_factory=lambda: [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
            "META", "TSLA", "BRK-B", "JPM", "V",
            "JNJ", "LLY", "XOM", "PG", "KO", "WMT",
        ]
    )

    # Alpaca uses dots instead of hyphens for some symbols
    alpaca_symbol_map: Dict = field(default_factory=lambda: {
        "BRK-B": "BRK.B",
    })
    start_date: str = "2021-01-01"
    end_date: str = ""  # empty = use today's date (always train on latest data)

    # -------------------------------------------------- feature-engineering
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    lag_days: List[int] = field(default_factory=lambda: [1, 2, 3, 5, 10])
    rolling_windows: List[int] = field(default_factory=lambda: [5, 10, 20, 50])

    # --------------------------------------------------------- model training
    test_size: float = 0.2
    n_estimators: int = 500
    max_depth: int = 5
    learning_rate: float = 0.03
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    random_state: int = 42
    cv_folds: int = 5

    # ------------------------------------------------------- signal generation
    signal_threshold_buy: float = 0.65
    signal_threshold_sell: float = 0.4
    top_n_signals: int = 5

    # --------------------------------------------------------- paper trading
    max_position_size: float = 0.1   # 10 % of portfolio per position
    stop_loss_pct: float = 0.05      # 5 % stop-loss
    take_profit_pct: float = 0.15    # 15 % take-profit
    max_open_positions: int = 10

    # ------------------------------------------------- ML pipeline tuning
    target_horizon: int = 5              # forward return look-ahead (trading days)
    target_return_threshold: float = 0.01  # min forward return for target=1 (1%)
    walk_forward_window: int = 756       # ~3 years of trading days
    min_feature_importance: float = 0.01 # prune features below this importance

    # --------------------------------------------------- Alpaca (from env)
    @property
    def alpaca_api_key(self) -> str:
        return os.environ.get("ALPACA_API_KEY", "")

    @property
    def alpaca_secret_key(self) -> str:
        return os.environ.get("ALPACA_SECRET_KEY", "")

    @property
    def alpaca_base_url(self) -> str:
        return os.environ.get(
            "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
        )

    # --------------------------------------------------- Telegram (from env)
    @property
    def telegram_bot_token(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_chat_id(self) -> str:
        return os.environ.get("TELEGRAM_CHAT_ID", "")


#: Module-level singleton — import this everywhere.
CFG = Config()
