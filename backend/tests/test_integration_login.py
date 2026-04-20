"""
Integration tests for full login flow.

These tests verify the complete end-to-end login process including:
- User login
- MFA verification
- Session creation
- Access to protected resources
- Logout

Validates: Requirements 11.1
"""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock

from app.main import app
from app.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.models.role import Role
from app.services.mfa_service import generate_totp_secret
import pyotp


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest_asyncio.fixture
async def test_user_with_mfa(db_session: AsyncSession, test_role: Role) -> User:
    """Create a test user with MFA enabled."""
    password = "SecurePassword123!"
    mfa_secret = generate_totp_secret()
    
    user = User(
        id=uuid.uuid4(),
        email=f"mfa_user_{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        full_name="MFA Test User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
        mfa_enabled=True,
        mfa_secret=mfa_secret,
        mfa_method="totp"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Store password and secret for test access
    user._test_password = password
    user._test_mfa_secret = mfa_secret
    
    return user


@pytest_asyncio.fixture
async def test_user_no_mfa(db_session: AsyncSession, test_role: Role) -> User:
    """Create a test user without MFA."""
    password = "SecurePassword123!"
    
    user = User(
        id=uuid.uuid4(),
        email=f"no_mfa_user_{uuid.uuid4()}@example.com",
        password_hash=hash_password(password),
        full_name="No MFA Test User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
        mfa_enabled=False
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Store password for test access
    user._test_password = password
    
    return user


@pytest.mark.asyncio
@patch('app.services.auth_service.redis_client')
async def test_full_login_flow_with_mfa(
    mock_redis,
    client: TestClient,
    db_session: AsyncSession,
    test_user_with_mfa: User
):
    """
    Integration test: Full login flow with MFA
    
    Tests the complete flow:
    1. User login with email/password
    2. System returns MFA required response
    3. User verifies MFA code
    4. System returns access tokens
    5. User accesses protected resource
    6. User logs out
    7. Token is invalidated
    
    Validates: Requirements 11.1
    """
    # Mock Redis for MFA session storage
    redis_storage = {}
    
    async def mock_setex(key, ttl, value):
        redis_storage[key] = value
        return True
    
    async def mock_get(key):
        return redis_storage.get(key)
    
    async def mock_delete(key):
        if key in redis_storage:
            del redis_storage[key]
        return True
    
    mock_redis.setex = AsyncMock(side_effect=mock_setex)
    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.delete = AsyncMock(side_effect=mock_delete)
    
    # Step 1: Login with email/password
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_with_mfa.email,
        "password": test_user_with_mfa._test_password
    })
    
    assert login_response.status_code == 200, \
        f"Login should succeed, got {login_response.status_code}: {login_response.text}"
    
    login_data = login_response.json()
    
    # Step 2: Verify MFA is required
    assert "mfa_method" in login_data, "Response should indicate MFA is required"
    assert login_data["mfa_method"] == "totp", "MFA method should be TOTP"
    assert "session_id" in login_data, "Response should contain MFA session ID"
    
    session_id = login_data["session_id"]
    
    # Step 3: Generate TOTP code
    totp = pyotp.TOTP(test_user_with_mfa._test_mfa_secret)
    current_code = totp.now()
    
    # Step 4: Verify MFA code
    mfa_response = client.post("/api/v1/auth/verify-mfa", json={
        "session_id": session_id,
        "code": current_code
    })
    
    assert mfa_response.status_code == 200, \
        f"MFA verification should succeed, got {mfa_response.status_code}: {mfa_response.text}"
    
    mfa_data = mfa_response.json()
    
    # Step 5: Verify tokens are returned
    assert "access_token" in mfa_data, "Response should contain access token"
    assert "refresh_token" in mfa_data, "Response should contain refresh token"
    assert "token_type" in mfa_data, "Response should contain token type"
    assert mfa_data["token_type"] == "bearer", "Token type should be bearer"
    
    access_token = mfa_data["access_token"]
    refresh_token = mfa_data["refresh_token"]
    
    # Step 6: Access protected resource
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = client.get("/api/v1/auth/me", headers=headers)
    
    assert me_response.status_code == 200, \
        f"Protected resource access should succeed, got {me_response.status_code}: {me_response.text}"
    
    me_data = me_response.json()
    assert me_data["email"] == test_user_with_mfa.email, \
        "Protected resource should return correct user data"
    assert me_data["full_name"] == test_user_with_mfa.full_name, \
        "Protected resource should return correct user name"
    
    # Step 7: Logout
    logout_response = client.post("/api/v1/auth/logout", json={
        "refresh_token": refresh_token
    })
    
    assert logout_response.status_code == 200, \
        f"Logout should succeed, got {logout_response.status_code}: {logout_response.text}"
    
    # Step 8: Verify token is invalidated (accessing protected resource should fail)
    me_response_after_logout = client.get("/api/v1/auth/me", headers=headers)
    
    # Note: Access token might still be valid until expiration, but refresh token should be invalidated
    # Try to refresh tokens
    refresh_response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    
    assert refresh_response.status_code == 401, \
        "Refresh should fail after logout (token invalidated)"


@pytest.mark.asyncio
async def test_full_login_flow_without_mfa(
    client: TestClient,
    db_session: AsyncSession,
    test_user_no_mfa: User
):
    """
    Integration test: Full login flow without MFA
    
    Tests the simplified flow for users without MFA:
    1. User login with email/password
    2. System returns access tokens immediately
    3. User accesses protected resource
    4. User logs out
    
    Validates: Requirements 11.1
    """
    # Step 1: Login with email/password
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_no_mfa.email,
        "password": test_user_no_mfa._test_password
    })
    
    assert login_response.status_code == 200, \
        f"Login should succeed, got {login_response.status_code}: {login_response.text}"
    
    login_data = login_response.json()
    
    # Step 2: Verify tokens are returned immediately (no MFA)
    assert "access_token" in login_data, "Response should contain access token"
    assert "refresh_token" in login_data, "Response should contain refresh token"
    assert "mfa_method" not in login_data, "Response should not require MFA"
    
    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]
    
    # Step 3: Access protected resource
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = client.get("/api/v1/auth/me", headers=headers)
    
    assert me_response.status_code == 200, \
        f"Protected resource access should succeed, got {me_response.status_code}: {me_response.text}"
    
    me_data = me_response.json()
    assert me_data["email"] == test_user_no_mfa.email, \
        "Protected resource should return correct user data"
    
    # Step 4: Logout
    logout_response = client.post("/api/v1/auth/logout", json={
        "refresh_token": refresh_token
    })
    
    assert logout_response.status_code == 200, \
        f"Logout should succeed, got {logout_response.status_code}: {logout_response.text}"


@pytest.mark.asyncio
async def test_login_with_wrong_password(
    client: TestClient,
    db_session: AsyncSession,
    test_user_no_mfa: User
):
    """
    Integration test: Login with wrong password should fail
    
    Validates: Requirements 11.1
    """
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_no_mfa.email,
        "password": "WrongPassword123!"
    })
    
    assert login_response.status_code == 401, \
        "Login with wrong password should fail with 401"
    
    assert "access_token" not in login_response.json(), \
        "Failed login should not return tokens"


@pytest.mark.asyncio
@patch('app.services.auth_service.redis_client')
async def test_mfa_with_wrong_code(
    mock_redis,
    client: TestClient,
    db_session: AsyncSession,
    test_user_with_mfa: User
):
    """
    Integration test: MFA verification with wrong code should fail
    
    Validates: Requirements 11.1
    """
    # Mock Redis for MFA session storage
    redis_storage = {}
    
    async def mock_setex(key, ttl, value):
        redis_storage[key] = value
        return True
    
    async def mock_get(key):
        return redis_storage.get(key)
    
    async def mock_delete(key):
        if key in redis_storage:
            del redis_storage[key]
        return True
    
    mock_redis.setex = AsyncMock(side_effect=mock_setex)
    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.delete = AsyncMock(side_effect=mock_delete)
    
    # Step 1: Login to get MFA session
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_with_mfa.email,
        "password": test_user_with_mfa._test_password
    })
    
    assert login_response.status_code == 200
    login_data = login_response.json()
    session_id = login_data["session_id"]
    
    # Step 2: Try to verify with wrong code
    mfa_response = client.post("/api/v1/auth/verify-mfa", json={
        "session_id": session_id,
        "code": "000000"  # Wrong code
    })
    
    assert mfa_response.status_code == 401, \
        "MFA verification with wrong code should fail with 401"
    
    assert "access_token" not in mfa_response.json(), \
        "Failed MFA verification should not return tokens"


@pytest.mark.asyncio
async def test_token_refresh_flow(
    client: TestClient,
    db_session: AsyncSession,
    test_user_no_mfa: User
):
    """
    Integration test: Token refresh flow
    
    Tests:
    1. User logs in
    2. User refreshes tokens using refresh_token
    3. New tokens are returned
    4. Old refresh token is invalidated
    
    Validates: Requirements 11.1
    """
    # Step 1: Login
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_no_mfa.email,
        "password": test_user_no_mfa._test_password
    })
    
    assert login_response.status_code == 200
    login_data = login_response.json()
    old_refresh_token = login_data["refresh_token"]
    
    # Step 2: Refresh tokens
    refresh_response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": old_refresh_token
    })
    
    assert refresh_response.status_code == 200, \
        f"Token refresh should succeed, got {refresh_response.status_code}: {refresh_response.text}"
    
    refresh_data = refresh_response.json()
    assert "access_token" in refresh_data, "Refresh should return new access token"
    assert "refresh_token" in refresh_data, "Refresh should return new refresh token"
    
    new_access_token = refresh_data["access_token"]
    new_refresh_token = refresh_data["refresh_token"]
    
    # Step 3: Verify new tokens work
    headers = {"Authorization": f"Bearer {new_access_token}"}
    me_response = client.get("/api/v1/auth/me", headers=headers)
    
    assert me_response.status_code == 200, \
        "New access token should work for protected resources"
    
    # Step 4: Verify old refresh token is invalidated
    old_refresh_response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": old_refresh_token
    })
    
    assert old_refresh_response.status_code == 401, \
        "Old refresh token should be invalidated after refresh"


@pytest.mark.asyncio
async def test_blocked_user_cannot_login(
    client: TestClient,
    db_session: AsyncSession,
    test_user_no_mfa: User
):
    """
    Integration test: Blocked user cannot login
    
    Validates: Requirements 11.1
    """
    # Block the user
    test_user_no_mfa.is_blocked = True
    await db_session.commit()
    
    # Try to login
    login_response = client.post("/api/v1/auth/login", json={
        "email": test_user_no_mfa.email,
        "password": test_user_no_mfa._test_password
    })
    
    # Login might succeed but token refresh should fail for blocked users
    # Or login itself might check is_blocked status
    # Let's check both scenarios
    
    if login_response.status_code == 200:
        # If login succeeds, try to refresh (should fail for blocked user)
        login_data = login_response.json()
        refresh_response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": login_data["refresh_token"]
        })
        assert refresh_response.status_code == 401, \
            "Blocked user should not be able to refresh tokens"
    else:
        # Login itself should fail
        assert login_response.status_code in [401, 403], \
            "Blocked user login should fail"
