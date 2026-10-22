"""Infrastructure and real-time telemetry workflow helpers for EdgeConnect.

Two curated layers over the raw API catalog:

- Orchestrator-side infrastructure KPIs (self-health of the GMS server:
  platform info, disk space, DB partitions, stats collectors, versions,
  appliance CPU/memory timeseries and interface state). These come from the
  Orchestrator REST API directly.
- Appliance-side real-time telemetry (live per-second stats, health summary,
  disk usage, disks, system info, flow bandwidth stats and per-appliance
  interface state) read from the EdgeConnect appliance itself through the
  Orchestrator appliance proxy (``/appliance/rest``), which reaches the
  appliances over the managed SD-WAN tunnel network — no direct WAN access to
  the appliances is required.

Operation ids are the stable catalog ids from the compatibility profiles
(9.3-9.6). The ``/stats/infrastructure/*`` debug endpoints exist only in the
9.6 profile and are fetched via raw path when the id is unavailable.
"""
from __future__ import annotations

from typing import Any

INFRASTRUCTURE_PLATFORM_INFO_READ = "get_platforminfo"
INFRASTRUCTURE_HOSTNAME_READ = "get_hostname"
INFRASTRUCTURE_IP_ADDRESS_READ = "get_ipaddress"
INFRASTRUCTURE_OS_FLAVOR_READ = "get_osflavorversion"
INFRASTRUCTURE_IS_CONTAINER_READ = "validates_container"

ORCHESTRATOR_DISK_SPACE_READ = "orchestrator.getapproximatediskspace333"
ORCHESTRATOR_DB_PARTITION_READ = "orchestrator.dbpartition208"
ORCHESTRATOR_GMS_SERVER_INFO_READ = "orchestrator.gmsserverinfo402"
ORCHESTRATOR_VERSIONS_READ = "orchestrator.versioninfo357"
ORCHESTRATOR_STATS_COLLECTOR_STATUS_READ = (
    "orchestrator.gethealthstatusofallstatscollectors726"
)
ORCHESTRATOR_STATS_RETENTION_READ = "orchestrator.statisticsretention338"
ORCHESTRATOR_INTERFACE_STATE_READ = "orchestrator.interfacestate423"
ORCHESTRATOR_APPLIANCE_PERFORMANCE_READ = "orchestrator.stats_timeseries_appliance665"
ORCHESTRATOR_CPU_TIMESERIES_READ = "orchestrator.appliancecputimeseriesstatsget1"
ORCHESTRATOR_MEMORY_METRICS_READ = "orchestrator.getstatsmemory690"

APPLIANCE_REALTIME_STATS_READ = "appliance.realtimestats885790"
APPLIANCE_HEALTH_READ = "appliance.health"
APPLIANCE_DISK_USAGE_READ = "appliance.diskusage783507"
APPLIANCE_DISKS_READ = "appliance.disksget573914"
APPLIANCE_SYSTEM_INFO_READ = "appliance.systeminfo841729"
APPLIANCE_SYSTEM_READ = "appliance.system506453"
APPLIANCE_FLOW_BANDWIDTH_STATS_READ = "appliance.flowbandwidthstats59434"

REALTIME_STATS_TYPES = (
    "tunnel", "port", "port_pair", "boosted_tunnel", "shaper",
    "traffic_type", "traffic_class", "dscp", "flow", "drops", "interface",
)
REALTIME_STAT_FILTERS = {
    "all": 0,
    "average": 1,
    "peak": 2,
}


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def first_payload_value(payload: Any) -> Any:
    """Unwrap common Orchestrator response shapes ({"data": [...]}, lists, scalars)."""
    if isinstance(payload, dict):
        if "data" in payload:
            return payload["data"]
        if "result" in payload:
            return payload["result"]
    return payload


def build_realtime_stats_body(
    target_type: str,
    name: str,
    filter_mode: str,
    count: int,
) -> dict[str, Any]:
    """Build the POST /stats/realtimeStats body (per-second live appliance stats).

    The appliance expects ``{"type": <str>, "name": <str>}`` plus ``filter``/``count``
    for the categories that support them (per the 10.0 official examples).
    """
    normalized_type = (target_type or "tunnel").strip().lower() or "tunnel"
    if normalized_type not in REALTIME_STATS_TYPES:
        raise ValueError(
            f"Invalid realtime stats type {target_type!r}; accepted: "
            + ", ".join(REALTIME_STATS_TYPES)
        )
    normalized_filter = (filter_mode or "all").strip().lower() or "all"
    if normalized_filter not in REALTIME_STAT_FILTERS:
        raise ValueError(
            f"Invalid realtime stats filter {filter_mode!r}; accepted: "
            + ", ".join(sorted(REALTIME_STAT_FILTERS))
        )
    body: dict[str, Any] = {
        "type": normalized_type,
        "name": name or "",
    }
    if normalized_type in ("drops",):
        return body
    body["filter"] = REALTIME_STAT_FILTERS[normalized_filter]
    body["count"] = max(1, count)
    return body
    return body


def summarize_realtime_stats(payload: Any) -> list[dict[str, Any]]:
    """Flatten realtime stats responses (list of rows or {"stats": [...]}) into rows."""
    rows = first_payload_value(payload)
    if isinstance(rows, dict):
        rows = next(
            (rows[key] for key in ("stats", "rows", "data", "results") if key in rows),
            [rows],
        )
    if not isinstance(rows, list):
        rows = [rows]
    return [row for row in rows if isinstance(row, dict)]


def summarize_interface_state(payload: Any) -> list[dict[str, Any]]:
    """Normalize GET /interfaceState rows (list or {"interfaceState": [...]})."""
    rows = first_payload_value(payload)
    if isinstance(rows, dict):
        rows = next(
            (rows[key] for key in ("interfaceState", "data", "interfaces") if key in rows),
            [rows],
        )
    if not isinstance(rows, list):
        rows = [rows]
    return [row for row in rows if isinstance(row, dict)]


def summarize_disks(payload: Any) -> list[dict[str, Any]]:
    rows = first_payload_value(payload)
    if isinstance(rows, dict):
        rows = next((rows[key] for key in ("disks", "data") if key in rows), [rows])
    if not isinstance(rows, list):
        rows = [rows]
    return [row for row in rows if isinstance(row, dict)]


def summarize_cpu_timeseries(payload: Any, limit: int = 10) -> list[dict[str, Any]]:
    """Keep the most recent CPU timeseries datapoints per entry."""
    rows = first_payload_value(payload)
    if not isinstance(rows, list):
        rows = [rows] if isinstance(rows, dict) else []
    kept: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        series = row.get("cpuUtilization") or row.get("data") or row.get("values")
        if isinstance(series, list):
            row = {k: v for k, v in row.items() if k not in ("cpuUtilization", "data", "values")}
            row["latest_samples"] = series[-max(1, limit):]
        kept.append(row)
    return kept


def summarize_performance_timeseries(payload: Any, limit: int = 10) -> list[dict[str, Any]]:
    """Keep the most recent per-appliance performance (throughput) samples."""
    rows = first_payload_value(payload)
    if not isinstance(rows, list):
        rows = [rows] if isinstance(rows, dict) else []
    kept: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("data", "values", "samples", "series"):
            series = row.get(key)
            if isinstance(series, list) and series:
                row = {k: v for k, v in row.items() if k != key}
                row["latest_samples"] = series[-max(1, limit):]
                break
        kept.append(row)
    return kept
