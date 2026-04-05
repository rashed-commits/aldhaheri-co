# Trade-Bot Project Guide

## Deployment

- **Droplet:** `root@165.232.162.72` at `/opt/trade-bot`
- **Docker:** `docker compose up --build -d` rebuilds and restarts the container
- **SSH key:** The droplet has an ED25519 deploy key added to GitHub (read-only). The remote must use SSH, not HTTPS.

### How to deploy

1. Commit and push from local:
   ```bash
   git add <files>
   git commit -m "message"
   git push origin main
   ```

2. SSH into droplet and pull + rebuild:
   ```bash
   ssh root@165.232.162.72 "cd /opt/trade-bot && git pull && docker compose up --build -d"
   ```

3. Verify:
   ```bash
   ssh root@165.232.162.72 "docker ps --filter name=trade-bot"
   ```

**Important:** After adding the deploy key, the droplet git remote must be switched to SSH:
```bash
ssh root@165.232.162.72 "cd /opt/trade-bot && git remote set-url origin git@github.com:rashed-commits/trade-bot.git"
```
This only needs to be done once. If `git pull` fails with "could not read Username", the remote is still HTTPS — run the command above.

There is a `deploy.sh` script but it runs `git add -A` which can include unwanted files. Prefer manual commit + deploy steps above.

## Cron Schedule (on droplet, ET timezone)

- **9:25 AM Mon-Fri:** Phase 4 — signal generation
- **9:35 AM Mon-Fri:** Phase 5 — trade execution
- **6:00 AM Sunday:** Full retrain (phases 1-3)

## Telegram

Bot token and chat ID are in `.env` on both local and droplet. Do NOT change these values — they point to the trade-bot's Telegram channel.

## Project Structure

- `main.py` — CLI entry point (`--phase 1-5`, `--dry-run`)
- `src/config.py` — All config (CFG singleton)
- `src/ingest.py` — Phase 1: download OHLCV + VIX/SPY market data
- `src/features.py` — Phase 2: technical indicators + fundamental ratios + market regime features
- `src/train.py` — Phase 3: XGBoost training with feature pruning
- `src/signals.py` — Phase 4: daily signal generation
- `src/execution/executor.py` — Phase 5: Alpaca paper trading
- `src/execution/alpaca.py` — Alpaca SDK wrapper
- `src/notifications.py` — Telegram notifications
- `src/feedback.py` — Prediction accuracy feedback loop (evaluates 5-day forward returns)

## Dashboard & API Layer

The project includes a React dashboard and FastAPI backend for viewing portfolio data via the aldhaheri.co SSO system.

### API (`api/`)

- `api/main.py` — FastAPI app with CORS, health endpoint
- `api/routers/portfolio.py` — Portfolio data endpoints (summary, positions, signals, model metrics, feature importances)
- `api/routers/auth.py` — JWT Bearer token verification middleware (HS256, `JWT_SECRET` env var)
- `api/Dockerfile` — Standalone container, port 8003
- `api/requirements.txt` — Python dependencies (fastapi, uvicorn, python-jose, etc.)

API reads from `output/` and `model/saved/` directories (mounted read-only). It tries Alpaca API first for live data, falls back to local JSON files.

**Endpoints:**
- `GET /health` — No auth, returns `{"status": "ok", "service": "trade-bot"}`
- `GET /api/portfolio/summary` — Equity, P&L, position count
- `GET /api/portfolio/positions` — Open positions with current prices
- `GET /api/portfolio/signals` — Last 30 days of signals
- `GET /api/portfolio/signals/latest` — Most recent signal file
- `GET /api/portfolio/performance` — Model metrics (accuracy, ROC-AUC, F1)
- `GET /api/portfolio/features` — Top 15 feature importances

### Dashboard (`dashboard/`)

- React + Vite + Tailwind CSS app
- Port 3003 (dev and production)
- SSO: reads `?token=` param or `localStorage`, redirects to `https://aldhaheri.co` if missing
- Components: Header, PortfolioSummary, PositionsTable, SignalsPanel, ModelMetrics, FeatureChart (Recharts)
- `dashboard/Dockerfile` — Multi-stage build (node:20-alpine -> nginx:alpine)

### Docker Services

Four containers in `docker-compose.yml`:
1. `trade-bot` — ML pipeline (no ports, cron-driven, no FinBERT)
2. `trade-bot-sentiment` — FinBERT sentiment worker (cron-driven, writes to sentiment.csv on shared volume)
3. `trade-bot-api` — FastAPI on port 8003
4. `trade-bot-dashboard` ��� Nginx on port 3003

### Environment Variables

`JWT_SECRET` is required in `.env` for SSO token verification (must match aldhaheri.co).

## Position Reconciliation (Phase 5)

Added 2026-03-18. Phase 5 now reconciles `open_positions.json` against Alpaca's actual positions before any trading logic runs. This prevents the local file from drifting when positions are manually opened/closed on Alpaca.

- `reconcile_positions()` in `src/execution/executor.py` — fetches all Alpaca positions via `api.list_positions()`, diffs against local file
- `list_positions()` in `src/execution/alpaca.py` — wraps `TradingClient.get_all_positions()`
- Runs after loading positions from disk (step 4b), before stop-loss/take-profit checks (step 5)
- Skipped in `--dry-run` mode
- Uses reverse `alpaca_symbol_map` from `CFG` to translate Alpaca symbols (e.g. `BRK.B`) back to yfinance tickers (`BRK-B`)
- Logs all changes with `RECONCILE:` prefix
- Fails safe: if Alpaca API call fails, keeps local positions unchanged

## FinBERT Sentiment Feature

Added 2026-03-15. Scores yfinance news headlines with ProsusAI/finbert. Three features: `sentiment_positive_score`, `sentiment_negative_score`, `sentiment_net_score`.

- `src/sentiment.py` — FinBERT scoring module (lazy-loads model on first call)
- Sentiment accumulates in `data/sentiment.csv` (Phase 1 merges new data with history)
- Phase 4 fetches live sentiment for signal reasoning display
- Container memory raised to 2G (FinBERT needs ~500MB), CPU-only PyTorch
- **Suspended from model training** as of 2026-04-05: 0.45% row coverage in features.csv, 0.0 feature importance. Three sentiment columns excluded via `_SUSPENDED_FEATURES` in `train.py`. Reintroduce when coverage exceeds 30% of training rows.
- **Isolated from main pipeline** as of 2026-04-05: FinBERT runs in its own container (`trade-bot-sentiment`) via `sentiment_cron.py`. Writes to `data/sentiment.csv` on the shared `trade-data` volume. Main pipeline (Phases 1-5) never imports `transformers` or `torch` — reads sentiment.csv as a flat file. This prevents FinBERT (~500MB) from OOM-killing the main pipeline.

## Scheduled Checkpoints

### March 22, 2026 — First retrain with expanded universe
- Automatic (Sunday cron). No action needed unless errors in logs.
- Check: `docker exec trade-bot cat model/saved/metrics.json`

### March 29, 2026 — Early warning check (COMPLETED)
**Result:** Accuracy 54.14% ± 2.62% — PASS (above 52%). However three blocking issues found and fixed:
1. **Feedback broken:** yfinance 1.2.0 MultiIndex columns caused `_get_actual_return()` to silently fail. Fixed by flattening columns.
2. **Zero trades:** Buy threshold 0.65 was unreachable for a 54% model. Lowered to 0.55 (sell to 0.35).
3. **Uncalibrated probabilities:** Added Platt scaling (`CalibratedClassifierCV`) to `train.py` so probabilities map to real likelihoods.
4. **Sentiment:** 41 rows (March 16-22), still pruned. Working correctly but only updates weekly (Phase 1). Coverage will grow naturally.
5. **Cron timing:** Retrain runs 6:00 AM EDT (not UTC) — `0 6 * * 0` on an EDT system = 10:00 UTC.

### April 5, 2026 — System health check (FAILED — model not viable)
**Result:** Zero trades in 33 days. Model not viable. April 12 review suspended.

**Root causes identified and fixed:**
1. **Platt calibration used StratifiedKFold** — `CalibratedClassifierCV(cv=5)` defaults to StratifiedKFold, which leaks future data into calibration. One of 5 sigmoid calibrators had inverted parameters (negative `a`), crushing prediction variance to std=0.03. All predictions compressed to 0.33–0.54 on training data. On live data with feature distribution shift, predictions skewed to 0.06–0.16 (all SELL). **Fixed:** replaced with `cv=TimeSeriesSplit(n_splits=5)`.
2. **HOLD inflation in feedback** — HOLD signals were scored as always correct, inflating accuracy. Corrected directional accuracy (BUY+SELL only): 80%→80%→60%→40%→40% (declining). **Fixed:** feedback now tracks `directional_accuracy` separately.
3. **Circuit breaker blind to inception drawdown** — only tracked peak-to-trough. Portfolio bled $26K from inception without triggering. **Fixed:** added inception-to-current check at same 8% threshold.
4. **FinBERT features dead weight** — 0.45% row coverage, 0.0 importance, 3 wasted features. **Fixed:** suspended from training via `_SUSPENDED_FEATURES` list. Accumulation pipeline continues; reintroduce at >30% coverage.
5. **No per-fold importance tracking** — could not diagnose temporal degradation. **Fixed:** `cross_validate()` now saves `fold_importances.json`.

**Feature audit results (42 features, sentiment excluded):**
- Overfitting candidates (high early, low late): `f_profit_margin`, `f_gross_margin`, `macd_hist`
- Improving features (gaining importance over time): `spy_return_20d/50d`, `f_revenue_growth_yoy/qoq`, `vix_above_avg`, `f_debt_to_assets`
- Fold 4 anomaly: accuracy dropped to 47.3% (below random). Investigate data quality in that time window.

**Next steps:** Fixes deployed and retrained same day. Model producing valid signals (25% SELL, 75% HOLD, 0% BUY). FinBERT isolated into separate container.

### April 11, 2026 — Threshold evaluation checkpoint
If no BUY signals have appeared by EOD April 11, lower `signal_threshold_buy` from 0.55 to 0.50. This is a live change, not evaluation-only. Report the first trading day's signal distribution at the new threshold. Temporary — reviewed at the April 13 retrain.

### May 3, 2026 — Full go/no-go review (RESCHEDULED from Apr 12)
Paper trading period effectively restarted on 2026-04-05 (prior 33 days used broken calibration). Clock reset — 4-week evaluation window: Apr 7 – May 2.

Review criteria:
1. **Out-of-sample directional accuracy** > 55% (from feedback_history.json, HOLD excluded)
2. **Number of directional trades** > 20 (BUY + SELL actions, in the Apr 7 – May 2 window)
3. **Max drawdown** < 12%
4. **Average return per trade** > 0.5%
5. **Win rate** > 50%
6. **Sentiment stats:** Total non-zero sentiment rows, whether features survived pruning, per-ticker coverage
7. **Week-by-week accuracy trend** — flat/declining after week 2 = serious
8. **Fold variance:** Compare `fold_importances.json` across retrains
9. **0.55 threshold analysis:** Did it filter good or bad trades?

**No-go triggers (any one = fail):** directional accuracy < 50%, drawdown > 15%, or < 20 directional trades in 4 weeks.
