"""
Self-improving loop. After every assistant turn this fires (async, non-blocking)
and writes pending proposals to the `proposals` table. User accepts or rejects
via the proposals router; nothing persists to memory or skills without consent.

Phase 4 ships a logging stub so the chat endpoint can call it. The full
Haiku-powered implementation lands in Phase 5.
"""

import logging

logger = logging.getLogger(__name__)


async def queue_reflection(
    agent_id: int,
    session_id: int,
    user_message: str,
    assistant_text: str,
) -> None:
    """Fire-and-forget reflection entry point — Phase 5 will implement."""
    logger.info(
        "reflection stub: agent=%d session=%d user_chars=%d assistant_chars=%d",
        agent_id, session_id, len(user_message), len(assistant_text),
    )
