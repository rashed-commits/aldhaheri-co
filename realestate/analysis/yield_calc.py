"""
Gross Rental Yield Calculator
==============================
Estimates yield for sale listings by comparing their price to
comparable rental listings in the same area.

Gross Yield = (Annual Rent / Sale Price) × 100
"""

from storage.db import _connect
from utils.logger import get_logger

log = get_logger()


def get_rental_benchmarks() -> dict[tuple, dict]:
    """
    Build a lookup of median annual rents keyed by (city, area_name, bedrooms).
    Falls back to (city, area_name) if bedroom-level data is sparse.
    """
    rents: dict[tuple, dict] = {}

    with _connect() as conn:
        # Bedroom-level medians
        rows = conn.execute(
            """SELECT city, area_name, bedrooms,
                      COUNT(*) AS cnt
               FROM listings
               WHERE purpose='rent' AND is_active=1 AND price > 0
               GROUP BY city, area_name, bedrooms
               HAVING cnt >= 2
               ORDER BY cnt DESC"""
        ).fetchall()

        for r in rows:
            city, area, beds = r["city"], r["area_name"], r["bedrooms"]
            key = (city, area, beds)

            # NULL bedrooms need IS NULL (= NULL always returns false in SQL)
            if beds is None:
                prices = conn.execute(
                    """SELECT price FROM listings
                       WHERE city=? AND area_name=? AND bedrooms IS NULL
                             AND purpose='rent' AND is_active=1 AND price > 0
                       ORDER BY price""",
                    (city, area),
                ).fetchall()
            else:
                prices = conn.execute(
                    """SELECT price FROM listings
                       WHERE city=? AND area_name=? AND bedrooms=?
                             AND purpose='rent' AND is_active=1 AND price > 0
                       ORDER BY price""",
                    (city, area, beds),
                ).fetchall()

            vals = [p["price"] for p in prices]
            if not vals:
                log.debug("Skipping empty group: %s", key)
                continue

            mid = len(vals) // 2
            rents[key] = {
                "median_rent": vals[mid],
                "count": r["cnt"],
                "min_rent": vals[0],
                "max_rent": vals[-1],
            }

        # Area-level fallback (all bedrooms combined)
        area_rows = conn.execute(
            """SELECT city, area_name,
                      COUNT(*) AS cnt
               FROM listings
               WHERE purpose='rent' AND is_active=1 AND price > 0
               GROUP BY city, area_name
               HAVING cnt >= 3"""
        ).fetchall()

        for r in area_rows:
            key_area = (r["city"], r["area_name"], None)
            if key_area not in rents:
                prices = conn.execute(
                    """SELECT price FROM listings
                       WHERE city=? AND area_name=?
                             AND purpose='rent' AND is_active=1 AND price > 0
                       ORDER BY price""",
                    (r["city"], r["area_name"]),
                ).fetchall()
                vals = [p["price"] for p in prices]
                if not vals:
                    continue
                mid = len(vals) // 2
                rents[key_area] = {
                    "median_rent": vals[mid],
                    "count": r["cnt"],
                    "min_rent": vals[0],
                    "max_rent": vals[-1],
                }

    log.info("Built rental benchmarks for %d area/bedroom combos", len(rents))
    return rents


def score_rental_yield(
    sale_price: float,
    city: str,
    area_name: str,
    bedrooms: int | None,
    rental_benchmarks: dict,
) -> dict:
    """
    Estimate gross rental yield for a sale listing.
    Returns:
      {
        "estimated_annual_rent": 85000,
        "gross_yield_pct": 7.1,
        "sub_score": 73.3,         # 0-100 normalised
        "rent_source": "2BR Al Reem Island (5 comps)",
      }
    """
    if not sale_price or sale_price <= 0:
        return {"estimated_annual_rent": None, "gross_yield_pct": 0, "sub_score": 0, "rent_source": None}

    # Try bedroom-specific first, then area fallback
    rent_data = None
    source_label = ""

    if bedrooms is not None:
        key_br = (city, area_name, bedrooms)
        if key_br in rental_benchmarks:
            rent_data = rental_benchmarks[key_br]
            source_label = f"{bedrooms}BR {area_name} ({rent_data['count']} comps)"

    if not rent_data:
        key_area = (city, area_name, None)
        if key_area in rental_benchmarks:
            rent_data = rental_benchmarks[key_area]
            source_label = f"{area_name} all types ({rent_data['count']} comps)"

    if not rent_data:
        return {"estimated_annual_rent": None, "gross_yield_pct": 0, "sub_score": 0, "rent_source": None}

    annual_rent = rent_data["median_rent"]
    gross_yield = (annual_rent / sale_price) * 100

    # Normalise to 0-100:
    #   <4% yield → 0 score
    #   6% yield → 50 score (threshold from config)
    #   8%+ yield → 100 score (capped)
    if gross_yield <= 4.0:
        sub_score = 0.0
    elif gross_yield >= 8.0:
        sub_score = 100.0
    else:
        sub_score = ((gross_yield - 4.0) / 4.0) * 100.0

    return {
        "estimated_annual_rent": round(annual_rent, 0),
        "gross_yield_pct": round(gross_yield, 2),
        "sub_score": round(min(100.0, sub_score), 1),
        "rent_source": source_label,
    }
