import logging
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import engine
from backend.models import Base
from backend.routers import auth, statements, transactions, webhook
from backend.routers.transactions import verify_auth
from backend.sweep import _sweep_zero_amounts

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Daily sweep at midnight UTC — soft-delete zero-amount transactions
    scheduler.add_job(_sweep_zero_amounts, "cron", hour=0, minute=0, id="sweep_zero")
    scheduler.start()
    logging.getLogger(__name__).info("Scheduled daily zero-amount sweep at 00:00 UTC")

    yield

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
