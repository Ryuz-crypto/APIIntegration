import uuid

from pydantic import BaseModel, HttpUrl


class OrchestratorCreate(BaseModel):
    name: str
    base_url: HttpUrl
    credential_label: str | None = None


class OrchestratorRead(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    api_version: str | None
    status: str
    polling_enabled: bool
    polling_active_seconds: int
    polling_idle_seconds: int
    credential_label: str | None

    model_config = {"from_attributes": True}


class OrchestratorValidationResult(BaseModel):
    orchestrator_id: uuid.UUID
    status: str
    detected_version: str | None
    compatibility_profile: str | None
    message: str
