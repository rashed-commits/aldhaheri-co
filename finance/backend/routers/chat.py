import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import Transaction, TransactionOut
from backend.routers.transactions import verify_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

SYSTEM_PROMPT = """\
You are a personal finance assistant for a UAE-based user. You help them \
understand their spending, analyse trends, and manage their transaction records.

You have access to their full transaction database. All monetary amounts are in AED \
(UAE Dirhams) unless stated otherwise.

Your capabilities:
- Analyse spending patterns, trends, and anomalies
- Answer questions about specific transactions, merchants, or categories
- Compare spending across time periods, accounts, or categories
- Provide budgeting advice based on actual spending data
- Modify, delete, or add transactions when the user requests it

When the user asks you to **modify**, **delete**, or **add** a transaction, you MUST \
return a structured action block in your response so the frontend can execute it. \
Wrap the action in <action>...</action> tags containing valid JSON.

Action formats:

To modify a transaction:
<action>{"type": "modify", "id": 123, "fields": {"category": "Groceries", "merchant": "Carrefour"}}</action>

To delete a transaction (soft-delete):
<action>{"type": "delete", "id": 123}</action>

To add a new transaction:
<action>{"type": "add", "fields": {"transaction_type": "Purchase", "account": "ADCB Credit", "amount": 150.0, "currency": "AED", "value_aed": 150.0, "date": "03/15/2026", "time": "14:30", "merchant": "Carrefour", "category": "Groceries", "flow_type": "Outflow"}}</action>

Rules for actions:
- Always explain what you are about to do BEFORE the action block
- Ask for confirmation if the request is ambiguous or affects multiple transactions
- For modify, only include the fields that need changing
- For delete, only include the transaction id
- For add, include all required fields (transaction_type, account, amount, currency, \
value_aed, date, merchant, category, flow_type)
- You may include multiple action blocks if the user requests bulk changes

Keep responses concise and use AED formatting (e.g. AED 1,234.56). Use tables or \
bullet points for clarity when listing transactions or comparisons.
"""


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ActionItem(BaseModel):
    type: str
    payload: dict
    description: str


class ChatResponse(BaseModel):
    response: str
    actions: list[ActionItem]


class ExecuteRequest(BaseModel):
    action_type: str
    payload: dict


class ExecuteResponse(BaseModel):
    status: str
    transaction: Optional[TransactionOut] = None
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_actions(text: str) -> tuple[str, list[ActionItem]]:
    """Extract <action>...</action> blocks from Claude's response."""
    pattern = re.compile(r"<action>(.*?)</action>", re.DOTALL)
    actions: list[ActionItem] = []

    for match in pattern.finditer(text):
        try:
            data = json.loads(match.group(1).strip())
            action_type = data.get("type", "unknown")
            description_parts = []
            if action_type == "modify":
                description_parts.append(f"Modify transaction #{data.get('id')}")
                fields = data.get("fields", {})
                if fields:
                    description_parts.append(f"— set {', '.join(f'{k}={v}' for k, v in fields.items())}")
            elif action_type == "delete":
                description_parts.append(f"Delete transaction #{data.get('id')}")
            elif action_type == "add":
                fields = data.get("fields", {})
                description_parts.append(
                    f"Add {fields.get('flow_type', 'Outflow')} of AED {fields.get('value_aed', 0):.2f}"
                    f" at {fields.get('merchant', 'Unknown')}"
                )
            else:
                description_parts.append(f"Unknown action: {action_type}")

            actions.append(ActionItem(
                type=action_type,
                payload=data,
                description=" ".join(description_parts),
            ))
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse action block: %s", exc)

    cleaned = pattern.sub("", text).strip()
    return cleaned, actions


async def _build_context(db: AsyncSession, user_message: str) -> str:
    """Query the DB and build a <context> block for the system prompt."""
    base = Transaction.deleted == False  # noqa: E712

    # Total count
    count_result = await db.execute(select(func.count(Transaction.id)).where(base))
    total_count = count_result.scalar() or 0

    # Inflow / outflow totals
    inflow_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.value_aed), 0)).where(
            base, Transaction.flow_type == "Inflow"
        )
    )
    total_inflow = inflow_result.scalar() or 0.0

    outflow_result = await db.execute(
        select(func.coalesce(func.sum(Transaction.value_aed), 0)).where(
            base, Transaction.flow_type == "Outflow"
        )
    )
    total_outflow = outflow_result.scalar() or 0.0

    # Top 5 spend categories
    cat_stmt = (
        select(Transaction.category, func.sum(Transaction.value_aed).label("total"))
        .where(base, Transaction.flow_type == "Outflow")
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.value_aed).desc())
        .limit(5)
    )
    cat_result = await db.execute(cat_stmt)
    top_categories = [{"category": r[0], "total": round(r[1], 2)} for r in cat_result.all()]

    # Recent 20 transactions
    recent_stmt = (
        select(Transaction)
        .where(base)
        .order_by(Transaction.id.desc())
        .limit(20)
    )
    recent_result = await db.execute(recent_stmt)
    recent_rows = recent_result.scalars().all()
    recent_txns = [
        {
            "id": t.id,
            "date": t.date,
            "account": t.account,
            "amount": t.value_aed,
            "merchant": t.merchant,
            "category": t.category,
            "flow_type": t.flow_type,
        }
        for t in recent_rows
    ]

    # Targeted search if the user mentions a merchant, category, or amount
    targeted_results: list[dict] = []
    msg_lower = user_message.lower()

    # Search by merchant name (partial match)
    merchant_stmt = (
        select(Transaction)
        .where(base, func.lower(Transaction.merchant).contains(msg_lower))
        .order_by(Transaction.id.desc())
        .limit(10)
    )
    merchant_result = await db.execute(merchant_stmt)
    merchant_rows = merchant_result.scalars().all()
    if merchant_rows:
        targeted_results.extend(
            {
                "id": t.id, "date": t.date, "account": t.account,
                "amount": t.value_aed, "merchant": t.merchant,
                "category": t.category, "flow_type": t.flow_type,
                "match": "merchant",
            }
            for t in merchant_rows
        )

    # Search by category (partial match)
    cat_search_stmt = (
        select(Transaction)
        .where(base, func.lower(Transaction.category).contains(msg_lower))
        .order_by(Transaction.id.desc())
        .limit(10)
    )
    cat_search_result = await db.execute(cat_search_stmt)
    cat_search_rows = cat_search_result.scalars().all()
    if cat_search_rows:
        targeted_results.extend(
            {
                "id": t.id, "date": t.date, "account": t.account,
                "amount": t.value_aed, "merchant": t.merchant,
                "category": t.category, "flow_type": t.flow_type,
                "match": "category",
            }
            for t in cat_search_rows
        )

    # Search by amount if the message contains a number
    amount_matches = re.findall(r"[\d,]+\.?\d*", user_message.replace(",", ""))
    for amt_str in amount_matches[:2]:
        try:
            amt = float(amt_str)
            if amt > 0:
                amt_stmt = (
                    select(Transaction)
                    .where(base, Transaction.value_aed == amt)
                    .order_by(Transaction.id.desc())
                    .limit(5)
                )
                amt_result = await db.execute(amt_stmt)
                amt_rows = amt_result.scalars().all()
                targeted_results.extend(
                    {
                        "id": t.id, "date": t.date, "account": t.account,
                        "amount": t.value_aed, "merchant": t.merchant,
                        "category": t.category, "flow_type": t.flow_type,
                        "match": "amount",
                    }
                    for t in amt_rows
                )
        except ValueError:
            pass

    context_parts = [
        f"Total active transactions: {total_count}",
        f"Total inflow: AED {total_inflow:,.2f}",
        f"Total outflow: AED {total_outflow:,.2f}",
        f"Net: AED {total_inflow - total_outflow:,.2f}",
        "",
        "Top 5 spending categories:",
        json.dumps(top_categories, indent=2),
        "",
        "Recent 20 transactions:",
        json.dumps(recent_txns, indent=2),
    ]

    if targeted_results:
        # Deduplicate by id
        seen_ids: set[int] = set()
        unique: list[dict] = []
        for item in targeted_results:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                unique.append(item)
        context_parts.extend([
            "",
            f"Targeted search results ({len(unique)} matches):",
            json.dumps(unique, indent=2),
        ])

    return "<context>\n" + "\n".join(context_parts) + "\n</context>"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request_body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> ChatResponse:
    """Send a message to the finance chatbot and get a response with optional actions."""
    context = await _build_context(db, request_body.message)

    full_system = SYSTEM_PROMPT + "\n\n" + context

    messages: list[dict] = []
    for msg in request_body.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": request_body.message})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=full_system,
            messages=messages,
        )
        reply_text = response.content[0].text
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to get response from AI")

    cleaned_text, actions = _parse_actions(reply_text)

    return ChatResponse(response=cleaned_text, actions=actions)


@router.post("/chat/execute", response_model=ExecuteResponse)
async def execute_action(
    request_body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> ExecuteResponse:
    """Execute a structured action (modify/delete/add) returned by the chatbot."""
    action_type = request_body.action_type
    payload = request_body.payload

    if action_type == "modify":
        txn_id = payload.get("id")
        fields = payload.get("fields", {})
        if not txn_id:
            raise HTTPException(status_code=400, detail="Missing transaction id")

        result = await db.execute(
            select(Transaction).where(Transaction.id == txn_id, Transaction.deleted == False)
        )
        txn = result.scalar_one_or_none()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        allowed_fields = {"category", "merchant", "account", "amount", "value_aed",
                          "date", "time", "transaction_type", "flow_type", "currency"}
        for key, value in fields.items():
            if key in allowed_fields:
                setattr(txn, key, value)

        await db.commit()
        await db.refresh(txn)
        return ExecuteResponse(
            status="ok",
            transaction=TransactionOut.model_validate(txn),
            message=f"Transaction #{txn_id} updated successfully",
        )

    elif action_type == "delete":
        txn_id = payload.get("id")
        if not txn_id:
            raise HTTPException(status_code=400, detail="Missing transaction id")

        result = await db.execute(
            select(Transaction).where(Transaction.id == txn_id, Transaction.deleted == False)
        )
        txn = result.scalar_one_or_none()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        txn.deleted = True
        await db.commit()
        return ExecuteResponse(
            status="ok",
            transaction=None,
            message=f"Transaction #{txn_id} deleted",
        )

    elif action_type == "add":
        fields = payload.get("fields", {})
        required = {"transaction_type", "amount", "value_aed", "flow_type"}
        missing = required - set(fields.keys())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(sorted(missing))}",
            )

        txn = Transaction(
            sms_raw=f"[manual] Added via chat on {datetime.now(timezone.utc).isoformat()}",
            transaction_type=fields.get("transaction_type", "Purchase"),
            account=fields.get("account"),
            amount=float(fields.get("amount", 0)),
            currency=fields.get("currency", "AED"),
            value_aed=float(fields.get("value_aed", 0)),
            date=fields.get("date"),
            time=fields.get("time"),
            merchant=fields.get("merchant"),
            category=fields.get("category", "Other"),
            flow_type=fields.get("flow_type", "Outflow"),
            deleted=False,
        )
        db.add(txn)
        await db.commit()
        await db.refresh(txn)
        return ExecuteResponse(
            status="ok",
            transaction=TransactionOut.model_validate(txn),
            message=f"Transaction #{txn.id} created",
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action type: {action_type}")
