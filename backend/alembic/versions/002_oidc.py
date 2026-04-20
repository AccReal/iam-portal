"""OIDC support: add department/locale to users, allowed_scopes to applications

Revision ID: 002_oidc
Revises: 001_initial
Create Date: 2026-04-19
"""
import sqlalchemy as sa
from alembic import op

revision = "002_oidc"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users: OIDC profile claims
    op.add_column("users", sa.Column("department", sa.String(100), nullable=True))
    op.add_column(
        "users",
        sa.Column("locale", sa.String(10), nullable=False, server_default="ru"),
    )

    # applications: allowed OIDC scopes per client
    op.add_column(
        "applications",
        sa.Column(
            "allowed_scopes",
            sa.String(500),
            nullable=True,
            server_default="openid profile email",
        ),
    )


def downgrade() -> None:
    op.drop_column("applications", "allowed_scopes")
    op.drop_column("users", "locale")
    op.drop_column("users", "department")
