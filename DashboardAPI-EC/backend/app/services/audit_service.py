from sqlmodel import Session

from app.models.audit import AuditEvent


def record_event(
    session: Session,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    actor: str = "system",
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    session.add(event)
    return event
