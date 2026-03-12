#!/usr/bin/env bash
# deploy.sh — Push updates to the VPS
# Usage: ./deploy.sh "commit message"

set -euo pipefail

VPS_USER="root"
VPS_HOST="165.232.162.72"
APP_DIR="/opt/uae-market-intel"
COMPOSE_FILE="docker-compose.yml"

MSG="${1:-deploy: update application}"

echo "==> Committing changes..."
git add -A
git commit -m "$MSG" || echo "Nothing to commit."

echo "==> Pushing to remote..."
git push origin main

echo "==> Deploying on VPS..."
ssh "${VPS_USER}@${VPS_HOST}" bash -s <<'REMOTE'
  set -euo pipefail
  cd /opt/uae-market-intel
  git pull origin main
  docker compose build --no-cache
  docker compose up -d
  echo "==> Deployment complete. Container status:"
  docker compose ps
REMOTE

echo "==> Done! App is live at http://${VPS_HOST}:8000"
