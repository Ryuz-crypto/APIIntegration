import uuid
from datetime import UTC, datetime

from sqlalchemy import desc
from sqlmodel import Session, select

from app.db.session import engine as database_engine
from app.models.api_sample import ApiSample
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.services.appliance_service import collect_appliance_metrics, discover_appliances
from app.services.compatibility_service import build_compatibility_engine
from app.workers.celery_app import celery_app


def is_due(last_sample_at: datetime | None, interval_seconds: int, now: datetime | None = None) -> bool:
    if last_sample_at is None:
        return True
    current = now or datetime.now(UTC)
    if last_sample_at.tzinfo is None:
        last_sample_at = last_sample_at.replace(tzinfo=UTC)
    return (current - last_sample_at).total_seconds() >= interval_seconds


def _last_sample_at(
    session: Session,
    orchestrator_id,
    operation_id: str,
    appliance_id=None,
) -> datetime | None:
    statement = select(ApiSample).where(
        ApiSample.orchestrator_id == orchestrator_id,
        ApiSample.operation_id == operation_id,
    )
    if appliance_id is not None:
        statement = statement.where(ApiSample.appliance_id == appliance_id)
    sample = session.exec(
        statement
        .order_by(desc(ApiSample.created_at))
        .limit(1)
    ).first()
    return sample.created_at if sample else None


@celery_app.task
def schedule_due_polling() -> dict:
    queued_orchestrators = 0
    queued_appliances = 0
    with Session(database_engine) as session:
        orchestrators = list(
            session.exec(select(Orchestrator).where(Orchestrator.polling_enabled.is_(True))).all()
        )
        for orchestrator in orchestrators:
            if orchestrator.auth_type == "session_otp":
                continue
            if is_due(
                _last_sample_at(session, orchestrator.id, "orchestrator.inventory.summary"),
                orchestrator.polling_active_seconds,
            ):
                poll_orchestrator.delay(str(orchestrator.id))
                queued_orchestrators += 1

            appliances = session.exec(
                select(Appliance).where(
                    Appliance.orchestrator_id == orchestrator.id,
                    Appliance.selected_for_monitoring.is_(True),
                )
            ).all()
            for appliance in appliances:
                if is_due(
                    _last_sample_at(
                        session,
                        orchestrator.id,
                        "appliance.performance",
                        appliance.id,
                    ),
                    appliance.polling_active_seconds,
                ):
                    poll_appliance.delay(str(appliance.id))
                    queued_appliances += 1
    return {
        "status": "scheduled",
        "orchestrators": queued_orchestrators,
        "appliances": queued_appliances,
    }


@celery_app.task
def poll_orchestrator(orchestrator_id: str) -> dict:
    with Session(database_engine) as session:
        compatibility_engine = build_compatibility_engine(session)
        orchestrator = session.get(Orchestrator, uuid.UUID(orchestrator_id))
        if orchestrator is None:
            return {"status": "not-found", "orchestrator_id": orchestrator_id}
        appliances = discover_appliances(session, orchestrator, compatibility_engine)
        return {"status": "sampled", "orchestrator_id": orchestrator_id, "appliances": len(appliances)}


@celery_app.task
def poll_appliance(appliance_id: str) -> dict:
    with Session(database_engine) as session:
        compatibility_engine = build_compatibility_engine(session)
        appliance = session.get(Appliance, uuid.UUID(appliance_id))
        if appliance is None:
            return {"status": "not-found", "appliance_id": appliance_id}
        orchestrator = session.get(Orchestrator, appliance.orchestrator_id)
        if orchestrator is None:
            return {"status": "orchestrator-not-found", "appliance_id": appliance_id}
        payload = collect_appliance_metrics(session, appliance, orchestrator, compatibility_engine)
        return {"status": "sampled", "appliance_id": appliance_id, "fields": len(payload)}
