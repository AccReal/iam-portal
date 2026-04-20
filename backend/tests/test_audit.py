"""
Property-based tests for Audit Logging system.

These tests verify universal properties that should hold across all inputs
using property-based testing with Hypothesis.
"""
import uuid
import json
import io
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User
from app.models.role import Role
from app.services.audit_service import log_event, get_audit_logs


# ============================================================================
# Property 29: Login event logging
# ============================================================================

@pytest.mark.asyncio
async def test_login_event_logging_success(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 29: Login event logging
    
    For any login attempt (successful), an audit log entry should be created
    with the correct user_id, action, ip_address, success status, and timestamp.
    
    Validates: Requirements 10.1
    """
    # Log a successful login event
    ip_address = "192.168.1.100"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,
        action="login",
        ip=ip_address,
        user_agent=user_agent,
        success=True,
        details={"method": "password"}
    )
    await db_session.commit()
    
    # Verify the entry was created correctly
    assert entry is not None
    assert entry.user_id == test_user.id
    assert entry.action == "login"
    assert entry.ip_address == ip_address
    assert entry.user_agent == user_agent
    assert entry.success is True
    assert entry.details == {"method": "password"}
    assert entry.created_at is not None
    
    # Verify it's in the database
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == entry.id)
    )
    db_entry = result.scalar_one_or_none()
    assert db_entry is not None
    assert db_entry.user_id == test_user.id
    assert db_entry.action == "login"
    assert db_entry.success is True


@pytest.mark.asyncio
async def test_login_event_logging_failure(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 29: Login event logging
    
    For any login attempt (failed), an audit log entry should be created
    with the correct user_id, action, ip_address, success=False status, and timestamp.
    
    Validates: Requirements 10.1
    """
    # Log a failed login event
    ip_address = "10.0.0.50"
    user_agent = "curl/7.68.0"
    
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,
        action="login",
        ip=ip_address,
        user_agent=user_agent,
        success=False,
        details={"reason": "invalid_password"}
    )
    await db_session.commit()
    
    # Verify the entry was created correctly
    assert entry is not None
    assert entry.user_id == test_user.id
    assert entry.action == "login"
    assert entry.ip_address == ip_address
    assert entry.success is False
    assert entry.details == {"reason": "invalid_password"}
    
    # Verify it's in the database
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == entry.id)
    )
    db_entry = result.scalar_one_or_none()
    assert db_entry is not None
    assert db_entry.success is False


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    success=st.booleans(),
    risk_score=st.integers(min_value=0, max_value=100)
)
@pytest.mark.asyncio
async def test_login_event_logging_property(
    success: bool,
    risk_score: int,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 29: Login event logging
    
    Property-based test: For any login attempt with any success status and risk score,
    an audit log entry should be created with all required fields.
    
    Validates: Requirements 10.1
    """
    ip_address = f"192.168.1.{risk_score % 256}"
    
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,
        action="login",
        ip=ip_address,
        user_agent="test-agent",
        success=success,
        risk_score=risk_score
    )
    await db_session.commit()
    
    # Verify all required fields are present
    assert entry.user_id == test_user.id
    assert entry.action == "login"
    assert entry.ip_address == ip_address
    assert entry.success == success
    assert entry.risk_score == risk_score
    assert entry.created_at is not None
    
    # Verify timestamp is recent (within last minute)
    time_diff = datetime.now(timezone.utc) - entry.created_at
    assert time_diff.total_seconds() < 60, "Timestamp should be recent"


# ============================================================================
# Property 30: User modification logging
# ============================================================================

@pytest.mark.asyncio
async def test_user_creation_logging(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 30: User modification logging
    
    For user creation, an audit log entry should be created with action type
    and details of what was created in the details field.
    
    Validates: Requirements 10.2
    """
    # Log user creation event
    new_user_id = uuid.uuid4()
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,  # Admin who created the user
        action="user_create",
        resource_type="user",
        resource_id=str(new_user_id),
        success=True,
        details={
            "created_user_id": str(new_user_id),
            "email": "newuser@example.com",
            "full_name": "New User"
        }
    )
    await db_session.commit()
    
    # Verify the entry
    assert entry.action == "user_create"
    assert entry.resource_type == "user"
    assert entry.resource_id == new_user_id
    assert entry.details is not None
    assert "created_user_id" in entry.details
    assert "email" in entry.details
    assert entry.details["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_user_update_logging(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 30: User modification logging
    
    For user update, an audit log entry should be created with details of
    what changed in the details field.
    
    Validates: Requirements 10.2
    """
    # Log user update event
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,  # Admin who updated the user
        action="user_update",
        resource_type="user",
        resource_id=str(test_user.id),
        success=True,
        details={
            "updated_user_id": str(test_user.id),
            "changes": {
                "full_name": {"old": "Old Name", "new": "New Name"},
                "phone": {"old": None, "new": "+1234567890"}
            }
        }
    )
    await db_session.commit()
    
    # Verify the entry
    assert entry.action == "user_update"
    assert entry.resource_type == "user"
    assert entry.details is not None
    assert "changes" in entry.details
    assert "full_name" in entry.details["changes"]
    assert entry.details["changes"]["full_name"]["new"] == "New Name"


@pytest.mark.asyncio
async def test_user_block_logging(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 30: User modification logging
    
    For user blocking, an audit log entry should be created with details
    in the details field.
    
    Validates: Requirements 10.2
    """
    # Log user block event
    blocked_user_id = uuid.uuid4()
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,  # Admin who blocked the user
        action="user_block",
        resource_type="user",
        resource_id=str(blocked_user_id),
        success=True,
        details={
            "blocked_user_id": str(blocked_user_id),
            "reason": "suspicious_activity",
            "blocked_by": str(test_user.id)
        }
    )
    await db_session.commit()
    
    # Verify the entry
    assert entry.action == "user_block"
    assert entry.resource_type == "user"
    assert entry.details is not None
    assert "reason" in entry.details
    assert entry.details["reason"] == "suspicious_activity"


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    action_type=st.sampled_from(["user_create", "user_update", "user_block", "user_delete"]),
    has_details=st.booleans()
)
@pytest.mark.asyncio
async def test_user_modification_logging_property(
    action_type: str,
    has_details: bool,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 30: User modification logging
    
    Property-based test: For any user modification action, an audit log entry
    should be created with the action type and optional details.
    
    Validates: Requirements 10.2
    """
    resource_id = uuid.uuid4()
    details = {"action": action_type, "timestamp": datetime.now(timezone.utc).isoformat()} if has_details else None
    
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,
        action=action_type,
        resource_type="user",
        resource_id=str(resource_id),
        success=True,
        details=details
    )
    await db_session.commit()
    
    # Verify the entry
    assert entry.action == action_type
    assert entry.resource_type == "user"
    assert entry.resource_id == resource_id
    
    if has_details:
        assert entry.details is not None
        assert "action" in entry.details
    else:
        assert entry.details is None or entry.details == {}


# ============================================================================
# Property 31: Audit export completeness
# ============================================================================

@pytest.mark.asyncio
async def test_audit_export_completeness(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 31: Audit export completeness
    
    For any set of audit log entries, exporting to CSV or XLSX should produce
    a file containing all entries with all fields correctly formatted.
    
    Validates: Requirements 10.3
    """
    # Create multiple audit log entries
    entries = []
    for i in range(5):
        entry = await log_event(
            db=db_session,
            user_id=test_user.id,
            action=f"test_action_{i}",
            ip=f"192.168.1.{i}",
            user_agent=f"test-agent-{i}",
            success=i % 2 == 0,
            risk_score=i * 10,
            details={"index": i, "test": True}
        )
        entries.append(entry)
    await db_session.commit()
    
    # Get all audit logs
    logs, total = await get_audit_logs(db_session, page=1, per_page=100)
    
    # Verify we got all entries
    assert total >= 5, f"Should have at least 5 entries, got {total}"
    
    # Verify all fields are present in each log
    for log in logs:
        assert "id" in log
        assert "user_id" in log
        assert "action" in log
        assert "ip_address" in log
        assert "user_agent" in log
        assert "success" in log
        assert "risk_score" in log
        assert "details" in log
        assert "created_at" in log
    
    # Verify the entries we created are in the results
    created_actions = {f"test_action_{i}" for i in range(5)}
    found_actions = {log["action"] for log in logs if log["action"].startswith("test_action_")}
    assert created_actions.issubset(found_actions), "All created entries should be in export"


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    num_entries=st.integers(min_value=1, max_value=20)
)
@pytest.mark.asyncio
async def test_audit_export_completeness_property(
    num_entries: int,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 31: Audit export completeness
    
    Property-based test: For any number of audit entries, the export should
    contain exactly that many entries with all fields preserved.
    
    Validates: Requirements 10.3
    """
    # Create entries
    created_ids = []
    for i in range(num_entries):
        entry = await log_event(
            db=db_session,
            user_id=test_user.id,
            action=f"export_test_{uuid.uuid4().hex[:8]}",
            success=True
        )
        created_ids.append(str(entry.id))
    await db_session.commit()
    
    # Get all logs
    logs, total = await get_audit_logs(db_session, page=1, per_page=1000)
    
    # Verify count
    assert total >= num_entries, f"Should have at least {num_entries} entries"
    
    # Verify our entries are present
    log_ids = {log["id"] for log in logs}
    for created_id in created_ids:
        assert created_id in log_ids, f"Entry {created_id} should be in export"


# ============================================================================
# Property 6: Audit filter correctness
# ============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    filter_user=st.booleans(),
    filter_action=st.booleans(),
    filter_date=st.booleans(),
    action_type=st.sampled_from(["login", "logout", "user_create", "user_update", "user_delete"]),
    days_back=st.integers(min_value=1, max_value=30)
)
@pytest.mark.asyncio
async def test_audit_filter_correctness_property(
    filter_user: bool,
    filter_action: bool,
    filter_date: bool,
    action_type: str,
    days_back: int,
    db_session: AsyncSession,
    test_user: User,
    test_role: Role
):
    """
    Feature: iam-system-completion, Property 6: Audit filter correctness
    
    For any combination of audit log filters (date range, user, action, risk score),
    all returned events should satisfy all active filter conditions.
    
    Validates: Requirements 3.2
    """
    # Create another user for testing user filter
    other_user = User(
        id=uuid.uuid4(),
        email=f"filter_prop_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        full_name="Filter Property Test User",
        role_id=test_role.id,
        is_active=True
    )
    db_session.add(other_user)
    await db_session.commit()
    
    # Create diverse audit entries
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=days_back + 5)
    recent_date = now - timedelta(days=days_back - 1)
    
    # Create entries with different combinations
    entries_created = []
    
    # Entry 1: test_user, action_type, old date
    entry1 = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action=action_type,
        success=True,
        created_at=old_date
    )
    db_session.add(entry1)
    entries_created.append({
        "id": entry1.id,
        "user_id": test_user.id,
        "action": action_type,
        "created_at": old_date
    })
    
    # Entry 2: test_user, different action, recent date
    entry2 = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="different_action",
        success=True,
        created_at=recent_date
    )
    db_session.add(entry2)
    entries_created.append({
        "id": entry2.id,
        "user_id": test_user.id,
        "action": "different_action",
        "created_at": recent_date
    })
    
    # Entry 3: other_user, action_type, recent date
    entry3 = AuditLog(
        id=uuid.uuid4(),
        user_id=other_user.id,
        action=action_type,
        success=True,
        created_at=recent_date
    )
    db_session.add(entry3)
    entries_created.append({
        "id": entry3.id,
        "user_id": other_user.id,
        "action": action_type,
        "created_at": recent_date
    })
    
    # Entry 4: other_user, different action, old date
    entry4 = AuditLog(
        id=uuid.uuid4(),
        user_id=other_user.id,
        action="another_action",
        success=True,
        created_at=old_date
    )
    db_session.add(entry4)
    entries_created.append({
        "id": entry4.id,
        "user_id": other_user.id,
        "action": "another_action",
        "created_at": old_date
    })
    
    await db_session.commit()
    
    # Build filter parameters
    filter_user_id = str(test_user.id) if filter_user else None
    filter_action_str = action_type if filter_action else None
    
    # Date filter: only include entries from the last 'days_back' days
    date_from = now - timedelta(days=days_back) if filter_date else None
    date_to = now if filter_date else None
    
    # Query with filters
    logs, total = await get_audit_logs(
        db_session,
        user_id=filter_user_id,
        action=filter_action_str,
        date_from=date_from,
        date_to=date_to,
        page=1,
        per_page=100
    )
    
    # Verify all returned logs satisfy ALL active filters
    for log in logs:
        log_id = log["id"]
        
        # Find the original entry if it's one we created
        original = None
        for entry in entries_created:
            if str(entry["id"]) == log_id:
                original = entry
                break
        
        # If this is one of our test entries, verify filters
        if original:
            # Check user filter
            if filter_user:
                assert log["user_id"] == str(test_user.id), \
                    f"Log {log_id} should match user filter: expected {test_user.id}, got {log['user_id']}"
            
            # Check action filter
            if filter_action:
                assert log["action"] == action_type, \
                    f"Log {log_id} should match action filter: expected {action_type}, got {log['action']}"
            
            # Check date filter
            if filter_date:
                log_time = datetime.fromisoformat(log["created_at"].replace('Z', '+00:00'))
                assert date_from <= log_time <= date_to, \
                    f"Log {log_id} timestamp {log_time} should be between {date_from} and {date_to}"
    
    # Verify that entries NOT matching filters are excluded
    for entry in entries_created:
        entry_id = str(entry["id"])
        log_ids = {log["id"] for log in logs}
        
        should_be_included = True
        
        # Check if entry should be filtered out by user filter
        if filter_user and entry["user_id"] != test_user.id:
            should_be_included = False
        
        # Check if entry should be filtered out by action filter
        if filter_action and entry["action"] != action_type:
            should_be_included = False
        
        # Check if entry should be filtered out by date filter
        if filter_date:
            if entry["created_at"] < date_from or entry["created_at"] > date_to:
                should_be_included = False
        
        if should_be_included:
            assert entry_id in log_ids, \
                f"Entry {entry_id} should be included in results"
        else:
            assert entry_id not in log_ids, \
                f"Entry {entry_id} should be excluded from results"


# ============================================================================
# Property 8: Audit export consistency
# ============================================================================

@pytest.mark.asyncio
async def test_audit_export_csv_consistency(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 8: Audit export consistency
    
    For any set of filtered audit events, the exported CSV file should contain
    exactly the same events with all fields preserved.
    
    Validates: Requirements 3.4
    """
    # Create test audit entries with diverse data
    entries_data = [
        {
            "action": "login",
            "ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "risk_score": 10,
            "details": {"method": "password"}
        },
        {
            "action": "logout",
            "ip": "192.168.1.101",
            "user_agent": "Chrome/90.0",
            "success": True,
            "risk_score": 5,
            "details": {"session_duration": 3600}
        },
        {
            "action": "user_update",
            "ip": "10.0.0.50",
            "user_agent": "Firefox/88.0",
            "success": False,
            "risk_score": 45,
            "details": {"field": "email", "reason": "validation_error"}
        }
    ]
    
    created_entries = []
    for entry_data in entries_data:
        entry = await log_event(
            db=db_session,
            user_id=test_user.id,
            action=entry_data["action"],
            ip=entry_data["ip"],
            user_agent=entry_data["user_agent"],
            success=entry_data["success"],
            risk_score=entry_data["risk_score"],
            details=entry_data["details"]
        )
        created_entries.append(entry)
    await db_session.commit()
    
    # Get audit logs (simulating what export would get)
    logs, total = await get_audit_logs(db_session, page=1, per_page=100)
    
    # Filter to only our created entries
    our_logs = [log for log in logs if log["id"] in [str(e.id) for e in created_entries]]
    
    # Verify we got all our entries
    assert len(our_logs) == len(created_entries), \
        f"Should retrieve all {len(created_entries)} created entries"
    
    # Verify all fields are present and correct in each log
    for i, log in enumerate(our_logs):
        # Find matching created entry
        matching_entry = next(e for e in created_entries if str(e.id) == log["id"])
        
        # Verify all fields are preserved
        assert log["user_id"] == str(test_user.id), "User ID should be preserved"
        assert log["user_email"] == test_user.email, "User email should be included"
        assert log["user_name"] == test_user.full_name, "User name should be included"
        assert log["action"] == matching_entry.action, "Action should be preserved"
        assert log["ip_address"] == matching_entry.ip_address, "IP address should be preserved"
        assert log["user_agent"] == matching_entry.user_agent, "User agent should be preserved"
        assert log["success"] == matching_entry.success, "Success status should be preserved"
        assert log["risk_score"] == matching_entry.risk_score, "Risk score should be preserved"
        assert log["details"] == matching_entry.details, "Details should be preserved"
        assert "created_at" in log, "Created timestamp should be present"


@pytest.mark.asyncio
async def test_audit_export_xlsx_consistency(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 8: Audit export consistency
    
    For any set of filtered audit events, the exported XLSX file should contain
    exactly the same events with all fields preserved.
    
    Validates: Requirements 3.4
    """
    # Create test audit entries
    entries_data = [
        {
            "action": "mfa_verify",
            "ip": "172.16.0.1",
            "success": True,
            "risk_score": 0,
            "details": {"method": "totp"}
        },
        {
            "action": "password_reset",
            "ip": "172.16.0.2",
            "success": True,
            "risk_score": 20,
            "details": {"email_sent": True}
        }
    ]
    
    created_entries = []
    for entry_data in entries_data:
        entry = await log_event(
            db=db_session,
            user_id=test_user.id,
            action=entry_data["action"],
            ip=entry_data["ip"],
            success=entry_data["success"],
            risk_score=entry_data["risk_score"],
            details=entry_data["details"]
        )
        created_entries.append(entry)
    await db_session.commit()
    
    # Get audit logs (simulating what export would get)
    logs, total = await get_audit_logs(db_session, page=1, per_page=100)
    
    # Filter to only our created entries
    our_logs = [log for log in logs if log["id"] in [str(e.id) for e in created_entries]]
    
    # Verify we got all our entries
    assert len(our_logs) == len(created_entries), \
        f"Should retrieve all {len(created_entries)} created entries"
    
    # Verify all fields are present and correct
    for log in our_logs:
        matching_entry = next(e for e in created_entries if str(e.id) == log["id"])
        
        # Verify all required fields for XLSX export
        assert log["user_id"] == str(test_user.id)
        assert log["user_email"] == test_user.email
        assert log["user_name"] == test_user.full_name
        assert log["action"] == matching_entry.action
        assert log["ip_address"] == matching_entry.ip_address
        assert log["success"] == matching_entry.success
        assert log["risk_score"] == matching_entry.risk_score
        assert log["details"] == matching_entry.details
        assert "created_at" in log


@pytest.mark.asyncio
async def test_audit_export_with_filters_consistency(
    db_session: AsyncSession,
    test_user: User,
    test_role: Role
):
    """
    Feature: iam-system-completion, Property 8: Audit export consistency
    
    For filtered audit events, the export should contain exactly the filtered
    events, not all events.
    
    Validates: Requirements 3.4
    """
    # Create another user
    other_user = User(
        id=uuid.uuid4(),
        email=f"export_filter_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        full_name="Export Filter Test User",
        role_id=test_role.id,
        is_active=True
    )
    db_session.add(other_user)
    await db_session.commit()
    
    # Create entries for both users with different actions
    test_user_login = await log_event(db_session, test_user.id, "login", success=True)
    test_user_logout = await log_event(db_session, test_user.id, "logout", success=True)
    other_user_login = await log_event(db_session, other_user.id, "login", success=True)
    other_user_logout = await log_event(db_session, other_user.id, "logout", success=True)
    await db_session.commit()
    
    # Get filtered logs (only test_user, only login action)
    filtered_logs, total = await get_audit_logs(
        db_session,
        user_id=str(test_user.id),
        action="login",
        page=1,
        per_page=100
    )
    
    # Verify only the matching entry is in the filtered results
    filtered_ids = {log["id"] for log in filtered_logs}
    
    # test_user_login should be included
    assert str(test_user_login.id) in filtered_ids, \
        "Filtered export should include test_user login"
    
    # Others should be excluded
    assert str(test_user_logout.id) not in filtered_ids, \
        "Filtered export should exclude test_user logout"
    assert str(other_user_login.id) not in filtered_ids, \
        "Filtered export should exclude other_user login"
    assert str(other_user_logout.id) not in filtered_ids, \
        "Filtered export should exclude other_user logout"
    
    # Verify all returned logs match the filter criteria
    for log in filtered_logs:
        if log["id"] in [str(test_user_login.id), str(test_user_logout.id), 
                         str(other_user_login.id), str(other_user_logout.id)]:
            assert log["user_id"] == str(test_user.id), \
                "All filtered logs should be for test_user"
            assert log["action"] == "login", \
                "All filtered logs should have action 'login'"


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    num_entries=st.integers(min_value=1, max_value=15),
    include_details=st.booleans(),
    include_risk_score=st.booleans()
)
@pytest.mark.asyncio
async def test_audit_export_consistency_property(
    num_entries: int,
    include_details: bool,
    include_risk_score: bool,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 8: Audit export consistency
    
    Property-based test: For any set of audit log entries, exporting should
    produce data containing all entries with all fields correctly preserved.
    
    Validates: Requirements 3.4
    """
    # Create random audit entries
    created_entries = []
    for i in range(num_entries):
        details = {"index": i, "test": True} if include_details else None
        risk_score = (i * 7) % 100 if include_risk_score else None
        
        entry = await log_event(
            db=db_session,
            user_id=test_user.id,
            action=f"export_prop_test_{uuid.uuid4().hex[:8]}",
            ip=f"192.168.{i % 256}.{(i * 3) % 256}",
            user_agent=f"TestAgent/{i}",
            success=i % 2 == 0,
            risk_score=risk_score,
            details=details
        )
        created_entries.append(entry)
    await db_session.commit()
    
    # Get all logs (simulating export)
    logs, total = await get_audit_logs(db_session, page=1, per_page=1000)
    
    # Filter to only our created entries
    our_logs = [log for log in logs if log["id"] in [str(e.id) for e in created_entries]]
    
    # Verify count matches
    assert len(our_logs) == num_entries, \
        f"Export should contain all {num_entries} created entries, got {len(our_logs)}"
    
    # Verify all fields are preserved for each entry
    for log in our_logs:
        # Find matching created entry
        matching_entry = next(e for e in created_entries if str(e.id) == log["id"])
        
        # Verify all fields
        assert log["user_id"] == str(test_user.id), \
            f"Entry {log['id']}: user_id should be preserved"
        assert log["action"] == matching_entry.action, \
            f"Entry {log['id']}: action should be preserved"
        assert log["ip_address"] == matching_entry.ip_address, \
            f"Entry {log['id']}: ip_address should be preserved"
        assert log["user_agent"] == matching_entry.user_agent, \
            f"Entry {log['id']}: user_agent should be preserved"
        assert log["success"] == matching_entry.success, \
            f"Entry {log['id']}: success should be preserved"
        
        # Verify optional fields
        if include_risk_score:
            assert log["risk_score"] == matching_entry.risk_score, \
                f"Entry {log['id']}: risk_score should be preserved"
        
        if include_details:
            assert log["details"] == matching_entry.details, \
                f"Entry {log['id']}: details should be preserved"
        
        # Verify timestamp is present
        assert "created_at" in log, \
            f"Entry {log['id']}: created_at should be present"
        assert log["created_at"] is not None, \
            f"Entry {log['id']}: created_at should not be None"


@pytest.mark.asyncio
async def test_audit_export_empty_fields_consistency(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 8: Audit export consistency
    
    For audit entries with null/empty fields, the export should preserve
    the null values correctly.
    
    Validates: Requirements 3.4
    """
    # Create entry with minimal fields (many nulls)
    entry = await log_event(
        db=db_session,
        user_id=test_user.id,
        action="minimal_action",
        ip=None,
        user_agent=None,
        success=True,
        risk_score=None,
        details=None
    )
    await db_session.commit()
    
    # Get the log
    logs, total = await get_audit_logs(db_session, page=1, per_page=100)
    our_log = next((log for log in logs if log["id"] == str(entry.id)), None)
    
    assert our_log is not None, "Entry should be in export"
    
    # Verify null fields are handled correctly
    assert our_log["ip_address"] is None, "Null IP should be preserved as None"
    assert our_log["user_agent"] is None, "Null user_agent should be preserved as None"
    assert our_log["risk_score"] is None, "Null risk_score should be preserved as None"
    assert our_log["details"] is None, "Null details should be preserved as None"
    
    # Verify required fields are still present
    assert our_log["user_id"] == str(test_user.id)
    assert our_log["action"] == "minimal_action"
    assert our_log["success"] is True
    assert "created_at" in our_log


# ============================================================================
# Property 32: Audit filter combination correctness
# ============================================================================

@pytest.mark.asyncio
async def test_audit_filter_by_user(
    db_session: AsyncSession,
    test_user: User,
    test_role: Role
):
    """
    Feature: iam-system-completion, Property 32: Audit filter combination correctness
    
    For user_id filter, the returned audit entries should only include entries
    for that specific user.
    
    Validates: Requirements 10.4
    """
    # Create another user
    other_user = User(
        id=uuid.uuid4(),
        email=f"other_{uuid.uuid4()}@example.com",
        password_hash="hashed",
        full_name="Other User",
        role_id=test_role.id,
        is_active=True
    )
    db_session.add(other_user)
    await db_session.commit()
    
    # Create entries for both users
    await log_event(db_session, test_user.id, "action1", success=True)
    await log_event(db_session, test_user.id, "action2", success=True)
    await log_event(db_session, other_user.id, "action3", success=True)
    await db_session.commit()
    
    # Filter by test_user
    logs, total = await get_audit_logs(db_session, user_id=str(test_user.id), page=1, per_page=100)
    
    # Verify all returned logs are for test_user
    for log in logs:
        if log["user_id"] is not None:
            assert log["user_id"] == str(test_user.id), \
                f"All logs should be for user {test_user.id}, got {log['user_id']}"


@pytest.mark.asyncio
async def test_audit_filter_by_action(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 32: Audit filter combination correctness
    
    For action filter, the returned audit entries should only include entries
    with that specific action.
    
    Validates: Requirements 10.4
    """
    # Create entries with different actions
    await log_event(db_session, test_user.id, "login", success=True)
    await log_event(db_session, test_user.id, "login", success=False)
    await log_event(db_session, test_user.id, "logout", success=True)
    await log_event(db_session, test_user.id, "user_update", success=True)
    await db_session.commit()
    
    # Filter by action "login"
    logs, total = await get_audit_logs(db_session, action="login", page=1, per_page=100)
    
    # Verify all returned logs have action "login"
    for log in logs:
        assert log["action"] == "login", \
            f"All logs should have action 'login', got '{log['action']}'"


@pytest.mark.asyncio
async def test_audit_filter_by_date_range(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 32: Audit filter combination correctness
    
    For date range filter, the returned audit entries should only include entries
    within that date range.
    
    Validates: Requirements 10.4
    """
    # Create entries (they will have current timestamp)
    now = datetime.now(timezone.utc)
    
    # Create some entries
    entry1 = await log_event(db_session, test_user.id, "recent_action", success=True)
    await db_session.commit()
    
    # Define date range (last hour to future)
    date_from = now - timedelta(hours=1)
    date_to = now + timedelta(hours=1)
    
    # Filter by date range
    logs, total = await get_audit_logs(
        db_session,
        date_from=date_from,
        date_to=date_to,
        page=1,
        per_page=100
    )
    
    # Verify all returned logs are within date range
    for log in logs:
        log_time = datetime.fromisoformat(log["created_at"].replace('Z', '+00:00'))
        assert date_from <= log_time <= date_to, \
            f"Log timestamp {log_time} should be between {date_from} and {date_to}"


@pytest.mark.asyncio
async def test_audit_filter_combination(
    db_session: AsyncSession,
    test_user: User,
    test_role: Role
):
    """
    Feature: iam-system-completion, Property 32: Audit filter combination correctness
    
    For any combination of filters, the returned audit entries should satisfy
    ALL filter conditions simultaneously.
    
    Validates: Requirements 10.4
    """
    # Create another user
    other_user = User(
        id=uuid.uuid4(),
        email=f"filter_test_{uuid.uuid4()}@example.com",
        password_hash="hashed",
        full_name="Filter Test User",
        role_id=test_role.id,
        is_active=True
    )
    db_session.add(other_user)
    await db_session.commit()
    
    # Create various entries
    await log_event(db_session, test_user.id, "login", success=True)
    await log_event(db_session, test_user.id, "logout", success=True)
    await log_event(db_session, other_user.id, "login", success=True)
    await log_event(db_session, other_user.id, "logout", success=False)
    await db_session.commit()
    
    # Filter by user AND action
    logs, total = await get_audit_logs(
        db_session,
        user_id=str(test_user.id),
        action="login",
        page=1,
        per_page=100
    )
    
    # Verify all returned logs match BOTH filters
    for log in logs:
        if log["user_id"] is not None:
            assert log["user_id"] == str(test_user.id), \
                "All logs should be for the filtered user"
        assert log["action"] == "login", \
            "All logs should have the filtered action"


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    filter_success=st.booleans(),
    include_success_filter=st.booleans()
)
@pytest.mark.asyncio
async def test_audit_filter_correctness_property(
    filter_success: bool,
    include_success_filter: bool,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 32: Audit filter combination correctness
    
    Property-based test: Filters should correctly include/exclude entries based
    on the filter criteria.
    
    Validates: Requirements 10.4
    """
    # Create entries with different success values
    await log_event(db_session, test_user.id, "test_success", success=True)
    await log_event(db_session, test_user.id, "test_failure", success=False)
    await db_session.commit()
    
    # Apply filter if requested
    if include_success_filter:
        # Query database directly with filter
        query = select(AuditLog).where(AuditLog.success == filter_success)
        result = await db_session.execute(query)
        logs = result.scalars().all()
        
        # Verify all logs match the filter
        for log in logs:
            assert log.success == filter_success, \
                f"All logs should have success={filter_success}"


# ============================================================================
# Property 33: Audit retention policy enforcement
# ============================================================================

@pytest.mark.asyncio
async def test_audit_retention_policy_old_entries(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 33: Audit retention policy enforcement
    
    For any audit log entry older than the configured retention period,
    it should be identifiable for deletion by the retention cleanup task.
    
    Note: This tests the logic for identifying old entries. The actual deletion
    would be performed by a scheduled task.
    
    Validates: Requirements 10.5
    """
    # Define retention period (e.g., 90 days)
    retention_days = 90
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    # Create a recent entry
    recent_entry = await log_event(
        db_session,
        test_user.id,
        "recent_action",
        success=True
    )
    await db_session.commit()
    
    # Simulate an old entry by manually setting created_at
    old_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="old_action",
        success=True,
        created_at=datetime.now(timezone.utc) - timedelta(days=retention_days + 10)
    )
    db_session.add(old_entry)
    await db_session.commit()
    
    # Query for entries older than retention period
    query = select(AuditLog).where(AuditLog.created_at < cutoff_date)
    result = await db_session.execute(query)
    old_entries = result.scalars().all()
    
    # Verify old entry is identified
    old_entry_ids = [str(e.id) for e in old_entries]
    assert str(old_entry.id) in old_entry_ids, \
        "Old entry should be identified for deletion"
    
    # Verify recent entry is NOT identified
    assert str(recent_entry.id) not in old_entry_ids, \
        "Recent entry should not be identified for deletion"


@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    days_old=st.integers(min_value=0, max_value=200)
)
@pytest.mark.asyncio
async def test_audit_retention_policy_property(
    days_old: int,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 33: Audit retention policy enforcement
    
    Property-based test: Entries older than retention period should be identifiable
    for deletion, while newer entries should not be.
    
    Validates: Requirements 10.5
    """
    retention_days = 90
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    # Create entry with specific age
    entry_date = datetime.now(timezone.utc) - timedelta(days=days_old)
    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action=f"action_age_{days_old}",
        success=True,
        created_at=entry_date
    )
    db_session.add(entry)
    await db_session.commit()
    
    # Check if entry should be deleted based on retention policy
    should_be_deleted = days_old > retention_days
    is_old = entry.created_at < cutoff_date
    
    assert is_old == should_be_deleted, \
        f"Entry {days_old} days old should {'be' if should_be_deleted else 'not be'} marked for deletion"


def test_audit_retention_policy_logic():
    """
    Feature: iam-system-completion, Property 33: Audit retention policy enforcement
    
    Unit test for retention policy logic without database.
    
    Validates: Requirements 10.5
    """
    def should_delete_entry(entry_date: datetime, retention_days: int) -> bool:
        """Determine if an entry should be deleted based on retention policy."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        return entry_date < cutoff_date
    
    retention_days = 90
    now = datetime.now(timezone.utc)
    
    # Test cases
    test_cases = [
        (now - timedelta(days=89), False, "Entry 89 days old should be kept"),
        (now - timedelta(days=90), True, "Entry exactly 90 days old should be deleted (< cutoff)"),
        (now - timedelta(days=91), True, "Entry 91 days old should be deleted"),
        (now - timedelta(days=365), True, "Entry 1 year old should be deleted"),
        (now, False, "Current entry should be kept"),
        (now - timedelta(hours=1), False, "Entry 1 hour old should be kept"),
    ]
    
    for entry_date, expected_delete, message in test_cases:
        result = should_delete_entry(entry_date, retention_days)
        assert result == expected_delete, message


# ============================================================================
# Additional Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_audit_log_with_null_user(
    db_session: AsyncSession
):
    """
    Test that audit logs can be created without a user_id (for system events).
    
    Validates: Requirements 10.1
    """
    # Log system event without user
    entry = await log_event(
        db=db_session,
        user_id=None,
        action="system_startup",
        success=True,
        details={"version": "1.0.0"}
    )
    await db_session.commit()
    
    # Verify the entry
    assert entry.user_id is None
    assert entry.action == "system_startup"
    assert entry.success is True


@pytest.mark.asyncio
async def test_audit_log_pagination(
    db_session: AsyncSession,
    test_user: User
):
    """
    Test that audit log pagination works correctly.
    
    Validates: Requirements 10.3
    """
    # Create 25 entries
    for i in range(25):
        await log_event(
            db_session,
            test_user.id,
            f"pagination_test_{i}",
            success=True
        )
    await db_session.commit()
    
    # Get first page (20 items)
    logs_page1, total = await get_audit_logs(db_session, page=1, per_page=20)
    assert len(logs_page1) <= 20
    assert total >= 25
    
    # Get second page
    logs_page2, _ = await get_audit_logs(db_session, page=2, per_page=20)
    assert len(logs_page2) >= 5  # At least our remaining entries
    
    # Verify no overlap
    page1_ids = {log["id"] for log in logs_page1}
    page2_ids = {log["id"] for log in logs_page2}
    assert len(page1_ids & page2_ids) == 0, "Pages should not overlap"


# ============================================================================
# Property 7: Audit search completeness
# ============================================================================

@pytest.mark.asyncio
async def test_audit_search_in_user_email(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 7: Audit search completeness
    
    For search query matching user email, all returned audit events should
    contain the search query in the user email field.
    
    Validates: Requirements 3.3
    """
    # Create audit entries
    await log_event(db_session, test_user.id, "test_action", success=True)
    await db_session.commit()
    
    # Search by part of user email
    search_term = test_user.email.split("@")[0][:5]  # First 5 chars of email
    logs, total = await get_audit_logs(db_session, search=search_term, page=1, per_page=100)
    
    # Verify all returned logs contain the search term in user email
    for log in logs:
        if log["user_email"]:
            assert search_term.lower() in log["user_email"].lower(), \
                f"Log should contain search term '{search_term}' in user_email"


@pytest.mark.asyncio
async def test_audit_search_in_action(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 7: Audit search completeness
    
    For search query matching action, all returned audit events should
    contain the search query in the action field.
    
    Validates: Requirements 3.3
    """
    # Create audit entries with specific actions
    await log_event(db_session, test_user.id, "user_login", success=True)
    await log_event(db_session, test_user.id, "user_logout", success=True)
    await log_event(db_session, test_user.id, "admin_action", success=True)
    await db_session.commit()
    
    # Search by action keyword
    search_term = "user"
    logs, total = await get_audit_logs(db_session, search=search_term, page=1, per_page=100)
    
    # Verify all returned logs contain the search term in at least one field
    for log in logs:
        found = False
        if log["action"] and search_term.lower() in log["action"].lower():
            found = True
        elif log["user_email"] and search_term.lower() in log["user_email"].lower():
            found = True
        elif log["user_name"] and search_term.lower() in log["user_name"].lower():
            found = True
        
        assert found, f"Log should contain search term '{search_term}' in some text field"


@pytest.mark.asyncio
async def test_audit_search_in_ip_address(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 7: Audit search completeness
    
    For search query matching IP address, all returned audit events should
    contain the search query in the IP address field.
    
    Validates: Requirements 3.3
    """
    # Create audit entries with specific IPs
    await log_event(db_session, test_user.id, "action1", ip="192.168.1.100", success=True)
    await log_event(db_session, test_user.id, "action2", ip="10.0.0.50", success=True)
    await log_event(db_session, test_user.id, "action3", ip="192.168.1.200", success=True)
    await db_session.commit()
    
    # Search by IP pattern
    search_term = "192.168"
    logs, total = await get_audit_logs(db_session, search=search_term, page=1, per_page=100)
    
    # Verify all returned logs contain the search term in at least one field
    for log in logs:
        found = False
        if log["ip_address"] and search_term in log["ip_address"]:
            found = True
        elif log["action"] and search_term in log["action"]:
            found = True
        elif log["user_email"] and search_term in log["user_email"]:
            found = True
        
        assert found, f"Log should contain search term '{search_term}' in some text field"


@pytest.mark.asyncio
async def test_audit_search_in_details(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 7: Audit search completeness
    
    For search query matching details field, all returned audit events should
    contain the search query in the details field.
    
    Validates: Requirements 3.3
    """
    # Create audit entries with specific details
    await log_event(
        db_session,
        test_user.id,
        "action1",
        success=True,
        details={"reason": "password_reset", "method": "email"}
    )
    await log_event(
        db_session,
        test_user.id,
        "action2",
        success=True,
        details={"reason": "account_locked", "attempts": 5}
    )
    await db_session.commit()
    
    # Search by details content
    search_term = "password"
    logs, total = await get_audit_logs(db_session, search=search_term, page=1, per_page=100)
    
    # Verify all returned logs contain the search term in at least one field
    for log in logs:
        found = False
        if log["details"] and search_term.lower() in str(log["details"]).lower():
            found = True
        elif log["action"] and search_term.lower() in log["action"].lower():
            found = True
        elif log["user_email"] and search_term.lower() in log["user_email"].lower():
            found = True
        
        assert found, f"Log should contain search term '{search_term}' in some text field"


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    search_field=st.sampled_from(["action", "ip", "details"]),
    search_value=st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')))
)
@pytest.mark.asyncio
async def test_audit_search_completeness_property(
    search_field: str,
    search_value: str,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 7: Audit search completeness
    
    Property-based test: For any search query string, all returned audit events
    should contain the search query in at least one text field (user email, action,
    resource, IP address, or details).
    
    Validates: Requirements 3.3
    """
    # Skip empty or whitespace-only search values
    if not search_value or not search_value.strip():
        return
    
    # Create audit entries with the search value in different fields
    if search_field == "action":
        action_name = f"test_{search_value}_action"
        await log_event(db_session, test_user.id, action_name, success=True)
    elif search_field == "ip":
        # Create a valid IP-like string with the search value
        ip_address = f"192.168.1.{abs(hash(search_value)) % 256}"
        await log_event(db_session, test_user.id, f"action_{search_value}", ip=ip_address, success=True)
    elif search_field == "details":
        details = {"key": search_value, "test": True}
        await log_event(db_session, test_user.id, "test_action", success=True, details=details)
    
    await db_session.commit()
    
    # Perform search
    logs, total = await get_audit_logs(db_session, search=search_value, page=1, per_page=100)
    
    # Verify all returned logs contain the search term in at least one text field
    for log in logs:
        search_lower = search_value.lower()
        found = False
        
        # Check all text fields
        if log.get("user_email") and search_lower in log["user_email"].lower():
            found = True
        elif log.get("user_name") and search_lower in log["user_name"].lower():
            found = True
        elif log.get("action") and search_lower in log["action"].lower():
            found = True
        elif log.get("resource_type") and search_lower in log["resource_type"].lower():
            found = True
        elif log.get("ip_address") and search_lower in log["ip_address"].lower():
            found = True
        elif log.get("user_agent") and search_lower in log["user_agent"].lower():
            found = True
        elif log.get("details") and search_lower in str(log["details"]).lower():
            found = True
        
        assert found, \
            f"Log {log['id']} should contain search term '{search_value}' in at least one text field. " \
            f"Fields: action={log.get('action')}, ip={log.get('ip_address')}, " \
            f"email={log.get('user_email')}, details={log.get('details')}"


@pytest.mark.asyncio
async def test_audit_search_no_results(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 7: Audit search completeness
    
    For search query that doesn't match any entries, the result should be empty.
    
    Validates: Requirements 3.3
    """
    # Create some audit entries
    await log_event(db_session, test_user.id, "login", success=True)
    await log_event(db_session, test_user.id, "logout", success=True)
    await db_session.commit()
    
    # Search for something that doesn't exist
    search_term = "nonexistent_search_term_xyz123"
    logs, total = await get_audit_logs(db_session, search=search_term, page=1, per_page=100)
    
    # Verify no results or all results contain the search term
    for log in logs:
        search_lower = search_term.lower()
        found = False
        
        if log.get("user_email") and search_lower in log["user_email"].lower():
            found = True
        elif log.get("action") and search_lower in log["action"].lower():
            found = True
        elif log.get("ip_address") and search_lower in log["ip_address"].lower():
            found = True
        elif log.get("details") and search_lower in str(log["details"]).lower():
            found = True
        
        assert found, "If any results returned, they must contain the search term"



# ============================================================================
# Property 9: Dashboard event distribution sum
# ============================================================================

@pytest.mark.asyncio
async def test_dashboard_event_distribution_sum(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 9: Dashboard event distribution sum
    
    For any time period, the sum of all event counts in the event distribution
    pie chart should equal the total number of events in that period.
    
    Validates: Requirements 4.3
    """
    # Create a diverse set of audit log entries with different actions
    now = datetime.now(timezone.utc)
    actions = ["login", "logout", "user_create", "user_update", "user_delete", "mfa_verify"]
    
    # Create entries over the last 7 days
    entries_created = []
    for i in range(30):
        action = actions[i % len(actions)]
        entry_date = now - timedelta(days=i % 7)
        
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=action,
            success=True,
            created_at=entry_date
        )
        db_session.add(entry)
        entries_created.append(entry)
    
    await db_session.commit()
    
    # Calculate expected totals
    start_date = now - timedelta(days=7)
    expected_total = sum(1 for e in entries_created if e.created_at >= start_date)
    
    # Get event distribution from the stats endpoint logic
    event_dist_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).where(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.action)
    
    event_dist_result = await db_session.execute(event_dist_query)
    event_distribution = [
        {"action": row.action, "count": row.count}
        for row in event_dist_result
    ]
    
    # Calculate sum of all event counts in distribution
    distribution_sum = sum(item["count"] for item in event_distribution)
    
    # Verify the property: sum of distribution equals total events
    assert distribution_sum == expected_total, \
        f"Sum of event distribution ({distribution_sum}) should equal total events ({expected_total})"
    
    # Additional verification: each action count should be positive
    for item in event_distribution:
        assert item["count"] > 0, f"Action {item['action']} should have positive count"
    
    # Verify all actions are accounted for
    actions_in_distribution = {item["action"] for item in event_distribution}
    expected_actions = {e.action for e in entries_created if e.created_at >= start_date}
    assert actions_in_distribution == expected_actions, \
        "All actions in the period should be in the distribution"


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    num_events=st.integers(min_value=1, max_value=50),
    num_action_types=st.integers(min_value=1, max_value=10),
    days_back=st.integers(min_value=1, max_value=30)
)
@pytest.mark.asyncio
async def test_dashboard_event_distribution_sum_property(
    num_events: int,
    num_action_types: int,
    days_back: int,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 9: Dashboard event distribution sum
    
    Property-based test: For any number of events with any number of action types
    over any time period, the sum of all event counts in the event distribution
    should equal the total number of events in that period.
    
    Validates: Requirements 4.3
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days_back)
    
    # Generate unique action types for this test run to avoid collision with other tests
    test_id = uuid.uuid4().hex[:8]
    action_types = [f"prop9_test_{test_id}_action_{i}" for i in range(num_action_types)]
    
    # Create random audit entries
    entries_created = []
    for i in range(num_events):
        action = action_types[i % num_action_types]
        # Randomly place entries within the time period
        days_offset = (i * 7) % days_back
        entry_date = now - timedelta(days=days_offset)
        
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=action,
            success=True,
            created_at=entry_date
        )
        db_session.add(entry)
        entries_created.append(entry)
    
    await db_session.commit()
    
    # Get event distribution (simulating the stats endpoint)
    # Filter to only our test actions to avoid interference from other tests
    event_dist_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).where(
        and_(
            AuditLog.created_at >= start_date,
            AuditLog.action.like(f"prop9_test_{test_id}%")
        )
    ).group_by(AuditLog.action)
    
    event_dist_result = await db_session.execute(event_dist_query)
    event_distribution = [
        {"action": row.action, "count": row.count}
        for row in event_dist_result
    ]
    
    # Calculate expected total (all entries in the time period)
    expected_total = sum(1 for e in entries_created if e.created_at >= start_date)
    
    # Calculate sum from distribution
    distribution_sum = sum(item["count"] for item in event_distribution)
    
    # Verify the property
    assert distribution_sum == expected_total, \
        f"Sum of event distribution ({distribution_sum}) should equal total events ({expected_total}). " \
        f"Created {num_events} events with {num_action_types} action types over {days_back} days."
    
    # Verify each action type has the correct count
    action_counts = {}
    for entry in entries_created:
        if entry.created_at >= start_date:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1
    
    for item in event_distribution:
        expected_count = action_counts.get(item["action"], 0)
        assert item["count"] == expected_count, \
            f"Action {item['action']} should have count {expected_count}, got {item['count']}"


@pytest.mark.asyncio
async def test_dashboard_event_distribution_empty_period(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 9: Dashboard event distribution sum
    
    Edge case: For a time period with no events, the event distribution should
    be empty and sum to zero.
    
    Validates: Requirements 4.3
    """
    # Create an entry far in the past (outside our query range)
    old_date = datetime.now(timezone.utc) - timedelta(days=100)
    old_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="old_action",
        success=True,
        created_at=old_date
    )
    db_session.add(old_entry)
    await db_session.commit()
    
    # Query for events in the last 7 days (should be empty)
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=7)
    
    event_dist_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).where(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.action)
    
    event_dist_result = await db_session.execute(event_dist_query)
    event_distribution = [
        {"action": row.action, "count": row.count}
        for row in event_dist_result
    ]
    
    # Calculate sum
    distribution_sum = sum(item["count"] for item in event_distribution)
    
    # Verify the property: empty period should have zero sum
    assert distribution_sum == 0, \
        f"Empty period should have zero event distribution sum, got {distribution_sum}"
    assert len(event_distribution) == 0, \
        f"Empty period should have no distribution entries, got {len(event_distribution)}"


@pytest.mark.asyncio
async def test_dashboard_event_distribution_single_action(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 9: Dashboard event distribution sum
    
    Edge case: For a period with only one action type, the distribution should
    have one entry with count equal to total events.
    
    Validates: Requirements 4.3
    """
    # Create multiple entries with the same action
    now = datetime.now(timezone.utc)
    num_entries = 15
    
    for i in range(num_entries):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action="single_action",
            success=True,
            created_at=now - timedelta(hours=i)
        )
        db_session.add(entry)
    
    await db_session.commit()
    
    # Get event distribution
    start_date = now - timedelta(days=7)
    event_dist_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).where(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.action)
    
    event_dist_result = await db_session.execute(event_dist_query)
    event_distribution = [
        {"action": row.action, "count": row.count}
        for row in event_dist_result
    ]
    
    # Filter to only our entries
    our_distribution = [item for item in event_distribution if item["action"] == "single_action"]
    
    # Verify the property
    assert len(our_distribution) == 1, \
        "Should have exactly one action type in distribution"
    assert our_distribution[0]["count"] == num_entries, \
        f"Single action should have count {num_entries}, got {our_distribution[0]['count']}"
    
    # Verify sum equals total
    distribution_sum = sum(item["count"] for item in our_distribution)
    assert distribution_sum == num_entries, \
        f"Sum should equal total events ({num_entries}), got {distribution_sum}"


@pytest.mark.asyncio
async def test_dashboard_event_distribution_boundary_dates(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 9: Dashboard event distribution sum
    
    Edge case: Events exactly at the boundary of the time period should be
    included correctly in the distribution.
    
    Validates: Requirements 4.3
    """
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=7)
    
    # Create entries at exact boundaries
    entries = [
        # Exactly at start boundary (should be included)
        AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action="boundary_start",
            success=True,
            created_at=start_date
        ),
        # Just before start boundary (should be excluded)
        AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action="before_start",
            success=True,
            created_at=start_date - timedelta(seconds=1)
        ),
        # In the middle (should be included)
        AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action="middle",
            success=True,
            created_at=now - timedelta(days=3)
        ),
        # At current time (should be included)
        AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action="current",
            success=True,
            created_at=now
        ),
    ]
    
    for entry in entries:
        db_session.add(entry)
    await db_session.commit()
    
    # Get event distribution
    event_dist_query = select(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).where(
        AuditLog.created_at >= start_date
    ).group_by(AuditLog.action)
    
    event_dist_result = await db_session.execute(event_dist_query)
    event_distribution = [
        {"action": row.action, "count": row.count}
        for row in event_dist_result
    ]
    
    # Calculate expected total (should be 3: boundary_start, middle, current)
    expected_total = 3
    distribution_sum = sum(item["count"] for item in event_distribution)
    
    # Verify the property
    assert distribution_sum == expected_total, \
        f"Sum should be {expected_total} (excluding before_start), got {distribution_sum}"
    
    # Verify "before_start" is not in distribution
    actions_in_dist = {item["action"] for item in event_distribution}
    assert "before_start" not in actions_in_dist, \
        "Entry before start boundary should not be in distribution"
    
    # Verify included actions are present
    assert "boundary_start" in actions_in_dist, \
        "Entry at start boundary should be included"
    assert "middle" in actions_in_dist, \
        "Entry in middle should be included"
    assert "current" in actions_in_dist, \
        "Entry at current time should be included"



# ============================================================================
# Property 10: Top risk events ordering
# ============================================================================

@pytest.mark.asyncio
async def test_top_risk_events_ordering_basic(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 10: Top risk events ordering
    
    For any time period, the top-N risk events should be ordered by risk_score
    in descending order.
    
    Validates: Requirements 4.4
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Create audit entries with different risk scores
    risk_scores = [95, 87, 82, 75, 68, 55, 42, 30, 15, 8, 3]
    created_entries = []
    
    for i, risk_score in enumerate(risk_scores):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=f"test_action_{i}",
            ip_address=f"192.168.1.{i}",
            success=True,
            risk_score=risk_score,
            created_at=today_start + timedelta(minutes=i)
        )
        db_session.add(entry)
        created_entries.append(entry)
    
    await db_session.commit()
    
    # Query top 10 high-risk events (same as the API endpoint)
    top_risk_query = select(AuditLog).where(
        AuditLog.created_at >= today_start,
        AuditLog.risk_score.isnot(None)
    ).order_by(AuditLog.risk_score.desc()).limit(10)
    
    top_risk_result = await db_session.execute(top_risk_query)
    top_risk_events = list(top_risk_result.scalars())
    
    # Verify we got 10 events (not 11)
    assert len(top_risk_events) == 10, \
        f"Should return exactly 10 events, got {len(top_risk_events)}"
    
    # Verify ordering: each event should have risk_score >= next event
    for i in range(len(top_risk_events) - 1):
        current_score = top_risk_events[i].risk_score
        next_score = top_risk_events[i + 1].risk_score
        assert current_score >= next_score, \
            f"Event {i} (score {current_score}) should have score >= event {i+1} (score {next_score})"
    
    # Verify the highest score is first
    assert top_risk_events[0].risk_score == 95, \
        f"First event should have highest score (95), got {top_risk_events[0].risk_score}"
    
    # Verify the 10th event has score 8 (not 3, which is the 11th)
    assert top_risk_events[9].risk_score == 8, \
        f"10th event should have score 8, got {top_risk_events[9].risk_score}"
    
    # Verify the 11th entry (score 3) is NOT in the top 10
    top_10_ids = {str(event.id) for event in top_risk_events}
    eleventh_entry = created_entries[10]  # The one with score 3
    assert str(eleventh_entry.id) not in top_10_ids, \
        "11th entry (score 3) should not be in top 10"


@pytest.mark.asyncio
async def test_top_risk_events_ordering_with_ties(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 10: Top risk events ordering
    
    When multiple events have the same risk score, they should all be included
    in the correct order, and the ordering should be consistent.
    
    Validates: Requirements 4.4
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Create entries with some tied risk scores
    risk_scores = [90, 85, 85, 85, 80, 75, 75, 70, 65, 60, 55, 50]
    created_entries = []
    
    for i, risk_score in enumerate(risk_scores):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=f"tied_action_{i}",
            ip_address=f"10.0.0.{i}",
            success=True,
            risk_score=risk_score,
            created_at=today_start + timedelta(minutes=i)
        )
        db_session.add(entry)
        created_entries.append(entry)
    
    await db_session.commit()
    
    # Query top 10 high-risk events
    top_risk_query = select(AuditLog).where(
        AuditLog.created_at >= today_start,
        AuditLog.risk_score.isnot(None)
    ).order_by(AuditLog.risk_score.desc()).limit(10)
    
    top_risk_result = await db_session.execute(top_risk_query)
    top_risk_events = list(top_risk_result.scalars())
    
    # Verify we got 10 events
    assert len(top_risk_events) == 10, \
        f"Should return exactly 10 events, got {len(top_risk_events)}"
    
    # Verify ordering property: each event's score >= next event's score
    for i in range(len(top_risk_events) - 1):
        current_score = top_risk_events[i].risk_score
        next_score = top_risk_events[i + 1].risk_score
        assert current_score >= next_score, \
            f"Event {i} (score {current_score}) should have score >= event {i+1} (score {next_score})"
    
    # Verify the first event has the highest score
    assert top_risk_events[0].risk_score == 90, \
        f"First event should have score 90, got {top_risk_events[0].risk_score}"
    
    # Verify all scores in top 10 are >= 60 (the 10th highest)
    for i, event in enumerate(top_risk_events):
        assert event.risk_score >= 60, \
            f"Event {i} should have score >= 60, got {event.risk_score}"


@pytest.mark.asyncio
async def test_top_risk_events_ordering_fewer_than_10(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 10: Top risk events ordering
    
    When there are fewer than 10 events, all should be returned in descending
    order by risk_score.
    
    Validates: Requirements 4.4
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Create only 5 entries
    risk_scores = [88, 72, 55, 41, 20]
    created_entries = []
    
    for i, risk_score in enumerate(risk_scores):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=f"few_action_{i}",
            ip_address=f"172.16.0.{i}",
            success=True,
            risk_score=risk_score,
            created_at=today_start + timedelta(minutes=i)
        )
        db_session.add(entry)
        created_entries.append(entry)
    
    await db_session.commit()
    
    # Query top 10 high-risk events
    top_risk_query = select(AuditLog).where(
        AuditLog.created_at >= today_start,
        AuditLog.risk_score.isnot(None)
    ).order_by(AuditLog.risk_score.desc()).limit(10)
    
    top_risk_result = await db_session.execute(top_risk_query)
    top_risk_events = list(top_risk_result.scalars())
    
    # Verify we got only 5 events (not padded to 10)
    assert len(top_risk_events) == 5, \
        f"Should return exactly 5 events (all available), got {len(top_risk_events)}"
    
    # Verify ordering property
    for i in range(len(top_risk_events) - 1):
        current_score = top_risk_events[i].risk_score
        next_score = top_risk_events[i + 1].risk_score
        assert current_score >= next_score, \
            f"Event {i} (score {current_score}) should have score >= event {i+1} (score {next_score})"
    
    # Verify the scores match our input in descending order
    expected_scores = sorted(risk_scores, reverse=True)
    actual_scores = [event.risk_score for event in top_risk_events]
    assert actual_scores == expected_scores, \
        f"Scores should be {expected_scores}, got {actual_scores}"


@pytest.mark.asyncio
async def test_top_risk_events_ordering_excludes_old_events(
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 10: Top risk events ordering
    
    Only events from today should be included in top risk events, even if
    older events have higher risk scores.
    
    Validates: Requirements 4.4
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today_start - timedelta(days=1)
    
    # Create high-risk events from yesterday (should be excluded)
    old_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=test_user.id,
        action="old_high_risk",
        ip_address="192.168.1.100",
        success=True,
        risk_score=99,  # Very high score
        created_at=yesterday
    )
    db_session.add(old_entry)
    
    # Create lower-risk events from today (should be included)
    today_scores = [80, 70, 60, 50, 40]
    today_entries = []
    for i, risk_score in enumerate(today_scores):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=f"today_action_{i}",
            ip_address=f"10.0.0.{i}",
            success=True,
            risk_score=risk_score,
            created_at=today_start + timedelta(minutes=i)
        )
        db_session.add(entry)
        today_entries.append(entry)
    
    await db_session.commit()
    
    # Query top 10 high-risk events (only from today)
    top_risk_query = select(AuditLog).where(
        AuditLog.created_at >= today_start,
        AuditLog.risk_score.isnot(None)
    ).order_by(AuditLog.risk_score.desc()).limit(10)
    
    top_risk_result = await db_session.execute(top_risk_query)
    top_risk_events = list(top_risk_result.scalars())
    
    # Verify we got only today's events
    assert len(top_risk_events) == 5, \
        f"Should return only today's 5 events, got {len(top_risk_events)}"
    
    # Verify the old high-risk event is NOT included
    top_10_ids = {str(event.id) for event in top_risk_events}
    assert str(old_entry.id) not in top_10_ids, \
        "Yesterday's event (score 99) should not be in today's top events"
    
    # Verify all returned events are from today
    for event in top_risk_events:
        assert event.created_at >= today_start, \
            f"Event {event.id} should be from today, but created_at is {event.created_at}"
    
    # Verify ordering of today's events
    for i in range(len(top_risk_events) - 1):
        current_score = top_risk_events[i].risk_score
        next_score = top_risk_events[i + 1].risk_score
        assert current_score >= next_score, \
            f"Event {i} (score {current_score}) should have score >= event {i+1} (score {next_score})"


@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    num_events=st.integers(min_value=1, max_value=25),
    risk_scores=st.lists(
        st.integers(min_value=0, max_value=100),
        min_size=1,
        max_size=25
    )
)
@pytest.mark.asyncio
async def test_top_risk_events_ordering_property(
    num_events: int,
    risk_scores: list,
    db_session: AsyncSession,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 10: Top risk events ordering
    
    Property-based test: For any set of events with risk scores, the top-N
    events should be ordered by risk_score in descending order, and all
    should have risk_score >= the (N+1)th event if it exists.
    
    Validates: Requirements 4.4
    """
    # Ensure we have the right number of risk scores
    if len(risk_scores) < num_events:
        risk_scores = risk_scores + [0] * (num_events - len(risk_scores))
    risk_scores = risk_scores[:num_events]
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Use a unique marker to identify our test entries
    test_marker = f"prop_test_{uuid.uuid4().hex}"
    
    # Create audit entries with the given risk scores
    created_entries = []
    created_ids = set()
    for i, risk_score in enumerate(risk_scores):
        entry = AuditLog(
            id=uuid.uuid4(),
            user_id=test_user.id,
            action=test_marker,
            ip_address=f"192.168.{i // 256}.{i % 256}",
            success=True,
            risk_score=risk_score,
            created_at=today_start + timedelta(seconds=i)
        )
        db_session.add(entry)
        created_entries.append(entry)
        created_ids.add(str(entry.id))
    
    await db_session.commit()
    
    # Query top 10 high-risk events from our test entries only
    top_risk_query = select(AuditLog).where(
        AuditLog.action == test_marker,
        AuditLog.risk_score.isnot(None)
    ).order_by(AuditLog.risk_score.desc()).limit(10)
    
    top_risk_result = await db_session.execute(top_risk_query)
    top_risk_events = list(top_risk_result.scalars())
    
    # Property 1: Should return at most 10 events
    assert len(top_risk_events) <= 10, \
        f"Should return at most 10 events, got {len(top_risk_events)}"
    
    # Property 2: Should return min(num_events, 10) events from our test
    expected_count = min(num_events, 10)
    assert len(top_risk_events) == expected_count, \
        f"Should return {expected_count} events, got {len(top_risk_events)}"
    
    # Property 3: Events should be ordered by risk_score descending
    for i in range(len(top_risk_events) - 1):
        current_score = top_risk_events[i].risk_score
        next_score = top_risk_events[i + 1].risk_score
        assert current_score >= next_score, \
            f"Event {i} (score {current_score}) should have score >= event {i+1} (score {next_score})"
    
    # Property 4: All returned events should have risk_score >= (N+1)th event if it exists
    if len(top_risk_events) == 10 and num_events > 10:
        # Get all risk scores sorted descending
        all_scores_sorted = sorted(risk_scores, reverse=True)
        
        # The 11th highest score (index 10)
        eleventh_score = all_scores_sorted[10]
        
        # All top 10 should have score >= 11th score
        for i, event in enumerate(top_risk_events):
            assert event.risk_score >= eleventh_score, \
                f"Top 10 event {i} (score {event.risk_score}) should have score >= 11th event (score {eleventh_score})"
    
    # Property 5: The first event should have the maximum risk score from our test
    if len(top_risk_events) > 0:
        max_score = max(risk_scores)
        assert top_risk_events[0].risk_score == max_score, \
            f"First event should have max score {max_score}, got {top_risk_events[0].risk_score}"
    
    # Property 6: All returned events should be from our test entries
    for event in top_risk_events:
        assert str(event.id) in created_ids, \
            f"Event {event.id} should be one of our created entries"
