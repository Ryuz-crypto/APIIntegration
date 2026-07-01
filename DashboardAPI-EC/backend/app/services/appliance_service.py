from sqlmodel import Session, select

from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceCreate
from app.services.audit_service import record_event


def create_appliance(session: Session, payload: ApplianceCreate) -> Appliance:
    appliance = Appliance(**payload.model_dump())
    session.add(appliance)
    session.flush()
    record_event(session, "appliance.created", "appliance", str(appliance.id))
    session.commit()
    session.refresh(appliance)
    return appliance


def list_appliances(session: Session) -> list[Appliance]:
    return list(session.exec(select(Appliance).order_by(Appliance.hostname)).all())


def discover_appliances(session: Session, orchestrator: Orchestrator) -> list[Appliance]:
    seed_hostname = f"{orchestrator.name.lower().replace(' ', '-')}-edge-01"
    existing = session.exec(select(Appliance).where(Appliance.hostname == seed_hostname)).first()
    if existing:
        return [existing]

    appliance = Appliance(
        orchestrator_id=orchestrator.id,
        hostname=seed_hostname,
        serial_number="DISCOVERED-PHASE1",
        site="Discovery Lab",
        model="EdgeConnect",
        software_version=orchestrator.api_version,
        status="discovered",
    )
    session.add(appliance)
    session.flush()
    record_event(
        session,
        "appliance.discovered",
        "orchestrator",
        str(orchestrator.id),
        {"count": 1},
    )
    session.commit()
    session.refresh(appliance)
    return [appliance]
