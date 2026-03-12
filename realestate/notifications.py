"""Telegram notifications for the Real Estate scraper pipeline."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL = "https://realestate.aldhaheri.co"
_NAXISTANT_FOOTER = (
    "\n\n\u2014\n"
    "This is an automated notification from Naxistant. "
    "Naxistant cannot respond to these updates yet \u2014 coming in a future update."
)


def notify_scrape_complete(total_fetched: int, new: int, updated: int, elapsed_secs: float) -> None:
    """Send a Telegram summary after a scrape run completes."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    message = (
        "\U0001f3e0 *Real Estate Scrape Complete*\n\n"
        f"Listings fetched: {total_fetched:,}\n"
        f"New: {new:,}\n"
        f"Updated: {updated:,}\n"
        f"Duration: {elapsed_secs:.0f}s\n\n"
        f"\U0001f449 {DASHBOARD_URL}"
        f"{_NAXISTANT_FOOTER}"
    )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not resp.ok:
            logger.warning("Telegram API %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("Telegram notification failed: %s", e)
