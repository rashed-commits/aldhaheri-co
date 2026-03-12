import os
import logging

from fastapi import APIRouter, HTTPException, Request
from jose import JWTError, jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"


def get_current_user(request: Request) -> dict:
    """Read and validate the session cookie set by aldhaheri.co."""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid session")


@router.get("/verify")
async def verify(request: Request) -> dict:
    user = get_current_user(request)
    return {"valid": True, "username": user.get("sub")}
