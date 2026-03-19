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


async def send_category_help_request(merchant: str, txn) -> None:
    """Ask the user on Telegram to categorize an unknown merchant."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        amount_str = f"{txn.currency} {txn.amount:,.2f}"
        message = (
            "\U0001f4ad Category Help Needed\n\n"
            f"New transaction from an unknown merchant:\n"
            f"Merchant: {merchant}\n"
            f"Amount: {amount_str}\n"
            f"Account: {txn.account or 'N/A'}\n\n"
            "Could not determine the category from previous transactions "
            "or the merchant name. Please update it on the dashboard.\n\n"
            f"\U0001f449 {DASHBOARD_URL}\n\n"
            "\u2014\n"
            "Automated alert from Naxistant."
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
        logger.error("Category help request failed: %s", e)


async def send_unidentified_alert() -> None:
    """Daily alert if there are any Unidentified transactions."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        from backend.db import async_session
        from backend.models import Transaction
        from sqlalchemy import select, func

        async with async_session() as db:
            result = await db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.category == "Unidentified",
                    Transaction.deleted == False,
                )
            )
            count = result.scalar() or 0

        if count == 0:
            logger.info("unidentified alert: no unidentified transactions")
            return

        message = (
            "\u26a0\ufe0f Unidentified Transactions\n\n"
            f"You have {count} transaction{'s' if count > 1 else ''} "
            "categorized as Unidentified that need review.\n\n"
            f"\U0001f449 {DASHBOARD_URL}\n\n"
            "\u2014\n"
            "Automated alert from Naxistant."
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            })
            if response.status_code != 200:
                logger.warning("Telegram API returned %d: %s", response.status_code, response.text)
            else:
                logger.info("Unidentified alert sent: %d transactions", count)
    except Exception as e:
        logger.error("Unidentified alert failed: %s", e)


async def send_statement_reminder() -> None:
    """Monthly reminder to upload bank/card statements for reconciliation."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("statement reminder: Telegram not configured")
        return

    try:
        from datetime import datetime
        prev_month = datetime.utcnow().replace(day=1)
        # Previous month name
        import calendar
        month_idx = prev_month.month - 1 or 12
        year = prev_month.year if prev_month.month > 1 else prev_month.year - 1
        month_name = calendar.month_name[month_idx]

        message = (
            "\U0001f4ca Monthly Statement Reminder\n\n"
            f"Time to upload your {month_name} {year} bank & card statements "
            "for reconciliation.\n\n"
            "Accounts to export from ADIB:\n"
            "  \u2022 11404538810001 (Card-5747 debit)\n"
            "  \u2022 11404538810002 (savings)\n"
            "  \u2022 11404538920001 (rental)\n"
            "  \u2022 11404538920002 (salary)\n"
            "  \u2022 Credit Card 5516\n"
            "  \u2022 Credit Card 0615\n"
            "  \u2022 Credit Card 4347\n\n"
            "Upload CSVs to the Statements folder, then run the import.\n\n"
            f"\U0001f449 {DASHBOARD_URL}\n\n"
            "\u2014\n"
            "Automated reminder from Naxistant."
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            })
            if response.status_code != 200:
                logger.warning("Telegram API returned %d: %s", response.status_code, response.text)
            else:
                logger.info("Statement reminder sent for %s %d", month_name, year)
    except Exception as e:
        logger.error("Statement reminder failed: %s", e)
