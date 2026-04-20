import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.role import Role
from app.core.security import hash_password, generate_temp_password


async def get_users(
    db: AsyncSession, page: int = 1, per_page: int = 20, search: str | None = None
) -> tuple[list[User], int]:
    conditions = []
    if search:
        conditions.append(
            (User.full_name.ilike(f"%{search}%")) | (User.email.ilike(f"%{search}%"))
        )

    where = conditions[0] if conditions else True

    total_q = select(func.count(User.id)).where(where)
    total = (await db.execute(total_q)).scalar()

    query = (
        select(User)
        .options(selectinload(User.role))
        .where(where)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    return result.scalars().all(), total


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == uuid.UUID(user_id))
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, full_name: str, phone: str | None, role_id: str | None, password: str | None
) -> tuple[User, str]:
    """Create user with temp password. Returns (user, plain_password)."""
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Пользователь с таким email уже существует")

    plain_password = password or generate_temp_password()
    user = User(
        email=email,
        password_hash=hash_password(plain_password),
        full_name=full_name,
        phone=phone,
        role_id=uuid.UUID(role_id) if role_id else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user, ["role"])
    return user, plain_password


async def update_user(db: AsyncSession, user_id: str, **kwargs) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise ValueError("Пользователь не найден")

    for key, value in kwargs.items():
        if value is not None:
            if key == "role_id":
                value = uuid.UUID(value)
            setattr(user, key, value)

    await db.flush()
    await db.refresh(user, ["role"])
    return user


async def block_user(db: AsyncSession, user_id: str) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise ValueError("Пользователь не найден")
    user.is_blocked = True
    await db.flush()
    return user


async def unblock_user(db: AsyncSession, user_id: str) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise ValueError("Пользователь не найден")
    user.is_blocked = False
    user.failed_login_count = 0
    user.locked_until = None
    await db.flush()
    return user


async def reset_password(db: AsyncSession, user_id: str) -> str:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise ValueError("Пользователь не найден")
    new_password = generate_temp_password()
    user.password_hash = hash_password(new_password)
    await db.flush()
    return new_password


async def change_password(db: AsyncSession, user: User, new_password: str):
    user.password_hash = hash_password(new_password)
    await db.flush()
