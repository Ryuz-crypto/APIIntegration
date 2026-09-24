import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.models.api_sample import ApiSample
from app.schemas.samples import ApiSampleRead, ApiTraceRead
from app.services.sample_service import list_recent_samples
from app.services.trace_service import build_trace

router = APIRouter()


@router.get("", response_model=list[ApiSampleRead])
def list_items(limit: int = 50, session: Session = Depends(get_session)):
    return list_recent_samples(session, limit=min(limit, 200))


@router.get("/{sample_id}/trace", response_model=ApiTraceRead)
def get_trace(sample_id: uuid.UUID, session: Session = Depends(get_session)) -> ApiTraceRead:
    sample = session.get(ApiSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="API sample not found")
    return build_trace(sample)
