import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.webauthn import router as webauthn_router
from utils.database import init_db
from services.session_store import cleanup_expired

app = FastAPI(title="aldhaheri-hub", version="2.0.0")

# CORS configuration — specific origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://aldhaheri.co",
        "https://hub.aldhaheri.co",
        "https://www.aldhaheri.co",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ],
    allow_origin_regex=r"https://.*\.aldhaheri\.co|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(webauthn_router, prefix="/api/auth/webauthn", tags=["webauthn"])


@app.on_event("startup")
async def startup():
    """Initialize database tables on startup."""
    init_db()


@app.get("/")
async def root() -> dict:
    """Root endpoint returning service info."""
    return {"service": "aldhaheri-hub", "status": "ok"}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "aldhaheri-hub"}
