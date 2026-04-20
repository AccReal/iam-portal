"""
Test configuration and fixtures for IAM system tests.
"""
import asyncio
import os
import uuid
import tempfile
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

# Set test environment variables BEFORE importing any app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DEBUG"] = "False"

# Configure Celery to run tasks synchronously in-process (no broker needed)
from app.tasks.celery_app import celery_app
celery_app.conf.update(task_always_eager=True, task_eager_propagates=False)

from app.database import get_db
from app.models.user import User
from app.models.role import Role, RolePermission
from app.models.application import Application
from app.main import app as fastapi_app


# ──────────────────────────────────────────────
# In-memory Redis fake
# ──────────────────────────────────────────────

class FakeRedis:
    """Simple in-memory fake for Redis. Sufficient for unit/integration tests."""

    def __init__(self):
        self._store: dict = {}

    async def incr(self, key: str) -> int:
        self._store[key] = int(self._store.get(key, 0)) + 1
        return self._store[key]

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def get(self, key: str):
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value) -> bool:
        self._store[key] = value
        return True

    async def set(self, key: str, value, ex: int | None = None) -> bool:
        self._store[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                removed += 1
        return removed


@pytest.fixture(autouse=True)
def mock_redis_global():
    """
    Patch every module-level redis_client reference with an in-memory fake.
    Applies automatically to every test — no Redis server required.
    Tests that use @patch(...) on top will override specific modules.
    """
    fake = FakeRedis()
    with (
        patch("app.core.rate_limit.redis_client", fake),
        patch("app.services.auth_service.redis_client", fake),
        patch("app.services.mfa_service.redis_client", fake),
        patch("app.services.sso_service.redis_client", fake),
    ):
        yield fake


# ──────────────────────────────────────────────
# Raw SQL table definitions (SQLite-compatible)
# ──────────────────────────────────────────────

_CREATE_TABLES = [
    """
    CREATE TABLE roles (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE applications (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        app_url TEXT,
        icon TEXT,
        integration_type TEXT NOT NULL,
        client_id TEXT UNIQUE,
        client_secret_hash TEXT,
        redirect_uris TEXT,
        is_active INTEGER DEFAULT 1,
        is_honeypot INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE role_permissions (
        id TEXT PRIMARY KEY,
        role_id TEXT NOT NULL,
        application_id TEXT NOT NULL,
        can_read INTEGER DEFAULT 0,
        can_write INTEGER DEFAULT 0,
        can_export INTEGER DEFAULT 0,
        ip_whitelist TEXT,
        time_restriction_start TEXT,
        time_restriction_end TEXT,
        require_mfa INTEGER DEFAULT 0,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT,
        role_id TEXT,
        is_active INTEGER DEFAULT 1,
        is_blocked INTEGER DEFAULT 0,
        failed_login_count INTEGER DEFAULT 0,
        locked_until TEXT,
        mfa_enabled INTEGER DEFAULT 0,
        mfa_secret TEXT,
        mfa_method TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )
    """,
    """
    CREATE TABLE audit_log (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        action TEXT NOT NULL,
        resource_type TEXT,
        resource_id TEXT,
        ip_address TEXT,
        user_agent TEXT,
        success INTEGER DEFAULT 1,
        details TEXT,
        risk_score INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        refresh_token_hash TEXT NOT NULL UNIQUE,
        ip_address TEXT,
        user_agent TEXT,
        device_info TEXT,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE user_credentials (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        application_id TEXT NOT NULL,
        encrypted_username TEXT NOT NULL,
        encrypted_password TEXT NOT NULL,
        encryption_iv TEXT NOT NULL,
        last_rotated_at TEXT,
        rotation_interval_days INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
    )
    """,
]


# ──────────────────────────────────────────────
# Per-test database engine + session
# ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Fresh file-based SQLite DB per test — created before, deleted after."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    test_db_url = f"sqlite+aiosqlite:///{db_path}"
    test_engine = create_async_engine(test_db_url, echo=False)

    async with test_engine.begin() as conn:
        for sql in _CREATE_TABLES:
            await conn.execute(text(sql))

    yield test_engine

    await test_engine.dispose()
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Test DB session shared with the FastAPI app via dependency_overrides[get_db].
    Data committed in fixtures is visible to TestClient requests.
    Any uncommitted work is rolled back after the test.
    """
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:

        async def override_get_db():
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        fastapi_app.dependency_overrides[get_db] = override_get_db

        yield session

        await session.rollback()
        fastapi_app.dependency_overrides.pop(get_db, None)


# ──────────────────────────────────────────────
# Common model fixtures
# ──────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_role(db_session: AsyncSession) -> Role:
    """Create a test role."""
    role = Role(
        id=uuid.uuid4(),
        name="test_role",
        description="Test role for testing",
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    return role


@pytest_asyncio.fixture
async def test_application(db_session: AsyncSession) -> Application:
    """Create a test application."""
    application = Application(
        id=uuid.uuid4(),
        name="Test App",
        description="Test application",
        integration_type="oauth",
        is_active=True,
    )
    db_session.add(application)
    await db_session.commit()
    await db_session.refresh(application)
    return application


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_role: Role) -> User:
    """Create a test user with a role."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed_password_for_testing",
        full_name="Test User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
