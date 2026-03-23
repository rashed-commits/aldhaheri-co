import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import engine
from backend.models import Base
from backend.routers import auth, chat, investments, statements, transactions, webhook
from backend.routers.transactions import verify_auth
from backend.notifications import send_statement_reminder, send_unidentified_alert
from backend.sweep import _sweep_zero_amounts
from backend.telegram_bot import poll_loop as telegram_poll_loop

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migrate: add close position columns if missing
        import sqlalchemy as sa
        try:
            await conn.execute(sa.text(
                "ALTER TABLE investment_positions ADD COLUMN status TEXT DEFAULT 'open'"
            ))
            logger.info("Migration: added 'status' column to investment_positions")
        except Exception:
            pass  # column already exists
        try:
            await conn.execute(sa.text(
                "ALTER TABLE investment_positions ADD COLUMN close_date TEXT"
            ))
            logger.info("Migration: added 'close_date' column to investment_positions")
        except Exception:
            pass
        try:
            await conn.execute(sa.text(
                "ALTER TABLE investment_positions ADD COLUMN close_price REAL"
            ))
            logger.info("Migration: added 'close_price' column to investment_positions")
        except Exception:
            pass

    # Seed initial investment positions if table is empty
    from backend.routers.investments import seed_positions
    from backend.db import async_session as _session
    async with _session() as db:
        await seed_positions(db)

    # Daily sweep at midnight UTC — soft-delete zero-amount transactions
    scheduler.add_job(_sweep_zero_amounts, "cron", hour=0, minute=0, id="sweep_zero")

    # Daily unidentified alert at 10:00 UTC (14:00 UAE) — only fires if count > 0
    scheduler.add_job(send_unidentified_alert, "cron", hour=10, minute=0, id="unidentified_alert")

    # Monthly statement reminder — 1st of each month at 09:00 UTC (13:00 UAE)
    scheduler.add_job(send_statement_reminder, "cron", day=1, hour=9, minute=0, id="stmt_reminder")

    scheduler.start()
    logging.getLogger(__name__).info("Scheduled: daily sweep (00:00), unidentified alert (10:00), monthly statement reminder (1st 09:00)")

    # Start Telegram chatbot polling in background
    import asyncio
    telegram_task = asyncio.create_task(telegram_poll_loop())

    yield

    telegram_task.cancel()
    scheduler.shutdown(wait=False)


app = FastAPI(title="SMS Finance", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aldhaheri.co", "https://finance.aldhaheri.co"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(webhook.router)
app.include_router(transactions.router)
app.include_router(statements.router)
app.include_router(chat.router)
app.include_router(investments.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "sms-finance"}


@app.post("/api/sweep")
async def trigger_sweep(
    _: str = Depends(verify_auth),
) -> dict:
    """Manually trigger zero-amount transaction sweep."""
    count = await _sweep_zero_amounts()
    return {"status": "ok", "deleted": count}
