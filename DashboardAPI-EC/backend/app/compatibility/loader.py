import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROFILES_DIR = Path(__file__).parent / "profiles"


def load_builtin_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in sorted(PROFILES_DIR.glob("edgeconnect-*.json")):
        with path.open(encoding="utf-8") as profile_file:
            profiles.append(json.load(profile_file))
    return profiles


def document_checksum(document: dict[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def profile_from_openapi_document(document: dict[str, Any], version: str) -> dict[str, Any]:
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise ValueError("The document does not contain an OpenAPI/Swagger paths object")
    if "openapi" not in document and "swagger" not in document:
        raise ValueError("The document is not identified as OpenAPI or Swagger")

    operations: dict[str, dict[str, Any]] = {}
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            operation_id = (
                operation.get("x-dashboard-operation")
                or _semantic_operation_id(method, path)
                or operation.get("operationId")
                or f"{method.lower()}:{path}"
            )
            operations[operation_id] = {
                "method": method.upper(),
                "path": path,
                "polling_hint_seconds": None,
                "source_operation_id": operation.get("operationId"),
                "tags": operation.get("tags", []),
                "notes": ["Generated from an imported OpenAPI document."],
            }

    return {
        "version": version,
        "status": "generated",
        "api_root": _api_root(document),
        "checksum": document_checksum(document),
        "operations": operations,
    }


def _api_root(document: dict[str, Any]) -> str:
    base_path = document.get("basePath")
    if isinstance(base_path, str):
        return base_path.rstrip("/")
    servers = document.get("servers", [])
    if servers and isinstance(servers[0], dict):
        server_url = servers[0].get("url", "")
        if isinstance(server_url, str):
            return urlsplit(server_url).path.rstrip("/")
    return ""


def _semantic_operation_id(method: str, path: str) -> str | None:
    normalized = "/" + path.lower().strip("/")
    verb = method.lower()
    rules = (
        (verb == "get" and normalized.endswith("/version"), "orchestrator.version"),
        (verb == "get" and normalized in {"/appliance", "/appliances"}, "orchestrator.inventory.summary"),
        (verb == "get" and normalized.endswith("/topology"), "orchestrator.topology"),
        (verb == "post" and "/stats/aggregate/interface" in normalized, "orchestrator.stats.aggregate.interface"),
        (verb == "get" and normalized.startswith("/interfacestate/"), "appliance.interfaces"),
        (verb == "get" and "/stats/aggregate/tunnel" in normalized, "appliance.tunnels"),
        (verb == "get" and "/stats/timeseries/appliance" in normalized, "appliance.performance"),
        (verb == "post" and normalized == "/health", "appliance.health"),
    )
    return next((operation_id for matches, operation_id in rules if matches), None)
