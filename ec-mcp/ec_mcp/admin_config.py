"""Validated web configuration for ec-mcp.

Only variables declared in SETTINGS can be changed. Secret values are never
returned by the API; an empty secret keeps the current value and explicit
entries in clear_secrets remove it.
"""

from __future__ import annotations

import os
import re
import ssl
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
    Setting(
        "EC_ORCHESTRATOR_URL",
        "Orchestrator",
        "URL del Orchestrator",
        "url",
        required=True,
        step="orchestrator",
        help="URL HTTPS o HTTP del Orchestrator. Obligatoria para usar el Orchestrator.",
    ),
    Setting(
        "EC_ORCHESTRATOR_API_KEY",
        "Orchestrator",
        "API key (X-Auth-Token)",
        "password",
        secret=True,
        step="orchestrator",
        help="Obligatoria salvo que configures usuario+password.",
    ),
    Setting("EC_ORCHESTRATOR_USER", "Orchestrator", "Usuario alternativo", step="orchestrator"),
    Setting(
        "EC_ORCHESTRATOR_PASSWORD", "Orchestrator", "Password alternativo", "password", secret=True, step="orchestrator"
    ),
    Setting("EC_VERIFY_TLS", "Orchestrator", "Verificar TLS", "boolean", "true", step="orchestrator"),
    Setting(
        "EC_SSH_ENABLED",
        "SSH opcional",
        "Habilitar SSH",
        "boolean",
        "false",
        step="ssh",
        help="run_show_api no usa SSH.",
    ),
    Setting(
        "EC_SSH_HOST", "SSH opcional", "Host SSH predeterminado", step="ssh", depends_on=("EC_SSH_ENABLED", "true")
    ),
    Setting("EC_SSH_USER", "SSH opcional", "Usuario SSH", step="ssh", depends_on=("EC_SSH_ENABLED", "true")),
    Setting(
        "EC_SSH_PASSWORD",
        "SSH opcional",
        "Password SSH",
        "password",
        secret=True,
        step="ssh",
        depends_on=("EC_SSH_ENABLED", "true"),
    ),
    Setting(
        "EC_SSH_ENABLE_PASSWORD",
        "SSH opcional",
        "Password enable",
        "password",
        secret=True,
        step="ssh",
        depends_on=("EC_SSH_ENABLED", "true"),
    ),
    Setting(
        "EC_SSH_PORT",
        "SSH opcional",
        "Puerto SSH",
        "integer",
        "22",
        minimum=1,
        maximum=65535,
        step="ssh",
        depends_on=("EC_SSH_ENABLED", "true"),
    ),
    Setting(
        "EC_SSH_AUTH_METHOD",
        "SSH opcional",
        "Método de autenticación",
        "choice",
        "auto",
        choices=("auto", "password", "keyboard-interactive"),
        step="ssh",
        depends_on=("EC_SSH_ENABLED", "true"),
    ),
    Setting(
        "EC_AXIS_ENABLED",
        "Axis Security (SSE)",
        "Habilitar Axis Security",
        "boolean",
        "false",
        step="sse",
        help="Plataforma SSE de Axis Security.",
    ),
    Setting(
        "EC_AXIS_ADMIN_TOKEN",
        "Axis Security (SSE)",
        "Token de administración (Bearer JWT)",
        "password",
        secret=True,
        step="sse",
        depends_on=("EC_AXIS_ENABLED", "true"),
        help="Token JWT para admin-api.axissecurity.com. Obligatoria si Axis está habilitado.",
    ),
    Setting(
        "EC_AXIS_BASE_URL",
        "Axis Security (SSE)",
        "URL base de Axis",
        "url",
        "https://admin-api.axissecurity.com",
        step="sse",
        depends_on=("EC_AXIS_ENABLED", "true"),
    ),
    Setting(
        "EC_AXIS_VERIFY_TLS",
        "Axis Security (SSE)",
        "Verificar TLS de Axis",
        "boolean",
        "true",
        step="sse",
        depends_on=("EC_AXIS_ENABLED", "true"),
    ),
    Setting(
        "EC_AXIS_TIMEOUT",
        "Axis Security (SSE)",
        "Timeout Axis (segundos)",
        "number",
        "30",
        minimum=1,
        maximum=300,
        step="sse",
        depends_on=("EC_AXIS_ENABLED", "true"),
    ),
    Setting(
        "EC_CENTRAL_ENABLED",
        "Aruba Central",
        "Habilitar Aruba Central",
        "boolean",
        "false",
        step="central",
        help="Sección de HPE Aruba Networking Central (nuevas familias REST API v1).",
    ),
    Setting(
        "EC_CENTRAL_CLIENT_ID",
        "Aruba Central",
        "Client ID (GreenLake OAuth2)",
        "text",
        "",
        step="central",
        depends_on=("EC_CENTRAL_ENABLED", "true"),
        help="Client ID creado en HPE GreenLake (Personal API clients). Obligatorio si Central está habilitado.",
    ),
    Setting(
        "EC_CENTRAL_CLIENT_SECRET",
        "Aruba Central",
        "Client Secret (GreenLake OAuth2)",
        "password",
        secret=True,
        step="central",
        depends_on=("EC_CENTRAL_ENABLED", "true"),
        help="Client Secret de HPE GreenLake; no se muestra. Obligatorio si Central está habilitado.",
    ),
    Setting(
        "EC_CENTRAL_BASE_URL",
        "Aruba Central",
        "URL del gateway de Central",
        "url",
        "https://us.api.central.arubanetworks.com",
        step="central",
        depends_on=("EC_CENTRAL_ENABLED", "true"),
        help="API gateway base URL de tu cuenta (p.ej. https://us5.api.central.arubanetworks.com).",
    ),
    Setting(
        "EC_CENTRAL_TOKEN_URL",
        "Aruba Central",
        "Token URL (opcional, on-prem)",
        "url",
        "https://sso.common.cloud.hpe.com/as/token.oauth2",
        step="central",
        depends_on=("EC_CENTRAL_ENABLED", "true"),
    ),
    Setting(
        "EC_CENTRAL_VERIFY_TLS",
        "Aruba Central",
        "Verificar TLS de Central",
        "boolean",
        "true",
        step="central",
        depends_on=("EC_CENTRAL_ENABLED", "true"),
    ),
    Setting(
        "EC_CENTRAL_TIMEOUT",
        "Aruba Central",
        "Timeout Central (segundos)",
        "number",
        "30",
        minimum=1,
        maximum=300,
        step="central",
        depends_on=("EC_CENTRAL_ENABLED", "true"),
    ),
    Setting(
        "EC_DEFAULT_ORCHESTRATOR",
        "Multi-target",
        "Orquestador por defecto (opcional)",
        step="targets",
        help="Solo si hay varios targets: el que se usa cuando un tool no indica 'target'. Si no hay, no importa.",
    ),
    Setting(
        "EC_DEFAULT_SSE",
        "Multi-target",
        "SSE por defecto (opcional)",
        step="targets",
        help="Solo si hay varias plataformas SSE.",
    ),
    Setting(
        "EC_DEFAULT_CENTRAL",
        "Multi-target",
        "Central por defecto (opcional)",
        step="targets",
        help="Solo si hay varias plataformas Aruba Central.",
    ),
    Setting(
        "EC_ALLOW_WRITE_TOOLS",
        "Seguridad",
        "Permitir escrituras en EdgeConnect (Orchestrator/appliances)",
        "boolean",
        "false",
        step="security",
        help="Gobierna las tools de escritura de EdgeConnect (API/SSH). Independiente de SSE.",
    ),
    Setting(
        "EC_ALLOW_SSE_WRITE_TOOLS",
        "Seguridad",
        "Permitir escrituras en HPE SSE (Axis)",
        "boolean",
        "false",
        step="security",
        help="Gobierna las tools de escritura de Axis Security (axis_create/update/delete/commit). Independiente de EdgeConnect.",
    ),
    Setting(
        "EC_ALLOW_DANGEROUS_WRITES", "Seguridad", "Permitir escrituras peligrosas", "boolean", "false", step="security"
    ),
    Setting(
        "EC_MAX_WRITES_PER_MINUTE",
        "Seguridad",
        "Máximo de escrituras por minuto",
        "integer",
        "10",
        minimum=1,
        maximum=1000,
        step="security",
    ),
    Setting(
        "EC_MAX_OUTPUT_CHARS",
        "Seguridad",
        "Máximo de caracteres de salida",
        "integer",
        "12000",
        minimum=1000,
        maximum=1000000,
        step="security",
    ),
    Setting(
        "EC_API_CACHE_TTL",
        "Seguridad",
        "TTL de caché API (segundos)",
        "number",
        "30",
        minimum=0,
        maximum=86400,
        step="security",
    ),
    Setting("EC_MCP_AUDIT_LOG", "Seguridad", "Archivo de auditoría", default="logs/mcp-audit.jsonl", step="security"),
    Setting("EC_MCP_PROFILES_DIR", "Seguridad", "Directorio de perfiles", step="security"),
    Setting(
        "EC_MCP_AUTH_TOKEN",
        "Transporte MCP",
        "Bearer token MCP",
        "password",
        secret=True,
        step="transport",
        help="Token principal. Genera tokens adicionales por plataforma de IA desde la pestaña Tokens MCP.",
    ),
    Setting(
        "EC_MCP_AUTH_TOKENS_JSON",
        "Transporte MCP",
        'Tokens con nombre (JSON {"Vibe": "..."})',
        "password",
        secret=True,
        step="transport",
        help="Tokens independientes por plataforma de IA, gestionados desde la pestaña Tokens MCP. Se pueden revocar sin afectar al token principal.",
    ),
    Setting("EC_MCP_HOST", "Transporte MCP", "IP de escucha MCP", default="127.0.0.1", step="transport"),
    Setting(
        "EC_MCP_PORT", "Transporte MCP", "Puerto MCP", "integer", "8000", minimum=1, maximum=65535, step="transport"
    ),
    Setting("EC_MCP_ALLOWED_HOSTS", "Transporte MCP", "Hosts permitidos", step="transport"),
    Setting("EC_MCP_JSON_RESPONSE", "Transporte MCP", "Respuesta JSON", "boolean", "true", step="transport"),
    Setting("EC_MCP_STATELESS", "Transporte MCP", "Modo stateless", "boolean", "false", step="transport"),
    Setting("EC_MCP_BUILD_COMMIT", "Transporte MCP", "Commit de build", step="transport"),
    Setting(
        "EC_MCP_DISABLED_TOOLS",
        "Seguridad",
        "Tools MCP desactivadas (coma)",
        step="security",
        help="Lista separada por comas de nombres de tools que no se exponen (p. ej. desde la pestaña Tools).",
    ),
    Setting("EC_ADMIN_HOST", "Panel web", "IP de escucha del panel", default="127.0.0.1", step="panel"),
    Setting(
        "EC_ADMIN_PORT", "Panel web", "Puerto del panel", "integer", "8080", minimum=1, maximum=65535, step="panel"
    ),
    Setting(
        "EC_ADMIN_PASSWORD",
        "Panel web",
        "Password del administrador",
        "password",
        secret=True,
        step="panel",
        help="Obligatoria si el panel escucha en una IP no loopback.",
    ),
    Setting(
        "EC_ADMIN_USERS_FILE",
        "Panel web",
        "Archivo de usuarios del panel",
        step="panel",
        help="JSON 0600 con usuarios y roles; si no existe se usa EC_ADMIN_PASSWORD.",
    ),
    Setting(
        "EC_ADMIN_LOGIN_MAX_FAILURES",
        "Panel web",
        "Intentos fallidos antes del bloqueo",
        "integer",
        "5",
        minimum=1,
        maximum=100,
        step="panel",
    ),
    Setting(
        "EC_ADMIN_LOGIN_WINDOW_SECONDS",
        "Panel web",
        "Ventana de bloqueo (segundos)",
        "number",
        "60",
        minimum=1,
        maximum=3600,
        step="panel",
    ),
    Setting("EC_ADMIN_PASSWORD_FILE", "Panel web", "Archivo de password", step="panel"),
    Setting("EC_ADMIN_STORE", "Panel web", "Archivo de orquestadores", step="panel"),
    Setting(
        "EC_ADMIN_TLS_ENABLED",
        "Panel web",
        "Habilitar HTTPS en el panel",
        "boolean",
        "false",
        step="panel",
        help="Usa los certificados subidos desde la pestaña Certificados.",
    ),
    Setting(
        "EC_ADMIN_TLS_CERT",
        "Panel web",
        "Ruta del certificado TLS (PEM)",
        step="panel",
        depends_on=("EC_ADMIN_TLS_ENABLED", "true"),
    ),
    Setting(
        "EC_ADMIN_TLS_KEY",
        "Panel web",
        "Ruta de la llave privada TLS (PEM)",
        step="panel",
        depends_on=("EC_ADMIN_TLS_ENABLED", "true"),
    ),
    Setting(
        "EC_ADMIN_TLS_DIR",
        "Panel web",
        "Directorio de certificados subidos",
        default=".ec-admin-tls",
        step="panel",
        depends_on=("EC_ADMIN_TLS_ENABLED", "true"),
    ),
    Setting(
        "EC_UPDATE_ALLOW_WEB", "Actualizaciones", "Permitir actualizaciones web", "boolean", "true", step="updates"
    ),
    Setting(
        "EC_UPDATE_REPOSITORY",
        "Actualizaciones",
        "Repositorio GitHub",
        default="Ryuz-crypto/APIIntegration",
        step="updates",
        help="Formato owner/repository.",
    ),
    Setting("EC_UPDATE_BRANCH", "Actualizaciones", "Rama de publicación", default="main", step="updates"),
    Setting("EC_UPDATE_GITHUB_USER", "Actualizaciones", "Usuario GitHub", step="updates"),
    Setting(
        "EC_UPDATE_GITHUB_TOKEN",
        "Actualizaciones",
        "Token GitHub",
        "password",
        secret=True,
        step="updates",
        help="Necesario para repositorios privados; nunca se devuelve al navegador.",
    ),
    Setting("EC_UPDATE_PROJECT_DIR", "Actualizaciones", "Directorio instalado", step="updates"),
    Setting(
        "EC_UPDATE_STATE_DIR",
        "Actualizaciones",
        "Directorio de estado",
        default="/var/lib/ec-mcp-update",
        step="updates",
    ),
    Setting("EC_UPDATE_SERVICE_NAME", "Actualizaciones", "Servicio MCP", default="ec-mcp.service", step="updates"),
    Setting(
        "EC_UPDATE_ADMIN_SERVICE_NAME",
        "Actualizaciones",
        "Servicio del panel",
        default="ec-mcp-admin.service",
        step="updates",
    ),
    Setting(
        "EC_DASHBOARD_REMOTE_ENABLED",
        "Dashboard remoto (SSH)",
        "Habilitar despliegue remoto",
        "boolean",
        "false",
        step="dashboard",
        help="Permite conectarse por SSH a OTRO servidor Linux (Ubuntu) y desplegar ahí todo el dashboard web (nginx incluido), con llave privada opcional.",
    ),
    Setting(
        "EC_DASHBOARD_REMOTE_HOST",
        "Dashboard remoto (SSH)",
        "IP/host del servidor Ubuntu",
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
    ),
    Setting(
        "EC_DASHBOARD_REMOTE_USER",
        "Dashboard remoto (SSH)",
        "Usuario SSH",
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
    ),
    Setting(
        "EC_DASHBOARD_REMOTE_PASSWORD",
        "Dashboard remoto (SSH)",
        "Password SSH",
        "password",
        secret=True,
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
        help="Requiere sudo en el servidor remoto (instala nginx).",
    ),
    Setting(
        "EC_DASHBOARD_REMOTE_PORT",
        "Dashboard remoto (SSH)",
        "Puerto SSH",
        "integer",
        "22",
        minimum=1,
        maximum=65535,
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
    ),
    Setting(
        "EC_DASHBOARD_REMOTE_KEY_PATH",
        "Dashboard remoto (SSH)",
        "Ruta de llave privada (opcional)",
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
        help="Si se configura, se usa en lugar del password.",
    ),
    Setting(
        "EC_DASHBOARD_PORT",
        "Dashboard remoto (SSH)",
        "Puerto HTTP del dashboard en el remoto",
        "integer",
        "8090",
        minimum=1,
        maximum=65535,
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
    ),
    Setting(
        "EC_DASHBOARD_DIR",
        "Dashboard remoto (SSH)",
        "Directorio del dashboard en el remoto",
        default="/var/www/ec-mcp-dashboard",
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
    ),
    Setting(
        "EC_DASHBOARD_REFRESH_SECONDS",
        "Dashboard remoto (SSH)",
        "Auto-refresh del dashboard (segundos)",
        "integer",
        "30",
        minimum=5,
        maximum=3600,
        step="dashboard",
        depends_on=("EC_DASHBOARD_REMOTE_ENABLED", "true"),
    ),
)

STEP_TITLES = {
    "orchestrator": "Orchestrator principal (.env)",
    "ssh": "SSH opcional",
    "sse": "SSE (Axis) en .env",
    "central": "Aruba Central en .env",
    "targets": "Targets: agregar más Orquestadores / SSE / Central",
    "security": "Seguridad del MCP",
    "transport": "Transporte MCP",
    "panel": "Panel web",
    "updates": "Actualizaciones",
    "dashboard": "Dashboard remoto",
}

STEP_TITLES_EN = {
    "orchestrator": "Main Orchestrator (.env)",
    "ssh": "Optional SSH",
    "sse": "SSE (Axis) in .env",
    "central": "Aruba Central in .env",
    "targets": "Targets: add more Orchestrators / SSE / Central",
    "security": "MCP security",
    "transport": "MCP transport",
    "panel": "Web panel",
    "updates": "Updates",
    "dashboard": "Remote dashboard",
}

STEP_DESCS = {
    "orchestrator": "Conexión principal del MCP: URL y credenciales (API key o usuario+password) que quedan en .env. Es el Orchestrator por defecto si no hay targets guardados.",
    "ssh": "Sirve para ejecutar comandos ECOS directamente en los appliances EdgeConnect por SSH (además de la API del Orchestrator). Off por defecto.",
    "sse": "Plataforma SSE (Axis Security) única en .env. Para VARIAS plataformas SSE usa el paso Targets.",
    "central": "Cuenta Aruba Central única en .env (OAuth2 de HPE GreenLake). Para VARIAS cuentas Central usa el paso Targets.",
    "targets": "Aquí se agregan GUARDADOS en el registro: Orquestador #2, #3…, plataformas SSE y cuentas Aruba Central adicionales, cada uno con su nombre. Si hay varios, opcionalmente marca uno como por defecto; si no hay, no pasa nada. Se pueden probar, duplicar, renombrar y eliminar.",
    "security": "Escrituras del MCP (off por defecto), límites y auditoría.",
    "transport": "Host/puerto y auth del transporte MCP (HTTP/SSE/stdio).",
    "panel": "Puerto del panel web, contraseña, bloqueo de login, usuarios multi-rol y certificados TLS.",
    "updates": "Updater web desde GitHub (repo, rama, credenciales si es privado).",
    "dashboard": "Despliegue del dashboard en OTRO servidor Linux por SSH.",
}

STEP_DESCS_EN = {
    "orchestrator": "Main MCP connection: URL and credentials (API key or user+password) saved to .env. Used as default when no registry targets exist.",
    "ssh": "Used to run ECOS commands directly on EdgeConnect appliances over SSH (in addition to the Orchestrator API). Off by default.",
    "sse": "Single SSE (Axis Security) platform in .env. For SEVERAL SSE platforms use the Targets step.",
    "central": "Single Aruba Central account in .env (HPE GreenLake OAuth2). For SEVERAL Central accounts use the Targets step.",
    "targets": "Saved in the registry here: Orchestrator #2, #3…, additional SSE platforms and Aruba Central accounts, each with its own name. If there are several, optionally mark one as default; if there are none, nothing happens. You can test, duplicate, rename and delete them.",
    "security": "MCP write tools (off by default), limits and audit log.",
    "transport": "MCP transport host/port and auth (HTTP/SSE/stdio).",
    "panel": "Web panel port, password, login lockout, multi-role users and TLS certificates.",
    "updates": "Web updater from GitHub (repo, branch, credentials if private).",
    "dashboard": "Deploy the dashboard on ANOTHER Linux server over SSH.",
}

EN_LABELS = {
    "EC_ORCHESTRATOR_URL": "Orchestrator URL",
    "EC_ORCHESTRATOR_API_KEY": "API key (X-Auth-Token)",
    "EC_ORCHESTRATOR_USER": "Alternative user",
    "EC_ORCHESTRATOR_PASSWORD": "Alternative password",  # nosec B105
    "EC_VERIFY_TLS": "Verify TLS",
    "EC_SSH_ENABLED": "Enable SSH",
    "EC_SSH_HOST": "Default SSH host",
    "EC_SSH_USER": "SSH user",
    "EC_SSH_PASSWORD": "SSH password",  # nosec B105
    "EC_SSH_ENABLE_PASSWORD": "Enable password",  # nosec B105
    "EC_SSH_PORT": "SSH port",
    "EC_SSH_AUTH_METHOD": "Authentication method",
    "EC_AXIS_ENABLED": "Enable Axis Security",
    "EC_AXIS_ADMIN_TOKEN": "Admin token (Bearer JWT)",  # nosec B105
    "EC_AXIS_BASE_URL": "Axis base URL",
    "EC_AXIS_VERIFY_TLS": "Verify Axis TLS",
    "EC_AXIS_TIMEOUT": "Axis timeout (seconds)",
    "EC_CENTRAL_ENABLED": "Enable Aruba Central",
    "EC_CENTRAL_CLIENT_ID": "Client ID (GreenLake OAuth2)",
    "EC_CENTRAL_CLIENT_SECRET": "Client Secret (GreenLake OAuth2)",  # nosec B105
    "EC_CENTRAL_BASE_URL": "Central gateway base URL",
    "EC_CENTRAL_TOKEN_URL": "Token URL (optional, on-prem)",
    "EC_CENTRAL_VERIFY_TLS": "Verify Central TLS",
    "EC_CENTRAL_TIMEOUT": "Central timeout (seconds)",
    "EC_DEFAULT_CENTRAL": "Default Central (optional)",
    "EC_DEFAULT_ORCHESTRATOR": "Default Orchestrator (optional)",
    "EC_DEFAULT_SSE": "Default SSE platform (optional)",
    "EC_ALLOW_WRITE_TOOLS": "Allow EdgeConnect writes (Orchestrator/appliances)",
    "EC_ALLOW_SSE_WRITE_TOOLS": "Allow HPE SSE (Axis) writes",
    "EC_ALLOW_DANGEROUS_WRITES": "Allow dangerous writes",
    "EC_MAX_WRITES_PER_MINUTE": "Max writes per minute",
    "EC_MAX_OUTPUT_CHARS": "Max output characters",
    "EC_API_CACHE_TTL": "API cache TTL (seconds)",
    "EC_MCP_AUDIT_LOG": "Audit log file",
    "EC_MCP_PROFILES_DIR": "Profiles directory",
    "EC_MCP_AUTH_TOKEN": "MCP bearer token",  # nosec B105
    "EC_MCP_HOST": "MCP listen IP",
    "EC_MCP_PORT": "MCP port",
    "EC_MCP_ALLOWED_HOSTS": "Allowed hosts",
    "EC_MCP_JSON_RESPONSE": "JSON responses",
    "EC_MCP_STATELESS": "Stateless mode",
    "EC_MCP_BUILD_COMMIT": "Build commit",
    "EC_MCP_DISABLED_TOOLS": "Disabled MCP tools (comma-separated)",
    "EC_ADMIN_HOST": "Panel listen IP",
    "EC_ADMIN_PORT": "Panel port",
    "EC_ADMIN_PASSWORD": "Administrator password",  # nosec B105
    "EC_ADMIN_USERS_FILE": "Panel users file",
    "EC_ADMIN_LOGIN_MAX_FAILURES": "Failed attempts before lockout",
    "EC_ADMIN_LOGIN_WINDOW_SECONDS": "Lockout window (seconds)",
    "EC_ADMIN_PASSWORD_FILE": "Password file",  # nosec B105
    "EC_ADMIN_STORE": "Orchestrators file",
    "EC_UPDATE_ALLOW_WEB": "Allow web updates",
    "EC_UPDATE_REPOSITORY": "GitHub repository",
    "EC_UPDATE_BRANCH": "Release branch",
    "EC_UPDATE_GITHUB_USER": "GitHub user",
    "EC_UPDATE_GITHUB_TOKEN": "GitHub token",  # nosec B105
    "EC_UPDATE_PROJECT_DIR": "Installed directory",
    "EC_UPDATE_STATE_DIR": "State directory",
    "EC_UPDATE_SERVICE_NAME": "MCP service",
    "EC_UPDATE_ADMIN_SERVICE_NAME": "Panel service",
    "EC_DASHBOARD_REMOTE_ENABLED": "Enable remote deploy",
    "EC_DASHBOARD_REMOTE_HOST": "Ubuntu server IP/host",
    "EC_DASHBOARD_REMOTE_USER": "SSH user",
    "EC_DASHBOARD_REMOTE_PASSWORD": "SSH password",  # nosec B105
    "EC_DASHBOARD_REMOTE_PORT": "SSH port",
    "EC_DASHBOARD_REMOTE_KEY_PATH": "Private key path (optional)",
    "EC_DASHBOARD_PORT": "Dashboard HTTP port on remote",
    "EC_DASHBOARD_DIR": "Dashboard directory on remote",
    "EC_DASHBOARD_REFRESH_SECONDS": "Dashboard auto-refresh (seconds)",
    "EC_ADMIN_TLS_ENABLED": "Serves the panel over HTTPS using the uploaded certificates.",
    "EC_ADMIN_TLS_CERT": "PEM certificate written by the Certificates tab.",
    "EC_ADMIN_TLS_KEY": "PEM private key written by the Certificates tab.",
    "EC_ADMIN_TLS_DIR": "Upload target directory; files are written with 0600.",
}

GROUP_EN = {
    "Orchestrator": "Orchestrator",
    "SSH opcional": "Optional SSH",
    "Axis Security (SSE)": "Axis Security (SSE)",
    "Aruba Central": "Aruba Central",
    "Multi-target": "Multi-target",
    "Seguridad": "Security",
    "Transporte MCP": "MCP transport",
    "Panel web": "Web panel",
    "Actualizaciones": "Updates",
    "Dashboard remoto (SSH)": "Remote dashboard (SSH)",
}

EN_LABELS_TLS = {
    "EC_ADMIN_TLS_ENABLED": "Enable HTTPS on the panel",
    "EC_ADMIN_TLS_CERT": "TLS certificate path (PEM)",
    "EC_ADMIN_TLS_KEY": "TLS private key path (PEM)",
    "EC_ADMIN_TLS_DIR": "Directory for uploaded certificates",
}
EN_LABELS.update(EN_LABELS_TLS)

EN_HELP = {
    "EC_ORCHESTRATOR_URL": "Orchestrator HTTP/HTTPS URL. Required to use the Orchestrator.",
    "EC_MCP_DISABLED_TOOLS": "Comma-separated list of MCP tool names to hide (managed from the Tools tab).",
    "EC_ORCHESTRATOR_API_KEY": "Required unless user+password are configured.",
    "EC_SSH_ENABLED": "run_show_api does not use SSH.",
    "EC_AXIS_ENABLED": "Axis Security SSE platform.",
    "EC_AXIS_ADMIN_TOKEN": "JWT token for admin-api.axissecurity.com. Required when Axis is enabled.",  # nosec B105
    "EC_CENTRAL_ENABLED": "HPE Aruba Networking Central section (new REST API families v1).",
    "EC_CENTRAL_CLIENT_SECRET": "HPE GreenLake client secret; never displayed. Required when Central is enabled.",  # nosec B105
    "EC_UPDATE_REPOSITORY": "Format owner/repository.",
    "EC_UPDATE_GITHUB_TOKEN": "Needed for private repositories; never returned to the browser.",  # nosec B105
    "EC_ADMIN_PASSWORD": "Required when the panel listens on a non-loopback IP.",  # nosec B105
    "EC_ADMIN_USERS_FILE": "JSON 0600 with users and roles; falls back to EC_ADMIN_PASSWORD when absent.",
    "EC_DASHBOARD_REMOTE_ENABLED": "Connects over SSH to ANOTHER Linux (Ubuntu) server and deploys the whole web dashboard there (nginx included), with optional private key.",
    "EC_DASHBOARD_REMOTE_PASSWORD": "Requires sudo on the remote server (installs nginx).",  # nosec B105
    "EC_DASHBOARD_REMOTE_KEY_PATH": "When set, used instead of the password.",
    "EC_DEFAULT_ORCHESTRATOR": "Only when several targets exist: used when a tool passes no 'target'. Otherwise irrelevant.",
    "EC_DEFAULT_SSE": "Only when several SSE platforms exist.",
    "EC_ALLOW_WRITE_TOOLS": "Governs EdgeConnect write tools (API/SSH). Independent from SSE.",
    "EC_ALLOW_SSE_WRITE_TOOLS": "Governs Axis Security write tools (axis_create/update/delete/commit). Independent from EdgeConnect.",
}

BY_KEY = {setting.key: setting for setting in SETTINGS}
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")


def env_path() -> Path:
    return Path(os.environ.get("EC_MCP_ENV_FILE") or Path.cwd() / ".env")


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
        item["label_en"] = EN_LABELS.get(setting.key, setting.label)
        item["help_en"] = EN_HELP.get(setting.key, setting.help)
        item["group_en"] = GROUP_EN.get(setting.group, setting.group)
        value = values.get(setting.key, setting.default)
        item["configured"] = bool(value) if setting.secret else True
        item["value"] = "" if setting.secret else value
        fields.append(item)
    steps = []
    seen = set()
    for setting in SETTINGS:
        if setting.step and setting.step not in seen:
            seen.add(setting.step)
            steps.append(
                {
                    "id": setting.step,
                    "title": STEP_TITLES.get(setting.step, setting.step),
                    "title_en": STEP_TITLES_EN.get(setting.step, setting.step),
                    "desc": STEP_DESCS.get(setting.step, ""),
                    "desc_en": STEP_DESCS_EN.get(setting.step, ""),
                }
            )
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


def tls_preflight_errors(effective: dict[str, str]) -> list[str]:
    """Validate the TLS pair as the admin service user before a restart."""
    if effective.get("EC_ADMIN_TLS_ENABLED", "false").strip().lower() != "true":
        return []
    cert = effective.get("EC_ADMIN_TLS_CERT", "").strip()
    key = effective.get("EC_ADMIN_TLS_KEY", "").strip()
    if not cert or not key:
        return ["HTTPS está habilitado: configura EC_ADMIN_TLS_CERT y EC_ADMIN_TLS_KEY antes de reiniciar."]
    for label, filename in (("certificado", cert), ("llave", key)):
        path = Path(filename).expanduser()
        if not path.is_file() or not os.access(path, os.R_OK):
            return [f"El archivo de {label} TLS no existe o no es legible por el servicio del panel."]
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(Path(cert).expanduser()), keyfile=str(Path(key).expanduser()))
    except (OSError, ssl.SSLError, ValueError):
        return ["No se pudo cargar el certificado y la llave TLS; revisa que sean válidos, coincidan y sean legibles."]
    return []


def restart_tls_errors(path: Path | None = None) -> list[str]:
    """Check effective configuration without modifying files or changing TLS."""
    return tls_preflight_errors(_effective_values(path))


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
            errors.append(
                "EC_ADMIN_HOST no es loopback: configura EC_ADMIN_PASSWORD o un EC_ADMIN_PASSWORD_FILE existente"
            )
    errors.extend(tls_preflight_errors(effective))
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


def diff_env(values: dict[str, object], clear_secrets: list[str] | None = None, path: Path | None = None) -> dict:
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
