#!/usr/bin/env python3
"""
UAE Real Estate Monitor Bot — Entry Point
==========================================
Usage:
  python main.py                              Full pipeline: scrape → score → report
  python main.py --scrape-only                Scrape only (no scoring/reporting)
  python main.py --score-only                 Score existing DB data
  python main.py --report-only                Generate PDF from last scoring run
  python main.py --pf-only                    PropertyFinder scraper only
  python main.py --skip-bayut                 Full pipeline minus Bayut
  python main.py --dry-run                    Fetch + print, no DB write
  python main.py --dry-run --limit-pages 2    Quick test
  python main.py --refresh-bayut-cookies      Launch browser to solve captcha
  python main.py --db-stats                   Show database statistics
"""

import argparse
import json
import sys
import time

from config import LOCATIONS, SCORING
from utils.logger import get_logger

log = get_logger()


def _db_stats():
    """Print database statistics."""
    import sqlite3
    from config import DB_PATH

    if not DB_PATH.exists():
        print("No database found. Run the pipeline first.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    print(f"\n{'='*60}")
    print(f"  DATABASE STATISTICS — {DB_PATH}")
    print(f"{'='*60}\n")

    total = conn.execute("SELECT COUNT(*) as c FROM listings").fetchone()["c"]
    print(f"Total listings: {total:,}")

    for purpose in ("sale", "rent"):
        cnt = conn.execute("SELECT COUNT(*) as c FROM listings WHERE purpose=?", (purpose,)).fetchone()["c"]
        print(f"  {purpose}: {cnt:,}")

    print("\nBy source:")
    for row in conn.execute("SELECT source, COUNT(*) as c FROM listings GROUP BY source ORDER BY c DESC"):
        print(f"  {row['source']}: {row['c']:,}")

    print("\nBy city:")
    for row in conn.execute("SELECT city, COUNT(*) as c FROM listings GROUP BY city ORDER BY c DESC"):
        print(f"  {row['city']}: {row['c']:,}")

    print("\nTop 10 areas (sale):")
    for row in conn.execute(
        """SELECT area_name, COUNT(*) as c,
                  ROUND(AVG(price), 0) as avg_price,
                  ROUND(AVG(price / NULLIF(area_sqft, 0)), 0) as avg_psf
           FROM listings WHERE purpose='sale' AND is_active=1
           GROUP BY area_name ORDER BY c DESC LIMIT 10"""
    ):
        print(f"  {row['area_name']:30s}  {row['c']:>5,} listings  avg AED {row['avg_price']:>12,.0f}  ({row['avg_psf'] or 0:,.0f}/sqft)")

    print("\nRecent runs:")
    for row in conn.execute(
        "SELECT * FROM run_log ORDER BY started_at DESC LIMIT 10"
    ):
        print(f"  {row['run_id']}  {row['status']:>8s}  fetched={row['listings_fetched']}  new={row['listings_new']}  updated={row['listings_updated']}")

    conn.close()


def _run_scoring():
    """Run the scoring engine and return split results."""
    from analysis.opportunity_score import get_top_opportunities_split
    split = get_top_opportunities_split()
    return split


def _run_report(split_or_scored):
    """Generate PDF and email it."""
    from alerts.pdf_report import generate_report
    from alerts.email_sender import send_report_email

    # Support both split dict and legacy list
    if isinstance(split_or_scored, dict) and "offplan" in split_or_scored:
        pdf_path = generate_report(split=split_or_scored)
        split = split_or_scored
    else:
        pdf_path = generate_report(split_or_scored)
        split = {"offplan": [], "secondary": split_or_scored}

    print(f"PDF report: {pdf_path}")

    # Email the report
    email_ok = send_report_email(split, pdf_path)
    if not email_ok:
        log.info("Email not sent (credentials not configured or failed). PDF saved locally.")

    return pdf_path


def main():
    parser = argparse.ArgumentParser(description="UAE Real Estate Monitor Bot")
    parser.add_argument("--scrape-only", action="store_true", help="Scrape only, no scoring/report")
    parser.add_argument("--score-only", action="store_true", help="Score existing DB data only")
    parser.add_argument("--report-only", action="store_true", help="Generate PDF from DB data")
    parser.add_argument("--pf-only", action="store_true", help="Only run PropertyFinder")
    parser.add_argument("--bayut-only", action="store_true", help="Only run Bayut (needs cookies)")
    parser.add_argument("--skip-bayut", action="store_true", help="Skip Bayut in full pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print — don't write to DB")
    parser.add_argument("--purpose", default="both", choices=["sale", "rent", "both"],
                        help="Which purpose to fetch (default: both)")
    parser.add_argument("--limit-pages", type=int, default=0,
                        help="Override max pages per search (0 = use config default)")
    parser.add_argument("--min-score", type=float, default=None,
                        help="Override minimum score threshold for report")
    parser.add_argument("--refresh-bayut-cookies", action="store_true",
                        help="Launch browser to solve Bayut captcha and save cookies")
    parser.add_argument("--db-stats", action="store_true", help="Show database statistics")
    args = parser.parse_args()

    # ── Special modes ────────────────────────────────────────────────
    if args.db_stats:
        _db_stats()
        return

    if args.refresh_bayut_cookies:
        from scrapers.bayut import refresh_bayut_cookies
        refresh_bayut_cookies()
        return

    # Override max pages if requested
    if args.limit_pages > 0:
        import config
        config.MAX_PAGES_PER_SEARCH = args.limit_pages

    start = time.time()

    # ── Score-only mode ──────────────────────────────────────────────
    if args.score_only:
        split = _run_scoring()
        all_scored = split["offplan"] + split["secondary"]
        print(f"\n{'='*60}")
        print(f"  SCORING RESULTS — {len(split['offplan'])} off-plan + {len(split['secondary'])} secondary")
        print(f"{'='*60}")
        for label, listings in [("OFF-PLAN", split["offplan"]), ("SECONDARY", split["secondary"])]:
            print(f"\n  --- {label} ---")
            for i, s in enumerate(listings[:10], 1):
                l = s["listing"]
                bd = s["breakdown"]
                yield_pct = bd["rental_yield"].get("gross_yield_pct", 0)
                discount = bd["price_below_avg"].get("discount_pct", 0)
                print(f"\n[{i}] Score: {s['composite_score']:.0f}/100")
                print(f"    {l['title']}")
                print(f"    {l['area_name']}, {'Abu Dhabi' if l['city'] == 'abu-dhabi' else 'Dubai'}")
                print(f"    AED {l['price']:,.0f}  |  Yield: {yield_pct:.1f}%  |  Discount: {discount:+.1f}%")
        elapsed = time.time() - start
        print(f"\nCompleted in {elapsed:.1f}s")
        return

    # ── Report-only mode ─────────────────────────────────────────────
    if args.report_only:
        scored = _run_scoring()
        pdf_path = _run_report(scored)
        elapsed = time.time() - start
        print(f"Report generated in {elapsed:.1f}s: {pdf_path}")
        return

    # ── Dry run ──────────────────────────────────────────────────────
    if args.dry_run:
        from scrapers.propertyfinder import fetch_pf_listings
        from scrapers.bayut import fetch_bayut_listings

        purposes = ["sale", "rent"] if args.purpose == "both" else [args.purpose]
        all_listings = []

        for purpose in purposes:
            if not args.bayut_only:
                all_listings.extend(fetch_pf_listings(purpose, LOCATIONS))
            if not args.pf_only:
                all_listings.extend(fetch_bayut_listings(purpose, LOCATIONS))

        print(f"\n{'='*60}")
        print(f"DRY RUN — {len(all_listings)} listings fetched")
        print(f"{'='*60}")

        from collections import Counter
        area_counts = Counter(l["area_name"] for l in all_listings)
        print("\nBy area:")
        for area, count in area_counts.most_common(20):
            print(f"  {area or '(unknown)':30s}  {count:>5,}")

        for i, l in enumerate(all_listings[:10]):
            psf = f"{l['price'] / l['area_sqft']:,.0f}/sqft" if l.get("area_sqft") and l["area_sqft"] > 0 else "?/sqft"
            offplan = " [OFF-PLAN]" if l.get("is_offplan") else ""
            print(f"\n[{i+1}] {l['source']} | {l['purpose']} | {l['area_name']}{offplan}")
            print(f"    {l['title']}")
            print(f"    AED {l['price']:,.0f}  |  {l.get('area_sqft') or '?'} sqft ({psf})  |  {l.get('bedrooms','?')} bed")

        elapsed = time.time() - start
        print(f"\nCompleted in {elapsed:.1f}s")
        return

    # ── Full pipeline: Scrape → Score → Report ───────────────────────
    from data.fetch_listings import run_full_pipeline

    if args.pf_only or args.bayut_only:
        # Single-source scrape
        from storage.db import init_db, upsert_listings, start_run, finish_run
        from data.fetch_listings import _generate_run_id
        from scrapers.propertyfinder import fetch_pf_listings
        from scrapers.bayut import fetch_bayut_listings

        init_db()
        purposes = ["sale", "rent"] if args.purpose == "both" else [args.purpose]
        total = 0

        for purpose in purposes:
            run_id = _generate_run_id()
            source = "bayut" if args.bayut_only else "pf"
            start_run(run_id, f"{source}_{purpose}")

            if args.bayut_only:
                listings = fetch_bayut_listings(purpose, LOCATIONS)
            else:
                listings = fetch_pf_listings(purpose, LOCATIONS)

            stats = upsert_listings(listings, run_id)
            finish_run(run_id, len(listings), stats["new"], stats["updated"], 0)
            total += len(listings)

        if not args.scrape_only:
            scored = _run_scoring()
            _run_report(scored)

        elapsed = time.time() - start
        log.info("Finished %d listings in %.1fs", total, elapsed)

        from notifications import notify_scrape_complete
        notify_scrape_complete(total, total, 0, elapsed)
    else:
        # Full pipeline
        summary = run_full_pipeline(skip_bayut=args.skip_bayut)

        if not args.scrape_only:
            scored = _run_scoring()
            _run_report(scored)
            summary["scored"] = len(scored.get("offplan", [])) + len(scored.get("secondary", []))

        elapsed = time.time() - start
        log.info("All done in %.1fs — summary: %s", elapsed, summary)
        print(json.dumps(summary, indent=2))

        from notifications import notify_scrape_complete
        notify_scrape_complete(
            summary.get("total_fetched", 0),
            summary.get("new", 0),
            summary.get("updated", 0),
            elapsed,
        )


if __name__ == "__main__":
    main()
