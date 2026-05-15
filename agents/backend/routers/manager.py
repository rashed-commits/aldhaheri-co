"""
Manager routing. Sonnet-powered.

Given an incoming user message, the manager picks one of three actions:
  - route: send the message to an existing sub-agent
  - spawn: propose creating a new specialist
  - fire:  propose dismissing an existing sub-agent (never the manager)

The frontend renders spawn/fire results as approval cards; the user gates
every mutation.
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import Agent, UserProfile
from backend.routers.auth import get_current_user
from backend.services.anthropic_client import MODEL_SONNET, async_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/manager", tags=["manager"])


MANAGER_ROUTING_SYSTEM_TEMPLATE = """\
You are the Manager of a small office of specialist agents owned by a single user.

# Soul
{manager_soul}

# USER.md
{user_md}

# Your sub-agents
{agents_block}

# Your job
Decide what to do with the user's incoming message. You have exactly three options:

1. ROUTE the message to one of the existing sub-agents above (by id), with a short framing sentence.
2. PROPOSE spawning a new specialist if no existing agent fits. Propose a NAME, a one-line SPECIALIZATION, and a short SOUL paragraph.
3. PROPOSE firing one of your sub-agents if the user is asking you to dismiss it. You can NEVER fire yourself (the manager). Only use `fire` when the user is clearly asking to remove an existing agent — never as a way to handle a substantive task.

You NEVER do the substantive work yourself.

Reply with ONLY a JSON object — no markdown, no prose, no code fences — in one of three shapes:

Route: {{"action": "route", "agent_id": <int>, "framing": "<one short sentence>"}}
Spawn: {{"action": "spawn", "proposed_agent": {{"name": "<name>", "specialization": "<one-line>", "soul": "<short paragraph>"}}, "rationale": "<one short sentence>"}}
Fire:  {{"action": "fire", "agent_id": <int>, "rationale": "<one short sentence>"}}
"""


class RouteRequest(BaseModel):
    message: str


class RouteResponse(BaseModel):
    action: str  # "route" | "spawn" | "fire"
    agent_id: Optional[int] = None
    framing: Optional[str] = None
    proposed_agent: Optional[dict] = None
    rationale: Optional[str] = None
    raw_manager_reply: str


def _build_agents_block(agents: list[Agent]) -> str:
    if not agents:
        return "(none yet — you will need to propose spawning the first specialist.)"
    return "\n".join(
        f"- id={a.id}, name={a.name!r}, specialization: {a.specialization or '(unspecified)'}"
        for a in agents
    )


def _extract_json(text: str) -> Optional[dict]:
    """Best-effort JSON extraction in case the model wrapped output in prose."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


@router.post("/route", response_model=RouteResponse)
async def route(
    body: RouteRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> RouteResponse:
    manager_result = await db.execute(select(Agent).where(Agent.role == "manager"))
    manager = manager_result.scalar_one_or_none()
    if manager is None:
        raise HTTPException(status_code=500, detail="Manager agent not seeded")

    user_result = await db.execute(select(UserProfile).where(UserProfile.id == 1))
    user_profile = user_result.scalar_one_or_none()
    user_md = user_profile.content_md if user_profile else ""

    sub_result = await db.execute(
        select(Agent)
        .where(Agent.role != "manager", Agent.deleted == False)  # noqa: E712
        .order_by(Agent.id)
    )
    sub_agents = sub_result.scalars().all()

    system_prompt = MANAGER_ROUTING_SYSTEM_TEMPLATE.format(
        manager_soul=manager.soul.strip(),
        user_md=user_md.strip() or "(empty)",
        agents_block=_build_agents_block(sub_agents),
    )

    try:
        response = await async_client.messages.create(
            model=MODEL_SONNET,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": body.message}],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Manager routing call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Manager call failed")

    raw_reply = response.content[0].text
    parsed = _extract_json(raw_reply)
    if parsed is None:
        raise HTTPException(status_code=502, detail="Manager returned unparseable response")

    action = parsed.get("action")
    if action == "route":
        return RouteResponse(
            action="route",
            agent_id=parsed.get("agent_id"),
            framing=parsed.get("framing", ""),
            raw_manager_reply=raw_reply,
        )
    if action == "spawn":
        return RouteResponse(
            action="spawn",
            proposed_agent=parsed.get("proposed_agent"),
            rationale=parsed.get("rationale", ""),
            raw_manager_reply=raw_reply,
        )
    if action == "fire":
        target_id = parsed.get("agent_id")
        target = next((a for a in sub_agents if a.id == target_id), None)
        if target is None:
            # The model picked an id that isn't a current sub-agent (could be
            # the manager itself, or a stale id). Fail safe rather than
            # surfacing a misleading approval card.
            raise HTTPException(
                status_code=502,
                detail=f"Manager proposed firing agent #{target_id}, which is not a current sub-agent",
            )
        return RouteResponse(
            action="fire",
            agent_id=target_id,
            rationale=parsed.get("rationale", ""),
            raw_manager_reply=raw_reply,
        )
    raise HTTPException(status_code=502, detail=f"Manager returned unknown action: {action}")
