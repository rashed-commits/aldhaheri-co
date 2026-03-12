#!/bin/bash
set -e

VPS="root@165.232.162.72"
PROJECT_DIR="/root/aldhaheri_co"

echo "==> Committing and pushing changes..."
git add .
git commit -m "deploy: update aldhaheri_co" || true
git push origin main

echo "==> Deploying to VPS..."
ssh $VPS << 'EOF'
  cd /root/aldhaheri_co || { git clone https://github.com/rashed-commits/aldhaheri-co.git /root/aldhaheri_co && cd /root/aldhaheri_co; }
  git pull origin main
  docker compose down
  docker compose up -d --build
  echo "==> Deployment complete!"
  docker compose ps
EOF
