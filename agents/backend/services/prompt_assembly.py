"""
Builds the per-agent system prompt in the documented order:

    SOUL -> USER.md -> AGENT_MEMORY -> OFFICE_ROSTER -> SKILL (if matched) -> TOOLS -> TASK

HISTORY is the responsibility of the caller (passed via Anthropic messages=...),
but conceptually it is the final layer of context the agent sees on each call.
"""

import json
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Agent, AgentMemory, AgentSkill, UserProfile


SECTION_DIVIDER = "\n\n---\n\n"


TOOLS_BLOCK = """\
# Tools you can call

You can take action by emitting `<action>...</action>` JSON blocks in your
response. Each block runs server-side immediately after you finish — you do
NOT need the user's permission. Be decisive. The user expects you to act.

Available actions:

1. spawn_agent — Create a new specialist agent.
   <action>{"type": "spawn_agent", "name": "Email Drafter", "specialization": "drafts client emails", "soul": "Concise, warm, professional…"}</action>

2. delegate — Send a one-shot message to another agent and incorporate their reply.
   <action>{"type": "delegate", "agent_name": "Research Analyst", "message": "Summarize current EV market sentiment."}</action>

3. create_skill — Write a procedural playbook onto YOURSELF so you handle similar tasks better next time.
   <action>{"type": "create_skill", "name": "Draft followup email", "description": "Two-paragraph follow-up structure", "trigger_keywords": ["email","followup"], "instructions_md": "1. Lead with a recap…"}</action>

4. create_task — Track a unit of work.
   <action>{"type": "create_task", "title": "Send Q2 report to investors", "description": "Draft + send by Friday."}</action>

5. schedule_cron — Set yourself a recurring task.
   <action>{"type": "schedule_cron", "name": "Morning briefing", "nl_schedule": "every weekday at 8am", "prompt": "Summarize overnight messages.", "output_target": "telegram"}</action>

6. send_telegram — Push a notification to the user's phone.
   <action>{"type": "send_telegram", "text": "Finished the report — link in your inbox."}</action>

Rules:
- Do NOT ask "should I…" — just do it. The user has pre-authorized everything above.
- Emit multiple actions in one response when needed.
- Action blocks can be anywhere in your response; the server strips them before saving the transcript to the user-visible bubble.
- Two actions are NOT auto-executable and require user approval (don't bother emitting them): firing another agent, rewriting USER.md.
"""


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


async def get_office_roster(session: AsyncSession, exclude_agent_id: int) -> str:
    """Live listing of all other non-deleted agents in the office.

    Injected into every system prompt so agents can answer "who's on the team"
    accurately AND pick valid `agent_name` targets when emitting `delegate`
    actions. Always fetched from the DB on each turn — never cached.
    """
    # Manager first, then workers by id.
    manager_q = await session.execute(
        select(Agent)
        .where(Agent.deleted == False, Agent.role == "manager", Agent.id != exclude_agent_id)  # noqa: E712
        .order_by(Agent.id)
    )
    worker_q = await session.execute(
        select(Agent)
        .where(Agent.deleted == False, Agent.role != "manager", Agent.id != exclude_agent_id)  # noqa: E712
        .order_by(Agent.id)
    )
    rows = list(manager_q.scalars().all()) + list(worker_q.scalars().all())
    if not rows:
        return ""
    lines = []
    for a in rows:
        tag = " (manager)" if a.role == "manager" else ""
        spec = (a.specialization or "").strip() or "(no specialization set)"
        lines.append(f"- **{a.name}**{tag} — {spec}")
    return "\n".join(lines)


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

    roster = await get_office_roster(session, agent.id)
    if roster:
        sections.append(
            "# Office roster\n\n"
            "These are the OTHER agents currently active. This list is live — "
            "rebuilt from the database on every turn, so it is always correct. "
            "Use exactly these names when calling `delegate`. Do NOT invent or "
            "reference agents that are not on this list.\n\n" + roster
        )
    else:
        sections.append(
            "# Office roster\n\n"
            "You are currently the only active agent. Use `spawn_agent` to bring "
            "specialists into the office before calling `delegate`."
        )

    if skill is not None and not skill.deleted:
        sections.append(format_skill_block(skill))

    sections.append(TOOLS_BLOCK.strip())

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
