# VPS Deployment Guide — UAE Real Estate Monitor Bot

Deploy the bot on your DigitalOcean droplet alongside the existing trading bot.

---

## Prerequisites

- Ubuntu 22.04+ droplet (already running `/opt/trading-bot/`)
- Python 3.10+
- Git configured for `rashed-commits/uae-realestate-bot`
- Free Brevo account for transactional email (HTTPS API — no SMTP ports needed)

---

## 1. Clone the Repo

```bash
cd /opt
sudo git clone https://github.com/rashed-commits/uae-realestate-bot.git
sudo chown -R $USER:$USER /opt/uae-realestate-bot
cd /opt/uae-realestate-bot
```

## 2. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** The email sender uses Brevo's HTTP API (`urllib` — Python stdlib).
> No extra packages needed beyond what's in `requirements.txt`.

## 3. Set Up Brevo (Email Delivery)

1. Sign up free at [https://app.brevo.com](https://app.brevo.com)
2. Go to **Settings → API Keys** and copy your API key (starts with `xkeysib-`)
3. Go to **Settings → Senders & IP → Add a Sender** and verify your sender email

## 4. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Fill in:

```
BREVO_API_KEY=xkeysib-your-api-key-here
SENDER_EMAIL=your-verified-sender@example.com
REPORT_RECIPIENT=rashed@aldhaheri.co
```

Then make the `.env` file readable only by your user:

```bash
chmod 600 .env
```

## 5. Load `.env` in the Cron Wrapper

Create a wrapper script that sources `.env` before running:

```bash
cat > /opt/uae-realestate-bot/run_daily.sh << 'EOF'
#!/bin/bash
# Daily real estate report — runs via cron at 3:00 AM UTC (7:00 AM GST)
set -euo pipefail

cd /opt/uae-realestate-bot
source venv/bin/activate

# Load environment variables
set -a
source .env
set +a

# Run pipeline (skip Bayut — captcha blocked)
python main.py --skip-bayut 2>&1 | tee -a logs/cron.log
EOF

chmod +x /opt/uae-realestate-bot/run_daily.sh
```

## 6. Create Log Directory

```bash
mkdir -p /opt/uae-realestate-bot/logs
```

## 7. Set Up the Cron Job

```bash
crontab -e
```

Add this line (runs at **3:00 AM UTC** = **7:00 AM GST**):

```
0 3 * * * /opt/uae-realestate-bot/run_daily.sh >> /opt/uae-realestate-bot/logs/cron.log 2>&1
```

## 8. Test It

Run manually first to verify everything works:

```bash
cd /opt/uae-realestate-bot
source venv/bin/activate
set -a && source .env && set +a

# Quick test — score existing data + send email (no scraping)
python main.py --report-only
```

Check your inbox for the report email with PDF attachment.

## 9. Full Pipeline Test

```bash
# Full run: scrape PropertyFinder → score → email report
python main.py --skip-bayut
```

---

## Directory Layout on VPS

```
/opt/
├── trading-bot/              ← existing
└── uae-realestate-bot/
    ├── venv/
    ├── .env                  ← Brevo API key (chmod 600)
    ├── run_daily.sh          ← cron wrapper script
    ├── main.py               ← entry point
    ├── config.py
    ├── scrapers/
    ├── analysis/
    ├── alerts/
    │   ├── email_sender.py   ← Brevo HTTP API sender
    │   └── pdf_report.py     ← PDF generator
    ├── data/
    │   └── listings.db       ← SQLite database
    ├── logs/
    │   ├── bot.log
    │   └── cron.log
    └── reports/              ← generated PDFs
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Brevo API error 401` | Check your API key is correct in `.env`. Regenerate at Settings → API Keys. |
| `Brevo API error 400` | Sender email must be verified in Brevo (Settings → Senders & IP). |
| `Brevo API key not configured` | Check `.env` file exists and `run_daily.sh` sources it correctly. |
| No email received | Check `logs/cron.log` and `logs/bot.log` for errors. Also check spam folder. |
| `No module named 'reportlab'` | Activate venv first: `source venv/bin/activate` |
| Bayut data stale | Bayut blocks headless scraping with captcha. Use `--skip-bayut` (PropertyFinder is the primary source). |
| PDF has no listings | Run `python main.py --db-stats` to check database state. May need to scrape first. |

---

## Updating the Bot

```bash
cd /opt/uae-realestate-bot
git pull
source venv/bin/activate
pip install -r requirements.txt  # in case of new deps
```

---

## Logs & Monitoring

- **Bot log:** `logs/bot.log` — detailed per-run output
- **Cron log:** `logs/cron.log` — daily cron execution output
- **Reports archive:** `reports/` — keeps all generated PDFs

Check last run:

```bash
tail -50 /opt/uae-realestate-bot/logs/cron.log
```

Check cron is active:

```bash
crontab -l | grep realestate
```
