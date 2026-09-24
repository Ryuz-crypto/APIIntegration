import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class NetworkResource(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "orchestrator_id",
            "resource_type",
            "external_id",
            name="uq_networkresource_identity",
        ),
    )

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    orchestrator_id: uuid.UUID = Field(foreign_key="orchestrator.id", index=True)
    appliance_id: uuid.UUID | None = Field(default=None, foreign_key="appliance.id", index=True)
    resource_type: str = Field(index=True, max_length=60)
    external_id: str = Field(index=True, max_length=240)
    name: str = Field(max_length=240)
    status: str | None = Field(default=None, index=True, max_length=80)
    attributes: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    source_operation_id: str = Field(index=True, max_length=160)
    source_sample_id: uuid.UUID | None = Field(default=None, foreign_key="apisample.id", index=True)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False, index=True)


class MetricPoint(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    orchestrator_id: uuid.UUID = Field(foreign_key="orchestrator.id", index=True)
    appliance_id: uuid.UUID | None = Field(default=None, foreign_key="appliance.id", index=True)
    resource_id: uuid.UUID | None = Field(default=None, foreign_key="networkresource.id", index=True)
    namespace: str = Field(index=True, max_length=100)
    metric_name: str = Field(index=True, max_length=180)
    value: float
    unit: str | None = Field(default=None, max_length=40)
    dimensions: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    source_operation_id: str = Field(index=True, max_length=160)
    source_sample_id: uuid.UUID | None = Field(default=None, foreign_key="apisample.id", index=True)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False, index=True)
