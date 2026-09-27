import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from sqlmodel import Session, select

from app.compatibility.loader import document_checksum, load_builtin_profiles
from app.models.api_sample import ApiSample
from app.models.compatibility import ApiCompatibilityProfile
from app.models.orchestrator import Orchestrator
from app.models.tryme_snapshot import TryMeSnapshot
from app.schemas.tryme import TryMeCatalog, TryMeExecuteRequest, TryMeExecuteResult
from app.services.compatibility_service import build_compatibility_engine, store_openapi_profile
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectClientError
from app.services.sample_service import record_error, record_success
from app.services.trace_service import sanitize

METHODS = {"get", "post", "put", "patch", "delete"}
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
BLOCKED_HEADERS = {
    "authorization",
    "cookie",
    "host",
    "x-auth-token",
    "x-xsrf-token",
    "proxy-authorization",
    "content-length",
    "transfer-encoding",
    "connection",
}
SWAGGER_PATHS = (
    "/webclient/html/apiDocs/gmsApiInfo.json",
    "/gms/rest/apiDocs/gmsApiInfo.json",
    "/apiDocs/gmsApiInfo.json",
    "/swagger.json",
    "/v3/api-docs",
)


def _version(orchestrator: Orchestrator) -> str:
    candidate = orchestrator.swagger_version or orchestrator.api_version or "9.6"
    parts = candidate.split(".")
    version = ".".join(parts[:2]) if len(parts) >= 2 else candidate
    return "9.6" if version == "9.7" else version


def _resolve_ref(document: dict, value: Any) -> Any:
    if not isinstance(value, dict) or not isinstance(value.get("$ref"), str):
        return value
    reference = value["$ref"]
    if not reference.startswith("#/"):
        return value
    current: Any = document
    try:
        for part in reference[2:].split("/"):
            current = current[part.replace("~1", "/").replace("~0", "~")]
    except (KeyError, TypeError):
        return value
    return current


def _schema_example(schema: dict) -> Any:
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        return {
            name: _schema_example(value)
            for name, value in schema.get("properties", {}).items()
            if isinstance(value, dict)
        }
    if kind == "array":
        return [_schema_example(schema.get("items", {}))]
    if schema.get("enum"):
        return schema["enum"][0]
    return {"string": "", "integer": 0, "number": 0, "boolean": False}.get(kind)


def _parameter(document: dict, raw: dict) -> dict:
    item = _resolve_ref(document, raw)
    schema = _resolve_ref(document, item.get("schema", {}))
    return {
        "name": str(item.get("name", "parameter")),
        "location": str(item.get("in", "query")),
        "required": bool(item.get("required", False)),
        "description": str(item.get("description", "")),
        "schema": schema if isinstance(schema, dict) else {},
        "example": item.get("example", _schema_example(schema) if isinstance(schema, dict) else None),
    }


def _document_catalog(orchestrator: Orchestrator, version: str, item: ApiCompatibilityProfile):
    document = item.raw_document
    api_root = str(item.profile.get("api_root", "")).rstrip("/")
    operations = []
    for raw_path, raw_path_item in document.get("paths", {}).items():
        path_item = _resolve_ref(document, raw_path_item)
        if not isinstance(path_item, dict):
            continue
        shared = path_item.get("parameters", [])
        for method, raw_operation in path_item.items():
            if method.lower() not in METHODS or not isinstance(raw_operation, dict):
                continue
            operation = _resolve_ref(document, raw_operation)
            parameters = [
                _parameter(document, parameter)
                for parameter in [*shared, *operation.get("parameters", [])]
                if isinstance(parameter, dict)
            ]
            request_schema: dict = {}
            request_example: Any = None
            body_parameter = next(
                (parameter for parameter in parameters if parameter["location"] == "body"), None
            )
            if body_parameter:
                request_schema = body_parameter["schema"]
                request_example = body_parameter["example"]
                parameters.remove(body_parameter)
            request_body = _resolve_ref(document, operation.get("requestBody", {}))
            if isinstance(request_body, dict):
                content = request_body.get("content", {})
                media = content.get("application/json") or next(iter(content.values()), {})
                if isinstance(media, dict):
                    request_schema = _resolve_ref(document, media.get("schema", {}))
                    request_example = media.get("example", _schema_example(request_schema))
            raw_path = str(raw_path)
            full_path = (
                raw_path
                if api_root and (raw_path == api_root or raw_path.startswith(f"{api_root}/"))
                else f"{api_root}/{raw_path.lstrip('/')}"
            )
            operations.append(
                {
                    "operation_id": operation.get("operationId") or f"{method.lower()}:{raw_path}",
                    "method": method.upper(),
                    "path": full_path,
                    "summary": operation.get("summary") or operation.get("operationId") or raw_path,
                    "description": operation.get("description", ""),
                    "tags": operation.get("tags", []),
                    "parameters": parameters,
                    "request_schema": request_schema,
                    "request_example": request_example,
                    "mutating": method.upper() in MUTATING,
                }
            )
    info = document.get("info", {})
    return TryMeCatalog(
        orchestrator_id=orchestrator.id,
        version=version,
        source=f"Swagger importado · {document_checksum(document)[:12]}",
        title=str(info.get("title", "EdgeConnect API")),
        operations=sorted(operations, key=lambda value: (value["tags"], value["path"], value["method"])),
    )


def catalog(session: Session, orchestrator: Orchestrator) -> TryMeCatalog:
    version = _version(orchestrator)
    stored = session.get(ApiCompatibilityProfile, version)
    if stored and stored.raw_document.get("paths"):
        return _document_catalog(orchestrator, version, stored)
    profile = next(
        (profile for profile in load_builtin_profiles() if profile["version"] == version), None
    )
    if profile is None:
        raise ValueError(f"No hay un Swagger o perfil compatible para la versión {version}.")
    api_root = profile.get("api_root", "").rstrip("/")
    operations = [
        {
            "operation_id": operation_id,
            "method": operation["method"],
            "path": f"{api_root}/{operation['path'].lstrip('/')}",
            "summary": operation_id,
            "description": " ".join(operation.get("notes", [])),
            "tags": [operation_id.split(".")[0]],
            "parameters": [
                {
                    "name": name,
                    "location": "path" if f"{{{name}}}" in operation["path"] else "query",
                    "required": True,
                    "schema": {"type": "string"},
                }
                for name in dict.fromkeys(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", operation["path"]))
            ],
            "request_schema": {},
            "request_example": None,
            "mutating": operation["method"] in MUTATING,
        }
        for operation_id, operation in profile.get("operations", {}).items()
    ]
    return TryMeCatalog(
        orchestrator_id=orchestrator.id,
        version=version,
        source="Perfil integrado; importa el Swagger completo para mostrar todas las APIs",
        title="EdgeConnect API",
        operations=operations,
    )


def sync_catalog(session: Session, orchestrator: Orchestrator) -> TryMeCatalog:
    api = EdgeConnectClient(orchestrator, build_compatibility_engine(session))
    errors = []
    for path in SWAGGER_PATHS:
        try:
            response = api.call_custom("try-me.swagger", "GET", path)
        except EdgeConnectClientError as exc:
            errors.append(f"{path}: {exc.status_code or 'connection'}")
            continue
        document = response.payload
        if not isinstance(document.get("paths"), dict) or not (
            document.get("openapi") or document.get("swagger")
        ):
            errors.append(f"{path}: formato no reconocido")
            continue
        store_openapi_profile(
            session, document, _version(orchestrator), activate=False, catalog_only=True
        )
        return catalog(session, orchestrator)
    raise ValueError(
        "El Orchestrator no publicó un Swagger compatible en las rutas conocidas. "
        "Descárgalo desde Support → REST APIs e impórtalo manualmente. "
        + "; ".join(errors)
    )


def _operation(selected: TryMeCatalog, method: str, path: str):
    return next(
        (operation for operation in selected.operations if operation.method == method and operation.path == path),
        None,
    )


def execute(
    session: Session,
    orchestrator: Orchestrator,
    payload: TryMeExecuteRequest,
) -> TryMeExecuteResult:
    selected = catalog(session, orchestrator)
    operation = _operation(selected, payload.method, payload.path)
    if operation is None:
        raise ValueError("La operación no pertenece al Swagger seleccionado.")
    if operation.mutating and payload.confirmation != f"EJECUTAR {payload.method} {payload.path}":
        raise ValueError("Escribe la confirmación exacta para ejecutar esta operación.")
    path = payload.path
    for key, value in payload.path_params.items():
        path = path.replace("{" + key + "}", quote(str(value), safe=""))
    if re.search(r"\{[^{}]+\}", path):
        raise ValueError("Completa todos los parámetros del path.")
    headers = {
        key: value
        for key, value in payload.headers.items()
        if key.lower() not in BLOCKED_HEADERS
    }
    if len(headers) != len(payload.headers):
        raise ValueError("No se permite reemplazar encabezados de autenticación o transporte.")
    request_data = {
        "path_params": payload.path_params,
        "query_params": payload.query_params,
        "headers": headers,
        "body": payload.body,
    }
    safe_request = sanitize(request_data)
    api = EdgeConnectClient(orchestrator, build_compatibility_engine(session))
    executed_at = datetime.now(UTC)
    try:
        response = api.call_custom(
            operation.operation_id,
            payload.method,
            path,
            payload.query_params,
            payload.body,
            headers,
        )
        sample = record_success(
            session,
            orchestrator.id,
            selected.version,
            response,
            request_params=safe_request,
            transformations=["try-me", "swagger-validated"],
        )
        safe_response = sanitize(response.payload)
        sample.payload = safe_response
        session.commit()
        session.refresh(sample)
        return TryMeExecuteResult(
            sample_id=sample.id,
            ok=True,
            operation_id=operation.operation_id,
            method=response.method,
            path=response.path,
            status_code=response.status_code,
            duration_ms=response.duration_ms,
            request=safe_request,
            response=safe_response,
            response_headers=response.response_headers,
            executed_at=executed_at,
        )
    except EdgeConnectClientError as exc:
        safe_error = replace_error_payload(exc, sanitize(exc.payload))
        sample = record_error(
            session,
            orchestrator.id,
            selected.version,
            operation.operation_id,
            safe_error,
            request_params=safe_request,
        )
        sample.transformations = ["try-me", "swagger-validated"]
        session.commit()
        session.refresh(sample)
        return TryMeExecuteResult(
            sample_id=sample.id,
            ok=False,
            operation_id=operation.operation_id,
            method=exc.method,
            path=exc.path,
            status_code=exc.status_code,
            duration_ms=exc.duration_ms,
            request=safe_request,
            response=safe_error.payload,
            error=str(safe_error),
            executed_at=executed_at,
        )


def replace_error_payload(error: EdgeConnectClientError, payload: dict) -> EdgeConnectClientError:
    return EdgeConnectClientError(
        str(error),
        status_code=error.status_code,
        duration_ms=error.duration_ms,
        payload=payload,
        method=error.method,
        path=error.path,
    )


def create_snapshot(session: Session, sample: ApiSample, name: str) -> TryMeSnapshot:
    if "try-me" not in sample.transformations:
        raise ValueError("Sólo las ejecuciones de Try Me pueden convertirse en snapshot.")
    item = TryMeSnapshot(
        orchestrator_id=sample.orchestrator_id,
        sample_id=sample.id,
        name=name,
        operation_id=sample.operation_id,
        method=sample.method,
        path=sample.path,
        status_code=sample.status_code,
        request_data=sample.request_params,
        response_data={"ok": sample.ok, "payload": sample.payload, "error": sample.error},
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_snapshots(session: Session, orchestrator_id: uuid.UUID) -> list[TryMeSnapshot]:
    statement = (
        select(TryMeSnapshot)
        .where(TryMeSnapshot.orchestrator_id == orchestrator_id)
        .order_by(TryMeSnapshot.created_at.desc())
    )
    return list(session.exec(statement).all())
