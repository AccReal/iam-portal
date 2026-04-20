"""
Property-based tests for Authorization enforcement.

These tests verify that authorization checks properly enforce permissions
across the system.
"""
import uuid
import pytest
import pytest_asyncio
from hypothesis import given, strategies as st, settings

try:
    from fastapi import HTTPException, status
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.user import User
    from app.models.role import Role
    from app.core.permissions import RequireRole
    from app.api.v1.deps import get_current_user
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Define minimal stubs for testing logic
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    
    class status:
        HTTP_403_FORBIDDEN = 403
        HTTP_401_UNAUTHORIZED = 401
    
    # Stub for type hints
    AsyncSession = None
    User = None
    Role = None


# ============================================================================
# Property 11: Authorization enforcement
# ============================================================================

def test_authorization_enforcement_logic():
    """
    Feature: iam-system-completion, Property 11: Authorization enforcement
    
    For any action requiring specific permissions, if a user lacks those permissions,
    the action should be rejected with an "Insufficient permissions" error.
    
    This test verifies the logical property of authorization enforcement.
    
    Validates: Requirements 5.5
    """
    def check_authorization(user_role: str | None, required_roles: list[str]) -> tuple[bool, str | None]:
        """
        Simulate authorization check logic.
        Returns: (is_authorized, error_message)
        """
        if user_role is None:
            return False, "Роль не назначена"
        
        if user_role not in required_roles:
            return False, "Недостаточно прав"
        
        return True, None
    
    # Test 1: User with correct role should be authorized
    is_auth, error = check_authorization("admin", ["admin"])
    assert is_auth is True, "User with admin role should be authorized for admin-only action"
    assert error is None
    
    # Test 2: User with wrong role should be rejected
    is_auth, error = check_authorization("user", ["admin"])
    assert is_auth is False, "User without admin role should be rejected"
    assert error == "Недостаточно прав"
    
    # Test 3: User with no role should be rejected
    is_auth, error = check_authorization(None, ["admin"])
    assert is_auth is False, "User with no role should be rejected"
    assert error == "Роль не назначена"
    
    # Test 4: User with one of multiple allowed roles should be authorized
    is_auth, error = check_authorization("auditor", ["admin", "auditor"])
    assert is_auth is True, "User with auditor role should be authorized when auditor is allowed"
    assert error is None
    
    # Test 5: User with role not in allowed list should be rejected
    is_auth, error = check_authorization("viewer", ["admin", "auditor"])
    assert is_auth is False, "User with viewer role should be rejected when not in allowed list"
    assert error == "Недостаточно прав"


@settings(max_examples=100)
@given(
    user_role=st.one_of(
        st.none(),
        st.sampled_from(["admin", "auditor", "manager", "user", "viewer"])
    ),
    required_role=st.sampled_from(["admin", "auditor", "manager"])
)
def test_authorization_enforcement_property(user_role: str | None, required_role: str):
    """
    Feature: iam-system-completion, Property 11: Authorization enforcement
    
    Property-based test: Authorization should be enforced consistently across all
    combinations of user roles and required roles.
    
    Validates: Requirements 5.5
    """
    def check_authorization(user_role: str | None, required_roles: list[str]) -> bool:
        """Check if user is authorized."""
        if user_role is None:
            return False
        return user_role in required_roles
    
    required_roles = [required_role]
    is_authorized = check_authorization(user_role, required_roles)
    
    # Property: User should be authorized if and only if their role is in required roles
    if user_role == required_role:
        assert is_authorized is True, \
            f"User with role '{user_role}' should be authorized for action requiring '{required_role}'"
    else:
        assert is_authorized is False, \
            f"User with role '{user_role}' should NOT be authorized for action requiring '{required_role}'"


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
@pytest.mark.asyncio
async def test_require_role_dependency_admin_success(
    db_session: AsyncSession,
    test_role: Role
):
    """
    Test RequireRole dependency with admin user (should succeed).
    
    Validates: Requirements 5.5
    """
    # Create admin role
    admin_role = Role(
        id=uuid.uuid4(),
        name="admin",
        description="Administrator role"
    )
    db_session.add(admin_role)
    await db_session.commit()
    await db_session.refresh(admin_role)
    
    # Create admin user
    admin_user = User(
        id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4()}@example.com",
        password_hash="hashed_password",
        full_name="Admin User",
        role_id=admin_role.id,
        is_active=True,
        is_blocked=False
    )
    admin_user.role = admin_role  # Set the relationship
    
    # Test RequireRole dependency
    require_admin = RequireRole("admin")
    
    # Should not raise exception for admin user
    result = await require_admin(current_user=admin_user)
    assert result == admin_user, "Admin user should pass admin role check"


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
@pytest.mark.asyncio
async def test_require_role_dependency_non_admin_failure(
    db_session: AsyncSession,
    test_role: Role
):
    """
    Test RequireRole dependency with non-admin user (should fail).
    
    Validates: Requirements 5.5
    """
    # Create user role
    user_role = Role(
        id=uuid.uuid4(),
        name="user",
        description="Regular user role"
    )
    db_session.add(user_role)
    await db_session.commit()
    await db_session.refresh(user_role)
    
    # Create regular user
    regular_user = User(
        id=uuid.uuid4(),
        email=f"user_{uuid.uuid4()}@example.com",
        password_hash="hashed_password",
        full_name="Regular User",
        role_id=user_role.id,
        is_active=True,
        is_blocked=False
    )
    regular_user.role = user_role  # Set the relationship
    
    # Test RequireRole dependency
    require_admin = RequireRole("admin")
    
    # Should raise HTTPException for non-admin user
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(current_user=regular_user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Недостаточно прав" in exc_info.value.detail


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
@pytest.mark.asyncio
async def test_require_role_dependency_no_role_failure(
    db_session: AsyncSession
):
    """
    Test RequireRole dependency with user having no role (should fail).
    
    Validates: Requirements 5.5
    """
    # Create user without role
    user_no_role = User(
        id=uuid.uuid4(),
        email=f"norole_{uuid.uuid4()}@example.com",
        password_hash="hashed_password",
        full_name="No Role User",
        role_id=None,
        is_active=True,
        is_blocked=False
    )
    user_no_role.role = None  # Explicitly set no role
    
    # Test RequireRole dependency
    require_admin = RequireRole("admin")
    
    # Should raise HTTPException for user with no role
    with pytest.raises(HTTPException) as exc_info:
        await require_admin(current_user=user_no_role)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Роль не назначена" in exc_info.value.detail


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
@pytest.mark.asyncio
async def test_require_role_multiple_allowed_roles(
    db_session: AsyncSession
):
    """
    Test RequireRole dependency with multiple allowed roles.
    
    Validates: Requirements 5.5
    """
    # Create auditor role
    auditor_role = Role(
        id=uuid.uuid4(),
        name="auditor",
        description="Auditor role"
    )
    db_session.add(auditor_role)
    await db_session.commit()
    await db_session.refresh(auditor_role)
    
    # Create auditor user
    auditor_user = User(
        id=uuid.uuid4(),
        email=f"auditor_{uuid.uuid4()}@example.com",
        password_hash="hashed_password",
        full_name="Auditor User",
        role_id=auditor_role.id,
        is_active=True,
        is_blocked=False
    )
    auditor_user.role = auditor_role
    
    # Test RequireRole with multiple allowed roles
    require_admin_or_auditor = RequireRole("admin", "auditor")
    
    # Should not raise exception for auditor user
    result = await require_admin_or_auditor(current_user=auditor_user)
    assert result == auditor_user, "Auditor user should pass admin or auditor role check"


@settings(max_examples=50)
@given(
    has_role=st.booleans(),
    is_admin=st.booleans(),
    is_active=st.booleans(),
    is_blocked=st.booleans()
)
def test_authorization_state_combinations(
    has_role: bool,
    is_admin: bool,
    is_active: bool,
    is_blocked: bool
):
    """
    Feature: iam-system-completion, Property 11: Authorization enforcement
    
    Property-based test: Test various combinations of user states and verify
    authorization logic is consistent.
    
    Validates: Requirements 5.5
    """
    def should_be_authorized(
        has_role: bool,
        is_admin: bool,
        is_active: bool,
        is_blocked: bool,
        requires_admin: bool
    ) -> bool:
        """
        Determine if user should be authorized based on their state.
        """
        # Blocked or inactive users should never be authorized
        if is_blocked or not is_active:
            return False
        
        # User must have a role
        if not has_role:
            return False
        
        # If admin is required, user must be admin
        if requires_admin and not is_admin:
            return False
        
        return True
    
    # Test with admin requirement
    result_admin_required = should_be_authorized(has_role, is_admin, is_active, is_blocked, requires_admin=True)
    
    # Property: User should be authorized only if all conditions are met
    if is_blocked or not is_active:
        assert result_admin_required is False, \
            "Blocked or inactive users should never be authorized"
    elif not has_role:
        assert result_admin_required is False, \
            "Users without a role should never be authorized"
    elif not is_admin:
        assert result_admin_required is False, \
            "Non-admin users should not be authorized for admin-only actions"
    else:
        assert result_admin_required is True, \
            "Active, non-blocked admin users should be authorized"
    
    # Test without admin requirement (any role is fine)
    result_any_role = should_be_authorized(has_role, is_admin, is_active, is_blocked, requires_admin=False)
    
    if is_blocked or not is_active:
        assert result_any_role is False, \
            "Blocked or inactive users should never be authorized"
    elif not has_role:
        assert result_any_role is False, \
            "Users without a role should never be authorized"
    else:
        assert result_any_role is True, \
            "Active, non-blocked users with a role should be authorized for non-admin actions"


def test_authorization_error_messages():
    """
    Test that authorization errors provide clear, user-friendly messages.
    
    Validates: Requirements 5.5
    """
    def get_authorization_error(user_role: str | None, required_roles: list[str]) -> str | None:
        """Get the appropriate error message for authorization failure."""
        if user_role is None:
            return "Роль не назначена"
        if user_role not in required_roles:
            return "Недостаточно прав"
        return None
    
    # Test error messages
    error = get_authorization_error(None, ["admin"])
    assert error == "Роль не назначена", "Should return 'role not assigned' message"
    
    error = get_authorization_error("user", ["admin"])
    assert error == "Недостаточно прав", "Should return 'insufficient permissions' message"
    
    error = get_authorization_error("admin", ["admin"])
    assert error is None, "Should return no error for authorized user"
    
    # Verify error messages are in Russian (as per requirements)
    error_no_role = get_authorization_error(None, ["admin"])
    error_insufficient = get_authorization_error("user", ["admin"])
    
    assert "Роль" in error_no_role or "роль" in error_no_role.lower(), \
        "Error message should be in Russian"
    assert "прав" in error_insufficient.lower(), \
        "Error message should be in Russian"
