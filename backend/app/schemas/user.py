from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    phone: str | None = None
    role_id: str | None = None
    password: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role_id: str | None = None
    is_active: bool | None = None
    mfa_enabled: bool | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    role: str | None
    role_id: str | None
    is_active: bool
    is_blocked: bool
    mfa_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
    page: int
    per_page: int
