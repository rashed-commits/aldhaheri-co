import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

HUB_USERNAME: str = os.getenv("HUB_USERNAME", "admin")
HUB_PASSWORD: str = os.getenv("HUB_PASSWORD", "admin")

# In-memory failed login attempt tracking: { ip: { count, locked_until } }
failed_attempts: dict[str, dict] = {}

# In-memory token blacklist
blacklisted_tokens: set[str] = set()

MAX_FAILED_ATTEMPTS: int = 5
LOCKOUT_MINUTES: int = 15


def is_locked_out(ip: str) -> bool:
    """Check if an IP address is currently locked out."""
    record = failed_attempts.get(ip)
    if record is None:
        return False

    locked_until = record.get("locked_until")
    if locked_until is None:
        return False

    if datetime.now(timezone.utc) < locked_until:
        return True

    # Lockout expired — reset the record
    failed_attempts.pop(ip, None)
    return False


def record_failed_attempt(ip: str) -> None:
    """Record a failed login attempt for the given IP."""
    record = failed_attempts.get(ip, {"count": 0, "locked_until": None})
    record["count"] += 1

    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["locked_until"] = datetime.now(timezone.utc) + timedelta(
            minutes=LOCKOUT_MINUTES
        )

    failed_attempts[ip] = record


def clear_failed_attempts(ip: str) -> None:
    """Clear failed attempt tracking for an IP after successful login."""
    failed_attempts.pop(ip, None)


def validate_credentials(username: str, password: str) -> bool:
    """Validate username and password against environment variables."""
    return username == HUB_USERNAME and password == HUB_PASSWORD


def blacklist_token(token: str) -> None:
    """Add a token to the blacklist."""
    blacklisted_tokens.add(token)


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted."""
    return token in blacklisted_tokens
