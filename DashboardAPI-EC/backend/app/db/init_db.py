from sqlmodel import Session, select

import app.models  # noqa: F401
from app.compatibility.loader import load_builtin_profiles
from app.db.session import create_db_and_tables, engine
from app.models.compatibility import ApiCompatibilityProfile


def init_db() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        for profile in load_builtin_profiles():
            exists = session.exec(
                select(ApiCompatibilityProfile).where(ApiCompatibilityProfile.version == profile["version"])
            ).first()
            if exists:
                continue
            session.add(
                ApiCompatibilityProfile(
                    version=profile["version"],
                    status=profile.get("status", "supported"),
                    source="builtin",
                    profile=profile,
                )
            )
        session.commit()
