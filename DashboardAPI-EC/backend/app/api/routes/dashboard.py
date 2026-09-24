import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.models.orchestrator import Orchestrator
from app.schemas.dashboard import DashboardRead
from app.services.dashboard_service import compose_dashboard

router = APIRouter()


@router.get("/{orchestrator_id}", response_model=DashboardRead)
def get_dashboard(orchestrator_id: uuid.UUID, session: Session = Depends(get_session)) -> DashboardRead:
    orchestrator = session.get(Orchestrator, orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    return compose_dashboard(session, orchestrator)
