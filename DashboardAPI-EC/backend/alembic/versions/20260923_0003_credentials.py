"""Track independent Orchestrator credential rotation.

Revision ID: 20260923_0003
Revises: 20260923_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20260923_0003"
down_revision = "20260923_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("orchestrator")}
    if "credentials_updated_at" not in columns:
        op.add_column("orchestrator", sa.Column("credentials_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("orchestrator")}
    if "credentials_updated_at" in columns:
        op.drop_column("orchestrator", "credentials_updated_at")
