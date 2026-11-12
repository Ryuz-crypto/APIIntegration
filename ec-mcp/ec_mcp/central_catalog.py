"""Catalog loader for the Aruba Central v2 (New Central REST API) operations.

The catalog (``catalogs/central-v2.json``) is generated from the official
New Central Postman collections (MRT + Configuration) and contains every
documented operation with its method, path, path parameters, query
parameters and (when compact) a body example.

The curated ``central_*`` tools (v1) stay unchanged; v2 exposes the full
catalog through ``central_v2_list_operations`` (browse) and
``central_v2_call_read_api`` (execute any read operation, catalog
validated). Write operations are listed but refused by the generic caller.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parent / "catalogs" / "central-v2.json"
PATH_PARAM_PATTERN = re.compile(r"\{([a-zA-Z0-9_-]+)\}")


class CatalogError(ValueError):
    """Raised for unknown operations or invalid catalog usage."""


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    with open(CATALOG_PATH, encoding="utf-8") as stream:
        return json.load(stream)


@lru_cache(maxsize=1)
def operations_by_id() -> dict[str, dict[str, Any]]:
    return {str(op["id"]): op for op in load_catalog()["operations"]}


def list_operations(
    group: str = "",
    search: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Browse catalog operations filtered by group and free-text search."""
    group_value = (group or "").strip().lower()
    search_value = (search or "").strip().lower()
    matches = []
    for op in load_catalog()["operations"]:
        if group_value and group_value not in str(op.get("group", "")).lower():
            continue
        if search_value:
            haystack = f"{op.get('id', '')} {op.get('name', '')} {op.get('path', '')} {op.get('group', '')}".lower()
            if search_value not in haystack:
                continue
        matches.append(
            {
                "id": op.get("id"),
                "name": op.get("name"),
                "method": op.get("method"),
                "path": op.get("path"),
                "group": op.get("group"),
                "path_params": op.get("path_params", []),
                "query_keys": [q.get("key") for q in op.get("query", [])],
                "read": op.get("method") == "GET",
            }
        )
        if len(matches) >= max(1, min(limit, 200)):
            break
    return {"count": len(matches), "operations": matches, "total_catalog": len(load_catalog()["operations"])}


def groups() -> list[str]:
    """List the distinct catalog groups (API families)."""
    return sorted({str(op.get("group", "")) for op in load_catalog()["operations"]})


def resolve_operation(operation_id: str) -> dict[str, Any]:
    op = operations_by_id().get((operation_id or "").strip())
    if op is None:
        raise CatalogError(
            f"Unknown Central operation '{operation_id}'. Use central_v2_list_operations to browse the catalog."
        )
    return op


def build_request(
    operation: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build (path, query params) for a catalog operation.

    Path parameters are mandatory; query parameters are optional and only
    known keys are forwarded (unknown keys are rejected to keep calls
    explicit).
    """
    params = params or {}
    if not isinstance(params, dict):
        raise CatalogError("params_json must be a JSON object")
    path = str(operation.get("path", ""))
    missing = [name for name in operation.get("path_params", []) if not str(params.get(name, "")).strip()]
    if missing:
        raise CatalogError(f"Missing required path parameters: {', '.join(missing)}")
    for name in operation.get("path_params", []):
        value = str(params[name]).strip()
        if "/" in value or "{" in value or "}" in value:
            raise CatalogError(f"Invalid value for path parameter '{name}'")
        path = path.replace("{" + name + "}", value)
    allowed = {q.get("key") for q in operation.get("query", [])}
    unknown = sorted(k for k in params if k not in operation.get("path_params", []) and k not in allowed)
    if unknown:
        raise CatalogError(
            f"Unknown query parameters: {', '.join(unknown)}. Supported: {', '.join(sorted(k for k in allowed if k))}"
        )
    query = {key: params[key] for key in sorted(allowed) if key in params and params[key] not in (None, "")}
    return path, query


def validate_read_operation(operation: dict[str, Any]) -> None:
    if operation.get("method") != "GET":
        raise CatalogError(
            f"Operation '{operation.get('id')}' is {operation.get('method')} (a write). "
            "The generic catalog caller is read-only; use the curated central_* tools for operations."
        )


__all__ = [
    "CATALOG_PATH",
    "CatalogError",
    "build_request",
    "groups",
    "list_operations",
    "load_catalog",
    "operations_by_id",
    "resolve_operation",
    "validate_read_operation",
]
