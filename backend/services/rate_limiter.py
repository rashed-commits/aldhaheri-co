from datetime import datetime, timedelta, timezone

from utils.database import get_db

MAX_ATTEMPTS = 5
ATTEMPT_WINDOW = timedelta(minutes=5)
LOCKOUT_DURATION = timedelta(minutes=15)


def check_rate_limit(ip: str) -> bool:
    """Check if an IP is allowed to attempt authentication.

    Returns True if the request is allowed, False if rate-limited.
    """
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rate_limits WHERE ip = ?", (ip,)
        ).fetchone()

        if row is None:
            return True

        # Check if locked out
        if row["locked_until"]:
            locked_until = datetime.fromisoformat(row["locked_until"])
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if now < locked_until:
                return False
            # Lockout expired, clear the record
            conn.execute("DELETE FROM rate_limits WHERE ip = ?", (ip,))
            return True

        # Check if attempt window has expired
        first_attempt = datetime.fromisoformat(row["first_attempt"])
        if first_attempt.tzinfo is None:
            first_attempt = first_attempt.replace(tzinfo=timezone.utc)
        if now > first_attempt + ATTEMPT_WINDOW:
            # Window expired, clear old record
            conn.execute("DELETE FROM rate_limits WHERE ip = ?", (ip,))
            return True

        # Within window, check count
        if row["attempts"] >= MAX_ATTEMPTS:
            return False

        return True


def record_attempt(ip: str) -> None:
    """Record a failed authentication attempt for the given IP."""
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM rate_limits WHERE ip = ?", (ip,)
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO rate_limits (ip, attempts, first_attempt) VALUES (?, 1, ?)",
                (ip, now.isoformat()),
            )
            return

        # Check if window expired
        first_attempt = datetime.fromisoformat(row["first_attempt"])
        if first_attempt.tzinfo is None:
            first_attempt = first_attempt.replace(tzinfo=timezone.utc)
        if now > first_attempt + ATTEMPT_WINDOW:
            # Reset window
            conn.execute(
                "UPDATE rate_limits SET attempts = 1, first_attempt = ?, locked_until = NULL WHERE ip = ?",
                (now.isoformat(), ip),
            )
            return

        new_attempts = row["attempts"] + 1
        locked_until = None
        if new_attempts >= MAX_ATTEMPTS:
            locked_until = (now + LOCKOUT_DURATION).isoformat()

        conn.execute(
            "UPDATE rate_limits SET attempts = ?, locked_until = ? WHERE ip = ?",
            (new_attempts, locked_until, ip),
        )


def clear_attempts(ip: str) -> None:
    """Clear rate limit tracking for an IP after successful auth."""
    with get_db() as conn:
        conn.execute("DELETE FROM rate_limits WHERE ip = ?", (ip,))
