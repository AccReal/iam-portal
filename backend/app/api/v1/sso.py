from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.sso_service import generate_auth_code, verify_auth_code, get_user_apps
from app.services.audit_service import log_event
from app.services.honeypot_service import check_honeypot

router = APIRouter()


@router.get("/authorize")
async def authorize(
    app_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None

    # Check honeypot
    is_trap = await check_honeypot(db, app_id, current_user, ip)
    if is_trap:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")

    try:
        code = await generate_auth_code(db, current_user, app_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    await log_event(
        db, current_user.id, "sso_authorize",
        resource_type="application", resource_id=app_id, ip=ip,
    )
    return {"code": code}


@router.post("/verify")
async def verify(body: dict):
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Код не указан")

    result = await verify_auth_code(code)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный или истёкший код")

    return {"valid": True, "user": result}


@router.get("/apps")
async def list_my_apps(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    apps = await get_user_apps(db, current_user)
    return {"apps": apps}


@router.get("/check-access")
async def check_access(
    app_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick access check used by desktop apps on launch.

    Unlike ``/authorize`` (which issues an OAuth code), this endpoint simply
    answers: is *this* authenticated user allowed into *this* application?
    Honeypots are treated as "not granted" and trigger an audit event.
    """
    import uuid as _uuid

    ip = request.client.host if request.client else None

    try:
        app_uuid = _uuid.UUID(app_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный app_id")

    # Honeypot first — any attempt is suspicious and must be logged.
    is_trap = await check_honeypot(db, app_id, current_user, ip)
    if is_trap:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")

    from sqlalchemy import select
    from app.models.application import Application
    from app.models.role import RolePermission

    app_result = await db.execute(select(Application).where(Application.id == app_uuid))
    app = app_result.scalar_one_or_none()
    if not app or not app.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приложение не найдено")

    if not current_user.role_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У пользователя нет роли")

    perm_result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id == current_user.role_id,
            RolePermission.application_id == app.id,
            RolePermission.can_read == True,
        )
    )
    perm = perm_result.scalar_one_or_none()
    if not perm:
        await log_event(
            db, current_user.id, "sso_access_denied",
            resource_type="application", resource_id=app_id, ip=ip, success=False,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к этому приложению")

    await log_event(
        db, current_user.id, "sso_access_granted",
        resource_type="application", resource_id=app_id, ip=ip,
    )

    return {
        "granted": True,
        "application": {
            "id": str(app.id),
            "name": app.name,
            "description": app.description,
        },
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role.name if current_user.role else None,
        },
        "permissions": {
            "can_read": perm.can_read,
            "can_write": perm.can_write,
            "can_export": perm.can_export,
        },
    }
