"""
Per-agent skills: list, create, patch, soft-delete.
"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    AgentSkill,
    AgentSkillCreate,
    AgentSkillOut,
    AgentSkillUpdate,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["skills"])


def _slugify(s: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out or "skill"


@router.get("/agents/{agent_id}/skills", response_model=list[AgentSkillOut])
async def list_skills(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> list[AgentSkill]:
    result = await db.execute(
        select(AgentSkill)
        .where(AgentSkill.agent_id == agent_id, AgentSkill.deleted == False)  # noqa: E712
        .order_by(AgentSkill.id)
    )
    return result.scalars().all()


@router.post("/agents/{agent_id}/skills", response_model=AgentSkillOut, status_code=201)
async def create_skill(
    agent_id: int,
    body: AgentSkillCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> AgentSkill:
    slug = body.slug or _slugify(body.name)
    collision = await db.execute(
        select(AgentSkill).where(
            AgentSkill.agent_id == agent_id,
            AgentSkill.slug == slug,
        )
    )
    if collision.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Skill slug '{slug}' already exists for this agent",
        )

    skill = AgentSkill(
        agent_id=agent_id,
        name=body.name,
        slug=slug,
        description=body.description,
        trigger_keywords=json.dumps(body.trigger_keywords),
        frontmatter_yaml=body.frontmatter_yaml,
        instructions_md=body.instructions_md,
        source="manual",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.patch("/skills/{skill_id}", response_model=AgentSkillOut)
async def update_skill(
    skill_id: int,
    body: AgentSkillUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> AgentSkill:
    result = await db.execute(
        select(AgentSkill).where(AgentSkill.id == skill_id, AgentSkill.deleted == False)  # noqa: E712
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    data = body.model_dump(exclude_unset=True)
    if "trigger_keywords" in data and isinstance(data["trigger_keywords"], list):
        data["trigger_keywords"] = json.dumps(data["trigger_keywords"])
    if "slug" in data and data["slug"] != skill.slug:
        collision = await db.execute(
            select(AgentSkill).where(
                AgentSkill.agent_id == skill.agent_id,
                AgentSkill.slug == data["slug"],
                AgentSkill.id != skill_id,
            )
        )
        if collision.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Slug '{data['slug']}' already exists for this agent",
            )

    for k, v in data.items():
        setattr(skill, k, v)

    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(AgentSkill).where(AgentSkill.id == skill_id, AgentSkill.deleted == False)  # noqa: E712
    )
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill.deleted = True
    await db.commit()
