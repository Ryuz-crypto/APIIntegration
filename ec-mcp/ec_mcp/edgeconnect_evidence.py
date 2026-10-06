"""Bounded, secret-safe observations inspired by pyedgeconnect read workflows."""

from __future__ import annotations

from typing import Any

SERVICE_PROVIDERS = "orchestrator.getserviceproviders845"
REMOTE_ENDPOINTS = "orchestrator.remoteendpoints841"
ENDPOINT_ASSOCIATIONS = "orchestrator.getremoteendpointassociation837"
IPSLA_SETTINGS = "orchestrator.serviceorchestrationipslasettingget858"
FLOW_DETAILS = "orchestrator.flowdetails2239"


def bounded_id(value: int, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 2_147_483_647:
        raise ValueError(f"{name} must be an integer between 0 and 2147483647")
    return value


def _unwrap(payload: Any) -> Any:
    for _ in range(3):
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        else:
            break
    return payload


def service_evidence(service_id: int, ne_pk: str, providers: Any, endpoints: Any, associations: Any, ipsla: Any) -> dict[str, Any]:
    """Report only allowlisted fields: tunnel settings can contain serialized PSKs."""
    provider_rows = _unwrap(providers)
    if not isinstance(provider_rows, list):
        raise ValueError("Service provider response shape is unrecognized")
    matches = [row for row in provider_rows if isinstance(row, dict) and str(row.get("serviceId")) == str(service_id)]
    if len(matches) != 1:
        raise ValueError("Service ID missing or ambiguous in provider inventory")
    provider = {key: matches[0][key] for key in ("serviceId", "serviceName", "servicePrefix") if key in matches[0]}

    endpoint_rows = _unwrap(endpoints)
    if isinstance(endpoint_rows, dict):
        endpoint_rows = endpoint_rows.get("remoteEndpoints")
    if not isinstance(endpoint_rows, list):
        raise ValueError("Remote endpoint response shape is unrecognized")
    safe_endpoints = []
    for row in endpoint_rows:
        if not isinstance(row, dict) or "remoteEndpointId" not in row:
            raise ValueError("Remote endpoint row is unrecognized")
        safe_endpoints.append({key: row[key] for key in (
            "remoteEndpointId", "remoteEndpointName", "labelId", "ipAddress", "probeIpAddress", "backupEndpointId"
        ) if key in row})

    association_map = _unwrap(associations)
    if not isinstance(association_map, dict) or not all(
        isinstance(ids, list) and all(isinstance(item, str) for item in ids)
        for ids in association_map.values()
    ):
        raise ValueError("Remote endpoint association response shape is unrecognized")
    associated = [row for row in safe_endpoints if ne_pk in association_map.get(str(row["remoteEndpointId"]), [])]
    return {
        "nePk": ne_pk,
        "service": provider,
        "remote_endpoints": safe_endpoints,
        "associated_endpoints": associated,
        "association_observed": True,
        "ipsla_settings_observed": _unwrap(ipsla) is not None,
        "evidence_scope": "service_configuration_and_association_only",
        "tunnel_state_observed": False,
        "policy_decision_observed": False,
        "enforcement_verified": False,
    }


FLOW_FIELDS = (
    "srcIp", "dstIp", "srcPort", "dstPort", "protocol", "appName", "application",
    "sourceIp", "destinationIp", "sourcePort", "destinationPort", "action", "policyName",
    "ruleName", "zoneIn", "zoneOut", "flowId", "seq",
)


def flow_evidence(ne_pk: str, flow_id: int, sequence: int, payload: Any) -> dict[str, Any]:
    """Allowlist known flow scalars; omit opaque nested data and unknown fields."""
    detail = _unwrap(payload)
    if not isinstance(detail, dict):
        detail = {}
    safe = {key: detail[key] for key in FLOW_FIELDS if type(detail.get(key)) in (str, int, bool, float)}
    return {
        "nePk": ne_pk,
        "flow_id": flow_id,
        "sequence": sequence,
        "flow_details": safe,
        "response_shape_recognized": bool(safe),
        "evidence_scope": "flow_detail_read" if safe else "flow_detail_schema_unrecognized",
        "policy_decision_observed": "action" in safe,
        "enforcement_verified": False,
    }
