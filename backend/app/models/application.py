import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    integration_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'oauth', 'saml', 'vault'
    client_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    client_secret_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    redirect_uris: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    # OIDC: space-separated list of allowed scopes, e.g. "openid profile email roles"
    allowed_scopes: Mapped[str | None] = mapped_column(String(500), nullable=True, default="openid profile email")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_honeypot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    role_permissions = relationship("RolePermission", back_populates="application", cascade="all, delete-orphan")
    credentials = relationship("UserCredential", back_populates="application", cascade="all, delete-orphan")
