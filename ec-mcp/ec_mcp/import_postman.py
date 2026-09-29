"""Import Postman collections (official HPE Aruba EdgeConnect SD-WAN workspace) into EdgeConnect profiles.

Usage:
    python -m ec_mcp.import_postman collection.json --version 9.6 --output ec_mcp/profiles/
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit


def is_postman_collection(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    schema = str(document.get("info", {}).get("schema", "")).lower()
    return "schema.getpostman.com" in schema and "collection" in schema


def collection_variables(document: dict[str, Any]) -> dict[str, str]:
    return {
        str(item.get("key")): str(item.get("value", ""))
        for item in document.get("variable", [])
        if isinstance(item, dict) and item.get("key")
    }


def _replace_vars(value: str, variables: dict[str, str], placeholders: bool = True) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return "{" + key + "}" if placeholders else str(variables.get(key, match.group(0)))

    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", replace, value)


def _url_parts(raw: Any, variables: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    if isinstance(raw, str):
        value = _replace_vars(raw, variables, False)
        parsed = urlsplit(value if "://" in value else "https://postman.invalid/" + value.lstrip("/"))
        return _replace_vars("/" + parsed.path.lstrip("/"), variables), [
            (key, _replace_vars(value_, variables)) for key, value_ in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    if not isinstance(raw, dict):
        return "", []
    raw_value = str(raw.get("raw", ""))
    if raw_value:
        path, embedded = _url_parts(raw_value, variables)
    else:
        parts = raw.get("path", [])
        path = "/" + "/".join(str(p) for p in parts) if isinstance(parts, list) else str(parts)
        embedded = []
    query = embedded + [
        (str(item.get("key")), _replace_vars(str(item.get("value", "")), variables))
        for item in raw.get("query", [])
        if isinstance(item, dict) and not item.get("disabled") and item.get("key")
    ]
    return _replace_vars(path, variables), query


def _body_example(body: dict[str, Any], variables: dict[str, str]) -> Any:
    mode = body.get("mode")
    if mode == "raw":
        raw = _replace_vars(str(body.get("raw", "")), variables, False)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw or None
    if mode in {"urlencoded", "formdata"}:
        return {
            str(item.get("key")): _replace_vars(str(item.get("value", "")), variables, False)
            for item in body.get(mode, [])
            if isinstance(item, dict) and item.get("key") and not item.get("disabled")
        }
    return None


def _operation_id_from(name: str, method: str, path: str, counts: Counter[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_") or f"{method}_{path}"
    base = re.sub(r"_+", "_", base).lower()
    counts[base] += 1
    return base if counts[base] == 1 else f"{base}_{counts[base]}"


def postman_to_profile(document: dict[str, Any], version: str) -> dict[str, Any]:
    """Convert a Postman Collection v2.0/v2.1 into an EdgeConnect profile document."""
    if not is_postman_collection(document):
        raise ValueError("Not a valid Postman Collection v2.0/v2.1 document")
    variables = collection_variables(document)
    operations: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()

    def walk(items: list[Any], folders: list[str]) -> None:
        for entry in items:
            if not isinstance(entry, dict):
                continue
            children = entry.get("item")
            if isinstance(children, list):
                walk(children, [*folders, str(entry.get("name", "General"))])
                continue
            request = entry.get("request")
            if not request:
                continue
            request = {"url": request} if isinstance(request, str) else request
            if not isinstance(request, dict):
                continue
            method = str(request.get("method", "GET")).upper()
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            path, query = _url_parts(request.get("url"), variables)
            if not path or path == "/":
                continue
            name = str(entry.get("name") or f"{method} {path}")
            operation_id = _operation_id_from(name, method, path, counts)
            operation: dict[str, Any] = {
                "method": method,
                "path": path,
                "risk": "read" if method == "GET" else "write",
                "source": "postman",
                "notes": [f"Imported from Postman collection folder '{folders[-1] if folders else 'root'}'."],
            }
            query_names = [key for key, _ in query]
            if query_names:
                operation["query_params"] = sorted(set(query_names))
            path_params = sorted(set(re.findall(r"\{([^{}]+)\}", path)))
            if path_params:
                operation["path_params"] = path_params
            body = request.get("body")
            if isinstance(body, dict):
                example = _body_example(body, variables)
                if example is not None:
                    operation["body_example"] = example
            operations[operation_id] = operation

    walk(document.get("item", []), [])
    if not operations:
        raise ValueError("The Postman collection contains no compatible HTTP requests")
    return {
        "version": version,
        "status": "imported",
        "api_root": "/gms/rest",
        "source": "postman",
        "operations": operations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a Postman collection into an EdgeConnect profile")
    parser.add_argument("collection", type=Path, help="Path to the Postman collection JSON (v2.0/v2.1)")
    parser.add_argument("--version", required=True, help="API version label for the profile (e.g. 9.6)")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "profiles")
    parser.add_argument("--merge-into", default="", help="Existing profile version to merge operations into")
    args = parser.parse_args()

    with args.collection.open(encoding="utf-8") as file_handle:
        document = json.load(file_handle)
    profile = postman_to_profile(document, args.version)

    if args.merge_into:
        target = args.output / f"edgeconnect-{args.merge_into}.json"
        with target.open(encoding="utf-8") as file_handle:
            existing = json.load(file_handle)
        existing.setdefault("operations", {}).update(profile["operations"])
        existing["status"] = "merged-postman"
        profile = existing
        args.version = args.merge_into

    output_path = args.output / f"edgeconnect-{args.version}.json"
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(profile, file_handle, indent=2, ensure_ascii=False)
        file_handle.write("\n")
    print(f"Wrote {len(profile['operations'])} operations to {output_path}")


if __name__ == "__main__":
    main()
