import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["viewer", "operator", "admin"]


class AuthStatus(BaseModel):
    users_configured: bool
    version: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class BootstrapRequest(LoginRequest):
    display_name: str = Field(default="", max_length=120)
    admin_token: str = Field(min_length=1)


class UserCreate(LoginRequest):
    display_name: str = Field(default="", max_length=120)
    role: Role = "viewer"


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: Role | None = None
    enabled: bool | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    role: Role
    enabled: bool
    created_at: datetime
    last_login_at: datetime | None


class SessionRead(BaseModel):
    token: str
    expires_at: datetime
    user: UserRead


class AuditRead(BaseModel):
    id: uuid.UUID
    actor: str
    action: str
    resource_type: str
    resource_id: str | None
    details: dict
    created_at: datetime
