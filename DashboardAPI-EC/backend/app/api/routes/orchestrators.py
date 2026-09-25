import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.db.session import get_session
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceRead
from app.schemas.orchestrator import (
    OrchestratorCapabilityRead,
    OrchestratorCreate,
    OrchestratorCredentialStatus,
    OrchestratorCredentialUpdate,
    OrchestratorRead,
    OrchestratorValidationRequest,
    OrchestratorValidationResult,
)
from app.services import interactive_auth
from app.services.appliance_service import discover_appliances
from app.services.compatibility_service import build_compatibility_engine
from app.services.edgeconnect_client import EdgeConnectClientError
from app.services.orchestrator_service import (
    create_orchestrator,
    credential_status,
    list_orchestrators,
    update_credentials,
    validate_orchestrator,
)

router = APIRouter()


class OtpChallenge(BaseModel):
    challenge_id: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class OtpComplete(OtpChallenge):
    otp: str = Field(min_length=4, max_length=12, pattern=r"^[0-9]+$")


def mfa_orchestrator(session, orchestrator_id):
    item = session.get(Orchestrator, orchestrator_id)
    if item is None:
        raise HTTPException(404, "Orchestrator not found")
    if item.auth_type != "session_otp":
        raise HTTPException(409, "Selecciona el método Sesión interactiva con OTP.")
    return item


def auth_error(exc):
    if isinstance(exc, interactive_auth.InteractiveAuthError):
        return HTTPException(409, str(exc))
    if isinstance(exc, EdgeConnectClientError):
        return HTTPException(502, str(exc))
    return HTTPException(
        502,
        "No fue posible establecer la conexión HTTPS con el Orchestrator. Revisa URL, TLS y conectividad.",
    )


@router.post("/{orchestrator_id}/auth/start")
def start_auth(orchestrator_id: uuid.UUID, session: Session = Depends(get_session)):
    item = mfa_orchestrator(session, orchestrator_id)
    try:
        return interactive_auth.start(item, build_compatibility_engine(session))
    except (interactive_auth.InteractiveAuthError, EdgeConnectClientError, httpx.HTTPError) as exc:
        raise auth_error(exc) from None


@router.post("/{orchestrator_id}/auth/complete", response_model=OrchestratorValidationResult)
def complete_auth(
    orchestrator_id: uuid.UUID, payload: OtpComplete, session: Session = Depends(get_session)
):
    item = mfa_orchestrator(session, orchestrator_id)
    engine = build_compatibility_engine(session)
    try:
        interactive_auth.complete(item, engine, payload.challenge_id, payload.otp)
        return validate_orchestrator(session, item, engine)
    except (interactive_auth.InteractiveAuthError, EdgeConnectClientError, httpx.HTTPError) as exc:
        raise auth_error(exc) from None


@router.post("/{orchestrator_id}/auth/cancel")
def cancel_auth(
    orchestrator_id: uuid.UUID, payload: OtpChallenge, session: Session = Depends(get_session)
):
    item = mfa_orchestrator(session, orchestrator_id)
    try:
        interactive_auth.cancel(item, payload.challenge_id)
    except interactive_auth.InteractiveAuthError as exc:
        raise auth_error(exc) from None
    return {"status": "cancelled"}


@router.get("", response_model=list[OrchestratorRead])
def list_items(session: Session = Depends(get_session)) -> list[Orchestrator]:
    return list_orchestrators(session)


@router.post("", response_model=OrchestratorRead, status_code=201)
def create_item(
    payload: OrchestratorCreate,
    session: Session = Depends(get_session),
) -> Orchestrator:
    return create_orchestrator(session, payload)


@router.get("/{orchestrator_id}/credential-status", response_model=OrchestratorCredentialStatus)
def get_credential_status(
    orchestrator_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> OrchestratorCredentialStatus:
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    return credential_status(orchestrator)


@router.put("/{orchestrator_id}/credentials", response_model=OrchestratorRead)
def put_credentials(
    orchestrator_id: uuid.UUID,
    payload: OrchestratorCredentialUpdate,
    session: Session = Depends(get_session),
) -> Orchestrator:
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    try:
        return update_credentials(session, orchestrator, payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    return validate_orchestrator(
        session, orchestrator, engine, otp=payload.otp if payload else None
    )


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
