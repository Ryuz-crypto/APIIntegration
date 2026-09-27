"""Add local users and revocable sessions.

Revision ID: 20260927_0007
Revises: 20260927_0006
"""

import sqlalchemy as sa
from alembic import op

revision = "20260927_0007"
down_revision = "20260927_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "user_accounts" not in tables:
        op.create_table(
            "user_accounts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("username", sa.String(80), nullable=False),
            sa.Column("display_name", sa.String(120), nullable=False, server_default=""),
            sa.Column("password_hash", sa.String(512), nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
        for name in ("id", "username", "role", "enabled"):
            op.create_index(f"ix_user_accounts_{name}", "user_accounts", [name])
    if "user_sessions" not in tables:
        op.create_table(
            "user_sessions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        for name in ("id", "user_id", "token_hash", "expires_at", "revoked_at"):
            op.create_index(f"ix_user_sessions_{name}", "user_sessions", [name])


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "user_sessions" in tables:
        op.drop_table("user_sessions")
    if "user_accounts" in tables:
        op.drop_table("user_accounts")
