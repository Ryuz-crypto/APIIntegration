from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.samples import ApiSampleRead
from app.services.sample_service import list_recent_samples

router = APIRouter()


@router.get("", response_model=list[ApiSampleRead])
def list_items(limit: int = 50, session: Session = Depends(get_session)):
    return list_recent_samples(session, limit=min(limit, 200))
