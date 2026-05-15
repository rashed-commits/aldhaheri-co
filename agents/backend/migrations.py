"""
Schema migrations and seed routines callable from the FastAPI lifespan.

- FTS5 virtual table cannot be modelled in SQLAlchemy, so its CREATE is raw SQL.
- Seeds: singleton USER profile (id=1) and the manager agent (slug='manager').
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Agent, AgentMemory, UserProfile


FTS5_CREATE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS agent_sessions_fts USING fts5(
    session_id UNINDEXED,
    agent_id UNINDEXED,
    role UNINDEXED,
    turn_index UNINDEXED,
    content,
    tokenize='porter unicode61'
);
"""


async def init_fts5(session: AsyncSession) -> None:
    await session.execute(text(FTS5_CREATE_SQL))
    await session.commit()


DEFAULT_USER_MD = """\
# USER.md

Global preferences and facts. Every agent reads this on every turn.

## Who I am
(Describe yourself for your agents — role, work style, location, hard preferences.)

## How I like to work
(Defaults that should apply to every agent unless overridden in that agent's MEMORY.md.)

## Hard rules
(Things no agent should ever do.)
"""


async def seed_user_profile(session: AsyncSession) -> None:
    existing = await session.execute(select(UserProfile).where(UserProfile.id == 1))
    if existing.scalar_one_or_none() is None:
        session.add(UserProfile(id=1, content_md=DEFAULT_USER_MD, version=1))
        await session.commit()


MANAGER_SOUL = """\
You are the Manager. You sit at the center of a small office of specialist agents.

Your job: receive every incoming user message, decide which existing agent should handle it,
and if no existing agent fits, propose spawning a new one. You never do the substantive work
yourself — you route or you propose.

You are concise, decisive, and protective of the user's time. Explain your routing choice in
one short sentence. When proposing a new agent, propose a name, a specialization, and a short
soul block, and wait for user approval before the agent is created.
"""

MANAGER_INITIAL_MEMORY = """\
# Manager memory

I am the manager. I do not hold substantive memory of my own — my role is to dispatch.

## Routing log
(Most recent routing decisions are appended here by the self-improving loop.)
"""


async def seed_manager_agent(session: AsyncSession) -> None:
    existing = await session.execute(select(Agent).where(Agent.role == "manager"))
    if existing.scalar_one_or_none() is not None:
        return

    manager = Agent(
        name="Manager",
        slug="manager",
        role="manager",
        specialization="Routes incoming requests to the right specialist. Spawns new agents when none fit.",
        soul=MANAGER_SOUL,
        status="idle",
    )
    session.add(manager)
    await session.flush()  # populate manager.id

    session.add(AgentMemory(
        agent_id=manager.id,
        content_md=MANAGER_INITIAL_MEMORY,
        version=1,
        source="initial",
    ))
    await session.commit()


async def run_migrations_and_seeds(session: AsyncSession) -> None:
    """Called from the FastAPI lifespan after Base.metadata.create_all."""
    await init_fts5(session)
    await seed_user_profile(session)
    await seed_manager_agent(session)
