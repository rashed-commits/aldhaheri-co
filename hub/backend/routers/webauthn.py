import os
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from models.auth import CredentialResponse
from services.auth import get_current_user
from services.rate_limiter import check_rate_limit, clear_attempts, record_attempt
from services.session_store import (
    clear_session_cookie,
    create_session,
    set_session_cookie,
)
from utils.database import get_db

load_dotenv()

router = APIRouter()

RP_ID = os.getenv("RP_ID", "aldhaheri.co")
RP_NAME = "aldhaheri.co"
ORIGIN = os.getenv("RP_ORIGIN", "https://aldhaheri.co")

CHALLENGE_TTL = timedelta(minutes=5)


def _store_challenge(challenge: bytes, challenge_type: str, user_id: str | None = None) -> str:
    """Store a WebAuthn challenge in the database. Returns the challenge_id."""
    challenge_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + CHALLENGE_TTL

    with get_db() as conn:
        conn.execute(
            """INSERT INTO challenges (challenge_id, challenge, user_id, type, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                challenge_id,
                bytes_to_base64url(challenge),
                user_id,
                challenge_type,
                now.isoformat(),
                expires_at.isoformat(),
            ),
        )
    return challenge_id


def _get_and_delete_challenge(challenge_id: str, challenge_type: str) -> dict | None:
    """Retrieve and delete a challenge from the database."""
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM challenges WHERE challenge_id = ? AND type = ?",
            (challenge_id, challenge_type),
        ).fetchone()

        if row is None:
            return None

        conn.execute("DELETE FROM challenges WHERE challenge_id = ?", (challenge_id,))

        # Check expiry
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            return None

        return dict(row)


# --- Registration endpoints (require auth) ---


@router.post("/register/begin")
async def register_begin(session: dict = Depends(get_current_user)):
    """Generate WebAuthn registration options. Requires an active session."""
    user_id = session["user_id"]

    # Get existing credentials to exclude
    with get_db() as conn:
        rows = conn.execute(
            "SELECT credential_id FROM credentials WHERE user_id = ?", (user_id,)
        ).fetchall()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=row["credential_id"])
        for row in rows
    ]

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_id.encode("utf-8"),
        user_name=user_id,
        user_display_name=user_id,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    challenge_id = _store_challenge(options.challenge, "registration", user_id)

    # Convert options to JSON-serializable dict
    import json
    from webauthn.helpers import options_to_json
    options_json = json.loads(options_to_json(options))
    options_json["challenge_id"] = challenge_id

    return options_json


@router.post("/register/complete")
async def register_complete(request: Request, session: dict = Depends(get_current_user)):
    """Verify and store a new WebAuthn credential. Requires an active session."""
    user_id = session["user_id"]
    body = await request.json()

    challenge_id = body.get("challenge_id")
    if not challenge_id:
        raise HTTPException(status_code=400, detail="Missing challenge_id")

    challenge_record = _get_and_delete_challenge(challenge_id, "registration")
    if challenge_record is None:
        raise HTTPException(status_code=400, detail="Challenge expired or not found")

    expected_challenge = base64url_to_bytes(challenge_record["challenge"])

    try:
        verification = verify_registration_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration verification failed: {e}")

    credential_db_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO credentials
               (id, user_id, credential_id, public_key, sign_count, name, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                credential_db_id,
                user_id,
                verification.credential_id,
                verification.credential_public_key,
                verification.sign_count,
                body.get("name", "My Passkey"),
                now.isoformat(),
            ),
        )

    return {
        "message": "Credential registered",
        "credential_id": credential_db_id,
        "name": body.get("name", "My Passkey"),
    }


# --- Authentication endpoints (no auth required) ---


@router.post("/login/begin")
async def login_begin(request: Request):
    """Generate WebAuthn authentication options. No auth required."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    # Get all registered credentials
    with get_db() as conn:
        rows = conn.execute("SELECT credential_id FROM credentials").fetchall()

    if not rows:
        raise HTTPException(status_code=400, detail="No passkeys registered")

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=row["credential_id"])
        for row in rows
    ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    challenge_id = _store_challenge(options.challenge, "authentication")

    import json
    from webauthn.helpers import options_to_json
    options_json = json.loads(options_to_json(options))
    options_json["challenge_id"] = challenge_id

    return options_json


@router.post("/login/complete")
async def login_complete(request: Request, response: Response):
    """Verify WebAuthn authentication and create a session. No auth required."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    body = await request.json()

    challenge_id = body.get("challenge_id")
    if not challenge_id:
        raise HTTPException(status_code=400, detail="Missing challenge_id")

    challenge_record = _get_and_delete_challenge(challenge_id, "authentication")
    if challenge_record is None:
        raise HTTPException(status_code=400, detail="Challenge expired or not found")

    expected_challenge = base64url_to_bytes(challenge_record["challenge"])

    # Find the credential by raw_id from the response
    raw_id_b64 = body.get("rawId") or body.get("id")
    if not raw_id_b64:
        raise HTTPException(status_code=400, detail="Missing credential identifier")

    raw_id_bytes = base64url_to_bytes(raw_id_b64)

    with get_db() as conn:
        cred_row = conn.execute(
            "SELECT * FROM credentials WHERE credential_id = ?", (raw_id_bytes,)
        ).fetchone()

    if cred_row is None:
        record_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Unknown credential")

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=cred_row["public_key"],
            credential_current_sign_count=cred_row["sign_count"],
        )
    except Exception as e:
        record_attempt(client_ip)
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

    # Update sign count and last_used
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        conn.execute(
            "UPDATE credentials SET sign_count = ?, last_used = ? WHERE id = ?",
            (verification.new_sign_count, now.isoformat(), cred_row["id"]),
        )

    # Create session
    user_id = cred_row["user_id"]
    user_agent = request.headers.get("user-agent", "")
    _, jwt_token = create_session(user_id, client_ip, user_agent)
    set_session_cookie(response, jwt_token)
    clear_attempts(client_ip)

    return {"message": "Login successful", "user": user_id}


# --- Credential management endpoints (require auth) ---


@router.get("/credentials", response_model=list[CredentialResponse])
async def list_credentials(session: dict = Depends(get_current_user)):
    """List all registered passkey credentials for the current user."""
    user_id = session["user_id"]

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, last_used FROM credentials WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    return [
        CredentialResponse(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            last_used=row["last_used"],
        )
        for row in rows
    ]


@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: str, session: dict = Depends(get_current_user)):
    """Delete a passkey credential. Must keep at least one."""
    user_id = session["user_id"]

    with get_db() as conn:
        # Check credential belongs to user
        cred = conn.execute(
            "SELECT id FROM credentials WHERE id = ? AND user_id = ?",
            (credential_id, user_id),
        ).fetchone()

        if cred is None:
            raise HTTPException(status_code=404, detail="Credential not found")

        # Check that at least one credential remains
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM credentials WHERE user_id = ?",
            (user_id,),
        ).fetchone()

        if count["cnt"] <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last credential. Register a new one first.",
            )

        conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))

    return {"message": "Credential deleted"}
