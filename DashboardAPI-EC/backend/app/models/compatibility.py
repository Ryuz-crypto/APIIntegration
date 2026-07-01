from datetime import UTC, datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class ApiCompatibilityProfile(SQLModel, table=True):
    version: str = Field(primary_key=True, max_length=40)
    status: str = Field(default="supported", index=True)
    source: str = Field(default="builtin", max_length=80)
    profile: dict = Field(default_factory=dict, sa_column=Column(JSON().with_variant(JSONB(), "postgresql")))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
