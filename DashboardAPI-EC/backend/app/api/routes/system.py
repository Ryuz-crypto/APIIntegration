from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.system import SystemOverview
from app.services.system_service import get_system_overview

router = APIRouter()


@router.get("/overview", response_model=SystemOverview)
def overview(session: Session = Depends(get_session)) -> SystemOverview:
    return get_system_overview(session)
