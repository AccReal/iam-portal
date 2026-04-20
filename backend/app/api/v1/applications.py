import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.v1.deps import get_current_user
from app.core.permissions import require_admin
from app.core.security import hash_token
from app.models.user import User
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationUpdate, ApplicationResponse
from app.services.audit_service import log_event

router = APIRouter()


def _app_to_response(app: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=str(app.id),
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        icon=app.icon,
        integration_type=app.integration_type,
        client_id=app.client_id,
        is_active=app.is_active,
        is_honeypot=app.is_honeypot,
        created_at=app.created_at,
    )


@router.get("")
async def list_applications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total = (await db.execute(select(func.count(Application.id)))).scalar()
    result = await db.execute(
        select(Application)
        .order_by(Application.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    apps = result.scalars().all()
    return {
        "applications": [_app_to_response(a) for a in apps],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    client_id = None
    client_secret = None
    client_secret_hash = None

    if body.integration_type in ("oauth", "saml"):
        client_id = f"app_{secrets.token_hex(16)}"
        client_secret = secrets.token_urlsafe(32)
        client_secret_hash = hash_token(client_secret)

    app = Application(
        name=body.name,
        description=body.description,
        app_url=body.app_url,
        icon=body.icon,
        integration_type=body.integration_type,
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        redirect_uris=body.redirect_uris,
        is_honeypot=body.is_honeypot,
    )
    db.add(app)
    await db.flush()

    await log_event(
        db, admin.id, "app_created",
        resource_type="application", resource_id=str(app.id),
        ip=request.client.host if request.client else None,
    )

    response = _app_to_response(app)
    result = response.model_dump()
    if client_secret:
        result["client_secret"] = client_secret  # show once
    return result


@router.put("/{app_id}")
async def update_application(
    app_id: str,
    body: ApplicationUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Application).where(Application.id == uuid.UUID(app_id)))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приложение не найдено")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(app, key, value)
    await db.flush()

    await log_event(
        db, admin.id, "app_updated",
        resource_type="application", resource_id=app_id,
        ip=request.client.host if request.client else None,
    )
    return _app_to_response(app)


@router.delete("/{app_id}")
async def delete_application(
    app_id: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Application).where(Application.id == uuid.UUID(app_id)))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приложение не найдено")

    await db.delete(app)
    await log_event(
        db, admin.id, "app_deleted",
        resource_type="application", resource_id=app_id,
        ip=request.client.host if request.client else None,
    )
    return {"message": "Приложение удалено"}
