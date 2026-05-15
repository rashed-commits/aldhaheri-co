"""
Translate natural-language schedule descriptions into 5-field cron strings
via Haiku, then validate via APScheduler's CronTrigger.from_crontab.
"""

import json
import logging

from apscheduler.triggers.cron import CronTrigger

from backend.services.anthropic_client import MODEL_HAIKU, async_client

logger = logging.getLogger(__name__)


NL_SCHEDULE_SYSTEM = """\
You translate natural-language schedule descriptions into 5-field cron strings.

Format: "minute hour day-of-month month day-of-week" (UTC).

Day-of-week: 0=Sun, 1=Mon ... 6=Sat. Always emit 5 fields, space-separated.

Examples:
- "every Monday at 9am"   -> "0 9 * * 1"
- "weekdays at 6:30am"    -> "30 6 * * 1-5"
- "1st of every month"    -> "0 0 1 * *"
- "every 15 minutes"      -> "*/15 * * * *"

Reply with ONLY a JSON object (no markdown, no prose, no code fences):
{"cron_expr": "<5-field cron string>", "explanation": "<one short plain-English summary>"}

If the input is ambiguous or unparseable, return:
{"cron_expr": null, "explanation": "<one short sentence explaining why>"}
"""


async def parse_nl_schedule(nl: str) -> dict:
    """Returns {cron_expr: str|None, explanation: str}."""
    try:
        response = await async_client.messages.create(
            model=MODEL_HAIKU,
            max_tokens=256,
            system=NL_SCHEDULE_SYSTEM,
            messages=[{"role": "user", "content": nl}],
        )
        raw = response.content[0].text.strip()
        parsed = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("NL schedule parse failed: %s", exc)
        return {"cron_expr": None, "explanation": "Could not parse the schedule."}

    cron_expr = parsed.get("cron_expr")
    explanation = parsed.get("explanation", "")

    if cron_expr is None:
        return {"cron_expr": None, "explanation": explanation or "Could not parse."}

    try:
        CronTrigger.from_crontab(cron_expr)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Haiku produced invalid cron expression %r: %s", cron_expr, exc)
        return {"cron_expr": None, "explanation": f"Generated cron string was invalid: {exc}"}

    return {"cron_expr": cron_expr, "explanation": explanation}
