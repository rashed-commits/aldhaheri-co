"""
UAE Real Estate API — FastAPI backend
=====================================
Read-only API layer on top of the existing SQLite listings database.
Provides listing search, area benchmarks, statistics, and price history.
Protected by cookie-based SSO shared across all aldhaheri.co services.
"""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import get_current_user
from routers.listings import router as listings_router

app = FastAPI(
    title="UAE Real Estate API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# CORS — allow specific origins with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aldhaheri.co", "https://realestate.aldhaheri.co", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(listings_router)


@app.get("/health")
def health():
    """Health check endpoint for Docker and monitoring."""
    return {"status": "ok", "service": "uae-realestate"}


@app.get("/api/auth/verify")
def verify_session(request: Request):
    user = get_current_user(request)
    return {"valid": True, "user": user.get("sub")}
