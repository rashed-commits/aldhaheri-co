"""
One-time migration script: wipe Google Sheets imports, reimport from bank statements.

Usage (inside container):
    python -m backend.migrate_statements /data/statements --dry-run
    python -m backend.migrate_statements /data/statements --execute
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import select, update

from backend.categorizer import categorize
from backend.db import async_session, engine
from backend.models import Base, Transaction
from backend.statement_parser import parse_bank_csv, parse_cc_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def detect_format(filepath: str) -> str:
    with open(filepath, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "Transaction Date,Description,Cr/Dr" in line:
                return "cc"
            if "Posting Date,Value Date,Reference No" in line:
                return "bank"
    return "bank"


def infer_transaction_type(description: str, flow_type: str) -> str:
    desc_upper = description.upper()
    if "MBTRF" in desc_upper or "TRF OUT TO" in desc_upper or "TRF B/O" in desc_upper:
        return "TRANSFER"
    if "CREDIT CARD PAYMNT" in desc_upper:
        return "CC_PAYMENT"
    if "ATM WDL" in desc_upper:
        return "ATM_WITHDRAWAL"
    if desc_upper.strip() == "SALARY":
        return "SALARY"
    if "CHEQUE" in desc_upper or "CHDP" in desc_upper:
        return "CHEQUE_DEPOSIT" if flow_type == "Inflow" else "CHEQUE_PAYMENT"
    return "BANK_SMS"


async def run(stmt_dir: str, dry_run: bool):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # Step 1: Count and optionally wipe Google Sheets imports
        result = await db.execute(
            select(Transaction.id).where(
                Transaction.sms_raw == "imported from Google Sheets",
                Transaction.deleted == False,
            )
        )
        sheets_ids = [r[0] for r in result.all()]
        logger.info("Google Sheets imports to wipe: %d", len(sheets_ids))

        if not dry_run and sheets_ids:
            await db.execute(
                update(Transaction)
                .where(Transaction.id.in_(sheets_ids))
                .values(deleted=True)
            )
            await db.commit()
            logger.info("Wiped %d Google Sheets imports", len(sheets_ids))

        # Step 2: Parse all statement CSVs
        all_rows = []
        for fname in sorted(os.listdir(stmt_dir)):
            if not fname.endswith(".csv"):
                continue
            filepath = os.path.join(stmt_dir, fname)
            fmt = detect_format(filepath)
            if fmt == "cc":
                rows = parse_cc_csv(filepath)
            else:
                rows = parse_bank_csv(filepath)
            logger.info("Parsed %s (%s): %d rows", fname, fmt, len(rows))
            all_rows.extend(rows)

        # Filter to 2026
        rows_2026 = [r for r in all_rows if r["date"].endswith("/2026")]
        logger.info("Total statement rows: %d, 2026 only: %d", len(all_rows), len(rows_2026))

        # Step 3: Deduplicate against remaining DB transactions
        # Re-fetch non-deleted transactions (after wipe)
        remaining = await db.execute(
            select(Transaction).where(Transaction.deleted == False)
        )
        db_rows = remaining.scalars().all()

        # Build index: (date, value_aed, flow_type) -> True
        db_index = set()
        for r in db_rows:
            db_index.add((r.date, r.value_aed, r.flow_type))
            # Also add fuzzy dates
            try:
                dt = datetime.strptime(r.date, "%m/%d/%Y")
                for delta in range(-3, 4):
                    alt = (dt + timedelta(days=delta)).strftime("%m/%d/%Y")
                    db_index.add((alt, r.value_aed, r.flow_type))
            except (ValueError, TypeError):
                pass

        matched = 0
        to_import = []

        for row in rows_2026:
            key = (row["date"], row["amount"], row["flow_type"])
            if key in db_index:
                matched += 1
            else:
                merchant, category = categorize(row["description"], row["flow_type"])
                txn_type = infer_transaction_type(row["description"], row["flow_type"])
                to_import.append({
                    **row,
                    "merchant": merchant,
                    "category": category,
                    "transaction_type": txn_type,
                })

        logger.info("Already in DB: %d, To import: %d", matched, len(to_import))

        # Step 4: Import
        if not dry_run and to_import:
            for m in to_import:
                txn = Transaction(
                    sms_raw=f"statement import: {m['description']}",
                    transaction_type=m["transaction_type"],
                    account=m["account"],
                    amount=m["amount"],
                    currency=m["currency"],
                    value_aed=m["amount"],
                    date=m["date"],
                    time="12:00:00 AM",
                    merchant=m["merchant"],
                    category=m["category"],
                    flow_type=m["flow_type"],
                )
                db.add(txn)
            await db.commit()
            logger.info("Imported %d transactions", len(to_import))
        elif dry_run:
            logger.info("[DRY RUN] Would import %d transactions:", len(to_import))
            for m in to_import[:20]:
                logger.info(
                    "  %s  %s  %10.2f AED  %-30s  %s",
                    m["date"], m["flow_type"], m["amount"],
                    m["merchant"][:30], m["category"],
                )
            if len(to_import) > 20:
                logger.info("  ... and %d more", len(to_import) - 20)

        # Final count
        final = await db.execute(
            select(Transaction.id).where(Transaction.deleted == False)
        )
        final_count = len(final.all())
        logger.info("Final active transaction count: %d", final_count)


def main():
    parser = argparse.ArgumentParser(description="Migrate from Google Sheets to bank statements")
    parser.add_argument("stmt_dir", help="Directory containing statement CSVs")
    parser.add_argument("--execute", action="store_true", help="Actually run (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    dry_run = not args.execute
    if dry_run:
        logger.info("=== DRY RUN MODE (use --execute to apply) ===")
    else:
        logger.info("=== EXECUTE MODE — changes will be applied ===")

    asyncio.run(run(args.stmt_dir, dry_run))


if __name__ == "__main__":
    main()
