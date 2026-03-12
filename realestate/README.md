# UAE Real Estate Monitor Bot

Automated bot that monitors PropertyFinder (and optionally Bayut) for investment-grade property listings in Abu Dhabi and Dubai. Scores listings on 4 opportunity signals (rental yield, price discount, price drops, off-plan) and delivers a polished daily PDF report via Gmail.

## Project Structure

```
uae-realestate-bot/
├── main.py                      # Entry point — run the pipeline
├── config.py                    # All tuneable parameters
├── requirements.txt             # Python dependencies
├── .env.example                 # Template for environment variables
├── DEPLOY.md                    # VPS deployment guide
├── run_daily.sh                 # Cron wrapper script (created on VPS)
├── scrapers/
│   ├── propertyfinder.py        # PropertyFinder scraper (HTTP + __NEXT_DATA__)
│   └── bayut.py                 # Bayut scraper (cookie-based, captcha-protected)
├── data/
│   ├── fetch_listings.py        # Orchestrator — coordinates scrapers + DB
│   └── listings.db              # SQLite database (auto-created)
├── storage/
│   └── db.py                    # SQLite schema, upsert, query helpers
├── analysis/
│   ├── price_benchmark.py       # Area avg price/sqft benchmarks
│   ├── yield_calc.py            # Gross rental yield from rent comps
│   └── opportunity_score.py     # Composite scorer (4 signals → 0-100)
├── alerts/
│   ├── email_sender.py          # Gmail SMTP sender (HTML + PDF attachment)
│   └── pdf_report.py            # ReportLab PDF generator (landscape A4)
├── utils/
│   └── logger.py                # Structured JSON logging
├── reports/                     # Generated PDF reports
└── logs/
    └── bot.log                  # Rotating log file
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up Gmail credentials (see .env.example)
cp .env.example .env
nano .env

# Full pipeline: scrape → score → PDF → email
python main.py --skip-bayut

# Score existing DB data only (no scrape)
python main.py --score-only

# Generate PDF + email from existing data
python main.py --report-only

# Quick test — sale only, 3 pages
python main.py --skip-bayut --purpose sale --limit-pages 3

# Dry run — fetch and print, don't write to DB
python main.py --pf-only --dry-run --limit-pages 2

# View database stats
python main.py --db-stats
```

## Usage

```
python main.py [options]

Options:
  --scrape-only              Scrape only, no scoring/report
  --score-only               Score existing DB data only
  --report-only              Generate PDF from DB data
  --pf-only                  Only run PropertyFinder
  --bayut-only               Only run Bayut (needs cookies)
  --skip-bayut               Full pipeline minus Bayut
  --dry-run                  Fetch and print — don't write to DB
  --purpose {sale,rent,both} Which purpose to fetch (default: both)
  --limit-pages N            Cap pages per search (0 = use config default of 20)
  --min-score N              Override minimum score threshold for report
  --refresh-bayut-cookies    Launch browser to solve captcha, save cookies
  --db-stats                 Show database statistics
```

## Scoring Engine

Each active sale listing is scored 0–100 using four weighted signals:

| Signal | Weight | Description |
|--------|--------|-------------|
| Rental Yield | 40% | Estimated gross yield from rent comparables |
| Price Discount | 25% | How far below area avg price/sqft |
| Price Drop | 20% | Price reduction since first seen |
| Off-plan | 15% | Binary: off-plan listings score higher |

**Yield normalisation:** <4% → 0, 6% → 50, 8%+ → 100
**Discount normalisation:** 0% → 0, 10% → 50, 20%+ → 100
**Price drop normalisation:** 0% → 0, 5% → 50, 10%+ → 100

Only listings scoring above the threshold (default: 40) make it into the daily report.

## PDF Report

Two-section report (landscape A4):
- **Section 1:** Top 20 off-plan opportunities
- **Section 2:** Top 20 secondary/ready listings

Each section includes:
- Summary stats (listing count, top score, avg score, cities/areas covered)
- Scoring methodology reminder
- Listing cards with price, size, price/sqft vs area average, estimated rental yield, price drop detection, signal breakdown, and direct link

## Email Delivery

The bot emails the report directly via **Gmail SMTP** (no middleware needed):

- **HTML body** — polished preview with top 5 listings, summary stats, hot areas
- **PDF attachment** — full 40-listing report

### Setup

1. Enable 2-Step Verification on your Google account
2. Generate an [App Password](https://myaccount.google.com/apppasswords)
3. Set environment variables (see `.env.example`)

## Data Sources

### PropertyFinder (✅ Working)
- Fetches data via plain HTTP requests
- Parses `__NEXT_DATA__` JSON from Next.js SSR pages
- Paginates using `?page=N` query parameter
- Covers city-wide searches for Abu Dhabi and Dubai
- ~800+ listings per full sale run (20 pages × 2 cities)

### Bayut (⚠️ Requires Manual Cookie Setup)
Bayut uses aggressive bot protection (EMPG hb-challenge + captcha) that blocks both plain HTTP requests and headless browsers.

**To enable Bayut:**
1. Open Bayut in your browser and browse a few listing pages
2. Export your cookies (using a browser extension like "EditThisCookie")
3. Save as `data/bayut_cookies.json` in the format: `{"cookie_name": "value", ...}`
4. Cookies typically last 24–72 hours before needing refresh

## Database Schema

### `listings` — Every unique listing ever seen
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | `{source}_{externalID}` |
| source | TEXT | `propertyfinder` or `bayut` |
| purpose | TEXT | `sale` or `rent` |
| price | REAL | Price in AED |
| area_sqft | REAL | Size in square feet |
| bedrooms | INT | Number of bedrooms |
| city | TEXT | `abu-dhabi` or `dubai` |
| area_name | TEXT | Community name (e.g. "Al Reem Island") |
| is_offplan | INT | 1 if off-plan |
| first_seen | TEXT | ISO timestamp |
| price_on_first | REAL | Price when first stored |

### `listing_history` — Price snapshot per run
Used for price-drop detection. Records price each time a listing is seen.

### `run_log` — Metadata per pipeline run
Tracks fetched/new/updated counts and errors.

## Configuration

Edit `config.py` to adjust:
- **LOCATIONS** — add or remove areas to monitor
- **BUDGET_PROFILES** — min/max price windows
- **MAX_PAGES_PER_SEARCH** — pagination depth (default: 20)
- **REQUEST_DELAY** — random delay between requests (default: 1.5–3.5s)
- **SCORING** — weights, thresholds, top_n_report count
- **EMAIL** — Gmail address, App Password, recipient

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GMAIL_ADDRESS` | Gmail account for sending reports | (required) |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not your regular password) | (required) |
| `REPORT_RECIPIENT` | Email address for the daily report | `rashed@aldhaheri.co` |

## Deployment

See **[DEPLOY.md](DEPLOY.md)** for the full VPS deployment guide including cron setup, environment configuration, and troubleshooting.

## Web Dashboard

The project includes a full-stack web dashboard for browsing listings and analytics.

### Architecture
- **Backend:** FastAPI (port 8002) — read-only API over the existing SQLite database
- **Frontend:** React + Vite + Tailwind (port 3002) — analytics dashboard with charts and tables
- **Auth:** Cookie-based SSO — the hub at aldhaheri.co sets a `session` cookie on `.aldhaheri.co` domain

### Dashboard Features
- Summary stats: total listings, avg price/sqft, cities covered, last scrape date
- Top listings table (sortable by price, price/sqft, bedrooms, size)
- Area benchmarks bar chart (avg price/sqft by area, color-coded by city)
- Price distribution breakdown by city and property type

### Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8002

# Frontend (in another terminal)
cd frontend
npm install
npm run dev   # http://localhost:3002
```

### Docker Deployment

```bash
# Build and run both services
docker compose up --build -d

# Check health
curl http://localhost:8002/health

# View logs
docker compose logs -f
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/listings` | List listings with filters (city, area, purpose, property_type, limit, offset) |
| `GET /api/listings/{id}` | Single listing detail with area benchmark |
| `GET /api/listings/{id}/history` | Price history snapshots |
| `GET /api/areas` | Area benchmarks (avg price/sqft per area) |
| `GET /api/stats` | Database statistics (totals, by city, by type, last scrape) |

All `/api/*` endpoints require a valid `session` cookie (JWT signed with `JWT_SECRET`, set by the hub at aldhaheri.co on the `.aldhaheri.co` domain).

| Endpoint | Description |
|----------|-------------|
| `GET /api/auth/verify` | Verify session cookie and return user info |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BREVO_API_KEY` | Brevo API key for transactional email | (required for email) |
| `SENDER_EMAIL` | Verified sender email in Brevo | (required for email) |
| `REPORT_RECIPIENT` | Email address for the daily report | `rashed@aldhaheri.co` |
| `JWT_SECRET` | Shared SSO secret across aldhaheri.co services | (required for API) |

## Roadmap

- [x] **Phase 1** — Core data pipeline (PropertyFinder, Bayut)
- [x] **Phase 2** — Analysis engine (price benchmarks, yield calc, composite scoring)
- [x] **Phase 3** — PDF report (two-section: off-plan + secondary)
- [x] **Phase 4** — Email delivery + VPS deployment
- [x] **Phase 5** — React dashboard, FastAPI API layer, SSO auth, Docker setup
- [ ] **Phase 6** — Tuning, additional sources, yield refinement
