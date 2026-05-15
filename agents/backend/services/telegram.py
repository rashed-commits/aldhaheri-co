"""
Telegram delivery for cron output. Reuses the existing TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID vars that Finance already populates.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured; skipping message")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text})
            if r.status_code != 200:
                logger.warning("Telegram API %d: %s", r.status_code, r.text)
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram send failed: %s", exc)
        return False
