from __future__ import annotations

import json
import re
import time
from collections import deque
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
from .compat import CompatibilityEngine, load_profiles
from .config import Settings
from .orchestrator_client import OrchestratorClient
from .security import SecurityError, redact_secrets, redact_sensitive_values
from .ssh_ecos import ApplianceSshPool


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
        r"(?i)reboot|suspend|delete|remove|wipe|factory|purge|halt|shutdown|decommission"
    )
    write_timestamps: deque[float] = deque()

    def require_writes(operation: str = "") -> None:
        if not settings.allow_write_tools:
            raise SecurityError("Write tools are disabled (EC_ALLOW_WRITE_TOOLS != true)")
        if operation and DANGEROUS_OPERATION_PATTERN.search(operation):
            if not settings.allow_dangerous_writes:
                raise SecurityError(
                    f"Operation '{operation}' is classified as dangerous and requires "
                    "EC_ALLOW_DANGEROUS_WRITES=true"
                )
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
            return redact_secrets(text, []), False
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
                    return redact_secrets(trimmed_text, []), True
        wrapper = {"truncated": True, "max_chars": max_chars}
        wrapper["hint"] = "Payload exceeded max_chars; reduce the result with fields/limit or raise max_chars."
        wrapper["excerpt"] = redact_secrets(text, [])[: max(0, budget)]
        return redact_secrets(json.dumps(wrapper, ensure_ascii=False, default=str), []), True

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
            value = source.get(name) or ""
            if not value:
                raise SecurityError(f"Missing required path parameter '{name}' for operation '{operation_id}'")
            path_params[name] = value
        for name in operation.get("query_params", []):
            value = source.get(name)
            if value:
                query_params[name] = str(value)
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
            return [str(a.get("nePk")) for a in client.list_appliances()]
        resolved = []
        for part in appliance_ids.split(","):
            part = part.strip()
            if part:
                resolved.append(resolve_ne_pk(client, part))
        return resolved

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
        "tunnelname", "tunnelid", "overlayid", "nepk", "source", "destination",
        "mos", "min_mos", "max_mos", "avg_mos", "mos_score",
        "jitter", "loss", "latency", "rtt", "packetslost", "losspercent",
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

    def _project_fields(node: Any, field_list: list[str]) -> Any:
        """Apply a client-requested field projection at the tunnel/KPI level."""
        if isinstance(node, list):
            return [_project_fields(item, field_list) for item in node]
        if not isinstance(node, dict):
            return node
        lowered = {str(k).lower(): k for k in node}
        kept = {}
        for f in field_list:
            key = lowered.get(f.strip().lower())
            if key is not None:
                kept[key] = _project_fields(node[key], field_list)
        if kept:
            return kept
        nested = {k: _project_fields(v, field_list) for k, v in node.items() if isinstance(v, (dict, list))}
        if any(nested.values()):
            return nested
        return {k: v for k, v in node.items() if str(k).lower() in ("tunnelname", "tunnel", "tunnelid")} or node

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
        return {str(k): str(v) for k, v in parsed.items()}

    def classify_cli_command(command: str) -> str | None:
        lowered = command.strip().lower()
        if not lowered:
            return None
        for entry in sorted(cli_risk_by_command, key=len, reverse=True):
            if lowered == entry or lowered.startswith(entry + " "):
                return cli_risk_by_command[entry]
        return None

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
                ops = []
                lowered_search = search.lower()
                lowered_prefix = prefix.lower()
                for op_id in sorted(profile_ops):
                    spec = profile_ops[op_id]
                    if lowered_prefix and not op_id.lower().startswith(lowered_prefix):
                        continue
                    if lowered_search and lowered_search not in op_id.lower() and lowered_search not in spec["path"].lower():
                        continue
                    if method and spec["method"].upper() != method.upper():
                        continue
                    ops.append(op_id)
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
                            "data": kpi_get(client, "mos", ne_pk, granularity, start_time, end_time),
                        })
                    except Exception as error:
                        rows.append({"nePk": ne_pk, "error": str(error)[:200]})
                payload = {"appliances": rows, "total_count": len(rows)}
            else:
                ne_pk = resolve_ne_pk(client, appliance_id)
                payload = kpi_get(client, "mos", ne_pk, granularity, start_time, end_time)
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
            return f"Error: {error}

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
    def get_ztp_status() -> str:
        """Zero-Touch Provisioning status with bounded, credential-free discovery rows."""
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
            result = {
                "manual_provisioning": manual,
                "discovered_count": len(discovered),
                "discovered": discovered,
            }
            audit.record("get_ztp_status", "read", settings.orchestrator_url, "ok", details={"discovered": len(discovered)})
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
            multi_targets: list[str] = []
            if appliance_id.strip().lower() == "all":
                multi_targets = [str(a.get("nePk")) for a in client.list_appliances()]
                appliance_id = ""
            missing_required: list[str] = []
            granularity_hint = False
            needs_ne_pk = "nePk" in (spec.get("query_params") or []) or "nePk" in (
                spec.get("path_params") or []
            )
            if needs_ne_pk and not appliance_id and "nePk" not in (
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
                appliance_id,
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
            if operation_id.startswith("appliance."):
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
                    appliance_path = operation.path
                    for key, value in path_params.items():
                        appliance_path = appliance_path.replace("{" + key + "}", value)
                    appliance_path = appliance_path.replace("{appliance_id}", ne_pk)
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
                    proxy_path = operation.path
                    for key, value in path_params.items():
                        proxy_path = proxy_path.replace("{" + key + "}", value)
                    proxy_path = proxy_path.replace("{appliance_id}", proxy_ne_pk)
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
    def run_cli_command(command: str, host: str = "", confirm: bool = False) -> str:
        """Run any official ECOS CLI command from the CLI Reference on an appliance over SSH. Monitoring/troubleshooting commands execute directly; configuration/administration/negation commands are dry-run by default and require confirm=true plus EC_ALLOW_WRITE_TOOLS=true. Use list_cli_commands to discover the 1367 available commands."""
        pool = ApplianceSshPool(settings)
        target = host or settings.ssh_host
        try:
            risk = classify_cli_command(command)
            if risk is None:
                raise SecurityError(f"Command not in the official ECOS CLI catalog: {command}")
            if risk == "write":
                require_writes()
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

    @mcp.tool()
    def apply_change(
        operation_id: str,
        body_json: str = "",
        appliance_id: str = "",
        group_id: str = "",
        interface_name: str = "",
        extra_path_params_json: str = "",
        extra_query_params_json: str = "",
        confirm: bool = False,
    ) -> str:
        """Apply a configuration change through the Orchestrator/Appliance API. Dry-run by default: without confirm=true it returns the exact method, path and body that would be executed. Effective permissions are those of the authenticated user. Use list_api_operations to discover available write operations and their required parameters."""
        try:
            require_writes(operation_id)
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            operation = engine.resolve(version, operation_id)
            if operation.method == "GET":
                raise SecurityError("Use call_read_api for GET operations")
            path_params, query_params = build_params(
                version,
                operation_id,
                appliance_id,
                group_id,
                interface_name,
                {
                    **_parse_json_object(extra_path_params_json, "extra_path_params_json"),
                    **_parse_json_object(extra_query_params_json, "extra_query_params_json"),
                },
            )
            body: dict | None = None
            if body_json.strip():
                parsed = json.loads(body_json)
                if not isinstance(parsed, dict):
                    raise SecurityError("body_json must be a JSON object")
                body = parsed
            audit_entry = {
                **operation_details(version, operation_id),
                "resolved_path": operation.path,
                "body": body,
                "confirmed": confirm,
            }
            audit_public_entry = {k: v for k, v in audit_entry.items() if k != "body"}
            audit_public_entry["body_keys"] = sorted(body.keys()) if body else []
            if not confirm:
                audit.record("apply_change", operation_id, operation.path, "dry-run", dry_run=True, details=audit_public_entry)
                return json_result({"dry_run": True, "would_execute": audit_entry}, settings.max_output_chars)
            payload = client.call(version, operation_id, path_params=path_params, json_body=body, **query_params)
            audit.record("apply_change", operation_id, operation.path, "ok", dry_run=False, details=audit_public_entry)
            return json_result({"applied": True, "result": payload}, settings.max_output_chars)
        except json.JSONDecodeError as error:
            audit.record("apply_change", operation_id, "", f"invalid body JSON: {error}")
            return f"Invalid body_json: {error}"
        except Exception as error:
            audit.record("apply_change", operation_id, "", f"error: {error}")
            return f"Error: {error}"

    return mcp


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
