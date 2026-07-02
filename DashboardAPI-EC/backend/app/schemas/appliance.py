import uuid
from datetime import datetime

from pydantic import BaseModel


class ApplianceCreate(BaseModel):
    orchestrator_id: uuid.UUID
    hostname: str
    serial_number: str | None = None
    site: str | None = None
    model: str | None = None
    software_version: str | None = None
    selected_for_monitoring: bool = False


class ApplianceRead(BaseModel):
    id: uuid.UUID
    orchestrator_id: uuid.UUID
    hostname: str
    serial_number: str | None
    site: str | None
    model: str | None
    software_version: str | None
    status: str
    selected_for_monitoring: bool
    polling_active_seconds: int
    polling_idle_seconds: int
    last_metrics: dict
    last_collected_at: datetime | None
    last_status_code: int | None
    last_latency_ms: int | None

    model_config = {"from_attributes": True}
