# SMS Finance

Self-hosted personal finance tracker. Receives raw bank SMS messages from an Android phone via Tasker HTTP POST, parses them using Claude AI into structured transaction data, stores them in SQLite, and serves a React dashboard with spending analytics.

Part of the [aldhaheri.co](https://aldhaheri.co) SSO ecosystem. Authentication is handled centrally by aldhaheri.co via a `session` cookie on the `.aldhaheri.co` domain. This service only validates the cookie — it does not handle login or registration.

## Architecture

```
┌──────────┐   SMS    ┌────────┐  HTTP POST  ┌──────────────┐
│  Phone   │ ──────── │ Tasker │ ──────────── │   Backend    │
│  (SMS)   │          │  App   │              │  (FastAPI)   │
└──────────┘          └────────┘              │              │
                                              │  Claude AI   │
                                              │  Parser      │
                                              │      │       │
                                              │      ▼       │
                                              │  SQLite DB   │
                                              └──────┬───────┘
                                                     │ API
                                              ┌──────▼───────┐
                                              │   Frontend   │
                                              │   (React +   │
                                              │   Tailwind)  │
                                              └──────────────┘
```

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key | `sk-ant-...` |
| `WEBHOOK_API_KEY` | Shared secret for webhook + API auth | `openssl rand -hex 32` |
| `JWT_SECRET` | JWT signing secret (shared across SSO ecosystem) | `openssl rand -hex 32` |
| `VITE_API_URL` | Public URL for backend API | `https://finance.aldhaheri.co` |

## Setup & Deployment

### Prerequisites
- Docker & Docker Compose
- An Anthropic API key

### Local Development

```bash
# Clone the repo
git clone https://github.com/RASHED-COMMITS/sms-finance.git
cd sms-finance

# Copy and fill env
cp .env.example .env
# Edit .env with your keys

# Create data directory
mkdir -p data

# Start services
docker compose up --build
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Health check: http://localhost:8000/health

### VPS Deployment

```bash
# First time — clone on VPS
ssh root@165.232.162.72
cd /opt
git clone https://github.com/RASHED-COMMITS/sms-finance.git
cd sms-finance
cp .env.example .env
# Edit .env with production values
mkdir -p data
docker compose up -d --build

# Subsequent deploys — from local machine
./deploy.sh
```

### Nginx Setup

Copy `nginx.conf.snippet` into your Nginx sites config, replacing `YOURDOMAIN.com` with your actual domain. Then:

```bash
sudo certbot --nginx -d finance.yourdomain.com
sudo nginx -t && sudo systemctl reload nginx
```

## Tasker Configuration

Set up on your Android phone to automatically forward bank SMS to the tracker.

### Profile
- **Trigger:** Event → Phone → Received SMS

### Task: HTTP Post
- **URL:** `https://finance.yourdomain.com/webhook/sms`
- **Method:** POST
- **Headers:**
  - `Content-Type: application/json`
  - `X-API-Key: <your WEBHOOK_API_KEY>`
- **Body:** `{"sms": "%SMSRB"}`

> `%SMSRB` is Tasker's built-in variable for the received SMS body.

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/webhook/sms` | X-API-Key | Receive and parse SMS (failed/declined transactions are auto-skipped) |
| `GET` | `/api/auth/verify` | Session cookie | Validate session |
| `GET` | `/api/transactions` | Session cookie or X-API-Key | List transactions (paginated) |
| `GET` | `/api/transactions/summary` | Session cookie or X-API-Key | Spending summary |
| `PATCH` | `/api/transactions/{id}` | Session cookie or X-API-Key | Update category/merchant |
| `DELETE` | `/api/transactions/{id}` | Session cookie or X-API-Key | Soft delete |
| `GET` | `/health` | None | Health check |

## Verify & Logs

```bash
# Watch backend logs
docker compose logs -f backend

# Test webhook
curl -X POST https://finance.yourdomain.com/webhook/sms \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"sms": "Your Cr.Card 8680 was used for AED 45.00 at CARREFOUR on 03/12/2026 02:30 PM"}'
```

## Troubleshooting

- **401 on webhook:** Check that `X-API-Key` header matches `WEBHOOK_API_KEY` in `.env`
- **Frontend shows no data:** Verify `VITE_API_URL` and `VITE_API_KEY` are set correctly. Frontend is built at Docker image build time, so rebuild after changing these.
- **Database errors:** Ensure `./data` directory exists and is writable. Check volume mount in `docker-compose.yml`.
- **Claude parsing failures:** Check `ANTHROPIC_API_KEY` is valid. Transactions with parse errors are saved as `UNKNOWN` type.
- **Failed transactions not recorded:** This is expected. SMS containing "failed", "declined", "rejected", "unsuccessful", or "not completed" are automatically skipped.
- **Port conflicts:** Make sure ports 8000 and 3000 are not in use by other services.
