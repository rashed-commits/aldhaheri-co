"""
Builds the per-agent system prompt in the documented order:

    SOUL -> USER.md -> AGENT_MEMORY -> SKILL (if matched) -> TASK

HISTORY is the responsibility of the caller (passed via Anthropic messages=...),
but conceptually it is the final layer of context the agent sees on each call.
"""

import json
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Agent, AgentMemory, AgentSkill, UserProfile


SECTION_DIVIDER = "\n\n---\n\n"


async def get_user_profile_md(session: AsyncSession) -> str:
    result = await session.execute(select(UserProfile).where(UserProfile.id == 1))
    row = result.scalar_one_or_none()
    return row.content_md if row else ""


async def get_latest_memory_md(session: AsyncSession, agent_id: int) -> str:
    result = await session.execute(
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(desc(AgentMemory.version))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row.content_md if row else ""


def format_skill_block(skill: AgentSkill) -> str:
    parts = [f"# Skill: {skill.name}"]
    if skill.description:
        parts.append(skill.description)
    if skill.frontmatter_yaml:
        parts.append("```yaml\n" + skill.frontmatter_yaml.strip() + "\n```")
    if skill.instructions_md:
        parts.append(skill.instructions_md.strip())
    return "\n\n".join(parts)


async def assemble_system_prompt(
    session: AsyncSession,
    agent: Agent,
    skill: Optional[AgentSkill] = None,
    task_framing: str = "",
) -> str:
    """Compose the system prompt: SOUL -> USER -> MEMORY -> SKILL -> TASK."""
    sections: list[str] = []

    if agent.soul:
        sections.append("# Soul\n\n" + agent.soul.strip())

    user_md = await get_user_profile_md(session)
    if user_md.strip():
        sections.append("# USER.md\n\n" + user_md.strip())

    memory_md = await get_latest_memory_md(session, agent.id)
    if memory_md.strip():
        sections.append("# Agent memory\n\n" + memory_md.strip())

    if skill is not None and not skill.deleted:
        sections.append(format_skill_block(skill))

    if task_framing.strip():
        sections.append("# Current task\n\n" + task_framing.strip())

    return SECTION_DIVIDER.join(sections)


def parse_history_to_messages(transcript_json: str) -> list[dict]:
    """Convert stored transcript JSON into Anthropic-shaped messages."""
    try:
        turns = json.loads(transcript_json or "[]")
    except json.JSONDecodeError:
        return []
    return [
        {"role": t["role"], "content": t["content"]}
        for t in turns
        if t.get("role") in ("user", "assistant") and t.get("content")
    ]
