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
  POST /api/apply   write selected orchestrator into .env and restart hint
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

from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from . import __version__
from .admin_config import public_config, update_env
from .admin_page import PAGE as _PAGE_TEMPLATE
from .admin_services import services_status
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

SESSIONS: dict[str, float] = {}
SESSION_TTL = 3600.0
LOGIN_FAILURES: dict[str, list[float]] = {}


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


def _check_session(request) -> bool:
    token = request.cookies.get("ec_admin_session", "")
    now = time.time()
    if token and token in SESSIONS and now - SESSIONS[token] < SESSION_TTL:
        SESSIONS[token] = now
        return True
    return False


async def home(request):
    if not _check_session(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponseMin(_render_page())


async def login_page(request):
    return HTMLResponseMin(_render_page())


async def login_post(request):
    body = await request.json()
    password = str(body.get("password") or "")
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")  # nosec B104
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    failures = [t for t in LOGIN_FAILURES.get(client_ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    valid = bool(password) and _verify_password(password, allow_first_run=_loopback_only(host))
    if valid:
        LOGIN_FAILURES.pop(client_ip, None)
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
        return JSONResponse(
            {
                "ok": False,
                "error": f"Contraseña incorrecta. Intentos restantes: {remaining}.",
                "remaining_attempts": remaining,
            },
        )
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = time.time()
    response = JSONResponse({"ok": True})
    response.set_cookie("ec_admin_session", token, httponly=True, samesite="lax", max_age=int(SESSION_TTL))
    return response


async def logout_post(request):
    token = request.cookies.get("ec_admin_session", "")
    SESSIONS.pop(token, None)
    response = JSONResponse({"ok": True})
    response.delete_cookie("ec_admin_session")
    return response


def _public_state() -> dict:
    registry = load_registry()
    active = os.environ.get("EC_ORCHESTRATOR_URL", "")
    orchestrators = []
    for name, entry in registry.list_orchestrators().items():
        item = public_orchestrator(name, entry)
        item["active"] = bool(active) and entry.get("url", "") == active
        orchestrators.append(item)
    sse_platforms = []
    for name, entry in registry.list_sse().items():
        item = public_sse(name, entry)
        if name == "default":
            item["active"] = os.environ.get("EC_AXIS_ENABLED", "false").lower() == "true"
        else:
            item["active"] = False
        sse_platforms.append(item)
    return {
        "orchestrators": orchestrators,
        "sse_platforms": sse_platforms,
        "ssh_enabled": os.environ.get("EC_SSH_ENABLED", "false").lower() == "true",
    }


async def api_state(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(_public_state())


async def api_save_orchestrator(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
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
    return JSONResponse({"ok": True, "message": f"Orquestador '{name}' guardado. Usa 'Aplicar' para activarlo."})


async def api_delete_orchestrator(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    name = str(body.get("name") or "")
    deleted = load_registry().delete_orchestrator(name)
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminado" if deleted else "No existía"})


async def api_save_sse(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
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
    return JSONResponse({"ok": True, "message": f"Plataforma SSE '{name}' guardada."})


async def api_delete_sse(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    name = str(body.get("name") or "")
    deleted = load_registry().delete_sse(name)
    return JSONResponse({"ok": True, "deleted": deleted, "message": "Eliminada" if deleted else "No existía"})


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
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
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
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(services_status(probe=True))


async def api_config(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(public_config())


async def api_save_config(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        path = update_env(body.get("values") or {}, body.get("clear_secrets") or [])
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)
    return JSONResponse(
        {
            "ok": True,
            "message": f"Variables guardadas de forma atómica en {path}. Reinicia los servicios para aplicarlas.",
            "restart_required": True,
        }
    )


async def api_update_check(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        return JSONResponse(check_update())
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


async def api_update_status(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(update_status())


async def api_update_apply(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        body = await request.json()
        result = queue_update(str(body.get("remote_sha") or ""), str(body.get("confirmation") or ""))
    except (OSError, TypeError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(result)


async def api_restart(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        return JSONResponse(queue_restart())
    except (OSError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)


async def api_restart_result(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    state = update_status()
    state.setdefault("state", "idle")
    state["request_pending"] = check_pending_request()
    return JSONResponse(state)


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
            Route("/api/sse", api_save_sse, methods=["POST"]),
            Route("/api/sse/delete", api_delete_sse, methods=["POST"]),
            Route("/api/apply", api_apply, methods=["POST"]),
            Route("/api/services/status", api_services_status, methods=["GET"]),
            Route("/api/config", api_config, methods=["GET"]),
            Route("/api/config", api_save_config, methods=["POST"]),
            Route("/api/update/check", api_update_check, methods=["POST"]),
            Route("/api/update/status", api_update_status, methods=["GET"]),
            Route("/api/update/apply", api_update_apply, methods=["POST"]),
            Route("/api/restart", api_restart, methods=["POST"]),
            Route("/api/restart/result", api_restart_result, methods=["GET"]),
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
    print(f"ec-mcp admin UI on http://{host}:{port}")
    if not _loopback_only(host):
        print(
            "AVISO: la UI de admin es alcanzable desde la red. Asegurate de "
            "usar EC_ADMIN_PASSWORD fuerte y, si es posible, restringir el "
            "acceso por firewall al puerto " + str(port) + "."
        )
    uvicorn.run(build_admin_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
