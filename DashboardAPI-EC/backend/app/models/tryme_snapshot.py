import uuid
from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class TryMeSnapshot(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    orchestrator_id: uuid.UUID = Field(foreign_key="orchestrator.id", index=True)
    sample_id: uuid.UUID = Field(foreign_key="apisample.id", index=True)
    name: str = Field(min_length=2, max_length=160, index=True)
    operation_id: str = Field(max_length=240, index=True)
    method: str = Field(max_length=12)
    path: str = Field(max_length=600)
    status_code: int | None = Field(default=None, index=True)
    request_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    response_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
