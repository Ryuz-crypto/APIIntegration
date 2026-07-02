from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import load_builtin_profiles
from app.db.session import engine as db_engine
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.services.appliance_service import collect_appliance_metrics, discover_appliances
from sqlmodel import Session
from app.workers.celery_app import celery_app


@celery_app.task
def poll_orchestrator(orchestrator_id: str) -> dict:
    compatibility_engine = CompatibilityEngine(load_builtin_profiles())
    with Session(db_engine) as session:
        orchestrator = session.get(Orchestrator, orchestrator_id)
        if orchestrator is None:
            return {"status": "not-found", "orchestrator_id": orchestrator_id}
        appliances = discover_appliances(session, orchestrator, compatibility_engine)
        return {"status": "sampled", "orchestrator_id": orchestrator_id, "appliances": len(appliances)}


@celery_app.task
def poll_appliance(appliance_id: str) -> dict:
    compatibility_engine = CompatibilityEngine(load_builtin_profiles())
    with Session(db_engine) as session:
        appliance = session.get(Appliance, appliance_id)
        if appliance is None:
            return {"status": "not-found", "appliance_id": appliance_id}
        orchestrator = session.get(Orchestrator, appliance.orchestrator_id)
        if orchestrator is None:
            return {"status": "orchestrator-not-found", "appliance_id": appliance_id}
        payload = collect_appliance_metrics(session, appliance, orchestrator, compatibility_engine)
        return {"status": "sampled", "appliance_id": appliance_id, "fields": len(payload)}
