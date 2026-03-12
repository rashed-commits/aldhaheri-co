#!/usr/bin/env bash
# deploy.sh — push local changes and rebuild on the droplet.
# Usage: ./deploy.sh

set -euo pipefail

REMOTE="root@165.232.162.72"
REMOTE_DIR="/opt/trade-bot"

echo "==> Committing & pushing …"
git add -A
git commit -m "deploy: $(date +%Y-%m-%d_%H:%M)" || true
git push origin main

echo "==> Deploying to $REMOTE …"
ssh "$REMOTE" "cd $REMOTE_DIR && git pull && docker compose up --build -d"

echo "==> Verifying health endpoint …"
ssh "$REMOTE" "sleep 5 && curl -sf http://localhost:8003/health || echo 'API health check failed'"

echo "==> Done.  Container status:"
ssh "$REMOTE" "docker ps --filter name=trade-bot --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
