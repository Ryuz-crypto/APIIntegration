import uuid

from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlmodel import Session

from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import load_builtin_profiles
from app.db.session import get_session
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceCreate, ApplianceRead
from app.services.appliance_service import create_appliance, list_appliances, collect_appliance_metrics
from app.services.edgeconnect_client import EdgeConnectClientError

router = APIRouter()


@router.get("", response_model=list[ApplianceRead])
def list_items(session: Session = Depends(get_session)) -> list[Appliance]:
    return list_appliances(session)


@router.post("", response_model=ApplianceRead, status_code=201)
def create_item(payload: ApplianceCreate, session: Session = Depends(get_session)) -> Appliance:
    return create_appliance(session, payload)


@router.get("/polling-plan")
def polling_plan() -> dict:
    return {
        "dashboard_active": {"orchestrator_seconds": 120, "appliance_seconds": 5},
        "dashboard_idle": {"orchestrator_seconds": 600, "appliance_seconds": 300},
    }


@router.post("/{appliance_id}/collect")
def collect_item(appliance_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    appliance = session.get(Appliance, appliance_id)
    if appliance is None:
        raise HTTPException(status_code=404, detail="Appliance not found")
    orchestrator = session.get(Orchestrator, appliance.orchestrator_id)
    if orchestrator is None:
        raise HTTPException(status_code=404, detail="Orchestrator not found")
    engine = CompatibilityEngine(load_builtin_profiles())
    try:
        return collect_appliance_metrics(session, appliance, orchestrator, engine)
    except EdgeConnectClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
