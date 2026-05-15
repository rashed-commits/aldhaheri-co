"""
Cron execution: run an agent in a fresh isolated session (no chat history),
persist transcript + FTS5, update CronRun, optionally deliver to Telegram.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from backend.db import async_session
from backend.models import Agent, AgentSession, AgentSkill, CronJob, CronRun
from backend.services import telegram
from backend.services.anthropic_client import MODEL_SONNET, async_client
from backend.services.prompt_assembly import assemble_system_prompt
from backend.services.sessions import (
    append_fts5_turn,
    append_turn_to_session,
    create_session,
)

logger = logging.getLogger(__name__)


async def execute_cron(cron_job_id: int) -> None:
    """Called by APScheduler when a cron job fires (or by /run-now)."""
    # ── Setup: load job, agent, skill; create session + run rows ──────────
    async with async_session() as db:
        job_res = await db.execute(select(CronJob).where(CronJob.id == cron_job_id))
        job = job_res.scalar_one_or_none()
        if job is None or not job.enabled or job.deleted:
            logger.info("Cron %d skipped (missing/disabled/deleted)", cron_job_id)
            return

        agent_res = await db.execute(
            select(Agent).where(Agent.id == job.agent_id, Agent.deleted == False)  # noqa: E712
        )
        agent = agent_res.scalar_one_or_none()
        if agent is None:
            logger.warning("Cron %d: agent %d missing", cron_job_id, job.agent_id)
            return

        skill = None
        if job.skill_id is not None:
            skill_res = await db.execute(
                select(AgentSkill).where(
                    AgentSkill.id == job.skill_id,
                    AgentSkill.deleted == False,  # noqa: E712
                )
            )
            skill = skill_res.scalar_one_or_none()

        session_row = await create_session(
            db, agent_id=agent.id, trigger="cron", cron_job_id=job.id
        )

        run = CronRun(cron_job_id=job.id, session_id=session_row.id, status="running")
        db.add(run)
        await db.commit()
        await db.refresh(run)

        system_prompt = await assemble_system_prompt(
            db, agent, skill=skill, task_framing=f"Scheduled task: {job.name}"
        )

        # Snapshot values so we can use them after the session closes
        agent_id = agent.id
        agent_name = agent.name
        job_name = job.name
        job_prompt = job.prompt
        job_output_target = job.output_target
        session_id = session_row.id
        run_id = run.id

    # ── Claude call (no DB held) ──────────────────────────────────────────
    try:
        response = await async_client.messages.create(
            model=MODEL_SONNET,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": job_prompt}],
        )
        assistant_text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
    except Exception as exc:  # noqa: BLE001
        logger.error("Cron %d execution failed: %s", cron_job_id, exc)
        async with async_session() as err_db:
            err_res = await err_db.execute(select(CronRun).where(CronRun.id == run_id))
            err_run = err_res.scalar_one()
            err_run.status = "failed"
            err_run.error = str(exc)[:1000]
            err_run.finished_at = datetime.now(timezone.utc)
            await err_db.commit()
        return

    # ── Persist turns + finalize ──────────────────────────────────────────
    async with async_session() as commit_db:
        user_idx = await append_turn_to_session(
            commit_db, session_id, role="user", content=job_prompt
        )
        await append_fts5_turn(
            commit_db, session_id, agent_id,
            role="user", turn_index=user_idx, content=job_prompt,
        )
        asst_idx = await append_turn_to_session(
            commit_db, session_id, role="assistant", content=assistant_text
        )
        await append_fts5_turn(
            commit_db, session_id, agent_id,
            role="assistant", turn_index=asst_idx, content=assistant_text,
        )

        sess_res = await commit_db.execute(
            select(AgentSession).where(AgentSession.id == session_id)
        )
        sess = sess_res.scalar_one()
        sess.token_input = (sess.token_input or 0) + input_tokens
        sess.token_output = (sess.token_output or 0) + output_tokens
        sess.ended_at = datetime.now(timezone.utc)

        run_res = await commit_db.execute(select(CronRun).where(CronRun.id == run_id))
        run_row = run_res.scalar_one()
        run_row.status = "success"
        run_row.output_excerpt = assistant_text[:500]
        run_row.finished_at = datetime.now(timezone.utc)

        job_res = await commit_db.execute(select(CronJob).where(CronJob.id == cron_job_id))
        job_row = job_res.scalar_one()
        job_row.last_run_at = datetime.now(timezone.utc)

        await commit_db.commit()

    # ── Telegram delivery ─────────────────────────────────────────────────
    if job_output_target in ("telegram", "both"):
        excerpt = assistant_text[:3500]
        await telegram.send_message(
            f"\U0001f916 {agent_name} — {job_name}\n\n{excerpt}"
        )

    logger.info("Cron %d completed successfully", cron_job_id)
