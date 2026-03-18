import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM: str = "HS256"
TOKEN_EXPIRY_HOURS: int = 8
TOTP_PENDING_EXPIRY_MINUTES: int = 5


def create_session_token(user_id: str, session_id: str) -> str:
    """Create a JWT token for a session.

    Returns the encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=TOKEN_EXPIRY_HOURS)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token.

    Returns the payload dict on success, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_totp_pending_token(user_id: str) -> str:
    """Create a short-lived token for the TOTP verification step.

    This token proves the user passed password auth but has not yet
    completed TOTP. It cannot be used as a session token (no sid claim).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "purpose": "totp",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=TOTP_PENDING_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def decode_totp_pending_token(token: str) -> str | None:
    """Decode a TOTP pending token. Returns user_id if valid, else None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("purpose") != "totp":
            return None
        return payload.get("sub")
    except JWTError:
        return None
