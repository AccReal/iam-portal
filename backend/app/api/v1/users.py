from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.api.v1.deps import get_current_user
from app.core.permissions import require_admin
from app.core.security import verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.services.user_service import (
    get_users, get_user_by_id, create_user, update_user,
    block_user, unblock_user, reset_password, change_password,
)
from app.services.mfa_service import (
    begin_totp_setup, confirm_totp_setup, verify_totp,
    generate_sms_code, verify_sms_code,
)
from app.services.audit_service import log_event, get_audit_logs

router = APIRouter()


class MFAConfirmRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    code: str


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role.name if user.role else None,
        role_id=str(user.role_id) if user.role_id else None,
        is_active=user.is_active,
        is_blocked=user.is_blocked,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_current(current_user: User = Depends(get_current_user)):
    return _user_to_response(current_user)


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users, total = await get_users(db, page, per_page, search)
    return UserListResponse(
        users=[_user_to_response(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_new_user(
    body: UserCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user, temp_password = await create_user(
            db, body.email, body.full_name, body.phone, body.role_id, body.password
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    await log_event(
        db, admin.id, "user_created",
        resource_type="user", resource_id=str(user.id),
        ip=request.client.host if request.client else None,
        details={"temp_password": temp_password},
    )
    user_data = _user_to_response(user)
    return {**user_data.model_dump(), "temp_password": temp_password}


@router.put("/{user_id}", response_model=UserResponse)
async def update_existing_user(
    user_id: str,
    body: UserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await update_user(db, user_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await log_event(
        db, admin.id, "user_updated",
        resource_type="user", resource_id=user_id,
        ip=request.client.host if request.client else None,
    )
    return _user_to_response(user)


@router.post("/{user_id}/block")
async def block_user_endpoint(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if str(user_id) == str(admin.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя заблокировать собственный аккаунт")
    try:
        await block_user(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await log_event(
        db, admin.id, "user_blocked",
        resource_type="user", resource_id=user_id,
        ip=request.client.host if request.client else None,
    )
    return {"message": "Пользователь заблокирован"}


@router.post("/{user_id}/unblock")
async def unblock_user_endpoint(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        await unblock_user(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    await log_event(
        db, admin.id, "user_unblocked",
        resource_type="user", resource_id=user_id,
        ip=request.client.host if request.client else None,
    )
    return {"message": "Пользователь разблокирован"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        new_password = await reset_password(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"message": "Пароль сброшен", "temp_password": new_password}


# ---------------------------------------------------------------------------
# MFA — step 1: generate secret + QR, store pending in Redis
# ---------------------------------------------------------------------------

@router.post("/me/setup-mfa")
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return QR code and secret. MFA is NOT enabled yet — call confirm-mfa next."""
    data = await begin_totp_setup(str(current_user.id), current_user.email)
    return data


# ---------------------------------------------------------------------------
# MFA — step 2: verify code from authenticator app → enable MFA
# ---------------------------------------------------------------------------

@router.post("/me/confirm-mfa")
async def confirm_mfa(
    body: MFAConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify TOTP code against the pending secret and activate MFA."""
    secret = await confirm_totp_setup(str(current_user.id), body.code)
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный код или время настройки истекло. Начните заново.",
        )

    current_user.mfa_secret = secret
    current_user.mfa_method = "totp"
    current_user.mfa_enabled = True
    await db.flush()

    await log_event(db, current_user.id, "mfa_enabled", details={"method": "totp"})
    return {"message": "TOTP успешно настроен и включён"}


# ---------------------------------------------------------------------------
# MFA — disable: requires current TOTP code as confirmation
# ---------------------------------------------------------------------------

@router.post("/me/disable-mfa")
async def disable_mfa(
    body: MFADisableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA. Requires a valid current TOTP code to prevent social engineering."""
    if not current_user.mfa_enabled or not current_user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA не включена")

    if not verify_totp(current_user.mfa_secret, body.code):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Неверный код TOTP. Проверьте время на устройстве и попробуйте снова.")

    if settings.MFA_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MFA обязательна для всех пользователей и не может быть отключена.",
        )

    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_method = None
    await db.flush()

    await log_event(db, current_user.id, "mfa_disabled")
    return {"message": "MFA отключена"}


# ---------------------------------------------------------------------------
# SMS MFA — send code (secondary method, requires SMSC configured + phone)
# ---------------------------------------------------------------------------

@router.post("/me/send-sms-code")
async def send_sms_code(
    current_user: User = Depends(get_current_user),
):
    """Trigger SMS OTP send. Only available when SMSC is configured and user has a phone."""
    if not settings.SMSC_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMS-шлюз не настроен.",
        )
    if not current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У пользователя не указан номер телефона.",
        )
    await generate_sms_code(str(current_user.id), current_user.phone)
    return {"message": "SMS с кодом отправлено"}


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

@router.post("/me/change-password")
async def change_my_password(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.get("old_password", ""), current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль")
    await change_password(db, current_user, body["new_password"])
    return {"message": "Пароль изменён"}


@router.get("/me/activity")
async def get_my_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await get_audit_logs(
        db, user_id=str(current_user.id), per_page=limit,
    )
    return {"activities": items, "total": total}


@router.get("/mfa-config")
async def get_mfa_config():
    """Return MFA feature flags so the frontend can adapt its UI."""
    return {
        "mfa_required": settings.MFA_REQUIRED,
        "sms_enabled": settings.SMSC_ENABLED,
    }
