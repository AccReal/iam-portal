"""SSO service — OAuth 2.0 authorization code flow."""

import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.user import User
from app.models.role import RolePermission
from app.redis import redis_client


async def generate_auth_code(
    db: AsyncSession, user: User, app_id: str
) -> str:
    """Generate an authorization code for SSO."""
    application = await db.execute(
        select(Application).where(Application.id == uuid.UUID(app_id))
    )
    app = application.scalar_one_or_none()
    if not app or not app.is_active:
        raise ValueError("Приложение не найдено или неактивно")

    # Check permissions
    if user.role_id:
        perm_result = await db.execute(
            select(RolePermission).where(
                RolePermission.role_id == user.role_id,
                RolePermission.application_id == app.id,
                RolePermission.can_read == True,
            )
        )
        perm = perm_result.scalar_one_or_none()
        if not perm:
            raise PermissionError("Нет доступа к этому приложению")

    code = secrets.token_urlsafe(32)
    data = json.dumps({
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if user.role else None,
        "app_id": app_id,
    })
    await redis_client.setex(f"sso_code:{code}", 300, data)
    return code


async def verify_auth_code(code: str) -> dict | None:
    """Verify an SSO authorization code. Returns user info or None."""
    data = await redis_client.get(f"sso_code:{code}")
    if not data:
        return None
    await redis_client.delete(f"sso_code:{code}")
    return json.loads(data)


async def get_user_apps(db: AsyncSession, user: User) -> list[dict]:
    """Get list of applications the user has access to."""
    if not user.role_id:
        return []

    result = await db.execute(
        select(RolePermission, Application)
        .join(Application, RolePermission.application_id == Application.id)
        .where(
            RolePermission.role_id == user.role_id,
            RolePermission.can_read == True,
            Application.is_active == True,
            Application.is_honeypot == False,
        )
    )
    rows = result.all()

    apps = []
    seen: set = set()
    for perm, app in rows:
        # Defensive de-dup: a role may have more than one permission row for the
        # same application (legacy seed data) — show each application only once.
        if app.id in seen:
            continue
        seen.add(app.id)
        apps.append({
            "id": str(app.id),
            "name": app.name,
            "description": app.description,
            "app_url": app.app_url,
            "icon": app.icon,
            "integration_type": app.integration_type,
            "client_id": app.client_id,
            "redirect_uris": app.redirect_uris or [],
            "allowed_scopes": app.allowed_scopes or "openid profile email",
            "permissions": {
                "can_read": perm.can_read,
                "can_write": perm.can_write,
                "can_export": perm.can_export,
            },
        })
    return apps
