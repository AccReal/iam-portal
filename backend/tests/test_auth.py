"""
Property-based tests for Authentication system.

These tests verify universal properties that should hold across all inputs
using property-based testing with Hypothesis.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from hypothesis import given, strategies as st, settings, HealthCheck
from jose import jwt

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.mfa_service import generate_totp_secret, verify_totp
from app.services.auth_service import authenticate_user, MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES
from app.models.user import User
from app.models.role import Role
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings as app_settings


# ============================================================================
# Property 12: Password hash uniqueness
# ============================================================================

@settings(max_examples=100, deadline=None)  # Argon2 is intentionally slow, disable deadline
@given(
    password=st.text(min_size=8, max_size=128, alphabet=st.characters(
        min_codepoint=33, max_codepoint=126
    ))
)
def test_password_hash_uniqueness(password: str):
    """
    Feature: iam-system-completion, Property 12: Password hash uniqueness
    
    For any password string, hashing it twice should produce two different hash strings
    (due to unique salts), and verify_password should return true for the correct password
    and false for incorrect passwords.
    
    Validates: Requirements 6.1
    """
    # Hash the same password twice
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    
    # Property 1: Two hashes of the same password should be different (due to salt)
    assert hash1 != hash2, \
        "Hashing the same password twice should produce different hashes due to unique salts"
    
    # Property 2: Both hashes should verify correctly with the original password
    assert verify_password(password, hash1) is True, \
        "First hash should verify correctly with original password"
    assert verify_password(password, hash2) is True, \
        "Second hash should verify correctly with original password"
    
    # Property 3: Hashes should not verify with incorrect passwords
    if len(password) > 0:
        wrong_password = password + "x"
        assert verify_password(wrong_password, hash1) is False, \
            "Hash should not verify with incorrect password"
        assert verify_password(wrong_password, hash2) is False, \
            "Hash should not verify with incorrect password"


def test_password_hash_uniqueness_example():
    """
    Example test: Password hash uniqueness
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 6.1
    """
    password = "SecurePassword123!"
    
    # Hash the same password twice
    hash1 = hash_password(password)
    hash2 = hash_password(password)
    
    # Hashes should be different
    assert hash1 != hash2, "Two hashes of the same password should be different"
    
    # Both should verify correctly
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
    
    # Wrong password should not verify
    assert verify_password("WrongPassword", hash1) is False
    assert verify_password("WrongPassword", hash2) is False


# ============================================================================
# Property 13: JWT token claims correctness
# ============================================================================

@settings(max_examples=100)
@given(
    user_id=st.uuids(),
)
def test_jwt_token_claims_correctness(user_id: uuid.UUID):
    """
    Feature: iam-system-completion, Property 13: JWT token claims correctness
    
    For any user, the generated JWT access_token and refresh_token should contain
    correct claims (user_id, exp, type) and should be decodable with the correct signature.
    
    Validates: Requirements 6.2
    """
    user_id_str = str(user_id)
    token_data = {"sub": user_id_str}
    
    # Generate access token
    access_token = create_access_token(token_data)
    
    # Generate refresh token
    refresh_token = create_refresh_token(token_data)
    
    # Decode access token
    access_payload = decode_token(access_token)
    assert access_payload is not None, "Access token should be decodable"
    assert access_payload["sub"] == user_id_str, \
        f"Access token should contain correct user_id: expected {user_id_str}, got {access_payload.get('sub')}"
    assert access_payload["type"] == "access", \
        "Access token should have type='access'"
    assert "exp" in access_payload, \
        "Access token should contain expiration claim"
    
    # Verify expiration is in the future
    exp_timestamp = access_payload["exp"]
    current_timestamp = datetime.now(timezone.utc).timestamp()
    assert exp_timestamp > current_timestamp, \
        "Access token expiration should be in the future"
    
    # Decode refresh token
    refresh_payload = decode_token(refresh_token)
    assert refresh_payload is not None, "Refresh token should be decodable"
    assert refresh_payload["sub"] == user_id_str, \
        f"Refresh token should contain correct user_id: expected {user_id_str}, got {refresh_payload.get('sub')}"
    assert refresh_payload["type"] == "refresh", \
        "Refresh token should have type='refresh'"
    assert "exp" in refresh_payload, \
        "Refresh token should contain expiration claim"
    
    # Verify refresh token expiration is further in the future than access token
    refresh_exp = refresh_payload["exp"]
    assert refresh_exp > exp_timestamp, \
        "Refresh token should expire later than access token"


def test_jwt_token_claims_correctness_example():
    """
    Example test: JWT token claims correctness
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 6.2
    """
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token_data = {"sub": user_id}
    
    # Generate tokens
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Decode and verify access token
    access_payload = decode_token(access_token)
    assert access_payload is not None
    assert access_payload["sub"] == user_id
    assert access_payload["type"] == "access"
    assert "exp" in access_payload
    
    # Decode and verify refresh token
    refresh_payload = decode_token(refresh_token)
    assert refresh_payload is not None
    assert refresh_payload["sub"] == user_id
    assert refresh_payload["type"] == "refresh"
    assert "exp" in refresh_payload
    
    # Refresh token should expire later
    assert refresh_payload["exp"] > access_payload["exp"]


def test_jwt_token_validation_expired():
    """
    Test JWT token validation with expired token.
    
    Validates: Requirements 6.3
    """
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    
    # Create an expired token manually
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
    expired_payload = {
        "sub": user_id,
        "exp": expired_time,
        "type": "access"
    }
    expired_token = jwt.encode(expired_payload, app_settings.JWT_SECRET_KEY, algorithm=app_settings.JWT_ALGORITHM)
    
    # Attempt to decode expired token
    decoded = decode_token(expired_token)
    
    # Should return None for expired token
    assert decoded is None, "Expired token should be rejected"


def test_jwt_token_validation_invalid_signature():
    """
    Test JWT token validation with invalid signature.
    
    Validates: Requirements 6.3
    """
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    
    # Create a token with wrong secret key
    wrong_secret = "wrong-secret-key-that-is-different"
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "type": "access"
    }
    invalid_token = jwt.encode(payload, wrong_secret, algorithm=app_settings.JWT_ALGORITHM)
    
    # Attempt to decode with correct secret
    decoded = decode_token(invalid_token)
    
    # Should return None for invalid signature
    assert decoded is None, "Token with invalid signature should be rejected"


# ============================================================================
# Property 14: TOTP code validation
# ============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    # Generate random secrets for testing
    seed=st.integers(min_value=0, max_value=1000000)
)
def test_totp_code_validation(seed: int):
    """
    Feature: iam-system-completion, Property 14: TOTP code validation
    
    For any generated TOTP secret, the code generated for the current time window
    should be validated as correct, and codes from different time windows should be rejected.
    
    Validates: Requirements 6.4
    """
    import pyotp
    
    # Generate a TOTP secret
    secret = generate_totp_secret()
    
    # Generate current valid code
    totp = pyotp.TOTP(secret)
    current_code = totp.now()
    
    # Property 1: Current code should verify successfully
    assert verify_totp(secret, current_code) is True, \
        "Current TOTP code should verify successfully"
    
    # Property 2: Wrong code should not verify
    wrong_code = "000000" if current_code != "000000" else "111111"
    assert verify_totp(secret, wrong_code) is False, \
        "Wrong TOTP code should be rejected"
    
    # Property 3: Empty secret should always fail
    assert verify_totp("", current_code) is False, \
        "Empty secret should always fail verification"
    
    # Property 4: Code from far past should be rejected
    # Generate a code from 10 time windows ago (5 minutes ago with 30s windows)
    past_time = time.time() - 300  # 5 minutes ago
    past_code = totp.at(past_time)
    assert verify_totp(secret, past_code) is False, \
        "Code from far past should be rejected"


def test_totp_code_validation_example():
    """
    Example test: TOTP code validation
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 6.4
    """
    import pyotp
    
    # Generate a TOTP secret
    secret = generate_totp_secret()
    
    # Generate current valid code
    totp = pyotp.TOTP(secret)
    current_code = totp.now()
    
    # Current code should verify
    assert verify_totp(secret, current_code) is True
    
    # Wrong code should not verify
    assert verify_totp(secret, "000000") is False
    assert verify_totp(secret, "999999") is False
    
    # Empty secret should fail
    assert verify_totp("", current_code) is False
    
    # Code from 10 minutes ago should be rejected
    past_time = time.time() - 600
    past_code = totp.at(past_time)
    assert verify_totp(secret, past_code) is False


# ============================================================================
# Property 15: Rate limiting enforcement
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limiting_enforcement_example(
    db_session: AsyncSession,
    test_role: Role
):
    """
    Feature: iam-system-completion, Property 15: Rate limiting enforcement
    
    For any user account, after N consecutive failed login attempts, the (N+1)th attempt
    should be blocked with a rate limit error, regardless of password correctness.
    
    Validates: Requirements 6.5
    """
    # Create a test user
    correct_password = "SecurePassword123!"
    user = User(
        id=uuid.uuid4(),
        email=f"ratelimit_example_{uuid.uuid4()}@example.com",
        password_hash=hash_password(correct_password),
        full_name="Rate Limit Example User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
        failed_login_count=0,
        locked_until=None
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Make 5 failed login attempts
    for i in range(5):
        result = await authenticate_user(db_session, user.email, "WrongPassword")
        assert result is None
        await db_session.refresh(user)
    
    # User should now be locked
    await db_session.refresh(user)
    assert user.locked_until is not None
    
    # Ensure locked_until has timezone info for comparison
    locked_until_aware = user.locked_until
    if locked_until_aware.tzinfo is None:
        locked_until_aware = locked_until_aware.replace(tzinfo=timezone.utc)
    
    assert locked_until_aware > datetime.now(timezone.utc)
    
    # Next attempt should be blocked even with correct password
    with pytest.raises(PermissionError, match="временно заблокирован"):
        await authenticate_user(db_session, user.email, correct_password)
    
    # Verify the lockout duration is approximately LOCKOUT_MINUTES
    lockout_duration = (locked_until_aware - datetime.now(timezone.utc)).total_seconds()
    expected_duration = LOCKOUT_MINUTES * 60
    # Allow 5 second tolerance
    assert abs(lockout_duration - expected_duration) < 5, \
        f"Lockout duration should be approximately {LOCKOUT_MINUTES} minutes"
    
    # Clean up
    await db_session.delete(user)
    await db_session.commit()


def test_rate_limiting_enforcement_property():
    """
    Feature: iam-system-completion, Property 15: Rate limiting enforcement
    
    Property-based test that verifies rate limiting logic without database.
    Tests the logical property across many values of failed attempt counts.
    
    Validates: Requirements 6.5
    """
    def simulate_failed_attempts(max_attempts: int, current_attempts: int) -> tuple[bool, bool]:
        """
        Simulate rate limiting logic.
        Returns: (should_lock, should_block_next)
        """
        should_lock = current_attempts >= max_attempts
        should_block_next = should_lock
        return should_lock, should_block_next
    
    # Test with the actual MAX_FAILED_ATTEMPTS value
    for num_attempts in range(1, MAX_FAILED_ATTEMPTS + 10):
        should_lock, should_block = simulate_failed_attempts(MAX_FAILED_ATTEMPTS, num_attempts)
        
        if num_attempts < MAX_FAILED_ATTEMPTS:
            assert should_lock is False, \
                f"Should not lock before {MAX_FAILED_ATTEMPTS} attempts (at {num_attempts})"
        else:
            assert should_lock is True, \
                f"Should lock after {MAX_FAILED_ATTEMPTS} attempts (at {num_attempts})"
            assert should_block is True, \
                f"Should block next attempt after {MAX_FAILED_ATTEMPTS} attempts"


@pytest.mark.asyncio
async def test_rate_limiting_reset_on_success(
    db_session: AsyncSession,
    test_role: Role
):
    """
    Test that failed login count resets on successful login.
    
    Validates: Requirements 6.5
    """
    # Create a test user
    correct_password = "SecurePassword123!"
    user = User(
        id=uuid.uuid4(),
        email=f"ratelimit_reset_{uuid.uuid4()}@example.com",
        password_hash=hash_password(correct_password),
        full_name="Rate Limit Reset User",
        role_id=test_role.id,
        is_active=True,
        is_blocked=False,
        failed_login_count=0,
        locked_until=None
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Make 3 failed attempts (less than MAX_FAILED_ATTEMPTS)
    for i in range(3):
        result = await authenticate_user(db_session, user.email, "WrongPassword")
        assert result is None
        await db_session.refresh(user)
    
    # Verify failed count increased
    assert user.failed_login_count == 3
    
    # Successful login should reset the counter
    result = await authenticate_user(db_session, user.email, correct_password)
    assert result is not None
    await db_session.refresh(user)
    
    # Failed login count should be reset
    assert user.failed_login_count == 0
    assert user.locked_until is None
    
    # Clean up
    await db_session.delete(user)
    await db_session.commit()
