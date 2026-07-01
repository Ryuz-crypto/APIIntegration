from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import load_builtin_profiles
from app.workers.celery_app import celery_app


@celery_app.task
def poll_orchestrator(version: str, operation_id: str = "orchestrator.inventory.summary") -> dict:
    engine = CompatibilityEngine(load_builtin_profiles())
    operation = engine.resolve(version, operation_id)
    return {
        "kind": "orchestrator",
        "version": version,
        "method": operation.method,
        "path": operation.path,
        "status": "contract-ready",
    }


@celery_app.task
def poll_appliance(version: str, appliance_id: str, operation_id: str = "appliance.performance") -> dict:
    engine = CompatibilityEngine(load_builtin_profiles())
    operation = engine.resolve(version, operation_id, {"appliance_id": appliance_id})
    return {
        "kind": "appliance",
        "version": version,
        "method": operation.method,
        "path": operation.path,
        "status": "contract-ready",
    }
