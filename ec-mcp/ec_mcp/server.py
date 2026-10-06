from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
from collections import deque
from threading import Lock
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as FastMCP

from .audit import AuditLog
from .build import build_info
from .cli_catalog import (
    catalog_entries,
    total_commands,
)
from .compat import CompatibilityEngine, is_read_only_operation, load_profiles, render_path
from .config import Settings
from .edgeconnect_evidence import (
    ENDPOINT_ASSOCIATIONS,
    FLOW_DETAILS,
    IPSLA_SETTINGS,
    REMOTE_ENDPOINTS,
    SERVICE_PROVIDERS,
    bounded_id,
    flow_evidence,
    service_evidence,
)
from .hpe_sse import SSE_RESOURCES, SSEAdminClient
from .orchestrator_client import OrchestratorClient
from .overlay_workflow import (
    OverlayPlanStore,
    extract_created_overlay_id,
    extract_overlays,
    prepare_overlay_plan,
    select_overlay,
)
from .security import (
    SecurityError,
    redact_sensitive_values,
    validate_cli_command,
    validate_show_command,
)
from .security_remediation import (
    DDOS_READ,
    IDS_STATE_READ,
    SecurityPlanStore,
    fingerprint,
    prepare_security_plan,
    security_write_guard,
    validate_ddos_snapshot,
    validate_ids_snapshot,
)
from .security_workflow import (
    BFD_SESSIONS_READ,
    BGP_NEIGHBOR_READ,
    BONDED_TUNNELS_STATE_READ,
    DDOS_PROTECTION_PROFILE_READ,
    DDOS_THRESHOLD_STATUS_READ,
    DEPLOYMENT_CONFIG_READ,
    IDS_IPS_EVENTS_READ,
    IDS_IPS_STATE_READ,
    SECURITY_MAP_SETTINGS_READ,
    SECURITY_MAPS_READ,
    SSE_PROVIDERS,
    THIRD_PARTY_TUNNELS_STATE_READ,
    TUNNELS_CONFIG_AND_STATE_READ,
    ZONE_LIST_READ,
    extract_rows,
    extract_sse_status,
    summarize_bgp_neighbors,
    summarize_ddos,
    summarize_ids_state,
    summarize_tunnels,
    summarize_zone_matrix,
)
from .ssh_ecos import ApplianceSshPool
from .ztp_workflow import (
    TEMPLATE_GROUPS_READ,
    ZTP_APPROVE_OPERATION,
    ZTP_DENY_OPERATION,
    ZTP_DISCOVERED_READ,
    ZTP_PRECONFIG_APPLY,
    ZTP_PRECONFIG_CREATE,
    ZTP_PRECONFIG_DELETE,
    ZTP_PRECONFIG_STATUS,
    ZTP_PRECONFIG_VALIDATE,
    ZTP_PRECONFIGS_READ,
    ZtpBulkPlan,
    ZtpPlan,
    ZtpPlanStore,
    extract_discovered,
    extract_preconfig_id,
    find_preconfig_id_by_name,
    normalize_serial,
    prepare_ztp_plan,
    render_bulk_yaml,
    select_discovered,
)


def guard_partial_deployment_body(body: dict | None) -> None:
    """Refuse a confirmed POST /deployment body that omits sections of a live deployment.

    Live finding (EC3 16.NE): POST /deployment is a full REPLACE, not a merge. A
    minimized body (e.g. only sysConfig.license) wiped every LAN/WAN interface
    (modeIfs) of an approved appliance. The contract-correct flow is:
    GET /deployment -> clone the whole object -> modify only what is needed -> POST.
    """
    if not body:
        return
    missing = [key for key in ("modeIfs", "sysConfig") if key not in body]
    if missing:
        raise SecurityError(
            "Refusing a confirmed POST /deployment: the body is a full REPLACE of the "
            "appliance deployment, but it is missing required sections: "
            + ", ".join(missing)
            + ". Live incident: a partial body wiped every LAN/WAN interface of an "
            "approved appliance. Always GET /deployment first, clone the complete "
            "object (modeIfs, sysConfig, dhcpFailover, dpRoutes), modify only what "
            "needs to change, and POST the full body."
        )


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.from_env()
    engine = CompatibilityEngine(load_profiles(settings.profiles_dir))
    audit = AuditLog(settings.audit_log_path)
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    try:
        server_version = pkg_version("ec-mcp")
    except PackageNotFoundError:
        server_version = "0.1.0.dev"
    mcp = FastMCP("edgeconnect-sdwan", version=server_version)

    cli_risk_by_command: dict[str, str] = {}
    for entry in catalog_entries():
        cli_risk_by_command[entry["command"]] = entry["risk"]

    shared_client: OrchestratorClient | None = None
    overlay_plans = OverlayPlanStore()
    ztp_plans = ZtpPlanStore(state_dir=os.environ.get("EC_ZTP_STATE_DIR", ""))
    ztp_bulk_plans: dict[str, ZtpBulkPlan] = {}
    security_plans = SecurityPlanStore()

    def require_client() -> OrchestratorClient | None:
        nonlocal shared_client
        if shared_client is not None:
            return shared_client
        try:
            shared_client = OrchestratorClient(settings, engine)
            return shared_client
        except ValueError as error:
            audit.record(
                "orchestrator_client",
                "init",
                settings.orchestrator_url or "(unset)",
                f"not configured: {error}",
            )
            return None

    DANGEROUS_OPERATION_PATTERN = re.compile(
        r"(?i)reboot|restart|reload|reset|erase|clear|suspend|delete|remove|wipe|factory|purge|halt|shutdown|decommission"
    )
    write_timestamps: deque[float] = deque()
    write_lock = Lock()

    def require_writes(operation: str = "", *, execute: bool = True) -> None:
        if not settings.allow_write_tools:
            raise SecurityError("Write tools are disabled (EC_ALLOW_WRITE_TOOLS != true)")
        if operation and DANGEROUS_OPERATION_PATTERN.search(operation):
            if not settings.allow_dangerous_writes:
                raise SecurityError(
                    f"Operation '{operation}' is classified as dangerous and requires "
                    "EC_ALLOW_DANGEROUS_WRITES=true"
                )
        if not execute:
            return
        with write_lock:
            now = time.monotonic()
            while write_timestamps and now - write_timestamps[0] > 60.0:
                write_timestamps.popleft()
            if len(write_timestamps) >= settings.max_writes_per_minute:
                raise SecurityError(
                    f"Write rate limit reached (max {settings.max_writes_per_minute} per minute)"
                )
            write_timestamps.append(now)

    def json_result(payload, max_chars: int) -> str:
        # Reuse the closed serializer so every helper response remains valid JSON.
        return closed_json_result(payload, max_chars)[0]

    def closed_json_result(payload: dict, max_chars: int) -> tuple[str, bool]:
        """Serialize to JSON that is ALWAYS valid: never returns a cut string.

        If the payload exceeds max_chars, wraps it with explicit truncation
        metadata instead of slicing the serialized text mid-literal.
        """
        text = json.dumps(redact_sensitive_values(payload), ensure_ascii=False, default=str)
        if len(text) <= max_chars:
            return text, False
        budget = max_chars - 256
        if isinstance(payload.get("versions"), dict):
            shrunk = json.loads(text)
            total_entries = sum(
                len(b.get("operations", {}))
                for b in shrunk.get("versions", {}).values()
                if isinstance(b.get("operations"), dict)
            )
            if total_entries:
                base_overhead = len(text) - sum(
                    len(json.dumps(b.get("operations", {}), ensure_ascii=False, default=str))
                    for b in shrunk.get("versions", {}).values()
                    if isinstance(b.get("operations"), dict)
                )
                per_entry = (len(text) - base_overhead) / max(1, total_entries)
                keep_total = max(1, int((budget - base_overhead) / max(per_entry, 1)))
                for v in list(shrunk.get("versions", {})):
                    body = shrunk["versions"][v]
                    entries = body.get("operations")
                    if not isinstance(entries, dict) or not entries:
                        continue
                    keep = max(1, keep_total // max(1, len(shrunk["versions"])))
                    body["operations"] = {k: entries[k] for k in list(entries)[:keep]}
                    body["page_size_adjusted"] = keep
                trimmed_text = json.dumps(shrunk, ensure_ascii=False, default=str)
                if len(trimmed_text) <= max_chars:
                    return trimmed_text, True
        wrapper = {"truncated": True, "max_chars": max_chars}
        wrapper["hint"] = "Payload exceeded max_chars; reduce the result with fields/limit or raise max_chars."
        wrapper["excerpt"] = text[: max(0, budget)]
        return json.dumps(wrapper, ensure_ascii=False, default=str), True

    def paginate_data(data: Any, offset: int, limit: int | None, fields: list[str]) -> tuple[dict, bool]:
        """Client-side pagination over a list payload, with explicit metadata."""
        if isinstance(data, list):
            total = len(data)
            items = data[offset : offset + limit] if limit is not None else data[offset:]
        elif isinstance(data, dict) and isinstance(next((v for v in data.values() if isinstance(v, list)), None), list):
            list_key = next(k for k, v in data.items() if isinstance(v, list))
            total = len(data[list_key])
            if fields:
                data[list_key] = [
                    {k: item.get(k) for k in fields if isinstance(item, dict) and k in item}
                    for item in data[list_key]
                ]
            items = data[list_key][offset : offset + limit] if limit is not None else data[list_key][offset:]
            return {list_key: items, "total_count": total, "offset": offset,
                    "returned": len(items),
                    "next_offset": (offset + len(items)) if offset + len(items) < total else None}, False
        else:
            if fields and isinstance(data, dict):
                data = {k: v for k, v in data.items() if k in fields}
            return data, False
        if fields:
            items = [
                {k: item.get(k) for k in fields if isinstance(item, dict) and k in item}
                for item in items
            ]
        paginated = {
            "data": items,
            "total_count": total,
            "offset": offset,
            "returned": len(items),
            "next_offset": (offset + len(items)) if offset + len(items) < total else None,
        }
        return paginated, False

    def _sanitize_example(value):
        if isinstance(value, str):
            return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)[:1000]
        return value

    def operation_details(version: str, operation_id: str) -> dict:
        profile = engine._profiles[version]
        operation = profile["operations"][operation_id]
        return {
            "operation": operation_id,
            "method": operation["method"],
            "path": operation["path"],
            "risk": operation.get("risk"),
            "path_params": operation.get("path_params", []),
            "query_params": operation.get("query_params", []),
            "body_example": _sanitize_example(operation.get("body_example")),
        }

    def build_params(version: str, operation_id: str, appliance_id: str, group_id: str, interface_name: str, extras: dict) -> tuple[dict, dict]:
        operation = engine._profiles[version]["operations"][operation_id]
        path_params: dict[str, str] = {}
        query_params: dict[str, str] = {}
        source = {
            "appliance_id": appliance_id,
            "group_id": group_id,
            "interface_name": interface_name,
            **extras,
        }
        for alias, canonical in (("startTime", "start_time"), ("endTime", "end_time"), ("nePk", "appliance_id"), ("ne", "appliance_id"), ("name", "appliance_id")):
            if alias in source and not source.get(canonical):
                source[canonical] = source[alias]
            if alias not in source and source.get(canonical):
                source[alias] = source[canonical]
        for name in operation.get("path_params", []):
            value = source.get(name)
            if value is None or value == "":
                raise SecurityError(f"Missing required path parameter '{name}' for operation '{operation_id}'")
            path_params[name] = str(value)
        for name in operation.get("query_params", []):
            value = source.get(name)
            if value is not None and value != "":
                query_params[name] = str(value).lower() if isinstance(value, bool) else str(value)
        return path_params, query_params

    def normalize_ne_pk(value: str) -> str:
        candidate = value.strip()
        if not candidate:
            return ""
        if re.fullmatch(r"\d+\.NE", candidate, re.IGNORECASE):
            return candidate.upper()
        match = re.fullmatch(r"(\d+)(?:\.NE)?", candidate)
        if match:
            return f"{match.group(1)}.NE"
        return ""

    def resolve_ne_pk(client: OrchestratorClient, appliance_id: str) -> str:
        candidate = appliance_id.strip()
        if candidate.lower() == "all":
            candidates = [str(a.get("nePk")) for a in client.list_appliances() if a.get("nePk")]
            if not candidates:
                raise SecurityError(
                    "No appliances registered in the Orchestrator inventory; "
                    "cannot expand 'all'."
                )
            return candidates[0]
        direct = normalize_ne_pk(candidate)
        if direct:
            return direct
        for appliance in client.list_appliances():
            if candidate.lower() in (
                str(appliance.get("name") or "").lower(),
                str(appliance.get("ip") or "").lower(),
                str(appliance.get("nePk") or "").lower(),
                str(appliance.get("serial_number") or "").lower(),
            ):
                return str(appliance.get("nePk"))
        raise SecurityError(
            f"Could not resolve '{appliance_id}' to a known appliance nePk. "
            "Use list_appliances to discover the registered appliances."
        )

    def resolve_ne_pks(client: OrchestratorClient, appliance_ids: str) -> list[str]:
        if not appliance_ids.strip() or appliance_ids.strip().lower() == "all":
            return list(dict.fromkeys(str(a["nePk"]) for a in client.list_appliances() if a.get("nePk")))
        resolved = []
        for part in appliance_ids.split(","):
            part = part.strip()
            if part:
                resolved.append(resolve_single_target(client, part))
        return list(dict.fromkeys(resolved))

    def resolve_single_target(client: OrchestratorClient, appliance_id: str) -> str:
        candidate = appliance_id.strip()
        if not candidate or candidate.lower() == "all" or "," in candidate:
            raise SecurityError("This operation requires one explicit appliance target; all, empty and comma-separated selectors are refused")
        direct = normalize_ne_pk(candidate)
        if direct:
            return direct
        matches = {
            str(appliance["nePk"])
            for appliance in client.list_appliances()
            if appliance.get("nePk") and candidate.casefold() in {
                str(appliance.get(key) or "").casefold() for key in ("name", "ip", "nePk", "serial_number")
            }
        }
        if len(matches) != 1:
            raise SecurityError("Appliance target is unknown or ambiguous; use an explicit nePk")
        return matches.pop()

    KPI_ENDPOINTS: dict[str, dict[str, Any]] = {
        "availability": {"paths": ["/stats/aggregate/availability/appliance", "/availability/appliance"]},
        "availability_tunnel": {"paths": ["/stats/aggregate/availability/tunnel"]},
        "mos": {"paths": ["/stats/aggregate/mos"]},
        "latency": {"paths": ["/stats/aggregate/tunnel"]},
        "top_talkers": {"paths": ["/stats/aggregate/topTalkers", "/stats/aggregate/topTalkers/split"]},
        "tunnel_state": {"paths": ["/tunnelsConfigAndState"], "appliance_level": True},
        "brownout": {"paths": ["/tunnelsConfigAndState"], "appliance_level": True},
        "ha_status": {"paths": ["/appliance/haPeerMeta", "/haGroups", "/vrrp"]},
        "firmware": {"paths": ["/appliancesSoftwareVersions", "/systemInfo"]},
        "ztp": {"paths": ["/spPortal/ztp", "/appliance/discovered"]},
        "reachability": {"paths": ["/reachability/appliance"]},
    }

    KPI_NO_ENDPOINT = (
        "per-application consumption/performance/QoE/Business-Intent/SLA violations "
        "(official KPI matrix rows 45-49) have no API endpoint yet; they are flagged "
        "as 'further development' by the vendor documentation."
    )

    def _default_stats_window(kpi: str, granularity: str, start_time: str, end_time: str) -> tuple[str, str]:
        if kpi not in ("latency", "mos", "availability", "availability_tunnel", "top_talkers"):
            return start_time, end_time
        if start_time and end_time:
            return start_time, end_time
        now = int(time.time())
        window = {"minute": 60, "5minute": 300, "hour": 3600, "day": 86400}.get(granularity or "hour", 3600)
        return str(now - window), str(now)

    def kpi_get(client: OrchestratorClient, kpi: str, ne_pk: str = "", granularity: str = "", start_time: str = "", end_time: str = "") -> Any:
        spec = KPI_ENDPOINTS[kpi]
        start_time, end_time = _default_stats_window(kpi, granularity, start_time, end_time)
        query = {k: v for k, v in {"nePk": ne_pk, "granularity": granularity, "startTime": start_time, "endTime": end_time}.items() if v}
        last_error: Exception | None = None
        results: list[Any] = []
        for path in spec["paths"]:
            try:
                if spec.get("appliance_level") and ne_pk:
                    results.append(client.appliance_api_get(ne_pk, path, **{k: v for k, v in query.items() if k != "nePk"}))
                else:
                    results.append(client.get_raw(path, **query))
            except RuntimeError as error:
                last_error = error
                if "HTTP 404" not in str(error) and "HTTP 400" not in str(error):
                    raise
        if results:
            return results if len(results) > 1 else results[0]
        raise last_error or RuntimeError(f"No endpoint available for KPI {kpi}")

    def reachability_map(client: OrchestratorClient) -> dict[str, str]:
        try:
            data = kpi_get(client, "reachability")
            rows = data if isinstance(data, list) else (data or {}).get("data") or []
            return {str(r.get("nePk") or r.get("ne")): str(r.get("reachability") or r.get("state") or "") for r in rows if isinstance(r, dict)}
        except Exception:
            return {}

    def kpi_alarm_counts(client: OrchestratorClient, ne_pk: str = "") -> Any:
        for path in ("/alarm/count/appliance",):
            try:
                return client.get_raw(path, **({"nePk": ne_pk} if ne_pk else {}))
            except RuntimeError as error:
                if "HTTP 404" not in str(error):
                    raise
        return {"data": None, "reason": "alarm count endpoint not available on this Orchestrator version"}

    ALARM_SEVERITIES = ("critical", "major", "minor", "warning", "info", "cleared")

    NUM_OF_SEVERITY_RE = re.compile(r"^numOf(Critical|Major|Minor|Warning|Info|Cleared)Alarms$", re.IGNORECASE)

    def _alarm_count_value(value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return 0
        return 0

    def _collect_alarm_counts(node: Any, severity_counts: dict[str, int], severity_context: str = "") -> int:
        """Recursively extract alarm counts from any payload shape.

        Handles: severity-keyed counters ({"critical": 3}), rows with
        severity + numOfAlarms, nested data lists, and string values.
        Returns the total number of alarms found in this subtree.
        """
        total = 0
        if isinstance(node, list):
            for item in node:
                total += _collect_alarm_counts(item, severity_counts, severity_context)
            return total
        if not isinstance(node, dict):
            return 0
        row_severity = str(node.get("severity") or node.get("alarmSeverity") or severity_context or "").lower()
        counted_as_severity_row = False
        has_severity_counters = any(NUM_OF_SEVERITY_RE.match(str(key)) for key in node)
        for key, value in node.items():
            lowered = str(key).lower()
            severity_match = NUM_OF_SEVERITY_RE.match(str(key))
            if severity_match and not isinstance(value, (dict, list)):
                count = _alarm_count_value(value)
                if count:
                    severity = severity_match.group(1).lower()
                    severity_counts[severity] = severity_counts.get(severity, 0) + count
                    total += count
                    counted_as_severity_row = True
                if has_severity_counters:
                    for missing in ("critical", "major", "minor", "warning"):
                        severity_counts.setdefault(missing, 0)
            elif lowered in ALARM_SEVERITIES and not isinstance(value, (dict, list)):
                count = _alarm_count_value(value)
                if count:
                    severity_counts[lowered] = severity_counts.get(lowered, 0) + count
                    total += count
                    counted_as_severity_row = True
            elif lowered == "numofalarms":
                if has_severity_counters:
                    continue
                count = _alarm_count_value(value)
                if count:
                    severity = row_severity if row_severity in ALARM_SEVERITIES else "total"
                    severity_counts[severity] = severity_counts.get(severity, 0) + count
                    total += count
                    counted_as_severity_row = True
            elif isinstance(value, (dict, list)):
                total += _collect_alarm_counts(value, severity_counts, row_severity)
        if not counted_as_severity_row:
            for key in ("count", "total", "totalalarms"):
                if str(key).lower() in {k.lower() for k in node}:
                    count = _alarm_count_value(node.get(key))
                    if count:
                        severity = row_severity if row_severity in ALARM_SEVERITIES else "total"
                        severity_counts[severity] = severity_counts.get(severity, 0) + count
                        total += count
                    break
        return total

    def kpi_alarm_counts_aggregate(client: OrchestratorClient, targets: list[str]) -> dict[str, Any]:
        per_appliance: list[dict[str, Any]] = []
        total_by_severity: dict[str, int] = {}
        total = 0
        for ne_pk in targets:
            entry: dict[str, Any] = {"nePk": ne_pk}
            try:
                payload = kpi_alarm_counts(client, ne_pk)
                appliance_by_severity: dict[str, int] = {}
                appliance_total = _collect_alarm_counts(payload, appliance_by_severity)
                entry["total"] = appliance_total
                entry["by_severity"] = appliance_by_severity
                total += appliance_total
                for severity, count in appliance_by_severity.items():
                    total_by_severity[severity] = total_by_severity.get(severity, 0) + count
            except Exception as error:
                entry["error"] = str(error)[:200]
            per_appliance.append(entry)
        return {"per_appliance": per_appliance, "total_alarms": total, "by_severity": total_by_severity}

    TUNNEL_KPI_KEYS = (
        "tunnelname", "tunnel", "tunnelid", "overlayid", "nepk",
        "mos", "min_mos", "max_mos", "avg_mos",
        "max_jitter", "avg_tx_jitter", "max_pre_pct_loss", "max_post_pct_loss",
        "avg_tx_latency", "min_latency_min", "max_latency_max",
    )

    def project_tunnel_kpis(node: Any) -> Any:
        """Project tunnel stats to identifiers plus a bounded KPI allow-list.

        The Orchestrator returns very wide nested rows. Keeping only the
        documented KPI fields prevents the MCP transport budget from cutting
        an otherwise valid WAN-health response.
        """
        if isinstance(node, list):
            return [project_tunnel_kpis(item) for item in node]
        if not isinstance(node, dict):
            return node
        projected: dict[str, Any] = {}
        for key, value in node.items():
            lowered = str(key).lower()
            if lowered in TUNNEL_KPI_KEYS:
                projected[str(key)] = project_tunnel_kpis(value) if isinstance(value, (dict, list)) else value
            elif isinstance(value, dict):
                nested = project_tunnel_kpis(value)
                if nested:
                    projected[str(key)] = nested
            elif isinstance(value, list):
                nested = project_tunnel_kpis(value)
                if nested:
                    projected[str(key)] = nested
        return projected

    def project_wan_health_stats(payload: Any) -> Any:
        """Project stats aggregates: accepts list rows or dict-of-tunnels shapes.

        Handles GET /stats/aggregate/* responses that arrive as {"data": [rows]}
        or as {"data": {"<tunnelName>": {"<nePk>": {<kpi>...}}}} (tunnel-keyed
        dict per orchestrator version), always returning KPI-only structures.
        """
        if not isinstance(payload, (dict, list)):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return {k: project_tunnel_kpis(v) for k, v in payload["data"].items()}
        rows = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), list) else payload
        projected_rows = project_tunnel_kpis(rows)
        if isinstance(payload, dict) and payload.get("data") is projected_rows:
            return {**payload, "data": projected_rows}
        return projected_rows

    WAN_FIELD_ALIASES = {
        "appliance": {"nepk", "ne"},
        "tunnel": {"tunnel", "tunnelname", "tunnelid"},
        "latency": {"latency", "avg_latency", "max_latency_max", "min_latency_min"},
        "jitter": {"jitter", "avg_jitter", "max_jitter"},
        "loss": {"loss", "pre_pct_loss", "post_pct_loss", "max_pre_pct_loss", "max_post_pct_loss"},
        "mos": {"mos", "min_mos"},
        "overlay": {"overlay", "overlayid", "overlay_id"},
    }

    def _project_fields(node: Any, field_list: list[str]) -> Any:
        """Project friendly KPI names onto the raw field names returned by Orchestrator."""
        if isinstance(node, list):
            return [_project_fields(item, field_list) for item in node]
        if not isinstance(node, dict):
            return node
        wanted = set()
        for field in field_list:
            normalized = field.strip().lower()
            wanted.update(WAN_FIELD_ALIASES.get(normalized, {normalized}))
        kept = {
            key: _project_fields(value, field_list)
            for key, value in node.items()
            if str(key).lower() in wanted
        }
        nested = {
            key: _project_fields(value, field_list)
            for key, value in node.items()
            if isinstance(value, (dict, list))
        }
        nested = {key: value for key, value in nested.items() if value not in ({}, [])}
        if kept:
            return {**nested, **kept}
        if nested:
            return nested
        identifiers = {"tunnelname", "tunnel", "tunnelid", "nepk", "ne", "overlayid"}
        return {key: value for key, value in node.items() if str(key).lower() in identifiers}

    def brownout_state(payload: Any) -> list[dict[str, Any]]:
        rows = payload if isinstance(payload, list) else payload.get("tunnels") or payload.get("data") or [] if isinstance(payload, dict) else []
        result = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            state = str(item.get("state") or item.get("tunnelState") or "").lower()
            reason = item.get("brownoutReason") or item.get("brownout_reason")
            result.append({
                "tunnel": item.get("tunnelName") or item.get("name") or item.get("tunnelId"),
                "state": state or "unknown",
                "brownout": "brownout" in state or bool(reason),
                "reason": reason or ("loss/latency/jitter threshold exceeded" if "brownout" in state else None),
            })
        return result

    def _parse_json_object(raw: str, name: str) -> dict:
        if not raw.strip():
            return {}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise SecurityError(f"{name} must be a JSON object")
        return {str(k): v for k, v in parsed.items()}

    def classify_cli_command(command: str) -> str | None:
        lowered = command.strip().lower()
        if not lowered:
            return None
        for entry in sorted(cli_risk_by_command, key=len, reverse=True):
            if lowered == entry or lowered.startswith(entry + " "):
                return cli_risk_by_command[entry]
        return None

    def validate_catalog_command(command: str) -> tuple[str, str]:
        normalized = validate_cli_command(command)
        risk = classify_cli_command(normalized)
        if risk is None:
            raise SecurityError("Command not in the official ECOS CLI catalog")
        if risk == "read":
            normalized = validate_show_command(normalized)
        return normalized, risk

    def guard_cli_body(path: str, body: Any) -> None:
        if path not in {"/cli", "/cliMultiple", "/broadcastCli"}:
            return
        if not isinstance(body, dict):
            raise SecurityError("CLI body must be a JSON object")
        commands = body.get("commands") if path == "/cliMultiple" else [body.get("command")]
        if not isinstance(commands, list) or not commands or not all(isinstance(c, str) for c in commands):
            raise SecurityError("CLI body requires a non-empty command or commands list")
        for command in commands:
            normalized, _risk = validate_catalog_command(command)
            require_writes(normalized, execute=False)

    @mcp.tool()
    def orchestrator_info() -> str:
        """Detect the Orchestrator version and the matching API compatibility profile."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            detected = client.detect_version()
            matched = engine.match_version(detected)
            try:
                appliances = client.list_appliances()
            except Exception:
                appliances = []
            payload = {
                "build": build_info(),
                "detected_version": detected,
                "active_profile": matched,
                "available_profiles": engine.versions,
                "write_tools_enabled": settings.allow_write_tools,
                "ssh_enabled": settings.ssh_enabled,
                "cli_commands_available": total_commands(),
                "appliance_count": len(appliances),
                "appliances": [
                    {"nePk": a.get("nePk"), "name": a.get("name"), "ip": a.get("ip")}
                    for a in appliances
                ],
                "hint": "Use get_wan_health/get_mos/get_tunnel_state for KPIs; the nePk of every appliance is listed here.",
            }
            audit.record("orchestrator_info", "detect", settings.orchestrator_url, "ok", details=payload)
            return json_result(payload, settings.max_output_chars)
        except Exception as error:
            audit.record("orchestrator_info", "detect", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    def suggest_operations(version: str, operation_id: str, limit: int = 5) -> list[str]:
        candidates = engine._profiles[version]["operations"]
        lowered = operation_id.lower()
        exact_substring = [op for op in candidates if lowered in op.lower()]
        if exact_substring:
            return sorted(exact_substring, key=len)[:limit]
        tokens = [t for t in re.split(r"[._]", lowered) if t]
        scored = []
        for op in candidates:
            op_tokens = set(re.split(r"[._]", op.lower()))
            score = sum(1 for t in tokens if t in op_tokens)
            if score:
                scored.append((-score, len(op), op))
        return [op for _, _, op in sorted(scored)[:limit]]

    def operation_not_found_error(version: str, operation_id: str) -> str:
        suggestions = suggest_operations(version, operation_id)
        return json_result(
            {
                "error": "OPERATION_NOT_FOUND",
                "operation_id": operation_id,
                "version": version,
                "suggestions": suggestions,
                "hint": "Use list_api_operations with search/prefix to discover the exact operation IDs.",
            },
            settings.max_output_chars,
        )

    @mcp.tool()
    def list_api_operations(version: str = "", prefix: str = "", search: str = "", method: str = "",
                             page: int = 0, page_size: int = 200, include_examples: bool = False, mode: str = "") -> str:
        """List the stable API operation IDs, paginated and filterable. Defaults to the ACTIVE profile only (pass version='all' for every profile). Filters: search (substring on operation id AND path), prefix, method (GET/POST/PUT/DELETE). mode='index' returns a compact id -> path map (smallest payload). By default body_example is omitted; include_examples=true adds it. Response is always valid JSON with total_operations, page, has_more_page; call with page+1 for the next chunk."""
        try:
            if version and version != "all" and version not in engine._profiles:
                return f"Unknown version {version}. Available: {engine.versions}"
            if version == "all":
                versions = list(engine.versions)
            elif version:
                versions = [version]
            else:
                try:
                    client = require_client()
                    versions = [client.resolve_active_profile()] if client else list(engine.versions)
                except Exception:
                    versions = list(engine.versions)
            page = max(0, int(page))
            page_size = min(max(1, int(page_size)), 1000)
            payload: dict = {}
            has_more = False
            for v in versions:
                profile_ops = engine._profiles[v]["operations"]
                ranked_ops: list[tuple[int, str]] = []
                lowered_search = search.strip().lower()
                lowered_prefix = prefix.lower()
                search_terms = set(re.findall(r"[a-z0-9]+", lowered_search))
                search_terms.difference_update(
                    {"orchestrator", "appliance", "operation", "api", "get", "post", "put", "delete"}
                )
                semantic_aliases = {
                    "business": {"overlay"},
                    "intent": {"overlay"},
                    "bio": {"overlay"},
                    "ztp": {"spportal", "discovered", "preconfiguration"},
                    "discover": {"discovered"},
                    "latency": {"tunnel", "health"},
                    "loss": {"tunnel", "health"},
                    "jitter": {"tunnel", "health"},
                }
                expanded_terms = set(search_terms)
                for term in search_terms:
                    expanded_terms.update(semantic_aliases.get(term, set()))
                if "business intent" in lowered_search or lowered_search == "bio":
                    expanded_terms = {"overlay"}
                for op_id in sorted(profile_ops):
                    spec = profile_ops[op_id]
                    if lowered_prefix and not op_id.lower().startswith(lowered_prefix):
                        continue
                    haystack = f'{op_id} {spec["path"]}'.lower()
                    score = sum(1 for term in expanded_terms if term in haystack)
                    if lowered_search and lowered_search not in haystack and score == 0:
                        continue
                    if method and spec["method"].upper() != method.upper():
                        continue
                    ranked_ops.append((-score, op_id))
                ops = [op_id for _, op_id in sorted(ranked_ops)]
                start = page * page_size
                chunk = ops[start : start + page_size]
                has_more = has_more or start + page_size < len(ops)
                entries = {}
                for op in chunk:
                    spec = profile_ops[op]
                    if mode == "index":
                        entries[op] = spec["path"]
                        continue
                    entry = {
                        "operation": op,
                        "method": spec["method"],
                        "path": spec["path"],
                        "risk": spec.get("risk"),
                        "path_params": spec.get("path_params", []),
                        "query_params": spec.get("query_params", []),
                    }
                    if spec.get("deprecated"):
                        entry["deprecated"] = True
                        entry["notes"] = spec.get("notes", [])
                    if include_examples:
                        entry["body_example"] = _sanitize_example(spec.get("body_example"))
                    entries[op] = entry
                payload[v] = {
                    "total_operations": len(ops),
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (len(ops) + page_size - 1) // page_size,
                    "has_more_page": start + page_size < len(ops),
                    "operations": entries,
                }
            result = {"has_more_page": has_more, "versions": payload}
            result_text, truncated = closed_json_result(result, settings.max_output_chars * 2)
            if truncated:
                result = json.loads(result_text)
                result["truncated"] = truncated
                result["hint"] = ("Catalog page too large for the transport budget; "
                                   "retry with a smaller page_size, or with search/prefix filters.")
                result.pop("excerpt", None)
                result_text = json.dumps(result, ensure_ascii=False, default=str)
            else:
                result = json.loads(result_text)
                result["truncated"] = False
                result_text = json.dumps(result, ensure_ascii=False, default=str)
            audit.record("list_api_operations", "read", "profiles", "ok",
                         details={"prefix": prefix, "search": search, "page": page})
            return json.dumps(result, ensure_ascii=False)
        except Exception as error:
            audit.record("list_api_operations", "read", "profiles", f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def list_appliances() -> str:
        """List every appliance registered in the EdgeConnect Orchestrator (nePk, name, IP, model, software version, state). Use this first to discover the nePk/device names needed for per-appliance API calls and SSH commands."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            appliances = client.list_appliances(refresh=True)
            audit.record("list_appliances", "read", settings.orchestrator_url, "ok", details={"count": len(appliances)})
            return json_result({"count": len(appliances), "appliances": appliances}, settings.max_output_chars)
        except Exception as error:
            audit.record("list_appliances", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def orchestrator_metrics() -> str:
        """Return per-operation API performance metrics: calls, total/max latency seconds, bytes transferred and cache hits. Use it to spot slow operations and tune offset/limit/max_chars."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            rows = []
            for label, entry in sorted(client.metrics().items()):
                calls = int(entry.get("calls", 0))
                rows.append({
                    "operation": label,
                    "calls": calls,
                    "avg_seconds": round(entry.get("total_time", 0.0) / calls, 3) if calls else 0.0,
                    "max_seconds": round(entry.get("max_time", 0.0), 3),
                    "total_kb": round(entry.get("total_bytes", 0.0) / 1024, 1),
                    "cache_hits": int(entry.get("cache_hits", 0)),
                })
            return json_result({"count": len(rows), "metrics": rows}, settings.max_output_chars)
        except Exception as error:
            audit.record("orchestrator_metrics", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_wan_health(appliance_id: str = "", granularity: str = "hour", start_time: str = "", end_time: str = "", fields: str = "") -> str:
        """One-call WAN health snapshot: latency, jitter, loss and MOS per tunnel (already aggregated, no raw 70-column rows). appliance_id accepts comma-separated nePks/names/IPs; empty = all appliances. Pass fields to project only some columns."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            targets = resolve_ne_pks(client, appliance_id)
            rows = []
            for ne_pk in targets:
                try:
                    stats = kpi_get(client, "latency", ne_pk, granularity, start_time, end_time)
                    rows.append({"nePk": ne_pk, "stats": project_wan_health_stats(stats)})
                except Exception as error:
                    rows.append({"nePk": ne_pk, "error": str(error)[:200]})
            mos_rows = []
            for ne_pk in targets:
                try:
                    mos_rows.append({
                        "nePk": ne_pk,
                        "data": project_wan_health_stats(
                            kpi_get(client, "mos", ne_pk, granularity, start_time, end_time)
                        ),
                    })
                except Exception as error:
                    mos_rows.append({"nePk": ne_pk, "error": str(error)[:200]})
            mos = mos_rows
            reach = reachability_map(client)
            for row in rows:
                if "error" in row and reach:
                    state = reach.get(row.get("nePk"), "")
                    if state and state.lower() not in ("", "ok", "reachable", "up"):
                        row["reachability"] = state
                        row["hint"] = "Orchestrator reports degraded reachability for this appliance; the error may be reachability, not the endpoint."
            payload = {
                "appliances": rows,
                "mos": mos,
                "granularity": granularity,
                "kpi_without_endpoint": KPI_NO_ENDPOINT,
            }
            field_list = [f.strip() for f in fields.split(",") if f.strip()]
            if field_list:
                payload["appliances"] = [
                    {
                        "nePk": row.get("nePk"),
                        "stats": _project_fields(row.get("stats"), field_list),
                        **({k: v for k, v in row.items() if k in ("error", "reachability", "hint")}),
                    }
                    for row in payload["appliances"]
                ]
            payload["total_count"] = len(payload["appliances"])
            payload["truncated"] = False
            audit.record("get_wan_health", "read", settings.orchestrator_url, "ok", details={"appliances": len(targets)})
            return json_result(payload, settings.max_output_chars)
        except Exception as error:
            audit.record("get_wan_health", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_mos(appliance_id: str = "", granularity: str = "hour", start_time: str = "", end_time: str = "") -> str:
        """Voice MOS score per tunnel/appliance from GET /stats/aggregate/mos (values are typically scaled x100: 440 = MOS 4.40). Use start_time/end_time (epoch ms) and granularity to bound the window."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if appliance_id.strip().lower() in ("", "all"):
                targets = resolve_ne_pks(client, "all")
                rows = []
                for ne_pk in targets:
                    try:
                        rows.append({
                            "nePk": ne_pk,
                            "data": project_wan_health_stats(
                                kpi_get(client, "mos", ne_pk, granularity, start_time, end_time)
                            ),
                        })
                    except Exception as error:
                        rows.append({"nePk": ne_pk, "error": str(error)[:200]})
                payload = {"appliances": rows, "total_count": len(rows)}
            else:
                ne_pk = resolve_ne_pk(client, appliance_id)
                payload = project_wan_health_stats(
                    kpi_get(client, "mos", ne_pk, granularity, start_time, end_time)
                )
            audit.record("get_mos", "read", settings.orchestrator_url, "ok")
            return json_result({"data": payload, "note": "MOS values may be scaled x100 (440 = 4.40)"}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_mos", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_tunnel_state(appliance_id: str = "") -> str:
        """Tunnel state per appliance from /tunnelsConfigAndState (proxied via the Orchestrator)."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if not appliance_id:
                return json_result({"error": "PARAM_REQUIRED", "required_params": ["appliance_id"], "hint": "Pass one appliance or 'all'; use list_appliances to discover them."}, settings.max_output_chars)
            targets = resolve_ne_pks(client, appliance_id)
            rows = []
            for ne_pk in targets:
                try:
                    rows.append({"nePk": ne_pk, "data": kpi_get(client, "tunnel_state", ne_pk)})
                except Exception as error:
                    rows.append({"nePk": ne_pk, "error": str(error)[:200]})
            audit.record("get_tunnel_state", "read", settings.orchestrator_url, "ok", details={"appliances": len(rows)})
            return json_result({"appliances": rows, "total_count": len(rows)}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_tunnel_state", "read", appliance_id, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_brownout_state(appliance_id: str = "") -> str:
        """Brownout/blackout detection per tunnel with reason."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if not appliance_id:
                return json_result({"error": "PARAM_REQUIRED", "required_params": ["appliance_id"], "hint": "Pass one appliance or 'all'."}, settings.max_output_chars)
            targets = resolve_ne_pks(client, appliance_id)
            rows = []
            total_tunnels = 0
            for ne_pk in targets:
                try:
                    tunnels = brownout_state(kpi_get(client, "brownout", ne_pk))
                    total_tunnels += len(tunnels)
                    rows.append({"nePk": ne_pk, "tunnels": tunnels})
                except Exception as error:
                    rows.append({"nePk": ne_pk, "error": str(error)[:200]})
            payload = {"appliances": rows, "total_count": len(rows)}
            if total_tunnels == 0:
                payload["status"] = "SKIPPED_NO_ENTITY"
                payload["reason"] = "No tunnel brownout entities were reported by the lab."
            audit.record("get_brownout_state", "read", settings.orchestrator_url, "ok", details={"tunnels": total_tunnels})
            return json_result(payload, settings.max_output_chars)
        except Exception as error:
            audit.record("get_brownout_state", "read", appliance_id, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def troubleshoot_flows(appliance_id: str, application: str = "", ip: str = "", limit: int = 20) -> str:
        """One-call flow troubleshooting: top talkers, filtered flows and today's firewall log (allow/drop with Flow-ID) for one appliance, cross-correlated: drops found in the security log are matched against active flows. Use for 'app X does not work / is slow / is blocked' investigations."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if not appliance_id:
                return json_result({"error": "PARAM_REQUIRED", "required_params": ["appliance_id"]}, settings.max_output_chars)
            ne_pk = resolve_ne_pk(client, appliance_id)
            version = client.resolve_active_profile()
            result: dict[str, Any] = {"nePk": ne_pk}
            try:
                talks = kpi_get(client, "top_talkers", ne_pk, "hour", "", "")
                if isinstance(talks, list):
                    talks = talks[: max(0, limit)]
                result["top_talkers"] = talks
            except Exception as error:
                result["top_talkers_error"] = str(error)[:200]
            query: dict[str, Any] = {"nePk": ne_pk, "maxFlows": str(max(1, limit))}
            if application:
                query["application"] = application
            if ip:
                query["ipEitherFlag"] = "true"
                query["ip1"] = ip
            try:
                result["flows"] = client.call(version, "orchestrator.flows242", query_params=None, json_body=None, **query)
            except Exception as error:
                result["flows_error"] = str(error)[:200]
            try:
                from ec_mcp.security_workflow import (
                    LOG_VIEWER_FILE_READ,
                    parse_firewall_log_entries,
                    summarize_security_log,
                )
                today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                log_payload = client.appliance_api_call(
                    version, ne_pk, LOG_VIEWER_FILE_READ,
                    path_params={"logType": "Firewall", "date": today, "lines": str(max(50, limit * 5))},
                )
                entries = parse_firewall_log_entries(log_payload)
                drops = [e for e in entries if str(e.get("Action", "")).lower().startswith("drop")]
                if application:
                    drops = [e for e in drops if application.lower() in str(e.get("Application", "")).lower()]
                if ip:
                    drops = [e for e in drops if ip in (str(e.get("SrcAddr", "")), str(e.get("DstAddr", "")))]
                result["security_log"] = {
                    "date": today,
                    "total_entries": len(entries),
                    "drops": drops[: max(1, limit)],
                    "summary": summarize_security_log(entries),
                }
            except Exception as error:
                result["security_log_error"] = str(error)[:200]
            findings: list[str] = []
            drops = (result.get("security_log") or {}).get("drops") or []
            if drops:
                reasons = sorted({str(d.get("Reason", "")).strip() for d in drops if d.get("Reason")})[:5]
                findings.append(f"{len(drops)} drop event(s) found in today's firewall log — reasons: {'; '.join(reasons)}")
                policy_drops = [d for d in drops if "policy" in str(d.get("Reason", "")).lower()]
                if policy_drops:
                    zones = sorted({f"{d.get('FromZone','?')}->{d.get('ToZone','?')}" for d in policy_drops})
                    findings.append(f"Policy drops on zone pairs {', '.join(zones)} — review the zone matrix for these pairs")
            else:
                findings.append("No drops in today's firewall log — if traffic still fails, check reachability and routing")
            result["findings"] = findings
            audit.record("troubleshoot_flows", "read", settings.orchestrator_url, "ok", details={"drops": len(drops)})
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            audit.record("troubleshoot_flows", "read", appliance_id, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def troubleshoot_tunnel(appliance_id: str, granularity: str = "hour", start_time: str = "", end_time: str = "") -> str:
        """One-call tunnel troubleshooting: tunnel state, brownout reasons, WAN health KPIs (latency/jitter/loss/MOS) and reachability for one appliance, plus a prioritized diagnostic interpretation (tunnel down vs degraded vs healthy). Use it instead of calling get_tunnel_state + get_brownout_state + get_wan_health separately."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if not appliance_id:
                return json_result({"error": "PARAM_REQUIRED", "required_params": ["appliance_id"]}, settings.max_output_chars)
            ne_pk = resolve_ne_pk(client, appliance_id)
            result: dict[str, Any] = {"nePk": ne_pk}
            tunnels: list[dict[str, Any]] = []
            try:
                tunnels = kpi_get(client, "tunnel_state", ne_pk)
                result["tunnels_raw_count"] = len(tunnels) if isinstance(tunnels, list) else None
            except Exception as error:
                result["tunnel_state_error"] = str(error)[:200]
            try:
                brownouts = brownout_state(kpi_get(client, "brownout", ne_pk))
                result["brownout"] = brownouts
            except Exception as error:
                result["brownout_error"] = str(error)[:200]
            try:
                stats = project_wan_health_stats(kpi_get(client, "latency", ne_pk, granularity, start_time, end_time))
                result["wan_health"] = stats
            except Exception as error:
                result["wan_health_error"] = str(error)[:200]
            reach = reachability_map(client)
            state = reach.get(ne_pk, "")
            if state:
                result["reachability"] = state
            findings: list[str] = []
            tunnels_list = tunnels if isinstance(tunnels, list) else []
            down_admin = [t for t in tunnels_list if isinstance(t, dict) and str(t.get("adminState") or t.get("admin") or "").lower() in ("down", "disabled", "false")]
            down_oper = [t for t in tunnels_list if isinstance(t, dict) and str(t.get("state") or t.get("status") or "").lower() == "down"]
            brownout_rows = result.get("brownout") or []
            active_brownouts = [b for b in brownout_rows if isinstance(b, dict) and b.get("brownout")]
            if down_admin:
                findings.append(f"{len(down_admin)} tunnel(s) are administratively down — verify intent before treating as failure")
            if down_oper:
                names = [str(t.get("tunnelName") or t.get("name") or t.get("tunnelId")) for t in down_oper[:5]]
                findings.append(f"{len(down_oper)} tunnel(s) operationally DOWN ({', '.join(names)}) — check transport/NAT-D; use traceroute under the tunnel to find the failing hop")
            if active_brownouts:
                reasons = sorted({str(b.get("reason")) for b in active_brownouts if b.get("reason")})
                findings.append(f"{len(active_brownouts)} tunnel(s) in brownout — reason: {'; '.join(reasons) if reasons else 'loss/latency/jitter threshold exceeded'}")
            if not down_oper and not active_brownouts and tunnels_list:
                findings.append("No tunnels down and no active brownouts — tunnel plane looks healthy")
            if not tunnels_list and "tunnel_state_error" not in result:
                findings.append("No tunnel entities reported — appliance may have no tunnels configured or reachability issues")
            if state and state.lower() not in ("", "ok", "reachable", "up"):
                findings.append(f"Orchestrator reports reachability '{state}' for this appliance — errors may be reachability, not the endpoint")
            result["findings"] = findings
            audit.record("troubleshoot_tunnel", "read", settings.orchestrator_url, "ok", details={"findings": len(findings)})
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            audit.record("troubleshoot_tunnel", "read", appliance_id, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_availability(appliance_id: str = "", granularity: str = "hour", start_time: str = "", end_time: str = "") -> str:
        """Availability per appliance/site from GET /stats/aggregate/availability/appliance (fallback /availability/appliance)."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            ne_pk = resolve_ne_pk(client, appliance_id) if appliance_id else ""
            payload = kpi_get(client, "availability", ne_pk, granularity, start_time, end_time)
            audit.record("get_availability", "read", settings.orchestrator_url, "ok")
            return json_result({"data": payload, "granularity": granularity}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_availability", "read", settings.orchestrator_url, f"error: {error}")
            if "HTTP 404" in str(error):
                return json_result({
                    "status": "SKIPPED_NO_ENTITY",
                    "reason": "Availability endpoint/entity is not exposed by this lab Orchestrator.",
                    "endpoint_candidates": KPI_ENDPOINTS["availability"]["paths"],
                }, settings.max_output_chars)
            return f"Error: {error}"

    @mcp.tool()
    def get_top_talkers(appliance_id: str = "", granularity: str = "hour", start_time: str = "", end_time: str = "", limit: int = 20) -> str:
        """Top talker applications/hosts from GET /stats/aggregate/topTalkers. Use it instead of pulling raw /flow rows."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            ne_pk = resolve_ne_pk(client, appliance_id) if appliance_id else ""
            payload = kpi_get(client, "top_talkers", ne_pk, granularity, start_time, end_time)
            if isinstance(payload, list) and limit:
                payload = payload[: max(0, limit)]
            audit.record("get_top_talkers", "read", settings.orchestrator_url, "ok")
            return json_result({"data": payload, "granularity": granularity}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_top_talkers", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_active_alarms(appliance_id: str = "") -> str:
        """Active alarm counts per appliance from /alarm/count/appliance (the /alarm/gms detail endpoint rejects view/severity filters — known upstream contract). appliance_id accepts 'all' (or empty) for every appliance, or a single nePk/name/IP; with 'all' the counts are aggregated per appliance and by severity. Use it for 'how many alarms are active right now' instead of alarm/gms."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if appliance_id.strip().lower() == "all":
                targets = resolve_ne_pks(client, "all")
                payload = kpi_alarm_counts_aggregate(client, targets)
            else:
                ne_pk = resolve_ne_pk(client, appliance_id) if appliance_id else ""
                payload = kpi_alarm_counts(client, ne_pk)
            audit.record("get_active_alarms", "read", settings.orchestrator_url, "ok")
            return json_result({"data": payload, "note": "Counts per appliance/severity; the alarm/gms detail endpoint only accepts from+to (epoch seconds) upstream."}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_active_alarms", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_ha_status(appliance_id: str = "") -> str:
        """High-availability status per appliance; missing HA is reported explicitly."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            targets = resolve_ne_pks(client, appliance_id) if appliance_id else [""]
            rows = []
            for ne_pk in targets:
                try:
                    rows.append({"nePk": ne_pk or None, "data": kpi_get(client, "ha_status", ne_pk)})
                except Exception as error:
                    rows.append({"nePk": ne_pk or None, "error": str(error)[:200]})
            audit.record("get_ha_status", "read", settings.orchestrator_url, "ok", details={"appliances": len(rows)})
            return json_result({"appliances": rows, "total_count": len(rows)}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_ha_status", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_firmware_compliance() -> str:
        """Firmware compliance per appliance from appliance-scoped software partitions."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            targets = resolve_ne_pks(client, "all")
            rows = []
            for ne_pk in targets:
                try:
                    rows.append({"nePk": ne_pk, "data": kpi_get(client, "firmware", ne_pk)})
                except Exception as error:
                    rows.append({"nePk": ne_pk, "error": str(error)[:200]})
            audit.record("get_firmware_compliance", "read", settings.orchestrator_url, "ok", details={"appliances": len(rows)})
            return json_result({"appliances": rows, "total_count": len(rows)}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_firmware_compliance", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def get_ztp_status(offset: int = 0, limit: int = 20, fields: str = "") -> str:
        """Zero-Touch Provisioning status with paginated, credential-free discovery rows."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            payload = kpi_get(client, "ztp")
            parts = payload if isinstance(payload, list) else [payload]
            manual = None
            discovered = []
            for part in parts:
                if isinstance(part, dict) and "enableManualProvisioning" in part:
                    manual = part.get("enableManualProvisioning")
                elif isinstance(part, list):
                    for item in part:
                        if not isinstance(item, dict):
                            continue
                        row = {key: item.get(key) for key in ("id", "uuid", "approved", "denied", "enabled", "discoveredTime") if key in item}
                        info = item.get("applianceInfo")
                        if isinstance(info, dict):
                            row["applianceInfo"] = {
                                key: info.get(key)
                                for key in ("hostname", "model", "serial", "softwareVersion", "site", "ip", "publicIp", "deviceType", "reachabilityStatus", "enabled")
                                if key in info
                            }
                        discovered.append(row)
            total = len(discovered)
            offset = max(0, int(offset))
            limit = min(max(1, int(limit)), 200)
            field_list = [field.strip() for field in fields.split(",") if field.strip()]
            page = discovered[offset : offset + limit]
            if field_list:
                page = [
                    {key: item.get(key) for key in field_list if key in item}
                    for item in page
                ]
            result = {
                "manual_provisioning": manual,
                "discovered_count": total,
                "discovered": page,
                "offset": offset,
                "returned": len(page),
                "next_offset": offset + len(page) if offset + len(page) < total else None,
            }
            audit.record("get_ztp_status", "read", settings.orchestrator_url, "ok", details={"discovered": total})
            return json_result({"data": result}, settings.max_output_chars)
        except Exception as error:
            audit.record("get_ztp_status", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def call_read_api(
        operation_id: str,
        appliance_id: str = "",
        group_id: str = "",
        start_time: str = "",
        end_time: str = "",
        granularity: str = "",
        extra_path_params_json: str = "",
        extra_query_params_json: str = "",
        fields: str = "",
        offset: int = 0,
        limit: int = 0,
        max_chars: int = 0,
    ) -> str:
        """Invoke a read-only Orchestrator/Appliance API operation by stable operation ID. Use list_api_operations(search=...) to find operation IDs, or list_appliances to get the appliances with their nePk. appliance_id accepts nePk, name, IP, serial, comma-separated list, or 'all' for every registered appliance (uses groupByNE when supported). Param formats: granularity=minute|5minute|hour|day (never numeric); start_time/end_time=epoch seconds (alarm endpoints) or epoch ms depending on endpoint — see the error hints. For list responses use fields (comma-separated columns), offset/limit and max_chars to page through data; the response is always complete valid JSON with pagination metadata (total_count, next_offset) — never a cut string."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            if operation_id not in engine._profiles[version]["operations"]:
                return operation_not_found_error(version, operation_id)
            spec = engine._profiles[version]["operations"][operation_id]
            if spec["method"].upper() != "GET" or not is_read_only_operation(spec):
                raise SecurityError(f"Operation '{operation_id}' is not read-only; use apply_change")
            multi_targets: list[str] = []
            if appliance_id.strip().lower() == "all" or "," in appliance_id:
                multi_targets = resolve_ne_pks(client, appliance_id)
                appliance_id = ""
                if not multi_targets:
                    return json_result({"data": [], "coverage_complete": False, "scope": "no_appliances_resolved"}, settings.max_output_chars)
            missing_required: list[str] = []
            granularity_hint = False
            needs_ne_pk = "nePk" in (spec.get("query_params") or []) or "nePk" in (
                spec.get("path_params") or []
            )
            if needs_ne_pk and not multi_targets and not appliance_id and "nePk" not in (
                json.dumps(_parse_json_object(extra_query_params_json, "extra_query_params_json"))
                if extra_query_params_json.strip()
                else ""
            ):
                missing_required.append("appliance_id (nePk)")
            declared_query = spec.get("query_params") or []
            used_appliance_proxy = False
            if (
                "/stats/" in spec["path"]
                and "/stats/infrastructure/" not in spec["path"]
                and "granularity" in declared_query
                and not granularity
            ):
                missing_required.append("granularity")
                granularity_hint = True
            if "/timeseries/" in spec["path"]:
                if not start_time and "startTime" in declared_query:
                    missing_required.append("start_time")
                if not end_time and "endTime" in declared_query:
                    missing_required.append("end_time")
            if missing_required:
                hint = "Provide the missing parameters; no upstream call was made."
                if granularity_hint or "granularity" in missing_required:
                    hint += " granularity accepts: minute | 5minute | hour | day (NOT numeric seconds like 3600)."
                if "start_time" in missing_required or "end_time" in missing_required:
                    hint += " start_time/end_time: epoch (seconds) for most stats endpoints; some accept ISO-8601."
                return json_result(
                    {
                        "error": "PARAM_REQUIRED",
                        "operation_id": operation_id,
                        "required_params": missing_required,
                        "hint": hint,
                    },
                    settings.max_output_chars,
                )
            operation = engine.resolve(version, operation_id)
            if operation.method != "GET":
                raise SecurityError(f"Operation '{operation_id}' is not read-only; use apply_change")
            path_params, query_params = build_params(
                version,
                operation_id,
                appliance_id or (multi_targets[0] if multi_targets else ""),
                group_id,
                "",
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "granularity": granularity,
                    **_parse_json_object(extra_path_params_json, "extra_path_params_json"),
                    **_parse_json_object(extra_query_params_json, "extra_query_params_json"),
                },
            )
            if operation_id.startswith("appliance.") and multi_targets:
                payload = []
                for target in multi_targets:
                    try:
                        per_path = dict(path_params)
                        for key in ("appliance_id", "nePk", "ne", "applianceId"):
                            if key in per_path:
                                per_path[key] = target
                        per_query = {key: value for key, value in query_params.items() if key != "nePk"}
                        proxy_path = render_path(operation.path, per_path)
                        payload.append({"nePk": target, "data": client.appliance_api_get(target, proxy_path, **per_query)})
                    except Exception as error:
                        payload.append({"nePk": target, "error": str(error)})
            elif operation_id.startswith("appliance."):
                if not appliance_id and not query_params.get("nePk"):
                    raise SecurityError("Appliance-scoped reads require appliance_id; use all for explicit fanout")
                needs_ne = "nePk" in (spec.get("query_params") or []) or "nePk" in (spec.get("path_params") or [])
                if needs_ne and not query_params.get("nePk"):
                    if not appliance_id:
                        return json_result(
                            {
                                "error": "PARAM_REQUIRED",
                                "operation_id": operation_id,
                                "required_params": ["appliance_id"],
                                "hint": "Appliance-scoped operation; pass appliance_id (nePk, name or IP; use list_appliances to discover them).",
                            },
                            settings.max_output_chars,
                        )
                    query_params["nePk"] = resolve_ne_pk(client, appliance_id)
                if operation_id == "orchestrator.appliancegetapi70" or (
                    not appliance_id and not query_params.get("nePk")
                ):
                    payload = client.call(version, operation_id, path_params=path_params, **query_params)
                else:
                    ne_pk = query_params.get("nePk") or resolve_ne_pk(client, appliance_id)
                    query_params.pop("nePk", None)
                    appliance_path = render_path(operation.path, {**path_params, "appliance_id": ne_pk})
                    if re.search(r"\{[^}]+\}", appliance_path):
                        missing = re.findall(r"\{([^}]+)\}", appliance_path)
                        return json_result(
                            {
                                "error": "PARAM_REQUIRED",
                                "operation_id": operation_id,
                                "required_params": missing,
                                "hint": "Pass the missing path parameters via extra_path_params_json.",
                            },
                            settings.max_output_chars,
                        )
                    payload = client.appliance_api_get(ne_pk, appliance_path, **query_params)
            else:
                declares_ne_pk = "nePk" in (spec.get("query_params") or []) or "nePk" in (spec.get("path_params") or [])

                def _call_orchestrator_op() -> Any:
                    if multi_targets:
                        results = []
                        for target in multi_targets:
                            per_query = dict(query_params)
                            if declares_ne_pk:
                                per_query["nePk"] = target
                                if "groupByNE" in (spec.get("query_params") or []):
                                    per_query.setdefault("groupByNE", "true")
                            try:
                                results.append({"nePk": target, "data": client.call(version, operation_id, path_params=path_params, **per_query)})
                            except Exception as per_error:
                                results.append({"nePk": target, "error": str(per_error)[:200]})
                        return results
                    if appliance_id and declares_ne_pk:
                        query_params.setdefault("nePk", resolve_ne_pk(client, appliance_id))
                        path_params.setdefault("nePk", query_params["nePk"])
                    return client.call(version, operation_id, path_params=path_params, **query_params)

                def _call_via_appliance_proxy() -> Any:
                    proxy_ne_pk = (query_params.get("nePk") if declares_ne_pk else "") or (
                        resolve_ne_pk(client, appliance_id) if appliance_id else resolve_ne_pk(client, "all")
                    )
                    proxy_path = render_path(operation.path, {**path_params, "appliance_id": proxy_ne_pk})
                    if re.search(r"\{[^}]+\}", proxy_path):
                        raise RuntimeError(str(last_orchestrator_error)[:200])
                    proxy_query = {k: v for k, v in query_params.items() if k != "nePk"}
                    return client.appliance_api_get(proxy_ne_pk, proxy_path, **proxy_query)

                last_orchestrator_error: Exception | None = None
                try:
                    payload = _call_orchestrator_op()
                except Exception as error:
                    last_orchestrator_error = error
                    payload = None
                    error_text = str(error)
                    if "Invalid nePk" in error_text or ("HTTP 400" in error_text and "nePk" in error_text):
                        try:
                            payload = _call_via_appliance_proxy()
                            used_appliance_proxy = True
                        except Exception as proxy_error:
                            raise RuntimeError(
                                f"{error} | appliance-scoped fallback via /appliance/rest also failed: {proxy_error}"
                            ) from error
                    else:
                        raise
                if payload is None:
                    raise last_orchestrator_error
            field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else []
            if field_list or offset or limit:
                paginated, _ = paginate_data(payload, max(0, offset), limit or None, field_list)
                payload = paginated
            budget = max(2000, min(max_chars or settings.max_output_chars, 50000))
            wrapper = {
                "data": payload,
                "request_echo": {
                    "operation_id": operation_id,
                    "resolved_path": "/appliance/rest" if used_appliance_proxy else operation.path,
                    "query_used": {k: str(v) for k, v in query_params.items()},
                    **({"via_appliance_proxy": True} if used_appliance_proxy else {}),
                },
            }
            result_text, truncated = closed_json_result(wrapper, budget)
            parsed = json.loads(result_text)
            parsed["truncated"] = truncated
            audit.record("call_read_api", operation_id, settings.orchestrator_url, "ok")
            return json.dumps(parsed, ensure_ascii=False, default=str)
        except Exception as error:
            audit.record("call_read_api", operation_id, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def list_cli_commands(category: str = "") -> str:
        """List the official ECOS CLI commands available via run_cli_command/run_show_command, from the HPE Aruba EdgeConnect CLI Reference: 1367 commands across categories monitoring (read), troubleshooting (diagnostic), alarm, administration, configuration and negation (write)."""
        entries = catalog_entries()
        if category:
            lowered = category.strip().lower()
            entries = [e for e in entries if e["category"] == lowered]
        payload = {
            "count": len(entries),
            "total": total_commands(),
            "categories": ["monitoring", "troubleshooting", "alarm", "administration", "configuration", "negation"],
            "commands": entries,
        }
        audit.record("list_cli_commands", "read", "cli-reference", "ok", details={"returned": len(entries)})
        return json_result(payload, settings.max_output_chars * 8)

    @mcp.tool()
    def run_show_command(command: str, host: str = "") -> str:
        """Run a whitelisted read-only ECOS 'show' command on an EdgeConnect appliance over SSH. Use list_cli_commands to discover the official monitoring commands."""
        pool = ApplianceSshPool(settings)
        try:
            session = pool.get(host or None)
            output = session.run_show(command)
            audit.record("run_show_command", command, host or settings.ssh_host, "ok")
            return output
        except Exception as error:
            audit.record("run_show_command", command, host or settings.ssh_host, f"error: {error}")
            return f"Error: {error}"
        finally:
            pool.close_all()

    @mcp.tool()
    def run_show_api(command: str, appliance_id: str) -> str:
        """Run an official read-only ECOS show command through the Orchestrator appliance API."""
        try:
            command, risk = validate_catalog_command(command)
            if risk != "read":
                raise SecurityError(
                    "Only commands classified as read-only in the official ECOS CLI catalog are allowed"
                )
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            ne_pk = resolve_ne_pk(client, appliance_id)
            payload = client.appliance_api_call(
                version,
                ne_pk,
                "appliance.clipost13533",
                json_body={"command": command.strip()},
            )
            audit.record(
                "run_show_api",
                command,
                ne_pk,
                "ok",
                details={"transport": "orchestrator", "risk": risk},
            )
            return json_result(
                {"applied": True, "transport": "orchestrator", "appliance": ne_pk, "result": payload},
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("run_show_api", command, appliance_id, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def run_cli_command(command: str, host: str = "", confirm: bool = False) -> str:
        """Run any official ECOS CLI command from the CLI Reference on an appliance over SSH. Monitoring/troubleshooting commands execute directly; configuration/administration/negation commands are dry-run by default and require confirm=true plus EC_ALLOW_WRITE_TOOLS=true. Use list_cli_commands to discover the 1367 available commands."""
        pool = ApplianceSshPool(settings)
        target = host or settings.ssh_host
        try:
            command, risk = validate_catalog_command(command)
            if risk == "write":
                require_writes(command, execute=confirm)
                if not confirm:
                    audit.record("run_cli_command", command, target, "dry-run", dry_run=True)
                    return json_result(
                        {
                            "dry_run": True,
                            "would_execute": command,
                            "risk": risk,
                            "hint": "Pass confirm=true to execute. Requires EC_ALLOW_WRITE_TOOLS=true.",
                        },
                        settings.max_output_chars,
                    )
            session = pool.get(host or None)
            if risk == "read":
                output = session.run_show(command)
            else:
                output = session.run_raw(command)
            audit.record("run_cli_command", command, target, "ok", dry_run=False, details={"risk": risk})
            return output
        except Exception as error:
            audit.record("run_cli_command", command, target, f"error: {error}")
            return f"Error: {error}"
        finally:
            pool.close_all()

    OVERLAY_GET_OPERATION = "orchestrator.getoverlay323"
    OVERLAY_CREATE_OPERATION = "orchestrator.addnewoverlay315"
    OVERLAY_DELETE_OPERATION = "orchestrator.deleteexistingoverlay322"

    def _read_overlays(client: OrchestratorClient, version: str) -> Any:
        return client.call(version, OVERLAY_GET_OPERATION)

    @mcp.tool()
    def list_overlay_sources(limit: int = 20) -> str:
        """List existing Business Intent Overlays that can be used as safe clone sources."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            limit = min(max(1, int(limit)), 100)
            rows = extract_overlays(_read_overlays(client, version))
            summaries = [
                {
                    "id": row.get("id") or row.get("overlayId"),
                    "name": row.get("name"),
                    "topology_type": (row.get("topology") or {}).get("topologyType")
                    if isinstance(row.get("topology"), dict)
                    else None,
                    "hubs": (row.get("topology") or {}).get("hubs", [])
                    if isinstance(row.get("topology"), dict)
                    else [],
                }
                for row in rows[:limit]
            ]
            return json_result(
                {"overlays": summaries, "total_count": len(rows), "returned": len(summaries)},
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("list_overlay_sources", "read", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def prepare_overlay_clone(
        source_overlay: str,
        target_name: str,
        overrides_json: str = "",
    ) -> str:
        """Read and sanitize an existing BIO, validate a parameterized clone, and return a diff plus exact confirmation phrase. This tool never writes."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            payload = _read_overlays(client, version)
            source = select_overlay(payload, source_overlay)
            existing_names = {
                str(row.get("name", "")).casefold() for row in extract_overlays(payload)
            }
            if target_name.casefold() in existing_names:
                raise SecurityError(f"An overlay named {target_name!r} already exists")
            plan = prepare_overlay_plan(source, target_name, overrides_json)
            overlay_plans.put(plan)
            audit.record(
                "prepare_overlay_clone",
                "preview",
                settings.orchestrator_url,
                "ok",
                dry_run=True,
                details={"plan_id": plan.plan_id, "source": plan.source_name, "target": target_name},
            )
            return json_result(
                {
                    "dry_run": True,
                    "plan": plan.public(),
                    "next_step": "Review the candidate and diff, then call apply_overlay_plan with confirm=true and the exact confirmation phrase.",
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("prepare_overlay_clone", "preview", settings.orchestrator_url, f"error: {error}", dry_run=True)
            return f"Error: {error}"

    @mcp.tool()
    def preview_overlay_plan(plan_id: str) -> str:
        """Return the immutable candidate, diff, status and confirmation phrase for a prepared overlay plan."""
        try:
            return json_result({"plan": overlay_plans.get(plan_id).public()}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"

    @mcp.tool()
    def apply_overlay_plan(
        plan_id: str,
        confirmation: str = "",
        confirm: bool = False,
    ) -> str:
        """Apply a prepared BIO clone, then read it back for a health check. Requires confirm=true and the plan-specific phrase."""
        try:
            plan = overlay_plans.get(plan_id)
            if plan.status != "prepared":
                raise SecurityError(f"Plan status is {plan.status!r}; only prepared plans can be applied")
            if not confirm:
                return json_result(
                    {
                        "dry_run": True,
                        "plan": plan.public(),
                        "hint": "Set confirm=true and pass confirmation_required exactly.",
                    },
                    settings.max_output_chars,
                )
            if confirmation != plan.confirmation:
                raise SecurityError("Confirmation phrase does not match this plan")
            require_writes(OVERLAY_CREATE_OPERATION)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            before = _read_overlays(client, version)
            if any(
                str(row.get("name", "")).casefold() == plan.target_name.casefold()
                for row in extract_overlays(before)
            ):
                raise SecurityError(f"An overlay named {plan.target_name!r} already exists")
            result = client.call(
                version,
                OVERLAY_CREATE_OPERATION,
                json_body=plan.candidate,
            )
            after = _read_overlays(client, version)
            plan.created_overlay_id = extract_created_overlay_id(result, after, plan.target_name)
            plan.apply_result = result
            if not plan.created_overlay_id:
                plan.status = "verification_failed"
                rollback = {"attempted": False, "reason": "Created overlay ID could not be determined safely"}
                result_payload = {
                    "applied": True,
                    "verified": False,
                    "plan": plan.public(include_candidate=False),
                    "rollback": rollback,
                }
            else:
                plan.status = "applied"
                result_payload = {
                    "applied": True,
                    "verified": True,
                    "health_check": {
                        "overlay_id": plan.created_overlay_id,
                        "name": plan.target_name,
                        "present_after_create": True,
                    },
                    "plan": plan.public(include_candidate=False),
                }
            audit.record(
                "apply_overlay_plan",
                OVERLAY_CREATE_OPERATION,
                settings.orchestrator_url,
                plan.status,
                dry_run=False,
                details={"plan_id": plan.plan_id, "overlay_id": plan.created_overlay_id},
            )
            return json_result(result_payload, settings.max_output_chars)
        except Exception as error:
            audit.record("apply_overlay_plan", OVERLAY_CREATE_OPERATION, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def verify_overlay_plan(plan_id: str) -> str:
        """Read the Orchestrator and verify that the planned overlay exists with the expected name."""
        try:
            plan = overlay_plans.get(plan_id)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            rows = extract_overlays(_read_overlays(client, client.resolve_active_profile()))
            match = next(
                (
                    row
                    for row in rows
                    if str(row.get("name", "")).casefold() == plan.target_name.casefold()
                ),
                None,
            )
            if match:
                plan.created_overlay_id = str(match.get("id") or match.get("overlayId") or "")
                if plan.status == "verification_failed":
                    plan.status = "applied"
            return json_result(
                {
                    "verified": match is not None,
                    "overlay": {
                        "id": (match or {}).get("id") or (match or {}).get("overlayId"),
                        "name": (match or {}).get("name"),
                    }
                    if match
                    else None,
                    "plan": plan.public(include_candidate=False),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"

    @mcp.tool()
    def rollback_overlay_plan(
        plan_id: str,
        confirmation: str = "",
        confirm: bool = False,
    ) -> str:
        """Delete an overlay created by this transaction. Requires dangerous writes and ROLLBACK <plan_id>."""
        try:
            plan = overlay_plans.get(plan_id)
            expected = f"ROLLBACK {plan.plan_id}"
            if not confirm:
                return json_result(
                    {
                        "dry_run": True,
                        "would_delete_overlay_id": plan.created_overlay_id,
                        "confirmation_required": expected,
                    },
                    settings.max_output_chars,
                )
            if confirmation != expected:
                raise SecurityError("Rollback confirmation phrase does not match this plan")
            if not plan.created_overlay_id:
                raise SecurityError("No verified created overlay ID is available for rollback")
            require_writes(OVERLAY_DELETE_OPERATION)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            result = client.call(
                version,
                OVERLAY_DELETE_OPERATION,
                overlayId=plan.created_overlay_id,
            )
            rows = extract_overlays(_read_overlays(client, version))
            still_present = any(
                str(row.get("id") or row.get("overlayId") or "") == plan.created_overlay_id
                for row in rows
            )
            plan.status = "rollback_failed" if still_present else "rolled_back"
            audit.record(
                "rollback_overlay_plan",
                OVERLAY_DELETE_OPERATION,
                settings.orchestrator_url,
                plan.status,
                dry_run=False,
                details={"plan_id": plan.plan_id, "overlay_id": plan.created_overlay_id},
            )
            return json_result(
                {
                    "rolled_back": not still_present,
                    "verified_absent": not still_present,
                    "result": result,
                    "plan": plan.public(include_candidate=False),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("rollback_overlay_plan", OVERLAY_DELETE_OPERATION, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    def _read_discovered(client: OrchestratorClient, version: str) -> Any:
        return client.call(version, ZTP_DISCOVERED_READ)

    def _extract_status_tasks(payload: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            for key in ("data", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    rows = [item for item in value if isinstance(item, dict)]
                    break
                if isinstance(value, dict):
                    inner = value.get("result")
                    if isinstance(inner, list):
                        rows = [item for item in inner if isinstance(item, dict)]
                        break
        return rows

    def _ztp_task_completed(task: dict[str, Any]) -> bool:
        # taskStatus=2 is the completed state observed in the supported 9.6 contract.
        return (
            task.get("completionStatus") is True
            and task.get("taskStatus") in (2, "2")
            and not task.get("error")
            and task.get("success") is not False
        )

    @mcp.tool()
    def get_ztp_apply_status(preconfig_id: str) -> str:
        """Read the asynchronous preconfig apply task chain status (operation 254) for a ZTP adoption: per-task completion (Add Appliance, Appliance Info, Zones, license, deployment, Reboot, templates, overlays)."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            payload = client.call(
                client.resolve_active_profile(),
                ZTP_PRECONFIG_STATUS,
                preconfigId=preconfig_id,
            )
            tasks = _extract_status_tasks(payload)
            pending = [t.get("name") for t in tasks if not _ztp_task_completed(t)]
            return json_result(
                {
                    "preconfig_id": preconfig_id,
                    "total_tasks": len(tasks),
                    "completed_tasks": len(tasks) - len(pending),
                    "all_completed": bool(tasks) and not pending,
                    "pending_tasks": pending,
                    "tasks": [
                        {
                            "name": t.get("name"),
                            "completionStatus": t.get("completionStatus"),
                            "taskStatus": t.get("taskStatus"),
                            "nePk": t.get("nePk"),
                        }
                        for t in tasks
                    ],
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"

    @mcp.tool()
    def list_discovered_appliances(limit: int = 20, offset: int = 0) -> str:
        """List discovered (ZTP) appliances that are not yet approved, with UUID, serial, model and software version."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            rows = extract_discovered(_read_discovered(client, version))
            pending = [row for row in rows if not row.get("approved") and not row.get("denied")]
            offset = max(0, int(offset))
            limit = min(max(1, int(limit)), 100)
            page = pending[offset : offset + limit]
            summaries = [
                {
                    "uuid": row.get("uuid", ""),
                    "hostname": (row.get("applianceInfo") or {}).get("hostname", ""),
                    "model": (row.get("applianceInfo") or {}).get("model", ""),
                    "serial": (row.get("applianceInfo") or {}).get("serial", ""),
                    "softwareVersion": (row.get("applianceInfo") or {}).get("softwareVersion", ""),
                    "deviceType": (row.get("applianceInfo") or {}).get("deviceType", ""),
                }
                for row in page
            ]
            return json_result(
                {
                    "discovered": summaries,
                    "total_count": len(pending),
                    "returned": len(summaries),
                    "offset": offset,
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("list_discovered_appliances", ZTP_DISCOVERED_READ, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def prepare_ztp_adoption(
        appliance_selector: str,
        preconfig_yaml: str,
    ) -> str:
        """Prepare a transactional ZTP adoption. ``appliance_selector`` accepts a serial number (preferred, dashed or undashed, e.g. 001BBC462C04 or 00-1B-BC-46-2C-04) or a discovered UUID. Validates the preconfiguration template YAML, verifies referenced template groups and overlays exist, and returns a plan plus confirmation phrase. Never writes."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            row = select_discovered(_read_discovered(client, version), appliance_selector)
            groups_payload = client.call(version, TEMPLATE_GROUPS_READ)
            overlays_payload = _read_overlays(client, version)
            plan = prepare_ztp_plan(row, preconfig_yaml, groups_payload, overlays_payload)
            ztp_plans.put(plan)
            audit.record(
                "prepare_ztp_adoption",
                ZTP_DISCOVERED_READ,
                settings.orchestrator_url,
                "prepared",
                dry_run=True,
                details={"plan_id": plan.plan_id, "uuid": plan.appliance_uuid},
            )
            return json_result(
                {
                    "dry_run": True,
                    "plan": plan.public(),
                    "next_step": "Review preconfig_yaml and confirmation phrase, then call apply_ztp_plan with confirm=true.",
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("prepare_ztp_adoption", ZTP_DISCOVERED_READ, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def preview_ztp_plan(plan_id: str) -> str:
        """Return the immutable schema, parameters, status and confirmation phrase for a prepared ZTP adoption plan."""
        try:
            return json_result({"plan": ztp_plans.get(plan_id).public()}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"

    @mcp.tool()
    def apply_ztp_plan(
        plan_id: str,
        confirmation: str = "",
        confirm: bool = False,
    ) -> str:
        """Apply a prepared ZTP adoption: validate deployment, apply preconfiguration, approve the appliance and verify it appears in inventory. Requires confirm=true and the plan phrase."""
        try:
            plan = ztp_plans.get(plan_id)
            if plan.status != "prepared":
                raise SecurityError(f"Plan status is {plan.status!r}; only prepared plans can be applied")
            if not confirm:
                return json_result(
                    {
                        "dry_run": True,
                        "plan": plan.public(),
                        "hint": "Set confirm=true and pass confirmation_required exactly.",
                    },
                    settings.max_output_chars,
                )
            if confirmation != plan.confirmation:
                raise SecurityError("Confirmation phrase does not match this plan")
            require_writes(ZTP_PRECONFIG_VALIDATE)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            discovered_before = _read_discovered(client, version)
            select_discovered(discovered_before, plan.appliance_uuid)
            preconfig_body = {
                "name": plan.preconfig_name,
                "preConfig": base64.b64encode(plan.preconfig_yaml.encode("utf-8")).decode("ascii"),
                "autoApply": False,
            }
            plan.validate_result = client.call(
                version,
                ZTP_PRECONFIG_VALIDATE,
                json_body=preconfig_body,
            )
            require_writes(ZTP_PRECONFIG_CREATE)
            created = client.call(
                version,
                ZTP_PRECONFIG_CREATE,
                json_body=preconfig_body,
            )
            created_id = extract_preconfig_id(created)
            if not created_id:
                created_id = find_preconfig_id_by_name(
                    client.call(version, ZTP_PRECONFIGS_READ),
                    plan.preconfig_name,
                )
            if not created_id:
                raise ValueError(f"Orchestrator did not return a preconfig id after creation: {created!r}")
            plan.created_preconfig_id = created_id
            require_writes(ZTP_PRECONFIG_APPLY)
            apply_query: dict[str, Any] = {"preconfigId": created_id}
            if plan.discovered_row_id:
                apply_query["discoveredId"] = plan.discovered_row_id
            else:
                apply_query["discoveredId"] = plan.appliance_uuid
            plan.preconfig_result = client.call(
                version,
                ZTP_PRECONFIG_APPLY,
                **apply_query,
            )
            plan.deny_available = True
            plan.status = "applied"
            ztp_plans.put(plan)
            audit.record(
                "apply_ztp_plan",
                ZTP_PRECONFIG_APPLY,
                settings.orchestrator_url,
                "applied",
                dry_run=False,
                details={
                    "plan_id": plan.plan_id,
                    "uuid": plan.appliance_uuid,
                    "discovered_row_id": plan.discovered_row_id,
                },
            )
            return json_result(
                {
                    "applied": True,
                    "verified": False,
                    "verification": "async",
                    "hint": (
                        "The preconfig apply is asynchronous and triggers the full task chain "
                        "(add, appliance info, deployment, reboot, templates, overlays). "
                        "Poll get_ztp_apply_status with the preconfig id, then verify_ztp_plan "
                        "once tasks complete."
                    ),
                    "plan": plan.public(include_details=False),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("apply_ztp_plan", ZTP_APPROVE_OPERATION, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def verify_ztp_plan(plan_id: str) -> str:
        """Verify an applied ZTP adoption: polls the preconfig apply task status (254) and checks the appliance inventory by serial. The apply is asynchronous; verified=true only when every task completed AND the appliance is registered in inventory."""
        try:
            plan = ztp_plans.get(plan_id)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            tasks_payload = None
            tasks_summary: dict[str, Any] = {"checked": False}
            if plan.created_preconfig_id:
                try:
                    tasks_payload = client.call(
                        version,
                        ZTP_PRECONFIG_STATUS,
                        preconfigId=plan.created_preconfig_id,
                    )
                    tasks = _extract_status_tasks(tasks_payload)
                    if tasks:
                        pending = [t.get("name") for t in tasks if not _ztp_task_completed(t)]
                        tasks_summary = {
                            "checked": True,
                            "total": len(tasks),
                            "completed": len(tasks) - len(pending),
                            "pending": pending,
                        }
                except Exception as error:
                    tasks_summary = {"checked": False, "error": str(error)}
            wanted = normalize_serial(plan.appliance_serial)
            inventory_match = None
            for appliance in client.list_appliances(refresh=True):
                if normalize_serial(appliance.get("serial_number", appliance.get("serial", ""))) == wanted:
                    inventory_match = {
                        "nePk": appliance.get("nePk"),
                        "name": appliance.get("name"),
                        "serial": appliance.get("serial_number", appliance.get("serial")),
                        "state": appliance.get("state"),
                    }
                    break
            still_discovered = any(
                normalize_serial((row.get("applianceInfo") or {}).get("serial")) == wanted
                for row in extract_discovered(_read_discovered(client, version))
            )
            tasks_done = bool(tasks_summary.get("checked") and not tasks_summary.get("pending"))
            verified = bool(
                plan.status in {"applied", "verification_failed", "verified"}
                and inventory_match and not still_discovered and tasks_done
            )
            if verified and plan.status in {"applied", "verification_failed"}:
                plan.status = "verified"
                plan.health_check = {"inventory": inventory_match, "tasks": tasks_summary}
                ztp_plans.put(plan)
            elif not verified and plan.status == "verified":
                plan.status = "verification_failed"
                plan.health_check = {"inventory": inventory_match, "tasks": tasks_summary}
                ztp_plans.put(plan)
            return json_result(
                {
                    "verified": verified,
                    "inventory": inventory_match,
                    "still_in_discovered": still_discovered,
                    "apply_tasks": tasks_summary,
                    "hostname": plan.appliance_hostname,
                    "serial": plan.appliance_serial,
                    "plan_status": plan.status,
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"

    @mcp.tool()
    def rollback_ztp_plan(
        plan_id: str,
        confirmation: str = "",
        confirm: bool = False,
    ) -> str:
        """Deny an appliance adopted by this transaction (only while safely reversible). Requires dangerous writes and ROLLBACK <plan_id>."""
        try:
            plan = ztp_plans.get(plan_id)
            expected = f"ROLLBACK {plan.plan_id}"
            if not confirm:
                return json_result(
                    {
                        "dry_run": True,
                        "would_deny_uuid": plan.appliance_uuid,
                        "confirmation_required": expected,
                    },
                    settings.max_output_chars,
                )
            if confirmation != expected:
                raise SecurityError("Rollback confirmation phrase does not match this plan")
            if plan.status not in {"applied", "verification_failed"}:
                raise SecurityError(f"Plan status {plan.status!r} has nothing to roll back")
            require_writes(ZTP_DENY_OPERATION)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            result = client.call(
                version,
                ZTP_DENY_OPERATION,
                id=plan.discovered_row_id or plan.appliance_uuid,
            )
            delete_result = None
            if plan.created_preconfig_id:
                delete_result = client.call(
                    version,
                    ZTP_PRECONFIG_DELETE,
                    preconfigId=plan.created_preconfig_id,
                )
            rows = [
                row
                for row in extract_discovered(_read_discovered(client, version))
                if str(row.get("uuid", "")).lower() == plan.appliance_uuid.lower()
            ]
            denied = bool(rows and rows[0].get("denied"))
            plan.status = "rolled_back" if denied else "rollback_failed"
            ztp_plans.put(plan)
            audit.record(
                "rollback_ztp_plan",
                ZTP_DENY_OPERATION,
                settings.orchestrator_url,
                plan.status,
                dry_run=False,
                details={"plan_id": plan.plan_id, "uuid": plan.appliance_uuid},
            )
            return json_result(
                {
                    "rolled_back": denied,
                    "verified_denied": denied,
                    "preconfig_deleted": bool(plan.created_preconfig_id),
                    "delete_result": delete_result,
                    "result": result,
                    "plan": plan.public(include_details=False),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("rollback_ztp_plan", ZTP_DENY_OPERATION, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def prepare_bulk_ztp_adoption(
        appliance_selectors: str,
        base_preconfig_yaml: str,
        hostnames: str = "",
        sites: str = "",
    ) -> str:
        """Prepare a bulk transactional ZTP adoption for many appliances at once. ``appliance_selectors`` is a comma-separated list of serial numbers (preferred) or UUIDs. ``base_preconfig_yaml`` may use {{hostname}} and {{site}} placeholders substituted per appliance from the comma-separated ``hostnames``/``sites`` lists (same order). Returns a bulk plan with one sub-plan per appliance and a single confirmation phrase. Never writes."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            selectors = [item.strip() for item in appliance_selectors.split(",") if item.strip()]
            if not selectors:
                raise ValueError("appliance_selectors must contain at least one serial or UUID")
            hostname_list = [item.strip() for item in hostnames.split(",") if item.strip()] if hostnames else []
            site_list = [item.strip() for item in sites.split(",") if item.strip()] if sites else []
            if hostname_list and len(hostname_list) != len(selectors):
                raise ValueError(
                    f"hostnames has {len(hostname_list)} entries but there are {len(selectors)} appliances"
                )
            if site_list and len(site_list) != len(selectors):
                raise ValueError(f"sites has {len(site_list)} entries but there are {len(selectors)} appliances")
            discovered = _read_discovered(client, version)
            groups_payload = client.call(version, TEMPLATE_GROUPS_READ)
            overlays_payload = _read_overlays(client, version)
            bulk_id = secrets.token_hex(6)
            plans: list[ZtpPlan] = []
            for index, selector in enumerate(selectors):
                row = select_discovered(discovered, selector)
                hostname = hostname_list[index] if hostname_list else str(
                    (row.get("applianceInfo") or {}).get("hostname") or ""
                )
                site = site_list[index] if site_list else ""
                rendered = render_bulk_yaml(base_preconfig_yaml, hostname, site)
                plan = prepare_ztp_plan(
                    row,
                    rendered,
                    groups_payload,
                    overlays_payload,
                    bulk_id=bulk_id,
                )
                plans.append(plan)
            for plan in plans:
                ztp_plans.put(plan)
            bulk = ZtpBulkPlan(
                bulk_id=bulk_id,
                plan_ids=[p.plan_id for p in plans],
                confirmation=f"ADOPTAR-BULK {bulk_id} {len(plans)}",
            )
            ztp_bulk_plans[bulk_id] = bulk
            audit.record(
                "prepare_bulk_ztp_adoption",
                ZTP_DISCOVERED_READ,
                settings.orchestrator_url,
                "prepared",
                dry_run=True,
                details={"bulk_id": bulk_id, "appliances": len(plans)},
            )
            return json_result(
                {
                    "dry_run": True,
                    "bulk": bulk.public(),
                    "plans": [p.public(include_details=False) for p in plans],
                    "next_step": (
                        "Review every sub-plan, then call apply_bulk_ztp_plan with the bulk "
                        "confirmation phrase and confirm=true."
                    ),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("prepare_bulk_ztp_adoption", ZTP_DISCOVERED_READ, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def apply_bulk_ztp_plan(
        bulk_id: str,
        confirmation: str = "",
        confirm: bool = False,
    ) -> str:
        """Apply every prepared sub-plan of a bulk ZTP adoption sequentially: validate, create, apply preconfig (with the numeric discoveredId) per appliance. Requires confirm=true and the bulk phrase. Sub-plans that fail do not stop the rest; the response reports per-plan results. Verify each appliance afterwards with verify_ztp_plan."""
        try:
            bulk = ztp_bulk_plans.get(bulk_id)
            if bulk is None:
                raise ValueError("Unknown or expired bulk ZTP plan")
            if bulk.status != "prepared":
                raise SecurityError(f"Bulk plan status is {bulk.status!r}; only prepared bulks can be applied")
            if not confirm:
                return json_result(
                    {
                        "dry_run": True,
                        "bulk": bulk.public(),
                        "hint": "Set confirm=true and pass confirmation_required exactly.",
                    },
                    settings.max_output_chars,
                )
            if confirmation != bulk.confirmation:
                raise SecurityError("Confirmation phrase does not match this bulk plan")
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            results: list[dict[str, Any]] = []
            applied = 0
            for plan_id in bulk.plan_ids:
                entry: dict[str, Any] = {"plan_id": plan_id}
                try:
                    plan = ztp_plans.get(plan_id)
                    if plan.status != "prepared":
                        raise SecurityError(f"Sub-plan status is {plan.status!r}")
                    preconfig_body = {
                        "name": plan.preconfig_name,
                        "preConfig": base64.b64encode(plan.preconfig_yaml.encode("utf-8")).decode("ascii"),
                        "autoApply": False,
                    }
                    require_writes(ZTP_PRECONFIG_VALIDATE)
                    client.call(version, ZTP_PRECONFIG_VALIDATE, json_body=preconfig_body)
                    require_writes(ZTP_PRECONFIG_CREATE)
                    created = client.call(version, ZTP_PRECONFIG_CREATE, json_body=preconfig_body)
                    created_id = extract_preconfig_id(created) or find_preconfig_id_by_name(
                        client.call(version, ZTP_PRECONFIGS_READ), plan.preconfig_name
                    )
                    if not created_id:
                        raise ValueError("Orchestrator did not return a preconfig id after creation")
                    plan.created_preconfig_id = created_id
                    require_writes(ZTP_PRECONFIG_APPLY)
                    client.call(
                        version,
                        ZTP_PRECONFIG_APPLY,
                        discoveredId=plan.discovered_row_id or plan.appliance_uuid,
                        preconfigId=created_id,
                    )
                    plan.status = "applied"
                    plan.deny_available = True
                    ztp_plans.put(plan)
                    entry.update({"applied": True, "preconfig_id": created_id})
                    applied += 1
                except Exception as error:
                    entry.update({"applied": False, "error": str(error)})
                results.append(entry)
            bulk.status = "applied" if applied else "failed"
            audit.record(
                "apply_bulk_ztp_plan",
                ZTP_PRECONFIG_APPLY,
                settings.orchestrator_url,
                bulk.status,
                dry_run=False,
                details={"bulk_id": bulk_id, "applied": applied, "total": len(bulk.plan_ids)},
            )
            return json_result(
                {
                    "applied": applied,
                    "total": len(bulk.plan_ids),
                    "results": results,
                    "next_step": (
                        "The applies are asynchronous: poll get_ztp_apply_status per preconfig id "
                        "and verify each appliance with verify_ztp_plan."
                    ),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            audit.record("apply_bulk_ztp_plan", ZTP_PRECONFIG_APPLY, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def list_bulk_ztp_plans() -> str:
        """List every bulk ZTP adoption plan with its sub-plans and status."""
        try:
            bulks = []
            for bulk in ztp_bulk_plans.values():
                item = bulk.public()
                item["plans"] = []
                for plan_id in bulk.plan_ids:
                    try:
                        item["plans"].append(ztp_plans.get(plan_id).public(include_details=False))
                    except Exception:
                        item["plans"].append({"plan_id": plan_id, "status": "expired"})
                bulks.append(item)
            return json_result({"bulks": bulks}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"

    @mcp.tool()
    def get_ids_ips_state(appliance_id: str = "all") -> str:
        """Read the IDS/IPS posture of one appliance (or all): mode (Off/IDS Only/IPS-Performant/IPS-Inline), profile and whether intrusion detection/prevention is active."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            results = []
            for ne_pk in resolve_ne_pks(client, appliance_id):
                try:
                    payload = client.appliance_api_call(version, ne_pk, IDS_IPS_STATE_READ)
                    results.append({"nePk": ne_pk, **summarize_ids_state(payload)})
                except Exception as error:
                    results.append(
                        {
                            "nePk": ne_pk,
                            "error": str(error),
                            "evidence_status": "error",
                            "active": False,
                            "detection_enabled": False,
                            "prevention_enabled": False,
                        }
                    )
            return json_result(
                {
                    "appliances": results,
                    "coverage_complete": bool(results) and all(row["evidence_status"] == "observed" for row in results),
                    "enforcement_verified": False,
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_ids_ips_events(appliance_id: str, start_time: str = "", end_time: str = "", limit: int = 50) -> str:
        """Read recent IDS/IPS events. Time windows are refused when absent from the active vendor contract; limit is 1..1000."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            ne_pk = resolve_single_target(client, appliance_id)
            if not 1 <= limit <= 1000:
                raise SecurityError("limit must be in [1, 1000]")
            declared = set(engine._profiles[version]["operations"][IDS_IPS_EVENTS_READ].get("query_params", []))
            if (start_time or end_time) and not {"startTime", "endTime"} <= declared:
                raise SecurityError(
                    "IDS event time window is unsupported by this API profile; it cannot be silently ignored"
                )
            query: dict[str, Any] = {}
            if start_time:
                query["startTime"] = start_time
            if end_time:
                query["endTime"] = end_time
            payload = client.appliance_api_call(version, ne_pk, IDS_IPS_EVENTS_READ, **query)
            rows = extract_rows(payload)
            return json_result(
                {
                    "nePk": ne_pk,
                    "total_events": len(rows),
                    "events": rows[:limit],
                    "returned": min(len(rows), limit),
                    "truncated": len(rows) > limit,
                    "time_filter_applied": bool(query),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_security_log(
        appliance_id: str,
        log_type: str = "Firewall",
        date: str = "",
        lines: int = 100,
        summarize: bool = True,
    ) -> str:
        """Read the appliance security log (Security Log Viewer equivalent): zone-based firewall entries with Action (allow/drop), Flow-ID, zones, application, NAT and reputation. log_type: Firewall|Alarm|Audit|Event. date: YYYY-MM-DD (defaults to today). Use it for incident detection and to correlate flow IDs with allow/drop decisions."""
        from ec_mcp.security_workflow import (
            LOG_VIEWER_FILE_READ,
            LOG_VIEWER_TYPES,
            parse_firewall_log_entries,
            summarize_security_log,
        )

        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            if log_type not in LOG_VIEWER_TYPES:
                return f"Error: log_type must be one of {list(LOG_VIEWER_TYPES)}"
            version = client.resolve_active_profile()
            ne_pk = resolve_single_target(client, appliance_id)
            from datetime import UTC, datetime

            if not 1 <= lines <= 1000:
                raise SecurityError("lines must be in [1, 1000]")
            if not date:
                date = datetime.now(UTC).strftime("%Y-%m-%d")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                raise SecurityError("date must be YYYY-MM-DD")
            datetime.strptime(date, "%Y-%m-%d")
            payload = client.appliance_api_call(
                version,
                ne_pk,
                LOG_VIEWER_FILE_READ,
                path_params={
                    "logType": log_type,
                    "date": date,
                    "lines": str(max(1, int(lines))),
                },
            )
            entries = parse_firewall_log_entries(payload)
            result: dict[str, Any] = {
                "nePk": ne_pk,
                "log_type": log_type,
                "date": date,
                "total_entries": len(entries),
                "entries": entries,
            }
            if summarize and entries:
                result["summary"] = summarize_security_log(entries)
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_zone_matrix(appliance_id: str) -> str:
        """Read the zone-based security matrix of an appliance: zones, security maps with per-priority zone-to-zone policies, and uncovered zone pairs (no explicit policy) for review."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            ne_pk = resolve_single_target(client, appliance_id)
            zones_payload = client.appliance_api_call(version, ne_pk, ZONE_LIST_READ)
            maps_payload = client.appliance_api_call(version, ne_pk, SECURITY_MAPS_READ)
            settings_payload = client.appliance_api_call(version, ne_pk, SECURITY_MAP_SETTINGS_READ)
            matrix = summarize_zone_matrix(zones_payload, maps_payload, settings_payload)
            return json_result({"nePk": ne_pk, **matrix}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_ddos_status(appliance_id: str) -> str:
        """Read the DDoS protection status of an appliance: threshold status and protection profiles per zone."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            ne_pk = resolve_single_target(client, appliance_id)
            thresholds = client.appliance_api_call(version, ne_pk, DDOS_THRESHOLD_STATUS_READ)
            profiles = client.appliance_api_call(version, ne_pk, DDOS_PROTECTION_PROFILE_READ)
            return json_result(
                {
                    "nePk": ne_pk,
                    "threshold_status": summarize_ddos(thresholds),
                    "protection_profiles": summarize_ddos(profiles),
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_deployment_config(appliance_id: str) -> str:
        """Read the LAN/WAN deployment configuration of an appliance: deployment mode, total bandwidths and per-interface addressing, labels, zones and firewall modes. First stop for LAN/WAN configuration review."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            ne_pk = resolve_single_target(client, appliance_id)
            payload = client.appliance_api_call(version, ne_pk, DEPLOYMENT_CONFIG_READ)
            return json_result({"nePk": ne_pk, "deployment": payload}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_site_to_site_tunnels(appliance_id: str = "all", include_third_party: bool = True) -> str:
        """Read site-to-site tunnel state: standard tunnelsConfigAndState, bonded tunnel state, and (optionally) third-party/SSE VGW tunnels. Use for tunnel flow review and troubleshooting."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            results = []
            for ne_pk in resolve_ne_pks(client, appliance_id):
                entry: dict[str, Any] = {
                    "nePk": ne_pk,
                    "tunnels": summarize_tunnels(client.appliance_api_call(version, ne_pk, TUNNELS_CONFIG_AND_STATE_READ)),
                    "bonded": summarize_tunnels(client.appliance_api_call(version, ne_pk, BONDED_TUNNELS_STATE_READ)),
                }
                if include_third_party:
                    entry["third_party"] = summarize_tunnels(
                        client.appliance_api_call(version, ne_pk, THIRD_PARTY_TUNNELS_STATE_READ)
                    )
                results.append(entry)
            return json_result({"appliances": results}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_bgp_neighbors(appliance_id: str = "all") -> str:
        """Read BGP neighbor configuration and state (plus BFD sessions) for routing troubleshooting; supports 'all'."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            neighbor_payload = client.call(version, BGP_NEIGHBOR_READ, nePk="")
            neighbors = summarize_bgp_neighbors(neighbor_payload)
            bfd_payload = client.call(version, BFD_SESSIONS_READ)
            results = []
            for ne_pk in resolve_ne_pks(client, appliance_id):
                per_appliance = client.appliance_api_call(version, ne_pk, BGP_NEIGHBOR_READ)
                results.append({"nePk": ne_pk, "neighbors": summarize_bgp_neighbors(per_appliance)})
            return json_result(
                {
                    "orchestrator_neighbors": neighbors,
                    "bfd_sessions": extract_rows(bfd_payload),
                    "appliances": results,
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_sse_status(provider: str = "all") -> str:
        """Read SSE (Secure Service Edge) integration status: connectivity and appliance associations for Zscaler, Netskope and Axis Security (HPE SSE). provider='all' or one of zscaler/netskope/axis."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            selected = list(SSE_PROVIDERS) if provider.strip().lower() in {"", "all"} else [provider.strip().lower()]
            unknown = [name for name in selected if name not in SSE_PROVIDERS]
            if unknown:
                raise ValueError(f"Unknown SSE provider(s): {unknown}; valid: {list(SSE_PROVIDERS)}")
            results = []
            for name in selected:
                ops = SSE_PROVIDERS[name]
                try:
                    connectivity = client.call(version, ops["connectivity"])
                    association = client.call(version, ops["association"])
                    results.append(extract_sse_status(name, connectivity, association))
                except Exception as error:
                    results.append({"provider": name, "error": str(error)})
            return json_result({"providers": results}, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def get_service_orchestration_evidence(appliance_id: str, service_id: int) -> str:
        """Read one Service Orchestration provider, endpoints, appliance association and IP SLA presence. No tunnel state or enforcement is inferred."""
        try:
            service_id = bounded_id(service_id, "service_id")
            client = require_client()
            if client is None:
                raise ValueError("Orchestrator is not configured")
            ne_pk = resolve_single_target(client, appliance_id)
            version = client.resolve_active_profile()
            result = service_evidence(
                service_id,
                ne_pk,
                client.call(version, SERVICE_PROVIDERS),
                client.call(version, REMOTE_ENDPOINTS, serviceId=service_id),
                client.call(version, ENDPOINT_ASSOCIATIONS, serviceId=service_id),
                client.call(version, IPSLA_SETTINGS, serviceId=service_id),
            )
            audit.record("get_service_orchestration_evidence", "read", ne_pk, "association_observed", details={"service_id": service_id})
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            audit.record("get_service_orchestration_evidence", "read", appliance_id, "not_observed")
            reason = str(error) if isinstance(error, (ValueError, SecurityError)) else "Orchestrator read failed"
            return json_result({"error": reason, "evidence_scope": "not_observed", "enforcement_verified": False}, settings.max_output_chars)


    @mcp.tool()
    def get_flow_evidence(appliance_id: str, flow_id: int, sequence: int) -> str:
        """Read one flow detail via Orchestrator, allowing only known scalar fields in the output."""
        try:
            flow_id = bounded_id(flow_id, "flow_id")
            sequence = bounded_id(sequence, "sequence")
            client = require_client()
            if client is None:
                raise ValueError("Orchestrator is not configured")
            ne_pk = resolve_single_target(client, appliance_id)
            version = client.resolve_active_profile()
            result = flow_evidence(ne_pk, flow_id, sequence, client.call(
                version, FLOW_DETAILS, nePk=ne_pk, id=flow_id, seq=sequence,
            ))
            audit.record("get_flow_evidence", "read", ne_pk, result["evidence_scope"])
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            audit.record("get_flow_evidence", "read", appliance_id, "not_observed")
            reason = str(error) if isinstance(error, (ValueError, SecurityError)) else "Orchestrator read failed"
            return json_result({"error": reason, "evidence_scope": "not_observed", "enforcement_verified": False}, settings.max_output_chars)


    @mcp.tool()
    def get_hpe_sse_inventory(resource: str, page: int = 1, page_size: int = 50) -> str:
        """Read HPE SSE Admin API inventory (web/IP categories, SSL exclusions, locations, tunnels, health). This does not establish applied web-filter policy or enforcement."""
        try:
            if resource not in SSE_RESOURCES:
                raise ValueError(f"Unknown SSE resource; valid: {sorted(SSE_RESOURCES)}")
            with SSEAdminClient(settings) as sse:
                result = sse.read(resource, page, page_size)
            audit.record("get_hpe_sse_inventory", "read", resource, "inventory_observed")
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            audit.record("get_hpe_sse_inventory", "read", resource, f"error: {error}")
            return json_result(
                {"resource": resource, "error": str(error), "evidence_scope": "not_observed", "enforcement_verified": False},
                settings.max_output_chars,
            )

    @mcp.tool()
    def get_web_filter_status(appliance_id: str, provider: str) -> str:
        """Read this appliance's SSE association and provider connectivity. URL/category policy and web-filter enforcement are explicitly not observed by these API profiles."""
        try:
            name = provider.strip().lower()
            if name not in SSE_PROVIDERS:
                raise SecurityError(f"provider must be one of {list(SSE_PROVIDERS)}")
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            ne_pk = resolve_single_target(client, appliance_id)
            version = client.resolve_active_profile()
            ops = SSE_PROVIDERS[name]
            status = extract_sse_status(
                name,
                client.call(version, ops["connectivity"]),
                client.call(version, ops["association"]),
            )
            result = {
                "nePk": ne_pk,
                "provider": name,
                "connectivity": status["connectivity"],
                "appliance_associated": (ne_pk in status["associated_appliances"])
                if status["association_evidence_status"] == "observed"
                else None,
                "association_evidence_status": status["association_evidence_status"],
                "evidence_scope": "connectivity_and_association_only",
                "policy_status": "not_observed",
                "coverage_complete": False,
                "enforcement_verified": False,
                "next_step": "Read URL/category policy and decision logs from the SSE provider; validate with bounded lab probes",
            }
            audit.record(
                "get_web_filter_status",
                "read",
                ne_pk,
                "policy_not_observed",
                details={
                    "provider": name,
                    "appliance_associated": result["appliance_associated"],
                },
            )
            return json_result(result, settings.max_output_chars)
        except Exception as error:
            audit.record("get_web_filter_status", "read", appliance_id, f"error: {error}")
            return json_result(
                {
                    "nePk": appliance_id,
                    "provider": provider,
                    "error": str(error),
                    "policy_status": "not_observed",
                    "coverage_complete": False,
                    "enforcement_verified": False,
                },
                settings.max_output_chars,
            )


    @mcp.tool()
    def get_security_posture(appliance_id: str = "all") -> str:
        """Read IDS/IPS, DDoS, directional firewall policies and tunnels. Errors and unknown evidence remain explicit findings; SSE/web filtering and data-plane enforcement are not verified."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            targets = resolve_ne_pks(client, appliance_id)
            findings: list[dict[str, Any]] = []
            results = []
            complete = bool(targets)

            def finding(
                ne_pk: str,
                control: str,
                severity: str,
                message: str,
                kind: str = "observation",
            ) -> None:
                findings.append(
                    {
                        "nePk": ne_pk,
                        "control": control,
                        "severity": severity,
                        "finding": message,
                        "kind": kind,
                    }
                )

            for ne_pk in targets:
                entry: dict[str, Any] = {"nePk": ne_pk, "coverage_complete": True}
                checks = {
                    "ids_ips": lambda ne_pk=ne_pk: summarize_ids_state(
                        client.appliance_api_call(version, ne_pk, IDS_IPS_STATE_READ)
                    ),
                    "zone_matrix": lambda ne_pk=ne_pk: summarize_zone_matrix(
                        client.appliance_api_call(version, ne_pk, ZONE_LIST_READ),
                        client.appliance_api_call(version, ne_pk, SECURITY_MAPS_READ),
                        client.appliance_api_call(version, ne_pk, SECURITY_MAP_SETTINGS_READ),
                    ),
                    "ddos": lambda ne_pk=ne_pk: {
                        "threshold_status": summarize_ddos(
                            client.appliance_api_call(version, ne_pk, DDOS_THRESHOLD_STATUS_READ)
                        ),
                        "protection_profiles": summarize_ddos(
                            client.appliance_api_call(version, ne_pk, DDOS_PROTECTION_PROFILE_READ)
                        ),
                    },
                    "tunnels": lambda ne_pk=ne_pk: summarize_tunnels(
                        client.appliance_api_call(version, ne_pk, TUNNELS_CONFIG_AND_STATE_READ)
                    ),
                }
                for control, read in checks.items():
                    try:
                        observation = read()
                        entry[control] = observation
                        evidence = observation.get("evidence_status", "observed")
                        if control == "ddos":
                            profiles = observation["protection_profiles"]
                            evidence = profiles["evidence_status"]
                            if profiles["disabled_zones"]:
                                finding(
                                    ne_pk,
                                    control,
                                    "high",
                                    f"DDoS protection disabled in zones {profiles['disabled_zones']}",
                                )
                        elif control == "ids_ips" and evidence == "observed":
                            if not observation["detection_enabled"]:
                                finding(ne_pk, control, "high", "IDS/IPS is not active")
                            elif not observation["prevention_enabled"]:
                                finding(
                                    ne_pk,
                                    control,
                                    "medium",
                                    "IDS detection is active; IPS prevention is disabled",
                                )
                        elif control == "zone_matrix":
                            if observation["uncovered_pair_count"]:
                                finding(
                                    ne_pk,
                                    control,
                                    "low",
                                    f"{observation['uncovered_pair_count']} directional zone pairs without explicit policy; review default action {observation['default_action']}",
                                    "review",
                                )
                            if observation["ambiguous_priorities"] or observation["invalid_rules"]:
                                finding(
                                    ne_pk,
                                    control,
                                    "medium",
                                    "Firewall rules contain invalid fields or ambiguous priorities",
                                    "review",
                                )
                            if observation["default_action"] == "unknown":
                                evidence = "unknown"
                        elif control == "tunnels":
                            if observation["down"]:
                                finding(
                                    ne_pk,
                                    control,
                                    "high",
                                    f"{observation['down']} tunnels down",
                                )
                            if observation["unknown"]:
                                evidence = "unknown"
                        if evidence != "observed":
                            entry["coverage_complete"] = False
                            finding(
                                ne_pk,
                                control,
                                "medium",
                                f"{control} evidence is {evidence}; protection cannot be inferred",
                                "coverage_gap",
                            )
                    except Exception as error:
                        entry[control] = {"error": str(error), "evidence_status": "error"}
                        entry["coverage_complete"] = False
                        finding(
                            ne_pk,
                            control,
                            "high",
                            f"{control} read failed: {error}",
                            "collection_error",
                        )
                entry["assessed_controls_complete"] = entry["coverage_complete"]
                entry["web_filtering"] = {
                    "evidence_status": "not_observed",
                    "reason": "Loaded profiles expose SSE connectivity, not URL/category filtering policy",
                    "enforcement_verified": False,
                }
                entry["coverage_complete"] = False
                finding(
                    ne_pk,
                    "web_filtering",
                    "medium",
                    "Web-filter policy and enforcement are not observed; check the SSE provider and lab probes",
                    "coverage_gap",
                )
                complete = complete and entry["coverage_complete"]
                results.append(entry)
            if not targets:
                finding(
                    "",
                    "inventory",
                    "high",
                    "No appliances resolved; security coverage is empty",
                    "coverage_gap",
                )
            findings.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}.get(item["severity"], 3))
            audit.record(
                "get_security_posture",
                "read",
                appliance_id,
                "complete" if complete else "incomplete",
                details={"appliances": len(results), "finding_count": len(findings)},
            )
            return json_result(
                {
                    "appliances": results,
                    "findings": findings,
                    "finding_count": len(findings),
                    "coverage_complete": complete,
                    "assessed_controls_complete": bool(results)
                    and all(row["assessed_controls_complete"] for row in results),
                    "enforcement_verified": False,
                    "coverage_scope": "configuration_and_state",
                },
                settings.max_output_chars,
            )
        except Exception as error:
            return f"Error: {error}"


    def record_security_event(
        tool: str,
        action: str,
        target: str,
        result: str,
        *,
        response: dict | None = None,
        before_write: bool = False,
        **kwargs,
    ) -> str | None:
        try:
            audit.record(tool, action, target, result, **kwargs)
            return None
        except OSError as error:
            if before_write:
                raise SecurityError(f"Cannot record security write attempt: {error}") from error
            if response is not None:
                response["audit_error"] = str(error)
            return str(error)


    def read_security_snapshot(client: OrchestratorClient, plan) -> dict:
        version = client.resolve_active_profile()
        if version != plan.version:
            raise SecurityError("API profile changed after preparation; prepare a new plan")
        if plan.ne_pk not in {str(a.get("nePk")) for a in client.list_appliances(refresh=True)}:
            raise SecurityError("Security target disappeared from the refreshed appliance inventory")
        if plan.control == "ids_ips":
            return validate_ids_snapshot(client.call(version, plan.read_operation))
        return validate_ddos_snapshot(client.appliance_api_call(version, plan.ne_pk, plan.read_operation))


    def write_security_snapshot(client: OrchestratorClient, plan, snapshot: dict) -> Any:
        if plan.control == "ids_ips":
            return client.call(plan.version, plan.write_operation, json_body=snapshot)
        return client.appliance_api_call(plan.version, plan.ne_pk, plan.write_operation, json_body=snapshot)


    @mcp.tool()
    def prepare_security_remediation(appliance_id: str, control: str, mode: str = "", profile_name: str = "") -> str:
        """Prepare a ten-minute, explicit-target plan: ids_ips changes one mode while preserving all assignments; ddos enables an existing assigned profile. NGFW/web-filter writes need validated contracts. No writes occur."""
        try:
            if control not in {"ids_ips", "ddos"}:
                raise SecurityError(
                    "Supported remediation controls: ids_ips, ddos. NGFW and web-filter writes require validated contracts"
                )
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            ne_pk = resolve_single_target(client, appliance_id)
            # Plans require positive inventory evidence, including direct IDs.
            if ne_pk not in {str(a.get("nePk")) for a in client.list_appliances(refresh=True)}:
                raise SecurityError("Target is not present in the refreshed appliance inventory")
            version = client.resolve_active_profile()
            payload = (
                client.call(version, IDS_STATE_READ)
                if control == "ids_ips"
                else client.appliance_api_call(version, ne_pk, DDOS_READ)
            )
            plan = prepare_security_plan(ne_pk, version, control, payload, mode, profile_name)
            security_plans.put(plan)
            record_security_event(
                "prepare_security_remediation",
                plan.write_operation,
                ne_pk,
                "prepared",
                dry_run=True,
                details=plan.public(),
            )
            return json_result({"dry_run": True, "plan": plan.public()}, settings.max_output_chars)
        except Exception as error:
            record_security_event("prepare_security_remediation", control, appliance_id, f"error: {error}")
            return f"Error: {error}"


    @mcp.tool()
    def apply_security_remediation(plan_id: str, confirmation: str = "", confirm: bool = False) -> str:
        """Apply a prepared snapshot once, with exact APPLY phrase and fresh conflict check; verify the complete desired configuration. An uncertain write must be verified, never blindly repeated."""
        try:
            plan = security_plans.get(plan_id)
            with security_plans.scope_lock(plan), plan.lock:
                if plan.status != "prepared":
                    raise SecurityError(f"Security plan status is {plan.status}; only prepared plans can be applied")
                if not confirm:
                    return json_result({"dry_run": True, "plan": plan.public()}, settings.max_output_chars)
                if confirmation != f"APPLY {plan.plan_id}":
                    raise SecurityError("Confirmation phrase does not match this security plan")
                guard = "security-disable" if plan.dangerous else plan.write_operation
                require_writes(guard, execute=False)
                if plan.dangerous and not settings.allow_dangerous_writes:
                    raise SecurityError("Protection downgrade requires EC_ALLOW_DANGEROUS_WRITES=true")
                client = require_client()
                if client is None:
                    return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
                if read_security_snapshot(client, plan) != plan.before:
                    raise SecurityError(
                        "Security configuration changed since preparation; conflict detected, prepare a new plan"
                    )
                record_security_event(
                    "apply_security_remediation",
                    plan.write_operation,
                    plan.ne_pk,
                    "attempt",
                    before_write=True,
                    details={
                        "plan_id": plan_id,
                        "before_sha256": fingerprint(plan.before),
                        "candidate_sha256": fingerprint(plan.candidate),
                    },
                )
                require_writes(guard)
                plan.status = "apply_unknown"
                try:
                    payload = write_security_snapshot(client, plan, plan.candidate)
                except Exception as error:
                    record_security_event(
                        "apply_security_remediation",
                        plan.write_operation,
                        plan.ne_pk,
                        "apply_unknown",
                        details={"plan_id": plan_id, "error": str(error)},
                    )
                    return json_result(
                        {
                            "applied": None,
                            "verified": False,
                            "error": str(error),
                            "next_step": "verify_security_remediation; do not repeat this write",
                            "plan": plan.public(),
                        },
                        settings.max_output_chars,
                    )
                plan.status = "applied"
                result = {
                    "applied": True,
                    "verified": False,
                    "result": payload,
                    "enforcement_verified": False,
                }
                try:
                    result["verified"] = read_security_snapshot(client, plan) == plan.candidate
                    plan.status = "verified" if result["verified"] else "verification_failed"
                except Exception as error:
                    plan.status = "verification_failed"
                    result["verification_error"] = str(error)
                result["plan"] = plan.public()
                record_security_event(
                    "apply_security_remediation",
                    plan.write_operation,
                    plan.ne_pk,
                    plan.status,
                    details={"plan_id": plan_id, "verified": result["verified"]},
                    response=result,
                )
                return json_result(result, settings.max_output_chars)
        except Exception as error:
            record_security_event("apply_security_remediation", "apply", plan_id, f"error: {error}")
            return f"Error: {error}"


    @mcp.tool()
    def verify_security_remediation(plan_id: str) -> str:
        """Re-read full state, compare with the desired snapshot, and keep missing evidence unverified. After rollback compare with the original snapshot."""
        try:
            plan = security_plans.get(plan_id)
            with security_plans.scope_lock(plan), plan.lock:
                client = require_client()
                if client is None:
                    return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
                rolling_back = plan.status.startswith("rollback") or plan.status == "rolled_back"
                expected = plan.before if rolling_back else plan.candidate
                try:
                    current = read_security_snapshot(client, plan)
                    verified = plan.status != "prepared" and current == expected
                    if plan.status != "prepared":
                        plan.status = (
                            ("rolled_back" if verified else "rollback_verification_failed")
                            if rolling_back
                            else ("verified" if verified else "verification_failed")
                        )
                    result = {
                        "verified": verified,
                        "observed_sha256": fingerprint(current),
                        "plan": plan.public(),
                        "enforcement_verified": False,
                    }
                except Exception as error:
                    if plan.status != "prepared":
                        plan.status = "rollback_verification_failed" if rolling_back else "verification_failed"
                    result = {
                        "verified": False,
                        "verification_error": str(error),
                        "plan": plan.public(),
                        "enforcement_verified": False,
                    }
                record_security_event(
                    "verify_security_remediation",
                    plan.read_operation,
                    plan.ne_pk,
                    plan.status,
                    details={"plan_id": plan_id, "verified": result["verified"]},
                    response=result,
                )
                return json_result(result, settings.max_output_chars)
        except Exception as error:
            return f"Error: {error}"


    @mcp.tool()
    def rollback_security_remediation(plan_id: str, confirmation: str = "", confirm: bool = False) -> str:
        """Restore the full original snapshot only while current state equals this plan's candidate. Exact ROLLBACK phrase, write permission and dangerous-write permission are required."""
        try:
            plan = security_plans.get(plan_id)
            with security_plans.scope_lock(plan), plan.lock:
                if plan.status not in {
                    "applied",
                    "verified",
                    "verification_failed",
                    "apply_unknown",
                }:
                    raise SecurityError("Only an applied or uncertain security plan can be rolled back")
                if not confirm:
                    return json_result({"dry_run": True, "plan": plan.public()}, settings.max_output_chars)
                if confirmation != f"ROLLBACK {plan.plan_id}":
                    raise SecurityError("Rollback confirmation phrase does not match this security plan")
                require_writes("security-rollback", execute=False)
                if not settings.allow_dangerous_writes:
                    raise SecurityError("Security rollback requires EC_ALLOW_DANGEROUS_WRITES=true")
                client = require_client()
                if client is None:
                    return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
                if read_security_snapshot(client, plan) != plan.candidate:
                    raise SecurityError(
                        "Security state drifted or apply is incomplete; refusing to overwrite it during rollback"
                    )
                record_security_event(
                    "rollback_security_remediation",
                    plan.write_operation,
                    plan.ne_pk,
                    "attempt",
                    before_write=True,
                    details={
                        "plan_id": plan_id,
                        "restore_sha256": fingerprint(plan.before),
                    },
                )
                require_writes("security-rollback")
                plan.status = "rollback_unknown"
                try:
                    write_security_snapshot(client, plan, plan.before)
                except Exception as error:
                    record_security_event(
                        "rollback_security_remediation",
                        plan.write_operation,
                        plan.ne_pk,
                        "rollback_unknown",
                        details={"plan_id": plan_id, "error": str(error)},
                    )
                    return json_result(
                        {
                            "rolled_back": None,
                            "verified": False,
                            "error": str(error),
                            "plan": plan.public(),
                        },
                        settings.max_output_chars,
                    )
                result = {
                    "rolled_back": True,
                    "verified": False,
                    "enforcement_verified": False,
                }
                try:
                    result["verified"] = read_security_snapshot(client, plan) == plan.before
                    plan.status = "rolled_back" if result["verified"] else "rollback_verification_failed"
                except Exception as error:
                    plan.status = "rollback_verification_failed"
                    result["verification_error"] = str(error)
                result["plan"] = plan.public()
                record_security_event(
                    "rollback_security_remediation",
                    plan.write_operation,
                    plan.ne_pk,
                    plan.status,
                    details={"plan_id": plan_id, "verified": result["verified"]},
                    response=result,
                )
                return json_result(result, settings.max_output_chars)
        except Exception as error:
            record_security_event("rollback_security_remediation", "rollback", plan_id, f"error: {error}")
            return f"Error: {error}"


    @mcp.tool()
    def apply_change(
        operation_id: str,
        body_json: str = "",
        appliance_id: str = "",
        group_id: str = "",
        interface_name: str = "",
        extra_path_params_json: str = "",
        extra_query_params_json: str = "",
        verify_operation_id: str = "",
        confirm: bool = False,
    ) -> str:
        """Apply a configuration change through the Orchestrator/Appliance API. Dry-run by default: without confirm=true it returns the method, resolved path, query and body. Effective permissions are those of the authenticated user. Use list_api_operations to discover contracts. Catalog-declared array bodies are accepted. verify_operation_id must be a GET and is validated before writing; its result is a read-after-write observation, not a comparison with desired state. A failed read after a successful write returns applied=true plus read_after_write_error: do not repeat that write. Only confirmed writes consume the local write quota."""
        try:
            require_writes(operation_id, execute=False)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            operation = engine.resolve(version, operation_id)
            if is_read_only_operation(engine._profiles[version]["operations"][operation_id]):
                raise SecurityError("Use call_read_api for read-only operations")
            extras = {
                **_parse_json_object(extra_path_params_json, "extra_path_params_json"),
                **_parse_json_object(extra_query_params_json, "extra_query_params_json"),
            }
            path_params, query_params = build_params(
                version,
                operation_id,
                appliance_id,
                group_id,
                interface_name,
                extras,
            )
            operation = engine.resolve(version, operation_id, path_params)
            verify_op = None
            verify_path_params, verify_query_params = {}, {}
            if verify_operation_id:
                verify_op = engine.resolve(version, verify_operation_id)
                if verify_op.method != "GET" or not is_read_only_operation(
                    engine._profiles[version]["operations"][verify_operation_id]
                ):
                    raise SecurityError("verify_operation_id must be a GET operation")
                verify_path_params, verify_query_params = build_params(
                    version,
                    verify_operation_id,
                    appliance_id,
                    group_id,
                    interface_name,
                    extras,
                )
                verify_op = engine.resolve(version, verify_operation_id, verify_path_params)
            body: dict | list | None = None
            if body_json.strip():
                parsed = json.loads(body_json)
                example_for_body = operation_details(version, operation_id).get("body_example")
                if isinstance(parsed, dict):
                    body = parsed
                elif isinstance(parsed, list) and isinstance(example_for_body, list):
                    body = parsed
                else:
                    raise SecurityError(
                        "body_json must be a JSON object"
                        + (" (or an array matching the catalog's array body_example)" if isinstance(parsed, list) else "")
                    )
            example = operation_details(version, operation_id).get("body_example")
            placeholder_example = isinstance(example, dict) and any(
                str(key).lower().startswith("placeholderproperty") for key in example
            )
            spec = engine._profiles[version]["operations"][operation_id]
            query_only_write = bool(spec.get("query_params")) and not spec.get("body_example")
            if confirm and operation.method in ("POST", "PUT", "PATCH") and not body and not query_only_write:
                raise SecurityError(
                    "Refusing a confirmed write with an empty JSON body. "
                    "Discover the required schema or copy a known-good object before applying."
                )
            if confirm and placeholder_example:
                raise SecurityError(
                    "Refusing a confirmed write because the catalog only has placeholder fields "
                    "for this endpoint. Capture a valid schema or known-good object first."
                )
            if confirm and operation_id == "appliance.deploymentpost567554":
                guard_partial_deployment_body(body)
            guard_cli_body(operation.path, body)
            if confirm and security_write_guard(operation.path, operation.method, body, query_params):
                require_writes("security-disable-or-DELETE", execute=False)
            ne_pk = None
            if operation_id.startswith("appliance.") or verify_operation_id.startswith("appliance."):
                ne_pk = resolve_single_target(client, appliance_id)
                if {"nePk", "url"} & extras.keys():
                    raise SecurityError("Proxy routing parameters cannot be overridden")
            audit_entry = {
                **operation_details(version, operation_id),
                "resolved_path": operation.path,
                "query": query_params,
                "body": body,
                "confirmed": confirm,
            }
            audit_public_entry = {k: v for k, v in audit_entry.items() if k != "body"}
            if isinstance(body, dict):
                audit_public_entry["body_keys"] = sorted(body.keys())
            elif isinstance(body, list):
                audit_public_entry["body_items"] = len(body)
            else:
                audit_public_entry["body_keys"] = []
            if not confirm:
                record_security_event(
                    "apply_change",
                    operation_id,
                    operation.path,
                    "dry-run",
                    dry_run=True,
                    details=audit_public_entry,
                )
                return json_result(
                    {"dry_run": True, "would_execute": audit_entry},
                    settings.max_output_chars,
                )
            record_security_event(
                "apply_change",
                operation_id,
                operation.path,
                "attempt",
                before_write=True,
                details=audit_public_entry,
            )
            require_writes(operation_id)
            try:
                if operation_id.startswith("appliance."):
                    payload = client.appliance_api_call(
                        version,
                        ne_pk,
                        operation_id,
                        path_params=path_params,
                        json_body=body,
                        **query_params,
                    )
                else:
                    payload = client.call(
                        version,
                        operation_id,
                        path_params=path_params,
                        json_body=body,
                        **query_params,
                    )
            except Exception as error:
                result = {
                    "applied": None,
                    "error": str(error),
                    "write_status": "unknown",
                    "next_step": "Read live state before preparing a new change; do not automatically repeat this write",
                }
                record_security_event(
                    "apply_change",
                    operation_id,
                    operation.path,
                    "write_unknown",
                    response=result,
                    details={"error": str(error)},
                )
                return json_result(result, settings.max_output_chars)
            audit_error = record_security_event(
                "apply_change",
                operation_id,
                operation.path,
                "ok",
                dry_run=False,
                details=audit_public_entry,
            )
            result = {
                "applied": True,
                "result": payload,
                "read_after_write": None,
                "read_after_write_status": "not_requested",
                "audit_error": audit_error,
            }
            if verify_op is not None:
                try:
                    if verify_operation_id.startswith("appliance."):
                        result["read_after_write"] = client.appliance_api_call(
                            version,
                            ne_pk,
                            verify_operation_id,
                            path_params=verify_path_params,
                            **verify_query_params,
                        )
                    else:
                        result["read_after_write"] = client.call(
                            version,
                            verify_operation_id,
                            path_params=verify_path_params,
                            **verify_query_params,
                        )
                    result["read_after_write_status"] = "ok"
                    record_security_event(
                        "apply_change",
                        verify_operation_id,
                        verify_op.path,
                        "read-after-write",
                        dry_run=False,
                    )
                except Exception as error:
                    result["read_after_write_status"] = "error"
                    result["read_after_write_error"] = str(error)
                    record_security_event(
                        "apply_change",
                        verify_operation_id,
                        verify_op.path,
                        "verification-error",
                        details={"error": str(error)},
                    )
            return json_result(result, settings.max_output_chars)
        except json.JSONDecodeError as error:
            record_security_event("apply_change", operation_id, "", f"invalid body JSON: {error}")
            return f"Invalid body_json: {error}"
        except Exception as error:
            record_security_event("apply_change", operation_id, "", f"error: {error}")
            return f"Error: {error}"

    return mcp


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
