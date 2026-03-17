"""Statement upload, reconciliation, and import endpoints."""

import io
import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.categorizer import categorize
from backend.db import get_db
from backend.models import Transaction, TransactionOut
from backend.routers.transactions import verify_auth
from backend.statement_parser import parse_bank_csv, parse_cc_csv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/statements", tags=["statements"])


def _detect_format(filename: str, first_lines: list[str]) -> str:
    """Detect whether a CSV is a bank statement or credit card statement."""
    for line in first_lines[:10]:
        if "Transaction Date,Description,Cr/Dr" in line:
            return "cc"
        if "Posting Date,Value Date,Reference No" in line:
            return "bank"
    return "bank"


async def _find_duplicate(
    db: AsyncSession, date: str, amount: float, flow_type: str, account: str
) -> bool:
    """Check if a matching transaction already exists (exact or fuzzy date)."""
    try:
        dt = datetime.strptime(date, "%m/%d/%Y")
    except ValueError:
        return False

    for delta in range(-3, 4):
        alt_date = (dt + timedelta(days=delta)).strftime("%m/%d/%Y")
        result = await db.execute(
            select(Transaction.id).where(
                Transaction.deleted == False,
                Transaction.date == alt_date,
                Transaction.flow_type == flow_type,
                Transaction.value_aed == amount,
            )
        )
        if result.first() is not None:
            return True

    return False


def _infer_transaction_type(description: str, flow_type: str, category: str) -> str:
    """Infer transaction type from description and category."""
    desc_upper = description.upper()
    if "MBTRF" in desc_upper or "TRF OUT TO" in desc_upper or "TRF B/O" in desc_upper:
        return "TRANSFER"
    if "CREDIT CARD PAYMNT" in desc_upper:
        return "CC_PAYMENT"
    if "ATM WDL" in desc_upper:
        return "ATM_WITHDRAWAL"
    if "SALARY" == desc_upper.strip():
        return "SALARY"
    if "CHEQUE" in desc_upper or "CHDP" in desc_upper:
        if flow_type == "Inflow":
            return "CHEQUE_DEPOSIT"
        return "CHEQUE_PAYMENT"
    if "PUR " in desc_upper:
        return "BANK_SMS"
    return "BANK_SMS"


@router.post("/upload")
async def upload_statement(
    file: UploadFile = File(...),
    dry_run: bool = Query(True, description="Preview only, don't import"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> dict:
    """Upload a bank/CC statement CSV and import missing transactions."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()

    fmt = _detect_format(file.filename, lines)

    # Write to temp file for parser
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        if fmt == "cc":
            rows = parse_cc_csv(tmp_path)
        else:
            rows = parse_bank_csv(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Filter to 2026 only
    rows_2026 = [r for r in rows if r["date"].endswith("/2026")]

    matched = 0
    missing = []

    for row in rows_2026:
        is_dup = await _find_duplicate(
            db, row["date"], row["amount"], row["flow_type"], row["account"]
        )
        if is_dup:
            matched += 1
        else:
            merchant, category = categorize(row["description"], row["flow_type"])
            txn_type = _infer_transaction_type(row["description"], row["flow_type"], category)
            missing.append({
                **row,
                "merchant": merchant,
                "category": category,
                "transaction_type": txn_type,
            })

    imported = 0
    if not dry_run and missing:
        for m in missing:
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
            imported += 1
        await db.commit()

    return {
        "filename": file.filename,
        "format": fmt,
        "total_rows": len(rows),
        "rows_2026": len(rows_2026),
        "already_matched": matched,
        "missing": len(missing),
        "imported": imported if not dry_run else 0,
        "dry_run": dry_run,
        "missing_preview": [
            {
                "date": m["date"],
                "amount": m["amount"],
                "flow_type": m["flow_type"],
                "description": m["description"],
                "merchant": m["merchant"],
                "category": m["category"],
            }
            for m in missing[:50]
        ],
    }


@router.post("/import-all")
async def import_from_directory(
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> dict:
    """Import from all CSVs in /data/statements/ directory."""
    stmt_dir = "/data/statements"
    if not os.path.isdir(stmt_dir):
        raise HTTPException(status_code=404, detail=f"Directory {stmt_dir} not found")

    all_rows = []
    files_processed = []

    for fname in sorted(os.listdir(stmt_dir)):
        if not fname.endswith(".csv"):
            continue
        filepath = os.path.join(stmt_dir, fname)
        with open(filepath, encoding="utf-8", errors="replace") as f:
            first_lines = [f.readline() for _ in range(10)]

        fmt = _detect_format(fname, first_lines)
        if fmt == "cc":
            rows = parse_cc_csv(filepath)
        else:
            rows = parse_bank_csv(filepath)

        all_rows.extend(rows)
        files_processed.append({"file": fname, "format": fmt, "rows": len(rows)})

    # Filter to 2026
    rows_2026 = [r for r in all_rows if r["date"].endswith("/2026")]

    matched = 0
    missing = []

    for row in rows_2026:
        is_dup = await _find_duplicate(
            db, row["date"], row["amount"], row["flow_type"], row["account"]
        )
        if is_dup:
            matched += 1
        else:
            merchant, category = categorize(row["description"], row["flow_type"])
            txn_type = _infer_transaction_type(row["description"], row["flow_type"], category)
            missing.append({
                **row,
                "merchant": merchant,
                "category": category,
                "transaction_type": txn_type,
            })

    imported = 0
    if not dry_run and missing:
        for m in missing:
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
            imported += 1
        await db.commit()

    return {
        "files_processed": files_processed,
        "total_rows": len(all_rows),
        "rows_2026": len(rows_2026),
        "already_matched": matched,
        "missing": len(missing),
        "imported": imported if not dry_run else 0,
        "dry_run": dry_run,
    }


@router.post("/wipe-sheets-import")
async def wipe_google_sheets_import(
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> dict:
    """Soft-delete all transactions imported from Google Sheets."""
    result = await db.execute(
        select(Transaction.id).where(
            Transaction.sms_raw == "imported from Google Sheets",
            Transaction.deleted == False,
        )
    )
    ids = [r[0] for r in result.all()]

    if not dry_run and ids:
        await db.execute(
            update(Transaction)
            .where(Transaction.id.in_(ids))
            .values(deleted=True)
        )
        await db.commit()

    return {
        "google_sheets_rows": len(ids),
        "deleted": len(ids) if not dry_run else 0,
        "dry_run": dry_run,
    }
