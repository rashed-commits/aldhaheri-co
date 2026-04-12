"""
Phase 2: Feature Engineering Pipeline
======================================
Reads ``data/combined.csv`` and produces ``data/features.csv`` with
technical indicators, fundamental ratios, market regime features,
and lagged returns used by the model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from src.config import CFG
from src.utils import (
    check_required_columns,
    drop_na_rows,
    get_logger,
    load_csv,
    save_csv,
)

log = get_logger("features")

_REQUIRED_COLS = ["date", "open", "high", "low", "close", "volume", "ticker"]


# ---------------------------------------------------------------------------
# Individual indicator builders
# ---------------------------------------------------------------------------

def _add_rsi(df: pd.DataFrame, period: int = CFG.rsi_period) -> pd.DataFrame:
    """Append RSI column (``rsi``) to *df* (in-place) and return it."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def _add_macd(
    df: pd.DataFrame,
    fast: int = CFG.macd_fast,
    slow: int = CFG.macd_slow,
    signal: int = CFG.macd_signal,
) -> pd.DataFrame:
    """Append MACD columns (``macd``, ``macd_signal``)."""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    return df


def _add_bollinger_bands(
    df: pd.DataFrame,
    period: int = CFG.bb_period,
    std_dev: float = CFG.bb_std,
) -> pd.DataFrame:
    """Append Bollinger-Band columns (``bb_upper``, ``bb_mid``, ``bb_lower``, ``bb_width``)."""
    rolling = df["close"].rolling(period)
    df["bb_mid"] = rolling.mean()
    std = rolling.std()
    df["bb_upper"] = df["bb_mid"] + std_dev * std
    df["bb_lower"] = df["bb_mid"] - std_dev * std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
    return df


def _add_atr(
    df: pd.DataFrame, period: int = CFG.atr_period
) -> pd.DataFrame:
    """Append Average True Range column (``atr``)."""
    hl = df["high"] - df["low"]
    hpc = (df["high"] - df["close"].shift()).abs()
    lpc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    df["atr"] = tr.ewm(com=period - 1, min_periods=period).mean()
    return df


def _add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Append volume Z-score and OBV columns."""
    vol_mean = df["volume"].rolling(20).mean()
    vol_std = df["volume"].rolling(20).std()
    df["volume_zscore"] = (df["volume"] - vol_mean) / vol_std.replace(0, np.nan)

    obv = np.where(df["close"] > df["close"].shift(), df["volume"], -df["volume"])
    df["obv"] = pd.Series(obv, index=df.index).cumsum()
    return df


def _add_lag_features(
    df: pd.DataFrame, lags: list[int] = CFG.lag_days
) -> pd.DataFrame:
    """Append lagged close-return columns (``return_lag_N``)."""
    for lag in lags:
        df[f"return_lag_{lag}"] = df["close"].pct_change(lag)
    return df


def _add_rolling_features(
    df: pd.DataFrame, windows: list[int] = CFG.rolling_windows
) -> pd.DataFrame:
    """Append rolling-mean and rolling-std return columns."""
    returns = df["close"].pct_change()
    for w in windows:
        df[f"rolling_mean_{w}"] = returns.rolling(w).mean()
        df[f"rolling_std_{w}"] = returns.rolling(w).std()
    return df


def _add_target(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append binary target column (``target``).

    ``target = 1`` if the forward return over ``CFG.target_horizon`` trading
    days exceeds ``CFG.target_return_threshold``, else ``0``.
    """
    fwd_return = df["close"].shift(-CFG.target_horizon) / df["close"] - 1
    df["target"] = (fwd_return > CFG.target_return_threshold).astype(int)
    return df


# ---------------------------------------------------------------------------
# Fundamental features (from yfinance quarterly financials)
# ---------------------------------------------------------------------------

def _fetch_quarterly_fundamentals(ticker: str) -> pd.DataFrame:
    """Fetch quarterly financial data and return a DataFrame indexed by date.

    Each row represents one quarter's financials, forward-filled to every
    trading day so the model only sees data that was publicly available at
    each point in time (no look-ahead bias).
    """
    try:
        t = yf.Ticker(ticker)
        inc = t.quarterly_financials
        bs = t.quarterly_balance_sheet
        cf = t.quarterly_cashflow
    except Exception as exc:
        log.warning("Could not fetch fundamentals for %s: %s", ticker, exc)
        return pd.DataFrame()

    if inc is None or inc.empty:
        return pd.DataFrame()

    records = []
    dates = sorted(inc.columns)

    for d in dates:
        row = {"date": pd.Timestamp(d)}

        # Income statement
        revenue = _safe_val(inc, "Total Revenue", d)
        net_income = _safe_val(inc, "Net Income", d)
        op_income = _safe_val(inc, "Operating Income", d)
        gross_profit = _safe_val(inc, "Gross Profit", d)

        row["f_profit_margin"] = net_income / revenue if (revenue and net_income is not None) else np.nan
        row["f_gross_margin"] = gross_profit / revenue if (revenue and gross_profit is not None) else np.nan

        # Revenue growth (QoQ)
        idx = dates.index(d)
        if idx > 0 and revenue is not None:
            prev_rev = _safe_val(inc, "Total Revenue", dates[idx - 1])
            row["f_revenue_growth_qoq"] = (revenue / prev_rev - 1) if prev_rev else np.nan
        else:
            row["f_revenue_growth_qoq"] = np.nan

        # Revenue growth (YoY) — compare to 4 quarters ago
        if idx >= 4 and revenue is not None:
            yoy_rev = _safe_val(inc, "Total Revenue", dates[idx - 4])
            row["f_revenue_growth_yoy"] = (revenue / yoy_rev - 1) if yoy_rev else np.nan
        else:
            row["f_revenue_growth_yoy"] = np.nan

        # Balance sheet
        if bs is not None and not bs.empty and d in bs.columns:
            total_debt = _safe_val(bs, "Total Debt", d)
            equity_val = _safe_val(bs, "Stockholders Equity", d)
            total_assets = _safe_val(bs, "Total Assets", d)
            cash = _safe_val(bs, "Cash And Cash Equivalents", d)
            current_assets = _safe_val(bs, "Current Assets", d)
            current_liab = _safe_val(bs, "Current Liabilities", d)

            row["f_debt_to_equity"] = total_debt / equity_val if (equity_val and total_debt is not None) else np.nan
            row["f_roe"] = net_income / equity_val if (equity_val and net_income is not None) else np.nan
            row["f_cash_to_debt"] = cash / total_debt if (total_debt and cash is not None) else np.nan
            row["f_debt_to_assets"] = total_debt / total_assets if (total_assets and total_debt is not None) else np.nan

        # Cash flow
        if cf is not None and not cf.empty and d in cf.columns:
            op_cf = _safe_val(cf, "Operating Cash Flow", d)
            capex = _safe_val(cf, "Capital Expenditure", d)
            fcf = (op_cf + capex) if op_cf is not None and capex is not None else None
            row["f_fcf_margin"] = fcf / revenue if (fcf is not None and revenue) else np.nan

        records.append(row)

    if not records:
        return pd.DataFrame()

    fund_df = pd.DataFrame(records)
    fund_df["date"] = pd.to_datetime(fund_df["date"]).dt.tz_localize(None)
    fund_df = fund_df.sort_values("date")
    return fund_df


def _safe_val(df: pd.DataFrame, row_name: str, col) -> float | None:
    """Safely extract a value from a financials DataFrame."""
    try:
        if row_name in df.index:
            val = df.loc[row_name, col]
            if pd.notna(val):
                return float(val)
    except Exception:
        pass
    return None


def _add_fundamental_features(
    df: pd.DataFrame, fund_df: pd.DataFrame
) -> pd.DataFrame:
    """Merge quarterly fundamentals into daily OHLCV data via asof join.

    Fundamentals are forward-filled: each day uses the most recent quarterly
    report that was available at that time.
    """
    if fund_df.empty:
        # Add NaN columns so downstream pipeline doesn't break
        for col in [
            "f_profit_margin", "f_gross_margin",
            "f_revenue_growth_qoq", "f_revenue_growth_yoy",
            "f_debt_to_equity", "f_roe",
            "f_cash_to_debt", "f_debt_to_assets", "f_fcf_margin",
        ]:
            df[col] = np.nan
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.as_unit("ns")
    fund_df["date"] = pd.to_datetime(fund_df["date"]).dt.as_unit("ns")

    df = df.sort_values("date")
    fund_df = fund_df.sort_values("date")

    merged = pd.merge_asof(
        df, fund_df, on="date", direction="backward"
    )
    # Forward-fill then fill remaining NaN with 0 for fundamental columns
    # (early dates before the first quarterly report will have NaN)
    fund_cols = [c for c in merged.columns if c.startswith("f_")]
    merged[fund_cols] = merged[fund_cols].ffill().fillna(0)
    return merged


# ---------------------------------------------------------------------------
# Market regime features (VIX + SPY)
# ---------------------------------------------------------------------------

def _add_market_regime(
    df: pd.DataFrame, market_df: pd.DataFrame | None
) -> pd.DataFrame:
    """Add VIX and SPY-based market regime features."""
    if market_df is None or market_df.empty:
        for col in [
            "vix", "vix_sma20", "vix_above_avg",
            "spy_return_20d", "spy_return_50d",
            "relative_strength_20d", "relative_strength_50d",
        ]:
            df[col] = np.nan
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.as_unit("ns")
    market_df = market_df.copy()
    market_df["date"] = pd.to_datetime(market_df["date"]).dt.as_unit("ns")

    # Compute SPY features on market_df before merge
    if "spy_close" in market_df.columns:
        market_df["spy_return_20d"] = market_df["spy_close"].pct_change(20)
        market_df["spy_return_50d"] = market_df["spy_close"].pct_change(50)

    if "vix_close" in market_df.columns:
        market_df["vix"] = market_df["vix_close"]
        market_df["vix_sma20"] = market_df["vix_close"].rolling(20).mean()
        market_df["vix_above_avg"] = (
            market_df["vix_close"] > market_df["vix_sma20"]
        ).astype(float)

    # Drop raw columns before merge
    merge_cols = ["date"]
    for c in ["vix", "vix_sma20", "vix_above_avg", "spy_return_20d", "spy_return_50d"]:
        if c in market_df.columns:
            merge_cols.append(c)

    market_merge = market_df[merge_cols].sort_values("date")
    df = df.sort_values("date")

    df = pd.merge_asof(df, market_merge, on="date", direction="backward")

    # Relative strength: ticker vs SPY
    ticker_return_20d = df["close"].pct_change(20)
    ticker_return_50d = df["close"].pct_change(50)
    spy_20 = df["spy_return_20d"] if "spy_return_20d" in df.columns else 0
    spy_50 = df["spy_return_50d"] if "spy_return_50d" in df.columns else 0
    df["relative_strength_20d"] = ticker_return_20d - spy_20
    df["relative_strength_50d"] = ticker_return_50d - spy_50

    # Fill NaN in market regime columns (early rows before enough data)
    mkt_cols = [c for c in df.columns if c in [
        "vix", "vix_sma20", "vix_above_avg",
        "spy_return_20d", "spy_return_50d",
        "relative_strength_20d", "relative_strength_50d",
    ]]
    df[mkt_cols] = df[mkt_cols].ffill().fillna(0)

    return df


# ---------------------------------------------------------------------------
# Sentiment features (FinBERT)
# ---------------------------------------------------------------------------

def _add_sentiment_features(
    df: pd.DataFrame, sentiment_df: pd.DataFrame
) -> pd.DataFrame:
    """Merge daily FinBERT sentiment scores into OHLCV data.

    Joins on date, forward-fills gaps (weekends/holidays), and fills any
    remaining missing days with 0 (neutral sentiment).
    """
    sent_cols = ["sentiment_positive_score", "sentiment_negative_score", "sentiment_net_score"]

    if sentiment_df.empty:
        for col in sent_cols:
            df[col] = 0.0
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.as_unit("ns")
    sentiment_df = sentiment_df.copy()
    sentiment_df["date"] = pd.to_datetime(sentiment_df["date"]).dt.as_unit("ns")

    # Filter sentiment to this ticker if ticker column exists
    if "ticker" in sentiment_df.columns and "ticker" in df.columns:
        ticker = df["ticker"].iloc[0]
        sentiment_df = sentiment_df[sentiment_df["ticker"] == ticker]

    if sentiment_df.empty:
        for col in sent_cols:
            df[col] = 0.0
        return df

    merge_df = sentiment_df[["date"] + sent_cols].sort_values("date")
    df = df.sort_values("date")

    df = pd.merge_asof(df, merge_df, on="date", direction="backward")

    # Forward-fill then fill remaining with 0 (neutral)
    df[sent_cols] = df[sent_cols].ffill().fillna(0.0)

    return df


# ---------------------------------------------------------------------------
# Analyst features (from yfinance upgrades_downgrades)
# ---------------------------------------------------------------------------

def _fetch_analyst_data(ticker: str) -> pd.DataFrame:
    """Fetch timestamped analyst upgrades/downgrades with price targets.

    Returns a DataFrame with columns: date, analyst_target, action_score.
    action_score: +1 for upgrades (up/init with positive tone), -1 for
    downgrades (down), 0 for maintains/reiterate.
    """
    try:
        t = yf.Ticker(ticker)
        ud = t.upgrades_downgrades
    except Exception as exc:
        log.warning("Could not fetch analyst data for %s: %s", ticker, exc)
        return pd.DataFrame()

    if ud is None or ud.empty:
        return pd.DataFrame()

    ud = ud.copy()
    ud.index = pd.to_datetime(ud.index).tz_localize(None)
    ud = ud.reset_index().rename(columns={"GradeDate": "date"})

    # Extract price targets (0 means not provided)
    ud["analyst_target"] = pd.to_numeric(ud["currentPriceTarget"], errors="coerce").fillna(0)

    # Score each action: up=+1, down=-1, maintain/init=0
    action_map = {"up": 1, "down": -1, "main": 0, "init": 0, "reit": 0}
    ud["action_score"] = ud["Action"].str.lower().map(action_map).fillna(0).astype(int)

    return ud[["date", "analyst_target", "action_score"]].sort_values("date")


def _add_analyst_features(
    df: pd.DataFrame, analyst_df: pd.DataFrame
) -> pd.DataFrame:
    """Add analyst_target_gap and analyst_revision_momentum features.

    analyst_target_gap: (consensus target / close) - 1
    analyst_revision_momentum: net upgrades minus downgrades in rolling 90 days
    """
    if analyst_df.empty:
        df["analyst_target_gap"] = 0.0
        df["analyst_revision_momentum"] = 0.0
        return df

    df["date"] = pd.to_datetime(df["date"]).dt.as_unit("ns")
    analyst_df = analyst_df.copy()
    analyst_df["date"] = pd.to_datetime(analyst_df["date"]).dt.as_unit("ns")

    # Build daily consensus target: rolling mean of last 10 analyst targets
    targets = analyst_df[analyst_df["analyst_target"] > 0].copy()
    if not targets.empty:
        # Group by date (multiple actions same day), take mean target
        daily_target = targets.groupby("date")["analyst_target"].mean().reset_index()
        daily_target = daily_target.rename(columns={"analyst_target": "_analyst_target_raw"})
        daily_target = daily_target.sort_values("date")

        df = df.sort_values("date")
        df = pd.merge_asof(df, daily_target, on="date", direction="backward")
        df["analyst_target_gap"] = np.where(
            (df["_analyst_target_raw"] > 0) & (df["close"] > 0),
            df["_analyst_target_raw"] / df["close"] - 1,
            0.0,
        )
        df.drop(columns=["_analyst_target_raw"], inplace=True)
    else:
        df["analyst_target_gap"] = 0.0

    # Revision momentum: net actions (upgrades - downgrades) in rolling 90-day window
    actions = analyst_df[["date", "action_score"]].copy()
    if not actions.empty:
        # For each trading date, count net upgrades in prior 90 days
        df = df.sort_values("date")
        momentum_values = []
        action_dates = actions["date"].values
        action_scores = actions["action_score"].values
        for trade_date in df["date"].values:
            window_start = trade_date - np.timedelta64(90, "D")
            mask = (action_dates > window_start) & (action_dates <= trade_date)
            momentum_values.append(int(action_scores[mask].sum()))
        df["analyst_revision_momentum"] = momentum_values
    else:
        df["analyst_revision_momentum"] = 0.0

    df[["analyst_target_gap", "analyst_revision_momentum"]] = (
        df[["analyst_target_gap", "analyst_revision_momentum"]].ffill().fillna(0.0)
    )
    return df


# ---------------------------------------------------------------------------
# Short interest features (from yfinance info)
# ---------------------------------------------------------------------------

def _fetch_short_interest(ticker: str) -> dict:
    """Fetch current short interest data. Returns a dict with pct and change."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        shares_short = info.get("sharesShort", 0) or 0
        shares_prior = info.get("sharesShortPriorMonth", 0) or 0
        float_shares = info.get("floatShares", 0) or 0

        pct = info.get("shortPercentOfFloat", 0) or 0
        change = (shares_short - shares_prior) / float_shares if float_shares > 0 else 0

        return {"short_interest_pct": pct, "short_interest_change": change}
    except Exception as exc:
        log.warning("Could not fetch short interest for %s: %s", ticker, exc)
        return {"short_interest_pct": 0.0, "short_interest_change": 0.0}


def _add_short_interest(df: pd.DataFrame, short_data: dict) -> pd.DataFrame:
    """Add short interest features as constant columns (updated bi-monthly by FINRA)."""
    df["short_interest_pct"] = short_data.get("short_interest_pct", 0.0)
    df["short_interest_change"] = short_data.get("short_interest_change", 0.0)
    return df


# ---------------------------------------------------------------------------
# Sector-relative strength features
# ---------------------------------------------------------------------------

def _add_sector_relative_strength(
    df: pd.DataFrame, market_df: pd.DataFrame | None, ticker: str
) -> pd.DataFrame:
    """Add sector-relative strength (stock return vs sector ETF return)."""
    sector_etf = CFG.ticker_sector.get(ticker)
    etf_col = f"{sector_etf.lower()}_close" if sector_etf else None

    if market_df is None or market_df.empty or etf_col is None or etf_col not in market_df.columns:
        df["sector_relative_20d"] = 0.0
        df["sector_relative_50d"] = 0.0
        return df

    # Compute sector ETF returns on market_df
    mkt = market_df[["date", etf_col]].copy()
    mkt["date"] = pd.to_datetime(mkt["date"]).dt.as_unit("ns")
    mkt[f"_sector_ret_20d"] = mkt[etf_col].pct_change(20)
    mkt[f"_sector_ret_50d"] = mkt[etf_col].pct_change(50)
    mkt = mkt[["date", "_sector_ret_20d", "_sector_ret_50d"]].sort_values("date")

    df["date"] = pd.to_datetime(df["date"]).dt.as_unit("ns")
    df = df.sort_values("date")
    df = pd.merge_asof(df, mkt, on="date", direction="backward")

    ticker_ret_20d = df["close"].pct_change(20)
    ticker_ret_50d = df["close"].pct_change(50)
    sector_20 = df["_sector_ret_20d"] if "_sector_ret_20d" in df.columns else 0
    sector_50 = df["_sector_ret_50d"] if "_sector_ret_50d" in df.columns else 0
    df["sector_relative_20d"] = ticker_ret_20d - sector_20
    df["sector_relative_50d"] = ticker_ret_50d - sector_50

    df.drop(columns=["_sector_ret_20d", "_sector_ret_50d"], errors="ignore", inplace=True)
    df[["sector_relative_20d", "sector_relative_50d"]] = (
        df[["sector_relative_20d", "sector_relative_50d"]].ffill().fillna(0)
    )
    return df


# ---------------------------------------------------------------------------
# Sector one-hot encoding
# ---------------------------------------------------------------------------

def _add_sector_encoding(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Add binary sector columns for the given ticker."""
    sector_etf = CFG.ticker_sector.get(ticker)
    for etf, sector_name in CFG.sector_etfs.items():
        col = "sector_" + sector_name.lower().replace(" ", "_")
        df[col] = 1.0 if etf == sector_etf else 0.0
    return df


# ---------------------------------------------------------------------------
# Per-ticker feature engineering
# ---------------------------------------------------------------------------

def build_features(
    df: pd.DataFrame,
    market_df: pd.DataFrame | None = None,
    fund_df: pd.DataFrame | None = None,
    sentiment_df: pd.DataFrame | None = None,
    analyst_df: pd.DataFrame | None = None,
    short_data: dict | None = None,
) -> pd.DataFrame:
    """
    Apply all indicator builders to a single-ticker DataFrame and return
    the result after dropping NaN rows introduced by look-back windows.

    Parameters
    ----------
    df : DataFrame with OHLCV + ticker columns
    market_df : Optional market regime data (VIX + SPY + sector ETFs)
    fund_df : Optional quarterly fundamentals for this ticker
    sentiment_df : Optional daily sentiment scores for this ticker
    analyst_df : Optional timestamped analyst upgrades/downgrades
    short_data : Optional dict with short_interest_pct and short_interest_change
    """
    ticker = str(df["ticker"].iloc[0])
    df = df.copy().sort_values("date").reset_index(drop=True)

    # Technical indicators
    df = _add_rsi(df)
    df = _add_macd(df)
    df = _add_bollinger_bands(df)
    df = _add_atr(df)
    df = _add_volume_features(df)
    df = _add_lag_features(df)
    df = _add_rolling_features(df)

    # Fundamental features
    if fund_df is None:
        fund_df = pd.DataFrame()
    df = _add_fundamental_features(df, fund_df)

    # Market regime features (VIX + SPY)
    df = _add_market_regime(df, market_df)

    # Sector-relative strength
    df = _add_sector_relative_strength(df, market_df, ticker)

    # Sector one-hot encoding
    df = _add_sector_encoding(df, ticker)

    # Analyst features (target gap + revision momentum)
    if analyst_df is None:
        analyst_df = pd.DataFrame()
    df = _add_analyst_features(df, analyst_df)

    # Short interest
    if short_data is None:
        short_data = {}
    df = _add_short_interest(df, short_data)

    # Sentiment features
    if sentiment_df is not None and not sentiment_df.empty:
        df = _add_sentiment_features(df, sentiment_df)
    else:
        for col in ["sentiment_positive_score", "sentiment_negative_score", "sentiment_net_score"]:
            df[col] = 0.0

    # Target
    df = _add_target(df)

    df = drop_na_rows(df, context=ticker)
    return df


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Entry point called by ``main.py --phase 2``."""
    src_path = CFG.data_dir / "combined.csv"
    df = load_csv(src_path)
    check_required_columns(df, _REQUIRED_COLS, context="combined.csv")

    # Load market regime data
    market_path = CFG.data_dir / "market.csv"
    market_df = None
    if market_path.exists():
        market_df = load_csv(market_path)
        log.info("Loaded %d market regime rows.", len(market_df))
    else:
        log.warning("No market.csv found — market regime features will be NaN.")

    # Load sentiment data
    sentiment_path = CFG.data_dir / "sentiment.csv"
    sentiment_df = None
    if sentiment_path.exists():
        sentiment_df = load_csv(sentiment_path)
        log.info("Loaded %d sentiment rows.", len(sentiment_df))
    else:
        log.warning("No sentiment.csv found — sentiment features will be neutral (0).")

    # Fetch fundamentals, analyst data, and short interest per ticker
    log.info("Building features for %d tickers ...", df["ticker"].nunique())
    parts = []
    for ticker, grp in df.groupby("ticker", sort=False):
        log.info("Fetching data for %s ...", ticker)
        fund_df = _fetch_quarterly_fundamentals(ticker)
        if not fund_df.empty:
            log.info("  %s: %d quarterly reports found.", ticker, len(fund_df))
        else:
            log.warning("  %s: no quarterly data available.", ticker)

        analyst_df = _fetch_analyst_data(ticker)
        if not analyst_df.empty:
            log.info("  %s: %d analyst actions found.", ticker, len(analyst_df))

        short_data = _fetch_short_interest(ticker)

        parts.append(build_features(
            grp, market_df=market_df, fund_df=fund_df,
            sentiment_df=sentiment_df, analyst_df=analyst_df,
            short_data=short_data,
        ))

    features_df = pd.concat(parts, ignore_index=True)

    out_path = CFG.data_dir / "features.csv"
    save_csv(features_df, out_path, index=False)
    log.info(
        "Saved %s rows / %d columns to %s",
        f"{len(features_df):,}",
        len(features_df.columns),
        out_path,
    )
