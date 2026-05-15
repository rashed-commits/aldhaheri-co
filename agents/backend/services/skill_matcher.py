"""
Haiku-based skill matcher. Given an agent's active skills and the user's
current message, picks the single best skill (or None) to inject this turn.
"""

import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AgentSkill
from backend.services.anthropic_client import MODEL_HAIKU, async_client

logger = logging.getLogger(__name__)


SKILL_MATCHER_SYSTEM = """\
You match user messages to procedural playbooks ("skills") owned by an agent.

You will be given:
- a JSON list of available skills with id, name, description, trigger_keywords
- the user's current message

Pick the single best skill, or null if none clearly fit.

Reply with ONLY a JSON object (no markdown, no prose, no code fences):
{"skill_id": <int or null>, "reason": "<one short sentence>"}
"""


async def match_skill(
    session: AsyncSession,
    agent_id: int,
    user_message: str,
) -> Optional[AgentSkill]:
    """Return the best-matching active skill for an agent, or None."""
    result = await session.execute(
        select(AgentSkill).where(
            AgentSkill.agent_id == agent_id,
            AgentSkill.deleted == False,  # noqa: E712
        )
    )
    skills = result.scalars().all()
    if not skills:
        return None

    skill_summaries = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "trigger_keywords": s.trigger_keywords,
        }
        for s in skills
    ]

    payload = {
        "available_skills": skill_summaries,
        "user_message": user_message,
    }

    try:
        response = await async_client.messages.create(
            model=MODEL_HAIKU,
            max_tokens=256,
            system=SKILL_MATCHER_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = response.content[0].text.strip()
        parsed = json.loads(text)
        skill_id = parsed.get("skill_id")
        if skill_id is None:
            return None
        for s in skills:
            if s.id == skill_id:
                return s
    except Exception as exc:  # noqa: BLE001
        logger.warning("Skill matcher failed: %s", exc)
    return None
