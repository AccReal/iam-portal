"""Automatic password rotation for legacy systems."""

import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def rotate_expired_passwords():
    """Check for credentials that need rotation and rotate them."""
    import asyncio
    asyncio.run(_rotate_async())


async def _rotate_async():
    from sqlalchemy import select
    from app.database import async_session
    from app.models.credential import UserCredential
    from app.services.password_generator import generate_password
    from app.services.vault_service import update_credential_password
    from app.services.audit_service import log_event

    async with async_session() as db:
        try:
            result = await db.execute(
                select(UserCredential).where(
                    UserCredential.rotation_interval_days.is_not(None)
                )
            )
            credentials = result.scalars().all()

            now = datetime.now(timezone.utc)
            rotated = 0

            for cred in credentials:
                if not cred.rotation_interval_days:
                    continue

                last = cred.last_rotated_at or cred.created_at
                days_since = (now - last).days

                if days_since >= cred.rotation_interval_days:
                    new_password = generate_password(length=20, include_special=True)
                    await update_credential_password(db, str(cred.id), new_password)

                    await log_event(
                        db, cred.user_id, "password_rotated",
                        resource_type="credential", resource_id=str(cred.id),
                        details={"application_id": str(cred.application_id)},
                    )
                    rotated += 1

            await db.commit()
            logger.info(f"Password rotation complete: {rotated} credentials rotated")

        except Exception as e:
            await db.rollback()
            logger.error(f"Password rotation failed: {e}")
            raise
