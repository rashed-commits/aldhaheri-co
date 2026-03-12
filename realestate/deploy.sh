#!/bin/bash
# deploy.sh — Commit, push, and deploy to VPS
set -e

VPS_USER="root"
VPS_HOST="vps.aldhaheri.co"
PROJECT_DIR="/opt/uae-realestate-bot-sso"

echo "=== UAE Real Estate — Deploy ==="

# 1. Commit and push
echo "[1/3] Committing and pushing..."
git add .
git commit -m "deploy: $(date '+%Y-%m-%d %H:%M')" || echo "Nothing to commit"
git push origin main

# 2. SSH to VPS, pull, rebuild
echo "[2/3] Deploying to VPS..."
ssh "${VPS_USER}@${VPS_HOST}" << EOF
  cd ${PROJECT_DIR}
  git pull origin main
  docker compose down
  docker compose up --build -d
  echo "Waiting for health check..."
  sleep 5
  curl -sf http://localhost:8002/health && echo " Backend OK" || echo " Backend FAILED"
  docker compose ps
EOF

echo "[3/3] Done!"
echo "  Backend:  http://${VPS_HOST}:8002/health"
echo "  Frontend: http://${VPS_HOST}:3002"
