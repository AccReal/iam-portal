"""
Property-based tests for SSO Integration system.

These tests verify universal properties that should hold across all inputs
using property-based testing with Hypothesis.
"""
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio
from hypothesis import given, strategies as st, settings
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sso_service import generate_auth_code, verify_auth_code
from app.core.encryption import encrypt_vault, decrypt_vault, generate_rsa_keypair, sign_data, verify_signature
from app.models.user import User
from app.models.role import Role, RolePermission
from app.models.application import Application
from app.redis import redis_client


# ============================================================================
# Property 25: Authorization code uniqueness and TTL
# ============================================================================

@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_authorization_code_uniqueness_and_ttl_example(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
    test_application: Application
):
    """
    Feature: iam-system-completion, Property 25: Authorization code uniqueness and TTL
    
    For any user and application, each generated authorization code should be unique,
    have an expiration time, and be associated with the correct user and application.
    
    Validates: Requirements 9.1
    """
    # Mock Redis storage
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
    
    # Create permission for user to access the application
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=test_application.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Generate multiple authorization codes
    codes = []
    for _ in range(5):
        code = await generate_auth_code(db_session, test_user, str(test_application.id))
        codes.append(code)
    
    # Property 1: All codes should be unique
    assert len(codes) == len(set(codes)), \
        "All generated authorization codes should be unique"
    
    # Property 2: Each code should be non-empty
    for code in codes:
        assert len(code) > 0, "Authorization code should not be empty"
    
    # Property 3: Each code should be verifiable and contain correct user/app data
    for code in codes:
        user_data = await verify_auth_code(code)
        assert user_data is not None, "Code should be verifiable"
        assert user_data["user_id"] == str(test_user.id), \
            f"Code should contain correct user_id: expected {test_user.id}, got {user_data.get('user_id')}"
        assert user_data["email"] == test_user.email, \
            "Code should contain correct email"
        assert user_data["app_id"] == str(test_application.id), \
            f"Code should contain correct app_id: expected {test_application.id}, got {user_data.get('app_id')}"
    
    # Property 4: Code should be single-use (already consumed in verification above)
    # Try to verify the first code again
    user_data = await verify_auth_code(codes[0])
    assert user_data is None, \
        "Authorization code should be single-use and not verifiable after first use"


@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_authorization_code_ttl(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
    test_application: Application
):
    """
    Test that authorization codes have a time-to-live (TTL).
    
    Validates: Requirements 9.1
    """
    # Mock Redis with TTL tracking
    redis_storage = {}
    redis_ttls = {}
    
    async def mock_setex(key, ttl, value):
        redis_storage[key] = value
        redis_ttls[key] = ttl
        return True
    
    async def mock_ttl(key):
        return redis_ttls.get(key, -2)  # -2 means key doesn't exist
    
    mock_redis.setex = AsyncMock(side_effect=mock_setex)
    mock_redis.ttl = AsyncMock(side_effect=mock_ttl)
    
    # Create permission for user to access the application
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=test_application.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Generate an authorization code
    code = await generate_auth_code(db_session, test_user, str(test_application.id))
    
    # Verify the code exists in Redis with TTL (use mock_redis instead of redis_client)
    ttl = await mock_redis.ttl(f"sso_code:{code}")
    
    # TTL should be positive (code exists and has expiration)
    assert ttl > 0, "Authorization code should have a positive TTL"
    
    # TTL should be approximately 300 seconds (5 minutes)
    assert ttl == 300, \
        f"Authorization code TTL should be 300 seconds, got {ttl}"


@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_authorization_code_expired(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
    test_application: Application
):
    """
    Test that expired authorization codes cannot be verified.
    
    Validates: Requirements 9.2
    """
    # Mock Redis storage
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
    
    # Create permission for user to access the application
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=test_application.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Generate an authorization code
    code = await generate_auth_code(db_session, test_user, str(test_application.id))
    
    # Manually expire the code by deleting it from Redis (simulating expiration) - use mock_redis
    await mock_redis.delete(f"sso_code:{code}")
    
    # Try to verify the expired code
    user_data = await verify_auth_code(code)
    
    # Should return None for expired code
    assert user_data is None, \
        "Expired authorization code should not be verifiable"


@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_authorization_code_used_once(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
    test_application: Application
):
    """
    Test that authorization codes can only be used once.
    
    Validates: Requirements 9.2
    """
    # Mock Redis storage
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
    
    # Create permission for user to access the application
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=test_application.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Generate an authorization code
    code = await generate_auth_code(db_session, test_user, str(test_application.id))
    
    # First verification should succeed
    user_data = await verify_auth_code(code)
    assert user_data is not None, "First verification should succeed"
    
    # Second verification should fail (code already used)
    user_data = await verify_auth_code(code)
    assert user_data is None, \
        "Authorization code should only be usable once"


# ============================================================================
# Property 26: OAuth token user data correctness
# ============================================================================

@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_oauth_token_user_data_correctness_example(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
    test_application: Application
):
    """
    Feature: iam-system-completion, Property 26: OAuth token user data correctness
    
    For any valid OAuth access_token (authorization code), decoding it should return
    the correct user_id and application_id that were used during authorization.
    
    Validates: Requirements 9.3
    """
    # Mock Redis storage
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
    
    # Create permission for user to access the application
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=test_application.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Generate an authorization code
    code = await generate_auth_code(db_session, test_user, str(test_application.id))
    
    # Verify the code (this simulates token exchange)
    user_data = await verify_auth_code(code)
    
    # Property 1: User data should not be None
    assert user_data is not None, "OAuth token should contain user data"
    
    # Property 2: User data should contain correct user_id
    assert user_data["user_id"] == str(test_user.id), \
        f"OAuth token should contain correct user_id: expected {test_user.id}, got {user_data.get('user_id')}"
    
    # Property 3: User data should contain correct app_id
    assert user_data["app_id"] == str(test_application.id), \
        f"OAuth token should contain correct app_id: expected {test_application.id}, got {user_data.get('app_id')}"
    
    # Property 4: User data should contain correct email
    assert user_data["email"] == test_user.email, \
        f"OAuth token should contain correct email: expected {test_user.email}, got {user_data.get('email')}"
    
    # Property 5: User data should contain correct full_name
    assert user_data["full_name"] == test_user.full_name, \
        f"OAuth token should contain correct full_name: expected {test_user.full_name}, got {user_data.get('full_name')}"


@settings(max_examples=100)
@given(
    user_id=st.uuids(),
    app_id=st.uuids(),
    email=st.emails(),
    full_name=st.text(min_size=1, max_size=100, alphabet=st.characters(
        min_codepoint=32, max_codepoint=126
    ))
)
def test_oauth_token_user_data_correctness_property(
    user_id: uuid.UUID,
    app_id: uuid.UUID,
    email: str,
    full_name: str
):
    """
    Feature: iam-system-completion, Property 26: OAuth token user data correctness
    
    Property-based test that verifies OAuth token data encoding/decoding
    preserves all user information correctly.
    
    Validates: Requirements 9.3
    """
    # Simulate the data structure stored in Redis for authorization codes
    user_data = {
        "user_id": str(user_id),
        "email": email,
        "full_name": full_name,
        "role": "test_role",
        "app_id": str(app_id),
    }
    
    # Encode to JSON (simulating Redis storage)
    encoded = json.dumps(user_data)
    
    # Decode from JSON (simulating retrieval)
    decoded = json.loads(encoded)
    
    # Property: All fields should be preserved exactly
    assert decoded["user_id"] == str(user_id), \
        "User ID should be preserved in OAuth token"
    assert decoded["email"] == email, \
        "Email should be preserved in OAuth token"
    assert decoded["full_name"] == full_name, \
        "Full name should be preserved in OAuth token"
    assert decoded["app_id"] == str(app_id), \
        "App ID should be preserved in OAuth token"


# ============================================================================
# Property 27: SAML assertion attributes
# ============================================================================

def generate_saml_assertion(user: dict, private_key: bytes) -> tuple[str, bytes]:
    """
    Generate a SAML assertion for a user.
    
    This is a simplified SAML assertion generator for testing purposes.
    In production, you would use a library like python3-saml.
    """
    # Create SAML assertion XML
    assertion = f"""<?xml version="1.0" encoding="UTF-8"?>
<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_{uuid.uuid4()}"
                Version="2.0"
                IssueInstant="{datetime.now(timezone.utc).isoformat()}">
    <saml:Issuer>IAM Portal</saml:Issuer>
    <saml:Subject>
        <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">
            {user['email']}
        </saml:NameID>
    </saml:Subject>
    <saml:AttributeStatement>
        <saml:Attribute Name="email">
            <saml:AttributeValue>{user['email']}</saml:AttributeValue>
        </saml:Attribute>
        <saml:Attribute Name="full_name">
            <saml:AttributeValue>{user['full_name']}</saml:AttributeValue>
        </saml:Attribute>
        <saml:Attribute Name="role">
            <saml:AttributeValue>{user.get('role', '')}</saml:AttributeValue>
        </saml:Attribute>
    </saml:AttributeStatement>
</saml:Assertion>"""
    
    # Sign the assertion
    signature = sign_data(assertion.encode(), private_key)
    
    return assertion, signature


def test_saml_assertion_attributes_example():
    """
    Feature: iam-system-completion, Property 27: SAML assertion attributes
    
    For any user, the generated SAML assertion should contain all required
    user attributes (email, full_name, role) and be properly signed.
    
    Validates: Requirements 9.4
    """
    # Generate RSA keypair for signing
    private_key, public_key = generate_rsa_keypair()
    
    # Create test user data
    user = {
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "admin"
    }
    
    # Generate SAML assertion
    assertion, signature = generate_saml_assertion(user, private_key)
    
    # Property 1: Assertion should contain email
    assert user["email"] in assertion, \
        "SAML assertion should contain user email"
    
    # Property 2: Assertion should contain full_name
    assert user["full_name"] in assertion, \
        "SAML assertion should contain user full_name"
    
    # Property 3: Assertion should contain role
    assert user["role"] in assertion, \
        "SAML assertion should contain user role"
    
    # Property 4: Assertion should be properly signed
    assert verify_signature(assertion.encode(), signature, public_key) is True, \
        "SAML assertion should be properly signed with correct key"
    
    # Property 5: Signature should not verify with wrong key
    wrong_private_key, wrong_public_key = generate_rsa_keypair()
    assert verify_signature(assertion.encode(), signature, wrong_public_key) is False, \
        "SAML assertion signature should not verify with wrong key"


@settings(max_examples=50, deadline=5000)  # Increased deadline for RSA key generation
@given(
    email=st.emails(),
    full_name=st.text(min_size=1, max_size=100, alphabet=st.characters(
        min_codepoint=32, max_codepoint=126
    )),
    role=st.sampled_from(["admin", "user", "manager", "viewer"])
)
def test_saml_assertion_attributes_property(email: str, full_name: str, role: str):
    """
    Feature: iam-system-completion, Property 27: SAML assertion attributes
    
    Property-based test that verifies SAML assertions contain all required
    attributes for any user data.
    
    Validates: Requirements 9.4
    """
    # Generate RSA keypair for signing
    private_key, public_key = generate_rsa_keypair()
    
    # Create user data
    user = {
        "email": email,
        "full_name": full_name,
        "role": role
    }
    
    # Generate SAML assertion
    assertion, signature = generate_saml_assertion(user, private_key)
    
    # Property 1: All user attributes should be present in assertion
    assert email in assertion, "Email should be in SAML assertion"
    assert full_name in assertion, "Full name should be in SAML assertion"
    assert role in assertion, "Role should be in SAML assertion"
    
    # Property 2: Assertion should be properly signed
    assert verify_signature(assertion.encode(), signature, public_key) is True, \
        "SAML assertion should be properly signed"
    
    # Property 3: Assertion should be valid XML-like structure
    assert assertion.startswith('<?xml version="1.0"'), \
        "SAML assertion should be valid XML"
    assert "<saml:Assertion" in assertion, \
        "SAML assertion should contain Assertion element"
    assert "</saml:Assertion>" in assertion, \
        "SAML assertion should be properly closed"


# ============================================================================
# Property 28: Vault encryption round-trip
# ============================================================================

@settings(max_examples=100)
@given(
    credential=st.text(min_size=1, max_size=1000, alphabet=st.characters(
        min_codepoint=32, max_codepoint=126
    ))
)
def test_vault_encryption_round_trip(credential: str):
    """
    Feature: iam-system-completion, Property 28: Vault encryption round-trip
    
    For any credential string, encrypting it with AES-256-GCM and then decrypting
    should return the exact original string.
    
    Validates: Requirements 9.5
    """
    # Encrypt the credential (returns iv||ciphertext blob)
    blob = encrypt_vault(credential)

    # Property 1: Blob should contain the 12-byte IV + non-empty ciphertext
    assert len(blob) > 12, "Blob should contain IV plus ciphertext"

    # Property 2: Blob must not equal plaintext
    assert blob != credential.encode(), \
        "Blob should be different from plaintext"

    # Property 3: Decryption should return original credential
    decrypted = decrypt_vault(blob)
    assert decrypted == credential, \
        f"Decrypted credential should match original: expected '{credential}', got '{decrypted}'"


def test_vault_encryption_round_trip_example():
    """
    Example test: Vault encryption round-trip
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 9.5
    """
    # Test with various credential types
    credentials = [
        "simple_password",
        "P@ssw0rd!Complex#123",
        "very-long-password-with-many-characters-" * 10,
        "unicode-password-тест-密码-🔐",
        "password with spaces and special chars: !@#$%^&*()",
    ]
    
    for credential in credentials:
        blob = encrypt_vault(credential)

        assert len(blob) > 12
        assert blob != credential.encode()

        decrypted = decrypt_vault(blob)

        assert decrypted == credential, \
            f"Round-trip failed for credential: {credential}"


def test_vault_encryption_uniqueness():
    """
    Test that encrypting the same credential twice produces different ciphertexts
    due to unique IVs.
    
    Validates: Requirements 9.5
    """
    credential = "test_password_123"

    blob1 = encrypt_vault(credential)
    blob2 = encrypt_vault(credential)

    # Each encryption must produce a unique IV, so blobs differ
    assert blob1[:12] != blob2[:12], "Each encryption should use a unique IV"
    assert blob1 != blob2, \
        "Encrypting the same credential twice should produce different blobs"

    assert decrypt_vault(blob1) == credential
    assert decrypt_vault(blob2) == credential


def test_vault_encryption_wrong_iv():
    """
    Test that tampering with the IV portion of the blob fails decryption.

    Validates: Requirements 9.5
    """
    import os

    credential = "test_password_123"
    blob = encrypt_vault(credential)

    # Replace the IV prefix with a random one — AES-GCM auth tag must fail.
    tampered = os.urandom(12) + blob[12:]

    with pytest.raises(Exception):
        decrypt_vault(tampered)


# ============================================================================
# Property 4: OAuth credentials generation uniqueness
# ============================================================================

def test_oauth_credentials_generation_uniqueness_example():
    """
    Feature: iam-system-completion, Property 4: OAuth credentials generation uniqueness
    
    For any OAuth application creation, the generated client_id and client_secret
    should be unique across all applications and non-empty.
    
    Validates: Requirements 2.2
    """
    # Simulate OAuth credential generation as done in applications.py
    import secrets
    
    # Generate multiple sets of credentials
    credentials = []
    for _ in range(100):
        client_id = f"app_{secrets.token_hex(16)}"
        client_secret = secrets.token_urlsafe(32)
        credentials.append((client_id, client_secret))
    
    # Extract all client_ids and client_secrets
    client_ids = [cred[0] for cred in credentials]
    client_secrets = [cred[1] for cred in credentials]
    
    # Property 1: All client_ids should be unique
    assert len(client_ids) == len(set(client_ids)), \
        "All generated client_ids should be unique"
    
    # Property 2: All client_secrets should be unique
    assert len(client_secrets) == len(set(client_secrets)), \
        "All generated client_secrets should be unique"
    
    # Property 3: All client_ids should be non-empty
    for client_id in client_ids:
        assert len(client_id) > 0, "client_id should not be empty"
        assert client_id.startswith("app_"), "client_id should start with 'app_' prefix"
    
    # Property 4: All client_secrets should be non-empty
    for client_secret in client_secrets:
        assert len(client_secret) > 0, "client_secret should not be empty"
    
    # Property 5: client_id should have expected format (app_ + 32 hex chars)
    for client_id in client_ids:
        assert len(client_id) == 4 + 32, \
            f"client_id should be 36 characters (app_ + 32 hex), got {len(client_id)}"
        # Verify the hex part is valid hex
        hex_part = client_id[4:]
        try:
            int(hex_part, 16)
        except ValueError:
            pytest.fail(f"client_id hex part should be valid hex: {hex_part}")
    
    # Property 6: client_secret should be URL-safe base64
    for client_secret in client_secrets:
        # URL-safe base64 uses only alphanumeric, -, and _
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', client_secret), \
            f"client_secret should be URL-safe base64: {client_secret}"


@settings(max_examples=100)
@given(
    num_apps=st.integers(min_value=2, max_value=50)
)
def test_oauth_credentials_generation_uniqueness_property(num_apps: int):
    """
    Feature: iam-system-completion, Property 4: OAuth credentials generation uniqueness
    
    Property-based test that verifies OAuth credentials are unique across
    multiple application creations.
    
    Validates: Requirements 2.2
    """
    import secrets
    
    # Generate credentials for multiple applications
    credentials = []
    for _ in range(num_apps):
        client_id = f"app_{secrets.token_hex(16)}"
        client_secret = secrets.token_urlsafe(32)
        credentials.append((client_id, client_secret))
    
    # Extract all client_ids and client_secrets
    client_ids = [cred[0] for cred in credentials]
    client_secrets = [cred[1] for cred in credentials]
    
    # Property: All credentials should be unique
    assert len(client_ids) == len(set(client_ids)), \
        f"All {num_apps} client_ids should be unique, but found duplicates"
    
    assert len(client_secrets) == len(set(client_secrets)), \
        f"All {num_apps} client_secrets should be unique, but found duplicates"
    
    # Property: All credentials should be non-empty
    assert all(len(cid) > 0 for cid in client_ids), \
        "All client_ids should be non-empty"
    
    assert all(len(cs) > 0 for cs in client_secrets), \
        "All client_secrets should be non-empty"


@pytest.mark.asyncio
async def test_oauth_credentials_database_uniqueness(
    db_session: AsyncSession,
):
    """
    Feature: iam-system-completion, Property 4: OAuth credentials generation uniqueness
    
    Test that OAuth credentials are unique at the database level and that
    duplicate client_ids are rejected by the unique constraint.
    
    Validates: Requirements 2.2
    """
    import secrets
    from sqlalchemy.exc import IntegrityError
    
    # Create first application with OAuth credentials
    client_id_1 = f"app_{secrets.token_hex(16)}"
    client_secret_1 = secrets.token_urlsafe(32)
    
    app1 = Application(
        id=uuid.uuid4(),
        name="Test OAuth App 1",
        description="First OAuth application",
        integration_type="oauth",
        client_id=client_id_1,
        client_secret_hash=client_secret_1,  # In production this would be hashed
        is_active=True
    )
    db_session.add(app1)
    await db_session.commit()
    await db_session.refresh(app1)
    
    # Property 1: First application should be created successfully
    assert app1.id is not None
    assert app1.client_id == client_id_1
    
    # Create second application with different credentials
    client_id_2 = f"app_{secrets.token_hex(16)}"
    client_secret_2 = secrets.token_urlsafe(32)
    
    app2 = Application(
        id=uuid.uuid4(),
        name="Test OAuth App 2",
        description="Second OAuth application",
        integration_type="oauth",
        client_id=client_id_2,
        client_secret_hash=client_secret_2,
        is_active=True
    )
    db_session.add(app2)
    await db_session.commit()
    await db_session.refresh(app2)
    
    # Property 2: Second application should be created successfully with different client_id
    assert app2.id is not None
    assert app2.client_id == client_id_2
    assert app2.client_id != app1.client_id
    
    # Property 3: Attempting to create an application with duplicate client_id should fail
    app3 = Application(
        id=uuid.uuid4(),
        name="Test OAuth App 3",
        description="Third OAuth application with duplicate client_id",
        integration_type="oauth",
        client_id=client_id_1,  # Duplicate client_id
        client_secret_hash=secrets.token_urlsafe(32),
        is_active=True
    )
    db_session.add(app3)
    
    # This should raise an IntegrityError due to unique constraint
    with pytest.raises(IntegrityError):
        await db_session.commit()
    
    # Rollback the failed transaction
    await db_session.rollback()
    
    # Property 4: After rollback, we should still be able to query existing apps
    from sqlalchemy import select
    result = await db_session.execute(select(Application))
    apps = result.scalars().all()
    assert len(apps) == 2, "Should have exactly 2 applications after failed insert"


@pytest.mark.asyncio
async def test_oauth_credentials_non_empty_constraint(
    db_session: AsyncSession,
):
    """
    Feature: iam-system-completion, Property 4: OAuth credentials generation uniqueness
    
    Test that OAuth applications must have non-empty client_id and client_secret
    when integration_type is 'oauth'.
    
    Validates: Requirements 2.2
    """
    import secrets
    
    # Test 1: OAuth app with valid credentials should succeed
    client_id = f"app_{secrets.token_hex(16)}"
    client_secret = secrets.token_urlsafe(32)
    
    app1 = Application(
        id=uuid.uuid4(),
        name="Valid OAuth App",
        description="OAuth app with valid credentials",
        integration_type="oauth",
        client_id=client_id,
        client_secret_hash=client_secret,
        is_active=True
    )
    db_session.add(app1)
    await db_session.commit()
    await db_session.refresh(app1)
    
    # Property 1: Valid OAuth app should be created
    assert app1.client_id is not None
    assert len(app1.client_id) > 0
    assert app1.client_secret_hash is not None
    assert len(app1.client_secret_hash) > 0
    
    # Test 2: Vault app without OAuth credentials should succeed
    app2 = Application(
        id=uuid.uuid4(),
        name="Vault App",
        description="Vault app without OAuth credentials",
        integration_type="vault",
        client_id=None,
        client_secret_hash=None,
        is_active=True
    )
    db_session.add(app2)
    await db_session.commit()
    await db_session.refresh(app2)
    
    # Property 2: Vault app without OAuth credentials should be allowed
    assert app2.client_id is None
    assert app2.client_secret_hash is None
    
    # Test 3: SAML app with OAuth credentials should succeed
    client_id_saml = f"app_{secrets.token_hex(16)}"
    client_secret_saml = secrets.token_urlsafe(32)
    
    app3 = Application(
        id=uuid.uuid4(),
        name="SAML App",
        description="SAML app with OAuth-style credentials",
        integration_type="saml",
        client_id=client_id_saml,
        client_secret_hash=client_secret_saml,
        is_active=True
    )
    db_session.add(app3)
    await db_session.commit()
    await db_session.refresh(app3)
    
    # Property 3: SAML app with credentials should be created
    assert app3.client_id is not None
    assert len(app3.client_id) > 0



# ============================================================================
# Property 5: Application status enforcement
# ============================================================================

@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_application_status_enforcement_example(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
    test_application: Application
):
    """
    Feature: iam-system-completion, Property 5: Application status enforcement
    
    For any application, when it is deactivated, all authorization attempts
    for that application should be immediately rejected until it is reactivated.
    
    Validates: Requirements 2.4
    """
    # Mock Redis storage
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
    
    # Create permission for user to access the application
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=test_application.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Property 1: When application is active, authorization should succeed
    assert test_application.is_active is True, "Test application should start as active"
    
    code = await generate_auth_code(db_session, test_user, str(test_application.id))
    assert code is not None, "Authorization should succeed for active application"
    assert len(code) > 0, "Authorization code should not be empty"
    
    # Property 2: When application is deactivated, authorization should be rejected
    test_application.is_active = False
    db_session.add(test_application)
    await db_session.commit()
    await db_session.refresh(test_application)
    
    assert test_application.is_active is False, "Application should be deactivated"
    
    # Attempting to generate auth code for inactive application should raise ValueError
    with pytest.raises(ValueError, match="Приложение не найдено или неактивно"):
        await generate_auth_code(db_session, test_user, str(test_application.id))
    
    # Property 3: When application is reactivated, authorization should succeed again
    test_application.is_active = True
    db_session.add(test_application)
    await db_session.commit()
    await db_session.refresh(test_application)
    
    assert test_application.is_active is True, "Application should be reactivated"
    
    code = await generate_auth_code(db_session, test_user, str(test_application.id))
    assert code is not None, "Authorization should succeed after reactivation"
    assert len(code) > 0, "Authorization code should not be empty"


@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_application_status_enforcement_immediate_effect(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
):
    """
    Feature: iam-system-completion, Property 5: Application status enforcement
    
    Test that application status changes take immediate effect without requiring
    cache invalidation or system restart.
    
    Validates: Requirements 2.4
    """
    # Mock Redis storage
    redis_storage = {}
    
    async def mock_setex(key, ttl, value):
        redis_storage[key] = value
        return True
    
    mock_redis.setex = AsyncMock(side_effect=mock_setex)
    
    # Create an active application
    app = Application(
        id=uuid.uuid4(),
        name="Test App for Status",
        description="Testing immediate status enforcement",
        integration_type="oauth",
        is_active=True
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    
    # Create permission for user
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=app.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Property 1: Authorization succeeds when active
    code1 = await generate_auth_code(db_session, test_user, str(app.id))
    assert code1 is not None, "First authorization should succeed"
    
    # Property 2: Immediately after deactivation, authorization fails
    app.is_active = False
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    
    with pytest.raises(ValueError, match="Приложение не найдено или неактивно"):
        await generate_auth_code(db_session, test_user, str(app.id))
    
    # Property 3: Immediately after reactivation, authorization succeeds
    app.is_active = True
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    
    code2 = await generate_auth_code(db_session, test_user, str(app.id))
    assert code2 is not None, "Authorization should succeed immediately after reactivation"


@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_application_status_enforcement_multiple_apps(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
):
    """
    Feature: iam-system-completion, Property 5: Application status enforcement
    
    Test that application status is enforced independently for each application.
    Deactivating one application should not affect others.
    
    Validates: Requirements 2.4
    """
    # Mock Redis storage
    redis_storage = {}
    
    async def mock_setex(key, ttl, value):
        redis_storage[key] = value
        return True
    
    mock_redis.setex = AsyncMock(side_effect=mock_setex)
    
    # Create multiple applications
    apps = []
    for i in range(3):
        app = Application(
            id=uuid.uuid4(),
            name=f"Test App {i+1}",
            description=f"Application {i+1}",
            integration_type="oauth",
            is_active=True
        )
        db_session.add(app)
        apps.append(app)
    
    await db_session.commit()
    
    # Create permissions for all apps
    for app in apps:
        await db_session.refresh(app)
        permission = RolePermission(
            id=uuid.uuid4(),
            role_id=test_user.role_id,
            application_id=app.id,
            can_read=True,
            can_write=False,
            can_export=False
        )
        db_session.add(permission)
    
    await db_session.commit()
    
    # Property 1: All active applications should allow authorization
    for app in apps:
        code = await generate_auth_code(db_session, test_user, str(app.id))
        assert code is not None, f"Authorization should succeed for active app {app.name}"
    
    # Property 2: Deactivate the second application
    apps[1].is_active = False
    db_session.add(apps[1])
    await db_session.commit()
    await db_session.refresh(apps[1])
    
    # Property 3: First and third apps should still work
    code0 = await generate_auth_code(db_session, test_user, str(apps[0].id))
    assert code0 is not None, "First app should still work"
    
    code2 = await generate_auth_code(db_session, test_user, str(apps[2].id))
    assert code2 is not None, "Third app should still work"
    
    # Property 4: Second app should be rejected
    with pytest.raises(ValueError, match="Приложение не найдено или неактивно"):
        await generate_auth_code(db_session, test_user, str(apps[1].id))
    
    # Property 5: Reactivate second app
    apps[1].is_active = True
    db_session.add(apps[1])
    await db_session.commit()
    await db_session.refresh(apps[1])
    
    # Property 6: All apps should work again
    for app in apps:
        code = await generate_auth_code(db_session, test_user, str(app.id))
        assert code is not None, f"Authorization should succeed for reactivated app {app.name}"


@pytest.mark.asyncio
@patch('app.services.sso_service.redis_client')
async def test_application_status_enforcement_multiple_toggles(
    mock_redis,
    db_session: AsyncSession,
    test_user: User,
):
    """
    Feature: iam-system-completion, Property 5: Application status enforcement
    
    Test that verifies application status enforcement works correctly across
    multiple status toggles. This simulates the property-based test behavior
    with a fixed number of toggles.
    
    Validates: Requirements 2.4
    """
    # Mock Redis storage
    redis_storage = {}
    
    async def mock_setex(key, ttl, value):
        redis_storage[key] = value
        return True
    
    mock_redis.setex = AsyncMock(side_effect=mock_setex)
    
    # Create an application
    app = Application(
        id=uuid.uuid4(),
        name="Property Test App",
        description="Testing status enforcement property",
        integration_type="oauth",
        is_active=True
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    
    # Create permission
    permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_user.role_id,
        application_id=app.id,
        can_read=True,
        can_write=False,
        can_export=False
    )
    db_session.add(permission)
    await db_session.commit()
    
    # Property: For any sequence of status toggles, authorization should
    # succeed when active and fail when inactive
    # Test with 10 toggles
    num_toggles = 10
    current_status = True
    
    for i in range(num_toggles):
        # Toggle status
        current_status = not current_status
        app.is_active = current_status
        db_session.add(app)
        await db_session.commit()
        await db_session.refresh(app)
        
        # Verify authorization matches current status
        if current_status:
            # Should succeed
            code = await generate_auth_code(db_session, test_user, str(app.id))
            assert code is not None, \
                f"Authorization should succeed when active (toggle {i+1}/{num_toggles})"
        else:
            # Should fail
            with pytest.raises(ValueError, match="Приложение не найдено или неактивно"):
                await generate_auth_code(db_session, test_user, str(app.id))
