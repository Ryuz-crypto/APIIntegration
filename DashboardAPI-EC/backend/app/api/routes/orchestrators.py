import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import load_builtin_profiles
from app.db.session import get_session
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceRead
from app.schemas.orchestrator import (
    OrchestratorConnectionPlan,
    OrchestratorCreate,
    OrchestratorRead,
    OrchestratorValidationResult,
    SUPPORTED_AUTH_TYPES,
)
from app.services.appliance_service import discover_appliances
from app.services.edgeconnect_client import EdgeConnectClientError
from app.services.orchestrator_service import (
    build_connection_plan,
    create_orchestrator,
    list_orchestrators,
    validate_orchestrator,
)

router = APIRouter()


@router.get("", response_model=list[OrchestratorRead])
def list_items(session: Session = Depends(get_session)) -> list[Orchestrator]:
    return list_orchestrators(session)


@router.get("/connection-plan", response_model=OrchestratorConnectionPlan)
def connection_plan(auth_type: str = "basic") -> OrchestratorConnectionPlan:
    normalized = auth_type.strip().lower()
    if normalized not in SUPPORTED_AUTH_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported auth_type")
    engine = CompatibilityEngine(load_builtin_profiles())
    return build_connection_plan(normalized, engine.versions)


@router.post("", response_model=OrchestratorRead, status_code=201)
def create_item(
    payload: OrchestratorCreate,
    session: Session = Depends(get_session),
) -> Orchestrator:
    return create_orchestrator(session, payload)


@router.post("/{orchestrator_id}/validate", response_model=OrchestratorValidationResult)
def validate_item(
    orchestrator_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> OrchestratorValidationResult:
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    engine = CompatibilityEngine(load_builtin_profiles())
    return validate_orchestrator(session, orchestrator, engine)


@router.post("/{orchestrator_id}/discover-appliances", response_model=list[ApplianceRead])
def discover_items(
    orchestrator_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    engine = CompatibilityEngine(load_builtin_profiles())
    try:
        return discover_appliances(session, orchestrator, engine)
    except EdgeConnectClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
