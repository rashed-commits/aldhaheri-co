#!/bin/bash
# VPS Setup Script for aldhaheri.co infrastructure
# Run this on the VPS: root@165.232.162.72
set -e

echo "=== aldhaheri.co VPS Infrastructure Setup ==="

# --- 1. Clone/pull hub repo ---
echo "==> Setting up hub repo..."
if [ -d "/root/aldhaheri_co" ]; then
    cd /root/aldhaheri_co && git pull origin main
else
    git clone https://github.com/rashed-commits/aldhaheri-co.git /root/aldhaheri_co
fi

# --- 2. Copy Nginx configs ---
echo "==> Installing Nginx server blocks..."

# aldhaheri.co
cp /root/aldhaheri_co/nginx/aldhaheri.co /etc/nginx/sites-available/aldhaheri.co
ln -sf /etc/nginx/sites-available/aldhaheri.co /etc/nginx/sites-enabled/aldhaheri.co

# market.aldhaheri.co
cp /root/aldhaheri_co/nginx/market.aldhaheri.co /etc/nginx/sites-available/market.aldhaheri.co
ln -sf /etc/nginx/sites-available/market.aldhaheri.co /etc/nginx/sites-enabled/market.aldhaheri.co

# realestate.aldhaheri.co
cp /root/aldhaheri_co/nginx/realestate.aldhaheri.co /etc/nginx/sites-available/realestate.aldhaheri.co
ln -sf /etc/nginx/sites-available/realestate.aldhaheri.co /etc/nginx/sites-enabled/realestate.aldhaheri.co

# trade.aldhaheri.co
cp /root/aldhaheri_co/nginx/trade.aldhaheri.co /etc/nginx/sites-available/trade.aldhaheri.co
ln -sf /etc/nginx/sites-available/trade.aldhaheri.co /etc/nginx/sites-enabled/trade.aldhaheri.co

# Test and reload nginx
nginx -t && systemctl reload nginx
echo "==> Nginx configs installed and reloaded"

# --- 3. SSL Certificates ---
echo "==> Setting up SSL certificates..."
echo "NOTE: DNS records must be pointing to this server first!"
echo "Skipping finance.aldhaheri.co (already has HTTPS)"

certbot --nginx -d aldhaheri.co -d www.aldhaheri.co --non-interactive --agree-tos --email rashed@aldhaheri.co || echo "WARN: certbot failed for aldhaheri.co - check DNS"
certbot --nginx -d market.aldhaheri.co --non-interactive --agree-tos --email rashed@aldhaheri.co || echo "WARN: certbot failed for market.aldhaheri.co - check DNS"
certbot --nginx -d realestate.aldhaheri.co --non-interactive --agree-tos --email rashed@aldhaheri.co || echo "WARN: certbot failed for realestate.aldhaheri.co - check DNS"
certbot --nginx -d trade.aldhaheri.co --non-interactive --agree-tos --email rashed@aldhaheri.co || echo "WARN: certbot failed for trade.aldhaheri.co - check DNS"

echo "==> SSL setup complete"

# --- 4. Build and start hub containers ---
echo "==> Building and starting hub containers..."
cd /root/aldhaheri_co
docker compose up -d --build
echo "==> Hub containers started"

# --- 5. Pull and rebuild existing repos ---
echo "==> Updating sms-finance..."
cd /opt/sms-finance && git pull origin main && docker compose up -d --build || echo "WARN: sms-finance update failed"

echo "==> Updating uae-market-intel..."
cd /opt/uae-market-intel && git pull origin main && docker compose up -d --build || echo "WARN: uae-market-intel update failed"

echo "==> Setting up uae-realestate-bot..."
if [ -d "/opt/uae-realestate-bot" ]; then
    cd /opt/uae-realestate-bot && git pull origin main
else
    git clone https://github.com/rashed-commits/uae-realestate-bot.git /opt/uae-realestate-bot
    cd /opt/uae-realestate-bot
fi
docker compose up -d --build || echo "WARN: uae-realestate-bot update failed"

echo "==> Updating trade-bot..."
cd /opt/trade-bot && git pull origin main && docker compose up -d --build || echo "WARN: trade-bot update failed"

# --- 6. Verify ---
echo ""
echo "=== Deployment Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "=== Health Checks ==="
curl -s http://localhost:4001/health 2>/dev/null && echo "" || echo "Hub backend: OFFLINE"
curl -s http://localhost:8001/health 2>/dev/null && echo "" || echo "SMS Finance: OFFLINE"
curl -s http://localhost:8000/health 2>/dev/null && echo "" || echo "Market Intel: OFFLINE"
curl -s http://localhost:8002/health 2>/dev/null && echo "" || echo "Real Estate: OFFLINE"
curl -s http://localhost:8003/health 2>/dev/null && echo "" || echo "Trade Bot: OFFLINE"
echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "1. Add DNS records in GoDaddy (if not done)"
echo "2. Create .env files on VPS for each project"
echo "3. Ensure JWT_SECRET is the SAME across all .env files"
