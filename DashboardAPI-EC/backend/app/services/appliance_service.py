import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityEngine
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceCreate
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectClientError
from app.services.audit_service import record_event
from app.services.sample_service import record_error, record_success


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


def discover_appliances(
    session: Session,
    orchestrator: Orchestrator,
    engine: CompatibilityEngine,
) -> list[Appliance]:
    version = orchestrator.api_version or engine.versions[-1]
    client = EdgeConnectClient(orchestrator, engine)
    operation_id = "orchestrator.inventory.summary"
    try:
        response = client.call_operation(version, operation_id)
    except EdgeConnectClientError as exc:
        record_error(session, orchestrator.id, version, operation_id, exc)
        orchestrator.last_error = str(exc)[:800]
        orchestrator.last_status_code = exc.status_code
        orchestrator.last_latency_ms = exc.duration_ms
        session.add(orchestrator)
        session.commit()
        raise

    record_success(session, orchestrator.id, version, response)
    orchestrator.last_status_code = response.status_code
    orchestrator.last_latency_ms = response.duration_ms
    orchestrator.last_error = None
    session.add(orchestrator)
    appliances = [_upsert_appliance(session, orchestrator, item) for item in _extract_items(response.payload)]
    record_event(
        session,
        "appliance.discovered",
        "orchestrator",
        str(orchestrator.id),
        {"count": len(appliances), "operation_id": operation_id},
    )
    session.commit()
    for appliance in appliances:
        session.refresh(appliance)
    return appliances


def collect_appliance_metrics(
    session: Session,
    appliance: Appliance,
    orchestrator: Orchestrator,
    engine: CompatibilityEngine,
) -> dict:
    version = orchestrator.api_version or appliance.software_version or engine.versions[-1]
    client = EdgeConnectClient(orchestrator, engine)
    operation_id = "appliance.performance"
    appliance_key = appliance.serial_number or appliance.hostname
    try:
        response = client.call_operation(version, operation_id, {"appliance_id": appliance_key})
    except EdgeConnectClientError as exc:
        record_error(session, orchestrator.id, version, operation_id, exc, appliance.id)
        session.commit()
        raise

    record_success(session, orchestrator.id, version, response, appliance.id)
    appliance.status = "sampled"
    appliance.last_metrics = _summarize_metrics(response.payload)
    appliance.last_collected_at = datetime.now(UTC)
    appliance.last_status_code = response.status_code
    appliance.last_latency_ms = response.duration_ms
    session.add(appliance)
    session.commit()
    return response.payload


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("appliances", "items", "data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    if all(isinstance(value, dict) for value in payload.values()):
        return [value for value in payload.values() if isinstance(value, dict)]
    return [payload] if payload else []


def _upsert_appliance(session: Session, orchestrator: Orchestrator, item: dict[str, Any]) -> Appliance:
    serial = _first(item, "serialNumber", "serial_number", "serial", "id", "applianceId")
    hostname = _first(item, "hostName", "hostname", "name", "applianceName") or serial
    if not hostname:
        hostname = f"edgeconnect-{uuid.uuid4().hex[:8]}"

    existing = None
    if serial:
        existing = session.exec(
            select(Appliance).where(
                Appliance.orchestrator_id == orchestrator.id,
                Appliance.serial_number == str(serial),
            )
        ).first()
    if existing is None:
        existing = session.exec(
            select(Appliance).where(
                Appliance.orchestrator_id == orchestrator.id,
                Appliance.hostname == str(hostname),
            )
        ).first()

    appliance = existing or Appliance(orchestrator_id=orchestrator.id, hostname=str(hostname))
    appliance.hostname = str(hostname)
    appliance.serial_number = str(serial) if serial else appliance.serial_number
    appliance.site = _first(item, "site", "siteName", "location") or appliance.site
    appliance.model = _first(item, "model", "platform", "applianceModel") or appliance.model
    appliance.software_version = (
        _first(item, "softwareVersion", "software_version", "version") or appliance.software_version
    )
    appliance.status = str(_first(item, "status", "state", "reachability") or "discovered")
    session.add(appliance)
    return appliance


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _summarize_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    preferred_keys = (
        "timestamp",
        "cpu",
        "cpuUtilization",
        "memory",
        "memoryUtilization",
        "tunnelCount",
        "tunnels",
        "wanRx",
        "wanTx",
        "rxBytes",
        "txBytes",
        "latency",
        "loss",
        "jitter",
    )
    summary: dict[str, Any] = {}
    for key in preferred_keys:
        value = payload.get(key)
        if _is_metric_value(value):
            summary[key] = value
    if summary:
        return summary
    for key, value in payload.items():
        if _is_metric_value(value):
            summary[key] = value
        if len(summary) >= 8:
            break
    return summary


def _is_metric_value(value: Any) -> bool:
    return isinstance(value, str | int | float | bool) and value not in ("", None)
