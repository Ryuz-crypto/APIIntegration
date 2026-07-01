import json
from pathlib import Path
from typing import Any

PROFILES_DIR = Path(__file__).parent / "profiles"


def load_builtin_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for path in sorted(PROFILES_DIR.glob("edgeconnect-*.json")):
        with path.open(encoding="utf-8") as profile_file:
            profiles.append(json.load(profile_file))
    return profiles


def profile_from_openapi_document(document: dict[str, Any], version: str) -> dict[str, Any]:
    operations: dict[str, dict[str, Any]] = {}
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_id = operation.get("operationId") or f"{method.lower()}:{path}"
            operations[operation_id] = {
                "method": method.upper(),
                "path": path,
                "polling_hint_seconds": None,
                "notes": ["Generated from uploaded OpenAPI document."],
            }

    return {
        "version": version,
        "status": "generated",
        "api_root": "",
        "operations": operations,
    }
