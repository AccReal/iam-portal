from functools import wraps
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User


class RequireRole:
    """FastAPI dependency to require a specific role."""

    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

    async def __call__(self, current_user: User = Depends(get_current_user)):
        if not current_user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Роль не назначена")
        if current_user.role.name not in self.allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return current_user


require_admin = RequireRole("admin")
require_admin_or_auditor = RequireRole("admin", "auditor")
