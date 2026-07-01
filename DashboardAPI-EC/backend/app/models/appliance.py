import uuid

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, new_uuid


class Appliance(TimestampMixin, SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    orchestrator_id: uuid.UUID = Field(foreign_key="orchestrator.id", index=True)
    hostname: str = Field(index=True, max_length=160)
    serial_number: str | None = Field(default=None, index=True, max_length=120)
    site: str | None = Field(default=None, index=True, max_length=160)
    model: str | None = Field(default=None, max_length=120)
    software_version: str | None = Field(default=None, index=True, max_length=40)
    status: str = Field(default="discovered", index=True)
    selected_for_monitoring: bool = Field(default=False)
    polling_active_seconds: int = Field(default=5)
    polling_idle_seconds: int = Field(default=300)
