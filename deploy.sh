#!/bin/bash
set -e

VPS="root@165.232.162.72"
PROJECT_DIR="/opt/aldhaheri-co"

echo "==> Committing and pushing changes..."
git add .
git commit -m "deploy: update aldhaheri_co" || true
git push origin main

echo "==> Deploying to VPS..."
ssh $VPS << 'EOF'
  cd /opt/aldhaheri-co
  git pull origin main
  docker compose up -d --build
  echo "==> Deployment complete!"
  docker compose ps
EOF
