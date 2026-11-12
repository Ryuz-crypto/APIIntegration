"""Helpers for the Aruba Central MCP tools."""

from __future__ import annotations

import json
from typing import Any

from .central_client import DEVICE_FAMILIES, TROUBLESHOOTING_DEVICE_TYPES

TREND_METRICS = {
    "aps": {
        "throughput": "throughput-trends",
        "frames": "frames-trends",
        "client-count": "client-count-trends",
    },
    "switches": {
        "throughput": "throughput-trends",
        "frames": "frames-trends",
        "poe": "poe-trends",
    },
    "gateways": {
        "cpu-utilization": "cpu-utilization-trends",
        "memory-utilization": "memory-utilization-trends",
        "throughput": "throughput-trends",
        "wan-availability": "wan-availability-trends",
    },
}

SHOW_COMMANDS_MAX = 20

NETWORK_TESTS = {
    "ping": "ping",
    "traceroute": "traceroute",
    "nslookup": "nslookup",
    "tcp": "tcp",
    "http": "http",
    "https": "https",
}


def build_network_test_body(
    test_type: str,
    destination: str,
    port: int = 0,
    count: int = 0,
) -> tuple[str, dict[str, Any]]:
    """Build the request body for a Central live network test.

    Returns (endpoint, body). Validation follows the parameters accepted by
    the network-troubleshooting v1 family for each test type.
    """
    test = (test_type or "").strip().lower()
    endpoint = NETWORK_TESTS.get(test)
    if endpoint is None:
        raise ValueError(f"Unsupported test_type '{test_type}'. Use one of: {', '.join(sorted(NETWORK_TESTS))}")
    if not destination.strip():
        raise ValueError("destination is required (IP address or hostname)")
    body: dict[str, Any] = {}
    if test == "nslookup":
        body["host"] = destination.strip()
    else:
        body["destination"] = destination.strip()
    if test in ("http", "https"):
        body["protocol"] = test.upper()
    if test == "tcp":
        if not port or not isinstance(port, int):
            raise ValueError("port is required for tcp tests")
        body["port"] = port
    if test == "ping" and count:
        if not isinstance(count, int) or not 1 <= count <= 100:
            raise ValueError("count must be an integer between 1 and 100")
        body["count"] = count
    return endpoint, body


def resolve_family(device_type: str) -> str:
    """Map a user-provided device type to a monitoring family."""
    value = (device_type or "").strip().lower()
    aliases = {
        "ap": "aps",
        "aps": "aps",
        "cx": "switches",
        "switch": "switches",
        "switches": "switches",
        "gateway": "gateways",
        "gateways": "gateways",
    }
    family = aliases.get(value)
    if family is None:
        raise ValueError(f"Unsupported device_type '{device_type}'. Use one of: ap, cx, switch, gateway")
    return family


def resolve_troubleshooting_device_type(device_type: str) -> str:
    """Map a user-provided device type to a troubleshooting device type."""
    value = (device_type or "").strip().lower()
    aliases = {
        "ap": "aps",
        "aps": "aps",
        "cx": "cx",
        "aos-s": "aos-s",
        "switch": "cx",
        "gateway": "gateways",
        "gateways": "gateways",
    }
    resolved = aliases.get(value)
    if resolved is None:
        raise ValueError(f"Unsupported device_type '{device_type}'. Use one of: ap, cx, aos-s, switch, gateway")
    return resolved


def trend_metric(family: str, metric: str) -> str:
    metrics = TREND_METRICS.get(family, {})
    resolved = metrics.get((metric or "").strip().lower())
    if resolved is None:
        raise ValueError(
            f"Unsupported trend metric '{metric}' for '{family}'. Available metrics: {', '.join(sorted(metrics))}"
        )
    return resolved


def parse_commands(commands_json: str) -> list[str]:
    """Parse a JSON list of show commands and validate the 'show ' prefix."""
    try:
        commands = json.loads(commands_json) if commands_json.strip() else []
    except json.JSONDecodeError as error:
        raise ValueError(f"commands_json is not valid JSON: {error}") from error
    if not commands or not isinstance(commands, list):
        raise ValueError("commands_json must be a non-empty JSON list of strings")
    if len(commands) > SHOW_COMMANDS_MAX:
        raise ValueError(f"maximum {SHOW_COMMANDS_MAX} commands per call")
    invalid = [c for c in commands if not isinstance(c, str) or not c.strip().lower().startswith("show ")]
    if invalid:
        raise ValueError(f"All commands must start with 'show '. Invalid: {invalid}")
    return [c.strip() for c in commands]


def parse_ports(ports_json: str) -> list[str]:
    """Parse a JSON list of port names/numbers."""
    try:
        ports = json.loads(ports_json) if ports_json.strip() else []
    except json.JSONDecodeError as error:
        raise ValueError(f"ports_json is not valid JSON: {error}") from error
    if not ports or not isinstance(ports, list) or any(not isinstance(p, str) or not p.strip() for p in ports):
        raise ValueError("ports_json must be a non-empty JSON list of port strings")
    return [p.strip() for p in ports]


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "data", "results", "devices", "clients", "wlans", "clusters", "alerts", "events", "sites"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def summarize_list(payload: Any) -> dict[str, Any]:
    """Compact a list-style Central response."""
    items = _items(payload)
    summary: dict[str, Any] = {"count": len(items)}
    if isinstance(payload, dict):
        for key in ("total", "total_count", "next", "offset", "limit"):
            if key in payload:
                summary[key] = payload[key]
    summary["items"] = items
    return summary


def summarize_sites(payload: Any) -> dict[str, Any]:
    items = _items(payload)
    return {"count": len(items), "sites": items}


def summarize_health(payload: Any) -> dict[str, Any]:
    """Summarize a sites-health style payload with per-site scores."""
    items = _items(payload)
    sites = []
    for raw in items:
        if not isinstance(raw, dict):
            sites.append(raw)
            continue
        sites.append(
            {
                "site_id": raw.get("site_id") or raw.get("siteId"),
                "site_name": raw.get("site_name") or raw.get("siteName"),
                "health": raw.get("health") or raw.get("healthCategory"),
                "device_health": raw.get("device_health") or raw.get("deviceHealth"),
                "client_health": raw.get("client_health") or raw.get("clientHealth"),
            }
        )
    return {"count": len(sites), "sites": sites}


def summarize_devices(payload: Any) -> dict[str, Any]:
    items = _items(payload)
    devices = []
    for raw in items:
        if not isinstance(raw, dict):
            devices.append(raw)
            continue
        devices.append(
            {
                "serial": raw.get("serialNumber") or raw.get("serial"),
                "name": raw.get("deviceName") or raw.get("name"),
                "model": raw.get("model"),
                "status": raw.get("status"),
                "site": raw.get("siteName") or raw.get("site_name"),
                "ip": raw.get("ipv4") or raw.get("ipAddress"),
            }
        )
    return {"count": len(devices), "devices": devices}


def summarize_clients(payload: Any) -> dict[str, Any]:
    items = _items(payload)
    clients = []
    for raw in items:
        if not isinstance(raw, dict):
            clients.append(raw)
            continue
        clients.append(
            {
                "mac": raw.get("macAddress") or raw.get("mac_address"),
                "name": raw.get("clientName") or raw.get("name"),
                "status": raw.get("status") or raw.get("connectionType"),
                "ip": raw.get("ipAddress") or raw.get("ipv4"),
                "ap": raw.get("connectedApSerial") or raw.get("ap_serial"),
                "ssid": raw.get("ssid"),
                "site": raw.get("siteName") or raw.get("site_name"),
            }
        )
    return {"count": len(clients), "clients": clients}


def summarize_alerts(payload: Any) -> dict[str, Any]:
    items = _items(payload)
    alerts = []
    for raw in items:
        if not isinstance(raw, dict):
            alerts.append(raw)
            continue
        alerts.append(
            {
                "id": raw.get("alertId") or raw.get("id"),
                "severity": raw.get("severity"),
                "category": raw.get("category"),
                "state": raw.get("state") or raw.get("status"),
                "description": raw.get("description") or raw.get("text"),
                "device": raw.get("deviceSerial") or raw.get("serial"),
                "site": raw.get("siteName") or raw.get("site_id"),
                "timestamp": raw.get("timestamp") or raw.get("createdAt"),
            }
        )
    return {"count": len(alerts), "alerts": alerts}


def summarize_events(payload: Any) -> dict[str, Any]:
    items = _items(payload)
    events = []
    for raw in items:
        if not isinstance(raw, dict):
            events.append(raw)
            continue
        events.append(
            {
                "id": raw.get("eventId") or raw.get("id"),
                "name": raw.get("eventName") or raw.get("name"),
                "severity": raw.get("severity"),
                "category": raw.get("category"),
                "device": raw.get("deviceSerial") or raw.get("serial"),
                "site": raw.get("siteName") or raw.get("site_id"),
                "timestamp": raw.get("timestamp") or raw.get("firstOccurrence"),
            }
        )
    return {"count": len(events), "events": events}


def validate_operation(operation: str) -> str:
    """Validate an async operation name for task result lookups."""
    value = (operation or "showCommands").strip() or "showCommands"
    from .central_client import ASYNC_OPERATIONS

    if value not in ASYNC_OPERATIONS:
        raise ValueError(f"Unsupported operation '{operation}'. Use one of {sorted(ASYNC_OPERATIONS)}")
    return value


def extract_task_id(payload: Any) -> str:
    """Extract the async task id from a troubleshooting initiation response."""
    if isinstance(payload, dict):
        for key in ("taskId", "task_id", "id", "operationId"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested = payload.get("task") if isinstance(payload.get("task"), dict) else None
        if nested:
            for key in ("taskId", "task_id", "id"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    raise ValueError(f"Could not extract a task id from Central response: {payload}")


__all__ = [
    "DEVICE_FAMILIES",
    "NETWORK_TESTS",
    "SHOW_COMMANDS_MAX",
    "TREND_METRICS",
    "TROUBLESHOOTING_DEVICE_TYPES",
    "extract_task_id",
    "parse_commands",
    "parse_ports",
    "resolve_family",
    "resolve_troubleshooting_device_type",
    "summarize_alerts",
    "summarize_clients",
    "summarize_devices",
    "summarize_events",
    "summarize_health",
    "summarize_list",
    "summarize_sites",
    "trend_metric",
    "validate_operation",
]
