"""
Singleton USER.md — global preferences/facts seen by every agent. Read + update.
Each PUT bumps the version counter.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import UserProfile, UserProfileOut, UserProfileUpdate
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/user-profile", tags=["user_profile"])


@router.get("", response_model=UserProfileOut)
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="USER profile not seeded")
    return row


@router.put("", response_model=UserProfileOut)
async def update_user_profile(
    body: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="USER profile not seeded")

    data = body.model_dump(exclude_unset=True)
    content_changed = "content_md" in data and data["content_md"] != row.content_md
    if "content_md" in data and data["content_md"] is not None:
        row.content_md = data["content_md"]
    if "auto_accept_memory" in data and data["auto_accept_memory"] is not None:
        row.auto_accept_memory = bool(data["auto_accept_memory"])
    if content_changed:
        row.version = (row.version or 1) + 1
    row.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(row)
    return row
