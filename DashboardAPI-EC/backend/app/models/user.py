import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

from app.models.base import new_uuid


class UserAccount(SQLModel, table=True):
    __tablename__ = "user_accounts"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    username: str = Field(unique=True, index=True, max_length=80)
    display_name: str = Field(default="", max_length=120)
    password_hash: str = Field(max_length=512)
    role: str = Field(default="viewer", index=True, max_length=20)
    enabled: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    last_login_at: datetime | None = Field(default=None, nullable=True)


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"

    id: uuid.UUID = Field(default_factory=new_uuid, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="user_accounts.id", index=True, ondelete="CASCADE")
    token_hash: str = Field(unique=True, index=True, max_length=64)
    expires_at: datetime = Field(index=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    revoked_at: datetime | None = Field(default=None, index=True, nullable=True)
