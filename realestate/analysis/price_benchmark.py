"""
Price Benchmark Engine
======================
Builds rolling price-per-sqft benchmarks from the listings database.
Used to flag listings trading at a discount to their area average.
"""

from storage.db import _connect
from utils.logger import get_logger

log = get_logger()


def get_area_benchmarks(purpose: str = "sale") -> dict[str, dict]:
    """
    Return a dict keyed by (city, area_name) with benchmark stats:
      {
        ("abu-dhabi", "Al Reem Island"): {
            "avg_psf": 1829.0,
            "median_psf": 1750.0,
            "count": 70,
            "min_psf": 900.0,
            "max_psf": 3200.0,
        },
        ...
      }
    """
    benchmarks = {}

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT city, area_name,
                   COUNT(*) AS cnt,
                   AVG(price / NULLIF(area_sqft, 0))    AS avg_psf,
                   MIN(price / NULLIF(area_sqft, 0))    AS min_psf,
                   MAX(price / NULLIF(area_sqft, 0))    AS max_psf
            FROM listings
            WHERE purpose = ? AND is_active = 1
                  AND price > 0 AND area_sqft > 0
            GROUP BY city, area_name
            HAVING cnt >= 3
            ORDER BY cnt DESC
            """,
            (purpose,),
        ).fetchall()

        for r in rows:
            key = (r["city"], r["area_name"])
            benchmarks[key] = {
                "avg_psf":    round(r["avg_psf"], 1),
                "min_psf":    round(r["min_psf"], 1),
                "max_psf":    round(r["max_psf"], 1),
                "count":      r["cnt"],
            }

        # Compute median separately (SQLite has no MEDIAN)
        for (city, area), stats in benchmarks.items():
            psf_rows = conn.execute(
                """SELECT price / area_sqft AS psf
                   FROM listings
                   WHERE city=? AND area_name=? AND purpose=?
                         AND is_active=1 AND price>0 AND area_sqft>0
                   ORDER BY psf""",
                (city, area, purpose),
            ).fetchall()
            vals = [r["psf"] for r in psf_rows]
            mid = len(vals) // 2
            stats["median_psf"] = round(vals[mid], 1) if vals else stats["avg_psf"]

    log.info("Built benchmarks for %d areas (%s)", len(benchmarks), purpose)
    return benchmarks


def score_price_vs_benchmark(
    price: float,
    area_sqft: float,
    city: str,
    area_name: str,
    benchmarks: dict,
) -> dict:
    """
    Score a listing's price/sqft against its area benchmark.
    Returns:
      {
        "listing_psf": 1500.0,
        "area_avg_psf": 1829.0,
        "discount_pct": 18.0,      # positive = cheaper than avg
        "sub_score": 85.0,         # 0-100 normalised score
      }
    """
    if not area_sqft or area_sqft <= 0 or not price or price <= 0:
        return {"listing_psf": None, "area_avg_psf": None, "discount_pct": 0, "sub_score": 0}

    listing_psf = price / area_sqft
    key = (city, area_name)
    bench = benchmarks.get(key)

    if not bench or not bench.get("avg_psf"):
        return {"listing_psf": round(listing_psf, 1), "area_avg_psf": None, "discount_pct": 0, "sub_score": 0}

    avg_psf = bench["avg_psf"]
    discount_pct = ((avg_psf - listing_psf) / avg_psf) * 100  # positive = below avg

    # Normalise to 0-100:
    #   0% discount → 0 score
    #   10% discount → 50 score
    #   20%+ discount → 100 score (capped)
    if discount_pct <= 0:
        sub_score = 0.0
    elif discount_pct >= 20:
        sub_score = 100.0
    else:
        sub_score = min(100.0, (discount_pct / 20.0) * 100.0)

    return {
        "listing_psf": round(listing_psf, 1),
        "area_avg_psf": round(avg_psf, 1),
        "discount_pct": round(discount_pct, 1),
        "sub_score": round(sub_score, 1),
    }
