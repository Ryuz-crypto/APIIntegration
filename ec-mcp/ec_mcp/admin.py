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
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

from .admin_config import public_config, update_env
from .admin_page import PAGE
from .web_update import check as check_update
from .web_update import queue_restart, queue_update
from .web_update import status as update_status

SESSIONS: dict[str, float] = {}
SESSION_TTL = 3600.0
LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 60.0


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
    return HTMLResponseMin(PAGE)


async def login_page(request):
    return HTMLResponseMin(PAGE)


async def login_post(request):
    body = await request.json()
    password = str(body.get("password") or "")
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")  # nosec B104
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    failures = [t for t in LOGIN_FAILURES.get(client_ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    if len(failures) >= LOGIN_MAX_FAILURES:
        return JSONResponse(
            {"ok": False, "error": "Demasiados intentos; espera un minuto."},
            status_code=429,
        )
    if not password or not _verify_password(password, allow_first_run=_loopback_only(host)):
        failures.append(now)
        LOGIN_FAILURES[client_ip] = failures
        return JSONResponse({"ok": False})
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
    store = _load_store()
    active = os.environ.get("EC_ORCHESTRATOR_URL", "")
    orchestrators = []
    for name, entry in store["orchestrators"].items():
        orchestrators.append(
            {
                "name": name,
                "url": entry.get("url", ""),
                "verify_tls": entry.get("verify_tls", True),
                "has_api_key": bool(entry.get("api_key")),
                "has_password": bool(entry.get("password")),
                "ssh_user": entry.get("ssh_user", ""),
                "ssh_host": entry.get("ssh_host", ""),
                "has_ssh_password": bool(entry.get("ssh_password")),
                "has_enable_password": bool(entry.get("ssh_enable_password")),
                "active": entry.get("url", "") == active,
            }
        )
    return {
        "orchestrators": orchestrators,
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
    url = str(body.get("url") or "").strip().rstrip("/")
    if not name or not url.startswith("http"):
        return JSONResponse({"ok": False, "error": "name y url son obligatorios"})
    store = _load_store()
    entry = store["orchestrators"].get(name, {})
    entry["url"] = url
    entry["verify_tls"] = bool(body.get("verify_tls", True))
    for field in ("api_key", "username", "password", "ssh_user", "ssh_password", "ssh_enable_password", "ssh_host"):
        value = body.get(field)
        if value:
            entry[field] = str(value)
    if body.get("ssh_user") == "":
        entry.pop("ssh_user", None)
    if body.get("ssh_host") == "":
        entry.pop("ssh_host", None)
    store["orchestrators"][name] = entry
    _save_store(store)
    return JSONResponse({"ok": True, "message": f"Orquestador '{name}' guardado. Usa 'Escribir en .env y activar' para aplicarlo."})


async def api_delete_orchestrator(request):
    if not _check_session(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    body = await request.json()
    name = str(body.get("name") or "")
    store = _load_store()
    if name in store["orchestrators"]:
        del store["orchestrators"][name]
        _save_store(store)
    return JSONResponse({"ok": True, "message": "Eliminado"})


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
    store = _load_store()
    if name and name not in store["orchestrators"]:
        return JSONResponse({"ok": False, "error": f"No existe el orquestador '{name}'"})
    if not name:
        # default: apply currently active or first entry
        entries = list(store["orchestrators"].items())
        if not entries:
            return JSONResponse({"ok": False, "error": "No hay orquestadores guardados"})
        name, _ = entries[0]
    entry = store["orchestrators"][name]
    env_path = Path(os.environ.get("EC_MCP_ENV_FILE", Path.cwd() / ".env"))
    lines = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    wanted = {
        "EC_ORCHESTRATOR_URL": entry.get("url", ""),
        "EC_ORCHESTRATOR_API_KEY": entry.get("api_key", ""),
        "EC_ORCHESTRATOR_USER": entry.get("username", ""),
        "EC_ORCHESTRATOR_PASSWORD": entry.get("password", ""),
        "EC_VERIFY_TLS": str(entry.get("verify_tls", True)).lower(),
        "EC_SSH_ENABLED": "true" if entry.get("ssh_user") else os.environ.get("EC_SSH_ENABLED", "false"),
        "EC_SSH_USER": entry.get("ssh_user", ""),
        "EC_SSH_PASSWORD": entry.get("ssh_password", ""),
        "EC_SSH_ENABLE_PASSWORD": entry.get("ssh_enable_password", ""),
        "EC_SSH_HOST": entry.get("ssh_host", ""),
    }
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
                f"Orquestador '{name}' escrito en {env_path}. Reinicia el servicio para "
                "que el cambio quede persistente. Usa 'Guardar y reiniciar servicios' desde Variables para aplicarlo"
            ),
        }
    )


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
            Route("/api/apply", api_apply, methods=["POST"]),
            Route("/api/config", api_config, methods=["GET"]),
            Route("/api/config", api_save_config, methods=["POST"]),
            Route("/api/update/check", api_update_check, methods=["POST"]),
            Route("/api/update/status", api_update_status, methods=["GET"]),
            Route("/api/update/apply", api_update_apply, methods=["POST"]),
            Route("/api/restart", api_restart, methods=["POST"]),
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
