"""Daily sweep: soft-delete zero-amount transactions."""

import logging

from sqlalchemy import select, update

from backend.db import async_session
from backend.models import Transaction

logger = logging.getLogger(__name__)


async def _sweep_zero_amounts() -> int:
    """Soft-delete all non-deleted transactions where amount == 0."""
    async with async_session() as db:
        result = await db.execute(
            select(Transaction.id).where(
                Transaction.deleted == False,
                Transaction.amount == 0,
            )
        )
        ids = [r[0] for r in result.all()]

        if not ids:
            logger.info("sweep: no zero-amount transactions found")
            return 0

        await db.execute(
            update(Transaction)
            .where(Transaction.id.in_(ids))
            .values(deleted=True)
        )
        await db.commit()
        logger.info("sweep: soft-deleted %d zero-amount transactions (ids=%s)", len(ids), ids)
        return len(ids)
