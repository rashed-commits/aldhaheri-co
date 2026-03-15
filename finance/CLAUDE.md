# SMS Finance — CLAUDE.md

## 1. Project Overview
Self-hosted personal finance tracker for UAE bank SMS. Receives SMS via Tasker webhook, parses with Claude AI, stores in SQLite, serves React dashboard. Optimizes for reliability and low maintenance.

## 2. Tech Stack
- **Backend:** FastAPI, SQLAlchemy + aiosqlite, Anthropic SDK, python-dotenv
- **Frontend:** React 18, Tailwind CSS 3, Recharts, Vite
- **Database:** SQLite at `/data/finance.db`
- **Infra:** Docker Compose, Nginx reverse proxy, DigitalOcean Ubuntu droplet

## 3. Architecture
```
backend/          → FastAPI app
  main.py         → entry point, CORS, lifespan
  db.py           → async SQLAlchemy engine + session
  models.py       → SQLAlchemy + Pydantic models
  parser.py       → Claude SMS parser
  routers/        → webhook.py, transactions.py
frontend/         → React SPA
  src/App.jsx     → main dashboard layout
  src/api.js      → fetch wrapper
  src/components/ → InflowOutflow, SpendByCategory, AccountBreakdown, RecentTransactions
```

## 4. Coding Conventions
- PEP8, type hints on all functions, async/await for all handlers
- Pydantic models for all request/response validation
- Use APIRouter, never define routes in main.py
- Keep route handlers thin — logic in parser.py or dedicated services

## 5. UI & Design Rules
- Dark theme: `bg-gray-950` base, `bg-gray-900` cards, `border-gray-800`
- Tailwind CSS utility classes only, no custom CSS
- Recharts for all charts (BarChart, PieChart)
- Green (#34D399) = inflow, Red (#F87171) = outflow

## 6. Content & Copy
- Dashboard only, no user-facing text generation
- Labels should be short and direct

## 7. Testing & Quality
- Manual testing via webhook curl commands
- Check `docker compose logs -f backend` for errors

## 8. File Placement Rules
- New API routes → `backend/routers/`
- New dashboard components → `frontend/src/components/`
- DB models → `backend/models.py`
- Business logic → `backend/parser.py` or new service files

## 9. Safe-Change Rules
- Never commit `.env` or `data/`
- Never change the Transaction table schema without migration plan
- Never modify `parser.py` system prompt without testing with real SMS samples
- Preserve `deleted` soft-delete pattern — never hard delete
- Failed/declined SMS are filtered pre-parse in webhook.py — do not remove this guard

## 10. Commands
```bash
# Local dev
docker compose up --build

# Deploy
./deploy.sh

# Backend only
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Frontend dev
cd frontend && npm run dev

# Watch logs
docker compose logs -f backend
```
