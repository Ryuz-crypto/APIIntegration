import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

SUPPORTED_AUTH_TYPES = {"none", "basic", "bearer", "api_key"}
SUPPORTED_API_VERSIONS = {"9.3", "9.4", "9.5", "9.6", "9.7"}


class OrchestratorCreate(BaseModel):
    name: str
    base_url: HttpUrl
    api_version: str | None = None
    credential_label: str | None = None
    auth_type: str = "none"
    username: str | None = None
    password: str | None = None
    api_token: str | None = None
    api_key_header: str | None = None
    verify_tls: bool = True
    timeout_seconds: int = Field(default=20, ge=3, le=120)

    @field_validator("auth_type")
    @classmethod
    def normalize_auth_type(cls, value: str) -> str:
        auth_type = value.strip().lower()
        if auth_type not in SUPPORTED_AUTH_TYPES:
            raise ValueError("auth_type must be one of: none, basic, bearer, api_key")
        return auth_type

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        if value not in SUPPORTED_API_VERSIONS:
            raise ValueError("api_version must be one of: 9.3, 9.4, 9.5, 9.6, 9.7")
        return value

    @model_validator(mode="after")
    def validate_auth_parameters(self) -> "OrchestratorCreate":
        if self.auth_type == "basic" and not (self.username and self.password):
            raise ValueError("basic auth requires username and password")
        if self.auth_type == "bearer" and not self.api_token:
            raise ValueError("bearer auth requires api_token")
        if self.auth_type == "api_key":
            if not self.api_token:
                raise ValueError("api_key auth requires api_token")
            if not self.api_key_header:
                raise ValueError("api_key auth requires api_key_header")
        return self


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
    last_validated_at: datetime | None
    last_status_code: int | None
    last_latency_ms: int | None
    last_error: str | None

    model_config = {"from_attributes": True}


class OrchestratorValidationResult(BaseModel):
    orchestrator_id: uuid.UUID
    status: str
    detected_version: str | None
    compatibility_profile: str | None
    message: str
    status_code: int | None = None
    duration_ms: int | None = None


class OrchestratorConnectionRequirement(BaseModel):
    field: str
    label: str
    required: bool
    secret: bool = False


class OrchestratorConnectionPlan(BaseModel):
    auth_type: str
    required_fields: list[OrchestratorConnectionRequirement]
    supported_versions: list[str]
    validation_operation: str = "orchestrator.version"
    discovery_operation: str = "orchestrator.inventory.summary"
    metrics_operation: str = "appliance.performance"
