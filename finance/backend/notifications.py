import logging
import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_CHATBOT_TOKEN", "")
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
            f"\U0001f449 {DASHBOARD_URL}"
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
            f"\U0001f449 {DASHBOARD_URL}"
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


async def send_duplicate_alert(new_txn, existing_txn) -> None:
    """Alert user about a suspected repeat transaction on Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        amount_str = f"{new_txn.currency} {new_txn.amount:,.2f}"
        message = (
            "\u26a0\ufe0f Suspected Repeat Transaction\n\n"
            f"A new transaction looks like a duplicate of an existing one:\n\n"
            f"NEW (#{new_txn.id}):\n"
            f"  Merchant: {new_txn.merchant}\n"
            f"  Amount: {amount_str}\n"
            f"  Date: {new_txn.date} at {new_txn.time or 'N/A'}\n"
            f"  Account: {new_txn.account or 'N/A'}\n\n"
            f"EXISTING (#{existing_txn.id}):\n"
            f"  Merchant: {existing_txn.merchant}\n"
            f"  Amount: {existing_txn.currency} {existing_txn.amount:,.2f}\n"
            f"  Date: {existing_txn.date} at {existing_txn.time or 'N/A'}\n"
            f"  Account: {existing_txn.account or 'N/A'}\n\n"
            "If this is a duplicate, delete it from the dashboard "
            "or tell the chatbot: \"delete transaction #"
            f"{new_txn.id}\"\n\n"
            f"\U0001f449 {DASHBOARD_URL}"
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
        logger.error("Duplicate alert failed: %s", e)


async def send_transfer_help_request(txn) -> None:
    """Ask the user on Telegram to categorize a transfer."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        amount_str = f"{txn.currency} {txn.amount:,.2f}"
        merchant_line = f"Recipient: {txn.merchant}\n" if txn.merchant else ""
        message = (
            "\U0001f4b8 Transfer — Please categorize\n\n"
            f"Amount: {amount_str}\n"
            f"{merchant_line}"
            f"Account: {txn.account or 'N/A'}\n"
            f"Date: {txn.date} at {txn.time or 'N/A'}\n"
            f"Transaction #{txn.id}\n\n"
            "Please update the category on the dashboard.\n\n"
            f"\U0001f449 {DASHBOARD_URL}"
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
        logger.error("Transfer help request failed: %s", e)


async def send_balance_imbalance_alert(category: str, inflow: float, outflow: float) -> None:
    """Warn user when Internal Transfers or CC Payments inflow != outflow."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        diff = abs(inflow - outflow)
        message = (
            "\u26a0\ufe0f Balance Imbalance — {category}\n\n"
            f"Total Inflow:  AED {inflow:,.2f}\n"
            f"Total Outflow: AED {outflow:,.2f}\n"
            f"Difference:    AED {diff:,.2f}\n\n"
            "These should be balanced. Please review on the dashboard.\n\n"
            f"\U0001f449 {DASHBOARD_URL}"
        ).replace("{category}", category)

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
            })
            if response.status_code != 200:
                logger.warning("Telegram API returned %d: %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Balance imbalance alert failed: %s", e)


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
            f"\U0001f449 {DASHBOARD_URL}"
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
            f"\U0001f449 {DASHBOARD_URL}"
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
