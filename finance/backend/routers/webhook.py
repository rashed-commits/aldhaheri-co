import os
import logging
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import Transaction, TransactionOut
from backend.notifications import send_telegram_notification, send_category_help_request, send_duplicate_alert
from backend.parser import parse_sms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")

UNCATEGORIZED = {"Other", "Unidentified", "Unknown"}


async def lookup_category_by_merchant(
    db: AsyncSession, merchant: str,
) -> str | None:
    """Find the most common category for a merchant from previous transactions."""
    if not merchant:
        return None
    result = await db.execute(
        select(Transaction.category, func.count(Transaction.id).label("cnt"))
        .where(
            func.upper(Transaction.merchant) == merchant.upper(),
            Transaction.deleted == False,
            Transaction.category.notin_(UNCATEGORIZED),
        )
        .group_by(Transaction.category)
        .order_by(func.count(Transaction.id).desc())
        .limit(1)
    )
    row = result.first()
    return row[0] if row else None


def verify_webhook_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != WEBHOOK_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@router.post("/sms", response_model=dict)
async def receive_sms(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_webhook_key),
) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        sms_text = body.get("sms", "")
    else:
        form = await request.form()
        sms_text = form.get("sms", "")

    if not sms_text:
        raise HTTPException(status_code=400, detail="No SMS text provided")

    if sms_text.startswith("{") and sms_text.endswith("}") and " " not in sms_text:
        raise HTTPException(status_code=400, detail="Unresolved Tasker variable")

    if len(sms_text) < 10:
        raise HTTPException(status_code=400, detail="SMS text too short to be valid")

    failed_keywords = ["failed", "declined", "rejected", "unsuccessful", "not completed"]
    sms_lower = sms_text.lower()
    if any(kw in sms_lower for kw in failed_keywords):
        logger.info("Skipped failed transaction SMS: %s", sms_text[:80])
        return {"status": "skipped", "reason": "failed transaction"}

    existing = await db.execute(
        select(Transaction.id).where(
            Transaction.sms_raw == sms_text,
            Transaction.deleted == False,
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Skipped duplicate SMS: %s", sms_text[:80])
        return {"status": "skipped", "reason": "duplicate SMS"}

    parsed = await parse_sms(sms_text)

    # Skip zero-amount transactions
    if parsed.get("amount", 0.0) == 0 and parsed.get("value_aed", 0.0) == 0:
        logger.info("Skipped zero-amount transaction: %s", sms_text[:80])
        return {"status": "skipped", "reason": "zero amount"}

    # Normalize account names
    account = parsed.get("account") or ""
    account_map = {"XXX810002": "810002", "XXX920001": "920001"}
    account = account_map.get(account, account)

    # For transfers, extract recipient as merchant
    merchant = parsed.get("merchant")
    category = parsed.get("category", "Other")
    txn_type = parsed.get("transaction_type", "UNKNOWN")
    if txn_type in ("TRANSFER", "TRANSFER_OUT") and not merchant:
        m = re.search(r"TRF OUT TO (.+?)(?:\s*$)", sms_text)
        if m:
            merchant = m.group(1).strip()

    # --- Category resolution (priority order) ---
    # 1. Cross-reference previous transactions for this merchant
    from backend.categorizer import categorize

    history_category = await lookup_category_by_merchant(db, merchant) if merchant else None
    if history_category:
        category = history_category
        logger.info("Category from merchant history: %s -> %s", merchant, category)
    else:
        # 2. Keyword categorizer
        cat_merchant, cat_category = categorize(sms_text, parsed.get("flow_type", "Outflow"))
        if cat_category != "Other":
            category = cat_category
            if not merchant:
                merchant = cat_merchant
            logger.info("Category from keyword categorizer: %s -> %s", merchant, category)
        # 3. Otherwise keep Claude's category guess from parser.py

    needs_help = category in UNCATEGORIZED

    txn = Transaction(
        sms_raw=sms_text,
        transaction_type=txn_type,
        account=account,
        amount=parsed.get("amount", 0.0),
        currency=parsed.get("currency", "AED"),
        value_aed=parsed.get("value_aed", 0.0),
        date=parsed.get("date"),
        time=parsed.get("time"),
        merchant=merchant,
        category=category,
        flow_type=parsed.get("flow_type", "Outflow"),
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    logger.info("Stored transaction %d: %s", txn.id, txn.transaction_type)

    # Check for suspected repeat transaction (same merchant + amount + date)
    suspected_duplicate = None
    if merchant and txn.date and txn.amount:
        dup_result = await db.execute(
            select(Transaction).where(
                Transaction.id != txn.id,
                Transaction.deleted == False,
                func.upper(Transaction.merchant) == merchant.upper(),
                Transaction.amount == txn.amount,
                Transaction.date == txn.date,
            ).limit(1)
        )
        suspected_duplicate = dup_result.scalar_one_or_none()

    try:
        await send_telegram_notification(txn)
        if suspected_duplicate:
            await send_duplicate_alert(txn, suspected_duplicate)
        # 4. If still uncategorized after all attempts, ask on Telegram
        elif needs_help and merchant:
            await send_category_help_request(merchant, txn)
    except Exception as e:
        logger.error("Telegram notification error: %s", e)

    return {"status": "ok", "transaction_id": txn.id}
