# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Monorepo for all aldhaheri.co services. SSO hub + four subdomain projects (finance, market, realestate, trade), deployed from one repo on a single DigitalOcean droplet. Single-user system (one username/password).

**Market Intel is shelved** — container serves a static "Coming Back Soon" page only. Scraper, API routes, and daily cron are disabled. Data volume (`market-data`) is preserved.

**Trade Bot is discontinued (2026-05-15)** — only a static "Discontinued" page is served on `trade.aldhaheri.co` (single `trade-bot-shelved` nginx container on port 3003). All crons removed; `trade-bot`, `trade-bot-api`, `trade-bot-sentiment` containers removed; `trade-bot-dashboard` was replaced by the shelved nginx. The four trade volumes (`aldhaheri-co_trade-data`, `_trade-model`, `_trade-output`, `_trade-logs`) are **preserved on the VPS** for now (not mounted by any service) — kept on disk in case the project is revived. Code under `trade/` (main.py, src/, api/, dashboard/) is kept in the repo for reference but no longer built. Hub project card removed.

**No test suite or CI/CD pipeline exists.** No pytest, jest, or GitHub Actions.

## Commands

### Local backend dev
```bash
cd hub/backend && uvicorn main:app --reload --port 4001
cd finance/backend && uvicorn backend.main:app --reload --port 8000
cd market && python server.py
cd realestate/backend && uvicorn main:app --reload --port 8002
```

Trade bot pipeline commands are deprecated — the project is discontinued (see above).

### Local frontend dev
```bash
cd <project>/frontend && npm install && npm run dev
# Hub: localhost:4000, Finance: localhost:3000, Realestate: localhost:3002
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
- **Market**: Flask + Vanilla JS + Anthropic SDK (Claude Haiku) — **shelved**, static page only
- **Real Estate**: React 18 + Vite + Recharts, FastAPI, Playwright + BeautifulSoup scrapers
- **Trade**: **discontinued** — static nginx page only. Legacy code (React 19 + Vite, FastAPI, XGBoost + FinBERT + Alpaca SDK) preserved under `trade/` but no longer built.
- **Databases**: All SQLite (no Postgres).
- **Package managers**: npm (all frontends), pip + requirements.txt (all backends)

## Architecture

### Docker Compose structure
Root `docker-compose.yml` uses `include:` to merge per-project compose files. Hub services are defined directly in root. Each per-project compose file references `../.env` (the single root env file) and can be started independently. Frontend containers use multi-stage Docker builds (node → nginx) with per-project `nginx.conf` files for SPA routing (`try_files $uri $uri/ /index.html`). Finance frontend bakes `VITE_API_URL` and `VITE_API_KEY` as Docker build args — other frontends have no build-time env vars.

### Services (8 total)
| Service | Port | Health |
|---|---|---|
| hub-frontend / hub-backend | 4000 / 4001 | /health (backend) |
| finance-frontend / finance-backend | 3000 / 8001 (internal 8000) | /health (backend) |
| market-intel | 8000 | /health |
| realestate-frontend / realestate-backend | 3002 / 8002 | /health (backend) |
| trade-bot-shelved | 3003 | /health (returns shelved JSON) |

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
- **Async DB**: Finance and Hub use async SQLAlchemy + aiosqlite. Real Estate uses `?immutable=1`. Market uses sync sqlite3.
- **File placement**: New API routes → `<project>/backend/routers/`, new UI components → `<project>/frontend/src/components/`, DB models → `<project>/backend/models.py`
- **Lifted filter state**: Finance dashboard search is owned by `Dashboard` in `App.jsx` (not `RecentTransactions`). All filters — toggle pills, date range, and text search — feed into one `filteredTransactions` memo that drives charts, stat cards, summary, and the transaction table.
- **Dashboard charts** (top to bottom, 2-col grid): Monthly Inflow vs Outflow | Cumulative Inflow vs Outflow | Income by Category | Income by Merchant | Spend by Category | Spend by Merchant. Category and merchant pie charts share `CategoryPieChart.jsx`; clicking a slice opens `CategoryDrilldown` filtered by category or merchant.

### Data paths (inside containers)
- Finance DB: `/data/finance.db` (Docker volume `finance-data`), statements: `/data/statements` (separate volume `finance-statements`)
- Hub DB: `/data/` (Docker volume `hub-data`)
- Market DB: `/app/data/market_intel.db`
- Real Estate DB: `data/listings.db` (local bind mount `./data`, not a named volume)

### Container resources
- All frontends/backends: 512M memory, 0.5 CPU
- **trade-bot-shelved**: 128M memory, 0.25 CPU (static nginx only)
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

### Date normalization (webhook.py)
UAE bank SMS uses DD/MM/YYYY format. The webhook extracts dates via regex (`on DD/MM/YYYY`) and converts to MM/DD/YYYY before storage. For SMS without explicit dates, a future-date guard swaps DD/MM if the parsed date is after today (UAE time). The parser prompt also hints Claude to convert, but the regex is the reliable path.

### Account normalization (webhook.py)
Account variants like `XXX810002`, `XXX920001`, `XXX920002` are mapped to short forms (`810002`, `920001`, `920002`) via `account_map` dict after parsing. Add new mappings there when new account formats appear.

### Webhook ingestion guards (webhook.py)
Rejects: empty/short SMS, unresolved Tasker variables, failed/declined keywords, pending/uncleared transactions (e.g. "subject to verification", "pending clearance", "cheque will be processed"), exact duplicate SMS, zero-amount transactions, confirmation SMS (processed as merchant update, not new transaction). Cheque deposits are only recorded once a separate confirmation SMS arrives (pending cheque notifications are filtered out). After save, checks for suspected repeats (same merchant + amount + date) and alerts via Telegram.

## Trade Bot — DISCONTINUED (2026-05-15)
Pipeline, daily signals, paper trading, Telegram messaging, and weekly retrain were all cancelled on 2026-05-15. All trade crons removed from VPS crontab. The four data volumes (`aldhaheri-co_trade-data/-model/-output/-logs`) are preserved on the VPS (parked, unmounted) so the model, signal history, Finnhub cache, and sentiment accumulation can be recovered if the project is revived. Only a single `trade-bot-shelved` nginx container (port 3003) remains, serving a static "Discontinued" page at `trade.aldhaheri.co`. The Telegram bot tokens (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`) are kept in `.env` because Finance still uses them.

Source code (`trade/main.py`, `trade/src/`, `trade/api/`, `trade/dashboard/`) is preserved in-repo for reference but is not built by any compose file. Reviving the bot would require: refactoring `trade/docker-compose.yml` back to the four-service layout from git history, re-attaching the preserved volumes, re-adding cron lines on the VPS, re-adding the hub project card, and validating the (now-stale) model against current market state.

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

### Trade — DISCONTINUED
All trade cron entries removed from VPS crontab on 2026-05-15.

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
- Never modify JWT_SECRET — shared across all 11 containers
- Never commit `.env` files or raw bank statement CSVs (`Statements/` directory)
- Never remove or change any `/health` endpoint shape
- Never change finance webhook path (`/webhook/sms`) — Tasker depends on it
- Database migrations need explicit planning (SQLite, no auto-migrate)
- Backups at `/opt/backups/` on VPS — verify before destructive operations
- Finance SMS parser prompt changes require careful testing — wrong parsing silently corrupts data
- TOTP secret storage (`totp_secrets` table) — if corrupted, users get locked out of 2FA

## Environment Variables
All services read from the single root `.env` file. See `.env.example` for the full list. Key shared var: `JWT_SECRET` (used by ALL services). Each project section in `.env.example` documents its own vars.

**Telegram bots**: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are used by Finance (notifications, webhook alerts). Kept in `.env` even though Trade is discontinued. `TELEGRAM_CHATBOT_TOKEN` is a separate bot token used only by the Finance conversational chatbot (`telegram_bot.py`).

**Discontinued vars**: `FINNHUB_API_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` are no longer used by any running service (Trade was cancelled 2026-05-15). Safe to remove from `.env` but leaving them doesn't hurt.

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
See `README.md` for the full API endpoint reference for all services. Every backend exposes `GET /health` (unauthenticated). All other `/api/*` endpoints require a valid session cookie. Trade has no API endpoints — only the shelved page's `/health` is exposed at `trade.aldhaheri.co/health`.

## Legacy Artifacts
Per-project `.env.example` and `deploy.sh` in subdirectories are leftovers — use only the root versions. Per-project `CLAUDE.md` files in subdirectories contain supplementary context but may be outdated — this root file is authoritative. **`trade/CLAUDE.md`, `trade/main.py`, `trade/src/`, `trade/api/`, `trade/dashboard/`, `trade/google_apps_script/`** describe the discontinued pipeline and are no longer authoritative — kept as historical reference only.

## VPS
- **IP**: 165.232.162.72 | **Repo**: `/opt/aldhaheri-co` | **Backups**: `/opt/backups/`
- Check status: `ssh root@165.232.162.72 "cd /opt/aldhaheri-co && docker compose ps"`
- **SSH access is available** — Claude Code can SSH into the VPS to manage crontab, restart containers, check logs, edit nginx configs, run deployments, and perform other server-side operations directly
- **Initial provisioning**: `vps-setup.sh` clones the repo, installs nginx configs from `nginx/`, and runs certbot for SSL
