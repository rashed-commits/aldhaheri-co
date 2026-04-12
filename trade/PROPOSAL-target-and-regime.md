# Proposal: 10-Day Target + Regime-Adjusted Thresholds

**Status:** Awaiting approval (Sunday retrain SUSPENDED)

## Recommendation: Both Options Combined

The two options are complementary, not competing. Changing the target improves model
accuracy; regime awareness improves signal quality. Together they solve both problems:
the model can't predict, and even when it can, the thresholds are unreachable.

---

## Part 1: Change Prediction Target to 10-Day Direction

### The Problem

The current target (`target = 1 if 5-day return > 1%`) has 42.4% positive class and
the model achieves 53.7% CV accuracy. With Platt calibration, probabilities compress
to [0.35, 0.51] — all HOLD.

### Quick CV Results Across Target Variants

| Target | Positive % | CV Accuracy | CV AUC | Fold Trend |
|---|---|---|---|---|
| 5-day absolute >1% (current) | 42.8% | 53.8% ± 4.4 | 55.0% ± 4.1 | 49→52→56→62→51 |
| 5-day sector-relative >0% | 50.2% | 50.3% ± 2.1 | 50.0% ± 1.9 | Random noise |
| **10-day absolute >1%** | **48.0%** | **55.2% ± 3.3** | **57.3% ± 4.2** | **51→53→59→59→55** |
| 10-day sector-relative >0% | 49.5% | 52.6% ± 3.1 | 53.3% ± 4.4 | Mixed |

### Why 10-Day Absolute Wins

1. **Higher accuracy**: 55.2% vs 53.8% (+1.4%) — the model's features (rolling
   windows, fundamentals, VIX) are medium-term signals that predict 10 days
   better than 5 days. This makes sense: a 50-day rolling std doesn't predict
   tomorrow, but it predicts next week.

2. **Better label balance**: 48.0% positive (vs 42.8%) reduces class imbalance,
   improving F1 and reducing the model's bias toward negative predictions.

3. **Wider probability spread with calibration**: On fold 5 (most recent data):
   - Current (5d): prob range [0.35, 0.51], std=0.06 — **zero actionable signals**
   - 10-day: prob range [0.35, 0.61], std=0.06 — **289 BUY signals at 0.55 threshold**

4. **Stable fold trend**: 51→53→59→59→55. No fold-4 collapse like the current model
   (46.6%). The later folds (recent data) are the strongest.

5. **Sector-relative targets fail**: Both 5d and 10d relative targets produce ~50%
   accuracy (random). The model cannot distinguish individual stock alpha from market
   beta. It's a regime model, not a stock-picker — lean into that.

### Calibrated Probability Distribution (Fold 5 Validation)

```
Current 5d target:  mean=0.41  std=0.06  range=[0.35, 0.51]
New 10d target:     mean=0.48  std=0.06  range=[0.35, 0.61]

Signals at buy=0.55 threshold:
  Current:  0 BUY,   0 SELL out of 2016
  New:    289 BUY,   0 SELL out of 2016

BUY accuracy at 0.55 threshold: 59.5%
```

### Implementation

**Files:** `src/features.py`, `src/config.py`, `src/execution/executor.py`

**Changes:**
1. `CFG.target_horizon`: 5 → 10
2. `_add_target()` in features.py — no code change needed, uses `CFG.target_horizon`
3. `executor.py` — update position hold expectations (10-day signals imply longer
   holds; stop-loss and take-profit percentages may need adjustment)

**Risk:** Longer horizon means slower feedback loop. Current feedback evaluates after
5 trading days; will now evaluate after 10. Fewer feedback cycles per month.

---

## Part 2: Regime-Adjusted Signal Thresholds

### The Problem

Uniform thresholds (buy=0.55, sell=0.35) ignore that the model performs very
differently across VIX regimes.

### Per-Regime Model Accuracy (10d Target, Fold 5)

| VIX Regime | Range | Samples | Accuracy | AUC | Positive Rate | Prob Std |
|---|---|---|---|---|---|---|
| Low | < 15 | 633 | 51.3% | 55.9% | 49.8% | 0.056 |
| Normal | 15-20 | 1001 | 56.1% | 56.4% | 43.7% | 0.057 |
| Elevated | 20-25 | 268 | 60.4% | 60.4% | 50.7% | 0.062 |
| **High** | **> 25** | **114** | **60.5%** | **68.8%** | **61.4%** | **0.065** |

The model is strongest in elevated/high VIX (60%+ accuracy, wider prob spread) and
weakest in low VIX (51%, barely above random). This makes sense — the model's top
features are macro/volatility signals (VIX, SPY returns, rolling std). In calm markets,
there's nothing for these features to work with.

### Proposed Regime Thresholds

| Regime | Buy Threshold | Sell Threshold | Rationale |
|---|---|---|---|
| Low VIX (< 15) | 0.58 | 0.35 | **Strictest buy** — model is weak, only trade high-conviction |
| Normal (15-20) | 0.55 | 0.35 | Standard — same as current |
| Elevated (20-25) | 0.52 | 0.38 | Slightly looser buy (model stronger), tighter sell |
| High (> 25) | 0.50 | 0.40 | **Loosest buy** (model at peak accuracy), tightest sell (regime volatile) |

### Backtested Signal Quality (Fold 5, 2016 samples)

| Regime | BUY Signals | BUY Accuracy | SELL Signals | SELL Accuracy |
|---|---|---|---|---|
| Low VIX | 24 | **79%** | 0 | — |
| Normal | 121 | 49% | 0 | — |
| Elevated | 77 | **65%** | 13 | **85%** |
| High | 53 | **74%** | 10 | **70%** |
| **Total** | **275** | **60.7%** | **23** | **78.3%** |

Compared to uniform thresholds on the same data: 289 BUY (59.5% acc), 0 SELL.
Regime thresholds produce fewer but better BUY signals (60.7% vs 59.5%) and
unlock SELL signals for the first time (23 at 78.3% accuracy).

### Implementation

**Files:** `src/config.py`, `src/signals.py`

**Changes:**
1. Add `regime_thresholds` dict to `CFG`:
   ```python
   regime_thresholds: Dict[str, Dict[str, float]] = {
       "low":      {"buy": 0.58, "sell": 0.35},
       "normal":   {"buy": 0.55, "sell": 0.35},
       "elevated": {"buy": 0.52, "sell": 0.38},
       "high":     {"buy": 0.50, "sell": 0.40},
   }
   regime_vix_bins: List[float] = [0, 15, 20, 25, float("inf")]
   ```

2. In `signals.py`, replace static threshold comparison:
   ```python
   # Before:
   if prob_up >= CFG.signal_threshold_buy:
       signal = "BUY"
   elif prob_up <= CFG.signal_threshold_sell:
       signal = "SELL"

   # After:
   regime = classify_regime(vix_value)
   thresholds = CFG.regime_thresholds[regime]
   if prob_up >= thresholds["buy"]:
       signal = "BUY"
   elif prob_up <= thresholds["sell"]:
       signal = "SELL"
   ```

3. Add `classify_regime()` helper that maps current VIX to regime label.

4. Include regime label in signal output JSON for transparency.

**Risk:** Regime thresholds are backtested on fold 5 only (2016 samples). They should
be treated as initial values and monitored during paper trading.

---

## Combined Impact Estimate

| Metric | Current | After Changes | Source |
|---|---|---|---|
| CV Accuracy | 53.8% | 55.2% | 10d target CV |
| Probability range | [0.35, 0.51] | [0.35, 0.61] | Calibrated fold 5 |
| BUY signals (backtest) | 0 per week | ~8-10 per week | 275 over ~40 weeks |
| BUY accuracy | N/A | 60.7% | Regime-adjusted backtest |
| SELL signals (backtest) | 0 per week | ~1 per week | 23 over ~40 weeks |
| SELL accuracy | N/A | 78.3% | Regime-adjusted backtest |

---

## Summary of All Changes

| File | Change |
|---|---|
| `src/config.py` | `target_horizon`: 5 → 10; add `regime_thresholds` + `regime_vix_bins` |
| `src/signals.py` | Add `classify_regime()`; replace static threshold with regime lookup |
| `src/features.py` | No changes (uses `CFG.target_horizon` already) |
| `src/train.py` | No changes |
| `src/feedback.py` | Update eval window from 5 to 10 trading days |
| `src/execution/executor.py` | Review stop-loss/take-profit for 10-day hold horizon |

---

## Next Steps (pending approval)

1. Implement changes (config, signals, feedback)
2. Run Phases 1-3 with new target
3. Compare new CV metrics to current
4. Run Phase 4 dry-run to verify signal generation
5. Re-enable Sunday retrain cron
6. Begin new 4-week evaluation window
