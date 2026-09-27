"""Persist global dashboard appearance settings.

Revision ID: 20260927_0005
Revises: 20260924_0004
"""

import sqlalchemy as sa
from alembic import op

revision = "20260927_0005"
down_revision = "20260924_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "systemsetting" not in inspector.get_table_names():
        op.create_table(
            "systemsetting",
            sa.Column("key", sa.String(80), primary_key=True, nullable=False),
            sa.Column("value", sa.JSON(), nullable=False),
        )


def downgrade() -> None:
    if "systemsetting" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("systemsetting")
