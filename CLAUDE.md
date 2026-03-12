# CLAUDE.md — aldhaheri_co (Hub)

## 1. Project Overview
A unified personal command center at aldhaheri.co. Provides SSO login and a project selector dashboard that grants access to all personal projects via subdomains. Single-user system (one username/password).

## 2. Tech Stack
- **Frontend**: React 18 + Vite + Tailwind CSS (dark theme)
- **Backend**: FastAPI (Python 3.11) with python-jose for JWT
- **Auth**: JWT (HS256, 8hr expiry) stored in localStorage
- **Deployment**: Docker Compose on DigitalOcean Ubuntu droplet
- **Reverse Proxy**: Nginx with Certbot HTTPS

## 3. Architecture
```
aldhaheri_co/
  backend/           # FastAPI auth API (port 4001)
    main.py          # Entry point
    routers/auth.py  # /api/auth/* endpoints
    models/auth.py   # Pydantic models
    services/auth.py # Auth logic, lockout, blacklist
    utils/jwt_handler.py # JWT create/decode
  frontend/          # React Vite app (port 4000)
    src/
      pages/         # Login.jsx, Dashboard.jsx
      components/    # Header.jsx, ProjectCard.jsx
      services/      # api.js, auth.js
      config/        # projects.js (project card definitions)
  docker-compose.yml
  deploy.sh
```

## 4. Coding Conventions
- Backend: PEP8, type hints, async handlers, APIRouter pattern
- Frontend: Functional components, hooks, Tailwind utility classes
- No dead code or commented-out blocks

## 5. UI & Design Rules
- Background: #0F0F1A | Card: #1A1A2E | Border: #2D2D4E
- Accent: #7C3AED (purple) | Accent light: #A78BFA
- Text: #F1F5F9 (primary) | #94A3B8 (muted)
- Success: #10B981 | Warning: #F59E0B | Danger: #EF4444
- Font: Inter / system-ui
- Nav height: 56px across all projects

## 6. SSO / JWT
- **JWT_SECRET must be identical across ALL project repos**
- Token issued on login with 8hr expiry
- Subdomains receive token via `?token=JWT` URL parameter
- Each subdomain validates JWT signature locally using shared secret

## 7. Adding a New Project
1. Add entry to `frontend/src/config/projects.js`
2. Set up subdomain DNS (A record → 165.232.162.72)
3. Create Nginx config at `/etc/nginx/sites-available/<subdomain>`
4. Run `certbot --nginx -d <subdomain>`
5. Add SSO middleware to the new project repo
6. Deploy with `docker compose up -d --build`

## 8. Environment Variables
```
HUB_USERNAME    — Login username
HUB_PASSWORD    — Login password
JWT_SECRET      — Shared JWT signing secret (SAME across all repos)
VITE_API_URL    — Frontend API base URL (https://aldhaheri.co)
```

## 9. Safe-Change Rules
- Never modify JWT_SECRET without updating ALL project repos
- Never commit .env files
- Never remove or change the /health endpoint shape

## 10. Commands
```bash
# Local dev
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 4001
cd frontend && npm install && npm run dev

# Build & deploy
docker compose up -d --build
bash deploy.sh
```
