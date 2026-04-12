# Feature Improvement Proposal — April 12, 2026

**Status:** Awaiting approval before April 13 retrain (retrain cron SUSPENDED)

## Problem Statement

The model achieves 53.7% CV accuracy with well-calibrated Platt probabilities that cluster
in [0.35, 0.51] (std=0.06). No predictions reach the BUY threshold (0.55) or SELL threshold
(0.35). The stable high-importance features are all macro/volatility signals — the model reads
market regime, not individual stock direction.

## Current Feature Audit (41 active features)

| Category | Count | Top performer | Weakest |
|---|---|---|---|
| Technical (RSI, MACD, BB, ATR, OBV, volume) | 11 | bb_upper (2.8%) | volume_zscore (1.8%) |
| Lagged returns | 5 | return_lag_10 (2.1%) | return_lag_2 (1.2%) |
| Rolling window (mean/std) | 8 | rolling_std_20 (3.3%) | rolling_mean_5 (1.2%) |
| Fundamentals (quarterly) | 11 | f_revenue_growth_yoy (4.6%) | f_operating_margin (erratic) |
| Market regime (VIX, SPY, rel. strength) | 7 | spy_return_20d (2.8%) | vix_above_avg (1.4%) |

---

## Part 1: New Stock-Specific Features (5 proposed)

### 1.1 Earnings Surprise / EPS Momentum

**What:** Forward EPS vs trailing EPS ratio, capturing analyst earnings growth expectations.

**Source:** `yf.Ticker(t).info["epsForward"]` and `yf.Ticker(t).info["trailingEps"]` — both
available for all 16 tickers (verified).

**Features:**
- `eps_growth_expected` = (epsForward / trailingEps) - 1

**Why it helps:** Currently the model uses only backward-looking quarterly financials (lagging
by up to 90 days). Forward EPS embeds analyst consensus about the next quarter. A stock with
high expected EPS growth is fundamentally different from one with flat expectations, even if
their trailing margins are identical. This is the single highest-value missing signal — it
directly predicts the direction the model is trying to forecast.

**Implementation:** Fetch once per ticker in `_fetch_quarterly_fundamentals()`, merge as a
slow-moving feature (changes only when analysts revise). Cache in `info` dict already fetched
during Phase 2.

### 1.2 Analyst Price Target Gap

**What:** Distance between current price and analyst consensus target.

**Source:** `yf.Ticker(t).info["targetMeanPrice"]` — available for all 16 tickers (verified).

**Features:**
- `analyst_target_gap` = (targetMeanPrice / close) - 1

**Why it helps:** This is a pure stock-specific signal. A stock trading 20% below consensus
target has a different expected return profile than one trading at or above target. The model
currently has zero analyst-derived features. Verified range across universe: TSLA at +20%
gap down to JNJ at +0.3% — sufficient variance to be informative.

**Implementation:** Fetch from `info` dict alongside EPS data. Recomputed daily against
closing price, so it's dynamic even when the target itself updates infrequently.

### 1.3 Analyst Revision Momentum

**What:** Change in consensus recommendation over recent months.

**Source:** `yf.Ticker(t).recommendations` — returns monthly snapshots of strongBuy/buy/hold/
sell/strongSell counts. Available for all 16 tickers (verified, 3-4 months of history).

**Features:**
- `analyst_revision_momentum` = recommendationMean(current month) - recommendationMean(3 months ago)

Lower values = upgrades (1=strongBuy, 5=strongSell), so negative momentum = bullish revision.

**Why it helps:** Analyst revisions are forward-looking and stock-specific. A cluster of
upgrades precedes price moves. This captures the *direction* of sentiment change among
professional analysts, not just the level. It's uncorrelated with the technical and macro
features that currently dominate.

**Implementation:** Pull `recommendations` DataFrame, compute weighted mean per period,
difference current vs 3-month-ago. Falls back to 0 if insufficient history.

### 1.4 Relative Strength vs Sector

**What:** Stock return relative to its sector ETF, not just SPY.

**Source:** Sector ETFs via yfinance (already used for SPY):
- Technology → XLK
- Communication Services → XLC
- Consumer Cyclical → XLY
- Financial Services → XLF
- Healthcare → XLV
- Energy → XLE
- Consumer Defensive → XLP

**Features:**
- `sector_relative_20d` = ticker 20-day return - sector ETF 20-day return
- `sector_relative_50d` = ticker 50-day return - sector ETF 50-day return

**Why it helps:** The existing `relative_strength_20d/50d` measures performance vs SPY
(broad market). But a tech stock outperforming SPY during a tech rally tells you nothing —
it's just riding the sector. Relative strength *within sector* isolates stock-specific alpha.
AAPL outperforming XLK while MSFT underperforms XLK is a much stronger signal than both
outperforming SPY.

**Implementation:** Add 7 sector ETFs to `fetch_market_data()` in Phase 1 (same as SPY/VIX
fetch). Map each ticker to its sector ETF in config. Compute relative returns in
`_add_market_regime()`. Adds ~7 small downloads to Phase 1, negligible cost.

### 1.5 Short Interest Change

**What:** Month-over-month change in short interest as a fraction of float.

**Source:** `yf.Ticker(t).info["shortPercentOfFloat"]` and
`yf.Ticker(t).info["sharesShortPriorMonth"]` — both available for all 16 tickers (verified).

**Features:**
- `short_interest_pct` = shortPercentOfFloat (current)
- `short_interest_change` = (sharesShort - sharesShortPriorMonth) / floatShares

**Why it helps:** Rising short interest signals institutional bearishness — a stock-specific
contrarian/momentum indicator. This is entirely uncorrelated with the technical features
(which are price-derived) and fundamental features (which are earnings-derived). Short
interest is relatively low across our large-cap universe (0.85% to 1.82%), but the *change*
has predictive value at extremes.

**Implementation:** Pull from `info` dict. Updates bi-monthly (FINRA schedule). Forward-fill
between updates. Two new columns.

---

## Part 2: Unstable Features — Drop or Replace

### Features to DROP (3)

| Feature | Issue | Fold 1 → Fold 5 trend | Action |
|---|---|---|---|
| `f_current_ratio` | 5.1% → 2.3%, collapsing | Halved in importance | **DROP** |
| `f_operating_margin` | 0.0% in fold 1 and fold 4 | Zero in 2/5 folds | **DROP** |
| `macd_hist` | 3.5% → 1.9%, declining | Redundant with macd + macd_signal | **DROP** |

**Rationale for dropping, not replacing:**
- `f_current_ratio`: Balance sheet liquidity ratio. For mega-caps, this is nearly constant
  and uninformative. The model learned it on early data where it correlated with a specific
  market environment, then lost that correlation.
- `f_operating_margin`: Zero importance in 2/5 folds means the model sometimes finds a
  spurious split, sometimes ignores it entirely. This is noise, not signal.
- `macd_hist`: This is literally `macd - macd_signal`. The model already has both components.
  The histogram adds collinearity without new information. Removing it reduces noise.

### Features to KEEP ON WATCH (2)

| Feature | Issue | Action |
|---|---|---|
| `f_profit_margin` | 4.7% → 2.8%, declining but still top-5 | Keep, monitor next retrain |
| `f_gross_margin` | 3.8% → 2.1%, declining | Keep, monitor next retrain |

These are declining but still above the pruning threshold (1%). The new EPS and analyst
features should absorb some of their predictive value. If they drop below 1.5% after the
next retrain, prune them.

---

## Part 3: Model Architecture — Single vs Per-Sector vs Per-Ticker

### Assessment

**Current architecture:** Single XGBoost trained on all 16 tickers pooled together.

**Sector distribution:**
- Technology: AAPL, MSFT, NVDA (3)
- Communication Services: GOOGL, META (2)
- Consumer Cyclical: AMZN, TSLA (2)
- Financial Services: BRK-B, JPM, V (3)
- Healthcare: JNJ, LLY (2)
- Energy: XOM (1)
- Consumer Defensive: PG, KO, WMT (3)

### Per-Ticker Model: REJECT

- 16 separate models with ~756 rows each = severe overfitting risk
- Cannot cross-learn patterns (e.g., "high VIX predicts down for all tech stocks")
- Maintenance burden is 16x
- Not viable at this universe size

### Per-Sector Model: REJECT (for now)

- Sector sizes range from 1 (Energy) to 3 (Tech, Financial, Consumer Defensive)
- Even the largest sector gives only ~2,268 rows (3 tickers x 756 days)
- Sectors with 1-2 tickers would overfit worse than the pooled model
- **Revisit if universe expands to 40+ tickers** where each sector has 5+

### Recommendation: KEEP SINGLE MODEL with sector-aware features

The right fix is not splitting the model — it's giving the single model the features it
needs to distinguish stocks. The new sector-relative-strength features (Part 1.4) let the
model learn "this stock is outperforming its sector" without needing separate models.

Additionally, add a **sector one-hot encoding** (7 binary columns) so the model can learn
sector-specific patterns within the single tree ensemble:
- `sector_technology`, `sector_communication`, `sector_consumer_cyclical`,
  `sector_financial`, `sector_healthcare`, `sector_energy`, `sector_consumer_defensive`

This gives the model the ability to make sector-conditional splits (e.g., "if Technology AND
VIX spike → SELL") without the sample-size penalty of splitting into separate models.

---

## Summary of Changes

### Add (12 new features)
| # | Feature | Type | Source |
|---|---|---|---|
| 1 | `eps_growth_expected` | Fundamental | yf.info |
| 2 | `analyst_target_gap` | Analyst | yf.info |
| 3 | `analyst_revision_momentum` | Analyst | yf.recommendations |
| 4 | `sector_relative_20d` | Market regime | Sector ETF OHLCV |
| 5 | `sector_relative_50d` | Market regime | Sector ETF OHLCV |
| 6 | `short_interest_pct` | Alternative | yf.info |
| 7 | `short_interest_change` | Alternative | yf.info |
| 8-14 | `sector_*` (7 one-hot) | Categorical | Hardcoded mapping |

### Drop (3 features)
- `f_current_ratio`, `f_operating_margin`, `macd_hist`

### Net change
- Current: 41 active features
- After: 41 - 3 + 14 = **52 active features**
- Feature pruning (existing 2-pass system) will automatically remove any that don't earn
  their keep

### Files to modify
1. `src/config.py` — Add sector ETF map, sector-to-ticker map
2. `src/ingest.py` — Add sector ETF downloads to `fetch_market_data()`
3. `src/features.py` — New functions: `_add_analyst_features()`, `_add_short_interest()`,
   `_add_sector_relative_strength()`, `_add_sector_encoding()`. Drop 3 features in
   `build_features()`.
4. `src/train.py` — No changes needed (pruning handles new features automatically)

### Implementation estimate
- Config + ingest changes: straightforward
- Feature engineering: 4 new functions, each ~20-40 lines
- Testing: Run Phase 1-3 locally with `--dry-run`, verify feature distributions

---

## Risk Assessment

| Risk | Mitigation |
|---|---|
| yfinance `info` rate-limited | Already fetch per-ticker; adds ~3 fields to existing call |
| Analyst data sparse for some tickers | Falls back to 0 (neutral), same as current fundamental handling |
| Sector ETF data gaps | Major ETFs (XLK, XLF, etc.) have full history back to 2021 |
| More features → overfitting | Existing 2-pass pruning handles this; 52 features for ~12,000 rows is reasonable |
| One-hot encoding in XGBoost | XGBoost handles binary splits natively; no special encoding needed |

---

## Next Steps (pending approval)

1. Implement features in `config.py`, `ingest.py`, `features.py`
2. Run Phases 1-3 locally, verify feature matrix
3. Compare CV accuracy: old 41 features vs new 52 features
4. If CV accuracy improves (target: >55%), deploy to VPS and re-enable retrain cron
5. Resume signal generation with new model
6. Re-evaluate thresholds based on new probability distribution
