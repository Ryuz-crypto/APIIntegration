import re

from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityEngine
from app.core.security import encrypt_secret
from app.models.orchestrator import Orchestrator
from app.schemas.orchestrator import OrchestratorCreate, OrchestratorValidationResult
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectClientError
from app.services.audit_service import record_event
from app.services.sample_service import record_error, record_success


def create_orchestrator(session: Session, payload: OrchestratorCreate) -> Orchestrator:
    orchestrator = Orchestrator(
        name=payload.name,
        base_url=str(payload.base_url).rstrip("/"),
        credential_label=payload.credential_label,
        auth_type=payload.auth_type,
        username=payload.username,
        encrypted_password=encrypt_secret(payload.password),
        encrypted_api_token=encrypt_secret(payload.api_token),
        api_key_header=payload.api_key_header,
        verify_tls=payload.verify_tls,
        timeout_seconds=payload.timeout_seconds,
    )
    session.add(orchestrator)
    session.flush()
    record_event(session, "orchestrator.created", "orchestrator", str(orchestrator.id))
    session.commit()
    session.refresh(orchestrator)
    return orchestrator


def list_orchestrators(session: Session) -> list[Orchestrator]:
    return list(session.exec(select(Orchestrator).order_by(Orchestrator.name)).all())


def validate_orchestrator(
    session: Session,
    orchestrator: Orchestrator,
    engine: CompatibilityEngine,
) -> OrchestratorValidationResult:
    client = EdgeConnectClient(orchestrator, engine)
    operation_id = "orchestrator.version"
    try:
        response = client.detect_version()
    except EdgeConnectClientError as exc:
        orchestrator.status = "connection_error"
        record_error(session, orchestrator.id, orchestrator.api_version, operation_id, exc)
        record_event(
            session,
            "orchestrator.validation_failed",
            "orchestrator",
            str(orchestrator.id),
            {"error": str(exc), "status_code": exc.status_code},
        )
        session.add(orchestrator)
        session.commit()
        session.refresh(orchestrator)
        return OrchestratorValidationResult(
            orchestrator_id=orchestrator.id,
            status=orchestrator.status,
            detected_version=orchestrator.api_version,
            compatibility_profile=orchestrator.api_version,
            message=str(exc),
            status_code=exc.status_code,
            duration_ms=exc.duration_ms,
        )

    detected = _extract_version(response.payload) or orchestrator.api_version or engine.versions[-1]
    if detected not in engine.versions:
        detected = orchestrator.api_version or engine.versions[-1]
    orchestrator.api_version = detected
    orchestrator.status = "validated"
    orchestrator.polling_enabled = True
    record_success(session, orchestrator.id, detected, response)
    record_event(
        session,
        "orchestrator.validated",
        "orchestrator",
        str(orchestrator.id),
        {"detected_version": detected, "status_code": response.status_code},
    )
    session.add(orchestrator)
    session.commit()
    session.refresh(orchestrator)
    return OrchestratorValidationResult(
        orchestrator_id=orchestrator.id,
        status=orchestrator.status,
        detected_version=detected,
        compatibility_profile=detected,
        message="Real EdgeConnect API response received and stored.",
        status_code=response.status_code,
        duration_ms=response.duration_ms,
    )


def _extract_version(payload: dict) -> str | None:
    text = " ".join(str(value) for value in payload.values())
    match = re.search(r"\b(9\.[3-6])\b", text)
    return match.group(1) if match else None
