## 1. Project Overview
UAE Market Intelligence - scrapes social media and news for UAE business signals, classifies with GPT-4o-mini, generates opportunity scores.

## 2. Tech Stack
Flask, Vanilla JS, SQLite, Apify, Tavily, OpenAI GPT-4o-mini, Docker

## 3. Architecture
Single-file Flask server (server.py) + scraper pipeline (scraper.py), vanilla JS frontend in static/

## 4. Coding Conventions
PEP8, type hints where possible

## 5. UI & Design Rules
Dark theme matching aldhaheri.co design system

## 6. SSO
JWT_SECRET must be identical across ALL project repos. Token validated on every API request.

## 7. Environment Variables
PORT, DATABASE_PATH, APIFY_TOKEN, TAVILY_API_KEY, OPENAI_API_KEY, JWT_SECRET, SCRAPE_MAX_ITEMS_PER_SOURCE

## 8. Safe-Change Rules
Never modify JWT_SECRET without updating all repos. Don't commit .env files.

## 9. Commands
docker compose up -d --build
python server.py (local dev)
