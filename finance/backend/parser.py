import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a bank SMS parser for UAE bank messages.
Return ONLY a valid JSON object — no markdown, no explanation.

Return exactly this structure:
{
  "transaction_type": "BANK_SMS|TRANSFER|CC_PAYMENT|TRANSFER_OUT|SALARY|CHEQUE_DEPOSIT|ATM_WITHDRAWAL|CHEQUE_PAYMENT|UNKNOWN",
  "account": "Card-XXXX or digits only",
  "amount": 0.0,
  "currency": "AED",
  "value_aed": 0.0,
  "date": "MM/DD/YYYY",
  "time": "HH:MM AM/PM",
  "merchant": "name or null",
  "category": "Food & Dining|Shopping|Transport|Utilities|Healthcare|Education|Entertainment|Travel|Real Estate|Salary|Transfer|ATM Cash|Credit Card Payment|Other",
  "flow_type": "Inflow|Outflow"
}

Rules:
- Cr.Card was used → BANK_SMS, Outflow
- Cr. transaction on account → TRANSFER, Inflow/Outflow from context
- received towards Cr.Card from account → CC_PAYMENT, Inflow
- Transfer Out + Confirm → TRANSFER_OUT, Outflow
- salary mention → SALARY, Inflow
- cheque deposit → CHEQUE_DEPOSIT, Inflow
- cash withdrawal or ATM → ATM_WITHDRAWAL, Outflow
- cheque payment → CHEQUE_PAYMENT, Outflow
- Card in SMS: prefix account with Card-, use last 4 digits only
- value_aed = amount if AED, else convert with approximate rate
- Use today's date if no date found in SMS"""

def _unknown_result() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "transaction_type": "UNKNOWN",
        "account": None,
        "amount": 0.0,
        "currency": "AED",
        "value_aed": 0.0,
        "date": now.strftime("%m/%d/%Y"),
        "time": now.strftime("%I:%M %p"),
        "merchant": None,
        "category": "Other",
        "flow_type": "Outflow",
    }


async def parse_sms(sms_text: str) -> dict[str, Any]:
    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": sms_text}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r'^```[a-zA-Z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
            raw = raw.strip()
        parsed = json.loads(raw)
        if parsed.get("transaction_type") == "TRANSFER":
            parsed["merchant"] = None
            parsed["category"] = "Unknown"
        return parsed
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON: %s", raw)
        return _unknown_result()
    except Exception as e:
        logger.error("SMS parsing failed: %s", e)
        return _unknown_result()
