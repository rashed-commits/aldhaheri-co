# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Monorepo for all aldhaheri.co services. SSO hub + four subdomain projects (finance, market, realestate, trade), deployed from one repo on a single DigitalOcean droplet. Single-user system (one username/password).

**No test suite or CI/CD pipeline exists.** No pytest, jest, or GitHub Actions.

## Commands

### Local backend dev
```bash
cd hub/backend && uvicorn main:app --reload --port 4001
cd finance/backend && uvicorn backend.main:app --reload --port 8000
cd market && python server.py
cd realestate/backend && uvicorn main:app --reload --port 8002
cd trade/api && uvicorn main:app --reload --port 8003
cd trade && python main.py --phase 1  # phases 1-5
```

### Local frontend dev
```bash
cd <project>/frontend && npm install && npm run dev
# Hub: localhost:4000, Finance: localhost:3000, Realestate: localhost:3002, Trade: localhost:3003
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
```

## Tech Stack
- **Hub**: React 19 + Vite + Tailwind 4, FastAPI + python-jose (JWT)
- **Finance**: React 18 + Recharts + Tailwind 3, FastAPI + async SQLAlchemy + aiosqlite + Anthropic SDK
- **Market**: Flask + Vanilla JS, OpenAI GPT-4o-mini, Apify, Tavily
- **Real Estate**: React 18 + Vite + Recharts, FastAPI, Playwright + BeautifulSoup scrapers
- **Trade**: React 19 + Vite + Recharts, FastAPI, XGBoost + FinBERT sentiment, Alpaca SDK
- **Databases**: All SQLite (no Postgres). Trade uses JSON files instead of a DB.
- **Package managers**: npm (all frontends), pip + requirements.txt (all backends)

## Architecture

### Docker Compose structure
Root `docker-compose.yml` uses `include:` to merge per-project compose files. Hub services are defined directly in root. Each per-project compose file references `../.env` (the single root env file) and can be started independently.

### Services (10 total)
| Service | Port | Health |
|---|---|---|
| hub-frontend / hub-backend | 4000 / 4001 | /health (backend) |
| finance-frontend / finance-backend | 3000 / 8001 (internal 8000) | /health (backend) |
| market-intel | 8000 | /health |
| realestate-frontend / realestate-backend | 3002 / 8002 | /health (backend) |
| trade-bot-dashboard / trade-bot-api / trade-bot | 3003 / 8003 / none | /health (api), cron (bot) |

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

### Code patterns
- **Thin routes + service logic**: Routes in `/routers/` handle HTTP only; business logic in service files (`parser.py`, `notifications.py`, `session_store.py`)
- **Soft-delete everywhere**: All deletes set `deleted=True`, queries filter `WHERE deleted=False`
- **Async DB**: Finance and Hub use async SQLAlchemy + aiosqlite. Real Estate uses `?immutable=1`. Market uses sync sqlite3. Trade reads JSON files.

## Finance Chatbot Architecture
- `POST /api/chat` builds DB context (totals, categories, merchant/category search results, last 100 transactions)
- Claude Sonnet returns text + optional `<action>...</action>` JSON blocks (`modify`, `delete`, `add`)
- Frontend shows approval UI → user confirms → `POST /api/chat/execute` runs the action
- **Merchant search**: keywords trigger unlimited case-insensitive search across ALL transactions
- **Telegram chatbot** (`finance/backend/telegram_bot.py`): mirrors web chatbot via long-polling, auto-executes actions without approval

### Transaction category resolution (webhook.py)
Priority order: merchant history → keyword categorizer (`categorizer.py`, 443 rules) → Claude parser guess → Telegram help request

### Webhook ingestion guards (webhook.py)
Rejects: empty/short SMS, unresolved Tasker variables, failed/declined keywords, exact duplicate SMS, zero-amount transactions. After save, checks for suspected repeats (same merchant + amount + date) and alerts via Telegram.

## Trade Pipeline Phases
CLI-driven via `trade/main.py --phase N`:
1. **Ingest**: OHLCV + market data from yfinance/Alpaca
2. **Features**: Technical indicators, fundamental ratios, FinBERT sentiment
3. **Train**: XGBoost with feature pruning → `model/saved/`
4. **Signals**: Daily buy/sell → `output/signals_YYYY-MM-DD.json`
5. **Execute**: Reconcile + paper trade → `output/open_positions.json`

VPS cron: Phases 4+5 weekdays 9:25/9:35 AM ET, Phases 1-3 Sunday 6:00 AM.

## Investment Portfolio Tracker (Finance)
- `/investments` route in finance frontend
- `InvestmentPosition` table: ticker, shares, cost_per_share, entry_date, soft-delete
- USD/AED fixed rate 3.6725 (constant in `finance/backend/routers/investments.py`)
- yfinance prices with in-memory 5-min TTL cache, falls back to stale cache on error
- Partial close splits the lot — original keeps remaining shares, sold portion becomes closed trade
- Seed data: VOO positions (44 shares, 3 lots) auto-inserted on first startup if empty

## Scheduled Jobs (Finance)
APScheduler inside finance backend:
- **00:00 UTC**: Zero-amount transaction sweep
- **10:00 UTC**: Telegram alert for unidentified transactions
- **1st of month 09:00 UTC**: Statement reminder

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
Per-project `.env.example` and `deploy.sh` in subdirectories are leftovers — use only the root versions. Per-project `CLAUDE.md` files in subdirectories contain supplementary context but may be outdated — this root file is authoritative. `trade/google_apps_script/` is a standalone Google Sheets script, not part of the pipeline.

## VPS
- **IP**: 165.232.162.72 | **Repo**: `/opt/aldhaheri-co` | **Backups**: `/opt/backups/`
- Check status: `ssh root@165.232.162.72 "cd /opt/aldhaheri-co && docker compose ps"`
