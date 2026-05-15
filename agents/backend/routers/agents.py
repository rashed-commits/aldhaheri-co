"""
Agent CRUD. The manager agent (role='manager') is protected from delete.
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    Agent,
    AgentCreate,
    AgentMemory,
    AgentMemoryOut,
    AgentOut,
    AgentSkill,
    AgentSkillOut,
    AgentUpdate,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/agents", tags=["agents"])


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "agent"


class AgentDetailOut(AgentOut):
    latest_memory: Optional[AgentMemoryOut] = None
    skills: list[AgentSkillOut] = []


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> list[Agent]:
    result = await db.execute(
        select(Agent).where(Agent.deleted == False).order_by(Agent.id)  # noqa: E712
    )
    return result.scalars().all()


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> Agent:
    slug = slugify(body.name)

    existing = await db.execute(select(Agent).where(Agent.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Agent with slug '{slug}' already exists")

    agent = Agent(
        name=body.name,
        slug=slug,
        role="worker",
        specialization=body.specialization,
        soul=body.soul,
        status="idle",
    )
    db.add(agent)
    await db.flush()

    db.add(AgentMemory(
        agent_id=agent.id,
        content_md=f"# {body.name} memory\n\n(No memories yet — proposals will appear as you work together.)\n",
        version=1,
        source="initial",
    ))
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentDetailOut)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> AgentDetailOut:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.deleted == False)  # noqa: E712
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    mem_result = await db.execute(
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent.id)
        .order_by(AgentMemory.version.desc())
        .limit(1)
    )
    latest_memory = mem_result.scalar_one_or_none()

    skills_result = await db.execute(
        select(AgentSkill)
        .where(AgentSkill.agent_id == agent.id, AgentSkill.deleted == False)  # noqa: E712
        .order_by(AgentSkill.id)
    )
    skills = skills_result.scalars().all()

    return AgentDetailOut(
        **AgentOut.model_validate(agent).model_dump(),
        latest_memory=AgentMemoryOut.model_validate(latest_memory) if latest_memory else None,
        skills=[AgentSkillOut.model_validate(s) for s in skills],
    )


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: int,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> Agent:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.deleted == False)  # noqa: E712
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)

    if "name" in update_data:
        new_slug = slugify(update_data["name"])
        if new_slug != agent.slug:
            collision = await db.execute(
                select(Agent).where(Agent.slug == new_slug, Agent.id != agent_id)
            )
            if collision.scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail=f"Slug '{new_slug}' already in use")
            agent.slug = new_slug

    for key, value in update_data.items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.deleted == False)  # noqa: E712
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.role == "manager":
        raise HTTPException(status_code=400, detail="Cannot delete the manager")

    agent.deleted = True
    await db.commit()
