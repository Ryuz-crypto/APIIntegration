import uuid
from datetime import datetime

from pydantic import BaseModel


class ApiSampleRead(BaseModel):
    id: uuid.UUID
    orchestrator_id: uuid.UUID
    appliance_id: uuid.UUID | None
    api_version: str | None
    operation_id: str
    method: str
    path: str
    status_code: int | None
    duration_ms: int | None
    ok: bool
    payload: dict
    request_params: dict
    extracted_values: dict
    transformations: list
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiCodeExamples(BaseModel):
    curl: str
    python: str
    javascript: str


class ApiTraceRead(ApiSampleRead):
    sanitized_payload: dict
    code_examples: ApiCodeExamples
