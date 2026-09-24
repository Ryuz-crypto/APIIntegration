from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import (
    document_checksum,
    load_builtin_profiles,
    profile_from_openapi_document,
)
from app.models.compatibility import ApiCompatibilityProfile


def load_active_profiles(session: Session | None = None) -> list[dict]:
    profiles = {profile["version"]: profile for profile in load_builtin_profiles()}
    if session is not None:
        stored = session.exec(
            select(ApiCompatibilityProfile).where(ApiCompatibilityProfile.is_active)
        ).all()
        for item in stored:
            if item.profile:
                profiles[item.version] = item.profile
    return [profiles[version] for version in sorted(profiles)]


def build_compatibility_engine(session: Session | None = None) -> CompatibilityEngine:
    return CompatibilityEngine(load_active_profiles(session))


def store_openapi_profile(
    session: Session,
    document: dict,
    version: str,
    activate: bool = False,
) -> ApiCompatibilityProfile:
    profile = profile_from_openapi_document(document, version)
    checksum = document_checksum(document)
    existing = session.get(ApiCompatibilityProfile, version)
    item = existing or ApiCompatibilityProfile(version=version)
    item.status = "supported" if activate else "draft"
    item.source = "openapi-upload"
    item.checksum = checksum
    item.is_active = activate
    item.profile = {**profile, "status": item.status}
    item.raw_document = document
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def activate_profile(session: Session, version: str) -> ApiCompatibilityProfile | None:
    item = session.get(ApiCompatibilityProfile, version)
    if item is None:
        return None
    item.is_active = True
    item.status = "supported"
    item.profile = {**item.profile, "status": "supported"}
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
