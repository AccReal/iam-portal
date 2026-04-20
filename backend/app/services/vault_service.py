"""Password Vault — AES-256-GCM encryption for legacy app credentials."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import UserCredential
from app.core.encryption import encrypt_vault, decrypt_vault


async def store_credential(
    db: AsyncSession,
    user_id: str,
    application_id: str,
    username: str,
    password: str,
    rotation_interval_days: int | None = None,
) -> UserCredential:
    enc_user = encrypt_vault(username)
    enc_pass = encrypt_vault(password)
    cred = UserCredential(
        user_id=uuid.UUID(user_id),
        application_id=uuid.UUID(application_id),
        encrypted_username=enc_user,
        encrypted_password=enc_pass,
        # Legacy column retained for schema compatibility; IV now lives inside each blob.
        encryption_iv=b"",
        rotation_interval_days=rotation_interval_days,
    )
    db.add(cred)
    await db.flush()
    return cred


async def get_credential(
    db: AsyncSession, user_id: str, application_id: str
) -> dict | None:
    result = await db.execute(
        select(UserCredential).where(
            UserCredential.user_id == uuid.UUID(user_id),
            UserCredential.application_id == uuid.UUID(application_id),
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return None

    try:
        username = decrypt_vault(cred.encrypted_username)
        password = decrypt_vault(cred.encrypted_password)
    except Exception:
        return None

    return {"username": username, "password": password}


async def update_credential_password(
    db: AsyncSession, cred_id: str, new_password: str
):
    result = await db.execute(
        select(UserCredential).where(UserCredential.id == uuid.UUID(cred_id))
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise ValueError("Учётные данные не найдены")

    cred.encrypted_password = encrypt_vault(new_password)
    cred.last_rotated_at = datetime.now(timezone.utc)
    await db.flush()
    return cred
