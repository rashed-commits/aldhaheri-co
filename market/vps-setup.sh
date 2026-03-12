#!/usr/bin/env bash
# vps-setup.sh — Run this ON the VPS (root@165.232.162.72)
# Sets up: firewall, SQLite backups, and verifies the app is running
#
# Usage:
#   ssh root@165.232.162.72
#   bash /opt/uae-market-intel/vps-setup.sh

set -euo pipefail

APP_DIR="/opt/uae-market-intel"
BACKUP_DIR="/opt/backups/uae-market-intel"

echo ""
echo "========================================="
echo "  UAE Market Intel — VPS Setup"
echo "========================================="
echo ""

# ------------------------------------------
# STEP 1: Verify the app is running
# ------------------------------------------
echo "--- Step 1: Checking if the app is running ---"

cd "$APP_DIR"

if docker compose ps --format '{{.State}}' 2>/dev/null | grep -q "running"; then
    echo "[OK] Container is running."
else
    echo "[..] Container not running. Starting it now..."
    docker compose up -d --build
    sleep 5
fi

echo "[..] Testing health endpoint..."
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "[OK] App is healthy!"
else
    echo "[!!] Health check failed. Check logs with: docker compose logs -f"
    echo "     Continuing setup anyway..."
fi
echo ""

# ------------------------------------------
# STEP 2: Configure firewall (UFW)
# ------------------------------------------
echo "--- Step 2: Configuring firewall (UFW) ---"

if ! command -v ufw &> /dev/null; then
    echo "[..] Installing UFW..."
    apt-get update -qq && apt-get install -y -qq ufw
fi

# Allow essential ports
ufw allow OpenSSH          > /dev/null 2>&1
ufw allow 8000/tcp         > /dev/null 2>&1

# Enable UFW if not already active
if ufw status | grep -q "inactive"; then
    echo "[..] Enabling UFW..."
    echo "y" | ufw enable > /dev/null 2>&1
fi

echo "[OK] Firewall configured. Open ports:"
ufw status numbered 2>/dev/null | grep -E "ALLOW|Status" || true
echo ""

# ------------------------------------------
# STEP 3: Set up SQLite database backups
# ------------------------------------------
echo "--- Step 3: Setting up SQLite backups ---"

mkdir -p "$BACKUP_DIR"

# Create the backup script
cat > /opt/backups/backup-uae-market-intel.sh << 'BACKUP_SCRIPT'
#!/usr/bin/env bash
# Backs up the SQLite database from the Docker volume
set -euo pipefail

BACKUP_DIR="/opt/backups/uae-market-intel"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/market_intel_${TIMESTAMP}.db"

# Copy the DB from the Docker volume
VOLUME_PATH=$(docker volume inspect uae-market-intel_app-data --format '{{.Mountpoint}}' 2>/dev/null)

if [ -z "$VOLUME_PATH" ] || [ ! -f "${VOLUME_PATH}/market_intel.db" ]; then
    echo "[!!] Database file not found. Is the container running?"
    exit 1
fi

# Use sqlite3 .backup for a safe copy (if available), otherwise cp
if command -v sqlite3 &> /dev/null; then
    sqlite3 "${VOLUME_PATH}/market_intel.db" ".backup '${BACKUP_FILE}'"
else
    cp "${VOLUME_PATH}/market_intel.db" "$BACKUP_FILE"
fi

# Keep only last 7 backups
ls -tp "${BACKUP_DIR}"/market_intel_*.db 2>/dev/null | tail -n +8 | xargs -r rm --

echo "[OK] Backup saved: ${BACKUP_FILE} ($(du -h "$BACKUP_FILE" | cut -f1))"
BACKUP_SCRIPT

chmod +x /opt/backups/backup-uae-market-intel.sh

# Add cron job (daily at 3 AM) if not already present
CRON_JOB="0 3 * * * /opt/backups/backup-uae-market-intel.sh >> /var/log/uae-market-intel-backup.log 2>&1"
if ! crontab -l 2>/dev/null | grep -qF "backup-uae-market-intel"; then
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "[OK] Cron job added: daily backup at 3:00 AM"
else
    echo "[OK] Cron job already exists."
fi

# Run a first backup now
echo "[..] Running initial backup..."
/opt/backups/backup-uae-market-intel.sh
echo ""

# ------------------------------------------
# DONE
# ------------------------------------------
echo "========================================="
echo "  Setup complete!"
echo "========================================="
echo ""
echo "  App URL:     http://$(curl -sf ifconfig.me 2>/dev/null || echo '165.232.162.72'):8000"
echo "  Backups:     ${BACKUP_DIR}/"
echo "  Backup log:  /var/log/uae-market-intel-backup.log"
echo ""
echo "  Useful commands:"
echo "    docker compose -f ${APP_DIR}/docker-compose.yml logs -f    # view logs"
echo "    docker compose -f ${APP_DIR}/docker-compose.yml restart    # restart"
echo "    docker compose -f ${APP_DIR}/docker-compose.yml ps         # status"
echo "    /opt/backups/backup-uae-market-intel.sh                    # manual backup"
echo ""
