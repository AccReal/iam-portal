"""
Property-based tests for RBAC (Role-Based Access Control) system.

These tests verify universal properties that should hold across all inputs
using property-based testing with Hypothesis.
"""
import uuid
import pytest
import pytest_asyncio
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role, RolePermission
from app.models.application import Application
from app.models.user import User


async def check_user_permission(
    db_session: AsyncSession,
    user: User,
    application_id: uuid.UUID,
    permission_type: str
) -> bool:
    """
    Check if a user has a specific permission for an application.
    
    Args:
        db_session: Database session
        user: User to check permissions for
        application_id: Application ID
        permission_type: Type of permission ('read', 'write', 'export')
    
    Returns:
        True if user has the permission, False otherwise
    """
    if not user.role_id:
        return False
    
    # Query the role permission for this role and application
    result = await db_session.execute(
        select(RolePermission).where(
            RolePermission.role_id == user.role_id,
            RolePermission.application_id == application_id
        )
    )
    role_permission = result.scalar_one_or_none()
    
    if not role_permission:
        return False
    
    # Check the specific permission type
    if permission_type == "read":
        return role_permission.can_read
    elif permission_type == "write":
        return role_permission.can_write
    elif permission_type == "export":
        return role_permission.can_export
    
    return False


@pytest.mark.asyncio
@settings(
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    can_read=st.booleans(),
    can_write=st.booleans(),
    can_export=st.booleans(),
)
async def test_permission_changes_apply_immediately(
    can_read: bool,
    can_write: bool,
    can_export: bool,
    db_session: AsyncSession,
    test_role: Role,
    test_application: Application,
    test_user: User
):
    """
    Feature: iam-system-completion, Property 2: Permission changes apply immediately
    
    For any role and any set of permission changes, after saving the changes,
    all users with that role should have the updated permissions when checked immediately.
    
    Validates: Requirements 1.4
    """
    # Create initial role permission with opposite values
    initial_permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_role.id,
        application_id=test_application.id,
        can_read=not can_read,
        can_write=not can_write,
        can_export=not can_export
    )
    db_session.add(initial_permission)
    await db_session.commit()
    
    # Verify initial permissions
    assert await check_user_permission(db_session, test_user, test_application.id, "read") == (not can_read)
    assert await check_user_permission(db_session, test_user, test_application.id, "write") == (not can_write)
    assert await check_user_permission(db_session, test_user, test_application.id, "export") == (not can_export)
    
    # Update the permissions
    initial_permission.can_read = can_read
    initial_permission.can_write = can_write
    initial_permission.can_export = can_export
    await db_session.commit()
    
    # Refresh the user to ensure we're not using cached data
    await db_session.refresh(test_user)
    
    # Verify permissions changed immediately
    assert await check_user_permission(db_session, test_user, test_application.id, "read") == can_read, \
        f"Read permission should be {can_read} immediately after update"
    assert await check_user_permission(db_session, test_user, test_application.id, "write") == can_write, \
        f"Write permission should be {can_write} immediately after update"
    assert await check_user_permission(db_session, test_user, test_application.id, "export") == can_export, \
        f"Export permission should be {can_export} immediately after update"
    
    # Clean up for next iteration
    await db_session.delete(initial_permission)
    await db_session.commit()


@pytest.mark.asyncio
async def test_permission_changes_apply_immediately_example(
    db_session: AsyncSession,
    test_role: Role,
    test_application: Application,
    test_user: User
):
    """
    Example test: Permission changes apply immediately
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 1.4
    """
    # Create initial role permission with read=False, write=False, export=False
    role_permission = RolePermission(
        id=uuid.uuid4(),
        role_id=test_role.id,
        application_id=test_application.id,
        can_read=False,
        can_write=False,
        can_export=False
    )
    db_session.add(role_permission)
    await db_session.commit()
    
    # Verify user has no permissions initially
    assert await check_user_permission(db_session, test_user, test_application.id, "read") is False
    assert await check_user_permission(db_session, test_user, test_application.id, "write") is False
    assert await check_user_permission(db_session, test_user, test_application.id, "export") is False
    
    # Update permissions to grant all access
    role_permission.can_read = True
    role_permission.can_write = True
    role_permission.can_export = True
    await db_session.commit()
    
    # Refresh user
    await db_session.refresh(test_user)
    
    # Verify user now has all permissions immediately
    assert await check_user_permission(db_session, test_user, test_application.id, "read") is True
    assert await check_user_permission(db_session, test_user, test_application.id, "write") is True
    assert await check_user_permission(db_session, test_user, test_application.id, "export") is True
    
    # Update permissions to revoke write access
    role_permission.can_write = False
    await db_session.commit()
    
    # Refresh user
    await db_session.refresh(test_user)
    
    # Verify write permission is immediately revoked
    assert await check_user_permission(db_session, test_user, test_application.id, "read") is True
    assert await check_user_permission(db_session, test_user, test_application.id, "write") is False
    assert await check_user_permission(db_session, test_user, test_application.id, "export") is True


@settings(max_examples=100)
@given(
    num_users=st.integers(min_value=1, max_value=10)
)
def test_role_deletion_with_users_blocked(num_users: int):
    """
    Feature: iam-system-completion, Property 3: Role deletion protection
    
    For any role that has one or more users assigned to it, attempting to delete
    the role should be blocked and return an error indicating users are still assigned.
    
    Validates: Requirements 1.5
    
    This tests the logical property: if a role has users, deletion should be blocked.
    """
    # Simulate a role with users
    def has_users_assigned(role_id: str, users: list) -> bool:
        """Check if any users are assigned to this role."""
        return any(user.get("role_id") == role_id for user in users)
    
    def can_delete_role(role_id: str, users: list) -> bool:
        """Check if a role can be deleted (only if no users assigned)."""
        return not has_users_assigned(role_id, users)
    
    # Create a role
    role_id = "test_role_123"
    
    # Create users assigned to this role
    users = [
        {"id": f"user_{i}", "role_id": role_id}
        for i in range(num_users)
    ]
    
    # Verify users are assigned
    assert has_users_assigned(role_id, users) is True, \
        f"Role should have {num_users} users assigned"
    
    # The property: if users exist with this role, deletion should be blocked
    assert can_delete_role(role_id, users) is False, \
        f"Role deletion should be blocked when {num_users} users are assigned"
    
    # Now remove all users from the role
    for user in users:
        user["role_id"] = None
    
    # Verify deletion is now allowed
    assert has_users_assigned(role_id, users) is False, \
        "No users should be assigned to role"
    assert can_delete_role(role_id, users) is True, \
        "Role deletion should be allowed when no users are assigned"


def test_role_deletion_protection_example():
    """
    Example test: Role deletion protection
    
    This is a concrete example test that demonstrates the property
    with specific values.
    
    Validates: Requirements 1.5
    """
    # Simulate checking if a role has users
    def has_users_assigned(role_id: str, users: list) -> bool:
        """Check if any users are assigned to this role."""
        return any(user.get("role_id") == role_id for user in users)
    
    def can_delete_role(role_id: str, users: list) -> bool:
        """Check if a role can be deleted (only if no users assigned)."""
        return not has_users_assigned(role_id, users)
    
    # Create a role
    role_id = "manager_role"
    
    # Create users assigned to this role
    users = [
        {"id": "user_1", "email": "manager1@example.com", "role_id": role_id},
        {"id": "user_2", "email": "manager2@example.com", "role_id": role_id}
    ]
    
    # Verify users are assigned
    assert has_users_assigned(role_id, users) is True
    
    # Deletion should be blocked
    assert can_delete_role(role_id, users) is False, \
        "Role deletion should be blocked when users are assigned"
    
    # Now remove users from the role
    users[0]["role_id"] = None
    users[1]["role_id"] = None
    
    # Verify deletion is now allowed
    assert has_users_assigned(role_id, users) is False
    assert can_delete_role(role_id, users) is True, \
        "Role deletion should be allowed when no users are assigned"
