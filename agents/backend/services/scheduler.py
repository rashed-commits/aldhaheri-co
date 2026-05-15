"""
APScheduler init + per-CronJob registration.

Lifespan calls `start_scheduler()` on startup which boots the scheduler
and restores every enabled non-deleted cron job from the DB. CRUD ops
in routers/crons.py call register_job / unregister_job as the user
makes changes — the scheduler state never persists between restarts.
"""

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from backend.db import async_session
from backend.models import CronJob
from backend.services.cron_executor import execute_cron

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _job_id(cron_job_id: int) -> str:
    return f"cron_{cron_job_id}"


async def register_job(job: CronJob) -> Optional[datetime]:
    """Register or replace a job in the scheduler. Returns next_run_time."""
    if not job.enabled or job.deleted:
        return None
    trigger = CronTrigger.from_crontab(job.cron_expr)
    aps_job = scheduler.add_job(
        execute_cron,
        trigger,
        args=[job.id],
        id=_job_id(job.id),
        replace_existing=True,
        misfire_grace_time=300,
    )
    return aps_job.next_run_time


def unregister_job(cron_job_id: int) -> None:
    try:
        scheduler.remove_job(_job_id(cron_job_id))
    except Exception:  # noqa: BLE001 — fine to no-op if it wasn't there
        pass


async def restore_jobs_from_db() -> None:
    async with async_session() as db:
        result = await db.execute(
            select(CronJob).where(
                CronJob.enabled == True,  # noqa: E712
                CronJob.deleted == False,  # noqa: E712
            )
        )
        jobs = result.scalars().all()
        for job in jobs:
            try:
                next_run = await register_job(job)
                if next_run is not None:
                    job.next_run_at = next_run
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to restore cron %d: %s", job.id, exc)
        await db.commit()
        logger.info("Restored %d cron jobs from DB", len(jobs))


async def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()
    await restore_jobs_from_db()
    logger.info("Scheduler running with %d jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
