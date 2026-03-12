from fastapi import APIRouter, HTTPException, Request

from models.auth import LoginRequest, LoginResponse, VerifyResponse
from services.auth import (
    blacklist_token,
    clear_failed_attempts,
    is_locked_out,
    is_token_blacklisted,
    record_failed_attempt,
    validate_credentials,
)
from utils.jwt_handler import create_token, decode_token

router = APIRouter()


def _extract_token(request: Request) -> str:
    """Extract Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return auth_header.removeprefix("Bearer ").strip()


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    """Authenticate a user and return a JWT token."""
    client_ip = request.client.host if request.client else "unknown"

    if is_locked_out(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    if not validate_credentials(body.username, body.password):
        record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    clear_failed_attempts(client_ip)
    token, expires_at = create_token(body.username)

    return LoginResponse(
        token=token,
        expires_at=expires_at.isoformat(),
    )


@router.get("/verify", response_model=VerifyResponse)
async def verify(request: Request) -> VerifyResponse:
    """Verify a JWT token is valid and not blacklisted."""
    token = _extract_token(request)

    if is_token_blacklisted(token):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return VerifyResponse(valid=True, username=payload["sub"])


@router.post("/logout")
async def logout(request: Request) -> dict:
    """Blacklist the provided token to log the user out."""
    token = _extract_token(request)

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    blacklist_token(token)
    return {"message": "logged out"}
