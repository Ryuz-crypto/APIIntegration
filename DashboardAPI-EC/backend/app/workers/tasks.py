from sqlmodel import Session

from app.db.session import engine as database_engine
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.services.appliance_service import collect_appliance_metrics, discover_appliances
from app.services.compatibility_service import build_compatibility_engine
from app.workers.celery_app import celery_app


@celery_app.task
def poll_orchestrator(orchestrator_id: str) -> dict:
    with Session(database_engine) as session:
        compatibility_engine = build_compatibility_engine(session)
        orchestrator = session.get(Orchestrator, orchestrator_id)
        if orchestrator is None:
            return {"status": "not-found", "orchestrator_id": orchestrator_id}
        appliances = discover_appliances(session, orchestrator, compatibility_engine)
        return {"status": "sampled", "orchestrator_id": orchestrator_id, "appliances": len(appliances)}


@celery_app.task
def poll_appliance(appliance_id: str) -> dict:
    with Session(database_engine) as session:
        compatibility_engine = build_compatibility_engine(session)
        appliance = session.get(Appliance, appliance_id)
        if appliance is None:
            return {"status": "not-found", "appliance_id": appliance_id}
        orchestrator = session.get(Orchestrator, appliance.orchestrator_id)
        if orchestrator is None:
            return {"status": "orchestrator-not-found", "appliance_id": appliance_id}
        payload = collect_appliance_metrics(session, appliance, orchestrator, compatibility_engine)
        return {"status": "sampled", "appliance_id": appliance_id, "fields": len(payload)}
