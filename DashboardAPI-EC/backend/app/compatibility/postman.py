import json
import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl, urlsplit


def is_postman_collection(document: Any) -> bool:
    if not isinstance(document, dict):
        return False
    schema = str(document.get("info", {}).get("schema", "")).lower()
    return "schema.getpostman.com" in schema and "collection" in schema


def postman_to_openapi(document: dict[str, Any], version: str) -> dict[str, Any]:
    """Convert Postman Collection v2.0/v2.1 into the subset used by Try Me."""
    if not is_postman_collection(document):
        raise ValueError("El archivo no es una colección Postman 2.0/2.1 válida.")
    variables = {
        str(item.get("key")): item.get("value", "")
        for item in document.get("variable", [])
        if isinstance(item, dict) and item.get("key")
    }
    paths: dict[str, dict[str, Any]] = {}
    ids: Counter[str] = Counter()

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
            method = str(request.get("method", "GET")).lower()
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            path, query = _url_parts(request.get("url"), variables)
            if not path:
                continue
            name = str(entry.get("name") or f"{method.upper()} {path}")
            base_id = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_") or method
            ids[base_id] += 1
            operation_id = base_id if ids[base_id] == 1 else f"{base_id}_{ids[base_id]}"
            parameters = _parameters(path, query, request.get("header", []), variables)
            operation: dict[str, Any] = {
                "operationId": operation_id,
                "summary": name,
                "description": _description(request.get("description")),
                "tags": folders[-1:] or ["Postman"],
                "parameters": parameters,
                "x-postman-name": name,
            }
            body = request.get("body")
            if isinstance(body, dict):
                example = _body_example(body, variables)
                if example is not None:
                    operation["requestBody"] = {
                        "content": {"application/json": {"example": example}}
                    }
            paths.setdefault(path, {})[method] = operation

    walk(document.get("item", []), [])
    if not paths:
        raise ValueError("La colección Postman no contiene requests HTTP compatibles.")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": str(document.get("info", {}).get("name", "Postman Collection")),
            "version": version,
            "description": "Importado desde Postman Collection v2.x.",
        },
        "paths": paths,
        "x-dashboard-source": "postman",
    }


def _replace_variables(value: str, variables: dict[str, Any], placeholders: bool = True) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if placeholders:
            return "{" + key + "}"
        return str(variables.get(key, match.group(0)))

    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", replace, value)


def _url_parts(raw: Any, variables: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    if isinstance(raw, str):
        value = _replace_variables(raw, variables, False)
        parsed = urlsplit(
            value if "://" in value else "https://postman.invalid/" + value.lstrip("/")
        )
        return _replace_variables("/" + parsed.path.lstrip("/"), variables), [
            (key, _replace_variables(value, variables))
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    if not isinstance(raw, dict):
        return "", []
    raw_value = str(raw.get("raw", ""))
    if raw_value:
        path, embedded = _url_parts(raw_value, variables)
    else:
        parts = raw.get("path", [])
        path = (
            "/" + "/".join(str(value) for value in parts) if isinstance(parts, list) else str(parts)
        )
        embedded = []
    query = embedded + [
        (str(item.get("key")), _replace_variables(str(item.get("value", "")), variables))
        for item in raw.get("query", [])
        if isinstance(item, dict) and not item.get("disabled") and item.get("key")
    ]
    return _replace_variables(path, variables), query


def _parameters(
    path: str, query: list[tuple[str, str]], headers: Any, variables: dict[str, Any]
) -> list[dict]:
    result = [
        {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
        for name in dict.fromkeys(re.findall(r"\{([^{}]+)\}", path))
    ]
    result.extend(
        {
            "name": key,
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
            "example": value,
        }
        for key, value in query
    )
    blocked = {"authorization", "cookie", "host", "content-length"}
    if isinstance(headers, list):
        result.extend(
            {
                "name": str(item.get("key")),
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "example": _replace_variables(str(item.get("value", "")), variables, False),
            }
            for item in headers
            if isinstance(item, dict)
            and item.get("key")
            and str(item.get("key")).lower() not in blocked
            and not item.get("disabled")
        )
    return result


def _body_example(body: dict, variables: dict[str, Any]) -> Any:
    mode = body.get("mode")
    if mode == "raw":
        raw = _replace_variables(str(body.get("raw", "")), variables, False)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw or None
    if mode in {"urlencoded", "formdata"}:
        return {
            str(item.get("key")): _replace_variables(str(item.get("value", "")), variables, False)
            for item in body.get(mode, [])
            if isinstance(item, dict) and item.get("key") and not item.get("disabled")
        }
    return None


def _description(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("content", ""))
    return str(value or "")
