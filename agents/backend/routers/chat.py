"""
Streaming chat endpoint — the core of the agents service.

Per turn:
  1. Look up the agent (and session if continuing).
  2. Match a skill for this user message (Haiku).
  3. Assemble the system prompt: SOUL -> USER -> MEMORY -> SKILL -> TASK.
  4. Stream the Sonnet response back as Server-Sent Events.
  5. Persist user + assistant turns into transcript + FTS5; update token totals.
  6. Kick off reflection (async, fire-and-forget) for memory/skill proposals.

SSE event types emitted:
  - session:  {session_id, agent_id, skill_id}
  - chunk:    {text}                    — incremental Claude output
  - actions:  {actions: [...]}          — parsed <action> blocks (if any)
  - end:      {session_id, input_tokens, output_tokens}
  - error:    {message}                 — only on failure
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import async_session, get_db
from backend.models import Agent, AgentSession
from backend.routers.auth import get_current_user
from backend.services.anthropic_client import MODEL_SONNET, async_client
from backend.services.prompt_assembly import (
    assemble_system_prompt,
    parse_history_to_messages,
)
from backend.services.reflection import queue_reflection
from backend.services.sessions import (
    append_fts5_turn,
    append_turn_to_session,
    create_session,
)
from backend.services.skill_matcher import match_skill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["chat"])

ACTION_PATTERN = re.compile(r"<action>(.*?)</action>", re.DOTALL)


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[int] = None
    task_framing: str = ""  # set by manager routing for the first message


def _parse_actions(text: str) -> tuple[str, list[dict]]:
    actions: list[dict] = []
    for match in ACTION_PATTERN.finditer(text):
        try:
            actions.append(json.loads(match.group(1).strip()))
        except json.JSONDecodeError:
            logger.warning("Action block was not valid JSON; ignoring")
    cleaned = ACTION_PATTERN.sub("", text).strip()
    return cleaned, actions


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def _set_agent_status(agent_id: int, status: str, msg: Optional[str] = None) -> None:
    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is None:
            return
        agent.status = status
        agent.status_msg = msg
        agent.status_updated_at = datetime.now(timezone.utc)
        await db.commit()


@router.post("/{agent_id}/chat")
async def chat(
    agent_id: int,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> StreamingResponse:
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.deleted == False)  # noqa: E712
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    skill = await match_skill(db, agent_id, body.message)
    system_prompt = await assemble_system_prompt(
        db, agent, skill=skill, task_framing=body.task_framing
    )

    if body.session_id is not None:
        sess_result = await db.execute(
            select(AgentSession).where(AgentSession.id == body.session_id)
        )
        session_row = sess_result.scalar_one_or_none()
        if session_row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        history_messages = parse_history_to_messages(session_row.transcript_json)
    else:
        session_row = await create_session(db, agent_id=agent_id, trigger="chat")
        history_messages = []

    messages = history_messages + [{"role": "user", "content": body.message}]

    agent.status = "thinking"
    agent.status_msg = body.message[:80]
    agent.status_updated_at = datetime.now(timezone.utc)
    await db.commit()

    session_id_final = session_row.id
    skill_id_final = skill.id if skill else None

    async def event_stream() -> AsyncIterator[str]:
        yield _sse("session", {
            "session_id": session_id_final,
            "agent_id": agent_id,
            "skill_id": skill_id_final,
        })

        assistant_chunks: list[str] = []
        input_tokens = 0
        output_tokens = 0

        try:
            await _set_agent_status(agent_id, "working", body.message[:80])

            async with async_client.messages.stream(
                model=MODEL_SONNET,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text_piece in stream.text_stream:
                    assistant_chunks.append(text_piece)
                    yield _sse("chunk", {"text": text_piece})

                final_message = await stream.get_final_message()
                input_tokens = final_message.usage.input_tokens
                output_tokens = final_message.usage.output_tokens
        except Exception as exc:  # noqa: BLE001
            logger.error("Chat stream failed: %s", exc)
            await _set_agent_status(agent_id, "error", str(exc)[:120])
            yield _sse("error", {"message": str(exc)})
            return

        full_text = "".join(assistant_chunks)
        cleaned_text, actions = _parse_actions(full_text)

        async with async_session() as commit_db:
            user_turn_index = await append_turn_to_session(
                commit_db, session_id_final, role="user", content=body.message
            )
            await append_fts5_turn(
                commit_db, session_id_final, agent_id,
                role="user", turn_index=user_turn_index, content=body.message,
            )
            assistant_turn_index = await append_turn_to_session(
                commit_db, session_id_final, role="assistant", content=full_text
            )
            await append_fts5_turn(
                commit_db, session_id_final, agent_id,
                role="assistant", turn_index=assistant_turn_index, content=cleaned_text,
            )

            sess_res = await commit_db.execute(
                select(AgentSession).where(AgentSession.id == session_id_final)
            )
            sess = sess_res.scalar_one()
            sess.token_input = (sess.token_input or 0) + input_tokens
            sess.token_output = (sess.token_output or 0) + output_tokens

            agent_res = await commit_db.execute(select(Agent).where(Agent.id == agent_id))
            commit_agent = agent_res.scalar_one()
            commit_agent.status = "done"
            commit_agent.status_msg = None
            commit_agent.status_updated_at = datetime.now(timezone.utc)

            await commit_db.commit()

        yield _sse("actions", {"actions": actions})
        yield _sse("end", {
            "session_id": session_id_final,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })

        asyncio.create_task(queue_reflection(
            agent_id=agent_id,
            session_id=session_id_final,
            user_message=body.message,
            assistant_text=cleaned_text,
        ))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
