"""
Seed script - creates initial data: roles, applications, admin user, test users.
Run: python seed.py
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, engine
from app.models import User, Role, RolePermission, Application, AuditLog, Notification
from app.core.security import hash_password


# Fixed UUIDs for reproducibility
ROLE_ADMIN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
ROLE_MANAGER_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
ROLE_ACCOUNTANT_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")
ROLE_USER_ID = uuid.UUID("10000000-0000-0000-0000-000000000004")

APP_CRM_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
APP_MAIL_ID = uuid.UUID("20000000-0000-0000-0000-000000000002")
APP_1C_ID = uuid.UUID("20000000-0000-0000-0000-000000000003")
APP_WAREHOUSE_ID = uuid.UUID("20000000-0000-0000-0000-000000000004")
APP_REPORTS_ID = uuid.UUID("20000000-0000-0000-0000-000000000005")
APP_HONEYPOT_ID = uuid.UUID("20000000-0000-0000-0000-000000000006")
# OIDC Relying Parties (Фаза 3)
APP_ODOO_ID = uuid.UUID("20000000-0000-0000-0000-000000000007")
APP_NEXTCLOUD_ID = uuid.UUID("20000000-0000-0000-0000-000000000008")

USER_ADMIN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
USER_MARINA_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
USER_PETR_ID = uuid.UUID("30000000-0000-0000-0000-000000000003")
USER_OLGA_ID = uuid.UUID("30000000-0000-0000-0000-000000000004")


async def seed():
    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(Role).where(Role.id == ROLE_ADMIN_ID))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        # --- Roles ---
        roles = [
            Role(id=ROLE_ADMIN_ID, name="admin", description="Полный доступ к системе"),
            Role(id=ROLE_MANAGER_ID, name="manager", description="Менеджер - доступ к CRM и отчётам"),
            Role(id=ROLE_ACCOUNTANT_ID, name="accountant", description="Бухгалтер - доступ к 1С и CRM (просмотр)"),
            Role(id=ROLE_USER_ID, name="user", description="Обычный пользователь - базовый доступ"),
        ]
        db.add_all(roles)
        await db.flush()
        print("Created roles: admin, manager, accountant, user")

        # --- Applications ---
        apps = [
            Application(
                id=APP_CRM_ID,
                name="CRM Система",
                description="Управление клиентами и продажами",
                app_url="https://crm.company.ru",
                icon="BarChartOutlined",
                integration_type="oauth",
                client_id="crm_client_001",
                is_active=True,
            ),
            Application(
                id=APP_MAIL_ID,
                name="Корпоративная почта",
                description="Email-сервер компании",
                app_url="https://mail.company.ru",
                icon="MailOutlined",
                integration_type="oauth",
                client_id="mail_client_001",
                is_active=True,
            ),
            Application(
                id=APP_1C_ID,
                name="1С Бухгалтерия",
                description="Бухгалтерский учёт",
                app_url="https://1c.company.ru",
                icon="DollarOutlined",
                integration_type="vault",
                is_active=True,
            ),
            Application(
                id=APP_WAREHOUSE_ID,
                name="Склад",
                description="Складской учёт",
                app_url="https://warehouse.company.ru",
                icon="ShopOutlined",
                integration_type="oauth",
                client_id="warehouse_client_001",
                is_active=True,
            ),
            Application(
                id=APP_REPORTS_ID,
                name="Отчёты",
                description="Система аналитической отчётности",
                app_url=None,
                icon="LineChartOutlined",
                integration_type="oauth",
                client_id="reports_client_001",
                is_active=True,
            ),
            Application(
                id=APP_HONEYPOT_ID,
                name="Зарплаты топ-менеджеров",
                description="Конфиденциальная информация",
                app_url="https://secret.company.ru",
                icon="LockOutlined",
                integration_type="oauth",
                is_active=True,
                is_honeypot=True,
            ),
            # OIDC Relying Parties — Odoo 17
            # client_secret: vB6jZ5-8lXQa_iJPzIj3xwqgWYToZqKXqUcLnmVG8_E
            # Odoo uses implicit flow → redirect to /web/session/authenticate
            Application(
                id=APP_ODOO_ID,
                name="Odoo ERP",
                description="Корпоративная ERP-система",
                app_url="http://localhost:8069/web",
                icon="🏢",
                integration_type="oauth",
                client_id="odoo",
                client_secret_hash="8954aad775df76eac9e7ab729095849a977959883dee13e7cbfd9692f06c4e7a",
                redirect_uris=["http://localhost:8069/iam/sso/callback"],
                allowed_scopes="openid profile email roles",
                is_active=True,
            ),
            # OIDC Relying Parties — Nextcloud 28
            # Access via HTTPS nginx proxy: https://localhost:8443
            # client_secret: NMCvIRGI9mS3z60fRWAFQCPPHghthRWM4B73jUfk8Gg
            Application(
                id=APP_NEXTCLOUD_ID,
                name="Nextcloud",
                description="Корпоративное облачное хранилище",
                app_url="https://localhost:8443",
                icon="☁️",
                integration_type="oauth",
                client_id="nextcloud",
                client_secret_hash="b673c29b8f8a4bbdcc5da502d8b2feb14b0edba0d206ae22ae4951a1ff24fe5e",
                redirect_uris=["https://localhost:8443/apps/user_oidc/code"],
                allowed_scopes="openid profile email",
                is_active=True,
            ),
        ]
        db.add_all(apps)
        await db.flush()
        print("Created 8 applications (including 1 honeypot, 2 OIDC RPs)")

        # --- Role Permissions ---
        permissions = [
            # Admin - full access to everything
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_CRM_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_MAIL_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_1C_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_WAREHOUSE_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_REPORTS_ID, can_read=True, can_write=True, can_export=True),
            # Manager - CRM full, Mail, Reports
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_CRM_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_MAIL_ID, can_read=True, can_write=True, can_export=False),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_REPORTS_ID, can_read=True, can_write=False, can_export=True),
            # Accountant - 1C full, CRM read-only, Mail
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_1C_ID, can_read=True, can_write=True, can_export=True, require_mfa=True),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_CRM_ID, can_read=True, can_write=False, can_export=False),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_MAIL_ID, can_read=True, can_write=True, can_export=False),
            # User - Mail only
            RolePermission(role_id=ROLE_USER_ID, application_id=APP_MAIL_ID, can_read=True, can_write=True, can_export=False),
            # Odoo ERP — admin и manager
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_ODOO_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_ODOO_ID, can_read=True, can_write=True, can_export=False),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_ODOO_ID, can_read=True, can_write=False, can_export=False),
            # Nextcloud — все роли кроме honeypot
            RolePermission(role_id=ROLE_ADMIN_ID, application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=True, can_export=True),
            RolePermission(role_id=ROLE_MANAGER_ID, application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=True, can_export=False),
            RolePermission(role_id=ROLE_ACCOUNTANT_ID, application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=True, can_export=False),
            RolePermission(role_id=ROLE_USER_ID, application_id=APP_NEXTCLOUD_ID, can_read=True, can_write=False, can_export=False),
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


if __name__ == "__main__":
    asyncio.run(seed())
