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
- `src/feedback.py` — Prediction accuracy feedback loop

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

Three containers in `docker-compose.yml`:
1. `trade-bot` — ML pipeline (no ports, cron-driven)
2. `trade-bot-api` — FastAPI on port 8003
3. `trade-bot-dashboard` — Nginx on port 3003

### Environment Variables

`JWT_SECRET` is required in `.env` for SSO token verification (must match aldhaheri.co).

## FinBERT Sentiment Feature

Added 2026-03-15. Scores yfinance news headlines with ProsusAI/finbert. Three features: `sentiment_positive_score`, `sentiment_negative_score`, `sentiment_net_score`.

- `src/sentiment.py` — FinBERT scoring module (lazy-loads model on first call)
- Sentiment accumulates in `data/sentiment.csv` (Phase 1 merges new data with history)
- Phase 4 fetches live sentiment for signal reasoning display
- Container memory raised to 2G (FinBERT needs ~500MB), CPU-only PyTorch
- Cold-start: all 3 features were pruned at first retrain (0.12% non-zero rows). Will gain value as data accumulates.

**LLY watch:** Only ticker with meaningfully negative sentiment (-0.353) at launch. Monitor its paper trading performance — if it consistently underperforms, sentiment may be a contributing factor.

## Scheduled Checkpoints

### March 22, 2026 — First retrain with expanded universe
- Automatic (Sunday cron). No action needed unless errors in logs.
- Check: `docker exec trade-bot cat model/saved/metrics.json`

### March 29, 2026 — Early warning check
After the Sunday retrain completes, review:
1. **Accuracy check:** If CV accuracy < 52%, flag immediately — do not wait for April 12.
2. **Sentiment coverage:** How many rows in `data/sentiment.csv`? Are sentiment features still pruned? Report coverage growth vs. March 15 baseline (41 rows).
3. **Feedback loop:** Check `output/feedback_history.json` for real out-of-sample accuracy so far.
4. **LLY performance:** Any trades executed on LLY? P&L?
```bash
docker exec trade-bot python -c "
import json, pandas as pd
# Metrics
with open('model/saved/metrics.json') as f: m = json.load(f)
print('Accuracy:', round(m['accuracy']['mean'], 4))
print('ROC-AUC:', round(m['roc_auc']['mean'], 4))
# Sentiment coverage
df = pd.read_csv('data/sentiment.csv')
print('Sentiment rows:', len(df))
print('Tickers with data:', df['ticker'].nunique())
# Feature names
with open('model/saved/feature_names.json') as f: fn = json.load(f)
print('Sentiment in model:', any('sentiment' in f for f in fn))
"
```

### April 12, 2026 — Full go/no-go review
Run comprehensive review against all criteria:
1. **Out-of-sample accuracy** > 55% (from feedback_history.json)
2. **Number of trades** > 20
3. **Max drawdown** < 12%
4. **Average return per trade** > 0.5%
5. **Win rate** > 50%
6. **Sentiment stats:** Total non-zero sentiment rows, whether features survived pruning, per-ticker coverage
7. **Week-by-week accuracy trend** across all 4 retrains (flat/declining after week 2 = serious)
8. **Fold variance:** Did ticker expansion narrow variance?
9. **0.65 threshold analysis:** Did it filter good or bad trades?

**No-go triggers (any one = fail):** accuracy < 50%, drawdown > 15%, or < 15 trades in 4 weeks.
