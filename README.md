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

## Auth Flow

**Primary**: WebAuthn/FIDO2 passkey authentication
**Fallback**: Password login for initial setup and emergency recovery

1. User visits aldhaheri.co
2. If passkeys are registered, user authenticates with passkey (WebAuthn)
3. If no passkeys exist (first setup), user logs in with password
4. Server creates a session stored in SQLite and issues a JWT in a secure HTTP-only cookie
5. Session cookie is scoped to `.aldhaheri.co` domain (shared across subdomains)
6. Sessions have 30-minute idle timeout and 8-hour absolute timeout
7. Rate limiting (5 attempts / 5 min, 15-min lockout) protects against brute force

## Tech Stack

- **Frontend**: React 18 + Vite + Tailwind CSS
- **Backend**: FastAPI (Python 3.11)
- **Auth**: WebAuthn (py-webauthn) + JWT session cookies (python-jose)
- **Session Store**: SQLite (server-side sessions)
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
| `HUB_USERNAME` | Login username (password fallback) |
| `HUB_PASSWORD` | Login password (password fallback) |
| `JWT_SECRET` | Shared JWT secret — **must be the same across ALL project repos** |
| `RP_ID` | WebAuthn Relying Party ID (default: `aldhaheri.co`) |
| `RP_ORIGIN` | WebAuthn expected origin (default: `https://aldhaheri.co`) |
| `COOKIE_DOMAIN` | Session cookie domain (default: `.aldhaheri.co`) |
| `COOKIE_SECURE` | Set cookies as Secure (default: `true`) |
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

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | No | Password login (fallback) |
| GET | `/api/auth/verify` | Yes | Verify current session |
| POST | `/api/auth/logout` | No | Revoke session + clear cookie |
| GET | `/api/auth/status` | No | Check if passkeys are registered |
| POST | `/api/auth/webauthn/register/begin` | Yes | Start passkey registration |
| POST | `/api/auth/webauthn/register/complete` | Yes | Complete passkey registration |
| POST | `/api/auth/webauthn/login/begin` | No | Start passkey login |
| POST | `/api/auth/webauthn/login/complete` | No | Complete passkey login |
| GET | `/api/auth/webauthn/credentials` | Yes | List registered passkeys |
| DELETE | `/api/auth/webauthn/credentials/{id}` | Yes | Delete a passkey |
| GET | `/health` | No | Health check |
