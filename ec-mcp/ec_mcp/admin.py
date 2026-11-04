"""Admin web UI for ec-mcp credentials and orchestrator management.

Serves a small single-page app on a separate port with its own session
auth. Secrets are stored in a JSON file (0600) and can be pushed into the
live MCP server's environment or the .env file.

Endpoints (all behind session cookie auth):
  GET  /            UI
  POST /login       password check (EC_ADMIN_PASSWORD, or first-run set)
  POST /logout
  GET  /api/state   orchestrators + non-secret config
  POST /api/orchestrators   add/update orchestrator entry
  POST /api/orchestrators/delete  remove entry
  POST /api/orchestrators/rename|duplicate  copy/rename registry entries
  POST /api/sse[/delete|/rename|/duplicate]  same for SSE platforms
  POST /api/apply   write selected target into .env (+ full registry blobs)
  POST /api/default set the default Orchestrator/SSE target (EC_DEFAULT_*)
  POST /api/probe   real health check of one registry target
  GET  /api/wizard  wizard payload (steps, fields with required/depends_on)
  POST /api/config/diff  validate + preview .env changes without writing
  GET/POST /api/users[/delete|/password]  multi-user management (admin role)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from math import ceil
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from . import __version__, admin_users
from .admin_config import diff_env, public_config, update_env
from .admin_page import PAGE as _PAGE_TEMPLATE
from .admin_services import ServiceProbeError, probe_axis, probe_orchestrator, services_status
from .admin_users import UserError
from .audit import AuditLog
from .config import Settings
from .multi_target import (
    RegistryError,
    load_registry,
    public_orchestrator,
    public_sse,
)


def _render_page() -> str:
    return _PAGE_TEMPLATE.replace(
        "__EC_MCP_VERSION__", __version__
    )
from .web_update import check as check_update
from .web_update import check_pending_request, queue_restart, queue_update
from .web_update import status as update_status

SESSIONS: dict[str, dict] = {}
SESSION_TTL = 3600.0
LOGIN_FAILURES: dict[str, list[float]] = {}

ROLE_PERMISSIONS = {
    "viewer": {"read"},
    "operator": {"read", "write", "restart", "update"},
    "admin": {"read", "write", "restart", "update", "users"},
}


def _audit_panel(user: str | None, action: str, target: str, result: str, details: dict | None = None) -> None:
    try:
        AuditLog(Settings.from_env().audit_log_path).record(
            tool="admin_panel",
            action=action,
            target=target,
            result=result,
            details=details or {},
            user=user,
        )
    except (OSError, ValueError):
        pass


def _authorize(request, permission: str):
    session = _check_session(request)
    if not session:
        return None, JSONResponse({"error": "unauthorized"}, status_code=401)
    if not isinstance(session, dict):
        session = {"user": "admin", "role": "admin"}
    role = str(session.get("role", "admin"))
    if permission not in ROLE_PERMISSIONS.get(role, set()):
        return None, JSONResponse({"error": "forbidden", "required": permission, "role": role}, status_code=403)
    return session, None


def _positive_number(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


LOGIN_MAX_FAILURES = int(_positive_number("EC_ADMIN_LOGIN_MAX_FAILURES", 5))
LOGIN_WINDOW_SECONDS = _positive_number("EC_ADMIN_LOGIN_WINDOW_SECONDS", 60.0)


def _store_path() -> Path:
    return Path(os.environ.get("EC_ADMIN_STORE", Path.cwd() / ".ec-admin.json"))


def _load_store() -> dict:
    path = _store_path()
    if not path.is_file():
        return {"orchestrators": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("orchestrators", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"orchestrators": {}}


def _save_store(store: dict) -> None:
    path = _store_path()
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
    path.chmod(0o600)


def _admin_password() -> str | None:
    return os.environ.get("EC_ADMIN_PASSWORD") or None


def _password_file() -> Path:
    return Path(os.environ.get("EC_ADMIN_PASSWORD_FILE", Path.cwd() / ".ec-admin-pass"))


def _loopback_only(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


def _has_password_configured() -> bool:
    if _admin_password():
        return True
    return _password_file().is_file()


def _verify_password(candidate: str, allow_first_run: bool = True) -> bool:
    expected = _admin_password()
    if expected is None:
        passfile = _password_file()
        if passfile.is_file():
            expected = passfile.read_text(encoding="utf-8").strip()
    if not expected:
        if not allow_first_run:
            return False
        # First run with no password configured: any password becomes the password.
        passfile = _password_file()
        digest = hashlib.sha256(candidate.encode()).hexdigest()
        passfile.write_text(digest + "\n", encoding="utf-8")
        passfile.chmod(0o600)
        return True
    if expected.startswith("sha256:"):
        return hmac.compare_digest(expected[7:], hashlib.sha256(candidate.encode()).hexdigest())
    if len(expected) == 64 and all(c in "0123456789abcdef" for c in expected.lower()):
        return hmac.compare_digest(expected.lower(), hashlib.sha256(candidate.encode()).hexdigest())
    return hmac.compare_digest(expected, candidate)


def _check_session(request):
    token = request.cookies.get("ec_admin_session", "")
    now = time.time()
    session = SESSIONS.get(token)
    if session and now - session.get("ts", 0) < SESSION_TTL:
        session["ts"] = now
        return session
    return None


async def home(request):
    if not _check_session(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponseMin(_render_page())


async def login_page(request):
    return HTMLResponseMin(_render_page())


async def login_post(request):
    body = await request.json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")  # nosec B104
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    failures = [t for t in LOGIN_FAILURES.get(client_ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    if admin_users.has_users():
        role = admin_users.verify_user(username, password) if username and password else None
        valid = role is not None
        user_label = username or "(sin usuario)"
    else:
        role = "admin"
        valid = bool(password) and _verify_password(password, allow_first_run=_loopback_only(host))
        user_label = "admin"
    if valid:
        LOGIN_FAILURES.pop(client_ip, None)
        _audit_panel(user_label, "login", "panel", "ok")
    elif len(failures) >= LOGIN_MAX_FAILURES:
        retry_after = max(1, ceil(LOGIN_WINDOW_SECONDS - (now - min(failures))))
        return JSONResponse(
            {
                "ok": False,
                "error": f"Demasiados intentos. Reintenta en {retry_after} segundos.",
                "retry_after_seconds": retry_after,
            },
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    else:
        failures.append(now)
        LOGIN_FAILURES[client_ip] = failures
        remaining = max(0, LOGIN_MAX_FAILURES - len(failures))
        _audit_panel(user_label, "login_denied", "panel", "denied")
        return JSONResponse(
            {
                "ok": False,
                "error": f"Credenciales incorrectas. Intentos restantes: {remaining}.",
                "remaining_attempts": remaining,
            },
        )
    token = secrets.token_urlsafe(32)
    role = role or "admin"
    SESSIONS[token] = {"user": user_label, "role": role, "ts": now}
    response = JSONResponse({"ok": True, "user": user_label, "role": role})
    response.set_cookie("ec_admin_session", token, httponly=True, samesite="lax", max_age=int(SESSION_TTL))
    return response


async def logout_post(request):
    token = request.cookies.get("ec_admin_session", "")
    session = SESSIONS.pop(token, None)
    if session:
        _audit_panel(session.get("user"), "logout", "panel", "ok")
    response = JSONResponse({"ok": True})
    response.delete_cookie("ec_admin_session")
    return response


def _public_state() -> dict:
    registry = load_registry()
    active = os.environ.get("EC_ORCHESTRATOR_URL", "")
    default_orch = os.environ.get("EC_DEFAULT_ORCHESTRATOR", "").strip()
    default_sse = os.environ.get("EC_DEFAULT_SSE", "").strip()
    orchestrators = []
    for name, entry in registry.list_orchestrators().items():
        item = public_orchestrator(name, entry)
        item["active"] = bool(active) and entry.get("url", "") == active
        item["default"] = bool(default_orch) and name == default_orch
        orchestrators.append(item)
    sse_platforms = []
    for name, entry in registry.list_sse().items():
        item = public_sse(name, entry)
        if name == "default":
            item["active"] = os.environ.get("EC_AXIS_ENABLED", "false").lower() == "true"
        else:
            item["active"] = False
        item["default"] = bool(default_sse) and name == default_sse
        sse_platforms.append(item)
    return {
        "orchestrators": orchestrators,
        "sse_platforms": sse_platforms,
        "ssh_enabled": os.environ.get("EC_SSH_ENABLED", "false").lower() == "true",
        "default_orchestrator": default_orch,
        "default_sse": default_sse,
        "blobs": {
            "orchestrators": bool(os.environ.get("EC_ORCHESTRATORS_JSON", "").strip()),
            "sse": bool(os.environ.get("EC_SSE_PLATFORMS_JSON", "").strip()),
        },
    }


async def api_state(request):
    session, denied = _authorize(request, "read")
    if denied:
        return denied
    state = _public_state()
    state["session"] = {"user": session["user"], "role": session["role"]}
    return JSONResponse(state)


async def api_save_orchestrator(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "").strip()
    entry = {
        "url": str(body.get("url") or "").strip(),
        "verify_tls": body.get("verify_tls", True),
        "api_key": body.get("api_key") or None,
        "username": body.get("username") or None,
        "password": body.get("password") or None,
        "ssh_user": body.get("ssh_user") or None,
        "ssh_password": body.get("ssh_password") or None,
        "ssh_enable_password": body.get("ssh_enable_password") or None,
        "ssh_host": body.get("ssh_host") or None,
    }
    try:
        load_registry().save_orchestrator(name, entry)
    except RegistryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)})
    _audit_panel(session["user"], "save_orchestrator", name, "ok")
    return JSONResponse({"ok": True, "message": f"Orquestador '{name}' guardado. Usa 'Aplicar' para activarlo."})


async def api_delete_orchestrator(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "")
    deleted = load_registry().delete_orchestrator(name)
    _audit_panel(session["user"], "delete_orchestrator", name, "ok" if deleted else "missing")
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminado" if deleted else "No existía"})


async def api_save_sse(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "").strip()
    entry = {
        "provider": body.get("provider") or "axis",
        "base_url": str(body.get("base_url") or "").strip(),
        "admin_token": body.get("admin_token") or None,
        "verify_tls": body.get("verify_tls", True),
        "timeout": body.get("timeout"),
    }
    try:
        load_registry().save_sse(name, entry)
    except RegistryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)})
    _audit_panel(session["user"], "save_sse", name, "ok")
    return JSONResponse({"ok": True, "message": f"Plataforma SSE '{name}' guardada."})


async def api_delete_sse(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "")
    deleted = load_registry().delete_sse(name)
    _audit_panel(session["user"], "delete_sse", name, "ok" if deleted else "missing")
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminada" if deleted else "No existía"})


async def _registry_copy(request, method, label: str):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "").strip()
    new_name = str(body.get("new_name") or "").strip()
    try:
        method(name, new_name)
    except RegistryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], method.__name__, f"{name} -> {new_name}", "ok")
    return JSONResponse({"ok": True, "message": f"{label} '{name}' -> '{new_name}'"})


async def api_rename_orchestrator(request):
    return await _registry_copy(request, load_registry().rename_orchestrator, "Orquestador")


async def api_duplicate_orchestrator(request):
    return await _registry_copy(request, load_registry().duplicate_orchestrator, "Orquestador")


async def api_rename_sse(request):
    return await _registry_copy(request, load_registry().rename_sse, "Plataforma SSE")


async def api_duplicate_sse(request):
    return await _registry_copy(request, load_registry().duplicate_sse, "Plataforma SSE")


async def api_default_target(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    kind = str(body.get("kind") or "").strip().lower()
    name = str(body.get("name") or "").strip()
    registry = load_registry()
    if kind == "sse":
        key = "EC_DEFAULT_SSE"
        exists = registry.get_sse(name) if name else True
    else:
        key = "EC_DEFAULT_ORCHESTRATOR"
        exists = registry.get_orchestrator(name) if name else True
    if name and not exists:
        return JSONResponse({"ok": False, "error": f"No existe el target '{name}'"}, status_code=404)
    try:
        update_env({key: name})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "default_target", f"{kind}:{name or '(auto)'}", "ok")
    return JSONResponse({"ok": True, "message": f"Target por defecto: {name or '(automático)'}"})


async def api_probe(request):
    session, denied = _authorize(request, "read")
    if denied:
        return denied
    body = await request.json()
    kind = str(body.get("kind") or "orchestrator").strip().lower()
    name = str(body.get("name") or "").strip()
    registry = load_registry()
    if kind == "sse":
        entry = registry.get_sse(name)
        probe = probe_axis
    else:
        entry = registry.get_orchestrator(name)
        probe = probe_orchestrator
    if not entry:
        return JSONResponse({"ok": False, "error": f"No existe el target '{name}'"}, status_code=404)
    try:
        result = probe(entry)
        payload = {"ok": True, "kind": kind, "name": name, "state": "up", **result}
    except (ServiceProbeError, httpx.HTTPError, ValueError) as exc:
        payload = {"ok": False, "kind": kind, "name": name, "state": "down", "error": str(exc)}
    _audit_panel(
        session["user"], "probe", f"{kind}:{name}", payload["state"], {"error": str(payload.get("error", ""))[:200]}
    )
    return JSONResponse(payload)


ENV_KEYS = {
    "url": "EC_ORCHESTRATOR_URL",
    "api_key": "EC_ORCHESTRATOR_API_KEY",
    "username": "EC_ORCHESTRATOR_USER",
    "password": "EC_ORCHESTRATOR_PASSWORD",  # nosec B105
    "verify_tls": "EC_VERIFY_TLS",
    "ssh_user": "EC_SSH_USER",
    "ssh_password": "EC_SSH_PASSWORD",  # nosec B105
    "ssh_enable_password": "EC_SSH_ENABLE_PASSWORD",  # nosec B105
    "ssh_host": "EC_SSH_HOST",
}


async def api_apply(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "").strip()
    kind = str(body.get("kind") or "orchestrator").strip().lower()
    registry = load_registry()
    if kind == "sse":
        if name and not registry.get_sse(name):
            return JSONResponse({"ok": False, "error": f"No existe la plataforma SSE '{name}'"})
        if not name:
            entries = registry.list_sse()
            if not entries:
                return JSONResponse({"ok": False, "error": "No hay plataformas SSE guardadas"})
            name = sorted(entries)[0]
        entry = registry.get_sse(name)
        wanted = {
            "EC_AXIS_ENABLED": "true",
            "EC_AXIS_ADMIN_TOKEN": entry.get("admin_token") or "",
            "EC_AXIS_BASE_URL": entry.get("base_url") or "",
            "EC_AXIS_VERIFY_TLS": str(public_sse(name, entry)["verify_tls"]).lower(),
            "EC_AXIS_TIMEOUT": str(public_sse(name, entry).get("timeout") or ""),
        }
        target_label = f"Plataforma SSE '{name}'"
    else:
        if name and not registry.get_orchestrator(name):
            return JSONResponse({"ok": False, "error": f"No existe el orquestador '{name}'"})
        if not name:
            entries = registry.list_orchestrators()
            if not entries:
                return JSONResponse({"ok": False, "error": "No hay orquestadores guardados"})
            active = os.environ.get("EC_ORCHESTRATOR_URL", "")
            name = next((n for n, e in sorted(entries.items()) if e.get("url") == active), sorted(entries)[0])
        entry = registry.get_orchestrator(name)
        wanted = {
            "EC_ORCHESTRATOR_URL": entry.get("url") or "",
            "EC_ORCHESTRATOR_API_KEY": entry.get("api_key") or "",
            "EC_ORCHESTRATOR_USER": entry.get("username") or "",
            "EC_ORCHESTRATOR_PASSWORD": entry.get("password") or "",
            "EC_VERIFY_TLS": str(public_orchestrator(name, entry)["verify_tls"]).lower(),
            "EC_SSH_ENABLED": "true" if entry.get("ssh_user") else os.environ.get("EC_SSH_ENABLED", "false"),
            "EC_SSH_USER": entry.get("ssh_user") or "",
            "EC_SSH_PASSWORD": entry.get("ssh_password") or "",
            "EC_SSH_ENABLE_PASSWORD": entry.get("ssh_enable_password") or "",
            "EC_SSH_HOST": entry.get("ssh_host") or "",
        }
        target_label = f"Orquestador '{name}'"
    # Persistir el registro completo como blobs JSON para el runtime multi-target.
    for key, value in registry.to_env_blob().items():
        wanted[key] = value
    for key in ("EC_DEFAULT_ORCHESTRATOR", "EC_DEFAULT_SSE"):
        if os.environ.get(key, "").strip():
            wanted[key] = os.environ[key]
    env_path = Path(os.environ.get("EC_MCP_ENV_FILE", Path.cwd() / ".env"))
    lines = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    for key, value in wanted.items():
        set_line = f"{key}={value}"
        for i, line in enumerate(lines):
            if line.startswith(key + "="):
                lines[i] = set_line
                break
        else:
            lines.append(set_line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    for key, value in wanted.items():
        os.environ[key] = value
    _audit_panel(session["user"], "apply", target_label, "ok", {"env_file": str(env_path)})
    return JSONResponse(
        {
            "ok": True,
            "message": (
                f"{target_label} escrito en {env_path}. Reinicia el servicio para "
                "que el cambio quede persistente. Usa 'Guardar y reiniciar servicios' desde Variables para aplicarlo"
            ),
        }
    )


async def api_services_status(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    return JSONResponse(services_status(probe=True))


async def api_config(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    return JSONResponse(public_config())


async def api_wizard(request):
    session, denied = _authorize(request, "read")
    if denied:
        return denied
    config = public_config()
    state = _public_state()
    state["session"] = {"user": session["user"], "role": session["role"]}
    return JSONResponse(
        {
            "steps": config["steps"],
            "fields": config["fields"],
            "state": state,
            "env_file": config["env_file"],
        }
    )


async def api_config_diff(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    try:
        body = await request.json()
        result = diff_env(body.get("values") or {}, body.get("clear_secrets") or [])
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"ok": False, "errors": [str(exc)], "changes": []}, status_code=400)
    return JSONResponse(result, status_code=200 if result["ok"] else 400)


async def api_save_config(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    try:
        body = await request.json()
        path = update_env(body.get("values") or {}, body.get("clear_secrets") or [])
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(
        session["user"], "save_config", "env", "ok", {"changed": sorted((body.get("values") or {}).keys())[:50]}
    )
    return JSONResponse(
        {
            "ok": True,
            "message": f"Variables guardadas de forma atómica en {path}. Reinicia los servicios para aplicarlas.",
            "restart_required": True,
        }
    )


async def api_update_check(request):
    _session, denied = _authorize(request, "update")
    if denied:
        return denied
    try:
        return JSONResponse(check_update())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


async def api_update_status(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    return JSONResponse(update_status())


async def api_update_apply(request):
    session, denied = _authorize(request, "update")
    if denied:
        return denied
    try:
        body = await request.json()
        result = queue_update(str(body.get("remote_sha") or ""), str(body.get("confirmation") or ""))
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "update_apply", "panel", str(result.get("state", "")))
    return JSONResponse(result)


async def api_restart(request):
    session, denied = _authorize(request, "restart")
    if denied:
        return denied
    try:
        result = queue_restart()
    except (OSError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "restart", "panel", str(result.get("state", "")))
    return JSONResponse(result)


async def api_restart_result(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    state = update_status()
    state.setdefault("state", "idle")
    state["request_pending"] = check_pending_request()
    return JSONResponse(state)


async def api_users_list(request):
    _session, denied = _authorize(request, "users")
    if denied:
        return denied
    return JSONResponse(
        {
            "ok": True,
            "users": admin_users.public_users(),
            "file": str(admin_users.users_path()),
            "multi_user": admin_users.has_users(),
            "roles": list(admin_users.ROLES),
        }
    )


async def api_users_save(request):
    session, denied = _authorize(request, "users")
    if denied:
        return denied
    body = await request.json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    role = str(body.get("role") or "viewer")
    try:
        result = admin_users.upsert_user(username, password, role)
    except UserError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "user_save", username, f"role={result['role']}")
    return JSONResponse({"ok": True, "message": f"Usuario '{username}' guardado con rol '{result['role']}'", **result})


async def api_users_delete(request):
    session, denied = _authorize(request, "users")
    if denied:
        return denied
    body = await request.json()
    username = str(body.get("username") or "").strip()
    users = admin_users.load_users()
    admins = [name for name, info in users.items() if str(info.get("role")) == "admin"]
    if users.get(username, {}).get("role") == "admin" and len(admins) <= 1:
        return JSONResponse({"ok": False, "error": "No se puede eliminar el último administrador"}, status_code=400)
    deleted = admin_users.delete_user(username)
    _audit_panel(session["user"], "user_delete", username, "ok" if deleted else "missing")
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminado" if deleted else "No existía"})


def _tls_dir() -> Path:
    return Path(os.environ.get("EC_ADMIN_TLS_DIR", Path.cwd() / ".ec-admin-tls"))


def _tls_paths() -> tuple[Path, Path]:
    directory = _tls_dir()
    cert = Path(os.environ.get("EC_ADMIN_TLS_CERT", "") or (directory / "cert.pem"))
    key = Path(os.environ.get("EC_ADMIN_TLS_KEY", "") or (directory / "key.pem"))
    return cert, key


def _cert_fingerprint(pem: str) -> str | None:
    try:
        import ssl

        der = ssl.PEM_cert_to_DER_cert(pem)
        return hashlib.sha256(der).hexdigest()
    except (ValueError, TypeError):
        return None


async def api_tls_status(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    cert_path, key_path = _tls_paths()
    cert_pem = cert_path.read_text(encoding="utf-8") if cert_path.is_file() else ""
    return JSONResponse(
        {
            "ok": True,
            "enabled": os.environ.get("EC_ADMIN_TLS_ENABLED", "false").lower() == "true",
            "cert": str(cert_path),
            "key": str(key_path),
            "cert_present": bool(cert_pem),
            "key_present": key_path.is_file(),
            "fingerprint": _cert_fingerprint(cert_pem) if cert_pem else None,
        }
    )


async def api_tls_upload(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    cert_pem = str(body.get("cert") or "")
    key_pem = str(body.get("key") or "")
    if "BEGIN CERTIFICATE" not in cert_pem:
        return JSONResponse({"ok": False, "error": "El certificado debe ser PEM con bloque BEGIN CERTIFICATE"}, status_code=400)
    if "PRIVATE KEY" not in key_pem:
        return JSONResponse({"ok": False, "error": "La llave debe ser PEM con bloque PRIVATE KEY"}, status_code=400)
    if _cert_fingerprint(cert_pem) is None:
        return JSONResponse({"ok": False, "error": "Certificado PEM inválido"}, status_code=400)
    cert_path, key_path = _tls_paths()
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_text(cert_pem if cert_pem.endswith("\n") else cert_pem + "\n", encoding="utf-8")
    key_path.write_text(key_pem if key_pem.endswith("\n") else key_pem + "\n", encoding="utf-8")
    cert_path.chmod(0o600)
    key_path.chmod(0o600)
    try:
        update_env({"EC_ADMIN_TLS_CERT": str(cert_path), "EC_ADMIN_TLS_KEY": str(key_path)})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "tls_upload", str(cert_path), "ok", {"fingerprint": _cert_fingerprint(cert_pem)})
    return JSONResponse(
        {
            "ok": True,
            "message": f"Certificado guardado en {cert_path} (0600). Activa EC_ADMIN_TLS_ENABLED=true y reinicia el panel para servir HTTPS.",
            "fingerprint": _cert_fingerprint(cert_pem),
        }
    )


async def api_tls_delete(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    cert_path, key_path = _tls_paths()
    removed = []
    for path in (cert_path, key_path):
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    try:
        update_env({"EC_ADMIN_TLS_CERT": "", "EC_ADMIN_TLS_KEY": ""})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "tls_delete", ",".join(removed) or "(nada)", "ok")
    return JSONResponse({"ok": True, "removed": removed, "message": "Certificados eliminados" if removed else "No había certificados"})


async def api_users_password(request):
    session, denied = _authorize(request, "read")
    if denied:
        return denied
    body = await request.json()
    target_user = str(body.get("username") or "").strip() or session["user"]
    old_password = str(body.get("old_password") or "")
    new_password = str(body.get("new_password") or "")
    if target_user != session["user"] and session.get("role") != "admin":
        return JSONResponse({"ok": False, "error": "Solo un admin puede cambiar la contraseña de otro usuario"}, status_code=403)
    try:
        if admin_users.has_users():
            if target_user == session["user"] and admin_users.verify_user(target_user, old_password) is None:
                return JSONResponse({"ok": False, "error": "Contraseña actual incorrecta"}, status_code=400)
            admin_users.set_password(target_user, new_password)
        else:
            if target_user != "admin":
                return JSONResponse({"ok": False, "error": "En modo de contraseña única solo existe 'admin'"}, status_code=400)
            if not _verify_password(old_password, allow_first_run=False):
                return JSONResponse({"ok": False, "error": "Contraseña actual incorrecta"}, status_code=400)
            update_env({"EC_ADMIN_PASSWORD": new_password})
    except (UserError, OSError, TypeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "user_password", target_user, "changed")
    return JSONResponse({"ok": True, "message": f"Contraseña actualizada para '{target_user}'"})


from starlette.responses import Response


def HTMLResponseMin(content: str) -> Response:
    return Response(content, media_type="text/html")


def build_admin_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/", home, methods=["GET"]),
            Route("/login", login_page, methods=["GET"]),
            Route("/login", login_post, methods=["POST"]),
            Route("/logout", logout_post, methods=["POST"]),
            Route("/api/state", api_state, methods=["GET"]),
            Route("/api/orchestrators", api_save_orchestrator, methods=["POST"]),
            Route("/api/orchestrators/delete", api_delete_orchestrator, methods=["POST"]),
            Route("/api/orchestrators/rename", api_rename_orchestrator, methods=["POST"]),
            Route("/api/orchestrators/duplicate", api_duplicate_orchestrator, methods=["POST"]),
            Route("/api/sse", api_save_sse, methods=["POST"]),
            Route("/api/sse/delete", api_delete_sse, methods=["POST"]),
            Route("/api/sse/rename", api_rename_sse, methods=["POST"]),
            Route("/api/sse/duplicate", api_duplicate_sse, methods=["POST"]),
            Route("/api/apply", api_apply, methods=["POST"]),
            Route("/api/default", api_default_target, methods=["POST"]),
            Route("/api/probe", api_probe, methods=["POST"]),
            Route("/api/services/status", api_services_status, methods=["GET"]),
            Route("/api/config", api_config, methods=["GET"]),
            Route("/api/config", api_save_config, methods=["POST"]),
            Route("/api/config/diff", api_config_diff, methods=["POST"]),
            Route("/api/wizard", api_wizard, methods=["GET"]),
            Route("/api/update/check", api_update_check, methods=["POST"]),
            Route("/api/update/status", api_update_status, methods=["GET"]),
            Route("/api/update/apply", api_update_apply, methods=["POST"]),
            Route("/api/restart", api_restart, methods=["POST"]),
            Route("/api/restart/result", api_restart_result, methods=["GET"]),
            Route("/api/users", api_users_list, methods=["GET"]),
            Route("/api/users", api_users_save, methods=["POST"]),
            Route("/api/users/delete", api_users_delete, methods=["POST"]),
            Route("/api/users/password", api_users_password, methods=["POST"]),
            Route("/api/tls", api_tls_status, methods=["GET"]),
            Route("/api/tls/upload", api_tls_upload, methods=["POST"]),
            Route("/api/tls/delete", api_tls_delete, methods=["POST"]),
        ]
    )


def main() -> None:
    import uvicorn

    from .__main__ import _load_env_file

    _load_env_file()
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("EC_ADMIN_PORT", "8080"))
    if not _loopback_only(host) and not _has_password_configured():
        raise SystemExit(
            "ERROR: la UI de admin escucha en una IP alcanzable desde la red "
            f"({host}) sin contraseña configurada.\n"
            "Configura EC_ADMIN_PASSWORD en .env (o entra una vez por "
            "127.0.0.1 para fijar la contraseña) y vuelve a arrancar.\n"
            "Alternativa: EC_ADMIN_HOST=127.0.0.1 para acceso solo local."
        )
    tls_enabled = os.environ.get("EC_ADMIN_TLS_ENABLED", "false").lower() == "true"
    cert_file = os.environ.get("EC_ADMIN_TLS_CERT", "")
    key_file = os.environ.get("EC_ADMIN_TLS_KEY", "")
    scheme = "https" if tls_enabled and cert_file and key_file else "http"
    print(f"ec-mcp admin UI on {scheme}://{host}:{port}")
    if scheme == "http" and not _loopback_only(host):
        print(
            "AVISO: la UI de admin es alcanzable desde la red. Asegurate de "
            "usar EC_ADMIN_PASSWORD fuerte y, si es posible, restringir el "
            "acceso por firewall al puerto " + str(port) + "."
        )
    if tls_enabled and not (cert_file and key_file):
        raise SystemExit("ERROR: EC_ADMIN_TLS_ENABLED=true requiere EC_ADMIN_TLS_CERT y EC_ADMIN_TLS_KEY existentes.")
    ssl_kwargs = {}
    if scheme == "https":
        ssl_kwargs = {"ssl_certfile": cert_file, "ssl_keyfile": key_file}
    uvicorn.run(build_admin_app(), host=host, port=port, log_level="warning", **ssl_kwargs)


if __name__ == "__main__":
    main()
