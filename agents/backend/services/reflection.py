"""
Self-improving loop. After every assistant turn this fires (async, non-blocking)
and writes pending proposals to the `proposals` table. User accepts or rejects
via the proposals router; nothing persists to memory or skills without consent.

Per locked design:
- Every turn classifies a task_type label and writes a Task row.
- Memory proposals are best-effort and may be empty.
- Skill proposals trigger only on the 2nd occurrence of the same task_type
  for this agent AND only when no existing skill is named the same.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import async_session
from backend.models import Agent, AgentMemory, AgentSkill, Proposal, Task, UserProfile
from backend.services.anthropic_client import MODEL_HAIKU, async_client
from backend.services.json_utils import parse_model_json

logger = logging.getLogger(__name__)


REFLECTION_SYSTEM = """\
You are the reflection module for an agent in a personal AI office.

You review one exchange (user message + assistant response) and produce:

1. task_type — a 2-4 word snake_case label classifying the work just done.
2. memory_proposal — full replacement MEMORY.md if something noteworthy
   was learned that should persist across sessions. Null otherwise.
3. skill_proposal — a procedural playbook for this kind of task. Propose
   ONLY when the task_type has appeared in the agent's recent task history
   AND no existing skill already covers it. Null otherwise.

The user gates every proposal — be conservative. Better to propose nothing
than to propose noisy or repetitive memory.

Reply with raw JSON only. Do NOT wrap in ```json``` code fences. Do not add any
prose before or after. The very first character of your reply must be `{` and
the very last must be `}`.

{
  "task_type": "<snake_case>",
  "memory_proposal": null | {"proposed_md": "<full new MEMORY.md>", "rationale": "<one sentence>"},
  "skill_proposal": null | {
    "name": "<short title>",
    "slug": "<kebab-case>",
    "description": "<one sentence>",
    "trigger_keywords": ["k1", "k2"],
    "frontmatter_yaml": "<optional YAML block as a string>",
    "instructions_md": "<the playbook body in markdown>",
    "rationale": "<one sentence>"
  }
}
"""


async def _fetch_reflection_context(db: AsyncSession, agent_id: int) -> dict:
    agent_res = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_res.scalar_one()

    mem_res = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(desc(AgentMemory.version))
        .limit(1)
    )
    latest_mem = mem_res.scalar_one_or_none()
    current_memory_md = latest_mem.content_md if latest_mem else ""

    tasks_res = await db.execute(
        select(Task.task_type)
        .where(Task.agent_id == agent_id, Task.task_type.is_not(None))
        .order_by(desc(Task.created_at))
        .limit(20)
    )
    recent_task_types = [r[0] for r in tasks_res.all()]

    skills_res = await db.execute(
        select(AgentSkill).where(
            AgentSkill.agent_id == agent_id,
            AgentSkill.deleted == False,  # noqa: E712
        )
    )
    existing_skill_names = [s.name for s in skills_res.scalars().all()]

    return {
        "agent": {
            "name": agent.name,
            "soul": agent.soul,
            "specialization": agent.specialization,
        },
        "current_memory_md": current_memory_md,
        "recent_task_types": recent_task_types,
        "existing_skill_names": existing_skill_names,
    }


async def queue_reflection(
    agent_id: int,
    session_id: int,
    user_message: str,
    assistant_text: str,
) -> None:
    """Run reflection in the background. Persists Task + optional Proposals."""
    try:
        async with async_session() as db:
            ctx = await _fetch_reflection_context(db, agent_id)

            payload = {
                "agent": ctx["agent"],
                "current_memory_md": ctx["current_memory_md"],
                "recent_task_types": ctx["recent_task_types"],
                "existing_skill_names": ctx["existing_skill_names"],
                "user_message": user_message,
                "assistant_response": assistant_text,
            }

            response = await async_client.messages.create(
                model=MODEL_HAIKU,
                max_tokens=2048,
                system=REFLECTION_SYSTEM,
                messages=[{"role": "user", "content": json.dumps(payload)}],
            )
            raw = response.content[0].text.strip()
            parsed = parse_model_json(raw)
            if parsed is None:
                logger.warning("Reflection returned unparseable JSON; raw=%s", raw[:200])
                return

            task_type = (parsed.get("task_type") or "unspecified").strip().lower()

            db.add(Task(
                agent_id=agent_id,
                title=user_message[:120],
                description=user_message,
                task_type=task_type,
                status="done",
                result=assistant_text[:500],
                origin="manual",
                session_id=session_id,
            ))

            mem_prop = parsed.get("memory_proposal")
            if mem_prop and isinstance(mem_prop, dict) and mem_prop.get("proposed_md"):
                # Look up the auto-accept flag — when on, memory proposals
                # are applied immediately and the proposal row is marked
                # accepted in the same transaction. Skill proposals are
                # always user-gated regardless.
                up_res = await db.execute(select(UserProfile).where(UserProfile.id == 1))
                user_prof = up_res.scalar_one_or_none()
                auto_accept = bool(user_prof and user_prof.auto_accept_memory)

                proposal = Proposal(
                    agent_id=agent_id,
                    session_id=session_id,
                    kind="memory_update",
                    current_snapshot=ctx["current_memory_md"],
                    proposed_snapshot=mem_prop["proposed_md"],
                    rationale=mem_prop.get("rationale", ""),
                    status="accepted" if auto_accept else "pending",
                    resolved_at=datetime.now(timezone.utc) if auto_accept else None,
                )
                db.add(proposal)

                if auto_accept:
                    await db.flush()  # populate proposal.id for the FK
                    latest_v = await db.execute(
                        select(func.max(AgentMemory.version)).where(
                            AgentMemory.agent_id == agent_id
                        )
                    )
                    next_version = (latest_v.scalar() or 0) + 1
                    db.add(AgentMemory(
                        agent_id=agent_id,
                        content_md=mem_prop["proposed_md"],
                        version=next_version,
                        source="proposal_accepted",
                        source_proposal_id=proposal.id,
                    ))

            skill_prop = parsed.get("skill_proposal")
            if skill_prop and isinstance(skill_prop, dict) and skill_prop.get("name"):
                # 2nd-occurrence trigger: the task_type must have appeared
                # in the agent's recent history before this turn.
                if task_type in ctx["recent_task_types"]:
                    db.add(Proposal(
                        agent_id=agent_id,
                        session_id=session_id,
                        kind="new_skill",
                        current_snapshot="",
                        proposed_snapshot=json.dumps(skill_prop),
                        rationale=skill_prop.get("rationale", ""),
                        status="pending",
                    ))

            await db.commit()
            logger.info(
                "reflection done: agent=%d session=%d task_type=%s",
                agent_id, session_id, task_type,
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Reflection failed for agent=%d session=%d: %s", agent_id, session_id, exc
        )
