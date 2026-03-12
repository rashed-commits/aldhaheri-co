"""
SQLite storage layer — schema, upsert, deduplication, and read helpers.

Tables
------
listings        — every unique listing ever seen (sale + rent)
listing_history — price snapshot each time we see a listing (for price-drop detection)
run_log         — metadata for each scraper run
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import DB_PATH
from utils.logger import get_logger

log = get_logger()


# ─── Schema DDL ──────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,   -- <source>_<externalID>  (e.g. bayut_13542272)
    source          TEXT NOT NULL,      -- 'bayut' | 'propertyfinder'
    external_id     TEXT NOT NULL,
    purpose         TEXT NOT NULL,      -- 'sale' | 'rent'
    property_type   TEXT,
    title           TEXT,
    price           REAL,
    currency        TEXT DEFAULT 'AED',
    area_sqft       REAL,
    bedrooms        INTEGER,
    bathrooms       INTEGER,
    city            TEXT,
    area_name       TEXT,               -- community / sub-area
    location_full   TEXT,               -- full breadcrumb
    latitude        REAL,
    longitude       REAL,
    url             TEXT,
    is_offplan      INTEGER DEFAULT 0,
    agent_name      TEXT,
    agent_phone     TEXT,
    listed_date     TEXT,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    price_on_first  REAL,              -- price when we first stored it
    is_active       INTEGER DEFAULT 1,
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS listing_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id  TEXT NOT NULL REFERENCES listings(id),
    price       REAL NOT NULL,
    seen_at     TEXT NOT NULL,
    run_id      TEXT
);

CREATE TABLE IF NOT EXISTS run_log (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    source      TEXT,
    listings_fetched INTEGER DEFAULT 0,
    listings_new     INTEGER DEFAULT 0,
    listings_updated INTEGER DEFAULT 0,
    errors           INTEGER DEFAULT 0,
    status           TEXT DEFAULT 'running'   -- running | success | failed
);

CREATE INDEX IF NOT EXISTS idx_listings_area   ON listings(city, area_name);
CREATE INDEX IF NOT EXISTS idx_listings_purpose ON listings(purpose);
CREATE INDEX IF NOT EXISTS idx_history_listing  ON listing_history(listing_id);
"""


# ─── Helpers ─────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect():
    """Yield a sqlite3 connection with WAL mode and foreign keys."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    log.info("Database initialised at %s", DB_PATH)


# ─── Run log ─────────────────────────────────────────────────────────
def start_run(run_id: str, source: str):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO run_log (run_id, started_at, source) VALUES (?, ?, ?)",
            (run_id, _now_iso(), source),
        )


def finish_run(run_id: str, fetched: int, new: int, updated: int, errors: int, status: str = "success"):
    with _connect() as conn:
        conn.execute(
            """UPDATE run_log
               SET finished_at=?, listings_fetched=?, listings_new=?,
                   listings_updated=?, errors=?, status=?
               WHERE run_id=?""",
            (_now_iso(), fetched, new, updated, errors, status, run_id),
        )


# ─── Upsert listings ────────────────────────────────────────────────
def upsert_listings(rows: list[dict], run_id: str) -> dict:
    """
    Insert new listings or update existing ones.
    Returns {"new": N, "updated": M, "unchanged": K}.
    """
    stats = {"new": 0, "updated": 0, "unchanged": 0}
    now = _now_iso()

    with _connect() as conn:
        for r in rows:
            lid = r["id"]  # e.g. bayut_13542272
            existing = conn.execute("SELECT id, price FROM listings WHERE id = ?", (lid,)).fetchone()

            if existing is None:
                # ── New listing ──────────────────────────────────────
                conn.execute(
                    """INSERT INTO listings
                       (id, source, external_id, purpose, property_type, title,
                        price, currency, area_sqft, bedrooms, bathrooms,
                        city, area_name, location_full, latitude, longitude,
                        url, is_offplan, agent_name, agent_phone, listed_date,
                        first_seen, last_seen, price_on_first, is_active)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        lid, r["source"], r["external_id"], r["purpose"],
                        r.get("property_type"), r.get("title"),
                        r.get("price"), r.get("currency", "AED"),
                        r.get("area_sqft"), r.get("bedrooms"), r.get("bathrooms"),
                        r.get("city"), r.get("area_name"), r.get("location_full"),
                        r.get("latitude"), r.get("longitude"),
                        r.get("url"), int(r.get("is_offplan", False)),
                        r.get("agent_name"), r.get("agent_phone"),
                        r.get("listed_date"),
                        now, now, r.get("price"),
                    ),
                )
                stats["new"] += 1
            else:
                # ── Existing listing — update last_seen + check price ─
                old_price = existing["price"]
                new_price = r.get("price")
                conn.execute(
                    "UPDATE listings SET last_seen=?, price=?, is_active=1 WHERE id=?",
                    (now, new_price, lid),
                )
                if new_price and old_price and new_price != old_price:
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

            # ── Always record a price snapshot ───────────────────────
            conn.execute(
                "INSERT INTO listing_history (listing_id, price, seen_at, run_id) VALUES (?,?,?,?)",
                (lid, r.get("price"), now, run_id),
            )

    return stats


# ─── Query helpers (used by Phase 2 analysis) ────────────────────────
def get_area_avg_price_sqft(city: str, area_name: str, purpose: str = "sale") -> float | None:
    """Return the average price/sqft for active listings in an area."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT AVG(price / NULLIF(area_sqft, 0)) AS avg_psf
               FROM listings
               WHERE city=? AND area_name=? AND purpose=? AND is_active=1
                     AND price > 0 AND area_sqft > 0""",
            (city, area_name, purpose),
        ).fetchone()
        return row["avg_psf"] if row else None


def get_comparable_rent(city: str, area_name: str, bedrooms: int) -> float | None:
    """Median yearly rent for a similar unit (same area + bedrooms)."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT price FROM listings
               WHERE city=? AND area_name=? AND purpose='rent'
                     AND bedrooms=? AND is_active=1 AND price > 0
               ORDER BY price""",
            (city, area_name, bedrooms),
        ).fetchall()
        if not rows:
            return None
        prices = [r["price"] for r in rows]
        mid = len(prices) // 2
        return prices[mid]


def get_price_history(listing_id: str) -> list[dict]:
    """Return chronological price snapshots for a listing."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT price, seen_at FROM listing_history WHERE listing_id=? ORDER BY seen_at",
            (listing_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_listing_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM listings").fetchone()
        return row["cnt"]
