import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, new_uuid


class Orchestrator(TimestampMixin, SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    name: str = Field(index=True, min_length=2, max_length=120)
    base_url: str = Field(max_length=500)
    deployment_type: str = Field(default="on_prem", index=True, max_length=40)
    tenant: str | None = Field(default=None, max_length=160)
    api_version: str | None = Field(default=None, index=True)
    swagger_version: str | None = Field(default=None, max_length=40)
    status: str = Field(default="pending", index=True)
    polling_enabled: bool = Field(default=False)
    polling_active_seconds: int = Field(default=120)
    polling_idle_seconds: int = Field(default=600)
    credential_label: str | None = Field(default=None, max_length=120)
    auth_type: str = Field(default="api_key", max_length=40)
    login_type: int = Field(default=0)
    username: str | None = Field(default=None, max_length=160)
    encrypted_password: str | None = Field(default=None)
    encrypted_api_token: str | None = Field(default=None)
    api_key_header: str | None = Field(default="X-Auth-Token", max_length=120)
    verify_tls: bool = Field(default=True)
    timeout_seconds: int = Field(default=20)
    capabilities: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB(), "postgresql")),
    )
    last_validated_at: datetime | None = Field(default=None)

    @property
    def has_secret(self) -> bool:
        return bool(self.encrypted_password or self.encrypted_api_token)
