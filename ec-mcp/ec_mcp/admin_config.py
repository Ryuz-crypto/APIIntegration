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
    required: bool = False
    depends_on: tuple[str, str] | None = None
    step: str = ""


SETTINGS = (
    Setting("EC_ORCHESTRATOR_URL", "Orchestrator", "URL del Orchestrator", "url", required=True, step="orchestrator", help="URL HTTPS o HTTP del Orchestrator. Obligatoria para usar el Orchestrator."),
    Setting("EC_ORCHESTRATOR_API_KEY", "Orchestrator", "API key (X-Auth-Token)", "password", secret=True, step="orchestrator", help="Obligatoria salvo que configures usuario+password."),
    Setting("EC_ORCHESTRATOR_USER", "Orchestrator", "Usuario alternativo", step="orchestrator"),
    Setting("EC_ORCHESTRATOR_PASSWORD", "Orchestrator", "Password alternativo", "password", secret=True, step="orchestrator"),
    Setting("EC_VERIFY_TLS", "Orchestrator", "Verificar TLS", "boolean", "true", step="orchestrator"),
    Setting("EC_SSH_ENABLED", "SSH opcional", "Habilitar SSH", "boolean", "false", step="ssh", help="run_show_api no usa SSH."),
    Setting("EC_SSH_HOST", "SSH opcional", "Host SSH predeterminado", step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting("EC_SSH_USER", "SSH opcional", "Usuario SSH", step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting("EC_SSH_PASSWORD", "SSH opcional", "Password SSH", "password", secret=True, step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting("EC_SSH_ENABLE_PASSWORD", "SSH opcional", "Password enable", "password", secret=True, step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting("EC_SSH_PORT", "SSH opcional", "Puerto SSH", "integer", "22", minimum=1, maximum=65535, step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting("EC_SSH_AUTH_METHOD", "SSH opcional", "Método de autenticación", "choice", "auto", choices=("auto", "password", "keyboard-interactive"), step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting("EC_AXIS_ENABLED", "Axis Security (SSE)", "Habilitar Axis Security", "boolean", "false", step="sse", help="Plataforma SSE de Axis Security."),
    Setting("EC_AXIS_ADMIN_TOKEN", "Axis Security (SSE)", "Token de administración (Bearer JWT)", "password", secret=True, step="sse", depends_on=("EC_AXIS_ENABLED", "true"), help="Token JWT para admin-api.axissecurity.com. Obligatoria si Axis está habilitado."),
    Setting("EC_AXIS_BASE_URL", "Axis Security (SSE)", "URL base de Axis", "url", "https://admin-api.axissecurity.com", step="sse", depends_on=("EC_AXIS_ENABLED", "true")),
    Setting("EC_AXIS_VERIFY_TLS", "Axis Security (SSE)", "Verificar TLS de Axis", "boolean", "true", step="sse", depends_on=("EC_AXIS_ENABLED", "true")),
    Setting("EC_AXIS_TIMEOUT", "Axis Security (SSE)", "Timeout Axis (segundos)", "number", "30", minimum=1, maximum=300, step="sse", depends_on=("EC_AXIS_ENABLED", "true")),
    Setting("EC_DEFAULT_ORCHESTRATOR", "Multi-target", "Orquestador por defecto", step="targets", help="Target usado cuando un tool no indica 'target'. Debe existir en el registro."),
    Setting("EC_DEFAULT_SSE", "Multi-target", "Plataforma SSE por defecto", step="targets", help="Plataforma SSE usada cuando un tool no indica 'target'."),
    Setting("EC_ALLOW_WRITE_TOOLS", "Seguridad", "Permitir tools de escritura", "boolean", "false", step="security"),
    Setting("EC_ALLOW_DANGEROUS_WRITES", "Seguridad", "Permitir escrituras peligrosas", "boolean", "false", step="security"),
    Setting("EC_MAX_WRITES_PER_MINUTE", "Seguridad", "Máximo de escrituras por minuto", "integer", "10", minimum=1, maximum=1000, step="security"),
    Setting("EC_MAX_OUTPUT_CHARS", "Seguridad", "Máximo de caracteres de salida", "integer", "12000", minimum=1000, maximum=1000000, step="security"),
    Setting("EC_API_CACHE_TTL", "Seguridad", "TTL de caché API (segundos)", "number", "30", minimum=0, maximum=86400, step="security"),
    Setting("EC_MCP_AUDIT_LOG", "Seguridad", "Archivo de auditoría", default="logs/mcp-audit.jsonl", step="security"),
    Setting("EC_MCP_PROFILES_DIR", "Seguridad", "Directorio de perfiles", step="security"),
    Setting("EC_MCP_AUTH_TOKEN", "Transporte MCP", "Bearer token MCP", "password", secret=True, step="transport"),
    Setting("EC_MCP_HOST", "Transporte MCP", "IP de escucha MCP", default="127.0.0.1", step="transport"),
    Setting("EC_MCP_PORT", "Transporte MCP", "Puerto MCP", "integer", "8000", minimum=1, maximum=65535, step="transport"),
    Setting("EC_MCP_ALLOWED_HOSTS", "Transporte MCP", "Hosts permitidos", step="transport"),
    Setting("EC_MCP_JSON_RESPONSE", "Transporte MCP", "Respuesta JSON", "boolean", "true", step="transport"),
    Setting("EC_MCP_STATELESS", "Transporte MCP", "Modo stateless", "boolean", "false", step="transport"),
    Setting("EC_MCP_BUILD_COMMIT", "Transporte MCP", "Commit de build", step="transport"),
    Setting("EC_ADMIN_HOST", "Panel web", "IP de escucha del panel", default="127.0.0.1", step="panel"),
    Setting("EC_ADMIN_PORT", "Panel web", "Puerto del panel", "integer", "8080", minimum=1, maximum=65535, step="panel"),
    Setting("EC_ADMIN_PASSWORD", "Panel web", "Password del administrador", "password", secret=True, step="panel", help="Obligatoria si el panel escucha en una IP no loopback."),
    Setting("EC_ADMIN_USERS_FILE", "Panel web", "Archivo de usuarios del panel", step="panel", help="JSON 0600 con usuarios y roles; si no existe se usa EC_ADMIN_PASSWORD."),
    Setting("EC_ADMIN_LOGIN_MAX_FAILURES", "Panel web", "Intentos fallidos antes del bloqueo", "integer", "5", minimum=1, maximum=100, step="panel"),
    Setting("EC_ADMIN_LOGIN_WINDOW_SECONDS", "Panel web", "Ventana de bloqueo (segundos)", "number", "60", minimum=1, maximum=3600, step="panel"),
    Setting("EC_ADMIN_PASSWORD_FILE", "Panel web", "Archivo de password", step="panel"),
    Setting("EC_ADMIN_STORE", "Panel web", "Archivo de orquestadores", step="panel"),
    Setting("EC_UPDATE_ALLOW_WEB", "Actualizaciones", "Permitir actualizaciones web", "boolean", "true", step="updates"),
    Setting("EC_UPDATE_REPOSITORY", "Actualizaciones", "Repositorio GitHub", default="Ryuz-crypto/APIIntegration", step="updates", help="Formato owner/repository."),
    Setting("EC_UPDATE_BRANCH", "Actualizaciones", "Rama de publicación", default="main", step="updates"),
    Setting("EC_UPDATE_GITHUB_USER", "Actualizaciones", "Usuario GitHub", step="updates"),
    Setting("EC_UPDATE_GITHUB_TOKEN", "Actualizaciones", "Token GitHub", "password", secret=True, step="updates", help="Necesario para repositorios privados; nunca se devuelve al navegador."),
    Setting("EC_UPDATE_PROJECT_DIR", "Actualizaciones", "Directorio instalado", step="updates"),
    Setting("EC_UPDATE_STATE_DIR", "Actualizaciones", "Directorio de estado", default="/var/lib/ec-mcp-update", step="updates"),
    Setting("EC_UPDATE_SERVICE_NAME", "Actualizaciones", "Servicio MCP", default="ec-mcp.service", step="updates"),
    Setting("EC_UPDATE_ADMIN_SERVICE_NAME", "Actualizaciones", "Servicio del panel", default="ec-mcp-admin.service", step="updates"),
    Setting("EC_DASHBOARD_REMOTE_ENABLED", "Dashboard remoto (SSH)", "Habilitar despliegue remoto", "boolean", "false", step="dashboard", help="Instala y publica el dashboard en un servidor Ubuntu vía SSH."),
    Setting("EC_DASHBOARD_REMOTE_HOST", "Dashboard remoto (SSH)", "IP/host del servidor Ubuntu", step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true")),
    Setting("EC_DASHBOARD_REMOTE_USER", "Dashboard remoto (SSH)", "Usuario SSH", step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true")),
    Setting("EC_DASHBOARD_REMOTE_PASSWORD", "Dashboard remoto (SSH)", "Password SSH", "password", secret=True, step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"), help="Requiere sudo en el servidor remoto (instala nginx)."),
    Setting("EC_DASHBOARD_REMOTE_PORT", "Dashboard remoto (SSH)", "Puerto SSH", "integer", "22", minimum=1, maximum=65535, step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true")),
    Setting("EC_DASHBOARD_REMOTE_KEY_PATH", "Dashboard remoto (SSH)", "Ruta de llave privada (opcional)", step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"), help="Si se configura, se usa en lugar del password."),
    Setting("EC_DASHBOARD_PORT", "Dashboard remoto (SSH)", "Puerto HTTP del dashboard en el remoto", "integer", "8090", minimum=1, maximum=65535, step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true")),
    Setting("EC_DASHBOARD_DIR", "Dashboard remoto (SSH)", "Directorio del dashboard en el remoto", default="/var/www/ec-mcp-dashboard", step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true")),
    Setting("EC_DASHBOARD_REFRESH_SECONDS", "Dashboard remoto (SSH)", "Auto-refresh del dashboard (segundos)", "integer", "30", minimum=5, maximum=3600, step="dashboard", depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true")),
)

STEP_TITLES = {
    "orchestrator": "Orchestrator",
    "ssh": "SSH opcional",
    "sse": "Plataforma SSE",
    "targets": "Targets por defecto (multi-orquestador / multi-SSE)",
    "security": "Seguridad del MCP",
    "transport": "Transporte MCP",
    "panel": "Panel web",
    "updates": "Actualizaciones",
    "dashboard": "Dashboard remoto",
}

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
        item["depends_on"] = list(setting.depends_on) if setting.depends_on else None
        value = values.get(setting.key, setting.default)
        item["configured"] = bool(value) if setting.secret else True
        item["value"] = "" if setting.secret else value
        fields.append(item)
    steps = []
    seen = set()
    for setting in SETTINGS:
        if setting.step and setting.step not in seen:
            seen.add(setting.step)
            steps.append({"id": setting.step, "title": STEP_TITLES.get(setting.step, setting.step)})
    return {
        "fields": fields,
        "steps": steps,
        "env_file": str(path or env_path()),
        "restart_required": True,
    }


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


def _env_or(effective: dict[str, str], key: str) -> str:
    return effective.get(key) or os.environ.get(key, "")


def _cross_field_errors(effective: dict[str, str]) -> list[str]:
    """Reglas obligatorias entre varias variables sobre la configuración efectiva."""
    errors: list[str] = []
    url = effective.get("EC_ORCHESTRATOR_URL", "")
    if url and not _env_or(effective, "EC_ORCHESTRATORS_JSON"):
        has_key = effective.get("EC_ORCHESTRATOR_API_KEY", "")
        has_user = effective.get("EC_ORCHESTRATOR_USER", "")
        has_pass = effective.get("EC_ORCHESTRATOR_PASSWORD", "")
        if not has_key and not (has_user and has_pass):
            errors.append(
                "EC_ORCHESTRATOR_URL está configurada pero falta EC_ORCHESTRATOR_API_KEY "
                "o EC_ORCHESTRATOR_USER+EC_ORCHESTRATOR_PASSWORD (o EC_ORCHESTRATORS_JSON)"
            )
    if effective.get("EC_AXIS_ENABLED", "").lower() == "true" and not _env_or(effective, "EC_SSE_PLATFORMS_JSON"):
        if not effective.get("EC_AXIS_ADMIN_TOKEN", ""):
            errors.append("EC_AXIS_ENABLED=true requiere EC_AXIS_ADMIN_TOKEN (o EC_SSE_PLATFORMS_JSON)")
        if not effective.get("EC_AXIS_BASE_URL", ""):
            errors.append("EC_AXIS_ENABLED=true requiere EC_AXIS_BASE_URL (o EC_SSE_PLATFORMS_JSON)")
    host = effective.get("EC_ADMIN_HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        password_file = effective.get("EC_ADMIN_PASSWORD_FILE", "") or str(Path.cwd() / ".ec-admin-pass")
        if not effective.get("EC_ADMIN_PASSWORD", "") and not Path(password_file).is_file():
            errors.append("EC_ADMIN_HOST no es loopback: configura EC_ADMIN_PASSWORD o un EC_ADMIN_PASSWORD_FILE existente")
    return errors


def _collect_wanted(
    values: dict[str, object], clear_secrets: list[str] | None, target: Path
) -> tuple[dict[str, str], list[str]]:
    clear = set(clear_secrets or [])
    unknown = (set(values) | clear) - set(BY_KEY)
    if unknown:
        return {}, ["Variables no permitidas: " + ", ".join(sorted(unknown))]
    errors: list[str] = []
    wanted: dict[str, str] = {}
    for key, raw in values.items():
        setting = BY_KEY[key]
        if setting.secret and (raw is None or str(raw) == ""):
            continue
        try:
            wanted[key] = _validate(setting, raw)
        except ValueError as exc:
            errors.append(str(exc))
    for key in clear:
        if not BY_KEY[key].secret:
            errors.append(f"{key}: sólo se pueden limpiar secretos")
        else:
            wanted[key] = ""
    if not errors:
        effective = _effective_values(target)
        effective.update(wanted)
        for key in clear:
            effective[key] = ""
        errors.extend(_cross_field_errors(effective))
    return wanted, errors


def diff_env(
    values: dict[str, object], clear_secrets: list[str] | None = None, path: Path | None = None
) -> dict:
    """Preview de cambios sobre el .env sin escribir: valida y lista el diff."""
    target = path or env_path()
    wanted, errors = _collect_wanted(values, clear_secrets, target)
    current = _effective_values(target)
    changes = []
    for key, new in wanted.items():
        setting = BY_KEY[key]
        old = current.get(key, setting.default)
        if old == new:
            continue
        cleared = key in set(clear_secrets or []) and new == ""
        changes.append(
            {
                "key": key,
                "old": "***" if setting.secret else old,
                "new": "***" if setting.secret else new,
                "secret": setting.secret,
                "cleared": cleared,
            }
        )
    return {"ok": not errors, "errors": errors, "changes": changes, "env_file": str(target)}


def update_env(values: dict[str, object], clear_secrets: list[str] | None = None, path: Path | None = None) -> Path:
    target = path or env_path()
    wanted, errors = _collect_wanted(values, clear_secrets, target)
    if errors:
        raise ValueError("; ".join(errors))

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
