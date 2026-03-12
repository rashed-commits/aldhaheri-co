#!/bin/bash
set -e

VPS="root@165.232.162.72"
PROJECT="sms-finance"
REMOTE_DIR="/opt/$PROJECT"

echo "==> Committing and pushing changes..."
git add .
git commit -m "deploy: update $PROJECT" || echo "Nothing to commit"
git push

echo "==> Deploying to VPS..."
ssh $VPS << 'ENDSSH'
  set -e
  cd /opt/sms-finance

  echo "==> Pulling latest code..."
  git pull

  echo "==> Rebuilding containers..."
  docker compose down
  docker compose build --no-cache
  docker compose up -d

  echo "==> Checking health..."
  sleep 5
  curl -sf http://localhost:8000/health && echo " Backend OK" || echo " Backend FAILED"

  echo "==> Done!"
ENDSSH
