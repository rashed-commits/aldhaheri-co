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
