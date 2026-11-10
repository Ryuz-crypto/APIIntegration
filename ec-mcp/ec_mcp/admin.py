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

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess  # nosec B404 - se usa con argv fijo y binario resuelto
import tempfile
import time
from collections import deque
from math import ceil
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.routing import Route

from . import __version__, admin_users
from .admin_config import diff_env, public_config, restart_tls_errors, update_env
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


def _sessions_path() -> Path:
    return Path(os.environ.get("EC_ADMIN_SESSIONS_FILE") or Path.cwd() / ".ec-admin-sessions.json")


def _load_sessions() -> None:
    global SESSIONS
    try:
        path = _sessions_path()
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                now = time.time()
                SESSIONS = {
                    str(k): v
                    for k, v in data.items()
                    if isinstance(v, dict) and now - float(v.get("ts", 0)) < SESSION_TTL
                }
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        SESSIONS = {}


def _save_sessions() -> None:
    try:
        path = _sessions_path()
        path.write_text(json.dumps(SESSIONS), encoding="utf-8")
        path.chmod(0o600)
    except OSError:
        pass


_load_sessions()

DEBUG_EVENTS: deque = deque(maxlen=500)


def _debug_record(source: str, action: str, target: str, result: str, latency: float = 0.0) -> None:
    DEBUG_EVENTS.append(
        {
            "ts": time.time(),
            "source": source,
            "action": action[:200],
            "target": target[:200],
            "result": result[:200],
            "latency": round(latency, 3),
        }
    )


class _DebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.time()
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        path = request.url.path
        if (path.startswith("/api/") and path not in {"/api/debug/events", "/api/monitor/host"}) or path == "/login":
            _debug_record(
                "panel-api",
                f"{request.method} {path}",
                request.client.host if request.client else "",
                str(response.status_code),
                time.time() - started,
            )
        return response


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
    return Path(os.environ.get("EC_ADMIN_STORE") or Path.cwd() / ".ec-admin.json")


def _backup_dir() -> Path:
    return Path(os.environ.get("EC_ADMIN_BACKUP_DIR") or Path.cwd() / ".ec-admin-backups")


def _latest_backup(directory: Path) -> Path | None:
    entries = sorted(p for p in directory.iterdir() if p.is_dir()) if directory.is_dir() else []
    return entries[-1] if entries else None


def _snapshot_backup(label: str) -> str | None:
    """Copia .env y el registro a .ec-admin-backups/<ts>-<label>/ con meta de cambios."""
    try:
        from datetime import UTC, datetime

        directory = _backup_dir()
        directory.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{ts}-{label}"
        target = directory / name
        if target.exists():
            name = f"{ts}-{label}-{os.getpid()}"
            target = directory / name
        target.mkdir()
        env_file = Path(os.environ.get("EC_MCP_ENV_FILE") or Path.cwd() / ".env")
        store_file = _store_path()
        prev = _latest_backup(directory)
        env_changed: list[str] = []
        registry_changed: list[str] = []
        if prev is not None:
            prev_env = prev / "env"
            prev_reg = prev / "registry.json"
            if env_file.is_file() and prev_env.is_file():
                old = dict(line.split("=", 1) for line in prev_env.read_text(encoding="utf-8").splitlines() if "=" in line)
                new = dict(line.split("=", 1) for line in env_file.read_text(encoding="utf-8").splitlines() if "=" in line)
                env_changed = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
            if store_file.is_file():
                new_r = json.loads(store_file.read_text(encoding="utf-8"))
                new_names = set(new_r.get("orchestrators", {})) | set(new_r.get("sse_platforms", {}))
                if prev_reg.is_file():
                    old_r = json.loads(prev_reg.read_text(encoding="utf-8"))
                    old_names = set(old_r.get("orchestrators", {})) | set(old_r.get("sse_platforms", {}))
                    registry_changed = sorted(old_names ^ new_names) or (["modificado"] if old_r != new_r else [])
                else:
                    registry_changed = sorted(new_names)  # primer backup con registro
            if env_file.is_file() and prev is not None and not prev_env.is_file():
                new = dict(line.split("=", 1) for line in env_file.read_text(encoding="utf-8").splitlines() if "=" in line)
                env_changed = sorted(new)
        if env_file.is_file():
            shutil.copy2(env_file, target / "env")
        if store_file.is_file():
            shutil.copy2(store_file, target / "registry.json")
        (target / "meta.json").write_text(
            json.dumps({"ts": ts, "label": label, "env_changed": env_changed, "registry_changed": registry_changed}, indent=2),
            encoding="utf-8",
        )
        backups = sorted(p for p in directory.iterdir() if p.is_dir())
        for old in backups[:-50]:
            shutil.rmtree(old, ignore_errors=True)
        return name
    except OSError:
        return None


def _restore_backup(name: str) -> dict:
    directory = _backup_dir()
    target = directory / name
    if not name or ".." in name or not target.is_dir():
        raise ValueError("Backup no encontrado")
    env_file = Path(os.environ.get("EC_MCP_ENV_FILE") or Path.cwd() / ".env")
    store_file = _store_path()
    restored = []
    if (target / "env").is_file():
        shutil.copy2(target / "env", env_file)
        restored.append("env")
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.strip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
    if (target / "registry.json").is_file():
        shutil.copy2(target / "registry.json", store_file)
        store_file.chmod(0o600)
        restored.append("registry")
    return {"restored": restored}


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


def _sync_registry_blob() -> None:
    """Espeja el registro en EC_ORCHESTRATORS_JSON / EC_SSE_PLATFORMS_JSON (.env + entorno)."""
    try:
        blob = load_registry().to_env_blob()
        env_path = Path(os.environ.get("EC_MCP_ENV_FILE") or Path.cwd() / ".env")
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
        for key in ("EC_ORCHESTRATORS_JSON", "EC_SSE_PLATFORMS_JSON"):
            value = blob.get(key)
            if value is None:
                lines = [line for line in lines if not line.startswith(key + "=")]
                os.environ.pop(key, None)
                continue
            set_line = f"{key}={value}"
            for i, line in enumerate(lines):
                if line.startswith(key + "="):
                    lines[i] = set_line
                    break
            else:
                lines.append(set_line)
            os.environ[key] = value
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            env_path.chmod(0o600)
        except OSError:
            pass
    except OSError:
        pass


def _admin_password() -> str | None:
    return os.environ.get("EC_ADMIN_PASSWORD") or None


def _password_file() -> Path:
    return Path(os.environ.get("EC_ADMIN_PASSWORD_FILE") or Path.cwd() / ".ec-admin-pass")


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
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("invalid login")
        username = str(body.get("username") or "").strip()
        password = str(body.get("password") or "")
        if len(username) > 64 or len(password) > admin_users.MAX_PASSWORD_LENGTH:
            raise ValueError("invalid login")
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "error": "Solicitud de autenticación inválida."}, status_code=400)
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")  # nosec B104
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    failures = [t for t in LOGIN_FAILURES.get(client_ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    if username and admin_users.has_users():
        role = admin_users.verify_user(username, password) if password else None
        valid = role is not None
        user_label = username
    else:
        # Sin username se usa la contraseña única (retrocompatible aunque exista archivo de usuarios).
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
    _save_sessions()
    response = JSONResponse({"ok": True, "user": user_label, "role": role})
    response.set_cookie("ec_admin_session", token, httponly=True, secure=request.url.scheme == "https" or os.environ.get("EC_ADMIN_TLS_ENABLED", "").lower() == "true", samesite="lax", max_age=int(SESSION_TTL))
    return response


async def logout_post(request):
    token = request.cookies.get("ec_admin_session", "")
    session = SESSIONS.pop(token, None)
    _save_sessions()
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
    try:
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
        _snapshot_backup(f"save-orch:{name}")
        load_registry().save_orchestrator(name, entry)
        _sync_registry_blob()
    except RegistryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)})
    except Exception as exc:  # nunca devolver HTML plano al panel
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
    _audit_panel(session["user"], "save_orchestrator", name, "ok")
    return JSONResponse({"ok": True, "message": f"Orquestador '{name}' guardado (backup creado). Usa 'Aplicar' para activarlo."})

async def api_delete_orchestrator(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    try:
        body = await request.json()
        name = str(body.get("name") or "")
        _snapshot_backup(f"delete-orch:{name}")
        deleted = load_registry().delete_orchestrator(name)
        _sync_registry_blob()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
    _audit_panel(session["user"], "delete_orchestrator", name, "ok" if deleted else "missing")
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminado" if deleted else "No existía"})


async def api_save_sse(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    try:
        body = await request.json()
        name = str(body.get("name") or "").strip()
        entry = {
            "provider": body.get("provider") or "axis",
            "base_url": str(body.get("base_url") or "").strip(),
            "admin_token": body.get("admin_token") or None,
            "verify_tls": body.get("verify_tls", True),
            "timeout": body.get("timeout"),
        }
        _snapshot_backup(f"save-sse:{name}")
        load_registry().save_sse(name, entry)
        _sync_registry_blob()
    except RegistryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
    _audit_panel(session["user"], "save_sse", name, "ok")
    return JSONResponse({"ok": True, "message": f"Plataforma SSE '{name}' guardada (backup creado)."})

async def api_delete_sse(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    try:
        body = await request.json()
        name = str(body.get("name") or "")
        _snapshot_backup(f"delete-sse:{name}")
        deleted = load_registry().delete_sse(name)
        _sync_registry_blob()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
    _audit_panel(session["user"], "delete_sse", name, "ok" if deleted else "missing")
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminada" if deleted else "No existía"})


async def _registry_copy(request, method, label: str):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    try:
        body = await request.json()
        name = str(body.get("name") or "").strip()
        new_name = str(body.get("new_name") or "").strip()
        _snapshot_backup(f"{method.__name__}:{name}->{new_name}")
        method(name, new_name)
        _sync_registry_blob()
    except RegistryError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
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
        _snapshot_backup(f"default:{kind}:{name}")
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
    _snapshot_backup(f"apply:{kind}:{name}")
    # Persistir el registro completo como blobs JSON para el runtime multi-target.
    for key, value in registry.to_env_blob().items():
        wanted[key] = value
    for key in ("EC_DEFAULT_ORCHESTRATOR", "EC_DEFAULT_SSE"):
        if os.environ.get(key, "").strip():
            wanted[key] = os.environ[key]
    env_path = Path(os.environ.get("EC_MCP_ENV_FILE") or Path.cwd() / ".env")
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
        _snapshot_backup("save-config")
        path = update_env(body.get("values") or {}, body.get("clear_secrets") or [])
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status_code=500)
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
    errors = restart_tls_errors()
    if errors:
        _audit_panel(session["user"], "restart", "panel", "blocked_tls")
        return JSONResponse({"state": "error", "error": "; ".join(errors)}, status_code=400)
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
    return Path(os.environ.get("EC_ADMIN_TLS_DIR") or Path.cwd() / ".ec-admin-tls")


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


_PEM_CERT_RE = re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S)
_PEM_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S)
TLS_MAX_BYTES = 3_000_000
TLS_CONFIRMATION = "INSTALAR CERTIFICADO"


def _openssl(args: list[str], data: bytes | None = None) -> bytes:
    binary = shutil.which("openssl")
    if not binary:
        raise ValueError("openssl no está disponible en el servidor")
    try:
        proc = subprocess.run([binary, *args], input=data, capture_output=True, timeout=20)  # noqa: S603 - argv fijo  # nosec B603 B607
    except FileNotFoundError as exc:
        raise ValueError("openssl no está disponible en el servidor") from exc
    if proc.returncode != 0:
        raise ValueError("openssl: " + proc.stderr.decode("utf-8", "replace").strip()[:300])
    return proc.stdout


def _decode_blob(raw: object) -> bytes:
    text = str(raw or "").strip()
    if not text:
        return b""
    if text.startswith("-----BEGIN"):
        return text.encode("utf-8")
    try:
        return base64.b64decode(text, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("El archivo no es PEM ni base64 válido") from exc


def _normalize_tls(mode: str, cert_raw: bytes, key_raw: bytes, password: str) -> tuple[str, str]:
    """Normaliza cualquier formato soportado a (certificado PEM, llave PEM)."""
    if mode == "pfx":
        handle = tempfile.NamedTemporaryFile(suffix=".pfx", delete=False)
        try:
            handle.write(cert_raw)
            handle.close()
            passin = ["-passin", f"pass:{password}"]
            cert_pem = _openssl(["pkcs12", "-in", handle.name, "-clcerts", "-nokeys", *passin]).decode("utf-8", "replace")
            key_pem = _openssl(["pkcs12", "-in", handle.name, "-nocerts", "-nodes", *passin]).decode("utf-8", "replace")
        finally:
            Path(handle.name).unlink(missing_ok=True)
    elif mode == "der":
        cert_pem = _openssl(["x509", "-inform", "der", "-outform", "pem"], cert_raw).decode("utf-8", "replace")
        key_pem = _openssl(["pkey", "-inform", "der", "-outform", "pem"], key_raw).decode("utf-8", "replace") if key_raw else ""
    elif mode == "pem-bundle":
        text = cert_raw.decode("utf-8", "replace")
        certs = _PEM_CERT_RE.findall(text)
        keys = _PEM_KEY_RE.findall(text)
        if not certs or not keys:
            raise ValueError("El bundle PEM debe incluir certificado y llave privada")
        cert_pem, key_pem = certs[0] + "\n", keys[0] + "\n"
    else:
        cert_pem = cert_raw.decode("utf-8", "replace")
        key_pem = key_raw.decode("utf-8", "replace") if key_raw else ""
    if not _PEM_CERT_RE.search(cert_pem):
        raise ValueError("No se encontró un certificado PEM válido")
    return cert_pem, key_pem


def _tls_key_matches(cert_pem: str, key_pem: str) -> bool:
    if not key_pem or not _PEM_KEY_RE.search(key_pem):
        return False
    try:
        cert_pub = _openssl(["x509", "-noout", "-pubkey"], cert_pem.encode("utf-8")).strip()
        key_pub = _openssl(["pkey", "-pubout"], key_pem.encode("utf-8")).strip()
    except ValueError:
        return False
    return cert_pub == key_pub


def _cert_info(path: Path) -> dict:
    try:
        import ssl

        info = ssl._ssl._test_decode_cert(str(path))
        def _dn(name) -> str:
            return ", ".join("=".join(part) for rdn in name for part in rdn)
        return {
            "subject": _dn(info.get("subject", ())),
            "issuer": _dn(info.get("issuer", ())),
            "expires_at": info.get("notAfter", ""),
        }
    except Exception:
        return {}


async def api_tls_status(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    cert_path, key_path = _tls_paths()
    cert_pem = cert_path.read_text(encoding="utf-8") if cert_path.is_file() else ""
    info = _cert_info(cert_path) if cert_path.is_file() else {}
    return JSONResponse(
        {
            "ok": True,
            "enabled": os.environ.get("EC_ADMIN_TLS_ENABLED", "false").lower() == "true",
            "cert": str(cert_path),
            "key": str(key_path),
            "cert_present": bool(cert_pem),
            "key_present": key_path.is_file(),
            "valid": bool(cert_pem) and _cert_fingerprint(cert_pem) is not None,
            "fingerprint": _cert_fingerprint(cert_pem) if cert_pem else None,
            "subject": info.get("subject", ""),
            "issuer": info.get("issuer", ""),
            "expires_at": info.get("expires_at", ""),
        }
    )


async def api_tls_upload(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    mode = str(body.get("mode") or "pem").strip().lower()
    if mode not in {"pem", "pem-bundle", "pfx", "der"}:
        return JSONResponse({"ok": False, "error": "Formato no soportado (pem, pem-bundle, pfx, der)"}, status_code=400)
    confirmation = str(body.get("confirmation") or "")
    if confirmation != TLS_CONFIRMATION:
        return JSONResponse({"ok": False, "error": f"Escribe exactamente: {TLS_CONFIRMATION}"}, status_code=400)
    try:
        cert_raw = _decode_blob(body.get("certificateData") or body.get("cert") or "")
        key_raw = _decode_blob(body.get("keyData") or body.get("key") or "")
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    password = str(body.get("password") or "")
    if not cert_raw:
        return JSONResponse({"ok": False, "error": "Falta el archivo del certificado"}, status_code=400)
    if len(cert_raw) > TLS_MAX_BYTES or len(key_raw) > TLS_MAX_BYTES:
        return JSONResponse({"ok": False, "error": "El archivo excede el límite de 3 MB"}, status_code=400)
    if mode in {"pem", "der"} and not key_raw:
        return JSONResponse({"ok": False, "error": "Falta la llave privada"}, status_code=400)
    try:
        cert_pem, key_pem = _normalize_tls(mode, cert_raw, key_raw, password)
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    if mode in {"pem", "der"} and not _tls_key_matches(cert_pem, key_pem):
        return JSONResponse({"ok": False, "error": "La llave privada no corresponde al certificado"}, status_code=400)
    cert_path, key_path = _tls_paths()
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    if cert_path.is_file():
        shutil.copy2(cert_path, cert_path.with_suffix(".pem.bak"))
        cert_path.with_suffix(".pem.bak").chmod(0o600)
    cert_path.write_text(cert_pem if cert_pem.endswith("\n") else cert_pem + "\n", encoding="utf-8")
    if key_pem:
        key_path.write_text(key_pem if key_pem.endswith("\n") else key_pem + "\n", encoding="utf-8")
    cert_path.chmod(0o600)
    key_path.chmod(0o600)
    try:
        update_env({"EC_ADMIN_TLS_CERT": str(cert_path), "EC_ADMIN_TLS_KEY": str(key_path)})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(
        session["user"], "tls_upload", str(cert_path), "ok",
        {"mode": mode, "fingerprint": _cert_fingerprint(cert_pem), "subject": _cert_info(cert_path).get("subject", "")},
    )
    return JSONResponse(
        {
            "ok": True,
            "message": f"Certificado instalado en {cert_path} (0600; el anterior quedó en cert.pem.bak). Activa EC_ADMIN_TLS_ENABLED=true y reinicia el panel para servir HTTPS.",
            "mode": mode,
            "fingerprint": _cert_fingerprint(cert_pem),
            "subject": _cert_info(cert_path).get("subject", ""),
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


_TOOLS_CACHE: list | None = None


TOOL_DESC_ES = {
    "list_appliances": "Inventario real del Orchestrator: nePk, nombre, IP, modelo, versión y estado de cada appliance. Úsala siempre primero.",
    "orchestrator_info": "Información general del Orchestrator (versión, licencias, salud).",
    "list_orchestrator_targets_tool": "Lista los Orchestrators configurados (multi-target) para usarlos como parámetro 'target'.",
    "list_sse_targets_tool": "Lista las plataformas SSE (Axis) configuradas.",
    "run_show_api": "Ejecuta un comando 'show ...' de ECOS por API del Orchestrator (o SSH si está habilitado). Solo lectura.",
    "run_api_operation": "Ejecuta cualquier operación de la API del Orchestrator por su operation ID (usa list_api_operations para buscarla).",
    "list_api_operations": "Busca operaciones de la API del Orchestrator por texto (search=...).",
    "get_appliance_health": "Salud por appliance: CPU, memoria, disco, temperatura, alarmas y estado.",
    "orchestrator_metrics": "Métricas del Orchestrator (throughput, túneles, sesiones).",
    "get_firmware_compliance": "Cumplimiento de firmware de los appliances frente al Orchestrator.",
    "apply_change": "Aplica un cambio de configuración vía API. Por defecto dry-run: devuelve exactamente qué se ejecutaría; con confirm=true y escrituras habilitadas lo aplica.",
    "apply_overlay_plan": "Aplica un plan BIO/overlay preparado (clon). Requiere confirmación escrita.",
    "prepare_ztp_adoption": "Prepara la adopción ZTP de un appliance (solo lectura; nunca escribe).",
    "apply_ztp_plan": "Aplica un plan ZTP preparado con confirmación escrita y verificación posterior.",
    "ask_sdwan_ai": "Pregunta en lenguaje natural al asistente SD-WAN AI (SASE Copilot) del Orchestrator.",
    "axis_health": "Salud en vivo de una plataforma Axis Security (SSE).",
    "axis_commit": "Publica en Axis todos los cambios pendientes (sin confirm=true solo muestra el preview).",
    "axis_list_applications": "Lista aplicaciones (Tags) de Axis Security.",
    "axis_create_application": "Crea una aplicación en Axis. Dry-run por defecto; requiere confirm=true para aplicar.",
    "axis_update_application": "Actualiza una aplicación de Axis. Dry-run por defecto.",
    "axis_delete_application": "Elimina una aplicación de Axis. Dry-run por defecto.",
    "axis_create_connector": "Crea un conector de Axis; la respuesta trae el comando de instalación.",
    "axis_connector_status": "Estado del conector Axis: red, memoria, disco, CPU y salud.",
    "security_scan": "Escaneo de seguridad del Orchestrator/appliances (solo lectura).",
    "telemetry_flows": "Flujos de tráfico recientes entre appliances.",
    "get_alarm_history": "Historial de alarmas del Orchestrator.",
    "dashboard_install": "Instala y publica el dashboard web local.",
    "web_update_check": "Comprueba si hay una actualización nueva en GitHub (rama configurada).",
    "wizard_probe": "Prueba la conexión real con un target guardado (Orchestrator o SSE).",
}


PANEL_TOOLS = {"dashboard_install", "web_update_check", "web_update_apply", "admin_probe", "admin_restart"}


def _tool_domain(name: str) -> str:
    if name.startswith("axis_") or name.startswith("sse_"):
        return "sse"
    if name in PANEL_TOOLS:
        return "panel"
    return "sdwan"


def _mcp_tools() -> list:
    global _TOOLS_CACHE
    if _TOOLS_CACHE is None:
        from . import server as _server

        mcp = _server.create_server()
        tool_manager = getattr(mcp, "_tool_manager", None)
        tools = list(tool_manager.list_tools()) if tool_manager is not None else []
        _TOOLS_CACHE = sorted(
            (
                {
                    "name": t.name,
                    "description": (t.description or "").strip().splitlines()[0][:200],
                    "description_es": TOOL_DESC_ES.get(t.name, ""),
                    "domain": _tool_domain(t.name),
                }
                for t in tools
            ),
            key=lambda item: item["name"],
        )
    return _TOOLS_CACHE


def _disabled_tools() -> set[str]:
    return {name.strip() for name in os.environ.get("EC_MCP_DISABLED_TOOLS", "").split(",") if name.strip()}


async def api_tools_list(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    disabled = _disabled_tools()
    tools = _mcp_tools()
    domains = {}
    for t in tools:
        domains[t["domain"]] = domains.get(t["domain"], 0) + 1
    return JSONResponse(
        {
            "ok": True,
            "total": len(tools),
            "disabled": sorted(disabled),
            "domains": domains,
            "tools": [
                {"name": t["name"], "description": t["description"], "description_es": t.get("description_es", ""), "domain": t["domain"], "disabled": t["name"] in disabled}
                for t in tools
            ],
        }
    )


async def api_tools_toggle(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    body = await request.json()
    name = str(body.get("name") or "").strip()
    enabled = bool(body.get("enabled"))
    if name not in {t["name"] for t in _mcp_tools()}:
        return JSONResponse({"ok": False, "error": f"Tool desconocida: {name}"}, status_code=404)
    disabled = _disabled_tools()
    if enabled:
        disabled.discard(name)
    else:
        disabled.add(name)
    try:
        update_env({"EC_MCP_DISABLED_TOOLS": ",".join(sorted(disabled))})
    except ValueError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "tool_toggle", name, "enabled" if enabled else "disabled")
    return JSONResponse({"ok": True, "name": name, "enabled": enabled, "disabled": sorted(disabled)})


AGENT_PROMPT_HEADER = """# ec-mcp — sugerencia para AI Agent (skill)

Eres un agente operando **ec-mcp**, un servidor MCP para HPE Aruba EdgeConnect SD-WAN.
Reglas de oro:
1. Descubre primero: `list_orchestrator_targets_tool`, `list_appliances` (necesitas el nePk), `orchestrator_info`.
2. Multi-target: pasa `target="<nombre>"` en las tools que lo aceptan; sin `target` se usa el default del panel.
3. Las escrituras están DESACTIVADAS por defecto (`EC_ALLOW_WRITE_TOOLS=false`) y siempre con dry-run/preview + confirmación explícita; nunca fuerces escrituras peligrosas.
4. SSH es opcional y está off por defecto; la API del Orchestrator es la ruta principal (`run_api_operation`, `run_show_api`).
5. ZTP/BIO son transaccionales: prepara → preview → confirma con texto exacto → verifica → rollback si falla.
6. SSE (Axis Security): usa `axis_health` y las tools `axis_*` con `target` de plataforma SSE; recuerda `axis_commit` para publicar.
7. Respeta los límites de salida y el audit log; nunca imprimas secretos.
8. Si un llamado falla, lee el mensaje de error: suele indicar el parámetro exacto que falta.

Consulta también la documentación completa en `ec-mcp/README.md` (125 tools) y los skills de `ec-mcp/docs/` reproducidos abajo.
"""


def _agent_prompt() -> str:
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    parts = [AGENT_PROMPT_HEADER]
    parts.append(f"\n- Versión: {__version__}\n- Tools totales: {len(_mcp_tools())}\n- Tools desactivadas: {len(_disabled_tools())}\n")
    for fname in ("EDGECONNECT_NOC_OPS_SKILL.md", "AI_AGENT_SKILL_RECOMMENDATIONS.md", "EDGECONNECT_EXPERT_SKILL.md"):
        path = docs_dir / fname
        if path.is_file():
            parts.append(f"\n---\n\n## {fname}\n\n" + path.read_text(encoding="utf-8"))
    return "\n".join(parts)


async def api_agent_prompt(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    prompt = _agent_prompt()
    return JSONResponse(
        {
            "ok": True,
            "prompt": prompt,
            "chars": len(prompt),
            "tools_total": len(_mcp_tools()),
            "disabled_tools": sorted(_disabled_tools()),
        }
    )


def _audit_tail(limit: int) -> list[dict]:
    path = Settings.from_env().audit_log_path
    entries: list[dict] = []
    if path.is_file():
        try:
            with path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                start = max(0, size - 8 * 1024 * 1024)
                stream.seek(start)
                tail = stream.read(8 * 1024 * 1024)
            lines = tail.decode("utf-8", "replace").splitlines()
            if start and lines:
                lines = lines[1:]  # first line may be incomplete
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
        except OSError:
            pass
    return entries[-limit:]


def _debug_events_payload(limit: int, query: str = "", source: str = "") -> list[dict]:
    from datetime import UTC, datetime

    events: list[dict] = []
    for e in DEBUG_EVENTS:
        events.append(
            {
                "ts": e["ts"],
                "ts_iso": datetime.fromtimestamp(e["ts"], UTC).isoformat(),
                "source": e["source"],
                "action": e["action"],
                "target": e["target"],
                "result": e["result"],
                "latency": e["latency"],
            }
        )
    for a in _audit_tail(2000):
        ts_raw = a.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            ts = 0.0
        events.append(
            {
                "ts": ts,
                "ts_iso": ts_raw,
                "source": "panel-audit" if a.get("tool") == "admin_panel" else "mcp-tool",
                "action": str(a.get("action", "")),
                "target": str(a.get("target", "")),
                "result": str(a.get("result", "")),
                "latency": None,
                "tool": str(a.get("tool", "")),
                "user": str(a.get("user", "")),
            }
        )
    if query:
        events = [e for e in events if query in json.dumps(e).lower()]
    if source:
        events = [e for e in events if e["source"] == source]
    events.sort(key=lambda e: e["ts"], reverse=True)
    return events[:limit]


async def api_host_monitor(request):
    _session, denied = _authorize(request, "users")
    if denied:
        return denied
    from .system_monitor import host_snapshot

    snapshot = host_snapshot(Settings.from_env().audit_log_path)
    events = _debug_events_payload(500, source="mcp-tool")
    now = time.time()
    snapshot["activity"] = {
        "observed_audit_events_last_minute": sum(1 for event in events if 0 <= now - event["ts"] <= 60),
        "scope": "last 500 audit events visible in bounded log tail; not concurrent requests",
        "concurrent_requests": None,
    }
    return JSONResponse(snapshot)


async def api_audit_report(request):
    session, denied = _authorize(request, "users")
    if denied:
        return denied
    from .audit_reports import csv_report, pdf_report, xlsx_report

    fmt = request.query_params.get("format", "csv").lower()
    formats = {
        "csv": (csv_report, "text/csv; charset=utf-8", "csv"),
        "xlsx": (xlsx_report, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
        "pdf": (pdf_report, "application/pdf", "pdf"),
    }
    if fmt not in formats:
        return JSONResponse({"error": "Formato no admitido."}, status_code=400)
    events = _debug_events_payload(500)
    build, media_type, extension = formats[fmt]
    body = build(events)
    _audit_panel(session["user"], "audit_report_export", "panel", "ok", {"format": fmt, "events": len(events)})
    return Response(body, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="ec-mcp-auditoria.{extension}"',
        "Cache-Control": "no-store",
    })


async def api_debug_events(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    params = request.query_params
    try:
        limit = min(max(int(params.get("limit") or 200), 1), 500)
    except ValueError:
        limit = 200
    events = _debug_events_payload(limit, (params.get("q") or "").strip().lower(), (params.get("source") or "").strip())
    return JSONResponse({"ok": True, "events": events, "buffer": len(DEBUG_EVENTS)})


async def api_debug_export(request):
    session, denied = _authorize(request, "read")
    if denied:
        return denied
    from datetime import UTC, datetime

    fmt = (request.query_params.get("format") or "jsonl").lower()
    events = _debug_events_payload(5000)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if fmt == "csv":
        import csv
        import io

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["ts", "source", "tool", "action", "target", "result", "latency_s", "user"])
        for e in events:
            writer.writerow(
                [e["ts_iso"], e["source"], e.get("tool", ""), e["action"], e["target"], e["result"], e["latency"], e.get("user", "")]
            )
        body = out.getvalue()
        media = "text/csv"
        filename = f"ec-mcp-debug-{stamp}.csv"
    else:
        body = "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n"
        media = "application/x-ndjson"
        filename = f"ec-mcp-debug-{stamp}.jsonl"
    _audit_panel(session["user"], "debug_export", filename, "ok", {"events": len(events), "format": fmt})
    return Response(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def api_debug_clear(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    path = Settings.from_env().audit_log_path
    size_before = path.stat().st_size if path.is_file() else 0
    _audit_panel(session["user"], "debug_clear", str(path), "ok", {"bytes_before": size_before})
    _debug_record("panel-api", "debug_clear", str(path), f"truncated {size_before}B")
    removed: list[str] = []
    if path.is_file():
        path.write_text("", encoding="utf-8")
        removed.append(str(path))
    for old in path.parent.glob(path.name + ".*"):
        if old.is_file() and old.suffix in {".old", ".bak", ".1"}:
            old.unlink(missing_ok=True)
            removed.append(str(old))
    DEBUG_EVENTS.clear()
    return JSONResponse(
        {
            "ok": True,
            "removed": removed,
            "bytes_before": size_before,
            "message": f"Logs limpiados ({size_before} bytes liberados del audit log y búfer vaciado).",
        }
    )


async def api_backups_list(request):
    _session, denied = _authorize(request, "read")
    if denied:
        return denied
    directory = _backup_dir()
    items = []
    if directory.is_dir():
        for entry in sorted((p for p in directory.iterdir() if p.is_dir()), reverse=True):
            meta = {}
            meta_file = entry / "meta.json"
            if meta_file.is_file():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    meta = {}
            items.append(
                {
                    "name": entry.name,
                    "ts": meta.get("ts", entry.name),
                    "label": meta.get("label", ""),
                    "env_changed": meta.get("env_changed", []),
                    "registry_changed": meta.get("registry_changed", []),
                    "has_env": (entry / "env").is_file(),
                    "has_registry": (entry / "registry.json").is_file(),
                }
            )
    return JSONResponse({"ok": True, "dir": str(directory), "backups": items})


async def api_backups_create(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    name = _snapshot_backup("manual")
    if not name:
        return JSONResponse({"ok": False, "error": "No se pudo crear el backup"}, status_code=500)
    _audit_panel(session["user"], "backup_create", name, "ok")
    return JSONResponse({"ok": True, "name": name, "message": f"Backup '{name}' creado."})


async def api_backups_restore(request):
    session, denied = _authorize(request, "write")
    if denied:
        return denied
    try:
        body = await request.json()
        name = str(body.get("name") or "").strip()
        _snapshot_backup(f"pre-restore:{name}")
        result = _restore_backup(name)
    except (ValueError, OSError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    _audit_panel(session["user"], "backup_restore", name, "ok", result)
    return JSONResponse({"ok": True, "restored": result["restored"], "message": f"Rollback aplicado desde '{name}'. Reinicia los servicios para aplicar .env."})


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




def HTMLResponseMin(content: str) -> Response:
    return Response(content, media_type="text/html")


def build_admin_app() -> Starlette:
    return Starlette(
        middleware=[Middleware(_DebugMiddleware)],
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
            Route("/api/tools", api_tools_list, methods=["GET"]),
            Route("/api/tools/toggle", api_tools_toggle, methods=["POST"]),
            Route("/api/agent-prompt", api_agent_prompt, methods=["GET"]),
            Route("/api/monitor/host", api_host_monitor, methods=["GET"]),
            Route("/api/audit/report", api_audit_report, methods=["GET"]),
            Route("/api/debug/events", api_debug_events, methods=["GET"]),
            Route("/api/debug/export", api_debug_export, methods=["GET"]),
            Route("/api/debug/clear", api_debug_clear, methods=["POST"]),
            Route("/api/backups", api_backups_list, methods=["GET"]),
            Route("/api/backups/create", api_backups_create, methods=["POST"]),
            Route("/api/backups/restore", api_backups_restore, methods=["POST"]),
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
