"""
Cron CRUD with a two-step create flow:

  1. POST /api/crons/parse  — Haiku translates NL into a cron expression
                              for the user to confirm.
  2. POST /api/crons        — persist the (confirmed) cron and register
                              with APScheduler.
"""

import asyncio
from typing import Optional

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    CronJob,
    CronJobCreate,
    CronJobOut,
    CronJobUpdate,
    CronRun,
    CronRunOut,
)
from backend.routers.auth import get_current_user
from backend.services.cron_executor import execute_cron
from backend.services.nl_schedule import parse_nl_schedule
from backend.services.scheduler import register_job, unregister_job

router = APIRouter(prefix="/api/crons", tags=["crons"])


class ParseRequest(BaseModel):
    nl_schedule: str


class ParseResponse(BaseModel):
    cron_expr: Optional[str]
    explanation: str


class CronJobCreateConfirmed(CronJobCreate):
    cron_expr: str  # confirmed by the user after /parse


@router.post("/parse", response_model=ParseResponse)
async def parse(
    body: ParseRequest,
    _: dict = Depends(get_current_user),
) -> ParseResponse:
    return ParseResponse(**(await parse_nl_schedule(body.nl_schedule)))


@router.get("", response_model=list[CronJobOut])
async def list_crons(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> list[CronJob]:
    result = await db.execute(
        select(CronJob).where(CronJob.deleted == False).order_by(CronJob.id)  # noqa: E712
    )
    return result.scalars().all()


@router.post("", response_model=CronJobOut, status_code=201)
async def create_cron(
    body: CronJobCreateConfirmed,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> CronJob:
    try:
        CronTrigger.from_crontab(body.cron_expr)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {exc}")

    job = CronJob(
        agent_id=body.agent_id,
        name=body.name,
        nl_schedule=body.nl_schedule,
        cron_expr=body.cron_expr,
        prompt=body.prompt,
        skill_id=body.skill_id,
        output_target=body.output_target,
        enabled=True,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    next_run = await register_job(job)
    if next_run is not None:
        job.next_run_at = next_run
        await db.commit()
        await db.refresh(job)

    return job


@router.patch("/{cron_id}", response_model=CronJobOut)
async def update_cron(
    cron_id: int,
    body: CronJobUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> CronJob:
    result = await db.execute(
        select(CronJob).where(CronJob.id == cron_id, CronJob.deleted == False)  # noqa: E712
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Cron job not found")

    data = body.model_dump(exclude_unset=True)

    # Editing the NL schedule re-parses via Haiku
    if "nl_schedule" in data:
        parsed = await parse_nl_schedule(data["nl_schedule"])
        if parsed["cron_expr"] is None:
            raise HTTPException(
                status_code=400,
                detail=f"Could not parse schedule: {parsed['explanation']}",
            )
        data["cron_expr"] = parsed["cron_expr"]

    for k, v in data.items():
        setattr(job, k, v)

    await db.commit()
    await db.refresh(job)

    # Re-register (handles enable/disable + schedule changes uniformly)
    unregister_job(cron_id)
    if job.enabled:
        next_run = await register_job(job)
        if next_run is not None:
            job.next_run_at = next_run
            await db.commit()
            await db.refresh(job)

    return job


@router.delete("/{cron_id}", status_code=204)
async def delete_cron(
    cron_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(CronJob).where(CronJob.id == cron_id, CronJob.deleted == False)  # noqa: E712
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Cron job not found")
    job.deleted = True
    await db.commit()
    unregister_job(cron_id)


@router.post("/{cron_id}/run-now", status_code=202)
async def run_now(
    cron_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(CronJob).where(CronJob.id == cron_id, CronJob.deleted == False)  # noqa: E712
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Cron job not found")

    asyncio.create_task(execute_cron(cron_id))
    return {"status": "queued"}


@router.get("/{cron_id}/runs", response_model=list[CronRunOut])
async def list_runs(
    cron_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> list[CronRun]:
    result = await db.execute(
        select(CronRun)
        .where(CronRun.cron_job_id == cron_id)
        .order_by(desc(CronRun.id))
        .limit(50)
    )
    return result.scalars().all()
