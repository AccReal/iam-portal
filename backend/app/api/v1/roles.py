from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.v1.deps import get_current_user
from app.models.role import Role
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_roles(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).order_by(Role.name))
    roles = result.scalars().all()
    return {
        "roles": [
            {"id": str(r.id), "name": r.name, "description": r.description}
            for r in roles
        ]
    }
