from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    user: str
    totp_required: bool = False
    totp_token: str | None = None


class TotpLoginRequest(BaseModel):
    totp_token: str
    code: str


class VerifyResponse(BaseModel):
    valid: bool
    user: str


class AuthStatusResponse(BaseModel):
    has_passkeys: bool
    setup_required: bool
    has_totp: bool = False


class CredentialResponse(BaseModel):
    id: str
    name: str
    created_at: str
    last_used: str | None


class RenameCredentialRequest(BaseModel):
    name: str


class TotpSetupResponse(BaseModel):
    qr_code: str
    secret: str
    message: str


class TotpVerifyRequest(BaseModel):
    code: str


class TotpStatusResponse(BaseModel):
    enabled: bool
