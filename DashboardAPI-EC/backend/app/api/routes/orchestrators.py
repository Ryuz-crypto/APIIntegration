import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceRead
from app.schemas.orchestrator import (
    OrchestratorCapabilityRead,
    OrchestratorCreate,
    OrchestratorRead,
    OrchestratorValidationRequest,
    OrchestratorValidationResult,
)
from app.services.appliance_service import discover_appliances
from app.services.compatibility_service import build_compatibility_engine
from app.services.edgeconnect_client import EdgeConnectClientError
from app.services.orchestrator_service import (
    create_orchestrator,
    list_orchestrators,
    validate_orchestrator,
)

router = APIRouter()


@router.get("", response_model=list[OrchestratorRead])
def list_items(session: Session = Depends(get_session)) -> list[Orchestrator]:
    return list_orchestrators(session)


@router.post("", response_model=OrchestratorRead, status_code=201)
def create_item(
    payload: OrchestratorCreate,
    session: Session = Depends(get_session),
) -> Orchestrator:
    return create_orchestrator(session, payload)


@router.post("/{orchestrator_id}/validate", response_model=OrchestratorValidationResult)
def validate_item(
    orchestrator_id: uuid.UUID,
    payload: OrchestratorValidationRequest | None = None,
    session: Session = Depends(get_session),
) -> OrchestratorValidationResult:
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    engine = build_compatibility_engine(session)
    return validate_orchestrator(session, orchestrator, engine, otp=payload.otp if payload else None)


@router.post("/{orchestrator_id}/discover-appliances", response_model=list[ApplianceRead])
def discover_items(
    orchestrator_id: uuid.UUID,
    session: Session = Depends(get_session),
):
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    engine = build_compatibility_engine(session)
    try:
        return discover_appliances(session, orchestrator, engine)
    except EdgeConnectClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{orchestrator_id}/capabilities", response_model=list[OrchestratorCapabilityRead])
def capabilities(
    orchestrator_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> list[OrchestratorCapabilityRead]:
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    operations = orchestrator.capabilities.get("operations", {})
    verified = set(orchestrator.capabilities.get("verified", []))
    source = orchestrator.capabilities.get("source", "unavailable")
    return [
        OrchestratorCapabilityRead(
            operation_id=operation_id,
            available=bool(available),
            source=source,
            verified=operation_id in verified,
        )
        for operation_id, available in sorted(operations.items())
    ]
