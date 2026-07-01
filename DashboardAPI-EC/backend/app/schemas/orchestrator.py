import uuid

from pydantic import BaseModel, HttpUrl


class OrchestratorCreate(BaseModel):
    name: str
    base_url: HttpUrl
    credential_label: str | None = None
    auth_type: str = "none"
    username: str | None = None
    password: str | None = None
    api_token: str | None = None
    api_key_header: str | None = None
    verify_tls: bool = True
    timeout_seconds: int = 20


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
    auth_type: str
    username: str | None
    api_key_header: str | None
    verify_tls: bool
    timeout_seconds: int
    has_secret: bool

    model_config = {"from_attributes": True}


class OrchestratorValidationResult(BaseModel):
    orchestrator_id: uuid.UUID
    status: str
    detected_version: str | None
    compatibility_profile: str | None
    message: str
    status_code: int | None = None
    duration_ms: int | None = None
