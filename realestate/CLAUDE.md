# CLAUDE.md — UAE Real Estate Analytics

## 1. Project Overview
UAE Real Estate property analytics platform. Scrapes PropertyFinder and Bayut for investment-grade listings in Abu Dhabi and Dubai, scores opportunities using 4 weighted signals (rental yield, price discount, price drops, off-plan), and presents results via a React dashboard and daily PDF reports. Part of the aldhaheri.co ecosystem with shared SSO.

## 2. Tech Stack
- **Backend:** FastAPI (Python 3.11), SQLite, python-jose (JWT)
- **Frontend:** React 18, Vite, Tailwind CSS, Recharts, Axios
- **Scrapers:** requests, BeautifulSoup4, lxml, Playwright (fallback)
- **Reports:** ReportLab (PDF generation), Brevo (transactional email)
- **Infrastructure:** Docker Compose, Nginx (frontend), Ubuntu VPS
- **Auth:** JWT-based SSO shared across all aldhaheri.co services

## 3. Architecture
```
uae-realestate-bot-sso/
├── main.py                  # CLI entry point (scrape/score/report pipeline)
├── config.py                # All tuneable parameters
├── scrapers/                # PropertyFinder + Bayut scrapers
├── storage/db.py            # SQLite schema, upsert, query helpers
├── analysis/                # Price benchmarks, yield calc, composite scorer
├── alerts/                  # PDF report generation + email delivery
├── backend/                 # FastAPI API layer (read-only over SQLite)
│   ├── main.py              # FastAPI app + /health endpoint
│   ├── routers/auth.py      # JWT verification middleware
│   └── routers/listings.py  # /api/listings, /api/areas, /api/stats
├── frontend/                # React dashboard (Vite + Tailwind)
│   ├── src/pages/           # Dashboard page
│   ├── src/components/      # Header, StatsBar, ListingsTable, AreaChart
│   └── Dockerfile           # Multi-stage: node build + nginx serve
├── docker-compose.yml       # Backend (8002) + Frontend (3002)
└── data/listings.db         # SQLite database (auto-created by scrapers)
```

The backend is a read-only API layer. Scrapers write to `data/listings.db` via the CLI pipeline (`python main.py`). The API reads from the same database file.

## 4. Coding Conventions
- Python: PEP 8, type hints, async route handlers in FastAPI
- JavaScript: ES modules, functional components, hooks
- All config via environment variables (python-dotenv)
- No secrets in code; use .env file

## 5. UI & Design Rules
- Background: #0F0F1A, Card: #1A1A2E, Border: #2D2D4E, Accent: #7C3AED
- Text: #F1F5F9 primary, #94A3B8 muted
- Success: #10B981, Warning: #F59E0B, Danger: #EF4444
- Font: Inter, Nav height: 56px
- Match aldhaheri.co hub design system exactly

## 6. Content & Copy
- Professional, data-driven tone
- Prices in AED, areas in sqft
- City names: "Abu Dhabi" (display), "abu-dhabi" (data)

## 7. Testing & Quality
- Test scraper output with `--dry-run --limit-pages 2`
- Test scoring with `--score-only`
- Backend health check: `GET /health`
- Frontend dev server: port 3002

## 8. File Placement Rules
- New API routes go in `backend/routers/`
- New React components go in `frontend/src/components/`
- New pages go in `frontend/src/pages/`
- Scraper logic stays in `scrapers/`
- Analysis logic stays in `analysis/`

## 9. Safe-Change Rules
- NEVER modify `storage/db.py` schema without migration plan
- NEVER change scoring weights without explicit approval
- NEVER modify scraper selectors without testing with `--dry-run`
- Keep all existing Python code intact when adding web layer

## 10. Commands
```bash
# Scraper pipeline
python main.py --skip-bayut              # Full pipeline
python main.py --pf-only --dry-run       # Test scraper
python main.py --score-only              # Score existing data
python main.py --db-stats                # View DB stats

# Backend (dev)
cd backend && uvicorn main:app --reload --port 8002

# Frontend (dev)
cd frontend && npm run dev               # Port 3002, proxies /api to 8002

# Docker
docker compose up --build -d
docker compose logs -f

# Deploy
./deploy.sh
```
