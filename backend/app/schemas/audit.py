from datetime import datetime
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    user_id: str | None
    user_email: str | None = None
    user_name: str | None = None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    success: bool
    details: dict | None
    risk_score: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    per_page: int
