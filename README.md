# aldhaheri.co — Personal Command Center

A unified dark-themed hub providing SSO access to all personal projects via subdomains.

## Architecture

```
aldhaheri.co               → Hub login + project selector  (this repo)
finance.aldhaheri.co       → SMS Finance Tracker
market.aldhaheri.co        → UAE Market Intel
realestate.aldhaheri.co    → UAE Real Estate Analytics
trade.aldhaheri.co         → Trade Bot Dashboard
```

## SSO Flow

1. User visits aldhaheri.co and logs in
2. Hub issues a signed JWT (HS256, 8hr expiry)
3. Token stored in localStorage
4. User clicks a project card → subdomain opens with `?token=JWT`
5. Subdomain validates JWT using shared `JWT_SECRET`

## Tech Stack

- **Frontend**: React 18 + Vite + Tailwind CSS
- **Backend**: FastAPI (Python 3.11)
- **Auth**: JWT via python-jose
- **Deployment**: Docker Compose + Nginx + Certbot

## Setup

### 1. Clone & Configure

```bash
git clone https://github.com/rashed-commits/aldhaheri-co.git
cd aldhaheri-co
cp .env.example .env
# Edit .env with your values
```

### 2. Environment Variables

| Variable | Description |
|----------|-------------|
| `HUB_USERNAME` | Login username |
| `HUB_PASSWORD` | Login password |
| `JWT_SECRET` | Shared JWT secret — **must be the same across ALL project repos** |
| `VITE_API_URL` | Frontend API URL (e.g., `https://aldhaheri.co`) |

### 3. Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 4001

# Frontend
cd frontend
npm install
npm run dev
```

### 4. Docker Deployment

```bash
docker compose up -d --build
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
| `market` | A | 165.232.162.72 |
| `realestate` | A | 165.232.162.72 |
| `trade` | A | 165.232.162.72 |

> `finance` A record already exists — do not modify.

## Adding a New Project

1. Add an entry to `frontend/src/config/projects.js`:
   ```js
   {
     name: 'Project Name',
     description: 'Short description',
     icon: '🎯',
     url: 'https://subdomain.aldhaheri.co',
     healthUrl: 'https://subdomain.aldhaheri.co/health'
   }
   ```
2. Add DNS A record for the subdomain → `165.232.162.72`
3. Create Nginx server block at `/etc/nginx/sites-available/subdomain.aldhaheri.co`
4. Symlink: `ln -s /etc/nginx/sites-available/subdomain.aldhaheri.co /etc/nginx/sites-enabled/`
5. Run `certbot --nginx -d subdomain.aldhaheri.co`
6. Add SSO middleware to the project repo using the shared `JWT_SECRET`
7. Deploy the project container

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Login with username/password |
| GET | `/api/auth/verify` | Verify JWT token |
| POST | `/api/auth/logout` | Logout (blacklist token) |
| GET | `/health` | Health check |
