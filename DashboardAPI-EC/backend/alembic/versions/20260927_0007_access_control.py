"""Dashboard user accounts and sessions for RBAC access control.

Revision ID: 20260927_0007
Revises: 20260927_0006
"""
import sqlalchemy as sa

from alembic import op

revision = "20260927_0007"
down_revision = "20260927_0006"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()

    if "app_user" not in tables:
        op.create_table(
            "app_user",
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("username", sa.String(120), nullable=False),
            sa.Column("full_name", sa.String(160), nullable=True),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("role", sa.String(40), nullable=False, server_default="viewer"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("username"),
        )
        for name in ("id", "username", "role", "enabled"):
            op.create_index(f"ix_app_user_{name}", "app_user", [name])

    if "app_user_session" not in tables:
        op.create_table(
            "app_user_session",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["app_user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        for name in ("id", "user_id", "token_hash", "expires_at"):
            op.create_index(f"ix_app_user_session_{name}", "app_user_session", [name])


def downgrade() -> None:
    tables = _tables()
    if "app_user_session" in tables:
        op.drop_table("app_user_session")
    if "app_user" in tables:
        op.drop_table("app_user")
