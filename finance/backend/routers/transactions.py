import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db import get_db
from backend.models import (
    SummaryOut,
    Transaction,
    TransactionOut,
    TransactionUpdate,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["transactions"])

API_KEY = os.getenv("WEBHOOK_API_KEY", "")


def verify_auth(request: Request, x_api_key: Optional[str] = Header(None)) -> str:
    # Allow X-API-Key auth for webhooks / external integrations
    if x_api_key and x_api_key == API_KEY:
        return "api_key"
    # Otherwise validate the session cookie from aldhaheri.co
    user = get_current_user(request)
    return user.get("sub", "session_user")


@router.get("/transactions", response_model=list[TransactionOut])
async def list_transactions(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
    account: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
) -> list[TransactionOut]:
    stmt = select(Transaction).where(Transaction.deleted == False)

    if account:
        stmt = stmt.where(Transaction.account == account)
    if type:
        stmt = stmt.where(Transaction.transaction_type == type)
    if from_date:
        stmt = stmt.where(Transaction.date >= from_date)
    if to_date:
        stmt = stmt.where(Transaction.date <= to_date)

    stmt = stmt.order_by(Transaction.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [TransactionOut.model_validate(r) for r in rows]


@router.get("/transactions/summary", response_model=SummaryOut)
async def transaction_summary(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> SummaryOut:
    base_filter = Transaction.deleted == False

    # Unfiltered totals
    inflow_stmt = select(func.coalesce(func.sum(Transaction.value_aed), 0)).where(
        base_filter, Transaction.flow_type == "Inflow"
    )
    outflow_stmt = select(func.coalesce(func.sum(Transaction.value_aed), 0)).where(
        base_filter, Transaction.flow_type == "Outflow"
    )
    total_inflow = (await db.execute(inflow_stmt)).scalar() or 0.0
    total_outflow = (await db.execute(outflow_stmt)).scalar() or 0.0

    # By category — separate spend (Outflow) and income (Inflow)
    spend_cat_stmt = (
        select(
            Transaction.category,
            func.sum(Transaction.value_aed).label("total"),
        )
        .where(base_filter, Transaction.flow_type == "Outflow")
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.value_aed).desc())
    )
    spend_cat_result = await db.execute(spend_cat_stmt)
    by_category_spend = [
        {"category": r[0], "total": r[1]}
        for r in spend_cat_result.all()
    ]

    income_cat_stmt = (
        select(
            Transaction.category,
            func.sum(Transaction.value_aed).label("total"),
        )
        .where(base_filter, Transaction.flow_type == "Inflow")
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.value_aed).desc())
    )
    income_cat_result = await db.execute(income_cat_stmt)
    by_category_income = [
        {"category": r[0], "total": r[1]}
        for r in income_cat_result.all()
    ]

    # By account
    acct_stmt = (
        select(
            Transaction.account,
            func.sum(
                case((Transaction.flow_type == "Inflow", Transaction.value_aed), else_=0)
            ).label("inflow"),
            func.sum(
                case((Transaction.flow_type == "Outflow", Transaction.value_aed), else_=0)
            ).label("outflow"),
        )
        .where(base_filter)
        .group_by(Transaction.account)
    )
    acct_result = await db.execute(acct_stmt)
    by_account = [
        {"account": r[0], "inflow": r[1], "outflow": r[2]} for r in acct_result.all()
    ]

    # By month — grouped by category for frontend filtering
    month_stmt = (
        select(
            func.substr(Transaction.date, 7, 4).concat("-").concat(func.substr(Transaction.date, 1, 2)).label("month"),
            Transaction.category,
            func.sum(
                case((Transaction.flow_type == "Inflow", Transaction.value_aed), else_=0)
            ).label("inflow"),
            func.sum(
                case((Transaction.flow_type == "Outflow", Transaction.value_aed), else_=0)
            ).label("outflow"),
        )
        .where(base_filter)
        .group_by("month", Transaction.category)
        .order_by("month")
    )
    month_result = await db.execute(month_stmt)
    by_month = [
        {"month": r[0], "category": r[1], "inflow": r[2], "outflow": r[3]}
        for r in month_result.all()
    ]

    # By day — grouped by category for cumulative line chart
    day_stmt = (
        select(
            Transaction.date,
            Transaction.category,
            func.sum(
                case((Transaction.flow_type == "Inflow", Transaction.value_aed), else_=0)
            ).label("inflow"),
            func.sum(
                case((Transaction.flow_type == "Outflow", Transaction.value_aed), else_=0)
            ).label("outflow"),
        )
        .where(base_filter)
        .group_by(Transaction.date, Transaction.category)
        .order_by(Transaction.date)
    )
    day_result = await db.execute(day_stmt)
    by_day = [
        {"date": r[0], "category": r[1], "inflow": r[2], "outflow": r[3]}
        for r in day_result.all()
    ]

    return SummaryOut(
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        by_category_spend=by_category_spend,
        by_category_income=by_category_income,
        by_account=by_account,
        by_month=by_month,
        by_day=by_day,
    )


@router.patch("/transactions/{txn_id}", response_model=TransactionOut)
async def update_transaction(
    txn_id: int,
    update: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> TransactionOut:
    result = await db.execute(
        select(Transaction).where(Transaction.id == txn_id, Transaction.deleted == False)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if update.category is not None:
        txn.category = update.category
    if update.merchant is not None:
        txn.merchant = update.merchant

    await db.commit()
    await db.refresh(txn)
    return TransactionOut.model_validate(txn)


@router.delete("/transactions/{txn_id}", status_code=204)
async def delete_transaction(
    txn_id: int,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_auth),
) -> None:
    result = await db.execute(
        select(Transaction).where(Transaction.id == txn_id, Transaction.deleted == False)
    )
    txn = result.scalar_one_or_none()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn.deleted = True
    await db.commit()
