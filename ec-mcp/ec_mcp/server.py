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
from .cli_catalog import (
    catalog_entries,
    total_commands,
)
from .compat import CompatibilityEngine, load_profiles
from .config import Settings
from .orchestrator_client import OrchestratorClient
from .security import SecurityError, redact_secrets, sanitize_output
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
        text = json.dumps(payload, ensure_ascii=False, default=str)
        return redact_secrets(sanitize_output(text, max_chars), [])

    def closed_json_result(payload: dict, max_chars: int) -> tuple[str, bool]:
        """Serialize to JSON that is ALWAYS valid: never returns a cut string.

        If the payload exceeds max_chars, wraps it with explicit truncation
        metadata instead of slicing the serialized text mid-literal.
        """
        text = json.dumps(payload, ensure_ascii=False, default=str)
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
        wrapper["excerpt"] = text[: max(0, budget)]
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
            payload = {
                "detected_version": detected,
                "active_profile": matched,
                "available_profiles": engine.versions,
                "write_tools_enabled": settings.allow_write_tools,
                "ssh_enabled": settings.ssh_enabled,
                "cli_commands_available": total_commands(),
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
                             page: int = 0, page_size: int = 200, include_examples: bool = False) -> str:
        """List the stable API operation IDs with method, path, risk and params, paginated and filterable. Filters: search (substring on operation id AND path), prefix (operation id prefix), method (GET/POST/PUT/DELETE). By default body_example is omitted to keep the payload small; pass include_examples=true to include it. Response is always valid JSON with total_operations, page, has_more_page; call with page+1 for the next chunk."""
        try:
            if version and version not in engine._profiles:
                return f"Unknown version {version}. Available: {engine.versions}"
            versions = [version] if version else engine.versions
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
        """Invoke a read-only Orchestrator/Appliance API operation by stable operation ID. Use list_api_operations(search=...) to find operation IDs, or list_appliances to get the appliances with their nePk. appliance_id accepts nePk, name, IP or serial. For list responses use fields (comma-separated columns), offset/limit and max_chars to page through data; the response is always complete valid JSON with pagination metadata (total_count, next_offset) — never a cut string."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            if operation_id not in engine._profiles[version]["operations"]:
                return operation_not_found_error(version, operation_id)
            spec = engine._profiles[version]["operations"][operation_id]
            missing_required: list[str] = []
            needs_ne_pk = "nePk" in (spec.get("query_params") or []) or "nePk" in (
                spec.get("path_params") or []
            )
            if needs_ne_pk and not appliance_id and "nePk" not in (
                json.dumps(_parse_json_object(extra_query_params_json, "extra_query_params_json"))
                if extra_query_params_json.strip()
                else ""
            ):
                missing_required.append("appliance_id (nePk)")
            if "/stats/" in spec["path"] and not granularity:
                missing_required.append("granularity")
            if "/timeseries/" in spec["path"]:
                if not start_time:
                    missing_required.append("start_time")
                if not end_time:
                    missing_required.append("end_time")
            if missing_required:
                return json_result(
                    {
                        "error": "PARAM_REQUIRED",
                        "operation_id": operation_id,
                        "required_params": missing_required,
                        "hint": "Provide the missing parameters; no upstream call was made.",
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
                if appliance_id:
                    query_params.setdefault("nePk", resolve_ne_pk(client, appliance_id))
                    path_params.setdefault("nePk", query_params["nePk"])
                payload = client.call(version, operation_id, path_params=path_params, **query_params)
            field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else []
            if field_list or offset or limit:
                paginated, _ = paginate_data(payload, max(0, offset), limit or None, field_list)
                payload = paginated
            budget = max(2000, min(max_chars or settings.max_output_chars, 50000))
            wrapper = {
                "data": payload,
                "request_echo": {
                    "operation_id": operation_id,
                    "resolved_path": operation.path,
                    "query_used": {k: str(v) for k, v in query_params.items()},
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
