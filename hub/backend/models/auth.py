from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    user: str


class VerifyResponse(BaseModel):
    valid: bool
    user: str


class AuthStatusResponse(BaseModel):
    has_passkeys: bool
    setup_required: bool


class CredentialResponse(BaseModel):
    id: str
    name: str
    created_at: str
    last_used: str | None


class RenameCredentialRequest(BaseModel):
    name: str
