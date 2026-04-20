import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.user import User


async def log_event(
    db: AsyncSession,
    user_id: uuid.UUID | str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    details: dict | None = None,
    risk_score: int | None = None,
):
    entry = AuditLog(
        user_id=uuid.UUID(str(user_id)) if user_id else None,
        action=action,
        resource_type=resource_type,
        resource_id=uuid.UUID(resource_id) if resource_id else None,
        ip_address=ip,
        user_agent=user_agent,
        success=success,
        details=details,
        risk_score=risk_score,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_audit_logs(
    db: AsyncSession,
    user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    conditions = []
    if user_id:
        conditions.append(AuditLog.user_id == uuid.UUID(user_id))
    if action:
        conditions.append(AuditLog.action == action)
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    where_clause = and_(*conditions) if conditions else True

    # Count
    count_q = select(func.count(AuditLog.id)).where(where_clause)
    total = (await db.execute(count_q)).scalar()

    # Data
    query = (
        select(AuditLog)
        .where(where_clause)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    items = []
    for log in logs:
        # Fetch user info
        user_email = None
        user_name = None
        if log.user_id:
            user_r = await db.execute(select(User).where(User.id == log.user_id))
            u = user_r.scalar_one_or_none()
            if u:
                user_email = u.email
                user_name = u.full_name

        item = {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "user_email": user_email,
            "user_name": user_name,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": str(log.resource_id) if log.resource_id else None,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "success": log.success,
            "details": log.details,
            "risk_score": log.risk_score,
            "created_at": log.created_at.isoformat(),
        }
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            # Check if search query appears in any text field
            matches = False
            
            # Check user email
            if user_email and search_lower in user_email.lower():
                matches = True
            # Check user name
            elif user_name and search_lower in user_name.lower():
                matches = True
            # Check action
            elif log.action and search_lower in log.action.lower():
                matches = True
            # Check resource_type
            elif log.resource_type and search_lower in log.resource_type.lower():
                matches = True
            # Check IP address
            elif log.ip_address and search_lower in log.ip_address.lower():
                matches = True
            # Check user agent
            elif log.user_agent and search_lower in log.user_agent.lower():
                matches = True
            # Check details (convert to string)
            elif log.details and search_lower in str(log.details).lower():
                matches = True
            
            if matches:
                items.append(item)
        else:
            items.append(item)

    # If search was applied, update total count
    if search:
        total = len(items)

    return items, total
