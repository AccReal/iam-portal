from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None


class UserBrief(BaseModel):
    id: str
    email: str
    full_name: str
    role: str | None
    mfa_enabled: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_setup_required: bool = False
    user: UserBrief


class MFARequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_method: str
    session_id: str


class MFAVerifyRequest(BaseModel):
    session_id: str
    code: str


class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str
