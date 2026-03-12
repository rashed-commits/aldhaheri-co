# aldhaheri.co — Personal Command Center

Monorepo for all aldhaheri.co services. SSO hub + four subdomain projects, deployed from a single repo on one DigitalOcean droplet.

## Subdomains

```
aldhaheri.co               → Hub login + project selector
finance.aldhaheri.co       → SMS Finance Tracker
market.aldhaheri.co        → UAE Market Intel
realestate.aldhaheri.co    → UAE Real Estate Analytics
trade.aldhaheri.co         → Trade Bot Dashboard
```

## Monorepo Structure

```
aldhaheri_co/
  hub/                    # SSO hub (ports 4000, 4001)
  finance/                # SMS finance tracker (ports 3000, 8001)
  market/                 # UAE market intel (port 8000)
  realestate/             # Real estate analytics (ports 3002, 8002)
  trade/                  # ML trade bot + dashboard (ports 3003, 8003)
  docker-compose.yml      # Root compose — includes per-project files
  .env                    # Single env file for ALL services
  deploy.sh               # Push + VPS pull + rebuild
  nginx/                  # Nginx site configs
```

Each project has its own `docker-compose.yml`. The root compose uses `include:` to merge them:

```yaml
include:
  - path: ./finance/docker-compose.yml
  - path: ./market/docker-compose.yml
  - path: ./realestate/docker-compose.yml
  - path: ./trade/docker-compose.yml
```

## Auth Flow

**Primary**: WebAuthn/FIDO2 passkey authentication
**Fallback**: Password login for initial setup

1. User visits aldhaheri.co and authenticates (passkey or password)
2. Server creates session in SQLite and issues JWT in secure HTTP-only cookie
3. Cookie is scoped to `.aldhaheri.co` (shared across subdomains)
4. All subdomain backends validate the cookie using the shared `JWT_SECRET`
5. Rate limiting: 5 attempts / 5 min, 15-min lockout

## Setup

### 1. Clone & Configure

```bash
git clone https://github.com/rashed-commits/aldhaheri-co.git
cd aldhaheri-co
cp .env.example .env
# Edit .env with your values
```

### 2. Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Used By | Description |
|----------|---------|-------------|
| `JWT_SECRET` | All | Shared SSO signing secret |
| `HUB_USERNAME` / `HUB_PASSWORD` | Hub | Login credentials |
| `ANTHROPIC_API_KEY` | Finance | Claude API for SMS parsing |
| `WEBHOOK_API_KEY` | Finance | Tasker webhook auth |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Finance | Transaction notifications |
| `OPENAI_API_KEY` | Market | GPT-4o-mini for signals |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Trade | Paper trading |

### 3. Local Development

```bash
# Hub
cd hub/backend && pip install -r requirements.txt && uvicorn main:app --reload --port 4001
cd hub/frontend && npm install && npm run dev

# Finance
cd finance/backend && pip install -r requirements.txt && uvicorn backend.main:app --reload --port 8000
cd finance/frontend && npm install && npm run dev

# Market
cd market && pip install -r requirements.txt && python server.py
```

### 4. Docker Deployment

```bash
# All services
docker compose up -d --build

# Single service
docker compose up -d --build finance-backend

# View logs
docker compose logs -f finance-backend
```

### 5. VPS Deployment

```bash
bash deploy.sh
```

## DNS Setup (GoDaddy)

| Record | Type | Value |
|--------|------|-------|
| `@` | A | 165.232.162.72 |
| `www` | A | 165.232.162.72 |
| `finance` | A | 165.232.162.72 |
| `market` | A | 165.232.162.72 |
| `realestate` | A | 165.232.162.72 |
| `trade` | A | 165.232.162.72 |

## Adding a New Project

1. Create `<project>/` directory with backend/frontend and `docker-compose.yml`
2. Add `include:` entry in root `docker-compose.yml`
3. Add env vars to root `.env` and `.env.example`
4. Add card to `hub/frontend/src/config/projects.js`
5. Add DNS A record → 165.232.162.72
6. Create Nginx config + `certbot --nginx -d <subdomain>`
7. Deploy: `docker compose up -d --build`

## Hub API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | No | Password login |
| GET | `/api/auth/verify` | Yes | Verify session |
| POST | `/api/auth/logout` | No | Revoke session |
| GET | `/api/auth/status` | No | Check passkey status |
| POST | `/api/auth/webauthn/register/begin` | Yes | Start passkey registration |
| POST | `/api/auth/webauthn/register/complete` | Yes | Complete registration |
| POST | `/api/auth/webauthn/login/begin` | No | Start passkey login |
| POST | `/api/auth/webauthn/login/complete` | No | Complete passkey login |
| GET | `/health` | No | Health check |

## Archived Repos

These repos are read-only archives. All development happens here.

- `rashed-commits/sms-finance` → `finance/`
- `rashed-commits/uae-market-intel` → `market/`
- `rashed-commits/uae-realestate-bot` → `realestate/`
- `rashed-commits/trade-bot` → `trade/`
