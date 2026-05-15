"""
Session persistence helpers: create sessions, append turns to a session's
structured transcript, and mirror each turn into the FTS5 virtual table.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AgentSession


async def create_session(
    session: AsyncSession,
    agent_id: int,
    trigger: str = "chat",
    cron_job_id: Optional[int] = None,
    task_id: Optional[int] = None,
) -> AgentSession:
    row = AgentSession(
        agent_id=agent_id,
        trigger=trigger,
        cron_job_id=cron_job_id,
        task_id=task_id,
        transcript_json="[]",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def append_turn_to_session(
    session: AsyncSession,
    session_id: int,
    role: str,
    content: str,
) -> int:
    """Append a turn and return its zero-based turn_index."""
    result = await session.execute(
        select(AgentSession).where(AgentSession.id == session_id)
    )
    row = result.scalar_one()

    try:
        turns = json.loads(row.transcript_json or "[]")
    except json.JSONDecodeError:
        turns = []

    turn_index = len(turns)
    turns.append({
        "role": role,
        "content": content,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    row.transcript_json = json.dumps(turns)
    await session.commit()
    return turn_index


async def append_fts5_turn(
    session: AsyncSession,
    session_id: int,
    agent_id: int,
    role: str,
    turn_index: int,
    content: str,
) -> None:
    """Index one turn into agent_sessions_fts for later FTS5 search."""
    await session.execute(
        text(
            "INSERT INTO agent_sessions_fts "
            "(session_id, agent_id, role, turn_index, content) "
            "VALUES (:sid, :aid, :role, :idx, :content)"
        ),
        {
            "sid": session_id,
            "aid": agent_id,
            "role": role,
            "idx": turn_index,
            "content": content,
        },
    )
    await session.commit()


async def close_session(session: AsyncSession, session_id: int) -> None:
    result = await session.execute(
        select(AgentSession).where(AgentSession.id == session_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return
    row.ended_at = datetime.now(timezone.utc)
    await session.commit()
