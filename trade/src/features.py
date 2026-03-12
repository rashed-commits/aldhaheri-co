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
    """Append MACD columns (``macd``, ``macd_signal``, ``macd_hist``)."""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
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
        row["f_operating_margin"] = op_income / revenue if (revenue and op_income is not None) else np.nan
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
            row["f_current_ratio"] = current_assets / current_liab if (current_liab and current_assets is not None) else np.nan
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
            "f_profit_margin", "f_operating_margin", "f_gross_margin",
            "f_revenue_growth_qoq", "f_revenue_growth_yoy",
            "f_debt_to_equity", "f_roe", "f_current_ratio",
            "f_cash_to_debt", "f_debt_to_assets", "f_fcf_margin",
        ]:
            df[col] = np.nan
        return df

    df["date"] = pd.to_datetime(df["date"])
    fund_df["date"] = pd.to_datetime(fund_df["date"])

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

    df["date"] = pd.to_datetime(df["date"])
    market_df = market_df.copy()
    market_df["date"] = pd.to_datetime(market_df["date"])

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
# Per-ticker feature engineering
# ---------------------------------------------------------------------------

def build_features(
    df: pd.DataFrame,
    market_df: pd.DataFrame | None = None,
    fund_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Apply all indicator builders to a single-ticker DataFrame and return
    the result after dropping NaN rows introduced by look-back windows.

    Parameters
    ----------
    df : DataFrame with OHLCV + ticker columns
    market_df : Optional market regime data (VIX + SPY)
    fund_df : Optional quarterly fundamentals for this ticker
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    # Technical indicators (existing)
    df = _add_rsi(df)
    df = _add_macd(df)
    df = _add_bollinger_bands(df)
    df = _add_atr(df)
    df = _add_volume_features(df)
    df = _add_lag_features(df)
    df = _add_rolling_features(df)

    # Fundamental features (new)
    if fund_df is None:
        fund_df = pd.DataFrame()
    df = _add_fundamental_features(df, fund_df)

    # Market regime features (new)
    df = _add_market_regime(df, market_df)

    # Target
    df = _add_target(df)

    df = drop_na_rows(df, context=str(df["ticker"].iloc[0]))
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

    # Fetch fundamentals per ticker and build features
    log.info("Building features for %d tickers ...", df["ticker"].nunique())
    parts = []
    for ticker, grp in df.groupby("ticker", sort=False):
        log.info("Fetching quarterly fundamentals for %s ...", ticker)
        fund_df = _fetch_quarterly_fundamentals(ticker)
        if not fund_df.empty:
            log.info("  %s: %d quarterly reports found.", ticker, len(fund_df))
        else:
            log.warning("  %s: no quarterly data available.", ticker)
        parts.append(build_features(grp, market_df=market_df, fund_df=fund_df))

    features_df = pd.concat(parts, ignore_index=True)

    out_path = CFG.data_dir / "features.csv"
    save_csv(features_df, out_path, index=False)
    log.info(
        "Saved %s rows / %d columns to %s",
        f"{len(features_df):,}",
        len(features_df.columns),
        out_path,
    )
