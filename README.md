# aldhaheri.co

Monorepo for all [aldhaheri.co](https://aldhaheri.co) services — a personal productivity platform running on a single DigitalOcean droplet. One SSO hub and four subdomain projects covering finance tracking, market intelligence, real estate analytics, and algorithmic trading.

## Projects

### Hub — [aldhaheri.co](https://aldhaheri.co)
SSO login portal and project dashboard. Handles authentication for all services via a shared JWT cookie on `.aldhaheri.co`. Supports WebAuthn/Passkey (primary), Password + TOTP via Microsoft Authenticator, and password-only fallback. Rate-limited: 5 attempts / 5 min with 15-min lockout.

### Finance — [finance.aldhaheri.co](https://finance.aldhaheri.co)
Personal finance tracker for UAE bank transactions. Receives SMS from an Android phone via Tasker webhook, parses with Claude AI, stores in SQLite, and serves a React dashboard with spending analytics.

Key features:
- **AI chatbot** (web + Telegram) that can query, modify, delete, and add transactions — context is rebuilt fresh from the database on every message, so the bot always has up-to-date data
- **Full merchant search** across the entire transaction history — the chatbot sees the last 100 transactions plus unlimited keyword-matched results from all records
- **CSV bank statement import** for reconciliation against existing transactions
- **Auto-categorization** by merchant history, 443-rule keyword lookup, Claude AI, and Telegram fallback
- **Pending transaction filter** — automatically rejects uncleared/pending SMS (e.g. cheque deposits awaiting clearance) so only confirmed transactions are recorded
- **Investment portfolio tracker** (`/investments`) — tracks stock/ETF positions with live prices via yfinance, USD/AED conversion, per-lot P&L, historical value chart, close positions (full or partial) with realized P&L tracking and trade history. Shows price update timestamp (UAE time) next to the exchange rate.
- **Unified search filtering** — the transaction search box filters charts, stat cards, and summary in real time (same behavior as the category/account/date toggle filters)

### Market — [market.aldhaheri.co](https://market.aldhaheri.co) *(shelved)*
UAE business signal intelligence. Currently offline — serves a static "Coming Back Soon" page. Scraper pipeline and API routes are disabled. Data volume is preserved.

### Real Estate — [realestate.aldhaheri.co](https://realestate.aldhaheri.co)
Property analytics for Abu Dhabi and Dubai. Scrapes PropertyFinder and Bayut, scores listings on 4 opportunity signals (rental yield, price discount, price drops, off-plan), delivers daily PDF reports via email, and serves a React dashboard with area benchmarks and listing tables.

### Trade — [trade.aldhaheri.co](https://trade.aldhaheri.co)
ML-powered stock trading bot. Five-phase pipeline: data ingestion (yfinance/Alpaca), feature engineering (technicals + fundamentals + analyst data + sector-relative strength + short interest), XGBoost model training with Platt-calibrated probabilities (TimeSeriesSplit), daily signal generation with VIX regime-adjusted thresholds, and Alpaca paper trade execution with position reconciliation. 10-day prediction horizon. Drawdown circuit breaker halts trading at 8% decline from peak or inception. Prediction feedback loop tracks directional accuracy (BUY/SELL only, HOLD excluded). Weekly Telegram summary after each Sunday retrain. FinBERT sentiment runs passively (accumulating data) but is suspended from model training until coverage exceeds 30%. React dashboard for portfolio monitoring.

## Architecture

```
aldhaheri_co/
  hub/                    # SSO login + project dashboard
    backend/              # FastAPI (port 4001)
    frontend/             # React 19 + Vite + Tailwind 4 (port 4000)
  finance/                # SMS-based bank transaction tracker
    backend/              # FastAPI (port 8001)
    frontend/             # React 18 + Recharts (port 3000)
  market/                 # UAE business signal intelligence
    server.py             # Flask (port 8000)
    static/               # Vanilla JS frontend
  realestate/             # Property analytics + scoring
    backend/              # FastAPI (port 8002)
    frontend/             # React 18 + Recharts (port 3002)
    scrapers/             # PropertyFinder + Bayut
  trade/                  # ML trading bot + dashboard
    main.py               # CLI orchestrator (phases 1-5)
    src/                  # XGBoost pipeline
    api/                  # FastAPI (port 8003)
    dashboard/            # React 19 + Recharts (port 3003)
  docker-compose.yml      # Root compose — includes all per-project compose files
  .env                    # Single env file for ALL services
  deploy.sh               # One-command deploy (push + VPS pull + rebuild)
  vps-setup.sh            # Initial VPS provisioning
  nginx/                  # Nginx site configs
```

The root `docker-compose.yml` uses `include:` to merge per-project compose files. Hub services are defined directly in the root file. Every service reads from one shared `.env`.

## Services

| Service | Container | Port | Health |
|---|---|---|---|
| Hub Frontend | hub-frontend | 4000 | -- |
| Hub Backend | hub-backend | 4001 | /health |
| Finance Backend | finance-backend | 8001 | /health |
| Finance Frontend | finance-frontend | 3000 | -- |
| Market Intel | market-intel | 8000 | /health |
| Real Estate Backend | realestate-backend | 8002 | /health |
| Real Estate Frontend | realestate-frontend | 3002 | -- |
| Trade Bot | trade-bot | -- | cron-driven |
| Trade Bot API | trade-bot-api | 8003 | /health |
| Trade Bot Dashboard | trade-bot-dashboard | 3003 | -- |

## Auth Flow

1. User visits aldhaheri.co and authenticates (passkey, password + TOTP, or password)
2. Hub backend creates a session in SQLite and issues a JWT in a secure HTTP-only cookie
3. Cookie is scoped to `.aldhaheri.co` (shared across all subdomains)
4. All subdomain backends validate the cookie using the shared `JWT_SECRET`
5. All frontends auto-redirect to `https://aldhaheri.co` on 401

## Setup

```bash
git clone https://github.com/rashed-commits/aldhaheri-co.git
cd aldhaheri-co
cp .env.example .env
# Edit .env with your API keys and secrets
```

## Environment Variables

All services read from the single root `.env`. See [`.env.example`](.env.example) for the full template.

| Variable | Service | Description |
|---|---|---|
| `JWT_SECRET` | All | Shared SSO signing secret |
| `HUB_USERNAME` / `HUB_PASSWORD` | Hub | Login credentials |
| `ANTHROPIC_API_KEY` | Finance, Market | Claude AI for SMS parsing, chatbot, signal classification |
| `WEBHOOK_API_KEY` | Finance | Tasker webhook auth |
| `TELEGRAM_BOT_TOKEN` | Finance, Trade | Telegram notifications (independent per service) |
| `TELEGRAM_CHATBOT_TOKEN` | Finance | Telegram chatbot (separate bot) |
| `TELEGRAM_CHAT_ID` | Finance, Trade | Telegram chat target |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Trade | Alpaca paper trading |
| `BREVO_API_KEY` | Real Estate | Email report delivery |
| `SENDER_EMAIL` / `REPORT_RECIPIENT` | Real Estate | Report sender and recipient |

## Development

```bash
# Run a backend locally
cd hub/backend && uvicorn main:app --reload --port 4001
cd finance/backend && uvicorn backend.main:app --reload --port 8000
cd market && python server.py
cd realestate/backend && uvicorn main:app --reload --port 8002
cd trade/api && uvicorn main:app --reload --port 8003

# Run a frontend locally (all follow the same pattern)
cd <project>/frontend && npm install && npm run dev

# Trade pipeline
cd trade && python main.py --phase 1  # phases 1-5

# Docker — build all services
docker compose up -d --build

# Docker — build a single service
docker compose up -d --build finance-backend

# View logs
docker compose logs -f finance-backend
```

## Deployment

```bash
# One-command deploy: commits, pushes, SSHs to VPS, pulls, rebuilds all
bash deploy.sh

# Check VPS status
ssh root@165.232.162.72 "cd /opt/aldhaheri-co && docker compose ps"
```

## Scheduled Jobs

### Finance (APScheduler, inside container)
- **00:00 UTC** — Zero-amount transaction sweep
- **10:00 UTC** — Telegram alert for unidentified transactions
- **1st of month 09:00 UTC** — Statement reminder

### Trade (VPS crontab, EDT timezone)
- **10:00 AM Mon-Fri** — Phase 4: signal generation + feedback loop evaluation
- **2:00 PM Mon-Fri** — Phase 5: trade execution with position reconciliation
- **6:00 AM Sunday** — Phases 1-3: full retrain (data ingest + features + training) + weekly Telegram summary
- **9:30 AM Mon-Fri** — FinBERT sentiment worker (separate container)

### Market (VPS crontab) — DISABLED
- Daily scraper cron removed on 2026-03-28

## API Endpoints

### Hub
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | No | Password login |
| GET | `/api/auth/verify` | Yes | Verify session |
| POST | `/api/auth/logout` | No | Revoke session |
| POST | `/api/auth/webauthn/register/begin` | Yes | Start passkey registration |
| POST | `/api/auth/webauthn/register/complete` | Yes | Complete registration |
| POST | `/api/auth/webauthn/login/begin` | No | Start passkey login |
| POST | `/api/auth/webauthn/login/complete` | No | Complete passkey login |
| GET | `/api/totp/status` | Yes | TOTP enabled check |
| POST | `/api/totp/setup` | Yes | Generate TOTP secret + QR |
| POST | `/api/totp/verify` | Yes | Verify and enable TOTP |
| POST | `/api/totp/disable` | Yes | Disable TOTP |
| POST | `/api/auth/totp/verify` | No | Verify TOTP during login |

### Finance
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/webhook/sms` | X-API-Key | Receive and parse SMS (with transfer reconciliation) |
| GET | `/api/transactions` | Session / X-API-Key | List transactions (paginated) |
| GET | `/api/transactions/summary` | Session / X-API-Key | Spending summary |
| PATCH | `/api/transactions/{id}` | Session / X-API-Key | Update fields |
| DELETE | `/api/transactions/{id}` | Session / X-API-Key | Soft delete |
| POST | `/api/chat` | Session | AI chatbot query |
| POST | `/api/chat/execute` | Session | Execute chatbot action |
| POST | `/api/statements/upload` | Session | Upload bank CSV for reconciliation |
| POST | `/api/statements/import-all` | Session | Batch import CSVs from `/data/statements/` |
| POST | `/api/sweep` | Session | Manual zero-amount cleanup |
| GET | `/api/investments/positions` | Session | List investment positions |
| POST | `/api/investments/positions` | Session | Add a position |
| DELETE | `/api/investments/positions/{id}` | Session | Soft-delete a position |
| POST | `/api/investments/positions/{id}/close` | Session | Close position (full or partial) |
| GET | `/api/investments/portfolio` | Session | Portfolio with open/closed positions and P&L |

### Market
| Method | Path | Description |
|---|---|---|
| GET | `/api?action=all` | All signals |
| GET | `/api?action=stats` | Dashboard stats |
| GET | `/api?action=sector&sector=Fintech` | Filter by sector |
| GET | `/api?action=search&q=halal` | Full-text search |

### Real Estate
| Method | Path | Description |
|---|---|---|
| GET | `/api/listings` | Listings with filters (city, area, purpose, type) |
| GET | `/api/listings/{id}` | Single listing with area benchmark |
| GET | `/api/listings/{id}/history` | Price history snapshots |
| GET | `/api/areas` | Area benchmarks (avg price/sqft) |
| GET | `/api/stats` | Database statistics |

### Trade
| Method | Path | Description |
|---|---|---|
| GET | `/api/portfolio/summary` | Equity, P&L, position count |
| GET | `/api/portfolio/positions` | Open positions with current prices |
| GET | `/api/portfolio/signals` | Last 30 days of signals |
| GET | `/api/portfolio/signals/latest` | Most recent signal file |
| GET | `/api/portfolio/performance` | Model metrics (accuracy, ROC-AUC, F1) |
| GET | `/api/portfolio/features` | Top 15 feature importances |

All `/api/*` endpoints require a valid session cookie unless noted otherwise. Every service exposes `GET /health` (unauthenticated).

## DNS Setup

| Record | Type | Value |
|---|---|---|
| `@` | A | 165.232.162.72 |
| `www` | A | 165.232.162.72 |
| `finance` | A | 165.232.162.72 |
| `market` | A | 165.232.162.72 |
| `realestate` | A | 165.232.162.72 |
| `trade` | A | 165.232.162.72 |

## Adding a New Project

1. Create `<project>/` directory with backend/frontend and its own `docker-compose.yml`
2. Add `include:` entry in root `docker-compose.yml`
3. Add env vars to root `.env` and `.env.example`
4. Add card to `hub/frontend/src/config/projects.js`
5. Add DNS A record pointing to 165.232.162.72
6. Create Nginx config at `/etc/nginx/sites-available/<subdomain>`
7. Run `certbot --nginx -d <subdomain>.aldhaheri.co`
8. Deploy: `docker compose up -d --build`

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontends | React 18/19, Vite, Tailwind CSS 3/4, Recharts |
| Backends | FastAPI (4 services), Flask (Market) |
| AI/ML | Claude Sonnet (Finance), Claude Haiku (Market), XGBoost + Platt calibration + FinBERT (Trade) |
| Databases | SQLite everywhere, JSON files (Trade pipeline output) |
| Infrastructure | Docker Compose, Nginx + Certbot, DigitalOcean Ubuntu VPS |
| Trading | Alpaca SDK (paper trading) |
| Scraping | Playwright, BeautifulSoup, Apify, Tavily |
| Notifications | Telegram Bot API, Brevo (email) |

## Tasker Configuration (Finance)

Set up on Android to automatically forward bank SMS:

- **Trigger:** Event > Phone > Received SMS
- **URL:** `https://finance.aldhaheri.co/webhook/sms`
- **Method:** POST
- **Headers:** `Content-Type: application/json`, `X-API-Key: <WEBHOOK_API_KEY>`
- **Body:** `{"sms": "%SMSRB"}`

### Transfer Reconciliation

The webhook handles bank transfers with automatic reconciliation:

1. **All transfers** start as Category "Transfer", Merchant blank (or extracted from SMS if present) — a Telegram message prompts the user to categorize each one
2. **Confirmation SMS** (`Confirmation recd. from ...`) is not stored as a new transaction — it updates the original transfer's merchant with the recipient name
3. **Internal transfers** (Cr/Dr pair with same amount on same day) are automatically re-categorized as "Internal Transfers"

### Auto-Categorization Rules

- **Cheques**: Inflows → "Real Estate Income", Outflows → "Real Estate Expenses"
- **Refunds**: Merchant is always set to "Refund"
- **Balance monitoring**: Internal Transfers and Credit Card Payments trigger a Telegram warning if total inflows ≠ total outflows

### Dashboard Charts

Six charts in a 2-column grid:

| Left | Right |
|---|---|
| Monthly Inflow vs Outflow | Cumulative Inflow vs Outflow |
| Income by Category | Income by Merchant |
| Spend by Category | Spend by Merchant |

All pie charts are clickable — clicking a slice opens a drilldown modal with the filtered transactions.

## Archived Repos

These standalone repos are read-only archives. All development happens in this monorepo.

- `rashed-commits/sms-finance` → `finance/`
- `rashed-commits/uae-market-intel` → `market/`
- `rashed-commits/uae-realestate-bot` → `realestate/`
- `rashed-commits/trade-bot` → `trade/`
