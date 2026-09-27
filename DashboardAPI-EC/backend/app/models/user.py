import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin, new_uuid


class User(TimestampMixin, SQLModel, table=True):
    __tablename__ = "app_user"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=120)
    full_name: str | None = Field(default=None, max_length=160)
    password_hash: str = Field(nullable=False)
    role: str = Field(default="viewer", index=True, max_length=40)
    enabled: bool = Field(default=True, index=True)
    last_login_at: datetime | None = Field(default=None)


class UserSession(SQLModel, table=True):
    __tablename__ = "app_user_session"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="app_user.id", index=True, nullable=False)
    token_hash: str = Field(unique=True, index=True, max_length=64, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    expires_at: datetime = Field(nullable=False, index=True)
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
