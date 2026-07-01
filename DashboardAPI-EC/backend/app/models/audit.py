import uuid
from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class AuditEvent(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    actor: str = Field(default="system", index=True, max_length=120)
    action: str = Field(index=True, max_length=160)
    resource_type: str = Field(index=True, max_length=80)
    resource_id: str | None = Field(default=None, max_length=160)
    ip_address: str | None = Field(default=None, max_length=80)
    duration_ms: int | None = None
    details: dict = Field(
        default_factory=dict,
        sa_column=Column("metadata", JSON().with_variant(JSONB(), "postgresql")),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
