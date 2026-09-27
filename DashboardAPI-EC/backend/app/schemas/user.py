from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=12, max_length=200)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str | None = Field(default=None, max_length=160)
    password: str = Field(min_length=12, max_length=200)
    role: str = Field(default="viewer", pattern=r"^(viewer|operator|admin)$")


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    password: str | None = Field(default=None, min_length=12, max_length=200)
    role: str | None = Field(default=None, pattern=r"^(viewer|operator|admin)$")
    enabled: bool | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=12, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: str | None
    role: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class Identity(BaseModel):
    id: str
    username: str
    full_name: str | None
    role: str
    enabled: bool
    expires_at: datetime | None = None


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead
