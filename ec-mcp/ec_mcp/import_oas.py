"""Import official Aruba EdgeConnect OpenAPI definitions into EdgeConnect profiles.

The official OAS files are published on the Aruba developer hub (ReadMe):
- Orchestrator REST APIs (orchestrator-rest-apis.json)
- Silver Peak Unity ECOS REST APIs (silver-peak-unity-ecos-rest-apis.json)

Usage:
    python -m ec_mcp.import_oas /tmp/orchestrator.json --version 9.6 \
        --prefix orchestrator --output ec_mcp/profiles
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return re.sub(r"_+", "_", slug)


def sanitize_path(path: str) -> str:
    return path if path.startswith("/") else "/" + path


def path_params_of(path: str) -> list[str]:
    return sorted(set(re.findall(r"\{([^{}]+)\}", path)))


def schema_to_example(schema: dict[str, Any] | None, components: dict[str, Any], depth: int = 0) -> Any:
    if schema is None or depth > 4:
        return None
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return schema_to_example(components.get("schemas", {}).get(ref), components, depth + 1)
    if "example" in schema:
        return schema["example"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if schema.get("type") == "object" or "properties" in schema:
        result = {}
        for name, prop in list(schema.get("properties", {}).items())[:20]:
            example = schema_to_example(prop, components, depth + 1)
            if example is not None:
                result[name] = example
        return result or None
    if schema.get("type") == "array":
        example = schema_to_example(schema.get("items"), components, depth + 1)
        return [example] if example is not None else None
    for key in ("default",):
        if key in schema:
            return schema[key]
    if "type" in schema:
        return {"string": "", "integer": 0, "number": 0, "boolean": False}.get(schema["type"])
    return None


def body_example_of(operation: dict[str, Any], components: dict[str, Any]) -> Any:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return None
    if "$ref" in request_body:
        ref = request_body["$ref"].split("/")[-1]
        request_body = components.get("requestBodies", {}).get(ref, {})
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    return schema_to_example(json_content.get("schema"), components)


def operation_id_for(method: str, path: str, operation: dict[str, Any], used: dict[str, int]) -> str:
    base = operation.get("operationId") or f"{method} {path}"
    slug = slugify(str(base))
    if not slug:
        slug = f"{method}_{slugify(path)}"
    used[slug] = used.get(slug, 0) + 1
    return slug if used[slug] == 1 else f"{slug}_{used[slug]}"


def oas_to_profile(document: dict[str, Any], version: str, prefix: str = "") -> dict[str, Any]:
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        raise ValueError("The document does not contain an OpenAPI/Swagger paths object")
    components = document.get("components", {})
    operations: dict[str, dict[str, Any]] = {}
    used: dict[str, int] = {}
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        path = sanitize_path(str(path))
        params_in_path = path_params_of(path)
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(operation, dict):
                continue
            operation_id = operation_id_for(method, path, operation, used)
            if prefix:
                operation_id = f"{prefix}.{operation_id}"
            entry: dict[str, Any] = {
                "method": method.upper(),
                "path": path,
                "risk": "read" if method.lower() == "get" else "write",
                "source": "official-oas",
                "notes": [str(operation.get("summary") or operation.get("description") or "")[:200]],
            }
            if params_in_path:
                entry["path_params"] = params_in_path
            query_params = sorted(
                {
                    str(param.get("name"))
                    for param in operation.get("parameters", [])
                    if isinstance(param, dict) and param.get("in") == "query" and param.get("name")
                }
            )
            if query_params:
                entry["query_params"] = query_params
            body_example = body_example_of(operation, components)
            if body_example is not None:
                entry["body_example"] = body_example
            tags = operation.get("tags") or []
            if tags:
                entry["tags"] = [str(tag) for tag in tags]
            operations[operation_id] = entry
    if not operations:
        raise ValueError("The document contains no compatible operations")
    servers = document.get("servers") or []
    api_root = ""
    if servers and isinstance(servers[0], dict):
        api_root = str(servers[0].get("url", ""))
    return {
        "version": version,
        "status": "official-oas",
        "api_root": api_root.rstrip("/"),
        "source": "official-oas",
        "source_title": document.get("info", {}).get("title"),
        "operations": operations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an official Aruba OpenAPI document into an EdgeConnect profile")
    parser.add_argument("document", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--prefix", default="", help="Operation ID prefix (e.g. 'orchestrator' or 'appliance')")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "profiles")
    parser.add_argument("--merge-into", default="")
    args = parser.parse_args()

    with args.document.open(encoding="utf-8") as handle:
        document = json.load(handle)
    profile = oas_to_profile(document, args.version, args.prefix)

    if args.merge_into:
        target = args.output / f"edgeconnect-{args.merge_into}.json"
        with target.open(encoding="utf-8") as handle:
            existing = json.load(handle)
        merged = dict(existing.get("operations", {}))
        merged.update(profile["operations"])
        # keep curated ops that the OAS may not contain (e.g. semantically-named ones)
        for key, value in existing.get("operations", {}).items():
            merged.setdefault(key, value)
        existing["operations"] = merged
        existing["status"] = "merged-official-oas"
        profile = existing
        args.version = args.merge_into

    output_path = args.output / f"edgeconnect-{args.version}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(profile, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"Wrote {len(profile['operations'])} operations to {output_path}")


if __name__ == "__main__":
    main()
