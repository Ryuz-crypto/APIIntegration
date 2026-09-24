"""Normalized resources, metrics, and API trace metadata.

Revision ID: 20260923_0002
Revises: 20260923_0001
"""

import sqlalchemy as sa
from alembic import op

revision = "20260923_0002"
down_revision = "20260923_0001"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in columns:
        op.add_column(table, column)


def upgrade() -> None:
    tables = _tables()
    if "networkresource" not in tables:
        op.create_table(
            "networkresource",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("orchestrator_id", sa.Uuid(), nullable=False),
            sa.Column("appliance_id", sa.Uuid(), nullable=True),
            sa.Column("resource_type", sa.String(60), nullable=False),
            sa.Column("external_id", sa.String(240), nullable=False),
            sa.Column("name", sa.String(240), nullable=False),
            sa.Column("status", sa.String(80), nullable=True),
            sa.Column("attributes", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("source_operation_id", sa.String(160), nullable=False),
            sa.Column("source_sample_id", sa.Uuid(), nullable=True),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["appliance_id"], ["appliance.id"]),
            sa.ForeignKeyConstraint(["orchestrator_id"], ["orchestrator.id"]),
            sa.ForeignKeyConstraint(["source_sample_id"], ["apisample.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "orchestrator_id",
                "resource_type",
                "external_id",
                name="uq_networkresource_identity",
            ),
        )
        for name in (
            "id",
            "orchestrator_id",
            "appliance_id",
            "resource_type",
            "external_id",
            "status",
            "source_operation_id",
            "source_sample_id",
            "observed_at",
        ):
            op.create_index(f"ix_networkresource_{name}", "networkresource", [name])

    if "metricpoint" not in tables:
        op.create_table(
            "metricpoint",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("orchestrator_id", sa.Uuid(), nullable=False),
            sa.Column("appliance_id", sa.Uuid(), nullable=True),
            sa.Column("resource_id", sa.Uuid(), nullable=True),
            sa.Column("namespace", sa.String(100), nullable=False),
            sa.Column("metric_name", sa.String(180), nullable=False),
            sa.Column("value", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(40), nullable=True),
            sa.Column("dimensions", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("source_operation_id", sa.String(160), nullable=False),
            sa.Column("source_sample_id", sa.Uuid(), nullable=True),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["appliance_id"], ["appliance.id"]),
            sa.ForeignKeyConstraint(["orchestrator_id"], ["orchestrator.id"]),
            sa.ForeignKeyConstraint(["resource_id"], ["networkresource.id"]),
            sa.ForeignKeyConstraint(["source_sample_id"], ["apisample.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        for name in (
            "id",
            "orchestrator_id",
            "appliance_id",
            "resource_id",
            "namespace",
            "metric_name",
            "source_operation_id",
            "source_sample_id",
            "observed_at",
        ):
            op.create_index(f"ix_metricpoint_{name}", "metricpoint", [name])

    _add_column_if_missing(
        "apisample", sa.Column("request_params", sa.JSON(), nullable=False, server_default="{}")
    )
    _add_column_if_missing(
        "apisample", sa.Column("extracted_values", sa.JSON(), nullable=False, server_default="{}")
    )
    _add_column_if_missing(
        "apisample", sa.Column("transformations", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade() -> None:
    for column in ("transformations", "extracted_values", "request_params"):
        if column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns("apisample")}:
            op.drop_column("apisample", column)
    if "metricpoint" in _tables():
        op.drop_table("metricpoint")
    if "networkresource" in _tables():
        op.drop_table("networkresource")
