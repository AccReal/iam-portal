from fastapi import APIRouter

from app.api.v1 import auth, users, password, applications, sso, audit, notifications, roles

api_router = APIRouter(prefix="/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["Аутентификация"])
api_router.include_router(users.router, prefix="/users", tags=["Пользователи"])
api_router.include_router(roles.router, prefix="/roles", tags=["Роли"])
api_router.include_router(password.router, prefix="/password", tags=["Пароли"])
api_router.include_router(applications.router, prefix="/applications", tags=["Приложения"])
api_router.include_router(sso.router, prefix="/sso", tags=["SSO"])
api_router.include_router(audit.router, prefix="/audit", tags=["Аудит"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Уведомления"])
