"""DashboardAPI-EC 1.0 stable schema baseline.

Revision ID: 20260923_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlmodel import SQLModel

import app.models  # noqa: F401

revision = "20260923_0001"
down_revision = None
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table)}
    if column.name not in columns:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)

    _add_column_if_missing("orchestrator", sa.Column("deployment_type", sa.String(40), nullable=False, server_default="on_prem"))
    _add_column_if_missing("orchestrator", sa.Column("tenant", sa.String(160), nullable=True))
    _add_column_if_missing("orchestrator", sa.Column("swagger_version", sa.String(40), nullable=True))
    _add_column_if_missing("orchestrator", sa.Column("login_type", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("orchestrator", sa.Column("capabilities", sa.JSON(), nullable=False, server_default="{}"))
    _add_column_if_missing("orchestrator", sa.Column("last_validated_at", sa.DateTime(), nullable=True))

    _add_column_if_missing("apicompatibilityprofile", sa.Column("checksum", sa.String(64), nullable=True))
    _add_column_if_missing("apicompatibilityprofile", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_column_if_missing("apicompatibilityprofile", sa.Column("raw_document", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    # The 1.0 baseline intentionally preserves operational data on downgrade.
    pass
