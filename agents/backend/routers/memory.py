"""
Per-agent MEMORY.md: read latest, list versions, manual edit (creates new version).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import AgentMemory, AgentMemoryOut, AgentMemoryUpdate
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/agents", tags=["memory"])


@router.get("/{agent_id}/memory", response_model=AgentMemoryOut)
async def get_memory(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> AgentMemory:
    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(desc(AgentMemory.version))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No memory for this agent")
    return row


@router.get("/{agent_id}/memory/versions", response_model=list[AgentMemoryOut])
async def list_memory_versions(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> list[AgentMemory]:
    result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(desc(AgentMemory.version))
    )
    return result.scalars().all()


@router.put("/{agent_id}/memory", response_model=AgentMemoryOut)
async def update_memory(
    agent_id: int,
    body: AgentMemoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> AgentMemory:
    latest = await db.execute(
        select(func.max(AgentMemory.version)).where(AgentMemory.agent_id == agent_id)
    )
    latest_version = latest.scalar() or 0

    new_row = AgentMemory(
        agent_id=agent_id,
        content_md=body.content_md,
        version=latest_version + 1,
        source="manual_edit",
    )
    db.add(new_row)
    await db.commit()
    await db.refresh(new_row)
    return new_row
