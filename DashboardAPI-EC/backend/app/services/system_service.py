from sqlmodel import Session, func, select

from app.models.appliance import Appliance
from app.models.compatibility import ApiCompatibilityProfile
from app.models.orchestrator import Orchestrator
from app.schemas.system import SystemOverview


def get_system_overview(session: Session) -> SystemOverview:
    orchestrators = session.exec(select(func.count()).select_from(Orchestrator)).one()
    appliances = session.exec(select(func.count()).select_from(Appliance)).one()
    selected = session.exec(
        select(func.count()).select_from(Appliance).where(Appliance.selected_for_monitoring)
    ).one()
    profiles = session.exec(select(func.count()).select_from(ApiCompatibilityProfile)).one()

    return SystemOverview(
        orchestrators=orchestrators,
        appliances=appliances,
        selected_appliances=selected,
        compatibility_profiles=profiles,
        services={
            "api": "ready",
            "database": "ready",
            "redis": "configured",
            "worker": "configured",
        },
    )
