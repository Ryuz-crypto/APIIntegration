import json

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.compatibility.engine import CompatibilityEngine, CompatibilityError
from app.compatibility.loader import load_builtin_profiles, profile_from_openapi_document
from app.schemas.compatibility import (
    CompatibilityProfileRead,
    OperationResolveRequest,
    OperationResolveResponse,
    SwaggerLoadResult,
)

router = APIRouter()


@router.get("/profiles", response_model=list[CompatibilityProfileRead])
def list_profiles() -> list[CompatibilityProfileRead]:
    profiles = load_builtin_profiles()
    return [
        CompatibilityProfileRead(
            version=profile["version"],
            status=profile.get("status", "supported"),
            source="builtin",
            operations=sorted(profile.get("operations", {})),
        )
        for profile in profiles
    ]


@router.post("/resolve", response_model=OperationResolveResponse)
def resolve_operation(payload: OperationResolveRequest) -> OperationResolveResponse:
    engine = CompatibilityEngine(load_builtin_profiles())
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
async def upload_swagger(version: str, file: UploadFile = File(...)) -> SwaggerLoadResult:
    content = await file.read()
    try:
        document = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Swagger/OpenAPI document must be JSON") from exc

    profile = profile_from_openapi_document(document, version)
    return SwaggerLoadResult(
        version=profile["version"],
        status=profile["status"],
        operation_count=len(profile["operations"]),
        message="Profile draft generated. Persistence and diff approval are scheduled for phase 2.",
    )
