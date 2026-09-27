"""Persist immutable Try Me response snapshots.

Revision ID: 20260927_0006
Revises: 20260927_0005
"""

import sqlalchemy as sa
from alembic import op

revision = "20260927_0006"
down_revision = "20260927_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "trymesnapshot" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "trymesnapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("orchestrator_id", sa.Uuid(), nullable=False),
        sa.Column("sample_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("operation_id", sa.String(240), nullable=False),
        sa.Column("method", sa.String(12), nullable=False),
        sa.Column("path", sa.String(600), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("request_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("response_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["orchestrator_id"], ["orchestrator.id"]),
        sa.ForeignKeyConstraint(["sample_id"], ["apisample.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in (
        "id",
        "orchestrator_id",
        "sample_id",
        "name",
        "operation_id",
        "status_code",
        "created_at",
    ):
        op.create_index(f"ix_trymesnapshot_{name}", "trymesnapshot", [name])


def downgrade() -> None:
    if "trymesnapshot" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("trymesnapshot")
