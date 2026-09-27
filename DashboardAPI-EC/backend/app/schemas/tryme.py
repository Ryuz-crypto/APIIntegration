import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TryMeParameter(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    location: str
    required: bool = False
    description: str = ""
    parameter_schema: dict[str, Any] = Field(
        default_factory=dict, alias="schema", serialization_alias="schema"
    )
    example: Any = None


class TryMeOperation(BaseModel):
    operation_id: str
    method: str
    path: str
    summary: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    parameters: list[TryMeParameter] = Field(default_factory=list)
    request_schema: dict[str, Any] = Field(default_factory=dict)
    request_example: Any = None
    mutating: bool


class TryMeCatalog(BaseModel):
    orchestrator_id: uuid.UUID
    version: str
    source: str
    title: str
    operations: list[TryMeOperation]


class TryMeExecuteRequest(BaseModel):
    orchestrator_id: uuid.UUID
    method: str = Field(pattern=r"^(GET|POST|PUT|PATCH|DELETE)$")
    path: str = Field(min_length=1, max_length=600)
    path_params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    confirmation: str = Field(default="", max_length=800)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        if not value.startswith("/") or "://" in value or ".." in value:
            raise ValueError("The path must be a relative API path")
        return value


class TryMeExecuteResult(BaseModel):
    sample_id: uuid.UUID
    ok: bool
    operation_id: str
    method: str
    path: str
    status_code: int | None
    duration_ms: int | None
    request: dict[str, Any]
    response: dict[str, Any]
    response_headers: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    executed_at: datetime


class SnapshotCreate(BaseModel):
    sample_id: uuid.UUID
    name: str = Field(min_length=2, max_length=160)


class SnapshotRead(BaseModel):
    id: uuid.UUID
    orchestrator_id: uuid.UUID
    sample_id: uuid.UUID
    name: str
    operation_id: str
    method: str
    path: str
    status_code: int | None
    request_data: dict
    response_data: dict
    created_at: datetime
