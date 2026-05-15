"""
List, accept, reject self-improving-loop proposals.

Accept performs the actual mutation:
- memory_update -> append-only new row in agent_memory (next version)
- new_skill    -> new agent_skills row
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import AgentMemory, AgentSkill, Proposal, ProposalOut
from backend.routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/proposals", tags=["proposals"])


@router.get("", response_model=list[ProposalOut])
async def list_proposals(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
    status: str = Query("pending"),
    agent_id: Optional[int] = Query(None),
    kind: Optional[str] = Query(None),
) -> list[Proposal]:
    stmt = select(Proposal).order_by(desc(Proposal.id))
    if status:
        stmt = stmt.where(Proposal.status == status)
    if agent_id is not None:
        stmt = stmt.where(Proposal.agent_id == agent_id)
    if kind is not None:
        stmt = stmt.where(Proposal.kind == kind)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{proposal_id}/accept", response_model=ProposalOut)
async def accept_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> Proposal:
    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if prop.status != "pending":
        raise HTTPException(status_code=400, detail=f"Proposal already {prop.status}")

    if prop.kind == "memory_update":
        latest = await db.execute(
            select(func.max(AgentMemory.version)).where(AgentMemory.agent_id == prop.agent_id)
        )
        latest_version = latest.scalar() or 0
        db.add(AgentMemory(
            agent_id=prop.agent_id,
            content_md=prop.proposed_snapshot,
            version=latest_version + 1,
            source="proposal_accepted",
            source_proposal_id=prop.id,
        ))

    elif prop.kind == "new_skill":
        try:
            skill_data = json.loads(prop.proposed_snapshot)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Stored skill proposal is not valid JSON")

        slug = skill_data.get("slug") or "skill"
        collision = await db.execute(
            select(AgentSkill).where(
                AgentSkill.agent_id == prop.agent_id,
                AgentSkill.slug == slug,
            )
        )
        if collision.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Skill slug '{slug}' already exists for this agent",
            )

        keywords = skill_data.get("trigger_keywords", [])
        if not isinstance(keywords, list):
            keywords = []

        db.add(AgentSkill(
            agent_id=prop.agent_id,
            name=skill_data.get("name", "Untitled"),
            slug=slug,
            description=skill_data.get("description", ""),
            trigger_keywords=json.dumps(keywords),
            frontmatter_yaml=skill_data.get("frontmatter_yaml", ""),
            instructions_md=skill_data.get("instructions_md", ""),
            source="proposal_accepted",
            source_proposal_id=prop.id,
        ))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown proposal kind: {prop.kind}")

    prop.status = "accepted"
    prop.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(prop)
    return prop


@router.post("/{proposal_id}/reject", response_model=ProposalOut)
async def reject_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> Proposal:
    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    prop = result.scalar_one_or_none()
    if prop is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if prop.status != "pending":
        raise HTTPException(status_code=400, detail=f"Proposal already {prop.status}")

    prop.status = "rejected"
    prop.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(prop)
    return prop
