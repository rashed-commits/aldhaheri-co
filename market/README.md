# UAE Market Intelligence

A dashboard for monitoring market opportunities across the UAE — tracking social media, forums, news, and review platforms to surface emerging pain points, unmet needs, and trending topics.

## Features

- **Multi-platform monitoring** — Reddit, X/Twitter, LinkedIn, Facebook Groups, Arabic Forums, Google Reviews, News
- **Bilingual support** — Arabic and English content
- **Sector categorization** — Food & Beverage, Fintech, Healthcare, Real Estate, Retail, Education, Logistics, Tourism
- **Opportunity scoring** — Signals rated High/Medium/Low with confidence scores
- **Interactive filtering** — Filter by sector, type, and full-text search

## Tech Stack

| Layer | Tool |
|-------|------|
| Backend | Python 3.12 / Flask / Gunicorn |
| Database | SQLite |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Docker / Docker Compose |

## Project Structure

```
├── server.py           # Flask API + static file server
├── static/
│   ├── index.html      # Dashboard UI
│   ├── app.js          # Frontend logic
│   └── style.css       # Dark theme styles
├── data/               # SQLite database (Docker volume, gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── deploy.sh           # One-command deployment script
└── README.md
```

## Deployment

### Prerequisites

- A VPS (e.g. DigitalOcean droplet) running Ubuntu with Docker and Docker Compose installed
- SSH access to the VPS
- Git installed on the VPS

### 1. First-time setup on VPS

```bash
# SSH into the VPS
ssh root@165.232.162.72

# Clone the repo
cd /opt
git clone https://github.com/rashed-commits/uae-market-intel.git
cd uae-market-intel

# Create .env from template
cp .env.example .env
# Edit .env if you need to change PORT or DATABASE_PATH
nano .env

# Build and start
docker compose up -d --build
```

### 2. Copy sensitive files to VPS (if needed)

```bash
# From your local machine
scp .env root@165.232.162.72:/opt/uae-market-intel/.env
```

### 3. Push updates (from local machine)

```bash
# Option A: Use the deploy script
chmod +x deploy.sh
./deploy.sh "your commit message"

# Option B: Manual steps
git add -A && git commit -m "update" && git push origin main
ssh root@165.232.162.72 "cd /opt/uae-market-intel && git pull && docker compose up -d --build"
```

### 4. Monitor and manage

```bash
# SSH into VPS first: ssh root@165.232.162.72

# Check container status
docker compose -f /opt/uae-market-intel/docker-compose.yml ps

# View logs (follow mode)
docker compose -f /opt/uae-market-intel/docker-compose.yml logs -f

# Restart the container
docker compose -f /opt/uae-market-intel/docker-compose.yml restart

# Stop the container
docker compose -f /opt/uae-market-intel/docker-compose.yml down

# Rebuild from scratch
docker compose -f /opt/uae-market-intel/docker-compose.yml up -d --build --force-recreate
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard UI |
| `GET /health` | Health check |
| `GET /api/auth/verify` | Verify session cookie (protected) |
| `GET /api?action=all` | All signals |
| `GET /api?action=stats` | Dashboard stats |
| `GET /api?action=sector&sector=Fintech` | Filter by sector |
| `GET /api?action=platform&platform=Reddit` | Filter by platform |
| `GET /api?action=search&q=halal` | Full-text search |

## TODO

- [ ] Custom domain + Nginx reverse proxy + SSL (Let's Encrypt)
- [x] Centralized cookie-based auth via aldhaheri.co hub
- [ ] Expand data sources (LinkedIn, Facebook Groups, Arabic forums)
- [ ] Automated data collection pipeline (replace n8n)
- [ ] AI-powered analysis (GPT-4o signal extraction)
- [ ] Daily email digest

---

Built for Rashed Al Dhaheri · Abu Dhabi, UAE
