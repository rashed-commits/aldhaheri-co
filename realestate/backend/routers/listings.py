"""
Listings API — read-only endpoints against the existing SQLite database.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["listings"], dependencies=[Depends(get_current_user)])

# Path to the existing SQLite database (mounted via Docker volume)
DB_PATH = Path("/app/data/listings.db")


@contextmanager
def _connect():
    """Yield a read-only SQLite connection."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Database not available")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    try:
        yield conn
    finally:
        conn.close()


# ─── GET /api/listings ────────────────────────────────────────────────
@router.get("/listings")
def list_listings(
    city: Optional[str] = Query(None, description="Filter by city (abu-dhabi, dubai)"),
    area: Optional[str] = Query(None, description="Filter by area_name"),
    purpose: Optional[str] = Query(None, description="Filter by purpose (sale, rent)"),
    property_type: Optional[str] = Query(None, description="Filter by property_type"),
    min_score: Optional[float] = Query(None, description="Minimum opportunity score (not stored — use /api/listings with scoring)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List listings with optional filters. Returns active listings sorted by price descending."""
    conditions = ["is_active = 1"]
    params = []

    if city:
        conditions.append("city = ?")
        params.append(city)
    if area:
        conditions.append("area_name = ?")
        params.append(area)
    if purpose:
        conditions.append("purpose = ?")
        params.append(purpose)
    if property_type:
        conditions.append("property_type = ?")
        params.append(property_type)

    where = " AND ".join(conditions)

    with _connect() as conn:
        # Total count
        count_row = conn.execute(f"SELECT COUNT(*) AS cnt FROM listings WHERE {where}", params).fetchone()
        total = count_row["cnt"]

        # Paginated results
        rows = conn.execute(
            f"""SELECT id, source, purpose, property_type, title, price, currency,
                       area_sqft, bedrooms, bathrooms, city, area_name, location_full,
                       url, is_offplan, listed_date, first_seen, last_seen,
                       price_on_first,
                       CASE WHEN area_sqft > 0 THEN ROUND(price / area_sqft, 1) ELSE NULL END AS price_per_sqft
                FROM listings
                WHERE {where}
                ORDER BY price DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "listings": [dict(r) for r in rows],
        }


# ─── GET /api/listings/{listing_id} ──────────────────────────────────
@router.get("/listings/{listing_id}")
def get_listing(listing_id: str):
    """Single listing detail with computed price/sqft."""
    with _connect() as conn:
        row = conn.execute(
            """SELECT *,
                      CASE WHEN area_sqft > 0 THEN ROUND(price / area_sqft, 1) ELSE NULL END AS price_per_sqft
               FROM listings WHERE id = ?""",
            (listing_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")

        listing = dict(row)

        # Compute area benchmark for context
        if listing.get("area_sqft") and listing["area_sqft"] > 0 and listing.get("city") and listing.get("area_name"):
            bench = conn.execute(
                """SELECT AVG(price / NULLIF(area_sqft, 0)) AS avg_psf,
                          COUNT(*) AS cnt
                   FROM listings
                   WHERE city = ? AND area_name = ? AND purpose = ?
                         AND is_active = 1 AND price > 0 AND area_sqft > 0""",
                (listing["city"], listing["area_name"], listing["purpose"]),
            ).fetchone()
            listing["area_avg_psf"] = round(bench["avg_psf"], 1) if bench["avg_psf"] else None
            listing["area_listing_count"] = bench["cnt"]
        else:
            listing["area_avg_psf"] = None
            listing["area_listing_count"] = 0

        return listing


# ─── GET /api/listings/{listing_id}/history ───────────────────────────
@router.get("/listings/{listing_id}/history")
def get_listing_history(listing_id: str):
    """Price history for a listing (chronological snapshots)."""
    with _connect() as conn:
        # Verify listing exists
        exists = conn.execute("SELECT id FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Listing not found")

        rows = conn.execute(
            "SELECT price, seen_at FROM listing_history WHERE listing_id = ? ORDER BY seen_at",
            (listing_id,),
        ).fetchall()

        return {
            "listing_id": listing_id,
            "history": [dict(r) for r in rows],
        }


# ─── GET /api/areas ──────────────────────────────────────────────────
@router.get("/areas")
def get_area_benchmarks(
    purpose: str = Query("sale", description="Purpose: sale or rent"),
):
    """Area benchmarks — average price/sqft per area with listing counts."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT city, area_name,
                      COUNT(*) AS listing_count,
                      ROUND(AVG(price / NULLIF(area_sqft, 0)), 1) AS avg_price_per_sqft,
                      ROUND(MIN(price / NULLIF(area_sqft, 0)), 1) AS min_price_per_sqft,
                      ROUND(MAX(price / NULLIF(area_sqft, 0)), 1) AS max_price_per_sqft,
                      ROUND(AVG(price), 0) AS avg_price
               FROM listings
               WHERE purpose = ? AND is_active = 1 AND price > 0 AND area_sqft > 0
               GROUP BY city, area_name
               HAVING listing_count >= 3
               ORDER BY listing_count DESC""",
            (purpose,),
        ).fetchall()

        return {"purpose": purpose, "areas": [dict(r) for r in rows]}


# ─── GET /api/stats ──────────────────────────────────────────────────
@router.get("/stats")
def get_stats():
    """Database statistics — totals, by city, by type, last scrape."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS cnt FROM listings").fetchone()["cnt"]
        active = conn.execute("SELECT COUNT(*) AS cnt FROM listings WHERE is_active = 1").fetchone()["cnt"]

        by_city = conn.execute(
            "SELECT city, COUNT(*) AS cnt FROM listings WHERE is_active = 1 GROUP BY city ORDER BY cnt DESC"
        ).fetchall()

        by_purpose = conn.execute(
            "SELECT purpose, COUNT(*) AS cnt FROM listings WHERE is_active = 1 GROUP BY purpose ORDER BY cnt DESC"
        ).fetchall()

        by_type = conn.execute(
            "SELECT property_type, COUNT(*) AS cnt FROM listings WHERE is_active = 1 AND property_type IS NOT NULL GROUP BY property_type ORDER BY cnt DESC"
        ).fetchall()

        # Last scrape date from run_log
        last_run = conn.execute(
            "SELECT started_at, source, status FROM run_log ORDER BY started_at DESC LIMIT 1"
        ).fetchone()

        # Average price per sqft (sale)
        avg_psf = conn.execute(
            """SELECT ROUND(AVG(price / NULLIF(area_sqft, 0)), 1) AS avg_psf
               FROM listings WHERE purpose = 'sale' AND is_active = 1 AND price > 0 AND area_sqft > 0"""
        ).fetchone()

        return {
            "total_listings": total,
            "active_listings": active,
            "avg_price_per_sqft": avg_psf["avg_psf"] if avg_psf else None,
            "by_city": [dict(r) for r in by_city],
            "by_purpose": [dict(r) for r in by_purpose],
            "by_type": [dict(r) for r in by_type],
            "last_scrape": dict(last_run) if last_run else None,
        }
