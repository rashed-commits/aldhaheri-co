import os
import secrets

from dotenv import load_dotenv
from fastapi import HTTPException, Request

from services.session_store import validate_session

load_dotenv()

HUB_USERNAME: str = os.getenv("HUB_USERNAME", "admin")
HUB_PASSWORD: str = os.getenv("HUB_PASSWORD", "admin")


def verify_password(username: str, password: str) -> bool:
    """Validate username and password against environment variables.

    Uses constant-time comparison to prevent timing attacks.
    """
    username_match = secrets.compare_digest(username, HUB_USERNAME)
    password_match = secrets.compare_digest(password, HUB_PASSWORD)
    return username_match and password_match


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
