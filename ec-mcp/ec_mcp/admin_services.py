"""Real service probes for the ec-mcp admin panel (Phase 2, refs #88).

Every status reported here is the result of an actual request against the
configured backend at probe time. The panel must never present a service as
ready without a successful, recent check, and probe results are recorded in
the structured audit log without secrets.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from .audit import AuditLog
from .config import Settings
from .multi_target import load_registry

PROBE_TIMEOUT = 10.0
PROBE_CACHE_SECONDS = 15.0


def _now() -> datetime:
    return datetime.now(UTC)


class ServiceProbeError(RuntimeError):
    pass


def _audit() -> AuditLog:
    return AuditLog(Settings.from_env().audit_log_path)


def _record(action: str, target: str, result: str, details: dict[str, Any] | None = None) -> None:
    _audit().record(tool="admin_panel", action=action, target=target, result=result, details=details)


def probe_orchestrator(entry: dict[str, Any]) -> dict[str, Any]:
    """Perform a real health request against an Orchestrator target."""
    url = str(entry.get("url") or "").strip()
    if not url:
        raise ServiceProbeError("El orquestador no tiene URL configurada.")
    verify_tls = entry.get("verify_tls", True)
    headers: dict[str, str] = {}
    api_key = entry.get("api_key")
    username = entry.get("username")
    password = entry.get("password")
    if api_key:
        headers["X-Auth-Token"] = str(api_key)
    elif username:
        headers["X-Auth-User"] = str(username)
        headers["X-Auth-Pass"] = str(password or "")
    started = _now()
    with httpx.Client(base_url=url, verify=verify_tls, timeout=PROBE_TIMEOUT) as client:
        response = client.get("/gms/rest/system/healthcheck", headers=headers)
    elapsed = (_now() - started).total_seconds()
    if response.status_code != 200:
        raise ServiceProbeError(f"HTTP {response.status_code} al consultar el orquestador.")
    return {"latency": elapsed, "status_code": response.status_code}


def probe_axis(entry: dict[str, Any]) -> dict[str, Any]:
    """Perform a real health request against an Axis Security SSE platform."""
    base_url = str(entry.get("base_url") or "").strip()
    token = str(entry.get("admin_token") or "").strip()
    if not base_url:
        raise ServiceProbeError("La plataforma SSE no tiene URL base configurada.")
    if not token:
        raise ServiceProbeError("La plataforma SSE no tiene token de administración.")
    verify_tls = entry.get("verify_tls", True)
    started = _now()
    with httpx.Client(base_url=base_url, verify=verify_tls, timeout=PROBE_TIMEOUT) as client:
        response = client.get("/Health", headers={"Authorization": f"Bearer {token}"})
    elapsed = (_now() - started).total_seconds()
    if response.status_code != 200:
        raise ServiceProbeError(f"HTTP {response.status_code} al consultar la plataforma SSE.")
    return {"latency": elapsed, "status_code": response.status_code}


def probe_update_service() -> dict[str, Any]:
    """Return the real updater worker state; never fabricate 'ready'."""
    from . import web_update

    return web_update.status()


def mcp_probe_url() -> str:
    """URL de sondeo del transporte MCP; 0.0.0.0/:: se sustituye por loopback."""
    host = os.environ.get("EC_MCP_HOST", "127.0.0.1")
    if host in ("0.0.0.0", "::", ""):  # nosec B104 - solo se sustituye por loopback para el sondeo local
        host = "127.0.0.1"
    port = int(os.environ.get("EC_MCP_PORT", "8000"))
    scheme = "https" if os.environ.get("EC_MCP_TLS_CERT") else "http"
    return f"{scheme}://{host}:{port}/health"


def probe_mcp_transport() -> dict[str, Any]:
    """Check the local MCP transport listener; falls back to loopback if needed."""
    candidates = [mcp_probe_url()]
    fallback = mcp_probe_url()
    if "127.0.0.1" not in fallback and "localhost" not in fallback:
        candidates.append(fallback.replace(f"://{os.environ.get('EC_MCP_HOST', '')}", "://127.0.0.1"))
    started = _now()
    last_error = ""
    for url in candidates:
        try:
            with httpx.Client(verify=True, timeout=PROBE_TIMEOUT) as client:
                response = client.get(url)
            if response.status_code == 200:
                return {
                    "state": "up",
                    "latency": (_now() - started).total_seconds(),
                    "status_code": response.status_code,
                    "url": url,
                }
            last_error = f"HTTP {response.status_code} en {url}"
        except httpx.HTTPError as exc:
            last_error = f"{url}: {type(exc).__name__}"
    raise ServiceProbeError(f"No hay respuesta del transporte MCP ({last_error})")


def services_status(probe: bool = True) -> dict[str, Any]:
    """Build the real services status consumed by the admin panel."""
    report: dict[str, Any] = {
        "checked_at": _now().isoformat(),
        "probe": bool(probe),
        "orchestrators": [],
        "sse_platforms": [],
        "update_worker": {},
        "mcp_transport": {},
    }
    if not probe:
        return report
    registry = load_registry()
    for name, entry in sorted((registry.list_orchestrators() or {}).items()):
        item: dict[str, Any] = {"name": name}
        try:
            result = probe_orchestrator(entry)
            item.update({"state": "up", **result})
        except (ServiceProbeError, httpx.HTTPError, ValueError) as exc:
            item.update({"state": "down", "error": str(exc)})
        item["checked_at"] = _now().isoformat()
        report["orchestrators"].append(item)
    for name, entry in sorted((registry.list_sse() or {}).items()):
        item = {"name": name}
        try:
            result = probe_axis(entry)
            item.update({"state": "up", **result})
        except (ServiceProbeError, httpx.HTTPError, ValueError) as exc:
            item.update({"state": "down", "error": str(exc)})
        item["checked_at"] = _now().isoformat()
        report["sse_platforms"].append(item)
    try:
        report["update_worker"] = probe_update_service()
    except (OSError, ValueError) as exc:
        report["update_worker"] = {"state": "unknown", "error": str(exc)}
    try:
        report["mcp_transport"] = probe_mcp_transport()
    except (ServiceProbeError, ValueError) as exc:
        report["mcp_transport"] = {"state": "down", "error": str(exc)}
    _record("services_status", "panel", "checked", {"probes": len(report["orchestrators"]) + len(report["sse_platforms"]) + 2})
    return report


def request_restart(reason: str = "") -> dict[str, Any]:
    """Queue a restart request with explicit audit trail (never autostop)."""
    from .web_update import queue_restart

    result = queue_restart()
    _record("restart_requested", "panel", "pending", {"reason": reason[:200]})
    return result


def request_update(remote_sha: str, confirmation: str) -> dict[str, Any]:
    """Queue an update request with explicit audit trail."""
    from .web_update import queue_update

    result = queue_update(remote_sha, confirmation)
    _record("update_requested", "panel", "pending", {"commit": remote_sha})
    return result
