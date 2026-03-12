import os
import sqlite3
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("AUTH_DB_PATH", "/data/auth.db")


def _ensure_dir():
    """Ensure the directory for the database file exists."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


@contextmanager
def get_db():
    """Context manager that yields a sqlite3 connection with row_factory set."""
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all required tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS credentials (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                credential_id BLOB NOT NULL UNIQUE,
                public_key BLOB NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL DEFAULT 'My Passkey',
                created_at TEXT NOT NULL,
                last_used TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                ip_address TEXT,
                user_agent TEXT
            );

            CREATE TABLE IF NOT EXISTS challenges (
                challenge_id TEXT PRIMARY KEY,
                challenge TEXT NOT NULL,
                user_id TEXT,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                ip TEXT PRIMARY KEY,
                attempts INTEGER NOT NULL DEFAULT 0,
                first_attempt TEXT NOT NULL,
                locked_until TEXT
            );
        """)
