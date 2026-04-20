"""Notification service — in-app notifications with async email dispatch."""

import uuid
import logging
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    user_email: str | None = None,
) -> Notification:
    notif = Notification(
        user_id=uuid.UUID(user_id),
        type=notification_type,
        title=title,
        message=message,
    )
    db.add(notif)
    await db.flush()

    if user_email:
        _dispatch_email(notification_type, user_email, title, message)

    return notif


def _dispatch_email(notification_type: str, user_email: str, title: str, message: str) -> None:
    """Fire-and-forget: enqueue an email Celery task for in-app notification types."""
    from app.tasks.notification_tasks import send_email_notification
    from app.core.email_templates import new_device_email, suspicious_login_email

    if notification_type == "new_device":
        # html was pre-built by auth layer; fall back to plain message
        subject, html = title, f"<p>{message}</p>"
    elif notification_type == "suspicious_login":
        subject, html = title, f"<p>{message}</p>"
    else:
        subject, html = title, f"<p>{message}</p>"

    send_email_notification.delay(user_email, subject, html)
    logger.debug("[EMAIL QUEUED] type=%s to=%s", notification_type, user_email)


async def get_notifications(
    db: AsyncSession, user_id: str, unread_only: bool = False, limit: int = 20
) -> list[Notification]:
    conditions = [Notification.user_id == uuid.UUID(user_id)]
    if unread_only:
        conditions.append(Notification.is_read == False)

    result = await db.execute(
        select(Notification)
        .where(and_(*conditions))
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_unread_count(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == uuid.UUID(user_id),
            Notification.is_read == False,
        )
    )
    return result.scalar()


async def mark_as_read(db: AsyncSession, notification_id: str):
    result = await db.execute(
        select(Notification).where(Notification.id == uuid.UUID(notification_id))
    )
    notif = result.scalar_one_or_none()
    if notif:
        notif.is_read = True
        await db.flush()


async def mark_all_read(db: AsyncSession, user_id: str):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == uuid.UUID(user_id),
            Notification.is_read == False,
        )
    )
    for notif in result.scalars():
        notif.is_read = True
    await db.flush()
