"""
Trade-Bot API — FastAPI backend serving portfolio data for the dashboard.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, portfolio

app = FastAPI(title="Trade-Bot API", version="1.0.0")

# CORS — allow dashboard origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://aldhaheri.co", "https://trade.aldhaheri.co", "http://localhost:3003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint — no auth required
@app.get("/health")
def health():
    return {"status": "ok", "service": "trade-bot"}

# Session verification endpoint — no router-level auth
@app.get("/api/auth/verify")
def verify_session(request: Request):
    from routers.auth import get_current_user
    user = get_current_user(request)
    return {"valid": True, "user": user.get("sub")}

# Protected portfolio routes
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
