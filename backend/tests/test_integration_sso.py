"""
Integration tests for SSO authorization flow.

These tests verify the complete end-to-end SSO process including:
- User login
- App authorization (GET /sso/authorize?app_id=...)
- Code generation
- Code verification (POST /sso/verify)
- Resource access via /sso/apps

Validates: Requirements 11.2
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock

from app.main import app
from app.core.security import hash_password
from app.models.user import User
from app.models.role import Role, RolePermission
from app.models.application import Application


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest_asyncio.fixture
async def test_oauth_app(db_session: AsyncSession) -> Application:
    """Create a test OAuth application."""
    import secrets

    oauth_app = Application(
        id=uuid.uuid4(),
        name="Test OAuth App",
        description="OAuth application for integration testing",
        app_url="https://testapp.example.com",
        integration_type="oauth",
        client_id=f"app_{secrets.token_hex(16)}",
        client_secret_hash=secrets.token_urlsafe(32),
        redirect_uris=None,
        is_active=True,
        is_honeypot=False,
    )
    db_session.add(oauth_app)
    await db_session.commit()
    await db_session.refresh(oauth_app)
    return oauth_app


@pytest_asyncio.fixture
async def test_user_with_app_access(
    db_session: AsyncSession,
    test_role: Role,
    test_oauth_app: Application,
) -> User:
    """Create a test user with access to the OAuth app."""
    password = "SecurePassword123!"

    user = User(
        id=uuid.uuid4(),
        email=f"sso_user_{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        full_name="SSO Test User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
        mfa_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Grant read permission on the application for this role
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_role.id,
        application_id=test_oauth_app.id,
        can_read=True,
        can_write=False,
        can_export=False,
    )
    db_session.add(permission)
    await db_session.commit()

    user._test_password = password
    return user


@pytest.mark.asyncio
async def test_full_sso_authorization_flow(
    client: TestClient,
    db_session: AsyncSession,
    test_user_with_app_access: User,
    test_oauth_app: Application,
):
    """
    Integration test: Full SSO authorization flow

    Tests the complete flow:
    1. User logs in to IAM system
    2. User authorizes application access via GET /sso/authorize?app_id=...
    3. System generates authorization code
    4. Code is verified via POST /sso/verify
    5. Code is single-use

    Validates: Requirements 11.2
    """
    # Step 1: User logs in
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_with_app_access.email,
        "password": test_user_with_app_access._test_password,
    })

    assert login_response.status_code == 200, \
        f"Login should succeed, got {login_response.status_code}: {login_response.text}"

    access_token = login_response.json()["access_token"]

    # Step 2: User authorizes application access
    headers = {"Authorization": f"Bearer {access_token}"}
    authorize_response = client.get(
        f"/api/v1/sso/authorize?app_id={test_oauth_app.id}",
        headers=headers,
    )

    assert authorize_response.status_code == 200, \
        f"Authorization should succeed, got {authorize_response.status_code}: {authorize_response.text}"

    authorize_data = authorize_response.json()

    # Step 3: Verify authorization code is generated
    assert "code" in authorize_data, "Response should contain authorization code"
    auth_code = authorize_data["code"]
    assert len(auth_code) >= 32, "Authorization code should be sufficiently long for security"

    # Step 4: Verify the code via POST /sso/verify
    verify_response = client.post("/api/v1/sso/verify", json={"code": auth_code})

    assert verify_response.status_code == 200, \
        f"Code verification should succeed, got {verify_response.status_code}: {verify_response.text}"

    verify_data = verify_response.json()
    assert verify_data.get("valid") is True, "Verification should return valid=True"
    user_info = verify_data.get("user", {})
    assert "user_id" in user_info, "Response should contain user_id"
    assert "email" in user_info, "Response should contain email"
    assert "full_name" in user_info, "Response should contain full_name"

    assert user_info["user_id"] == str(test_user_with_app_access.id)
    assert user_info["email"] == test_user_with_app_access.email
    assert user_info["full_name"] == test_user_with_app_access.full_name

    # Step 5: Verify code is single-use
    second_verify = client.post("/api/v1/sso/verify", json={"code": auth_code})
    assert second_verify.status_code in [400, 401], \
        "Authorization code should be single-use"


@pytest.mark.asyncio
async def test_sso_authorization_without_permission(
    client: TestClient,
    db_session: AsyncSession,
    test_role: Role,
    test_oauth_app: Application,
):
    """
    Integration test: SSO authorization fails without permission

    Tests that a user without permission to access an application
    cannot authorize it.

    Validates: Requirements 11.2
    """
    # Create a user WITHOUT permission to the app
    password = "SecurePassword123!"
    user = User(
        id=uuid.uuid4(),
        email=f"no_access_user_{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        full_name="No Access User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
        mfa_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()

    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": user.email,
        "password": password,
    })
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # Try to authorize application access (should fail — no RolePermission row)
    headers = {"Authorization": f"Bearer {access_token}"}
    authorize_response = client.get(
        f"/api/v1/sso/authorize?app_id={test_oauth_app.id}",
        headers=headers,
    )

    assert authorize_response.status_code in [403, 404], \
        "Authorization should fail for user without permission"


@pytest.mark.asyncio
async def test_sso_authorization_inactive_app(
    client: TestClient,
    db_session: AsyncSession,
    test_user_with_app_access: User,
    test_oauth_app: Application,
):
    """
    Integration test: SSO authorization fails for inactive application

    Validates: Requirements 11.2, Property 5
    """
    # Deactivate the application
    test_oauth_app.is_active = False
    await db_session.commit()

    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_with_app_access.email,
        "password": test_user_with_app_access._test_password,
    })
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # Try to authorize inactive application (should fail)
    headers = {"Authorization": f"Bearer {access_token}"}
    authorize_response = client.get(
        f"/api/v1/sso/authorize?app_id={test_oauth_app.id}",
        headers=headers,
    )

    assert authorize_response.status_code in [400, 403, 404], \
        "Authorization should fail for inactive application"


@pytest.mark.asyncio
async def test_sso_token_exchange_with_wrong_client_id(
    client: TestClient,
    db_session: AsyncSession,
    test_user_with_app_access: User,
    test_oauth_app: Application,
):
    """
    Integration test: Verification fails with invalid/random code

    Tests that verifying a random code returns an error.

    Validates: Requirements 11.2
    """
    # Attempt to verify a completely random code (never issued)
    fake_code = "nonexistent_code_that_was_never_generated_1234567890abcdef"
    verify_response = client.post("/api/v1/sso/verify", json={"code": fake_code})

    assert verify_response.status_code in [400, 401], \
        "Verification should fail with invalid code"


@pytest.mark.asyncio
async def test_sso_my_apps_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    test_user_with_app_access: User,
    test_oauth_app: Application,
):
    """
    Integration test: User can list their accessible applications via GET /sso/apps

    Validates: Requirements 11.2
    """
    # Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_with_app_access.email,
        "password": test_user_with_app_access._test_password,
    })
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    # Get user's accessible apps
    headers = {"Authorization": f"Bearer {access_token}"}
    apps_response = client.get("/api/v1/sso/apps", headers=headers)

    assert apps_response.status_code == 200, \
        f"Apps endpoint should succeed, got {apps_response.status_code}: {apps_response.text}"

    response_data = apps_response.json()
    assert "apps" in response_data, "Response should contain 'apps' key"
    apps_data = response_data["apps"]
    assert isinstance(apps_data, list), "apps should be a list"

    # Verify the test app is in the list
    app_ids = [a["id"] for a in apps_data]
    assert str(test_oauth_app.id) in app_ids, \
        "User's accessible applications should include the test app"

    # Verify app data structure
    test_app_data = next(a for a in apps_data if a["id"] == str(test_oauth_app.id))
    assert "name" in test_app_data
    assert "description" in test_app_data
    assert "app_url" in test_app_data
    assert "integration_type" in test_app_data
    assert test_app_data["name"] == test_oauth_app.name
    assert test_app_data["integration_type"] == "oauth"
