"""Notifications API — user notifications management."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.notification_service import (
    get_notifications, get_unread_count, mark_as_read, mark_all_read,
)

router = APIRouter()


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notifications = await get_notifications(db, str(current_user.id), unread_only, limit)
    unread = await get_unread_count(db, str(current_user.id))
    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
        "unread_count": unread,
    }


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await get_unread_count(db, str(current_user.id))
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await mark_as_read(db, notification_id)
    return {"message": "Уведомление прочитано"}


@router.post("/read-all")
async def read_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await mark_all_read(db, str(current_user.id))
    return {"message": "Все уведомления прочитаны"}
