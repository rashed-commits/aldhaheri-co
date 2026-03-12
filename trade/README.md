# Trade-Bot

ML-powered stock trading pipeline that ingests market data, engineers features,
trains an XGBoost classifier, generates daily buy/sell signals, and executes
paper trades on Alpaca — all running inside a Docker container on a
DigitalOcean droplet.

## Pipeline Phases

| Phase | Description | Output |
|-------|-------------|--------|
| 1 | Data ingestion (yfinance) | `data/combined.csv` |
| 2 | Feature engineering | `data/features.csv` |
| 3 | Model training (XGBoost) | `model/saved/` |
| 4 | Daily signal generation | `output/signals_YYYY-MM-DD.json` |
| 5 | Alpaca paper trade execution | `output/open_positions.json` |

## Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/rashed-commits/trade-bot.git && cd trade-bot

# 2. Configure
cp .env.example .env
# Fill in ALPACA_API_KEY, ALPACA_SECRET_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# 3. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Run
python main.py              # phases 1-3 (training)
python main.py --phase 4    # daily signals
python main.py --phase 5    # execute trades
python main.py --phase 4 --dry-run   # signal gen without writing files
```

## Docker Deployment (DigitalOcean)

### Initial Setup

```bash
ssh root@165.232.162.72
cd /opt && git clone https://github.com/rashed-commits/trade-bot.git && cd trade-bot
cp .env.example .env && nano .env   # fill in real values
timedatectl set-timezone America/New_York
docker compose up --build -d
```

### Cron Schedule

Add to the host's crontab (`crontab -e`):

```cron
# Phase 4 (signals): 9:25 AM ET, Mon-Fri
25 9 * * 1-5 docker exec trade-bot python main.py --phase 4 >> /opt/trade-bot/logs/cron.log 2>&1

# Phase 5 (execution): 9:35 AM ET, Mon-Fri
35 9 * * 1-5 docker exec trade-bot python main.py --phase 5 >> /opt/trade-bot/logs/cron.log 2>&1

# Phases 1-3 (retrain): Sunday 6:00 AM ET
0 6 * * 0 docker exec trade-bot python main.py >> /opt/trade-bot/logs/cron.log 2>&1
```

### Redeployment

```bash
./deploy.sh   # commit, push, SSH pull, rebuild
```

## Web Dashboard

A React dashboard at port 3003 provides a visual overview of the portfolio. Authentication uses a `session` cookie set on `.aldhaheri.co` by the central hub, containing a JWT signed with `JWT_SECRET`.

- **Dashboard**: `http://<host>:3003` — Portfolio summary, positions, signals, model metrics, feature importance
- **API**: `http://<host>:8003` — FastAPI backend serving portfolio data (session cookie auth)
- **Health**: `http://<host>:8003/health` — Unauthenticated health check

### Dashboard Features

- Portfolio equity, total/daily P&L, position count
- Current positions table with unrealized P&L
- Latest trading signals with color-coded BUY/SELL/HOLD
- Model performance metrics (accuracy, ROC-AUC, F1)
- Feature importance chart (top 15 features)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPACA_API_KEY` | Yes | Alpaca paper trading API key |
| `ALPACA_SECRET_KEY` | Yes | Alpaca paper trading secret |
| `ALPACA_BASE_URL` | No | Defaults to `https://paper-api.alpaca.markets` |
| `TELEGRAM_BOT_TOKEN` | No | Bot token from @BotFather (blank = no notifications) |
| `TELEGRAM_CHAT_ID` | No | Telegram chat ID to receive alerts |
| `JWT_SECRET` | Yes* | Shared secret for SSO token verification (*required for dashboard) |

## Project Structure

```
trade-bot/
├── main.py                    # CLI orchestrator
├── src/
│   ├── config.py              # Centralised configuration
│   ├── ingest.py              # Phase 1: data ingestion
│   ├── features.py            # Phase 2: feature engineering
│   ├── train.py               # Phase 3: model training
│   ├── signals.py             # Phase 4: signal generation
│   ├── notifications.py       # Telegram notification helpers
│   ├── execution/
│   │   ├── alpaca.py          # Alpaca API wrapper
│   │   └── executor.py        # Phase 5: trade execution
│   └── utils.py               # Logging & file utilities
├── google_apps_script/
│   └── dashboard.gs           # Google Sheets analytics dashboard
├── api/
│   ├── main.py                # FastAPI app
│   ├── routers/
│   │   ├── auth.py            # Session cookie auth middleware
│   │   └── portfolio.py       # Portfolio data endpoints
│   ├── Dockerfile
│   └── requirements.txt
├── dashboard/
│   ├── src/
│   │   ├── App.jsx            # SSO check + routing
│   │   ├── api.js             # Fetch API client (cookie auth)
│   │   ├── pages/Dashboard.jsx
│   │   └── components/        # Header, PortfolioSummary, PositionsTable, etc.
│   ├── Dockerfile             # Multi-stage (node build → nginx)
│   └── nginx.conf
├── Dockerfile
├── docker-compose.yml
├── deploy.sh
├── requirements.txt
└── .env.example
```
