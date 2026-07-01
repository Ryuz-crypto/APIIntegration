import uuid
from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class ApiSample(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    orchestrator_id: uuid.UUID = Field(foreign_key="orchestrator.id", index=True)
    appliance_id: uuid.UUID | None = Field(default=None, foreign_key="appliance.id", index=True)
    api_version: str | None = Field(default=None, index=True, max_length=40)
    operation_id: str = Field(index=True, max_length=160)
    method: str = Field(max_length=12)
    path: str = Field(max_length=600)
    status_code: int | None = Field(default=None, index=True)
    duration_ms: int | None = None
    ok: bool = Field(default=False, index=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON().with_variant(JSONB(), "postgresql")))
    error: str | None = Field(default=None, max_length=800)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False, index=True)
