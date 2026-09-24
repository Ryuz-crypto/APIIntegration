import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WidgetProvenance(BaseModel):
    sample_id: uuid.UUID | None = None
    operation_id: str
    method: str | None = None
    path: str | None = None
    collected_at: datetime | None = None


class DashboardWidget(BaseModel):
    id: str
    title: str
    description: str
    visualization: Literal["stat", "bars", "table", "timeseries", "status"]
    status: Literal["ready", "waiting", "unavailable"]
    reason: str | None = None
    value: int | float | str | None = None
    unit: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    required_operations: list[str] = Field(default_factory=list)
    provenance: WidgetProvenance | None = None


class DashboardSection(BaseModel):
    id: str
    title: str
    widgets: list[DashboardWidget]


class DashboardRead(BaseModel):
    orchestrator_id: uuid.UUID
    orchestrator_name: str
    api_version: str | None
    generated_at: datetime
    sections: list[DashboardSection]
