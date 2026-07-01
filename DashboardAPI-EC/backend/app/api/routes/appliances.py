from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.models.appliance import Appliance
from app.schemas.appliance import ApplianceCreate, ApplianceRead
from app.services.appliance_service import create_appliance, list_appliances

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
