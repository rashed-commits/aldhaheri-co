"""
Session listing + full transcript retrieval + FTS5 search across all turns.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import AgentSession, AgentSessionOut
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SearchHit(BaseModel):
    session_id: int
    agent_id: int
    role: str
    turn_index: int
    content_snippet: str
    rank: float


@router.get("", response_model=list[AgentSessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
    agent_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> list[AgentSession]:
    stmt = select(AgentSession).order_by(desc(AgentSession.id)).limit(limit)
    if agent_id is not None:
        stmt = stmt.where(AgentSession.agent_id == agent_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/search", response_model=list[SearchHit])
async def search(
    q: str = Query(..., min_length=1),
    agent_id: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> list[SearchHit]:
    """FTS5 full-text search across all stored session turns.

    `q` accepts the standard FTS5 MATCH syntax:
      - bare terms: "deploy"
      - phrase: '"production deploy"'
      - operators: "deploy AND vps", "deploy NOT staging"
      - prefix: "deploy*"
    """
    base_sql = """
        SELECT session_id, agent_id, role, turn_index,
               snippet(agent_sessions_fts, 4, '[', ']', '...', 12) AS content_snippet,
               rank
        FROM agent_sessions_fts
        WHERE agent_sessions_fts MATCH :q
    """
    params: dict = {"q": q}
    if agent_id is not None:
        base_sql += " AND agent_id = :agent_id"
        params["agent_id"] = agent_id
    base_sql += " ORDER BY rank LIMIT :limit"
    params["limit"] = limit

    try:
        result = await db.execute(text(base_sql), params)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"FTS5 query error: {exc}")

    rows = result.fetchall()
    return [
        SearchHit(
            session_id=int(r[0]),
            agent_id=int(r[1]),
            role=str(r[2]),
            turn_index=int(r[3]),
            content_snippet=str(r[4]),
            rank=float(r[5]),
        )
        for r in rows
    ]


@router.get("/{session_id}", response_model=AgentSessionOut)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> AgentSession:
    result = await db.execute(select(AgentSession).where(AgentSession.id == session_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row
