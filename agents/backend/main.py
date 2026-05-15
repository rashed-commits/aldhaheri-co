import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db import async_session, engine
from backend.migrations import run_migrations_and_seeds
from backend.models import Base
from backend.routers import (
    agents,
    auth,
    chat,
    crons,
    manager,
    memory,
    proposals,
    skills,
    user_profile,
)
from backend.services.scheduler import shutdown_scheduler, start_scheduler

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        await run_migrations_and_seeds(session)

    await start_scheduler()
    logger.info("agents-backend: schema, seeds, scheduler ready")

    yield

    shutdown_scheduler()


app = FastAPI(title="aldhaheri-agents", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aldhaheri.co",
        "https://agents.aldhaheri.co",
        "http://localhost:3004",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"https://.*\.aldhaheri\.co|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(manager.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(skills.router)
app.include_router(proposals.router)
app.include_router(user_profile.router)
app.include_router(crons.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "aldhaheri-agents"}
