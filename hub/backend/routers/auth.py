import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from models.auth import (
    AuthStatusResponse,
    LoginRequest,
    LoginResponse,
    TotpLoginRequest,
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
from utils.jwt_handler import (
    create_totp_pending_token,
    decode_totp_pending_token,
)

router = APIRouter()

HUB_USERNAME = os.getenv("HUB_USERNAME", "admin")


def _is_totp_enabled(username: str) -> bool:
    """Check if TOTP is enabled for a user."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT enabled FROM totp_secrets WHERE username = ? AND enabled = 1",
            (username,),
        ).fetchone()
        return row is not None


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    """Password-based login. Returns totp_required=True if TOTP is enabled."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 30 minutes.",
        )

    if not verify_password(body.username, body.password):
        record_attempt(client_ip)
        await asyncio.sleep(2)  # Deliberate delay to slow brute-force attacks
        raise HTTPException(status_code=401, detail="Invalid username or password")

    clear_attempts(client_ip)

    # Check if TOTP is enabled — if so, don't create session yet
    if _is_totp_enabled(body.username):
        pending_token = create_totp_pending_token(body.username)
        return LoginResponse(
            message="TOTP verification required",
            user=body.username,
            totp_required=True,
            totp_token=pending_token,
        )

    # No TOTP — create session directly
    user_agent = request.headers.get("user-agent", "")
    _, jwt_token = create_session(body.username, client_ip, user_agent)
    set_session_cookie(response, jwt_token)

    return LoginResponse(message="Login successful", user=body.username)


@router.post("/login/totp", response_model=LoginResponse)
async def login_totp(body: TotpLoginRequest, request: Request, response: Response):
    """Complete login by verifying a TOTP code after password auth."""
    import pyotp

    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 30 minutes.",
        )

    # Validate the pending token
    username = decode_totp_pending_token(body.totp_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired TOTP token. Please log in again.")

    # Look up TOTP secret
    with get_db() as conn:
        row = conn.execute(
            "SELECT secret FROM totp_secrets WHERE username = ? AND enabled = 1",
            (username,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=400, detail="TOTP is not enabled for this account.")

    totp = pyotp.TOTP(row["secret"])
    if not totp.verify(body.code, valid_window=1):
        record_attempt(client_ip)
        await asyncio.sleep(2)
        raise HTTPException(status_code=401, detail="Invalid TOTP code.")

    clear_attempts(client_ip)
    user_agent = request.headers.get("user-agent", "")
    _, jwt_token = create_session(username, client_ip, user_agent)
    set_session_cookie(response, jwt_token)

    return LoginResponse(message="Login successful", user=username)


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
    """Check whether any passkeys/TOTP are registered (no auth required)."""
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM credentials").fetchone()
        passkey_count = row["cnt"] if row else 0

        totp_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM totp_secrets WHERE enabled = 1"
        ).fetchone()
        totp_count = totp_row["cnt"] if totp_row else 0

    return AuthStatusResponse(
        has_passkeys=passkey_count > 0,
        setup_required=passkey_count == 0,
        has_totp=totp_count > 0,
    )
