import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM: str = "HS256"
TOKEN_EXPIRY_HOURS: int = 8


def create_token(username: str) -> tuple[str, datetime]:
    """Create a JWT token for the given username.

    Returns a tuple of (token, expires_at).
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)
    payload = {
        "sub": username,
        "exp": expires_at,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token.

    Returns the payload dict on success, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
