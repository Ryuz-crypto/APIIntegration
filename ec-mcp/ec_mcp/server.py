from __future__ import annotations

import json
from functools import wraps

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as FastMCP

from .audit import AuditLog
from .compat import CompatibilityEngine, load_profiles
from .config import Settings
from .orchestrator_client import OrchestratorClient
from .security import SecurityError, sanitize_output
from .ssh_ecos import ApplianceSshPool


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or Settings.from_env()
    engine = CompatibilityEngine(load_profiles(settings.profiles_dir))
    audit = AuditLog(settings.audit_log_path)
    mcp = FastMCP("edgeconnect-sdwan")

    def require_client() -> OrchestratorClient | None:
        try:
            return OrchestratorClient(settings, engine)
        except ValueError:
            return None

    def require_writes() -> None:
        if not settings.allow_write_tools:
            raise SecurityError("Write tools are disabled (EC_ALLOW_WRITE_TOOLS != true)")

    def json_result(payload, max_chars: int) -> str:
        text = json.dumps(payload, ensure_ascii=False, default=str)
        return sanitize_output(text, max_chars)

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
            }
            audit.record("orchestrator_info", "detect", settings.orchestrator_url, "ok", details=payload)
            return json_result(payload, settings.max_output_chars)
        except Exception as error:
            audit.record("orchestrator_info", "detect", settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def list_api_operations() -> str:
        """List the stable operation IDs available for each supported API version."""
        payload = {version: engine.list_operations(version) for version in engine.versions}
        audit.record("list_api_operations", "read", "profiles", "ok")
        return json_result(payload, settings.max_output_chars)

    @mcp.tool()
    def call_read_api(operation_id: str, appliance_id: str = "", start_time: str = "", end_time: str = "", granularity: str = "") -> str:
        """Invoke a read-only Orchestrator API operation by stable operation ID (e.g. orchestrator.topology, orchestrator.inventory.summary, appliance.tunnels, appliance.interfaces, appliance.performance)."""
        try:
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            operation = engine.resolve(version, operation_id)
            if operation.method != "GET":
                raise SecurityError(f"Operation '{operation_id}' is not read-only; use a write tool")
            path_params = {"appliance_id": appliance_id} if appliance_id else {}
            payload = client.call(
                version,
                operation_id,
                path_params=path_params,
                cached="false",
                start_time=start_time or None,
                end_time=end_time or None,
                granularity=granularity or None,
            )
            audit.record("call_read_api", operation_id, settings.orchestrator_url, "ok")
            return json_result(payload, settings.max_output_chars)
        except Exception as error:
            audit.record("call_read_api", operation_id, settings.orchestrator_url, f"error: {error}")
            return f"Error: {error}"

    @mcp.tool()
    def run_show_command(command: str, host: str = "") -> str:
        """Run a whitelisted read-only ECOS 'show' command on an EdgeConnect appliance over SSH."""
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
    def apply_change(operation_id: str, body_json: str = "", confirm: bool = False) -> str:
        """Apply a configuration change through the Orchestrator API. Dry-run by default: without confirm=true it only returns the operation and body that would be executed."""
        try:
            require_writes()
            client = require_client()
            if client is None:
                return "Orchestrator is not configured. Set EC_ORCHESTRATOR_URL and credentials."
            version = client.resolve_active_profile()
            operation = engine.resolve(version, operation_id)
            if operation.method == "GET":
                raise SecurityError("Use call_read_api for GET operations")
            body: dict | None = None
            if body_json.strip():
                parsed = json.loads(body_json)
                if not isinstance(parsed, dict):
                    raise SecurityError("body_json must be a JSON object")
                body = parsed
            audit_entry = {
                "operation": operation_id,
                "method": operation.method,
                "path": operation.path,
                "body": body,
                "confirmed": confirm,
            }
            if not confirm:
                audit.record("apply_change", operation_id, operation.path, "dry-run", dry_run=True, details=audit_entry)
                return json_result({"dry_run": True, "would_execute": audit_entry}, settings.max_output_chars)
            payload = client.call(version, operation_id, json_body=body)
            audit.record("apply_change", operation_id, operation.path, "ok", dry_run=False, details=audit_entry)
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
