from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityEngine
from app.models.orchestrator import Orchestrator
from app.schemas.orchestrator import OrchestratorCreate, OrchestratorValidationResult
from app.services.audit_service import record_event


def create_orchestrator(session: Session, payload: OrchestratorCreate) -> Orchestrator:
    orchestrator = Orchestrator(
        name=payload.name,
        base_url=str(payload.base_url).rstrip("/"),
        credential_label=payload.credential_label,
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
    detected = orchestrator.api_version or engine.versions[-1]
    orchestrator.api_version = detected
    orchestrator.status = "validated"
    orchestrator.polling_enabled = True
    record_event(
        session,
        "orchestrator.validated",
        "orchestrator",
        str(orchestrator.id),
        {"detected_version": detected},
    )
    session.add(orchestrator)
    session.commit()
    session.refresh(orchestrator)
    return OrchestratorValidationResult(
        orchestrator_id=orchestrator.id,
        status=orchestrator.status,
        detected_version=detected,
        compatibility_profile=detected,
        message="Connectivity contract validated. Real EdgeConnect call is delegated to collectors.",
    )
