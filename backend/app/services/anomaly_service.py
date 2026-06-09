"""Anomaly detection — risk scoring based on IP, time, device, behavior."""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)

RISK_THRESHOLD = 70


async def calculate_risk_score(
    db: AsyncSession,
    user: User,
    ip: str | None,
    user_agent: str | None,
) -> int:
    """Calculate risk score (0-100) for a login attempt."""
    score = 0
    details = []

    if not ip:
        return 0

    # 1. Check if IP is new for this user (+20)
    known_ips = await db.execute(
        select(AuditLog.ip_address)
        .where(AuditLog.user_id == user.id, AuditLog.action == "login", AuditLog.success == True)
        .distinct()
    )
    known = {r[0] for r in known_ips.all() if r[0]}
    if ip not in known and len(known) > 0:
        score += 20
        details.append("Новый IP-адрес")

    # 2. GeoIP check — foreign country (+30)
    try:
        geo = await _get_geo_info(ip)
        if geo and geo.get("countryCode") and geo["countryCode"] != "RU":
            score += 30
            details.append(f"Вход из-за рубежа: {geo.get('country', 'Неизвестно')}")
    except Exception:
        pass

    # 3. Unusual time (+15) — outside 7:00-22:00 MSK
    now_msk = datetime.now(timezone.utc).hour + 3  # simplified UTC+3
    if now_msk < 7 or now_msk > 22:
        score += 15
        details.append("Вход в нерабочее время")

    # 4. New device/user-agent (+15)
    if user_agent:
        known_agents = await db.execute(
            select(AuditLog.user_agent)
            .where(AuditLog.user_id == user.id, AuditLog.action == "login", AuditLog.success == True)
            .distinct()
        )
        known_ua = {r[0] for r in known_agents.all() if r[0]}
        if user_agent not in known_ua and len(known_ua) > 0:
            score += 15
            details.append("Новое устройство/браузер")

    # 5. Recent failed attempts (+20)
    from datetime import timedelta
    recent_failures = await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.user_id == user.id,
            AuditLog.action == "login_failed",
            AuditLog.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    failures = recent_failures.scalar()
    if failures and failures >= 3:
        score += 20
        details.append(f"{failures} неудачных попыток за последний час")

    return min(100, score)


async def process_anomaly(
    db: AsyncSession, user: User, risk_score: int, ip: str | None
):
    """Handle high-risk login: block user and notify admins."""
    if risk_score < RISK_THRESHOLD:
        return

    user.is_blocked = True
    await db.flush()

    await create_notification(
        db, str(user.id), "alert",
        "Подозрительный вход заблокирован",
        f"Обнаружена подозрительная попытка входа (риск: {risk_score}/100, IP: {ip}). "
        f"Ваш аккаунт временно заблокирован.",
    )

    # Notify admins
    from app.models.role import Role
    admin_role = await db.execute(select(Role).where(Role.name == "admin"))
    role = admin_role.scalar_one_or_none()
    if role:
        admins = await db.execute(select(User).where(User.role_id == role.id, User.id != user.id))
        for admin in admins.scalars():
            await create_notification(
                db, str(admin.id), "warning",
                f"Подозрительная активность: {user.full_name}",
                f"Пользователь {user.email} заблокирован. Риск: {risk_score}/100, IP: {ip}.",
            )

    logger.warning(f"ANOMALY: User {user.email} blocked. Risk={risk_score}, IP={ip}")


async def get_user_typical_hours(db: AsyncSession, user_id) -> tuple | None:
    """Return (start_time, end_time) of typical login hours, or None if insufficient data."""
    return None


def _is_private_ip(ip: str) -> bool:
    """Return True for loopback, link-local and RFC-1918 private ranges."""
    return (
        ip in ("127.0.0.1", "::1", "localhost")
        or ip.startswith("10.")
        or ip.startswith("192.168.")
        or ip.startswith("172.16.")
        or ip.startswith("172.17.")
        or ip.startswith("172.18.")
        or ip.startswith("172.19.")
        or ip.startswith("172.2")
        or ip.startswith("172.3")
        or ip.startswith("fc00:")
        or ip.startswith("fd")
        or ip.startswith("fe80:")
    )


async def _get_geo_info(ip: str) -> dict | None:
    """Get geolocation info from ip-api.com (free tier)."""
    if _is_private_ip(ip):
        return {"countryCode": "RU", "country": "Local"}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip}?fields=country,countryCode,city")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None
