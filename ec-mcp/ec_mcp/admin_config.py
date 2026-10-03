"""Validated web configuration for ec-mcp.

Only variables declared in SETTINGS can be changed. Secret values are never
returned by the API; an empty secret keeps the current value and explicit
entries in clear_secrets remove it.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Setting:
    key: str
    group: str
    label: str
    kind: str = "text"
    default: str = ""
    secret: bool = False
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    help: str = ""


SETTINGS = (
    Setting("EC_ORCHESTRATOR_URL", "Orchestrator", "URL del Orchestrator", "url", help="URL HTTPS o HTTP del Orchestrator."),
    Setting("EC_ORCHESTRATOR_API_KEY", "Orchestrator", "API key (X-Auth-Token)", "password", secret=True),
    Setting("EC_ORCHESTRATOR_USER", "Orchestrator", "Usuario alternativo"),
    Setting("EC_ORCHESTRATOR_PASSWORD", "Orchestrator", "Password alternativo", "password", secret=True),
    Setting("EC_VERIFY_TLS", "Orchestrator", "Verificar TLS", "boolean", "true"),
    Setting("EC_SSH_ENABLED", "SSH opcional", "Habilitar SSH", "boolean", "false", help="run_show_api no usa SSH."),
    Setting("EC_SSH_HOST", "SSH opcional", "Host SSH predeterminado"),
    Setting("EC_SSH_USER", "SSH opcional", "Usuario SSH"),
    Setting("EC_SSH_PASSWORD", "SSH opcional", "Password SSH", "password", secret=True),
    Setting("EC_SSH_ENABLE_PASSWORD", "SSH opcional", "Password enable", "password", secret=True),
    Setting("EC_SSH_PORT", "SSH opcional", "Puerto SSH", "integer", "22", minimum=1, maximum=65535),
    Setting("EC_SSH_AUTH_METHOD", "SSH opcional", "Método de autenticación", "choice", "auto", choices=("auto", "password", "keyboard-interactive")),
    Setting("EC_ALLOW_WRITE_TOOLS", "Seguridad", "Permitir tools de escritura", "boolean", "false"),
    Setting("EC_ALLOW_DANGEROUS_WRITES", "Seguridad", "Permitir escrituras peligrosas", "boolean", "false"),
    Setting("EC_MAX_WRITES_PER_MINUTE", "Seguridad", "Máximo de escrituras por minuto", "integer", "10", minimum=1, maximum=1000),
    Setting("EC_MAX_OUTPUT_CHARS", "Seguridad", "Máximo de caracteres de salida", "integer", "12000", minimum=1000, maximum=1000000),
    Setting("EC_API_CACHE_TTL", "Seguridad", "TTL de caché API (segundos)", "number", "30", minimum=0, maximum=86400),
    Setting("EC_MCP_AUDIT_LOG", "Seguridad", "Archivo de auditoría", default="logs/mcp-audit.jsonl"),
    Setting("EC_MCP_PROFILES_DIR", "Seguridad", "Directorio de perfiles"),
    Setting("EC_MCP_AUTH_TOKEN", "Transporte MCP", "Bearer token MCP", "password", secret=True),
    Setting("EC_MCP_HOST", "Transporte MCP", "IP de escucha MCP", default="127.0.0.1"),
    Setting("EC_MCP_PORT", "Transporte MCP", "Puerto MCP", "integer", "8000", minimum=1, maximum=65535),
    Setting("EC_MCP_ALLOWED_HOSTS", "Transporte MCP", "Hosts permitidos"),
    Setting("EC_MCP_JSON_RESPONSE", "Transporte MCP", "Respuesta JSON", "boolean", "true"),
    Setting("EC_MCP_STATELESS", "Transporte MCP", "Modo stateless", "boolean", "false"),
    Setting("EC_MCP_BUILD_COMMIT", "Transporte MCP", "Commit de build"),
    Setting("EC_ADMIN_HOST", "Panel web", "IP de escucha del panel", default="127.0.0.1"),
    Setting("EC_ADMIN_PORT", "Panel web", "Puerto del panel", "integer", "8080", minimum=1, maximum=65535),
    Setting("EC_ADMIN_PASSWORD", "Panel web", "Password del administrador", "password", secret=True),
    Setting("EC_ADMIN_PASSWORD_FILE", "Panel web", "Archivo de password"),
    Setting("EC_ADMIN_STORE", "Panel web", "Archivo de orquestadores"),
    Setting("EC_UPDATE_ALLOW_WEB", "Actualizaciones", "Permitir actualizaciones web", "boolean", "true"),
    Setting("EC_UPDATE_REPOSITORY", "Actualizaciones", "Repositorio GitHub", default="Ryuz-crypto/APIIntegration", help="Formato owner/repository."),
    Setting("EC_UPDATE_BRANCH", "Actualizaciones", "Rama de publicación", default="main"),
    Setting("EC_UPDATE_GITHUB_USER", "Actualizaciones", "Usuario GitHub"),
    Setting("EC_UPDATE_GITHUB_TOKEN", "Actualizaciones", "Token GitHub", "password", secret=True, help="Necesario para repositorios privados; nunca se devuelve al navegador."),
    Setting("EC_UPDATE_PROJECT_DIR", "Actualizaciones", "Directorio instalado"),
    Setting("EC_UPDATE_STATE_DIR", "Actualizaciones", "Directorio de estado", default="/var/lib/ec-mcp-update"),
    Setting("EC_UPDATE_SERVICE_NAME", "Actualizaciones", "Servicio MCP", default="ec-mcp.service"),
    Setting("EC_UPDATE_ADMIN_SERVICE_NAME", "Actualizaciones", "Servicio del panel", default="ec-mcp-admin.service"),
)

BY_KEY = {setting.key: setting for setting in SETTINGS}
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")


def env_path() -> Path:
    return Path(os.environ.get("EC_MCP_ENV_FILE", Path.cwd() / ".env"))


def read_env(path: Path | None = None) -> dict[str, str]:
    target = path or env_path()
    values: dict[str, str] = {}
    if not target.is_file():
        return values
    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _effective_values(path: Path | None = None) -> dict[str, str]:
    values = read_env(path)
    for setting in SETTINGS:
        if setting.key in os.environ:
            values[setting.key] = os.environ[setting.key]
    return values


def public_config(path: Path | None = None) -> dict:
    values = _effective_values(path)
    fields = []
    for setting in SETTINGS:
        item = asdict(setting)
        item["choices"] = list(setting.choices)
        value = values.get(setting.key, setting.default)
        item["configured"] = bool(value) if setting.secret else True
        item["value"] = "" if setting.secret else value
        fields.append(item)
    return {"fields": fields, "env_file": str(path or env_path()), "restart_required": True}


def _validate(setting: Setting, raw: object) -> str:
    value = str(raw if raw is not None else "").strip()
    if "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError(f"{setting.key}: el valor contiene caracteres no permitidos")
    if setting.kind == "boolean":
        lowered = value.lower()
        if lowered not in {"true", "false"}:
            raise ValueError(f"{setting.key}: usa true o false")
        value = lowered
    elif setting.kind in {"integer", "number"} and value:
        try:
            number = int(value) if setting.kind == "integer" else float(value)
        except ValueError:
            raise ValueError(f"{setting.key}: debe ser numérico") from None
        if setting.minimum is not None and number < setting.minimum:
            raise ValueError(f"{setting.key}: mínimo {setting.minimum:g}")
        if setting.maximum is not None and number > setting.maximum:
            raise ValueError(f"{setting.key}: máximo {setting.maximum:g}")
        value = str(number)
    elif setting.kind == "choice" and value not in setting.choices:
        raise ValueError(f"{setting.key}: valor no permitido")
    elif setting.kind == "url" and value:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"{setting.key}: URL inválida")
        value = value.rstrip("/")
    if setting.key == "EC_UPDATE_REPOSITORY" and not _REPOSITORY.fullmatch(value):
        raise ValueError("EC_UPDATE_REPOSITORY: usa owner/repository")
    if setting.key == "EC_UPDATE_BRANCH" and (not _BRANCH.fullmatch(value) or ".." in value):
        raise ValueError("EC_UPDATE_BRANCH: rama inválida")
    return value


def update_env(values: dict[str, object], clear_secrets: list[str] | None = None, path: Path | None = None) -> Path:
    target = path or env_path()
    clear = set(clear_secrets or [])
    unknown = (set(values) | clear) - set(BY_KEY)
    if unknown:
        raise ValueError("Variables no permitidas: " + ", ".join(sorted(unknown)))
    wanted: dict[str, str] = {}
    for key, raw in values.items():
        setting = BY_KEY[key]
        if setting.secret and (raw is None or str(raw) == ""):
            continue
        wanted[key] = _validate(setting, raw)
    for key in clear:
        if not BY_KEY[key].secret:
            raise ValueError(f"{key}: sólo se pueden limpiar secretos")
        wanted[key] = ""

    lines = target.read_text(encoding="utf-8").splitlines() if target.is_file() else []
    positions: dict[str, int] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            positions[stripped.split("=", 1)[0].strip()] = index
    for key, value in wanted.items():
        rendered = f"{key}={value}"
        if key in positions:
            lines[positions[key]] = rendered
        else:
            lines.append(rendered)

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines).rstrip() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, target)
    finally:
        Path(temporary_name).unlink(missing_ok=True)
    for key, value in wanted.items():
        os.environ[key] = value
    return target
