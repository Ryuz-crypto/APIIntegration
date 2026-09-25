import uuid
from typing import Any

from sqlmodel import Session, select

from app.compatibility.engine import CompatibilityEngine
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.schemas.appliance import ApplianceCreate
from app.services.audit_service import record_event
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectClientError
from app.services.normalization_service import normalize_inventory, normalize_metrics
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
    version = orchestrator.api_version
    if not version:
        raise EdgeConnectClientError("Validate the Orchestrator version before discovery")
    client = EdgeConnectClient(orchestrator, engine)
    operation_id = "orchestrator.inventory.summary"
    try:
        response = client.call_operation(version, operation_id)
    except EdgeConnectClientError as exc:
        record_error(session, orchestrator.id, version, operation_id, exc)
        session.commit()
        raise

    raw_items = _extract_items(response.payload)
    appliances = [_upsert_appliance(session, orchestrator, item) for item in raw_items]
    session.flush()
    sample = record_success(
        session,
        orchestrator.id,
        version,
        response,
        extracted_values={"inventory_count": len(appliances)},
        transformations=["Extract inventory list", "Normalize appliances and sites"],
    )
    session.flush()
    normalized = normalize_inventory(session, orchestrator.id, appliances, raw_items, sample)
    sample.extracted_values = {**sample.extracted_values, **normalized}
    session.add(sample)
    _mark_verified(orchestrator, operation_id)
    session.add(orchestrator)
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
    version = orchestrator.api_version
    if not version:
        raise EdgeConnectClientError("Validate the Orchestrator version before collecting metrics")
    client = EdgeConnectClient(orchestrator, engine)
    operation_id = "appliance.performance"
    appliance_key = appliance.ne_pk or appliance.hostname or appliance.serial_number
    if not appliance_key:
        raise EdgeConnectClientError(
            "El appliance no tiene identificador nePk; ejecuta el descubrimiento para "
            "obtenerlo desde GET /gms/rest/appliance."
        )
    try:
        response = client.call_operation(version, operation_id, {"appliance_id": appliance_key})
    except EdgeConnectClientError as exc:
        record_error(session, orchestrator.id, version, operation_id, exc, appliance.id)
        session.commit()
        raise

    sample = record_success(
        session,
        orchestrator.id,
        version,
        response,
        appliance.id,
        request_params={"appliance_id": appliance_key},
        transformations=["Flatten numeric fields", "Persist normalized metric points"],
    )
    session.flush()
    values = normalize_metrics(session, orchestrator.id, appliance, response.payload, sample)
    sample.extracted_values = values
    session.add(sample)
    _mark_verified(orchestrator, operation_id)
    session.add(orchestrator)
    appliance.status = "sampled"
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
    serial = _first(item, "serialNumber", "serial_number", "serial")
    ne_pk = _first(item, "nePk", "ne_pk", "id", "applianceId")
    hostname = _first(item, "hostName", "hostname", "name", "applianceName") or ne_pk or serial
    if not hostname:
        hostname = f"edgeconnect-{uuid.uuid4().hex[:8]}"

    existing = None
    if ne_pk:
        existing = session.exec(
            select(Appliance).where(
                Appliance.orchestrator_id == orchestrator.id,
                Appliance.ne_pk == str(ne_pk),
            )
        ).first()
    if existing is None and serial:
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

    appliance = existing or Appliance(
        orchestrator_id=orchestrator.id,
        hostname=str(hostname),
        selected_for_monitoring=True,
    )
    appliance.hostname = str(hostname)
    appliance.serial_number = str(serial) if serial else appliance.serial_number
    appliance.ne_pk = str(ne_pk) if ne_pk else appliance.ne_pk
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


def _mark_verified(orchestrator: Orchestrator, operation_id: str) -> None:
    capabilities = dict(orchestrator.capabilities or {})
    verified = set(capabilities.get("verified", []))
    verified.add(operation_id)
    capabilities["verified"] = sorted(verified)
    orchestrator.capabilities = capabilities
