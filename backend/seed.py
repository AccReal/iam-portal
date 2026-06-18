"""
Seed script — creates initial data: roles, applications, admin user, test users.

Run on a fresh DB:
    python seed.py

Run to update application URLs/secrets/redirect_uris on an existing DB:
    python seed.py --update-apps
"""
import asyncio
import os
import sys
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine
from app.models import User, Role, RolePermission, Application, AuditLog, Notification
from app.core.security import hash_password, hash_token


# ---------------------------------------------------------------------------
# Fixed UUIDs for reproducibility
# ---------------------------------------------------------------------------

ROLE_ADMIN_ID     = uuid.UUID("10000000-0000-0000-0000-000000000001")
ROLE_MANAGER_ID   = uuid.UUID("10000000-0000-0000-0000-000000000002")
ROLE_ACCOUNTANT_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")
ROLE_USER_ID      = uuid.UUID("10000000-0000-0000-0000-000000000004")

APP_CRM_ID       = uuid.UUID("20000000-0000-0000-0000-000000000001")
APP_MAIL_ID      = uuid.UUID("20000000-0000-0000-0000-000000000002")
APP_1C_ID        = uuid.UUID("20000000-0000-0000-0000-000000000003")
APP_WAREHOUSE_ID = uuid.UUID("20000000-0000-0000-0000-000000000004")
APP_REPORTS_ID   = uuid.UUID("20000000-0000-0000-0000-000000000005")
APP_HONEYPOT_ID  = uuid.UUID("20000000-0000-0000-0000-000000000006")
APP_ODOO_ID      = uuid.UUID("20000000-0000-0000-0000-000000000007")
APP_NEXTCLOUD_ID = uuid.UUID("20000000-0000-0000-0000-000000000008")

USER_ADMIN_ID  = uuid.UUID("30000000-0000-0000-0000-000000000001")
USER_MARINA_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
USER_PETR_ID   = uuid.UUID("30000000-0000-0000-0000-000000000003")
USER_OLGA_ID   = uuid.UUID("30000000-0000-0000-0000-000000000004")


# ---------------------------------------------------------------------------
# Application definitions — source of truth for URLs and OAuth config
# ---------------------------------------------------------------------------

def _base(env_key: str, default: str) -> str:
    """Read a service's public base URL from env (localhost default for dev)."""
    return os.getenv(env_key, default).rstrip("/")


# Public base URLs per service. In production deploy.sh sets these env vars to
# https://<service>.<domain>; locally they fall back to the docker-compose ports.
CRM_URL       = _base("CRM_PUBLIC_URL", "http://localhost:8090")
MAIL_URL      = _base("MAIL_PUBLIC_URL", "http://localhost:8093")
WAREHOUSE_URL = _base("INVENTREE_PUBLIC_URL", "http://localhost:8092")
REPORTS_URL   = _base("GRAFANA_PUBLIC_URL", "http://localhost:8091")
ODOO_URL      = _base("ODOO_PUBLIC_URL", "http://localhost:8069")
NEXTCLOUD_URL = _base("NEXTCLOUD_PUBLIC_URL", "https://localhost:8443")


def build_apps() -> list[dict]:
    """Return application upsert data with current secrets and URLs."""
    return [
        # ---- EspoCRM (CRM) ----
        # client_secret: EspoCRMSecret2024
        dict(
            id=APP_CRM_ID,
            name="CRM Система",
            description="Управление клиентами и продажами",
            app_url=CRM_URL,
            icon="👥",
            integration_type="oauth",
            client_id="espocrm",
            client_secret_hash=hash_token("EspoCRMSecret2024"),
            redirect_uris=[f"{CRM_URL}/oauth-callback.php", f"{CRM_URL}/?entryPoint=oauthCallback"],
            allowed_scopes="openid profile email",
            is_active=True,
            is_honeypot=False,
        ),
        # ---- Roundcube (Mail) ----
        # client_secret: RoundcubeSecret2024
        dict(
            id=APP_MAIL_ID,
            name="Корпоративная почта",
            description="Веб-почта компании (Roundcube + Dovecot)",
            app_url=MAIL_URL,
            icon="✉️",
            integration_type="oauth",
            client_id="roundcube",
            client_secret_hash=hash_token("RoundcubeSecret2024"),
            redirect_uris=[f"{MAIL_URL}/index.php/login/oauth", f"{MAIL_URL}/"],
            allowed_scopes="openid profile email",
            is_active=True,
            is_honeypot=False,
        ),
        # ---- 1С Бухгалтерия (vault — не трогаем) ----
        dict(
            id=APP_1C_ID,
            name="1С Бухгалтерия",
            description="Бухгалтерский учёт",
            app_url="https://1c.company.ru",
            icon="💰",
            integration_type="vault",
            client_id=None,
            client_secret_hash=None,
            redirect_uris=None,
            allowed_scopes=None,
            is_active=True,
            is_honeypot=False,
        ),
        # ---- InvenTree (Склад) ----
        # client_secret: InvenTreeSecret2024
        dict(
            id=APP_WAREHOUSE_ID,
            name="Склад",
            description="Управление запасами и складской учёт",
            app_url=WAREHOUSE_URL,
            icon="📦",
            integration_type="oauth",
            client_id="inventree",
            client_secret_hash=hash_token("InvenTreeSecret2024"),
            redirect_uris=[f"{WAREHOUSE_URL}/accounts/iam-portal/login/callback/"],
            allowed_scopes="openid profile email",
            is_active=True,
            is_honeypot=False,
        ),
        # ---- Grafana (Отчёты) ----
        # client_secret: GrafanaOAuthSecret2024
        dict(
            id=APP_REPORTS_ID,
            name="Отчёты",
            description="Аналитика и дашборды (Grafana)",
            app_url=REPORTS_URL,
            icon="📊",
            integration_type="oauth",
            client_id="grafana",
            client_secret_hash=hash_token("GrafanaOAuthSecret2024"),
            redirect_uris=[f"{REPORTS_URL}/login/generic_oauth"],
            allowed_scopes="openid profile email",
            is_active=True,
            is_honeypot=False,
        ),
        # ---- Honeypot ----
        dict(
            id=APP_HONEYPOT_ID,
            name="Зарплаты топ-менеджеров",
            description="Конфиденциальная информация",
            app_url="https://secret.company.ru",
            icon="🔐",
            integration_type="oauth",
            client_id=None,
            client_secret_hash=None,
            redirect_uris=None,
            allowed_scopes=None,
            is_active=True,
            is_honeypot=True,
        ),
        # ---- Odoo ERP (OIDC RP) ----
        # client_secret: vB6jZ5-8lXQa_iJPzIj3xwqgWYToZqKXqUcLnmVG8_E
        dict(
            id=APP_ODOO_ID,
            name="Odoo ERP",
            description="Корпоративная ERP-система",
            app_url=f"{ODOO_URL}/web",
            icon="🏢",
            integration_type="oauth",
            client_id="odoo",
            client_secret_hash="8954aad775df76eac9e7ab729095849a977959883dee13e7cbfd9692f06c4e7a",
            redirect_uris=[f"{ODOO_URL}/auth_oauth/signin", f"{ODOO_URL}/iam/sso/callback"],
            allowed_scopes="openid profile email roles",
            is_active=True,
            is_honeypot=False,
        ),
        # ---- Nextcloud (OIDC RP) ----
        # client_secret: NMCvIRGI9mS3z60fRWAFQCPPHghthRWM4B73jUfk8Gg
        dict(
            id=APP_NEXTCLOUD_ID,
            name="Nextcloud",
            description="Корпоративное облачное хранилище",
            app_url=NEXTCLOUD_URL,
            icon="☁️",
            integration_type="oauth",
            client_id="nextcloud",
            client_secret_hash="b673c29b8f8a4bbdcc5da502d8b2feb14b0edba0d206ae22ae4951a1ff24fe5e",
            redirect_uris=[f"{NEXTCLOUD_URL}/apps/user_oidc/code"],
            allowed_scopes="openid profile email",
            is_active=True,
            is_honeypot=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Upsert applications (safe to run multiple times)
# ---------------------------------------------------------------------------

async def upsert_apps(db: AsyncSession) -> None:
    for app_data in build_apps():
        app_id = app_data["id"]
        existing = (await db.execute(
            select(Application).where(Application.id == app_id)
        )).scalar_one_or_none()

        if existing:
            await db.execute(
                update(Application)
                .where(Application.id == app_id)
                .values(
                    name=app_data["name"],
                    description=app_data["description"],
                    app_url=app_data["app_url"],
                    icon=app_data["icon"],
                    integration_type=app_data["integration_type"],
                    client_id=app_data["client_id"],
                    client_secret_hash=app_data["client_secret_hash"],
                    redirect_uris=app_data["redirect_uris"],
                    allowed_scopes=app_data["allowed_scopes"],
                    is_active=app_data["is_active"],
                    is_honeypot=app_data["is_honeypot"],
                )
            )
        else:
            db.add(Application(
                id=app_data["id"],
                name=app_data["name"],
                description=app_data["description"],
                app_url=app_data["app_url"],
                icon=app_data["icon"],
                integration_type=app_data["integration_type"],
                client_id=app_data["client_id"],
                client_secret_hash=app_data["client_secret_hash"],
                redirect_uris=app_data["redirect_uris"],
                allowed_scopes=app_data["allowed_scopes"],
                is_active=app_data["is_active"],
                is_honeypot=app_data["is_honeypot"],
            ))

    await db.flush()
    print("Upserted 8 applications")


# ---------------------------------------------------------------------------
# Full seed (first run)
# ---------------------------------------------------------------------------

async def seed():
    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(Role).where(Role.id == ROLE_ADMIN_ID))
        already_seeded = result.scalar_one_or_none() is not None

        if already_seeded:
            print("Roles already exist — skipping role/user creation.")
            print("Run with --update-apps to update application URLs and secrets.")
            return

        # --- Roles ---
        roles = [
            Role(id=ROLE_ADMIN_ID,      name="admin",      description="Полный доступ к системе"),
            Role(id=ROLE_MANAGER_ID,    name="manager",    description="Менеджер - доступ к CRM и отчётам"),
            Role(id=ROLE_ACCOUNTANT_ID, name="accountant", description="Бухгалтер - доступ к 1С и CRM (просмотр)"),
            Role(id=ROLE_USER_ID,       name="user",       description="Обычный пользователь - базовый доступ"),
        ]
        db.add_all(roles)
        await db.flush()
        print("Created roles: admin, manager, accountant, user")

        # --- Applications ---
        await upsert_apps(db)

        # --- Role Permissions ---
        permissions = [
            # Admin — full access
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_CRM_ID,       can_read=True,  can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_MAIL_ID,      can_read=True,  can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_1C_ID,        can_read=True,  can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_WAREHOUSE_ID, can_read=True,  can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_REPORTS_ID,   can_read=True,  can_write=True,  can_export=True),
            # Manager — CRM full, Mail, Reports
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_CRM_ID,     can_read=True,  can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_MAIL_ID,    can_read=True,  can_write=True,  can_export=False),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_REPORTS_ID, can_read=True,  can_write=False, can_export=True),
            # Accountant — 1C full, CRM read, Mail
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_1C_ID,   can_read=True,  can_write=True,  can_export=True,  require_mfa=True),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_CRM_ID,  can_read=True,  can_write=False, can_export=False),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_MAIL_ID, can_read=True,  can_write=True,  can_export=False),
            # User — Mail only
            RolePermission(role_id=ROLE_USER_ID, application_id=APP_MAIL_ID,       can_read=True,  can_write=True,  can_export=False),
            # Odoo — admin, manager, accountant
            RolePermission(role_id=ROLE_ADMIN_ID,      application_id=APP_ODOO_ID, can_read=True,  can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID,    application_id=APP_ODOO_ID, can_read=True,  can_write=True,  can_export=False),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_ODOO_ID, can_read=True,  can_write=False, can_export=False),
            # Nextcloud — all roles
            RolePermission(role_id=ROLE_ADMIN_ID,      application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID,    application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=True,  can_export=False),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=True,  can_export=False),
            RolePermission(role_id=ROLE_USER_ID,       application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=False, can_export=False),
            # Склад — admin, manager
            RolePermission(role_id=ROLE_ADMIN_ID,   application_id=APP_WAREHOUSE_ID, can_read=True, can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_WAREHOUSE_ID, can_read=True, can_write=True,  can_export=False),
            # Отчёты/Grafana — admin, manager
            RolePermission(role_id=ROLE_ADMIN_ID,   application_id=APP_REPORTS_ID, can_read=True, can_write=True,  can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_REPORTS_ID, can_read=True, can_write=False, can_export=True),
        ]
        db.add_all(permissions)
        await db.flush()
        print("Created role permissions matrix")

        # --- Users ---
        # Password for all test users: Test123456!@
        test_password_hash = hash_password("Test123456!@")

        users = [
            User(
                id=USER_ADMIN_ID,
                email="admin@company.ru",
                password_hash=test_password_hash,
                full_name="Администратор Системы",
                phone="+79001234567",
                role_id=ROLE_ADMIN_ID,
                is_active=True,
            ),
            User(
                id=USER_MARINA_ID,
                email="marina@company.ru",
                password_hash=test_password_hash,
                full_name="Марина Иванова",
                phone="+79001234568",
                role_id=ROLE_MANAGER_ID,
                is_active=True,
            ),
            User(
                id=USER_PETR_ID,
                email="petr@company.ru",
                password_hash=test_password_hash,
                full_name="Пётр Сидоров",
                phone="+79001234569",
                role_id=ROLE_ACCOUNTANT_ID,
                is_active=True,
            ),
            User(
                id=USER_OLGA_ID,
                email="olga@company.ru",
                password_hash=test_password_hash,
                full_name="Ольга Смирнова",
                phone="+79001234570",
                role_id=ROLE_USER_ID,
                is_active=True,
            ),
        ]
        db.add_all(users)
        await db.flush()
        print("Created 4 users (admin, marina, petr, olga)")
        print("Password for all users: Test123456!@")

        await db.commit()
        print("\nSeed completed successfully!")


# ---------------------------------------------------------------------------
# Update-only mode: refreshes app URLs / secrets without touching users/roles
# ---------------------------------------------------------------------------

async def update_apps_only():
    async with async_session() as db:
        await upsert_apps(db)
        await db.commit()
        print("\nApplication URLs and secrets updated successfully!")
        print("\nClient secrets (plaintext) for service configuration:")
        print("  espocrm   → EspoCRMSecret2024")
        print("  roundcube → RoundcubeSecret2024")
        print("  inventree → InvenTreeSecret2024")
        print("  grafana   → GrafanaOAuthSecret2024")
        print("  odoo      → vB6jZ5-8lXQa_iJPzIj3xwqgWYToZqKXqUcLnmVG8_E")
        print("  nextcloud → NMCvIRGI9mS3z60fRWAFQCPPHghthRWM4B73jUfk8Gg")


if __name__ == "__main__":
    if "--update-apps" in sys.argv:
        asyncio.run(update_apps_only())
    else:
        asyncio.run(seed())
