import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator


class OrchestratorCreate(BaseModel):
    name: str
    base_url: HttpUrl
    deployment_type: str = "on_prem"
    tenant: str | None = None
    credential_label: str | None = None
    auth_type: str = "api_key"
    login_type: int = Field(default=0, ge=0, le=2)
    username: str | None = None
    password: str | None = None
    api_token: str | None = None
    api_key_header: str | None = "X-Auth-Token"
    verify_tls: bool = True
    timeout_seconds: int = 20

    @model_validator(mode="after")
    def validate_credentials(self):
        allowed = {"none", "api_key", "bearer", "basic", "session", "session_otp"}
        if self.auth_type not in allowed:
            raise ValueError(f"auth_type must be one of: {', '.join(sorted(allowed))}")
        if self.deployment_type not in {"on_prem", "oaas", "orchestrator_sp", "global_enterprise"}:
            raise ValueError("Unsupported deployment_type")
        if self.auth_type in {"api_key", "bearer"} and not self.api_token:
            raise ValueError("api_token is required for token authentication")
        if self.auth_type in {"basic", "session", "session_otp"} and not (self.username and self.password):
            raise ValueError("username and password are required for session authentication")
        return self


class OrchestratorRead(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    deployment_type: str
    tenant: str | None
    api_version: str | None
    swagger_version: str | None
    status: str
    polling_enabled: bool
    polling_active_seconds: int
    polling_idle_seconds: int
    credential_label: str | None
    auth_type: str
    login_type: int
    username: str | None
    api_key_header: str | None
    verify_tls: bool
    timeout_seconds: int
    has_secret: bool
    capabilities: dict
    last_validated_at: datetime | None
    credentials_updated_at: datetime | None

    model_config = {"from_attributes": True}


class OrchestratorValidationResult(BaseModel):
    orchestrator_id: uuid.UUID
    status: str
    detected_version: str | None
    compatibility_profile: str | None
    message: str
    status_code: int | None = None
    duration_ms: int | None = None
    capabilities: dict[str, bool] = {}


class OrchestratorValidationRequest(BaseModel):
    otp: str | None = Field(default=None, min_length=4, max_length=12)


class OrchestratorCredentialUpdate(BaseModel):
    credential_label: str | None = Field(default=None, max_length=120)
    auth_type: str
    login_type: int = Field(default=0, ge=0, le=2)
    username: str | None = Field(default=None, max_length=160)
    password: str | None = None
    api_token: str | None = None
    api_key_header: str | None = Field(default="X-Auth-Token", max_length=120)

    @model_validator(mode="after")
    def validate_method(self):
        allowed = {"none", "api_key", "bearer", "basic", "session", "session_otp"}
        if self.auth_type not in allowed:
            raise ValueError(f"auth_type must be one of: {', '.join(sorted(allowed))}")
        if self.auth_type in {"basic", "session", "session_otp"} and not self.username:
            raise ValueError("username is required for session authentication")
        return self


class OrchestratorCredentialStatus(BaseModel):
    orchestrator_id: uuid.UUID
    credential_label: str | None
    auth_type: str
    username: str | None
    api_key_header: str | None
    configured: bool
    encrypted_at_rest: bool = True
    supports_unattended_polling: bool
    updated_at: datetime | None


class OrchestratorCapabilityRead(BaseModel):
    operation_id: str
    available: bool
    source: str
    verified: bool = False
