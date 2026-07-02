#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
API_ROOT = "/gms/rest"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate EdgeConnect compatibility profiles.")
    parser.add_argument("--postman", action="append", default=[], help="version=path to Postman collection")
    parser.add_argument("--openapi-dir", action="append", default=[], help="version=directory with OpenAPI JSON files")
    parser.add_argument("--out", required=True, help="profiles output directory")
    args = parser.parse_args()

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for item in args.postman:
        version, source = split_source(item)
        profile = profile_from_postman(version, Path(source))
        generated.append(write_profile(output_dir, profile))

    for item in args.openapi_dir:
        version, source = split_source(item)
        profile = profile_from_openapi_directory(version, Path(source))
        generated.append(write_profile(output_dir, profile))

    for path in generated:
        print(path)


def split_source(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise SystemExit(f"Source must use version=path format: {value}")
    version, source = value.split("=", 1)
    return version.strip(), source.strip()


def profile_from_postman(version: str, path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    operations: dict[str, dict[str, Any]] = {}

    for request in iter_postman_requests(document.get("item", [])):
        method = request["method"].upper()
        raw_path = request["path"]
        if not raw_path:
            continue
        operation_id = unique_operation_id(
            operations,
            ".".join(
                part
                for part in (
                    request["scope"],
                    slug(request["folder"]),
                    slug(request["name"]),
                )
                if part
            ),
            method,
            raw_path,
        )
        operations[operation_id] = {
            "method": method,
            "path": raw_path,
            "polling_hint_seconds": polling_hint(raw_path, request["name"]),
            "notes": [
                f"Generated from Postman collection {path.name}.",
                f"Collection path: {request['trail']}",
            ],
        }

    add_canonical_aliases(operations, "Postman collection")
    return {
        "version": version,
        "status": "imported",
        "api_root": API_ROOT,
        "source_contracts": [path.name],
        "operations": dict(sorted(operations.items())),
    }


def iter_postman_requests(items: list[dict[str, Any]], trail: tuple[str, ...] = ()):
    for item in items:
        name = item.get("name", "unnamed")
        next_trail = trail + (name,)
        if isinstance(item.get("item"), list):
            yield from iter_postman_requests(item["item"], next_trail)
            continue
        request = item.get("request")
        if not isinstance(request, dict):
            continue
        method = str(request.get("method", "GET")).upper()
        path = normalize_postman_url(request.get("url"))
        scope = "orchestrator"
        if next_trail and "appliance" in next_trail[0].lower():
            scope = "appliance"
        folder = next_trail[-2] if len(next_trail) > 1 else "root"
        yield {
            "method": method,
            "path": path,
            "scope": scope,
            "folder": folder,
            "name": name,
            "trail": " / ".join(next_trail),
        }


def normalize_postman_url(url: Any) -> str:
    if isinstance(url, dict):
        raw = url.get("raw")
        if not raw:
            raw_path = "/".join(str(part).strip("/") for part in url.get("path", []))
            raw = "/" + raw_path
            query = url.get("query") or []
            if query:
                raw += "?" + "&".join(f"{q.get('key')}={q.get('value', '')}" for q in query if q.get("key"))
    else:
        raw = str(url or "")

    raw = raw.replace("{{orchestratorBaseUrl}}", "")
    raw = raw.replace("{{applianceBaseUrl}}", "")
    raw = re.sub(r"^https?://[^/]+", "", raw)
    raw = raw.replace(API_ROOT, "")
    raw = re.sub(r"^/rest/json/?", "/", raw)
    raw = re.sub(r"^/rest/?", "/", raw)
    raw = raw.replace(" ", "%20")
    raw = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", raw)
    path, _, query = raw.partition("?")
    path = "/" + path.strip("/")
    path = re.sub(r"/+", "/", path)
    if not query:
        return path

    query_parts: list[str] = []
    for pair in query.split("&"):
        if not pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip()
        if not key:
            continue
        query_parts.append(f"{key}={normalize_query_value(key, value)}")
    return f"{path}?{'&'.join(query_parts)}" if query_parts else path


def normalize_query_value(key: str, value: str) -> str:
    if value.startswith("{") and value.endswith("}"):
        return value
    if value in {"true", "false", "0", "1"}:
        return value
    if re.fullmatch(r"-?\d+(\.\d+)?", value or ""):
        return value
    return "{" + alias_param(key) + "}"


def alias_param(value: str) -> str:
    aliases = {"nePk": "appliance_id", "applianceId": "appliance_id", "id": "appliance_id"}
    return aliases.get(value, value)


def profile_from_openapi_directory(version: str, directory: Path) -> dict[str, Any]:
    operations: dict[str, dict[str, Any]] = {}
    source_contracts: list[str] = []

    for path in sorted(directory.glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if "paths" not in document:
            continue
        source_contracts.append(path.name)
        tag = slug((document.get("tags") or [{}])[0].get("name", path.stem))
        for api_path, path_item in sorted(document.get("paths", {}).items()):
            if not isinstance(path_item, dict):
                continue
            for method, operation in sorted(path_item.items()):
                if method.lower() not in HTTP_METHODS:
                    continue
                op_id = operation.get("operationId") or f"{method}:{api_path}"
                operation_id = unique_operation_id(
                    operations,
                    ".".join(part for part in ("orchestrator", tag, slug(op_id)) if part),
                    method.upper(),
                    api_path,
                )
                operations[operation_id] = {
                    "method": method.upper(),
                    "path": normalize_openapi_path(api_path),
                    "polling_hint_seconds": polling_hint(api_path, operation.get("summary", "")),
                    "notes": [
                        f"Generated from OpenAPI module {path.name}.",
                        f"Summary: {operation.get('summary', 'No summary')}",
                    ],
                }

    add_canonical_aliases(operations, "OpenAPI modules")
    return {
        "version": version,
        "status": "imported",
        "api_root": API_ROOT,
        "source_contracts": source_contracts,
        "operations": dict(sorted(operations.items())),
    }


def normalize_openapi_path(path: str) -> str:
    path = path.replace(API_ROOT, "")
    path = re.sub(r"/+", "/", "/" + path.strip("/"))
    return path


def add_canonical_aliases(operations: dict[str, dict[str, Any]], source: str) -> None:
    aliases = {
        "orchestrator.version": first_matching(
            operations,
            method="GET",
            paths=("/gmsserver/ping", "/gmsserver/briefInfo", "/gmsserver/info", "/gms/versions"),
        ),
        "orchestrator.inventory.summary": first_matching(
            operations,
            method="GET",
            paths=("/appliance/approved", "/appliance"),
        ),
        "orchestrator.topology": first_matching(
            operations,
            method="GET",
            contains=("/topology", "/grNode"),
        ),
        "appliance.interfaces": first_matching(
            operations,
            method="GET",
            contains=("/appliance/interfaceMeta", "/interfaceState", "/interface"),
        ),
        "appliance.tunnels": first_matching(
            operations,
            method="GET",
            contains=("/tunnels2/physical", "/tunnel"),
        ),
        "appliance.performance": first_matching(
            operations,
            method="GET",
            paths=("/appliance",),
        ),
    }
    for alias, operation in aliases.items():
        if not operation:
            continue
        aliased = dict(operation)
        aliased["notes"] = [f"Canonical dashboard alias generated from {source}.", *operation.get("notes", [])]
        if alias in {"appliance.performance", "appliance.interfaces"}:
            aliased["path"] = ensure_appliance_id_query(aliased["path"])
            aliased["polling_hint_seconds"] = 5
        operations[alias] = aliased


def first_matching(
    operations: dict[str, dict[str, Any]],
    method: str,
    paths: tuple[str, ...] = (),
    contains: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    method = method.upper()
    for target in paths:
        for operation in operations.values():
            path = operation["path"].split("?", 1)[0]
            if operation["method"] == method and path == target:
                return operation
    for target in contains:
        for operation in operations.values():
            if operation["method"] == method and target.lower() in operation["path"].lower():
                return operation
    return None


def ensure_appliance_id_query(path: str) -> str:
    if "{appliance_id}" in path:
        return path
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}nePk={{appliance_id}}"


def unique_operation_id(
    operations: dict[str, dict[str, Any]],
    base: str,
    method: str,
    path: str,
) -> str:
    base = base.strip(".") or f"{method.lower()}.{slug(path)}"
    if base not in operations:
        return base
    digest = hashlib.sha1(f"{method}:{path}".encode("utf-8")).hexdigest()[:8]
    candidate = f"{base}.{digest}"
    counter = 2
    while candidate in operations:
        counter += 1
        candidate = f"{base}.{digest}.{counter}"
    return candidate


def slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:90]


def polling_hint(path: str, name: str) -> int | None:
    text = f"{path} {name}".lower()
    if any(token in text for token in ("realtime", "performance", "interface", "tunnel", "health")):
        return 5
    if any(token in text for token in ("appliance", "topology", "stats")):
        return 120
    if any(token in text for token in ("gmsserver", "version", "ping")):
        return 600
    return None


def write_profile(output_dir: Path, profile: dict[str, Any]) -> Path:
    path = output_dir / f"edgeconnect-{profile['version']}.json"
    path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    main()
