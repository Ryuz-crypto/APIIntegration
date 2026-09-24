import json

import yaml
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityError
from app.db.session import get_session
from app.models.compatibility import ApiCompatibilityProfile
from app.schemas.compatibility import (
    CompatibilityProfileRead,
    OperationResolveRequest,
    OperationResolveResponse,
    SwaggerLoadResult,
)
from app.services.compatibility_service import (
    activate_profile,
    build_compatibility_engine,
    load_active_profiles,
    store_openapi_profile,
)

router = APIRouter()


@router.get("/profiles", response_model=list[CompatibilityProfileRead])
def list_profiles(session: Session = Depends(get_session)) -> list[CompatibilityProfileRead]:
    stored = {item.version: item for item in session.exec(select(ApiCompatibilityProfile)).all()}
    profiles = load_active_profiles(session)
    results = []
    for profile in profiles:
        item = stored.get(profile["version"])
        uses_stored_profile = bool(item and item.is_active and item.profile == profile)
        results.append(
            CompatibilityProfileRead(
                version=profile["version"],
                status=profile.get("status", "supported"),
                source=item.source if uses_stored_profile else profile.get("source", "builtin"),
                operations=sorted(profile.get("operations", {})),
                checksum=item.checksum if uses_stored_profile else profile.get("checksum"),
                is_active=True,
            )
        )
    return results


@router.post("/resolve", response_model=OperationResolveResponse)
def resolve_operation(
    payload: OperationResolveRequest,
    session: Session = Depends(get_session),
) -> OperationResolveResponse:
    engine = build_compatibility_engine(session)
    try:
        resolved = engine.resolve(payload.version, payload.operation_id, payload.path_params)
    except CompatibilityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OperationResolveResponse(
        version=resolved.version,
        operation_id=resolved.operation_id,
        method=resolved.method,
        path=resolved.path,
        polling_hint_seconds=resolved.polling_hint_seconds,
        notes=list(resolved.notes),
    )


@router.post("/swagger", response_model=SwaggerLoadResult)
async def upload_swagger(
    version: str,
    activate: bool = False,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> SwaggerLoadResult:
    content = await file.read()
    try:
        document = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        try:
            document = yaml.safe_load(content.decode("utf-8"))
        except yaml.YAMLError as exc:
            raise HTTPException(status_code=400, detail="Swagger/OpenAPI document must be JSON or YAML") from exc

    try:
        item = store_openapi_profile(session, document, version, activate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SwaggerLoadResult(
        version=item.version,
        status=item.status,
        operation_count=len(item.profile["operations"]),
        message="OpenAPI profile stored and activated." if activate else "OpenAPI profile stored as a draft.",
        checksum=item.checksum or "",
        activated=item.is_active,
    )


@router.post("/profiles/{version}/activate", response_model=CompatibilityProfileRead)
def activate(version: str, session: Session = Depends(get_session)) -> CompatibilityProfileRead:
    item = activate_profile(session, version)
    if item is None:
        raise HTTPException(status_code=404, detail="Compatibility profile not found")
    return CompatibilityProfileRead(
        version=item.version,
        status=item.status,
        source=item.source,
        operations=sorted(item.profile.get("operations", {})),
        checksum=item.checksum,
        is_active=item.is_active,
    )
