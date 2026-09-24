from sqlmodel import Session, select

import app.models  # noqa: F401
from app.compatibility.loader import document_checksum, load_builtin_profiles
from app.core.config import settings
from app.db.session import create_db_and_tables, engine
from app.models.compatibility import ApiCompatibilityProfile


def init_db() -> None:
    if settings.auto_create_schema:
        create_db_and_tables()
    with Session(engine) as session:
        for profile in load_builtin_profiles():
            exists = session.exec(
                select(ApiCompatibilityProfile).where(ApiCompatibilityProfile.version == profile["version"])
            ).first()
            if exists and exists.source != "builtin":
                continue
            item = exists or ApiCompatibilityProfile(version=profile["version"])
            item.status = profile.get("status", "supported")
            item.source = "builtin"
            item.checksum = document_checksum(profile)
            item.is_active = True
            item.profile = profile
            session.add(item)
        session.commit()
