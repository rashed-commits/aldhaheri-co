"""Telegram chatbot for finance — mirrors the web chatbot functionality.

Uses a SEPARATE bot token (TELEGRAM_CHATBOT_TOKEN) but the same TELEGRAM_CHAT_ID.
Runs as a long-polling background task inside the finance backend process.
"""

import asyncio
import json
import logging
import os

import anthropic
import httpx

from backend.db import async_session
from backend.models import Transaction
from backend.routers.chat import SYSTEM_PROMPT, _build_context, _parse_actions

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_CHATBOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

# Per-chat conversation history (keyed by chat_id, kept in memory)
_histories: dict[str, list[dict]] = {}
MAX_HISTORY = 20


async def _send_message(text: str, chat_id: str | None = None) -> None:
    """Send a plain-text message to Telegram."""
    target = chat_id or CHAT_ID
    async with httpx.AsyncClient(timeout=15) as http:
        await http.post(f"{API_BASE}/sendMessage", json={
            "chat_id": target,
            "text": text,
        })


async def _handle_message(text: str, chat_id: str) -> None:
    """Process an incoming message: build context, call Claude, execute actions."""
    # Reset history on command
    if text.strip().lower() in ("/clear", "/reset"):
        _histories.pop(chat_id, None)
        await _send_message("Conversation cleared.", chat_id)
        return

    async with async_session() as db:
        context = await _build_context(db, text)
        full_system = SYSTEM_PROMPT + "\n\n" + context

        # Build message history
        history = _histories.setdefault(chat_id, [])
        history.append({"role": "user", "content": text})

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=full_system,
                messages=history,
            )
            reply_text = response.content[0].text
        except anthropic.APIError as exc:
            logger.error("Anthropic API error in Telegram bot: %s", exc)
            await _send_message("Sorry, I couldn't process that right now.", chat_id)
            return

        cleaned_text, actions = _parse_actions(reply_text)

        # Save assistant reply to history
        history.append({"role": "assistant", "content": reply_text})

        # Trim history to last N messages
        if len(history) > MAX_HISTORY:
            _histories[chat_id] = history[-MAX_HISTORY:]

        # Send the text reply
        if cleaned_text:
            # Telegram has a 4096 char limit per message
            for i in range(0, len(cleaned_text), 4000):
                await _send_message(cleaned_text[i:i + 4000], chat_id)

        # Auto-execute actions and report results
        if actions:
            for action in actions:
                result = await _execute_action(db, action.type, action.payload)
                await _send_message(result, chat_id)


async def _execute_action(db, action_type: str, payload: dict) -> str:
    """Execute a chatbot action directly against the DB. Returns a status message."""
    from datetime import datetime, timezone

    try:
        if action_type == "modify":
            txn_id = payload.get("id")
            fields = payload.get("fields", {})
            if not txn_id:
                return "Could not modify — missing transaction ID."

            from sqlalchemy import select
            result = await db.execute(
                select(Transaction).where(
                    Transaction.id == txn_id, Transaction.deleted == False
                )
            )
            txn = result.scalar_one_or_none()
            if not txn:
                return f"Transaction #{txn_id} not found."

            allowed = {"category", "merchant", "account", "amount", "value_aed",
                        "date", "time", "transaction_type", "flow_type", "currency"}
            changed = []
            for key, value in fields.items():
                if key in allowed:
                    setattr(txn, key, value)
                    changed.append(f"{key} = {value}")

            await db.commit()
            return f"\u2705 Transaction #{txn_id} updated: {', '.join(changed)}"

        elif action_type == "delete":
            txn_id = payload.get("id")
            if not txn_id:
                return "Could not delete — missing transaction ID."

            from sqlalchemy import select
            result = await db.execute(
                select(Transaction).where(
                    Transaction.id == txn_id, Transaction.deleted == False
                )
            )
            txn = result.scalar_one_or_none()
            if not txn:
                return f"Transaction #{txn_id} not found."

            txn.deleted = True
            await db.commit()
            return f"\u2705 Transaction #{txn_id} deleted."

        elif action_type == "add":
            fields = payload.get("fields", {})
            required = {"transaction_type", "amount", "value_aed", "flow_type"}
            missing = required - set(fields.keys())
            if missing:
                return f"Could not add — missing fields: {', '.join(sorted(missing))}"

            txn = Transaction(
                sms_raw=f"[manual] Added via Telegram on {datetime.now(timezone.utc).isoformat()}",
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
            return f"\u2705 Transaction #{txn.id} created ({fields.get('merchant', 'Unknown')}, AED {txn.value_aed:,.2f})"

        else:
            return f"Unknown action type: {action_type}"

    except Exception as exc:
        logger.error("Telegram action execution error: %s", exc)
        return f"Error executing action: {exc}"


async def poll_loop() -> None:
    """Long-poll the Telegram Bot API for new messages."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram chatbot not configured (TELEGRAM_CHATBOT_TOKEN or TELEGRAM_CHAT_ID missing)")
        return

    logger.info("Telegram chatbot polling started (chat_id=%s)", CHAT_ID)
    offset = 0

    async with httpx.AsyncClient(timeout=60) as http:
        while True:
            try:
                resp = await http.get(f"{API_BASE}/getUpdates", params={
                    "offset": offset,
                    "timeout": 30,
                    "allowed_updates": '["message"]',
                })
                data = resp.json()

                if not data.get("ok"):
                    logger.warning("Telegram getUpdates error: %s", data)
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    # Only respond to the configured chat
                    if chat_id != CHAT_ID or not text:
                        continue

                    # Process in background so polling continues
                    asyncio.create_task(_handle_message(text, chat_id))

            except httpx.ReadTimeout:
                # Normal for long polling — just retry
                continue
            except Exception as exc:
                logger.error("Telegram poll error: %s", exc)
                await asyncio.sleep(5)
