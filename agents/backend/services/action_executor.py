"""
Server-side dispatcher for `<action>` blocks emitted by agents.

After the chat stream ends, parsed actions run through this executor. Each
handler returns a structured result that gets bundled back into the SSE
`actions` event so the frontend can show executed state with outcomes.

Whitelist of auto-executable actions:
  - spawn_agent     create a new sub-agent
  - delegate        send a one-shot message to another agent
  - create_skill    write a procedural playbook onto the calling agent
  - create_task     track a unit of work
  - send_telegram   push a notification to the user's phone
  - schedule_cron   set up a recurring task

Anything else (fire_agent, update_user_profile, …) is refused — those
remain user-gated by separate UI flows.
"""

import json
import logging
import re
from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from backend.db import async_session
from backend.models import (
    Agent,
    AgentMemory,
    AgentSession,
    AgentSkill,
    CronJob,
    Task,
)
from backend.services import telegram
from backend.services.anthropic_client import MODEL_SONNET, async_client
from backend.services.nl_schedule import parse_nl_schedule
from backend.services.prompt_assembly import assemble_system_prompt
from backend.services.scheduler import register_job
from backend.services.sessions import (
    append_fts5_turn,
    append_turn_to_session,
    create_session,
)

logger = logging.getLogger(__name__)


def _slugify(s: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out or "x"


async def execute_action(action: dict, actor_agent_id: int, session_id: int) -> dict:
    """Dispatch one parsed action block.

    Returns a result dict: {"success": bool, "message": str, "data": dict?}.
    Never raises — all exceptions are converted to {"success": False, ...}.
    """
    if not isinstance(action, dict):
        return {"success": False, "message": "Action must be a JSON object"}

    action_type = action.get("type")
    if not action_type:
        return {"success": False, "message": "Action missing 'type' field"}

    handler = _HANDLERS.get(action_type)
    if handler is None:
        return {
            "success": False,
            "message": (
                f"Action '{action_type}' is not auto-executable. "
                "Available actions: " + ", ".join(sorted(_HANDLERS))
            ),
        }

    try:
        return await handler(action, actor_agent_id, session_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Action %s failed", action_type)
        return {"success": False, "message": f"{action_type} failed: {exc}"}


# ── handlers ─────────────────────────────────────────────────────────────────

async def _handle_spawn_agent(action, actor_id, session_id):
    name = (action.get("name") or "").strip()
    if not name:
        return {"success": False, "message": "spawn_agent requires 'name'"}
    specialization = (action.get("specialization") or "").strip()
    soul = (action.get("soul") or "").strip()
    slug = _slugify(name)

    async with async_session() as db:
        # Auto-suffix on slug collision so spawns never fail because of names.
        collision = await db.execute(select(Agent).where(Agent.slug == slug))
        if collision.scalar_one_or_none() is not None:
            n = 2
            while True:
                trial = f"{slug}-{n}"
                tr = await db.execute(select(Agent).where(Agent.slug == trial))
                if tr.scalar_one_or_none() is None:
                    slug = trial
                    break
                n += 1
            # Also append the suffix to the display name so the office shows it.
            name = f"{name} ({n})"

        new_agent = Agent(
            name=name,
            slug=slug,
            role="worker",
            specialization=specialization,
            soul=soul,
            status="idle",
        )
        db.add(new_agent)
        await db.flush()
        db.add(AgentMemory(
            agent_id=new_agent.id,
            content_md=f"# {name} memory\n\n(Spawned autonomously by agent #{actor_id}.)\n",
            version=1,
            source="initial",
        ))
        await db.commit()
        await db.refresh(new_agent)
        return {
            "success": True,
            "message": f"Spawned {name}",
            "data": {"agent_id": new_agent.id, "name": new_agent.name},
        }


async def _handle_delegate(action, actor_id, session_id):
    target_name = (action.get("agent_name") or "").strip()
    target_id_raw = action.get("agent_id")
    message = (action.get("message") or "").strip()
    if not message:
        return {"success": False, "message": "delegate requires 'message'"}

    async with async_session() as db:
        target = None
        if target_id_raw:
            try:
                tid = int(target_id_raw)
                r = await db.execute(
                    select(Agent).where(Agent.id == tid, Agent.deleted == False)  # noqa: E712
                )
                target = r.scalar_one_or_none()
            except (TypeError, ValueError):
                pass
        if target is None and target_name:
            r = await db.execute(
                select(Agent).where(
                    func.lower(Agent.name) == target_name.lower(),
                    Agent.deleted == False,  # noqa: E712
                )
            )
            target = r.scalar_one_or_none()
        if target is None:
            return {"success": False, "message": f"Target agent not found: {target_name or target_id_raw}"}
        if target.id == actor_id:
            return {"success": False, "message": "Cannot delegate to yourself"}

        sub_session = await create_session(
            db, agent_id=target.id, trigger="delegated"
        )
        system_prompt = await assemble_system_prompt(
            db, target, skill=None,
            task_framing=f"Delegated by agent #{actor_id}. Stay focused on the message; reply with the result only.",
        )
        target_name_snap = target.name
        target_id_snap = target.id
        sub_session_id = sub_session.id

    # Call Sonnet outside the DB session.
    try:
        resp = await async_client.messages.create(
            model=MODEL_SONNET,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )
        delegated_text = resp.content[0].text
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
    except Exception as exc:  # noqa: BLE001
        logger.exception("Delegate call failed")
        return {"success": False, "message": f"Delegate to {target_name_snap} failed: {exc}"}

    # Persist the sub-session transcript.
    async with async_session() as commit_db:
        ui = await append_turn_to_session(commit_db, sub_session_id, "user", message)
        await append_fts5_turn(commit_db, sub_session_id, target_id_snap, "user", ui, message)
        ai = await append_turn_to_session(commit_db, sub_session_id, "assistant", delegated_text)
        await append_fts5_turn(commit_db, sub_session_id, target_id_snap, "assistant", ai, delegated_text)
        sr = await commit_db.execute(select(AgentSession).where(AgentSession.id == sub_session_id))
        s = sr.scalar_one()
        s.token_input = (s.token_input or 0) + in_tok
        s.token_output = (s.token_output or 0) + out_tok
        s.ended_at = datetime.now(timezone.utc)
        await commit_db.commit()

    return {
        "success": True,
        "message": f"Delegated to {target_name_snap}",
        "data": {
            "target_agent_id": target_id_snap,
            "target_agent_name": target_name_snap,
            "session_id": sub_session_id,
            "response": delegated_text,
        },
    }


async def _handle_create_skill(action, actor_id, session_id):
    name = (action.get("name") or "").strip()
    if not name:
        return {"success": False, "message": "create_skill requires 'name'"}
    slug = (action.get("slug") or "").strip() or _slugify(name)

    async with async_session() as db:
        # Auto-suffix on slug collision per-agent.
        collision = await db.execute(
            select(AgentSkill).where(
                AgentSkill.agent_id == actor_id, AgentSkill.slug == slug
            )
        )
        if collision.scalar_one_or_none() is not None:
            n = 2
            while True:
                trial = f"{slug}-{n}"
                tr = await db.execute(
                    select(AgentSkill).where(
                        AgentSkill.agent_id == actor_id, AgentSkill.slug == trial
                    )
                )
                if tr.scalar_one_or_none() is None:
                    slug = trial
                    break
                n += 1

        keywords = action.get("trigger_keywords", [])
        if not isinstance(keywords, list):
            keywords = []

        skill = AgentSkill(
            agent_id=actor_id,
            name=name,
            slug=slug,
            description=(action.get("description") or "").strip(),
            trigger_keywords=json.dumps(keywords),
            frontmatter_yaml=action.get("frontmatter_yaml") or "",
            instructions_md=action.get("instructions_md") or "",
            source="manual",
        )
        db.add(skill)
        await db.commit()
        await db.refresh(skill)
        return {
            "success": True,
            "message": f"Created skill '{name}'",
            "data": {"skill_id": skill.id, "slug": slug},
        }


async def _handle_create_task(action, actor_id, session_id):
    title = (action.get("title") or "").strip()
    if not title:
        return {"success": False, "message": "create_task requires 'title'"}
    desc = (action.get("description") or "").strip()
    target_id = action.get("agent_id") or actor_id

    async with async_session() as db:
        t = Task(
            agent_id=int(target_id),
            title=title,
            description=desc,
            status="open",
            origin="manual",
            session_id=session_id,
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return {
            "success": True,
            "message": f"Created task '{title}'",
            "data": {"task_id": t.id},
        }


async def _handle_send_telegram(action, actor_id, session_id):
    text = (action.get("text") or "").strip()
    if not text:
        return {"success": False, "message": "send_telegram requires 'text'"}
    ok = await telegram.send_message(text[:3500])
    return {
        "success": ok,
        "message": "Sent Telegram" if ok else "Telegram not configured or send failed",
    }


async def _handle_schedule_cron(action, actor_id, session_id):
    name = (action.get("name") or "").strip()
    nl = (action.get("nl_schedule") or "").strip()
    prompt = (action.get("prompt") or "").strip()
    if not (name and nl and prompt):
        return {"success": False, "message": "schedule_cron requires name, nl_schedule, prompt"}

    parsed = await parse_nl_schedule(nl)
    if parsed["cron_expr"] is None:
        return {"success": False, "message": f"Schedule parse failed: {parsed['explanation']}"}

    try:
        CronTrigger.from_crontab(parsed["cron_expr"])
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "message": f"Invalid cron expression: {exc}"}

    target_agent_id = action.get("agent_id") or actor_id
    output_target = action.get("output_target") or "ui_only"
    if output_target not in ("ui_only", "telegram", "both"):
        output_target = "ui_only"

    async with async_session() as db:
        job = CronJob(
            agent_id=int(target_agent_id),
            name=name,
            nl_schedule=nl,
            cron_expr=parsed["cron_expr"],
            prompt=prompt,
            skill_id=action.get("skill_id") or None,
            output_target=output_target,
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

        return {
            "success": True,
            "message": f"Scheduled '{name}' ({parsed['cron_expr']})",
            "data": {
                "cron_id": job.id,
                "cron_expr": parsed["cron_expr"],
                "explanation": parsed["explanation"],
            },
        }


_HANDLERS = {
    "spawn_agent": _handle_spawn_agent,
    "delegate": _handle_delegate,
    "create_skill": _handle_create_skill,
    "create_task": _handle_create_task,
    "send_telegram": _handle_send_telegram,
    "schedule_cron": _handle_schedule_cron,
}
