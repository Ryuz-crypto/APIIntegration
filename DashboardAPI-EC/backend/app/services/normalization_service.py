import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, select

from app.models.api_sample import ApiSample
from app.models.appliance import Appliance
from app.models.network_resource import MetricPoint, NetworkResource

UNIT_RULES = (
    (re.compile(r"(percent|percentage|utilization|loss|cpu|memory)", re.IGNORECASE), "%"),
    (re.compile(r"(latency|jitter|rtt|response.*time)", re.IGNORECASE), "ms"),
    (re.compile(r"(bytes|octets)", re.IGNORECASE), "bytes"),
    (re.compile(r"(bandwidth|throughput|bps)", re.IGNORECASE), "bps"),
    (
        re.compile(r"(packets|flows|sessions|tunnels|interfaces|count)", re.IGNORECASE),
        "count",
    ),
)


def normalize_inventory(
    session: Session,
    orchestrator_id: uuid.UUID,
    appliances: list[Appliance],
    raw_items: list[dict[str, Any]],
    sample: ApiSample,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    sites: set[str] = set()
    for appliance, raw in zip(appliances, raw_items, strict=False):
        external_id = appliance.serial_number or appliance.hostname
        _upsert_resource(
            session,
            orchestrator_id=orchestrator_id,
            appliance_id=appliance.id,
            resource_type="appliance",
            external_id=external_id,
            name=appliance.hostname,
            status=appliance.status,
            attributes={
                "site": appliance.site,
                "model": appliance.model,
                "software_version": appliance.software_version,
                "raw": raw,
            },
            sample=sample,
            observed_at=now,
        )
        if appliance.site:
            sites.add(appliance.site)
            _upsert_resource(
                session,
                orchestrator_id=orchestrator_id,
                appliance_id=None,
                resource_type="site",
                external_id=appliance.site,
                name=appliance.site,
                status="active",
                attributes={},
                sample=sample,
                observed_at=now,
            )
    return {"appliances": len(appliances), "sites": len(sites)}


def normalize_metrics(
    session: Session,
    orchestrator_id: uuid.UUID,
    appliance: Appliance,
    payload: dict[str, Any],
    sample: ApiSample,
) -> dict[str, float]:
    values = dict(_numeric_values(payload))
    for metric_name, value in values.items():
        session.add(
            MetricPoint(
                orchestrator_id=orchestrator_id,
                appliance_id=appliance.id,
                namespace="appliance.performance",
                metric_name=metric_name,
                value=value,
                unit=_infer_unit(metric_name),
                dimensions={"hostname": appliance.hostname, "site": appliance.site},
                source_operation_id=sample.operation_id,
                source_sample_id=sample.id,
            )
        )
    return values


def _upsert_resource(
    session: Session,
    *,
    orchestrator_id: uuid.UUID,
    appliance_id: uuid.UUID | None,
    resource_type: str,
    external_id: str,
    name: str,
    status: str | None,
    attributes: dict[str, Any],
    sample: ApiSample,
    observed_at: datetime,
) -> NetworkResource:
    resource = session.exec(
        select(NetworkResource).where(
            NetworkResource.orchestrator_id == orchestrator_id,
            NetworkResource.resource_type == resource_type,
            NetworkResource.external_id == external_id,
        )
    ).first()
    if resource is None:
        resource = NetworkResource(
            orchestrator_id=orchestrator_id,
            resource_type=resource_type,
            external_id=external_id,
            name=name,
            source_operation_id=sample.operation_id,
        )
    resource.appliance_id = appliance_id
    resource.name = name
    resource.status = status
    resource.attributes = attributes
    resource.source_operation_id = sample.operation_id
    resource.source_sample_id = sample.id
    resource.observed_at = observed_at
    session.add(resource)
    return resource


def _numeric_values(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, nested in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            yield from _numeric_values(nested, name)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _numeric_values(nested, f"{prefix}[{index}]")
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and prefix:
        yield prefix, float(value)


def _infer_unit(metric_name: str) -> str | None:
    for pattern, unit in UNIT_RULES:
        if pattern.search(metric_name):
            return unit
    return None
