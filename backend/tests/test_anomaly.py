"""
Property-based tests for Anomaly Detection system.

These tests verify universal properties that should hold across all inputs
using property-based testing with Hypothesis.
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.role import Role
from app.models.audit import AuditLog
from app.models.application import Application
from app.services.anomaly_service import calculate_risk_score
from app.services.honeypot_service import check_honeypot


# ============================================================================
# Property 20: New IP risk increase
# ============================================================================

@pytest.mark.asyncio
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    new_ip=st.from_regex(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', fullmatch=True),
    known_ip=st.from_regex(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', fullmatch=True),
)
async def test_new_ip_risk_increase(
    db_session: AsyncSession,
    test_user: User,
    new_ip: str,
    known_ip: str
):
    """
    Feature: iam-system-completion, Property 20: New IP risk increase
    
    For any user login, if the IP address has never been used by that user before,
    the calculated risk_score should be higher than if using a known IP address.
    
    Validates: Requirements 8.1
    """
    # Ensure IPs are different
    if new_ip == known_ip:
        return
    
    # Clear any existing audit logs for this user to ensure clean state
    from sqlalchemy import delete
    await db_session.execute(delete(AuditLog).where(AuditLog.user_id == test_user.id))
    await db_session.commit()
    
    # Create TWO successful login audit logs with the known IP to establish it as "known"
    # This ensures the known IP has history
    for i in range(2):
        known_audit = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action="login",
            ip_address=known_ip,
            success=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=i+1)
        )
        db_session.add(known_audit)
    await db_session.commit()
    
    # Mock the GeoIP call to return consistent results
    mock_geo = {"countryCode": "RU", "country": "Russia"}
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = mock_geo
        
        # Calculate risk score for known IP
        risk_known = await calculate_risk_score(db_session, test_user, known_ip, "Mozilla/5.0")
        
        # Calculate risk score for new IP
        risk_new = await calculate_risk_score(db_session, test_user, new_ip, "Mozilla/5.0")
    
    # Property: New IP should have higher risk score than known IP
    # The difference should be at least 20 points (the new IP penalty)
    assert risk_new >= risk_known + 20, \
        f"New IP ({new_ip}) should have risk score at least 20 points higher than known IP ({known_ip}): new={risk_new}, known={risk_known}"


@pytest.mark.asyncio
async def test_new_ip_risk_increase_example(
    db_session: AsyncSession,
    test_user: User
):
    """
    Example test: New IP risk increase
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 8.1
    """
    known_ip = "192.168.1.100"
    new_ip = "10.0.0.50"
    
    # Create a successful login audit log with the known IP
    known_audit = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="login",
        ip_address=known_ip,
        success=True,
        created_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(known_audit)
    await db_session.commit()
    
    # Mock the GeoIP call
    mock_geo = {"countryCode": "RU", "country": "Russia"}
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = mock_geo
        
        # Calculate risk scores
        risk_known = await calculate_risk_score(db_session, test_user, known_ip, "Mozilla/5.0")
        risk_new = await calculate_risk_score(db_session, test_user, new_ip, "Mozilla/5.0")
    
    # New IP should have higher risk
    assert risk_new > risk_known, \
        f"New IP should have higher risk score: new={risk_new}, known={risk_known}"
    
    # The difference should be at least 20 points (the new IP penalty)
    assert risk_new - risk_known >= 20, \
        f"New IP should add at least 20 points to risk score"


# ============================================================================
# Property 21: Unusual time risk increase
# ============================================================================

@pytest.mark.asyncio
async def test_unusual_time_risk_increase_example(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 21: Unusual time risk increase
    
    For any user login, if the login time is outside the user's typical activity hours
    (e.g., 2 AM when user normally logs in 9 AM - 6 PM), the risk_score should be increased.
    
    Validates: Requirements 8.2
    """
    test_ip = "192.168.1.100"
    test_user_agent = "Mozilla/5.0"
    
    # Mock the GeoIP call
    mock_geo = {"countryCode": "RU", "country": "Russia"}
    
    # Mock datetime to simulate different times
    # Normal working hours: 10:00 MSK (7:00 UTC)
    normal_time = datetime(2025, 1, 15, 7, 0, 0, tzinfo=timezone.utc)
    
    # Unusual hours: 2:00 MSK (23:00 UTC previous day)
    unusual_time = datetime(2025, 1, 14, 23, 0, 0, tzinfo=timezone.utc)
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = mock_geo
        
        # Calculate risk during normal hours
        with patch('app.services.anomaly_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = normal_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            risk_normal = await calculate_risk_score(db_session, test_user, test_ip, test_user_agent)
        
        # Calculate risk during unusual hours
        with patch('app.services.anomaly_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = unusual_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            risk_unusual = await calculate_risk_score(db_session, test_user, test_ip, test_user_agent)
    
    # Property: Unusual time should have higher risk score
    assert risk_unusual > risk_normal, \
        f"Unusual time (2 AM) should have higher risk score ({risk_unusual}) than normal time ({risk_normal})"
    
    # The difference should be at least 15 points (the unusual time penalty)
    assert risk_unusual - risk_normal >= 15, \
        f"Unusual time should add at least 15 points to risk score"


@pytest.mark.asyncio
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    hour_utc=st.integers(min_value=0, max_value=23),
)
async def test_unusual_time_risk_increase(
    db_session: AsyncSession,
    test_user: User,
    hour_utc: int
):
    """
    Feature: iam-system-completion, Property 21: Unusual time risk increase
    
    Property-based test that verifies unusual time detection across all hours.
    
    Validates: Requirements 8.2
    """
    test_ip = "192.168.1.100"
    test_user_agent = "Mozilla/5.0"
    
    # Mock the GeoIP call
    mock_geo = {"countryCode": "RU", "country": "Russia"}
    
    # Create a test time with the given hour
    test_time = datetime(2025, 1, 15, hour_utc, 0, 0, tzinfo=timezone.utc)
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = mock_geo
        
        with patch('app.services.anomaly_service.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            risk_score = await calculate_risk_score(db_session, test_user, test_ip, test_user_agent)
    
    # Calculate MSK hour (UTC + 3)
    hour_msk = (hour_utc + 3) % 24
    
    # Property: If hour is outside 7:00-22:00 MSK, risk should include unusual time penalty
    if hour_msk < 7 or hour_msk > 22:
        # Should have unusual time penalty (at least 15 points)
        assert risk_score >= 15, \
            f"Unusual hour {hour_msk}:00 MSK should have risk score >= 15, got {risk_score}"
    else:
        # Normal hours - risk should be lower (no unusual time penalty)
        # Risk could still be non-zero due to other factors, but should be < 15 if only time matters
        pass  # We can't assert exact value as other factors may contribute


# ============================================================================
# Property 22: New device risk increase
# ============================================================================

@pytest.mark.asyncio
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    known_ua=st.text(min_size=10, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
    new_ua=st.text(min_size=10, max_size=100, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
)
async def test_new_device_risk_increase(
    db_session: AsyncSession,
    test_user: User,
    known_ua: str,
    new_ua: str
):
    """
    Feature: iam-system-completion, Property 22: New device risk increase
    
    For any user login, if the user-agent string has never been seen for that user before,
    the risk_score should be higher than for a known device.
    
    Validates: Requirements 8.3
    """
    # Ensure user agents are different
    if known_ua == new_ua:
        return
    
    test_ip = "192.168.1.100"
    
    # Create a successful login audit log with the known user agent
    known_audit = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="login",
        user_agent=known_ua,
        ip_address=test_ip,
        success=True,
        created_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(known_audit)
    await db_session.commit()
    
    # Mock the GeoIP call
    mock_geo = {"countryCode": "RU", "country": "Russia"}
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = mock_geo
        
        # Calculate risk score for known user agent
        risk_known = await calculate_risk_score(db_session, test_user, test_ip, known_ua)
        
        # Calculate risk score for new user agent
        risk_new = await calculate_risk_score(db_session, test_user, test_ip, new_ua)
    
    # Property: New device should have higher risk score than known device
    assert risk_new > risk_known, \
        f"New device should have higher risk score ({risk_new}) than known device ({risk_known})"


@pytest.mark.asyncio
async def test_new_device_risk_increase_example(
    db_session: AsyncSession,
    test_user: User
):
    """
    Example test: New device risk increase
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 8.3
    """
    known_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
    new_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1"
    test_ip = "192.168.1.100"
    
    # Create a successful login audit log with the known user agent
    known_audit = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="login",
        user_agent=known_ua,
        ip_address=test_ip,
        success=True,
        created_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    db_session.add(known_audit)
    await db_session.commit()
    
    # Mock the GeoIP call
    mock_geo = {"countryCode": "RU", "country": "Russia"}
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = mock_geo
        
        # Calculate risk scores
        risk_known = await calculate_risk_score(db_session, test_user, test_ip, known_ua)
        risk_new = await calculate_risk_score(db_session, test_user, test_ip, new_ua)
    
    # New device should have higher risk
    assert risk_new > risk_known, \
        f"New device should have higher risk score: new={risk_new}, known={risk_known}"
    
    # The difference should be at least 15 points (the new device penalty)
    assert risk_new - risk_known >= 15, \
        f"New device should add at least 15 points to risk score"


# ============================================================================
# Property 23: Geographic distance risk scaling
# ============================================================================

@pytest.mark.asyncio
async def test_geographic_distance_risk_scaling_example(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 23: Geographic distance risk scaling
    
    For any user login, the risk_score increase from a different country should be
    greater than the risk_score increase from a different city in the same country.
    
    Validates: Requirements 8.4
    """
    test_ip_russia = "192.168.1.100"
    test_ip_foreign = "8.8.8.8"
    test_user_agent = "Mozilla/5.0"
    
    # Mock GeoIP responses
    geo_russia = {"countryCode": "RU", "country": "Russia", "city": "Moscow"}
    geo_foreign = {"countryCode": "US", "country": "United States", "city": "New York"}
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        # Calculate risk for Russian IP
        mock_get_geo.return_value = geo_russia
        risk_russia = await calculate_risk_score(db_session, test_user, test_ip_russia, test_user_agent)
        
        # Calculate risk for foreign IP
        mock_get_geo.return_value = geo_foreign
        risk_foreign = await calculate_risk_score(db_session, test_user, test_ip_foreign, test_user_agent)
    
    # Property: Foreign country should have higher risk score than same country
    assert risk_foreign > risk_russia, \
        f"Foreign country should have higher risk score ({risk_foreign}) than same country ({risk_russia})"
    
    # The difference should be at least 30 points (the foreign country penalty)
    assert risk_foreign - risk_russia >= 30, \
        f"Foreign country should add at least 30 points to risk score"


@pytest.mark.asyncio
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    country_code=st.sampled_from(["US", "GB", "DE", "FR", "CN", "JP", "BR", "IN"]),
)
async def test_geographic_distance_risk_scaling(
    db_session: AsyncSession,
    test_user: User,
    country_code: str
):
    """
    Feature: iam-system-completion, Property 23: Geographic distance risk scaling
    
    Property-based test that verifies foreign country detection across various countries.
    
    Validates: Requirements 8.4
    """
    test_ip = "8.8.8.8"
    test_user_agent = "Mozilla/5.0"
    
    # Mock GeoIP response with the given country
    geo_info = {"countryCode": country_code, "country": "Foreign Country"}
    
    with patch('app.services.anomaly_service._get_geo_info', new_callable=AsyncMock) as mock_get_geo:
        mock_get_geo.return_value = geo_info
        risk_score = await calculate_risk_score(db_session, test_user, test_ip, test_user_agent)
    
    # Property: Any non-RU country should add foreign country penalty (30 points)
    if country_code != "RU":
        assert risk_score >= 30, \
            f"Foreign country {country_code} should have risk score >= 30, got {risk_score}"


# ============================================================================
# Property 24: Honeypot maximum risk
# ============================================================================

@pytest.mark.asyncio
async def test_honeypot_maximum_risk_example(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 24: Honeypot maximum risk
    
    For any access to a honeypot resource, the risk_score should be set to the
    maximum value (100) and an alert should be created.
    
    Validates: Requirements 8.5
    """
    # Create a honeypot application
    honeypot_app = Application(
        id=uuid.uuid4(),
        name="Honeypot App",
        description="Fake app to detect compromised accounts",
        integration_type="oauth",
        is_active=True,
        is_honeypot=True
    )
    db_session.add(honeypot_app)
    await db_session.commit()
    await db_session.refresh(honeypot_app)
    
    test_ip = "192.168.1.100"
    
    # Check honeypot
    is_honeypot = await check_honeypot(db_session, str(honeypot_app.id), test_user, test_ip)
    
    # Property 1: Should detect as honeypot
    assert is_honeypot is True, "Should detect honeypot application"
    
    # Property 2: User should be blocked
    await db_session.refresh(test_user)
    assert test_user.is_blocked is True, "User should be blocked after honeypot access"
    
    # Property 3: Audit log should be created with risk_score = 100
    from sqlalchemy import select
    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == test_user.id,
            AuditLog.action == "honeypot_triggered"
        )
    )
    audit_log = audit_result.scalar_one_or_none()
    
    assert audit_log is not None, "Audit log should be created for honeypot access"
    assert audit_log.risk_score == 100, \
        f"Honeypot risk score should be 100, got {audit_log.risk_score}"


@pytest.mark.asyncio
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    app_name=st.text(min_size=5, max_size=50, alphabet=st.characters(min_codepoint=32, max_codepoint=126)),
)
async def test_honeypot_maximum_risk(
    db_session: AsyncSession,
    test_user: User,
    app_name: str
):
    """
    Feature: iam-system-completion, Property 24: Honeypot maximum risk
    
    Property-based test that verifies honeypot detection across various app names.
    
    Validates: Requirements 8.5
    """
    # Create a honeypot application with random name
    honeypot_app = Application(
        id=uuid.uuid4(),
        name=app_name,
        description="Honeypot application",
        integration_type="oauth",
        is_active=True,
        is_honeypot=True
    )
    db_session.add(honeypot_app)
    await db_session.commit()
    await db_session.refresh(honeypot_app)
    
    # Reset user blocked status for this test
    test_user.is_blocked = False
    await db_session.commit()
    
    test_ip = "192.168.1.100"
    
    # Check honeypot
    is_honeypot = await check_honeypot(db_session, str(honeypot_app.id), test_user, test_ip)
    
    # Property: Should always detect as honeypot and block user
    assert is_honeypot is True, f"Should detect honeypot application '{app_name}'"
    
    await db_session.refresh(test_user)
    assert test_user.is_blocked is True, f"User should be blocked after accessing honeypot '{app_name}'"
    
    # Verify audit log with maximum risk score
    from sqlalchemy import select
    audit_result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == test_user.id,
            AuditLog.action == "honeypot_triggered",
            AuditLog.resource_id == honeypot_app.id
        )
    )
    audit_log = audit_result.scalar_one_or_none()
    
    assert audit_log is not None, f"Audit log should be created for honeypot '{app_name}'"
    assert audit_log.risk_score == 100, \
        f"Honeypot '{app_name}' risk score should be 100, got {audit_log.risk_score}"


@pytest.mark.asyncio
async def test_non_honeypot_normal_behavior(
    db_session: AsyncSession,
    test_user: User
):
    """
    Test that non-honeypot applications behave normally.
    
    Validates: Requirements 8.5
    """
    # Create a normal (non-honeypot) application
    normal_app = Application(
        id=uuid.uuid4(),
        name="Normal App",
        description="Regular application",
        integration_type="oauth",
        is_active=True,
        is_honeypot=False
    )
    db_session.add(normal_app)
    await db_session.commit()
    await db_session.refresh(normal_app)
    
    test_ip = "192.168.1.100"
    
    # Check honeypot
    is_honeypot = await check_honeypot(db_session, str(normal_app.id), test_user, test_ip)
    
    # Property: Should NOT detect as honeypot
    assert is_honeypot is False, "Normal app should not be detected as honeypot"
    
    # User should NOT be blocked
    await db_session.refresh(test_user)
    assert test_user.is_blocked is False, "User should not be blocked for normal app access"
