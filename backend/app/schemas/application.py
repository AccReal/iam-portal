from datetime import datetime
from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    name: str
    description: str | None = None
    app_url: str | None = None
    icon: str | None = None
    integration_type: str  # 'oauth', 'saml', 'vault'
    redirect_uris: list[str] | None = None
    is_honeypot: bool = False


class ApplicationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    app_url: str | None = None
    icon: str | None = None
    integration_type: str | None = None
    redirect_uris: list[str] | None = None
    is_active: bool | None = None
    is_honeypot: bool | None = None


class ApplicationResponse(BaseModel):
    id: str
    name: str
    description: str | None
    app_url: str | None
    icon: str | None
    integration_type: str
    client_id: str | None
    is_active: bool
    is_honeypot: bool
    created_at: datetime

    class Config:
        from_attributes = True
