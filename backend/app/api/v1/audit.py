import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.core.permissions import require_admin_or_auditor
from app.models.user import User
from app.models.audit import AuditLog
from app.models.session import Session
from app.services.audit_service import get_audit_logs

router = APIRouter()


@router.get("")
async def list_audit_logs(
    user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(require_admin_or_auditor),
    db: AsyncSession = Depends(get_db),
):
    logs, total = await get_audit_logs(db, user_id, action, date_from, date_to, search, page, per_page)
    return {"logs": logs, "total": total, "page": page, "per_page": per_page}


@router.get("/export")
async def export_audit(
    format: str = Query("csv", regex="^(csv|xlsx)$"),
    user_id: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    _user: User = Depends(require_admin_or_auditor),
    db: AsyncSession = Depends(get_db),
):
    logs, _ = await get_audit_logs(db, user_id, action, date_from, date_to, search, page=1, per_page=10000)

    if format == "csv":
        return _export_csv(logs)
    else:
        return _export_xlsx(logs)


def _export_csv(logs: list[dict]) -> StreamingResponse:
    output = io.StringIO()
    output.write("Время,Пользователь,Email,Действие,IP,Успех,Риск,Детали\n")
    for log in logs:
        output.write(
            f"{log['created_at']},{log.get('user_name', '')},{log.get('user_email', '')},"
            f"{log['action']},{log.get('ip_address', '')},{log['success']},"
            f"{log.get('risk_score', '')},{log.get('details', '')}\n"
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


def _export_xlsx(logs: list[dict]) -> StreamingResponse:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Журнал аудита"
    ws.append(["Время", "Пользователь", "Email", "Действие", "IP", "Успех", "Риск", "Детали"])

    for log in logs:
        ws.append([
            log["created_at"],
            log.get("user_name", ""),
            log.get("user_email", ""),
            log["action"],
            log.get("ip_address", ""),
            "Да" if log["success"] else "Нет",
            log.get("risk_score", ""),
            str(log.get("details", "")),
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=audit_log.xlsx"},
    )


@router.get("/stats")
async def get_audit_stats(
    days: int = Query(7, ge=1, le=90),
    _user: User = Depends(require_admin_or_auditor),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics for audit logs"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    # Get total users count
    total_users_query = select(func.count(User.id))
    total_users_result = await db.execute(total_users_query)
    total_users = total_users_result.scalar() or 0
    
    # Get active sessions count
    active_sessions_query = select(func.count(Session.id)).where(Session.expires_at > now)
    active_sessions_result = await db.execute(active_sessions_query)
    active_sessions = active_sessions_result.scalar() or 0
    
    # Get events today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    events_today_query = select(func.count(AuditLog.id)).where(AuditLog.created_at >= today_start)
    events_today_result = await db.execute(events_today_query)
    events_today = events_today_result.scalar() or 0
    
    # Get blocked users count
    blocked_users_query = select(func.count(User.id)).where(User.is_blocked == True)
    blocked_users_result = await db.execute(blocked_users_query)
    blocked_users = blocked_users_result.scalar() or 0
    
    # Get failed logins today
    failed_logins_query = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= today_start,
        AuditLog.action == 'login',
        AuditLog.success == False
    )
    failed_logins_result = await db.execute(failed_logins_query)
    failed_logins_today = failed_logins_result.scalar() or 0
    
    # Get high risk events today
    high_risk_query = select(func.count(AuditLog.id)).where(
        AuditLog.created_at >= today_start,
        AuditLog.risk_score >= 70
    )
    high_risk_result = await db.execute(high_risk_query)
    high_risk_events_today = high_risk_result.scalar() or 0
    
    # Get login trends for the period (daily breakdown)
    login_trends = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        # Successful logins
        success_query = select(func.count(AuditLog.id)).where(
            AuditLog.created_at >= day_start,
            AuditLog.created_at < day_end,
            AuditLog.action == 'login',
            AuditLog.success == True
        )
        success_result = await db.execute(success_query)
        successful = success_result.scalar() or 0
        
        # Failed logins
        failed_query = select(func.count(AuditLog.id)).where(
            AuditLog.created_at >= day_start,
            AuditLog.created_at < day_end,
            AuditLog.action == 'login',
            AuditLog.success == False
        )
        failed_result = await db.execute(failed_query)
        failed = failed_result.scalar() or 0
        
        login_trends.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "successful": successful,
            "failed": failed
        })
    
    # Get event distribution by action type
    event_dist_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).where(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.action)
    
    event_dist_result = await db.execute(event_dist_query)
    event_distribution = [
        {"action": row.action, "count": row.count}
        for row in event_dist_result
    ]
    
    # Get top 10 high-risk events
    top_risk_query = select(AuditLog).where(
        AuditLog.created_at >= today_start,
        AuditLog.risk_score.isnot(None)
    ).order_by(AuditLog.risk_score.desc()).limit(10)
    
    top_risk_result = await db.execute(top_risk_query)
    top_risk_events = []
    for log in top_risk_result.scalars():
        # Get user info if available
        user_email = None
        if log.user_id:
            user_query = select(User.email).where(User.id == log.user_id)
            user_result = await db.execute(user_query)
            user_email = user_result.scalar()
        
        top_risk_events.append({
            "id": str(log.id),
            "user_email": user_email,
            "action": log.action,
            "risk_score": log.risk_score,
            "created_at": log.created_at.isoformat(),
            "ip_address": log.ip_address,
            "details": log.details
        })
    
    return {
        "total_users": total_users,
        "active_sessions": active_sessions,
        "events_today": events_today,
        "blocked_users": blocked_users,
        "failed_logins_today": failed_logins_today,
        "high_risk_events_today": high_risk_events_today,
        "login_trends": login_trends,
        "event_distribution": event_distribution,
        "top_risk_events": top_risk_events
    }

