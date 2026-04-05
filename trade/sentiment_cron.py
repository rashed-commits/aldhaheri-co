"""
Standalone FinBERT Sentiment Worker
====================================
Runs independently of the main trade pipeline. Fetches news headlines
for all configured tickers, scores them with ProsusAI/finbert, and
writes/merges results into ``data/sentiment.csv``.

Designed to run in its own container or cron job so the main pipeline
never loads the FinBERT model (~500 MB RAM).

Usage::

    python sentiment_cron.py          # fetch and score all tickers
    python sentiment_cron.py --dry-run  # fetch and score but don't write
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from src.config import CFG
from src.sentiment import fetch_all_sentiment
from src.utils import ensure_dir, get_logger, load_csv, save_csv

log = get_logger("sentiment-cron")


def run(dry_run: bool = False) -> None:
    sentiment = fetch_all_sentiment()

    if sentiment.empty:
        log.warning("No sentiment data collected — nothing to write.")
        return

    sentiment_path = CFG.data_dir / "sentiment.csv"
    ensure_dir(sentiment_path.parent)

    if dry_run:
        log.info("Dry-run: would write %d rows. Sample:", len(sentiment))
        log.info("\n%s", sentiment.head(10).to_string())
        return

    # Merge with existing history (accumulate over time)
    if sentiment_path.exists():
        existing = load_csv(sentiment_path)
        existing["date"] = pd.to_datetime(existing["date"])
        sentiment["date"] = pd.to_datetime(sentiment["date"])
        combined = pd.concat([existing, sentiment], ignore_index=True)
        combined = combined.drop_duplicates(
            subset=["date", "ticker"], keep="last"
        )
        combined = combined.sort_values(["ticker", "date"])
        save_csv(combined, sentiment_path, index=False)
        log.info(
            "Updated sentiment history: %d rows (%d new) -> %s",
            len(combined), len(sentiment), sentiment_path,
        )
    else:
        save_csv(sentiment, sentiment_path, index=False)
        log.info("Saved %d sentiment rows to %s", len(sentiment), sentiment_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="FinBERT sentiment worker")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and score but don't write",
    )
    args = parser.parse_args()

    log.info("=== Sentiment Worker ===")
    try:
        run(dry_run=args.dry_run)
    except Exception as exc:
        log.error("Sentiment worker failed: %s", exc, exc_info=True)
        sys.exit(1)
    log.info("Sentiment worker complete.")


if __name__ == "__main__":
    main()
