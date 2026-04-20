import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.session import Session
from app.models.role import Role
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, hash_token, generate_temp_password,
)
from app.config import settings
from app.redis import redis_client


LOCKOUT_MINUTES = 30
MAX_FAILED_ATTEMPTS = 5
_PWD_RESET_TTL = 3600  # 1 hour


async def register_user(
    db: AsyncSession, email: str, password: str, full_name: str, phone: str | None = None
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Пользователь с таким email уже существует")

    # Assign default 'user' role
    role_result = await db.execute(select(Role).where(Role.name == "user"))
    default_role = role_result.scalar_one_or_none()

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        phone=phone,
        role_id=default_role.id if default_role else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, ["role"])
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.email == email)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None

    # Check lockout - handle timezone-naive datetimes from SQLite
    if user.locked_until:
        locked_until_aware = user.locked_until
        if locked_until_aware.tzinfo is None:
            locked_until_aware = locked_until_aware.replace(tzinfo=timezone.utc)
        if locked_until_aware > datetime.now(timezone.utc):
            raise PermissionError("Аккаунт временно заблокирован. Попробуйте позже.")

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        await db.flush()
        return None

    # Reset failed login count on success
    user.failed_login_count = 0
    user.locked_until = None
    await db.flush()
    return user


async def create_tokens_for_user(user: User, db: AsyncSession, ip: str | None = None, user_agent: str | None = None) -> dict:
    token_data = {"sub": str(user.id)}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Store session
    session = Session(
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        ip_address=ip,
        user_agent=user_agent,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(session)
    await db.flush()

    mfa_setup_required = settings.MFA_REQUIRED and not user.mfa_enabled

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "mfa_setup_required": mfa_setup_required,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.name if user.role else None,
            "mfa_enabled": user.mfa_enabled,
        },
    }


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict | None:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        return None

    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(Session).where(Session.refresh_token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    # Load user
    user_result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == session.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user or user.is_blocked:
        return None

    # Rotate: delete old session, create new
    await db.delete(session)
    return await create_tokens_for_user(user, db)


async def logout_user(db: AsyncSession, refresh_token: str):
    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(Session).where(Session.refresh_token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)


async def is_new_ip(db: AsyncSession, user_id: str, ip: str | None) -> bool:
    """Return True if this IP has never appeared in any previous session for the user."""
    if not ip:
        return False
    result = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.ip_address == ip,
        ).limit(1)
    )
    return result.scalar_one_or_none() is None


async def request_password_reset(db: AsyncSession, email: str) -> str | None:
    """Generate a reset token stored in Redis. Returns token or None if user not found."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return None

    token = secrets.token_urlsafe(48)
    await redis_client.setex(f"pwd_reset:{token}", _PWD_RESET_TTL, str(user.id))
    return token


async def reset_password(db: AsyncSession, token: str, new_password: str) -> User | None:
    """Verify reset token, update password, invalidate token. Returns User or None."""
    user_id = await redis_client.get(f"pwd_reset:{token}")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        return None

    user.password_hash = hash_password(new_password)
    await redis_client.delete(f"pwd_reset:{token}")
    await db.flush()
    return user


async def create_mfa_session(user_id: str, mfa_method: str) -> str:
    """Store MFA session in Redis, return session_id."""
    session_id = secrets.token_urlsafe(32)
    await redis_client.setex(f"mfa:{session_id}", 300, f"{user_id}:{mfa_method}")
    return session_id


async def get_mfa_session(session_id: str) -> tuple[str, str] | None:
    """Retrieve MFA session. Returns (user_id, method) or None."""
    data = await redis_client.get(f"mfa:{session_id}")
    if not data:
        return None
    user_id, method = data.split(":", 1)
    return user_id, method


async def delete_mfa_session(session_id: str):
    await redis_client.delete(f"mfa:{session_id}")
