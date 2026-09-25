import uuid

from pydantic import BaseModel, Field


class ApplianceCreate(BaseModel):
    orchestrator_id: uuid.UUID
    hostname: str
    serial_number: str | None = None
    ne_pk: str | None = None
    site: str | None = None
    model: str | None = None
    software_version: str | None = None
    selected_for_monitoring: bool = False


class ApplianceRead(BaseModel):
    id: uuid.UUID
    orchestrator_id: uuid.UUID
    hostname: str
    serial_number: str | None
    ne_pk: str | None
    site: str | None
    model: str | None
    software_version: str | None
    status: str
    selected_for_monitoring: bool
    polling_active_seconds: int
    polling_idle_seconds: int

    model_config = {"from_attributes": True}


class ApplianceMonitoringUpdate(BaseModel):
    enabled: bool
    active_seconds: int = Field(default=5, ge=5, le=3600)
    idle_seconds: int = Field(default=300, ge=30, le=86400)
