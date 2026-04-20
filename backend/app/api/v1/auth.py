import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.core.rate_limit import check_login_rate_limit
from app.schemas.auth import (
    LoginRequest, RegisterRequest, TokenResponse,
    MFARequiredResponse, MFAVerifyRequest, MFASetupResponse,
    RefreshRequest, UserBrief,
    ForgotPasswordRequest, ResetPasswordRequest, MessageResponse,
)
from app.services.auth_service import (
    register_user, authenticate_user, create_tokens_for_user,
    refresh_tokens, logout_user,
    create_mfa_session, get_mfa_session, delete_mfa_session,
    is_new_ip, request_password_reset, reset_password,
)
from app.services.mfa_service import verify_totp, verify_sms_code, generate_sms_code
from app.services.audit_service import log_event
from app.services.notification_service import create_notification
from app.api.v1.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
    )


def _now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await register_user(db, body.email, body.password, body.full_name, body.phone)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await log_event(db, user.id, "register", ip=request.client.host if request.client else None)
    result = await create_tokens_for_user(user, db, ip=request.client.host if request.client else None)
    _set_refresh_cookie(response, result["refresh_token"])
    return result


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await check_login_rate_limit(request)
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    # Peek at the user before authentication to get email for lockout notifications
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    pre_result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.email == body.email)
    )
    candidate = pre_result.scalar_one_or_none()

    try:
        user = await authenticate_user(db, body.email, body.password)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))

    if not user:
        # If the account just got locked (failed_login_count reset → locked_until set),
        # notify the owner via email.
        if candidate and candidate.locked_until:
            from app.core.email_templates import suspicious_login_email
            from app.tasks.notification_tasks import send_email_notification
            locked_str = candidate.locked_until.strftime("%Y-%m-%d %H:%M:%S")
            subj, html = suspicious_login_email(
                candidate.full_name, ip or "?", settings.MAX_FAILED_ATTEMPTS if hasattr(settings, "MAX_FAILED_ATTEMPTS") else 5, locked_str
            )
            send_email_notification.delay(candidate.email, subj, html)
            await create_notification(
                db,
                str(candidate.id),
                "suspicious_login",
                "Аккаунт заблокирован",
                f"Зафиксировано несколько неудачных попыток входа с IP {ip}. Аккаунт временно заблокирован.",
            )

        await log_event(db, None, "login_failed", ip=ip, success=False, details={"email": body.email})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")

    if user.mfa_enabled:
        method = user.mfa_method or "totp"
        session_id = await create_mfa_session(str(user.id), method)

        if method == "sms":
            code = await generate_sms_code(str(user.id))
            logger.info("sms_mfa_code_generated user_id=%s", user.id)
            if settings.DEBUG:
                logger.debug("sms_mfa_code user_id=%s code=%s", user.id, code)

        return MFARequiredResponse(mfa_method=method, session_id=session_id)

    # Check for new device before anomaly so anomaly notification is created last
    new_device = await is_new_ip(db, user.id, ip)
    if new_device:
        from app.core.email_templates import new_device_email
        from app.tasks.notification_tasks import send_email_notification
        subj, html = new_device_email(user.full_name, ip or "?", user_agent, _now_utc_str())
        send_email_notification.delay(user.email, subj, html)
        await create_notification(
            db,
            str(user.id),
            "new_device",
            "Вход с нового устройства",
            f"Зафиксирован вход с нового IP-адреса: {ip}.",
        )

    # Anomaly detection — calculate risk score and process if high risk (notification created last)
    from app.services.anomaly_service import calculate_risk_score, process_anomaly
    risk_score = await calculate_risk_score(db, user, ip, user_agent)
    await process_anomaly(db, user, risk_score, ip)

    if user.is_blocked:
        await log_event(db, user.id, "login", ip=ip, success=False,
                        details={"risk_score": risk_score, "blocked_by_anomaly": True})
        await db.commit()  # Persist block before HTTPException triggers rollback
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован из-за подозрительной активности.",
        )

    await log_event(db, user.id, "login", ip=ip, details={"user_agent": user_agent}, risk_score=risk_score)
    result = await create_tokens_for_user(user, db, ip=ip, user_agent=user_agent)

    _set_refresh_cookie(response, result["refresh_token"])
    return result


@router.post("/verify-mfa", response_model=TokenResponse)
async def verify_mfa(
    body: MFAVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    session_data = await get_mfa_session(body.session_id)
    if not session_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сессия MFA истекла или недействительна")

    user_id_str, method = session_data

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(select(User).options(selectinload(User.role)).where(User.id == uuid.UUID(user_id_str)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    if method == "totp":
        if not verify_totp(user.mfa_secret, body.code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный код")
    elif method == "sms":
        if not await verify_sms_code(user_id, body.code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный код")

    await delete_mfa_session(body.session_id)
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")

    new_device = await is_new_ip(db, user.id, ip)
    await log_event(db, user.id, "login", ip=ip, details={"mfa": method})
    tokens = await create_tokens_for_user(user, db, ip=ip, user_agent=user_agent)

    if new_device:
        from app.core.email_templates import new_device_email
        from app.tasks.notification_tasks import send_email_notification
        subj, html = new_device_email(user.full_name, ip or "?", user_agent, _now_utc_str())
        send_email_notification.delay(user.email, subj, html)
        await create_notification(
            db,
            str(user.id),
            "new_device",
            "Вход с нового устройства",
            f"Зафиксирован вход с нового IP-адреса: {ip}.",
        )

    _set_refresh_cookie(response, tokens["refresh_token"])
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    body: RefreshRequest | None = None,
    cookie_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    token = cookie_refresh or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token отсутствует")

    result = await refresh_tokens(db, token)
    if not result:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh token")

    _set_refresh_cookie(response, result["refresh_token"])
    return result


@router.post("/logout")
async def logout(
    response: Response,
    body: RefreshRequest | None = None,
    cookie_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    token = cookie_refresh or (body.refresh_token if body else None)
    if token:
        await logout_user(db, token)
    _clear_refresh_cookie(response)
    return {"message": "Выход выполнен"}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return UserBrief(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.name if current_user.role else None,
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password-reset link. Always returns 200 to prevent user enumeration."""
    token = await request_password_reset(db, body.email)
    if token:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()
        if user:
            from app.core.email_templates import password_reset_email
            from app.tasks.notification_tasks import send_email_notification
            reset_url = f"{settings.APP_FRONTEND_URL}/reset-password?token={token}"
            subj, html = password_reset_email(user.full_name, reset_url)
            send_email_notification.delay(user.email, subj, html)
    return MessageResponse(message="Если аккаунт с таким email существует, письмо со ссылкой отправлено.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password_endpoint(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply a password reset using the one-time token from the email link."""
    user = await reset_password(db, body.token, body.new_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ссылка недействительна или истекла.",
        )

    from app.core.email_templates import password_changed_email
    from app.tasks.notification_tasks import send_email_notification
    subj, html = password_changed_email(user.full_name, _now_utc_str())
    send_email_notification.delay(user.email, subj, html)

    await log_event(db, user.id, "password_reset", details={"via": "email_token"})
    return MessageResponse(message="Пароль успешно изменён.")
