import re
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityEngine
from app.core.security import encrypt_secret
from app.models.orchestrator import Orchestrator
from app.schemas.orchestrator import OrchestratorCreate, OrchestratorValidationResult
from app.services.audit_service import record_event
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectClientError
from app.services.sample_service import record_error, record_success


def create_orchestrator(session: Session, payload: OrchestratorCreate) -> Orchestrator:
    orchestrator = Orchestrator(
        name=payload.name,
        base_url=str(payload.base_url).rstrip("/"),
        deployment_type=payload.deployment_type,
        tenant=payload.tenant,
        credential_label=payload.credential_label,
        auth_type=payload.auth_type,
        login_type=payload.login_type,
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
    otp: str | None = None,
) -> OrchestratorValidationResult:
    client = EdgeConnectClient(orchestrator, engine, otp=otp)
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
            capabilities={},
        )

    detected_raw = _extract_version(response.payload)
    detected = engine.match_version(detected_raw) if detected_raw else None
    if detected is None:
        orchestrator.status = "unsupported_version"
        session.add(orchestrator)
        record_event(
            session,
            "orchestrator.version_unsupported",
            "orchestrator",
            str(orchestrator.id),
            {"detected_version": detected_raw},
        )
        session.commit()
        return OrchestratorValidationResult(
            orchestrator_id=orchestrator.id,
            status=orchestrator.status,
            detected_version=detected_raw,
            compatibility_profile=None,
            message="Connection succeeded, but the EdgeConnect version is not supported.",
            status_code=response.status_code,
            duration_ms=response.duration_ms,
            capabilities={},
        )
    orchestrator.api_version = detected
    orchestrator.swagger_version = detected
    orchestrator.status = "validated"
    orchestrator.polling_enabled = orchestrator.auth_type != "session_otp"
    capabilities = {operation: True for operation in engine.list_operations(detected)}
    orchestrator.capabilities = {
        "source": f"profile:{detected}",
        "operations": capabilities,
        "verified": ["orchestrator.version"],
    }
    orchestrator.last_validated_at = datetime.now(UTC)
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
        capabilities=capabilities,
    )


def _extract_version(payload: dict) -> str | None:
    candidates: list[str] = []

    def visit(value, key: str = "") -> None:
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                visit(nested_value, str(nested_key))
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif "version" in key.lower() or "release" in key.lower():
            candidates.append(str(value))

    visit(payload)
    candidates.append(str(payload))
    for text in candidates:
        match = re.search(r"\b(\d+\.\d+(?:\.\d+)*)\b", text)
        if match:
            return match.group(1)
    return None
