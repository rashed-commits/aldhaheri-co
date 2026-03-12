import logging
import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DASHBOARD_URL = "https://finance.aldhaheri.co"


async def send_telegram_notification(txn) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        amount_str = f"{txn.currency} {txn.amount:,.2f}"
        time_str = f"{txn.date} at {txn.time}" if txn.date and txn.time else "N/A"
        merchant_str = txn.merchant or "N/A"
        flow_icon = "\U0001f7e2" if txn.flow_type == "Inflow" else "\U0001f534"

        message = (
            f"{flow_icon} New Transaction\n\n"
            f"Type: {txn.transaction_type}\n"
            f"Amount: {amount_str}\n"
            f"Account: {txn.account or 'N/A'}\n"
            f"Merchant: {merchant_str}\n"
            f"Category: {txn.category}\n"
            f"Date: {time_str}\n\n"
            f"\U0001f449 {DASHBOARD_URL}\n\n"
            f"\u2014\n"
            f"This is an automated notification from Naxistant. "
            f"Naxistant cannot respond to these updates yet \u2014 coming in a future update."
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            })
            if response.status_code != 200:
                logger.warning("Telegram API returned %d: %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Telegram notification failed: %s", e)
