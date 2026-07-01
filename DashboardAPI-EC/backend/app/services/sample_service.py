import uuid

from sqlalchemy import desc
from sqlmodel import Session, select

from app.models.api_sample import ApiSample
from app.services.edgeconnect_client import EdgeConnectClientError, EdgeConnectResponse


def record_success(
    session: Session,
    orchestrator_id: uuid.UUID,
    api_version: str | None,
    response: EdgeConnectResponse,
    appliance_id: uuid.UUID | None = None,
) -> ApiSample:
    sample = ApiSample(
        orchestrator_id=orchestrator_id,
        appliance_id=appliance_id,
        api_version=api_version,
        operation_id=response.operation_id,
        method=response.method,
        path=response.path,
        status_code=response.status_code,
        duration_ms=response.duration_ms,
        ok=True,
        payload=response.payload,
    )
    session.add(sample)
    return sample


def record_error(
    session: Session,
    orchestrator_id: uuid.UUID,
    api_version: str | None,
    operation_id: str,
    error: EdgeConnectClientError,
    appliance_id: uuid.UUID | None = None,
) -> ApiSample:
    sample = ApiSample(
        orchestrator_id=orchestrator_id,
        appliance_id=appliance_id,
        api_version=api_version,
        operation_id=operation_id,
        method="GET",
        path="unresolved",
        status_code=error.status_code,
        duration_ms=error.duration_ms,
        ok=False,
        payload=error.payload,
        error=str(error),
    )
    session.add(sample)
    return sample


def list_recent_samples(session: Session, limit: int = 50) -> list[ApiSample]:
    statement = select(ApiSample).order_by(desc(ApiSample.created_at)).limit(limit)
    return list(session.exec(statement).all())
