import uuid

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, new_uuid


class Orchestrator(TimestampMixin, SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    name: str = Field(index=True, min_length=2, max_length=120)
    base_url: str = Field(max_length=500)
    api_version: str | None = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)
    polling_enabled: bool = Field(default=False)
    polling_active_seconds: int = Field(default=120)
    polling_idle_seconds: int = Field(default=600)
    credential_label: str | None = Field(default=None, max_length=120)
