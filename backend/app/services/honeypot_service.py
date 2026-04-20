"""Honeypot — fake apps to detect compromised accounts."""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.user import User
from app.services.audit_service import log_event
from app.services.notification_service import create_notification


async def check_honeypot(
    db: AsyncSession, app_id: str, user: User, ip: str | None = None
) -> bool:
    """Check if the app is a honeypot. If yes, log alert and block user."""
    result = await db.execute(
        select(Application).where(Application.id == uuid.UUID(app_id))
    )
    app = result.scalar_one_or_none()
    if not app or not app.is_honeypot:
        return False

    # It's a honeypot! Log the event with high risk
    await log_event(
        db, user.id, "honeypot_triggered",
        resource_type="application", resource_id=app_id,
        ip=ip, risk_score=100,
        details={"app_name": app.name, "user_email": user.email},
    )

    # Block the user
    user.is_blocked = True
    await db.flush()

    # Notify all admins
    from app.models.role import Role
    admin_role = await db.execute(select(Role).where(Role.name == "admin"))
    role = admin_role.scalar_one_or_none()
    if role:
        from sqlalchemy import select as sel
        admins = await db.execute(sel(User).where(User.role_id == role.id))
        for admin in admins.scalars():
            await create_notification(
                db, str(admin.id), "honeypot_alert",
                f"Honeypot: {app.name}",
                f"Пользователь {user.full_name} ({user.email}) попытался получить доступ к ловушке '{app.name}'. Аккаунт автоматически заблокирован.",
            )

    return True
