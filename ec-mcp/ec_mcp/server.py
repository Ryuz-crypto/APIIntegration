from __future__ import annotations

import json
import re
import time
from collections import deque

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

    def require_client() -> OrchestratorClient | None:
        try:
            return OrchestratorClient(settings, engine)
        except ValueError:
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

    @mcp.tool()
    def list_api_operations(version: str = "", prefix: str = "", page: int = 0, page_size: int = 200) -> str:
        """List the stable API operation IDs with method, risk and parameters, paginated. Use prefix to filter by operation family (e.g. 'appliance.interfaces', 'orchestrator', 'stats') and page/page_size to walk the full catalog (~1500 operations per version). Call with the same filters and page+1 to get the next chunk; has_more_page tells you when to stop."""
        try:
            if version and version not in engine._profiles:
                return f"Unknown version {version}. Available: {engine.versions}"
            versions = [version] if version else engine.versions
            page = max(0, int(page))
            page_size = min(max(1, int(page_size)), 500)
            payload: dict = {}
            has_more = False
            for v in versions:
                ops = sorted(engine._profiles[v]["operations"])
                if prefix:
                    lowered = prefix.lower()
                    ops = [op for op in ops if op.lower().startswith(lowered)]
                start = page * page_size
                chunk = ops[start : start + page_size]
                has_more = has_more or start + page_size < len(ops)
                payload[v] = {
                    "total_operations": len(ops),
                    "page": page,
                    "page_size": page_size,
                    "has_more_pages": start + page_size < len(ops),
                    "operations": {op: operation_details(v, op) for op in chunk},
                }
            result = {"has_more_page": has_more, "versions": payload}
            audit.record("list_api_operations", "read", "profiles", "ok", details={"prefix": prefix, "page": page})
            return json_result(result, settings.max_output_chars * 2)
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
            appliances = client.list_appliances()
            audit.record("list_appliances", "read", settings.orchestrator_url, "ok", details={"count": len(appliances)})
            return json_result({"count": len(appliances), "appliances": appliances}, settings.max_output_chars)
        except Exception as error:
            audit.record("list_appliances", "read", settings.orchestrator_url, f"error: {error}")
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
    ) -> str:
        """Invoke a read-only Orchestrator/Appliance API operation by stable operation ID. Use list_api_operations to discover the ~1500 available operations, or list_appliances to get the appliances with their nePk. appliance_id accepts a nePk (e.g. 1.NE), a device name, an IP or a serial number; per-appliance operations (flows, tunnels, interfaces, stats...) are proxied through the Orchestrator so no direct appliance connectivity is needed."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
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
            if version and operation_id.startswith("appliance."):
                profile = engine._profiles[version]
                profile_ops = profile["operations"][operation_id]
                needs_ne = "nePk" in (profile_ops.get("query_params") or []) or "nePk" in (profile_ops.get("path_params") or [])
                if needs_ne and not query_params.get("nePk"):
                    if not appliance_id:
                        raise SecurityError(
                            f"Operation '{operation_id}' is appliance-scoped: pass appliance_id "
                            "(nePk, name or IP; discover them with list_appliances)."
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
                        raise SecurityError(
                            f"Operation '{operation_id}' is missing path parameters {missing}; "
                            "pass them via extra_path_params_json."
                        )
                    payload = client.appliance_api_get(ne_pk, appliance_path, **query_params)
            else:
                if appliance_id:
                    query_params.setdefault("nePk", resolve_ne_pk(client, appliance_id))
                    path_params.setdefault("nePk", query_params["nePk"])
                payload = client.call(version, operation_id, path_params=path_params, **query_params)
            audit.record("call_read_api", operation_id, settings.orchestrator_url, "ok")
            return json_result(payload, settings.max_output_chars)
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
