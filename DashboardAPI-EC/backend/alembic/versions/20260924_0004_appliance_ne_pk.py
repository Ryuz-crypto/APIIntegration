"""Store the Orchestrator nePk identifier on each appliance.

Revision ID: 20260924_0004
Revises: 20260923_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "20260924_0004"
down_revision = "20260923_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("appliance")}
    if "ne_pk" not in columns:
        op.add_column(
            "appliance",
            sa.Column("ne_pk", sa.String(120), nullable=True),
        )
        op.create_index("ix_appliance_ne_pk", "appliance", ["ne_pk"])


def downgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("appliance")}
    if "ne_pk" in columns:
        op.drop_index("ix_appliance_ne_pk", table_name="appliance")
        op.drop_column("appliance", "ne_pk")
