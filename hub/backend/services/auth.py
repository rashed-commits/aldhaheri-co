import os
import secrets

import bcrypt
from dotenv import load_dotenv
from fastapi import HTTPException, Request

from services.session_store import validate_session
from utils.database import get_db

load_dotenv()

HUB_USERNAME: str = os.getenv("HUB_USERNAME", "admin")
HUB_PASSWORD: str = os.getenv("HUB_PASSWORD", "admin")


def _get_stored_hash() -> bytes | None:
    """Retrieve the stored bcrypt hash from the database, if it exists."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM password_store WHERE username = ?",
            (HUB_USERNAME,),
        ).fetchone()
        return row["password_hash"] if row else None


def _store_hash(password_hash: bytes) -> None:
    """Store a bcrypt hash in the database."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO password_store (username, password_hash) VALUES (?, ?)",
            (HUB_USERNAME, password_hash),
        )


def _hash_password(password: str) -> bytes:
    """Hash a password with bcrypt using a random salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))


def verify_password(username: str, password: str) -> bool:
    """Validate username and password.

    Uses bcrypt for password verification. On first login (or if no hash exists),
    automatically migrates the plaintext env password to a bcrypt hash.
    """
    if not secrets.compare_digest(username, HUB_USERNAME):
        # Spend time hashing anyway to prevent timing leak on username
        bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=12))
        return False

    stored_hash = _get_stored_hash()

    if stored_hash is None:
        # First run: verify against env var, then store the hash
        if not secrets.compare_digest(password, HUB_PASSWORD):
            return False
        _store_hash(_hash_password(HUB_PASSWORD))
        return True

    # Verify against stored bcrypt hash
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode("utf-8")

    return bcrypt.checkpw(password.encode("utf-8"), stored_hash)


def get_current_user(request: Request) -> dict:
    """FastAPI dependency that extracts and validates the session from cookies.

    Returns the session dict if valid, raises 401 otherwise.
    """
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = validate_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return session
