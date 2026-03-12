import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from models.auth import (
    AuthStatusResponse,
    LoginRequest,
    LoginResponse,
    VerifyResponse,
)
from services.auth import get_current_user, verify_password
from services.rate_limiter import check_rate_limit, clear_attempts, record_attempt
from services.session_store import (
    clear_session_cookie,
    create_session,
    revoke_session,
    set_session_cookie,
)
from utils.database import get_db

router = APIRouter()

HUB_USERNAME = os.getenv("HUB_USERNAME", "admin")


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    """Password-based login (fallback / initial setup)."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    if not verify_password(body.username, body.password):
        record_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    clear_attempts(client_ip)
    user_agent = request.headers.get("user-agent", "")
    _, jwt_token = create_session(body.username, client_ip, user_agent)
    set_session_cookie(response, jwt_token)

    return LoginResponse(message="Login successful", user=body.username)


@router.get("/verify", response_model=VerifyResponse)
async def verify(session: dict = Depends(get_current_user)):
    """Verify the current session is valid."""
    return VerifyResponse(valid=True, user=session["user_id"])


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Revoke the current session and clear the cookie."""
    token = request.cookies.get("session")
    if token:
        from utils.jwt_handler import decode_token

        payload = decode_token(token)
        if payload and payload.get("sid"):
            revoke_session(payload["sid"])

    clear_session_cookie(response)
    return {"message": "Logged out"}


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    """Check whether any passkeys are registered (no auth required)."""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM credentials").fetchone()
        count = row["cnt"] if row else 0

    return AuthStatusResponse(
        has_passkeys=count > 0,
        setup_required=count == 0,
    )
