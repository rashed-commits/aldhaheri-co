"""
Composite Opportunity Scorer
=============================
Combines all four signals into a single 0-100 score per listing.
Only sale listings are scored (rent listings feed the yield calculator).

Signals & weights (yield-heavy profile):
  1. Rental yield        — 40%
  2. Price below avg/sqft — 25%
  3. Price drop           — 20%
  4. Off-plan with PP     — 15%
"""

from config import SCORING
from storage.db import _connect, get_price_history
from analysis.price_benchmark import get_area_benchmarks, score_price_vs_benchmark
from analysis.yield_calc import get_rental_benchmarks, score_rental_yield
from utils.logger import get_logger

log = get_logger()

WEIGHTS = SCORING["weights"]


def _score_price_drop(listing_id: str) -> dict:
    """
    Check if the listing's price has dropped since first seen.
    Returns:
      {
        "first_price": 1200000,
        "current_price": 1050000,
        "drop_pct": 12.5,
        "sub_score": 62.5,
      }
    """
    history = get_price_history(listing_id)
    if len(history) < 2:
        return {"first_price": None, "current_price": None, "drop_pct": 0, "sub_score": 0}

    first_price = history[0]["price"]
    current_price = history[-1]["price"]

    if not first_price or first_price <= 0:
        return {"first_price": first_price, "current_price": current_price, "drop_pct": 0, "sub_score": 0}

    drop_pct = ((first_price - current_price) / first_price) * 100

    # Normalise: 0% drop → 0, 5% drop → 50, 10%+ → 100
    if drop_pct <= 0:
        sub_score = 0.0
    elif drop_pct >= 10:
        sub_score = 100.0
    else:
        sub_score = (drop_pct / 10.0) * 100.0

    return {
        "first_price": first_price,
        "current_price": current_price,
        "drop_pct": round(drop_pct, 1),
        "sub_score": round(min(100.0, sub_score), 1),
    }


def _score_offplan(is_offplan: bool) -> dict:
    """Binary signal: off-plan = 100, ready = 0."""
    return {
        "is_offplan": is_offplan,
        "sub_score": 100.0 if is_offplan else 0.0,
    }


def score_all_listings() -> list[dict]:
    """
    Score every active sale listing in the database.
    Returns a sorted list (highest score first) of dicts:
      {
        "listing": { ...row data... },
        "composite_score": 72.5,
        "breakdown": {
            "price_below_avg": { sub_score, discount_pct, ... },
            "rental_yield": { sub_score, gross_yield_pct, ... },
            "price_drop": { sub_score, drop_pct, ... },
            "off_plan": { sub_score, is_offplan },
        }
      }
    """
    log.info("Starting opportunity scoring run...")

    # Pre-compute benchmarks
    sale_benchmarks = get_area_benchmarks("sale")
    rental_benchmarks = get_rental_benchmarks()

    # Fetch all active sale listings
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM listings
               WHERE purpose='sale' AND is_active=1 AND price > 0
               ORDER BY city, area_name"""
        ).fetchall()

    log.info("Scoring %d active sale listings", len(rows))
    scored = []

    for row in rows:
        listing = dict(row)
        lid = listing["id"]

        # Signal 1: Price below area average
        price_bench = score_price_vs_benchmark(
            listing["price"], listing["area_sqft"],
            listing["city"], listing["area_name"],
            sale_benchmarks,
        )

        # Signal 2: Rental yield
        yield_score = score_rental_yield(
            listing["price"], listing["city"], listing["area_name"],
            listing["bedrooms"], rental_benchmarks,
        )

        # Signal 3: Price drop since first seen
        drop_score = _score_price_drop(lid)

        # Signal 4: Off-plan
        offplan_score = _score_offplan(bool(listing.get("is_offplan")))

        # Composite
        composite = (
            WEIGHTS["price_below_avg"] * price_bench["sub_score"]
            + WEIGHTS["rental_yield"]  * yield_score["sub_score"]
            + WEIGHTS["price_drop"]    * drop_score["sub_score"]
            + WEIGHTS["off_plan_launch"] * offplan_score["sub_score"]
        )

        scored.append({
            "listing": listing,
            "composite_score": round(composite, 1),
            "breakdown": {
                "price_below_avg": price_bench,
                "rental_yield": yield_score,
                "price_drop": drop_score,
                "off_plan": offplan_score,
            },
        })

    # Sort by composite score descending
    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    log.info("Scoring complete. Top score: %.1f, listings above threshold (%d): %d",
             scored[0]["composite_score"] if scored else 0,
             SCORING["alert_threshold"],
             sum(1 for s in scored if s["composite_score"] >= SCORING["alert_threshold"]))

    return scored


def get_top_opportunities(min_score: float | None = None, limit: int | None = None) -> list[dict]:
    """Convenience: score all, filter by threshold, cap at limit."""
    threshold = min_score if min_score is not None else SCORING["alert_threshold"]
    cap = limit if limit is not None else SCORING["top_n_report"]

    all_scored = score_all_listings()
    filtered = [s for s in all_scored if s["composite_score"] >= threshold]
    return filtered[:cap]


def get_top_opportunities_split(
    min_score: float | None = None,
    limit_per_section: int | None = None,
) -> dict[str, list[dict]]:
    """
    Score all listings and return two ranked lists:
      - "offplan":  top N off-plan listings
      - "secondary": top N ready / non-off-plan listings
    """
    threshold = min_score if min_score is not None else SCORING["alert_threshold"]
    cap = limit_per_section if limit_per_section is not None else SCORING["top_n_report"]

    all_scored = score_all_listings()

    offplan = [
        s for s in all_scored
        if s["composite_score"] >= threshold and s["listing"].get("is_offplan")
    ][:cap]

    secondary = [
        s for s in all_scored
        if s["composite_score"] >= threshold and not s["listing"].get("is_offplan")
    ][:cap]

    log.info(
        "Split results — off-plan: %d (cap %d), secondary: %d (cap %d)",
        len(offplan), cap, len(secondary), cap,
    )
    return {"offplan": offplan, "secondary": secondary}
