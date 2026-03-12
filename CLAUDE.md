# CLAUDE.md — aldhaheri_co (Monorepo)

## 1. Project Overview
Monorepo for all aldhaheri.co services. Contains the SSO hub and four subdomain projects, all deployed from a single repo on one DigitalOcean droplet. Single-user system (one username/password).

## 2. Tech Stack
- **Hub**: React 18 + Vite + Tailwind, FastAPI + python-jose (JWT)
- **Finance**: React + Recharts, FastAPI + SQLAlchemy + Anthropic SDK (SMS parsing)
- **Market**: Flask + Vanilla JS, OpenAI GPT-4o-mini, Apify, Tavily
- **Real Estate**: React + Vite + Recharts, FastAPI, Playwright + BeautifulSoup scrapers
- **Trade**: React + Vite + Recharts, FastAPI, XGBoost, Alpaca SDK
- **Auth**: Cookie-based JWT (HS256, 8hr expiry), shared JWT_SECRET across all services
- **Infra**: Docker Compose, Nginx + Certbot, DigitalOcean Ubuntu droplet

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
    src/                  # XGBoost pipeline (cron-driven, no port)
    api/                  # FastAPI (port 8003)
    dashboard/            # React Vite (port 3003)
    docker-compose.yml
  docker-compose.yml      # Root: hub services + include: per-project files
  .env                    # Single env file for ALL services
  deploy.sh               # Git push + VPS pull + rebuild
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

## 4. Coding Conventions
- **Python**: PEP8, type hints, async handlers, APIRouter pattern, thin routes + service logic
- **JavaScript**: Functional components, hooks, Tailwind utility classes
- No dead code or commented-out blocks

## 5. UI & Design Rules
- Background: #0F0F1A | Card: #1A1A2E | Border: #2D2D4E
- Accent: #7C3AED (purple) | Accent light: #A78BFA
- Text: #F1F5F9 (primary) | #94A3B8 (muted)
- Success: #10B981 | Warning: #F59E0B | Danger: #EF4444
- Font: Inter / system-ui
- Nav height: 56px across all projects

## 6. SSO / JWT
- Single `JWT_SECRET` in root `.env`, shared by all services
- Hub sets `session` cookie on login
- All subdomains validate the cookie using the shared secret
- On auth failure, all frontends redirect to `https://aldhaheri.co`
- No `?token=` URL parameter — cookie-only auth

## 7. Environment Variables
All services read from the single root `.env` file. Each service only uses the vars it needs.

```
# Shared
JWT_SECRET              — SSO signing secret (ALL services)

# Hub
HUB_USERNAME            — Login username
HUB_PASSWORD            — Login password
VITE_API_URL            — Hub frontend API base URL

# Finance
ANTHROPIC_API_KEY       — Claude API for SMS parsing
WEBHOOK_API_KEY         — Tasker webhook + API auth
DASHBOARD_USERNAME      — Finance dashboard login
DASHBOARD_PASSWORD      — Finance dashboard password
FINANCE_VITE_API_URL    — Finance frontend API base URL
TELEGRAM_BOT_TOKEN      — Finance transaction notifications
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
```

## 8. Adding a New Project
1. Create `<project>/` directory with backend/frontend
2. Add `<project>/docker-compose.yml` referencing `../.env`
3. Add `include:` entry in root `docker-compose.yml`
4. Add env vars to root `.env` and `.env.example`
5. Add entry to `hub/frontend/src/config/projects.js`
6. Set up subdomain DNS (A record → 165.232.162.72)
7. Create Nginx config at `/etc/nginx/sites-available/<subdomain>`
8. Run `certbot --nginx -d <subdomain>`
9. Deploy with `docker compose up -d --build`

## 9. Safe-Change Rules
- Never modify JWT_SECRET — it's shared across all 10 containers
- Never commit `.env` files
- Never remove or change any `/health` endpoint shape
- Never change finance webhook path (`/webhook/sms`) — Tasker depends on it
- Database migrations need explicit planning (SQLite, no auto-migrate)
- Backups at `/opt/backups/` on VPS — verify before destructive operations

## 10. VPS Details
- **IP**: 165.232.162.72
- **Repo**: `/opt/aldhaheri-co`
- **Backups**: `/opt/backups/`
- **Cron jobs**: trade-bot phases 4+5 weekdays, market-intel scraper daily

## 11. Commands
```bash
# Local dev — any project
cd hub/backend && uvicorn main:app --reload --port 4001
cd finance/backend && uvicorn backend.main:app --reload --port 8000
cd market && python server.py

# Build all
docker compose up -d --build

# Build single service
docker compose up -d --build finance-backend

# Deploy to VPS
bash deploy.sh

# View logs
docker compose logs -f finance-backend

# VPS direct
ssh root@165.232.162.72 "cd /opt/aldhaheri-co && docker compose ps"
```

## 12. Archived Repos (read-only, do not use)
- `rashed-commits/sms-finance` → now `finance/`
- `rashed-commits/uae-market-intel` → now `market/`
- `rashed-commits/uae-realestate-bot` → now `realestate/`
- `rashed-commits/trade-bot` → now `trade/`
