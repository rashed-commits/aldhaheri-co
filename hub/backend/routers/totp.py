import base64
from datetime import datetime, timezone
from io import BytesIO

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException

from models.auth import TotpSetupResponse, TotpStatusResponse, TotpVerifyRequest
from services.auth import get_current_user
from utils.database import get_db

router = APIRouter()


def _get_totp_secret(username: str) -> tuple[str | None, bool]:
    """Return (secret, enabled) for a user, or (None, False) if not set up."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT secret, enabled FROM totp_secrets WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None, False
        return row["secret"], bool(row["enabled"])


@router.get("/status", response_model=TotpStatusResponse)
async def totp_status(session: dict = Depends(get_current_user)):
    """Check if TOTP is enabled for the current user."""
    _, enabled = _get_totp_secret(session["user_id"])
    return TotpStatusResponse(enabled=enabled)


@router.post("/setup", response_model=TotpSetupResponse)
async def totp_setup(session: dict = Depends(get_current_user)):
    """Generate a new TOTP secret and QR code for setup."""
    username = session["user_id"]

    # Check if already enabled
    _, enabled = _get_totp_secret(username)
    if enabled:
        raise HTTPException(status_code=400, detail="TOTP is already enabled. Disable it first to re-setup.")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=username, issuer_name="aldhaheri.co")

    # Generate QR code as base64 PNG
    img = qrcode.make(provisioning_uri)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Store secret (not yet enabled — user must verify first)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO totp_secrets (username, secret, enabled, created_at) VALUES (?, ?, 0, ?)",
            (username, secret, now),
        )

    return TotpSetupResponse(
        qr_code=qr_b64,
        secret=secret,
        message="Scan the QR code with Microsoft Authenticator, then verify with a code.",
    )


@router.post("/verify")
async def totp_verify(body: TotpVerifyRequest, session: dict = Depends(get_current_user)):
    """Verify a TOTP code to complete setup (enables TOTP)."""
    username = session["user_id"]
    secret, enabled = _get_totp_secret(username)

    if secret is None:
        raise HTTPException(status_code=400, detail="No TOTP setup in progress. Run setup first.")
    if enabled:
        raise HTTPException(status_code=400, detail="TOTP is already enabled.")

    totp = pyotp.TOTP(secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code. Please try again.")

    with get_db() as conn:
        conn.execute(
            "UPDATE totp_secrets SET enabled = 1 WHERE username = ?",
            (username,),
        )

    return {"message": "TOTP enabled successfully."}


@router.delete("/disable")
async def totp_disable(session: dict = Depends(get_current_user)):
    """Disable TOTP for the current user."""
    username = session["user_id"]
    with get_db() as conn:
        conn.execute("DELETE FROM totp_secrets WHERE username = ?", (username,))
    return {"message": "TOTP disabled."}
