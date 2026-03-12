import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Response

from utils.database import get_db
from utils.jwt_handler import create_session_token, decode_token

load_dotenv()

# Timeouts
IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=8)

# Cookie settings
SESSION_COOKIE_NAME = "session"
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", ".aldhaheri.co")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"


def create_session(user_id: str, ip: str, user_agent: str) -> tuple[str, str]:
    """Create a new session and return (session_id, jwt_token)."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + ABSOLUTE_TIMEOUT

    with get_db() as conn:
        conn.execute(
            """INSERT INTO sessions
               (session_id, user_id, created_at, last_active, expires_at, revoked, ip_address, user_agent)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
            (
                session_id,
                user_id,
                now.isoformat(),
                now.isoformat(),
                expires_at.isoformat(),
                ip,
                user_agent,
            ),
        )

    jwt_token = create_session_token(user_id, session_id)
    return session_id, jwt_token


def validate_session(session_token: str) -> dict | None:
    """Validate a session token and return session info or None."""
    payload = decode_token(session_token)
    if payload is None:
        return None

    session_id = payload.get("sid")
    user_id = payload.get("sub")
    if not session_id or not user_id:
        return None

    now = datetime.now(timezone.utc)

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

        if row is None:
            return None

        if row["revoked"]:
            return None

        # Check absolute timeout
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if now > created_at + ABSOLUTE_TIMEOUT:
            return None

        # Check idle timeout
        last_active = datetime.fromisoformat(row["last_active"])
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        if now > last_active + IDLE_TIMEOUT:
            return None

        # Update last_active
        conn.execute(
            "UPDATE sessions SET last_active = ? WHERE session_id = ?",
            (now.isoformat(), session_id),
        )

    return {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": row["created_at"],
        "last_active": now.isoformat(),
        "ip_address": row["ip_address"],
    }


def revoke_session(session_id: str) -> None:
    """Revoke a single session."""
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE session_id = ?", (session_id,)
        )


def revoke_all_sessions(user_id: str) -> None:
    """Revoke all sessions for a user."""
    with get_db() as conn:
        conn.execute(
            "UPDATE sessions SET revoked = 1 WHERE user_id = ?", (user_id,)
        )


def cleanup_expired() -> None:
    """Delete expired and revoked sessions."""
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE expires_at < ? OR revoked = 1",
            (now.isoformat(),),
        )
        # Also clean up expired challenges
        conn.execute(
            "DELETE FROM challenges WHERE expires_at < ?",
            (now.isoformat(),),
        )


def set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie with all security flags."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        domain=COOKIE_DOMAIN,
        path="/",
        max_age=int(ABSOLUTE_TIMEOUT.total_seconds()),
    )


def clear_session_cookie(response: Response) -> None:
    """Delete the session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        domain=COOKIE_DOMAIN,
        path="/",
    )
