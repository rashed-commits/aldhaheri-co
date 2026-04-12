# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Monorepo for all aldhaheri.co services. SSO hub + four subdomain projects (finance, market, realestate, trade), deployed from one repo on a single DigitalOcean droplet. Single-user system (one username/password).

**Market Intel is shelved** — container serves a static "Coming Back Soon" page only. Scraper, API routes, and daily cron are disabled. Data volume (`market-data`) is preserved.

**No test suite or CI/CD pipeline exists.** No pytest, jest, or GitHub Actions.

## Commands

### Local backend dev
```bash
cd hub/backend && uvicorn main:app --reload --port 4001
cd finance/backend && uvicorn backend.main:app --reload --port 8000
cd market && python server.py
cd realestate/backend && uvicorn main:app --reload --port 8002
cd trade/api && uvicorn main:app --reload --port 8003
cd trade && python main.py --phase 1  # phases 1-5, add --dry-run for safe testing
```

### Local frontend dev
```bash
cd <project>/frontend && npm install && npm run dev
# Hub: localhost:4000, Finance: localhost:3000, Realestate: localhost:3002, Trade: localhost:3003
```

### Real Estate scraper pipeline
```bash
cd realestate && python main.py --skip-bayut       # Full pipeline
cd realestate && python main.py --pf-only --dry-run # Test scraper
cd realestate && python main.py --score-only        # Score existing data
cd realestate && python main.py --db-stats          # View DB stats
```

### Docker
```bash
docker compose up -d --build                     # Build all
docker compose up -d --build finance-backend     # Build single service
docker compose logs -f finance-backend           # View logs
docker compose ps                                # Status
```

### Lint (frontend only)
```bash
cd <project>/frontend && npx eslint .
# Hub, Realestate, Trade dashboard have ESLint configs
# Finance frontend has no ESLint config; no Python linters configured
```

### Deploy
```bash
bash deploy.sh   # Commits, pushes, SSHs to VPS, pulls, rebuilds
# WARNING: deploy.sh uses `git add .` — ensure .gitignore covers .env and sensitive files
```

## Tech Stack
- **Hub**: React 19 + Vite + Tailwind 4, FastAPI + python-jose (JWT)
- **Finance**: React 18 + Recharts + Tailwind 3, FastAPI + async SQLAlchemy + aiosqlite + Anthropic SDK
- **Market**: Flask + Vanilla JS — **shelved**, static page only
- **Real Estate**: React 18 + Vite + Recharts, FastAPI, Playwright + BeautifulSoup scrapers
- **Trade**: React 19 + Vite + Recharts, FastAPI, XGBoost + FinBERT sentiment, Alpaca SDK
- **Databases**: All SQLite (no Postgres). Trade uses JSON files instead of a DB.
- **Package managers**: npm (all frontends), pip + requirements.txt (all backends)

## Architecture

### Docker Compose structure
Root `docker-compose.yml` uses `include:` to merge per-project compose files. Hub services are defined directly in root. Each per-project compose file references `../.env` (the single root env file) and can be started independently. Frontend containers use multi-stage Docker builds (node → nginx) with per-project `nginx.conf` files for SPA routing (`try_files $uri $uri/ /index.html`). Finance frontend bakes `VITE_API_URL` and `VITE_API_KEY` as Docker build args — other frontends have no build-time env vars.

### Services (10 total)
| Service | Port | Health |
|---|---|---|
| hub-frontend / hub-backend | 4000 / 4001 | /health (backend) |
| finance-frontend / finance-backend | 3000 / 8001 (internal 8000) | /health (backend) |
| market-intel | 8000 | /health |
| realestate-frontend / realestate-backend | 3002 / 8002 | /health (backend) |
| trade-bot-dashboard / trade-bot-api / trade-bot / trade-bot-sentiment | 3003 / 8003 / none / none | /health (api), cron (bot, sentiment) |

### SSO / JWT Auth
- Hub backend creates JWT with `sub` + `sid`, sets `session` cookie on `.aldhaheri.co`
- All other services validate via shared `get_current_user()` dependency
- All frontends auto-redirect to `https://aldhaheri.co` on 401 (see each project's `api.js`)
- Cookie-only auth — no `?token=` URL parameter
- Cookie-based JWT: HS256, 8hr expiry, shared JWT_SECRET across all services

### Hub Login Flow
1. **WebAuthn/Passkey** (primary) — `hub/backend/routers/webauthn.py`
2. **Password + TOTP** — password returns `totp_pending` token → verify 6-digit code → `hub/backend/routers/totp.py`
3. **Password only** — fallback when TOTP not enabled
- Rate-limited: 5 attempts / 5 min, 15-min lockout (slowapi)

### Code patterns
- **Thin routes + service logic**: Routes in `/routers/` handle HTTP only; business logic in service files (`parser.py`, `notifications.py`, `session_store.py`, `sweep.py`)
- **Soft-delete everywhere**: All deletes set `deleted=True`, queries filter `WHERE deleted=False`
- **Async DB**: Finance and Hub use async SQLAlchemy + aiosqlite. Real Estate uses `?immutable=1`. Market uses sync sqlite3. Trade reads JSON files.
- **File placement**: New API routes → `<project>/backend/routers/`, new UI components → `<project>/frontend/src/components/`, DB models → `<project>/backend/models.py`
- **Lifted filter state**: Finance dashboard search is owned by `Dashboard` in `App.jsx` (not `RecentTransactions`). All filters — toggle pills, date range, and text search — feed into one `filteredTransactions` memo that drives charts, stat cards, summary, and the transaction table.
- **Dashboard charts** (top to bottom, 2-col grid): Monthly Inflow vs Outflow | Cumulative Inflow vs Outflow | Income by Category | Income by Merchant | Spend by Category | Spend by Merchant. Category and merchant pie charts share `CategoryPieChart.jsx`; clicking a slice opens `CategoryDrilldown` filtered by category or merchant.

### Data paths (inside containers)
- Finance DB: `/data/finance.db` (Docker volume `finance-data`), statements: `/data/statements` (separate volume `finance-statements`)
- Hub DB: `/data/` (Docker volume `hub-data`)
- Market DB: `/app/data/market_intel.db`
- Real Estate DB: `data/listings.db` (local bind mount `./data`, not a named volume)
- Trade: four named volumes — `trade-data`, `trade-model`, `trade-output`, `trade-logs`

### Container resources
- All frontends/backends: 512M memory, 0.5 CPU
- **Trade bot**: 2G memory, 1.0 CPU (FinBERT model needs ~500MB)
- Logging: `json-file` driver, 10MB max × 3 files per service

### Nginx (VPS reverse proxy)
Configs in `nginx/` directory, deployed to `/etc/nginx/sites-available/` on VPS. Each subdomain proxies to the corresponding Docker port. Finance is the only service without a repo-tracked nginx config (uses Docker port mapping directly).

## Finance Chatbot Architecture
- `POST /api/chat` rebuilds full DB context from scratch on **every message** (totals, categories, merchant/category search results, last 100 transactions) — the model always sees current data
- Claude Sonnet returns text + optional `<action>...</action>` JSON blocks (`modify`, `delete`, `add`)
- Frontend shows approval UI → user confirms → `POST /api/chat/execute` runs the action
- **Merchant search**: keywords trigger unlimited case-insensitive search across ALL transactions
- **Telegram chatbot** (`finance/backend/telegram_bot.py`): mirrors web chatbot via long-polling, auto-executes actions without approval

### Transaction category resolution (webhook.py)
**Transfers**: Always categorized as "Transfer" (temporary — user must manually recategorize). Confirmation SMS (`Confirmation recd. from ...`) is intercepted before parsing — it updates the original transfer's merchant with the recipient name and is not stored as a separate transaction. After saving a `TRANSFER` type, the system checks for a same-amount opposite-flow pair on the same day; if found, both are re-categorized as "Internal Transfers". Every non-internal transfer triggers a Telegram message prompting the user to categorize it.

**Cheques**: Auto-categorized — inflows become "Real Estate Income", outflows become "Real Estate Expenses" (both merchant and category).

**Refunds**: Merchant is always set to "Refund" regardless of the original merchant name.

**Balance monitoring**: After saving an Internal Transfer or Credit Card Payment, the system sums all inflows vs outflows for that category and sends a Telegram warning if they are imbalanced.

**Non-transfers/non-cheques**: Priority order: merchant history → keyword categorizer (`categorizer.py`, 443 rules) → Claude parser guess → Telegram help request

### Webhook ingestion guards (webhook.py)
Rejects: empty/short SMS, unresolved Tasker variables, failed/declined keywords, pending/uncleared transactions (e.g. "subject to verification", "pending clearance", "cheque will be processed"), exact duplicate SMS, zero-amount transactions, confirmation SMS (processed as merchant update, not new transaction). Cheque deposits are only recorded once a separate confirmation SMS arrives (pending cheque notifications are filtered out). After save, checks for suspected repeats (same merchant + amount + date) and alerts via Telegram.

## Trade Pipeline Phases
CLI-driven via `trade/main.py --phase N` (add `--dry-run` to skip real trades):
1. **Ingest**: OHLCV + market data from yfinance/Alpaca
2. **Features**: Technical indicators, fundamental ratios, analyst data, sector-relative strength, short interest, FinBERT sentiment
3. **Train**: XGBoost with feature pruning + Platt calibration → `model/saved/`
4. **Signals**: Daily buy/sell → `output/signals_YYYY-MM-DD.json` (fetches live sentiment for reasoning)
5. **Execute**: Reconcile positions against Alpaca (`reconcile_positions()`) + paper trade → `output/open_positions.json`

**Position reconciliation** (Phase 5): Before trading, `reconcile_positions()` syncs `open_positions.json` against Alpaca's actual positions to prevent drift from manual trades. Skipped in `--dry-run`. Fails safe — keeps local positions unchanged if Alpaca API fails. Uses reverse `alpaca_symbol_map` from `CFG` to translate Alpaca symbols back to yfinance tickers.

**Feature set (49 active after pruning)**: Technical indicators (RSI, MACD, Bollinger, ATR, OBV, volume z-score), rolling window stats, lagged returns, fundamental ratios (from yfinance quarterly financials), market regime (VIX, SPY), sector-relative strength (vs SPDR sector ETFs: XLK/XLC/XLY/XLF/XLV/XLE/XLP), sector one-hot encoding, analyst features (target gap from `upgrades_downgrades`, revision momentum), and short interest. Sector ETF mapping in `CFG.ticker_sector`. Dropped features: `f_current_ratio`, `f_operating_margin`, `macd_hist` (unstable across folds).

**FinBERT sentiment**: `src/sentiment.py` lazy-loads ProsusAI/finbert on first call. Container memory raised to 2G (model needs ~500MB RAM, CPU-only PyTorch). Sentiment accumulates in `data/sentiment.csv`; Phase 4 fetches live sentiment for signal reasoning. **Suspended from model training** (0.45% row coverage, 0.0 feature importance). Accumulation pipeline runs passively; reintroduce to model when coverage exceeds 30%. Controlled by `_SUSPENDED_FEATURES` list in `train.py`.

### Trade (VPS crontab, EDT timezone)
Phases 4+5 weekdays 10:00 AM / 2:00 PM UTC (6:00 AM / 10:00 AM EDT), Phases 1-3 Sunday 6:00 AM EDT (10:00 UTC). Phase 4 includes feedback loop evaluation of past predictions (directional accuracy only — HOLD signals excluded from scoring). Signal thresholds: buy=0.55, sell=0.35. Model uses Platt-calibrated XGBoost (CalibratedClassifierCV with TimeSeriesSplit, not StratifiedKFold). Drawdown circuit breaker halts new buys at 8% drawdown from peak OR 8% decline from inception equity — whichever triggers first.

### Market — DISABLED
Daily scraper cron removed from VPS on 2026-03-28.

## Investment Portfolio Tracker (Finance)
- `/investments` route in finance frontend
- `InvestmentPosition` table: ticker, shares, cost_per_share, entry_date, soft-delete
- USD/AED fixed rate 3.6725 (constant in `finance/backend/routers/investments.py`)
- yfinance prices with disk-persisted 5-min TTL cache (`/data/price_cache.json`), falls back to stale cache on error (only if cached price > 0)
- Portfolio API returns `prices_updated_at` (UAE time) — displayed next to USD/AED rate on frontend
- Partial close splits the lot — original keeps remaining shares, sold portion becomes closed trade
- Seed data: VOO positions (44 shares, 3 lots) auto-inserted on first startup if empty

## Scheduled Jobs

### Finance (APScheduler in `main.py` lifespan)
- **00:00 UTC**: Zero-amount transaction sweep (`sweep.py`)
- **10:00 UTC**: Telegram alert for unidentified transactions (`notifications.py`)
- **1st of month 09:00 UTC**: Statement reminder (`notifications.py`)

## Coding Conventions
- **Python**: PEP8, type hints, async handlers, APIRouter pattern
- **JavaScript**: Functional components, hooks, Tailwind utility classes
- No dead code or commented-out blocks

## UI & Design Rules
- Background: #0F0F1A | Card: #1A1A2E | Border: #2D2D4E
- Accent: #7C3AED (purple) | Accent light: #A78BFA
- Text: #F1F5F9 (primary) | #94A3B8 (muted)
- Success: #10B981 | Warning: #F59E0B | Danger: #EF4444
- Font: Inter / system-ui | Nav height: 56px
- Finance charts: Green (#34D399) = inflow, Red (#F87171) = outflow

## Safe-Change Rules
- Never modify JWT_SECRET — shared across all 10 containers
- Never commit `.env` files or raw bank statement CSVs (`Statements/` directory)
- Never remove or change any `/health` endpoint shape
- Never change finance webhook path (`/webhook/sms`) — Tasker depends on it
- Database migrations need explicit planning (SQLite, no auto-migrate)
- Backups at `/opt/backups/` on VPS — verify before destructive operations
- Finance SMS parser prompt changes require careful testing — wrong parsing silently corrupts data
- TOTP secret storage (`totp_secrets` table) — if corrupted, users get locked out of 2FA

## Environment Variables
All services read from the single root `.env` file. See `.env.example` for the full list. Key shared var: `JWT_SECRET` (used by ALL services). Each project section in `.env.example` documents its own vars.

Note: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are used independently by both Finance and Trade containers.

## Adding a New Project
1. Create `<project>/` directory with backend/frontend and its own `docker-compose.yml`
2. Add `include:` entry in root `docker-compose.yml`
3. Add env vars to root `.env` and `.env.example`
4. Add card to `hub/frontend/src/config/projects.js`
5. Add DNS A record pointing to 165.232.162.72
6. Create Nginx config at `/etc/nginx/sites-available/<subdomain>`
7. Run `certbot --nginx -d <subdomain>.aldhaheri.co`
8. Deploy: `docker compose up -d --build`

## API Endpoints
See `README.md` for the full API endpoint reference for all services. Every backend exposes `GET /health` (unauthenticated). All other `/api/*` endpoints require a valid session cookie.

## Legacy Artifacts
Per-project `.env.example` and `deploy.sh` in subdirectories are leftovers — use only the root versions. Per-project `CLAUDE.md` files in subdirectories contain supplementary context but may be outdated — this root file is authoritative. `trade/google_apps_script/` is a standalone Google Sheets script, not part of the pipeline. Note: `trade/CLAUDE.md` references `?token=` URL auth in the dashboard — this is outdated; all services now use cookie-only auth.

## VPS
- **IP**: 165.232.162.72 | **Repo**: `/opt/aldhaheri-co` | **Backups**: `/opt/backups/`
- Check status: `ssh root@165.232.162.72 "cd /opt/aldhaheri-co && docker compose ps"`
- **SSH access is available** — Claude Code can SSH into the VPS to manage crontab, restart containers, check logs, edit nginx configs, run deployments, and perform other server-side operations directly
