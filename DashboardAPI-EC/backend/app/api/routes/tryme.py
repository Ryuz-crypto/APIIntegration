import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.models.api_sample import ApiSample
from app.models.orchestrator import Orchestrator
from app.models.tryme_snapshot import TryMeSnapshot
from app.schemas.tryme import (
    SnapshotCreate,
    SnapshotRead,
    TryMeCatalog,
    TryMeExecuteRequest,
    TryMeExecuteResult,
)
from app.services.audit_service import record_event
from app.services.tryme_service import (
    catalog,
    create_snapshot,
    execute,
    list_snapshots,
    sync_catalog,
)

router = APIRouter()


def _orchestrator(session: Session, orchestrator_id: uuid.UUID) -> Orchestrator:
    item = session.get(Orchestrator, orchestrator_id)
    if item is None:
        raise HTTPException(404, "Orchestrator not found")
    return item


def _authorize_mutation(request: Request, token: str) -> None:
    if not settings.tls_admin_token or not secrets.compare_digest(
        token.encode(), settings.tls_admin_token.encode()
    ):
        raise HTTPException(403, "Clave administrativa incorrecta.")
    if request.url.scheme != "https" and (
        not request.client or request.client.host not in {"127.0.0.1", "::1"}
    ):
        raise HTTPException(400, "Usa HTTPS o el túnel SSH local para ejecutar cambios.")


@router.get("/catalog/{orchestrator_id}", response_model=TryMeCatalog)
def get_catalog(orchestrator_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        return catalog(session, _orchestrator(session, orchestrator_id))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/catalog/{orchestrator_id}/sync", response_model=TryMeCatalog)
def synchronize_catalog(orchestrator_id: uuid.UUID, session: Session = Depends(get_session)):
    try:
        return sync_catalog(session, _orchestrator(session, orchestrator_id))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/execute", response_model=TryMeExecuteResult)
def run_operation(
    payload: TryMeExecuteRequest,
    request: Request,
    x_tls_admin_token: str = Header(default=""),
    session: Session = Depends(get_session),
):
    if payload.method != "GET":
        _authorize_mutation(request, x_tls_admin_token)
    orchestrator = _orchestrator(session, payload.orchestrator_id)
    try:
        result = execute(session, orchestrator, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if payload.method != "GET":
        record_event(
            session,
            "try_me.mutation_executed",
            "orchestrator",
            str(orchestrator.id),
            {
                "operation_id": result.operation_id,
                "method": result.method,
                "path": result.path,
                "status_code": result.status_code,
                "sample_id": str(result.sample_id),
            },
        )
        session.commit()
    return result


@router.get("/snapshots/{orchestrator_id}", response_model=list[SnapshotRead])
def snapshots(orchestrator_id: uuid.UUID, session: Session = Depends(get_session)):
    _orchestrator(session, orchestrator_id)
    return list_snapshots(session, orchestrator_id)


@router.post("/snapshots", response_model=SnapshotRead, status_code=201)
def save_snapshot(payload: SnapshotCreate, session: Session = Depends(get_session)):
    sample = session.get(ApiSample, payload.sample_id)
    if sample is None:
        raise HTTPException(404, "API sample not found")
    try:
        return create_snapshot(session, sample, payload.name)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.delete("/snapshots/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: uuid.UUID, session: Session = Depends(get_session)):
    item = session.get(TryMeSnapshot, snapshot_id)
    if item is None:
        raise HTTPException(404, "Snapshot not found")
    session.delete(item)
    session.commit()
    return Response(status_code=204)
