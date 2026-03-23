# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 1. Project Overview
Monorepo for all aldhaheri.co services. Contains the SSO hub and four subdomain projects, all deployed from a single repo on one DigitalOcean droplet. Single-user system (one username/password).

## 2. Tech Stack
- **Hub**: React 19 + Vite + Tailwind 4, FastAPI + python-jose (JWT)
- **Finance**: React 18 + Recharts + Tailwind 3, FastAPI + async SQLAlchemy + aiosqlite + Anthropic SDK
- **Market**: Flask + Vanilla JS, OpenAI GPT-4o-mini, Apify, Tavily
- **Real Estate**: React 18 + Vite + Recharts, FastAPI, Playwright + BeautifulSoup scrapers
- **Trade**: React 19 + Vite + Recharts, FastAPI, XGBoost + FinBERT sentiment, Alpaca SDK
- **Auth**: Cookie-based JWT (HS256, 8hr expiry), shared JWT_SECRET across all services
- **Infra**: Docker Compose, Nginx + Certbot, DigitalOcean Ubuntu droplet
- **Databases**: All SQLite (no Postgres). Trade uses JSON files instead of a DB.
- **Package managers**: npm (all frontends), pip + requirements.txt (all backends)
- **No test suite or CI/CD pipeline exists.** No pytest, jest, or GitHub Actions.

## 3. Architecture

### Monorepo structure
```
aldhaheri_co/
  hub/                    # SSO login + project dashboard
    backend/              # FastAPI (port 4001)
    frontend/             # React Vite (port 4000)
  finance/                # SMS-based bank transaction tracker
    backend/              # FastAPI (port 8001→8000 internal)
    frontend/             # React Vite (port 3000→80 internal)
    docker-compose.yml    # Per-project compose
  market/                 # UAE business signal intelligence
    server.py             # Flask (port 8000)
    scraper.py            # Apify/Tavily pipeline
    static/               # Vanilla JS frontend
    docker-compose.yml
  realestate/             # Property analytics + scoring
    backend/              # FastAPI (port 8002)
    frontend/             # React Vite (port 3002)
    scrapers/             # PropertyFinder + Bayut
    docker-compose.yml
  trade/                  # ML trading bot + dashboard
    main.py               # CLI orchestrator (phases 1-5)
    src/                  # XGBoost pipeline (cron-driven, no port)
    api/                  # FastAPI (port 8003)
    dashboard/            # React Vite (port 3003)
    docker-compose.yml
  docker-compose.yml      # Root: hub services + include: per-project files
  .env                    # Single env file for ALL services
  deploy.sh               # Git push + VPS pull + rebuild
  vps-setup.sh            # Initial VPS provisioning script
  nginx/                  # Nginx site configs
```

### Docker Compose structure
The root `docker-compose.yml` uses `include:` to merge per-project compose files:
```yaml
include:
  - path: ./finance/docker-compose.yml
  - path: ./market/docker-compose.yml
  - path: ./realestate/docker-compose.yml
  - path: ./trade/docker-compose.yml
```
Hub services (hub-frontend, hub-backend) are defined directly in the root file.

Each per-project compose file:
- Defines its own services and named volumes
- References `../.env` (the single root env file)
- Can be started independently: `docker compose up finance-backend`

### Services (10 total)
| Service | Container | Port | Health |
|---|---|---|---|
| Hub Frontend | hub-frontend | 4000 | — |
| Hub Backend | hub-backend | 4001 | /health |
| Finance Backend | finance-backend | 8001 | /health |
| Finance Frontend | finance-frontend | 3000 | — |
| Market Intel | market-intel | 8000 | /health |
| Realestate Backend | realestate-backend | 8002 | /health |
| Realestate Frontend | realestate-frontend | 3002 | — |
| Trade Bot | trade-bot | none | cron-driven |
| Trade Bot API | trade-bot-api | 8003 | /health |
| Trade Bot Dashboard | trade-bot-dashboard | 3003 | — |

## 4. Commands

### Local backend dev
```bash
# Hub
cd hub/backend && uvicorn main:app --reload --port 4001

# Finance
cd finance/backend && uvicorn backend.main:app --reload --port 8000

# Market
cd market && python server.py

# Real Estate
cd realestate/backend && uvicorn main:app --reload --port 8002

# Trade API
cd trade/api && uvicorn main:app --reload --port 8003

# Trade pipeline (phases 1-5)
cd trade && python main.py --phase 1  # or 2,3,4,5
```

### Local frontend dev
```bash
# All frontends follow the same pattern
cd <project>/frontend && npm install && npm run dev
# Hub: localhost:4000, Finance: localhost:3000, Realestate: localhost:3002, Trade: localhost:3003
```

### Docker
```bash
docker compose up -d --build              # Build all
docker compose up -d --build finance-backend  # Build single service
docker compose logs -f finance-backend     # View logs
docker compose ps                          # Status
```

### Lint (frontend only)
```bash
# Hub, Realestate, Trade dashboard have ESLint configs
cd <project>/frontend && npx eslint .
# Finance frontend has no ESLint config
# No Python linter tooling is configured
```

### Deploy
```bash
bash deploy.sh   # Auto-commits (git add . + generic message), pushes, SSHs to VPS, pulls, rebuilds
```

### VPS
```bash
ssh root@165.232.162.72 "cd /opt/aldhaheri-co && docker compose ps"
```

## 5. Key Architectural Patterns

### SSO / JWT Auth
- Hub backend creates JWT with `sub` (username) + `sid` (session ID), sets `session` cookie on `.aldhaheri.co`
- All other services validate the cookie with a shared `get_current_user()` dependency
- All frontends auto-redirect to `https://aldhaheri.co` on 401 (see each project's `api.js`)
- No `?token=` URL parameter — cookie-only auth

### Hub Login Flow (multi-method)
1. **WebAuthn/Passkey** (primary) — passwordless via `hub/backend/routers/webauthn.py`
2. **Password + TOTP** — if TOTP is enabled, password returns a `totp_pending` token; user must then verify a 6-digit code from Microsoft Authenticator
3. **Password only** — fallback when TOTP is not enabled
- TOTP setup/verify/disable endpoints in `hub/backend/routers/totp.py` (uses `pyotp` + `qrcode`)
- TOTP secrets stored in `totp_secrets` table in hub's auth SQLite DB
- Frontend settings page (`hub/frontend/src/pages/Settings.jsx`) provides QR code setup UI

### Thin routes + service logic
- Routes in `/routers/` handle validation and HTTP concerns only
- Business logic lives in service files (`parser.py`, `notifications.py`, `session_store.py`)

### Soft-delete pattern
All deletes set `deleted=True`, never hard-delete. Queries filter `WHERE deleted=False`.

### Async database access
Finance and Hub use async SQLAlchemy with aiosqlite. Real Estate uses read-only immutable SQLite (`?immutable=1`). Market uses sync SQLite3. Trade has no database — reads JSON files from the pipeline output.

### Frontend auth pattern (all React apps)
```javascript
// api.js — every project wraps fetch with auth check
if (res.status === 401) window.location.href = 'https://aldhaheri.co'
```

## 6. Finance Chatbot Architecture
- `POST /api/chat` → builds DB context (totals, categories, full merchant/category search results, last 100 transactions)
- Claude Sonnet processes message + context, returns text + optional `<action>...</action>` JSON blocks
- Actions: `modify` (update fields), `delete` (soft-delete), `add` (create transaction)
- Frontend shows approval UI → user confirms → `POST /api/chat/execute` runs the action
- **Full merchant search**: keywords from user message trigger unlimited case-insensitive search across ALL transactions — no caps, no early termination
- **Category search**: matched categories pull all transactions (no limit)
- **Amount search**: exact-match on `value_aed`, up to 10 per amount
- All search results include id, date, account, amount, merchant, category, flow_type for direct action
- **Telegram chatbot** (`finance/backend/telegram_bot.py`): mirrors the web chatbot via long-polling with a separate bot token (`TELEGRAM_CHATBOT_TOKEN`). Auto-executes actions without approval step. `/clear` or `/reset` to reset conversation. Maintains per-chat conversation history in memory (capped at 20 messages).

### Statement Import (`finance/backend/routers/statements.py`)
- `POST /api/statements/upload` — Upload a bank/credit card CSV, detect format, find missing transactions, optionally import
- `POST /api/statements/import-all` — Batch import from all CSVs in `/data/statements/` on the container
- `POST /api/statements/wipe-sheets-import` — Soft-delete all transactions previously imported from Google Sheets
- Supporting files: `statement_parser.py` (CSV format detection + parsing), `migrate_statements.py`

### Transaction category resolution (webhook.py)
When a new SMS transaction arrives, category is resolved in priority order:
1. **Merchant history** — most common category from previous transactions for the same merchant
2. **Keyword categorizer** (`categorizer.py`) — 443-rule static lookup table
3. **Claude parser guess** — from SMS parsing
4. **Telegram help request** — if still Other/Unidentified/Unknown, sends a message asking the user

### Webhook ingestion guards (webhook.py)
Before saving a transaction, the webhook rejects:
- Empty/short SMS, unresolved Tasker variables, failed/declined keywords
- **Exact duplicate SMS** — same `sms_raw` text as an existing non-deleted transaction
- **Zero-amount transactions** — both `amount` and `value_aed` are zero

After saving, the webhook checks for **suspected repeat transactions** (same merchant + same amount + same date as an existing transaction) and sends a Telegram alert asking the user to confirm or delete the duplicate.

## 7. Trade Pipeline Phases
CLI-driven via `trade/main.py --phase N`:
1. **Ingest**: OHLCV + market data from yfinance/Alpaca
2. **Features**: Technical indicators, fundamental ratios, FinBERT sentiment scores
3. **Train**: XGBoost with feature pruning, saves model + metrics to `model/saved/`
4. **Signals**: Daily buy/sell signal generation → `output/signals_YYYY-MM-DD.json`
5. **Execute**: Reconcile positions against Alpaca, then paper trade → `output/open_positions.json`

VPS cron: Phases 4+5 weekdays 9:25/9:35 AM ET, Phases 1-3 Sunday 6:00 AM.

## 8. Scheduled Jobs (Finance)
APScheduler runs inside the finance backend process:
- **00:00 UTC**: Soft-delete zero-amount transactions (sweep)
- **10:00 UTC**: Telegram alert if unidentified transactions exist
- **1st of month 09:00 UTC**: Statement reminder notification
- **Manual**: `POST /api/sweep` — trigger zero-amount sweep on demand

## 9. Coding Conventions
- **Python**: PEP8, type hints, async handlers, APIRouter pattern, thin routes + service logic
- **JavaScript**: Functional components, hooks, Tailwind utility classes
- No dead code or commented-out blocks

## 10. UI & Design Rules
- Background: #0F0F1A | Card: #1A1A2E | Border: #2D2D4E
- Accent: #7C3AED (purple) | Accent light: #A78BFA
- Text: #F1F5F9 (primary) | #94A3B8 (muted)
- Success: #10B981 | Warning: #F59E0B | Danger: #EF4444
- Font: Inter / system-ui
- Nav height: 56px across all projects

## 11. Environment Variables
All services read from the single root `.env` file. Each service only uses the vars it needs.

```
# Shared
JWT_SECRET              — SSO signing secret (ALL services)

# Hub
HUB_USERNAME            — Login username
HUB_PASSWORD            — Login password
VITE_API_URL            — Hub frontend API base URL
AUTH_DB_PATH            — Hub auth SQLite path (default: /data/auth.db)

# Finance
ANTHROPIC_API_KEY       — Claude API for SMS parsing + chatbot
WEBHOOK_API_KEY         — Tasker webhook + API auth
DASHBOARD_USERNAME      — Finance dashboard login
DASHBOARD_PASSWORD      — Finance dashboard password
FINANCE_VITE_API_URL    — Finance frontend API base URL
TELEGRAM_BOT_TOKEN      — Finance transaction notifications
TELEGRAM_CHATBOT_TOKEN  — Finance Telegram chatbot (separate bot, same chat)
TELEGRAM_CHAT_ID        — Finance Telegram chat target

# Market
OPENAI_API_KEY          — GPT-4o-mini for signal classification
PORT                    — Server port (8000)
DATABASE_PATH           — SQLite path (/app/data/market_intel.db)

# Real Estate
BREVO_API_KEY           — Email report delivery
SENDER_EMAIL            — Report sender address
REPORT_RECIPIENT        — Report recipient email

# Trade
ALPACA_API_KEY          — Paper trading API key
ALPACA_SECRET_KEY       — Paper trading secret
ALPACA_BASE_URL         — Alpaca API endpoint
TELEGRAM_BOT_TOKEN      — Trade pipeline notifications (shared var name with Finance, independent usage)
TELEGRAM_CHAT_ID        — Trade Telegram chat target

# Market (additional)
SCRAPE_MAX_ITEMS_PER_SOURCE — Max items per scraping source (default: 20)
```

## 12. Adding a New Project
1. Create `<project>/` directory with backend/frontend
2. Add `<project>/docker-compose.yml` referencing `../.env`
3. Add `include:` entry in root `docker-compose.yml`
4. Add env vars to root `.env` and `.env.example`
5. Add entry to `hub/frontend/src/config/projects.js`
6. Set up subdomain DNS (A record → 165.232.162.72)
7. Create Nginx config at `/etc/nginx/sites-available/<subdomain>`
8. Run `certbot --nginx -d <subdomain>`
9. Deploy with `docker compose up -d --build`

## 13. Safe-Change Rules
- Never modify JWT_SECRET — it's shared across all 10 containers
- Never commit `.env` files or raw bank statement CSVs (`Statements/` directory)
- Never remove or change any `/health` endpoint shape
- Never change finance webhook path (`/webhook/sms`) — Tasker depends on it
- Database migrations need explicit planning (SQLite, no auto-migrate)
- Backups at `/opt/backups/` on VPS — verify before destructive operations
- Finance SMS parser prompt changes require careful testing — wrong parsing silently corrupts data
- TOTP secret storage (`totp_secrets` table) — if corrupted, users get locked out of 2FA

## 14. VPS Details
- **IP**: 165.232.162.72
- **Repo**: `/opt/aldhaheri-co`
- **Backups**: `/opt/backups/`
- **Cron jobs**: trade-bot phases 4+5 weekdays, phases 1-3 Sunday, market-intel scraper daily

## 15. Legacy Artifacts
Per-project `.env.example` and `deploy.sh` files exist in some subdirectories (finance, market, realestate, trade) — these are leftovers from when each was a standalone repo. The root `.env.example` and root `deploy.sh` are the canonical ones. Do not use the per-project versions.

`trade/google_apps_script/` contains a Google Sheets analytics dashboard script (not part of the main pipeline).

## 16. API Endpoints Quick Reference

All `/api/*` endpoints require a valid session cookie unless noted. Every backend exposes `GET /health` (unauthenticated).

### Hub
- `POST /api/auth/login` — Password login (no auth)
- `GET /api/auth/verify` — Verify session
- `POST /api/auth/logout` — Revoke session (no auth)
- `POST /api/auth/webauthn/{register,login}/{begin,complete}` — Passkey flow
- `GET /api/totp/status`, `POST /api/totp/{setup,verify,disable}` — TOTP management
- `POST /api/auth/totp/verify` — TOTP during login (no auth)

### Finance
- `POST /webhook/sms` — Receive SMS (X-API-Key auth, not session)
- `GET /api/transactions` — List (paginated, session or X-API-Key)
- `GET /api/transactions/summary` — Spending summary
- `PATCH /api/transactions/{id}` — Update fields
- `DELETE /api/transactions/{id}` — Soft delete
- `POST /api/chat` — AI chatbot query
- `POST /api/chat/execute` — Execute chatbot action
- `POST /api/statements/upload` — Upload bank CSV
- `POST /api/statements/import-all` — Batch import from `/data/statements/`
- `POST /api/statements/wipe-sheets-import` — Soft-delete Google Sheets imports
- `POST /api/sweep` — Manual zero-amount cleanup

### Market
- `GET /api?action=all|stats|sector&sector=X|search&q=X`

### Real Estate
- `GET /api/listings` — Listings with filters (city, area, purpose, type)
- `GET /api/listings/{id}` — Single listing with area benchmark
- `GET /api/listings/{id}/history` — Price history
- `GET /api/areas` — Area benchmarks
- `GET /api/stats` — Database statistics

### Trade
- `GET /api/portfolio/summary` — Equity, P&L, position count
- `GET /api/portfolio/positions` — Open positions
- `GET /api/portfolio/signals` — Last 30 days of signals
- `GET /api/portfolio/signals/latest` — Most recent signal file
- `GET /api/portfolio/performance` — Model metrics
- `GET /api/portfolio/features` — Top 15 feature importances

## 17. External Integration: Tasker (Finance SMS)
Android Tasker is configured to forward bank SMS to the finance webhook:
- **Trigger**: Event > Phone > Received SMS
- **URL**: `https://finance.aldhaheri.co/webhook/sms`
- **Method**: POST, **Headers**: `Content-Type: application/json`, `X-API-Key: <WEBHOOK_API_KEY>`
- **Body**: `{"sms": "%SMSRB"}`

## 18. DNS Setup
All subdomains point to the same VPS IP via A records:

| Record | Value |
|---|---|
| `@`, `www`, `finance`, `market`, `realestate`, `trade` | 165.232.162.72 |

## 19. Archived Repos (read-only, do not use)
- `rashed-commits/sms-finance` → now `finance/`
- `rashed-commits/uae-market-intel` → now `market/`
- `rashed-commits/uae-realestate-bot` → now `realestate/`
- `rashed-commits/trade-bot` → now `trade/`
