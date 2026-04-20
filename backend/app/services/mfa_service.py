import secrets
import pyotp
import qrcode
from io import BytesIO
import base64
import logging

from app.config import settings
from app.redis import redis_client

logger = logging.getLogger(__name__)

_PENDING_TOTP_TTL = 600  # 10 minutes to complete setup
_SMS_CODE_TTL = 300       # 5 minutes


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.MFA_ISSUER)


def generate_qr_base64(uri: str) -> str:
    qr = qrcode.make(uri)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ---------------------------------------------------------------------------
# Two-step TOTP enrollment
# ---------------------------------------------------------------------------

async def begin_totp_setup(user_id: str, email: str) -> dict:
    """Generate a new TOTP secret, store it pending in Redis, return QR data.

    MFA is NOT yet enabled — the user must call confirm_totp_setup() with a
    valid code to activate it.
    """
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, email)
    qr_image = generate_qr_base64(uri)

    await redis_client.setex(f"totp_pending:{user_id}", _PENDING_TOTP_TTL, secret)
    return {"secret": secret, "qr_uri": uri, "qr_image": qr_image}


async def confirm_totp_setup(user_id: str, code: str) -> str | None:
    """Verify the code against the pending TOTP secret.

    Returns the secret on success (caller should persist it and enable MFA),
    or None if invalid / expired.
    """
    secret = await redis_client.get(f"totp_pending:{user_id}")
    if not secret:
        return None
    if not verify_totp(secret, code):
        return None
    await redis_client.delete(f"totp_pending:{user_id}")
    return secret


# ---------------------------------------------------------------------------
# SMS MFA via SMSC.ru (Celery task)
# ---------------------------------------------------------------------------

async def generate_sms_code(user_id: str, phone: str) -> None:
    """Generate a 6-digit OTP, store in Redis, dispatch Celery send task.

    If SMSC is not configured, logs the code in DEBUG mode only (dev fallback).
    """
    code = f"{secrets.randbelow(1000000):06d}"
    await redis_client.setex(f"sms_code:{user_id}", _SMS_CODE_TTL, code)

    if settings.SMSC_ENABLED and settings.SMSC_LOGIN and settings.SMSC_PASSWORD:
        from app.tasks.notification_tasks import send_sms_via_smsc
        message = f"Ваш код входа: {code}. Действителен 5 минут."
        send_sms_via_smsc.delay(phone, message, settings.SMSC_LOGIN, settings.SMSC_PASSWORD)
        logger.info("SMS MFA code dispatched via SMSC.ru for user_id=%s", user_id)
    else:
        logger.warning(
            "SMSC not configured — SMS not sent for user_id=%s. "
            "Set SMSC_LOGIN, SMSC_PASSWORD, SMSC_ENABLED=true in .env.",
            user_id,
        )
        if settings.DEBUG:
            logger.debug("sms_mfa_code user_id=%s code=%s", user_id, code)


async def verify_sms_code(user_id: str, code: str) -> bool:
    stored = await redis_client.get(f"sms_code:{user_id}")
    if stored and stored == code:
        await redis_client.delete(f"sms_code:{user_id}")
        return True
    return False
