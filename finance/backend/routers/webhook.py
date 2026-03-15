import os
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import Transaction, TransactionOut
from backend.notifications import send_telegram_notification
from backend.parser import parse_sms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

WEBHOOK_API_KEY = os.getenv("WEBHOOK_API_KEY", "")


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

    parsed = await parse_sms(sms_text)

    txn = Transaction(
        sms_raw=sms_text,
        transaction_type=parsed.get("transaction_type", "UNKNOWN"),
        account=parsed.get("account"),
        amount=parsed.get("amount", 0.0),
        currency=parsed.get("currency", "AED"),
        value_aed=parsed.get("value_aed", 0.0),
        date=parsed.get("date"),
        time=parsed.get("time"),
        merchant=parsed.get("merchant"),
        category=parsed.get("category", "Other"),
        flow_type=parsed.get("flow_type", "Outflow"),
    )
    db.add(txn)
    await db.commit()
    await db.refresh(txn)

    logger.info("Stored transaction %d: %s", txn.id, txn.transaction_type)

    try:
        await send_telegram_notification(txn)
    except Exception as e:
        logger.error("Telegram notification error: %s", e)

    return {"status": "ok", "transaction_id": txn.id}
