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

SESSIONS: dict[str, float] = {}
SESSION_TTL = 3600.0
LOGIN_FAILURES: dict[str, list[float]] = {}
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 60.0

PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>ec-mcp admin</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;display:flex;justify-content:center;padding:40px 16px}
 .card{background:#1e293b;border-radius:12px;padding:28px;max-width:760px;width:100%;box-shadow:0 10px 30px rgba(0,0,0,.4)}
 h1{font-size:1.3rem;margin:0 0 4px} h2{font-size:1rem;margin:24px 0 8px;color:#94a3b8}
 input,select{width:100%;padding:9px 11px;margin:4px 0 12px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;box-sizing:border-box}
 button{padding:10px 16px;border-radius:8px;border:0;background:#2563eb;color:#fff;font-weight:600;cursor:pointer}
 button.sec{background:#475569} button:disabled{opacity:.5}
 .msg{margin:10px 0;padding:10px 12px;border-radius:8px;font-size:.9rem}
 .ok{background:#052e16;border:1px solid #166534} .err{background:#3f1d1d;border:1px solid #7f1d1d}
 .orch{border:1px solid #334155;border-radius:10px;padding:14px;margin:10px 0}
 .row{display:flex;gap:10px} .row>div{flex:1}
 table{width:100%;border-collapse:collapse;font-size:.9rem}
 td,th{padding:6px 8px;border-bottom:1px solid #334155;text-align:left}
 .tag{display:inline-block;padding:2px 8px;border-radius:99px;font-size:.75rem;background:#334155}
 .active{background:#166534}
</style></head><body><div class="card" id="app">Cargando...</div>
<script>
let AUTHED=false;
const $=q=>document.querySelector(q);
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 if(r.redirected&&r.url.includes('/login')){AUTHED=false;render();return null;} return r.json();}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function render(){
 const app=$('#app');
 if(!AUTHED){app.innerHTML=`<h1>ec-mcp admin</h1><h2>Contraseña de administrador</h2>
  <input type="password" id="pw" placeholder="EC_ADMIN_PASSWORD" onkeydown="if(event.key==='Enter')login()">
  <button onclick="login()">Entrar</button><div id="msg"></div>`;return;}
 app.innerHTML=`<h1>ec-mcp admin</h1><span class="tag">multiorquestador</span>
 <h2>Orquestadores</h2><div id="list"></div>
 <h2>Agregar / actualizar orquestador</h2>
 <div class="row"><div><label>Nombre</label><input id="n_name" placeholder="lab-useast1"></div>
 <div><label>URL</label><input id="n_url" placeholder="https://orchestrator.example.com"></div></div>
 <div class="row"><div><label>API key (X-Auth-Token)</label><input id="n_key" type="password"></div>
 <div><label>Usuario (alternativo)</label><input id="n_user"></div></div>
 <div class="row"><div><label>Password usuario</label><input id="n_pass" type="password"></div>
 <div><label>Verificar TLS</label><select id="n_tls"><option>true</option><option>false</option></select></div></div>
 <h2>SSH común (appliance)</h2>
 <div class="row"><div><label>Usuario SSH</label><input id="n_sshuser"></div>
 <div><label>Password SSH</label><input id="n_sshpass" type="password"></div></div>
 <div class="row"><div><label>Password enable</label><input id="n_enable" type="password"></div>
 <div><label>Host por defecto (opcional)</label><input id="n_sshhost"></div></div>
 <button onclick="save()">Guardar orquestador</button>
 <h2>Acción</h2>
 <button onclick="apply()">Escribir en .env y activar</button>
 <button class="sec" onclick="logout()">Salir</button>
 <div id="msg"></div>`;
 refresh();
}
async function login(){const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#pw').value})});
 const j=await r.json(); if(j.ok){AUTHED=true;render();}else{$('#msg').innerHTML='<div class="msg err">Contraseña incorrecta</div>';}}
async function logout(){await api('/logout');AUTHED=false;render();}
async function refresh(){const s=await api('/api/state'); if(!s)return;
 $('#list').innerHTML=s.orchestrators.map(o=>`<div class="orch">
  <b>${esc(o.name)}</b> ${o.active?'<span class="tag active">activo</span>':''}<br>
  <small>${esc(o.url)}</small>
  <button class="sec" style="float:right;margin-left:8px" onclick="del('${esc(o.name)}')">Eliminar</button>
  <button class="sec" style="float:right" onclick="edit('${esc(o.name)}')">Editar</button></div>`).join('')||'<small>Ninguno registrado</small>';}
function edit(name){const s=stateCache[name]; if(!s)return;
 $('#n_name').value=name; $('#n_url').value=s.url||''; $('#n_tls').value=String(s.verify_tls??true);
 $('#n_sshuser').value=s.ssh_user||''; $('#n_sshhost').value=s.ssh_host||'';}
let stateCache={};
const _refresh=refresh;
refresh=async()=>{const s=await api('/api/state'); if(!s)return; stateCache={};
 s.orchestrators.forEach(o=>stateCache[o.name]=o); _refresh.__patched||null;
 $('#list').innerHTML=(s.orchestrators.map(o=>`<div class="orch">
  <b>${esc(o.name)}</b> ${o.active?'<span class="tag active">activo</span>':''}<br>
  <small>${esc(o.url)}</small>
  <button class="sec" style="float:right;margin-left:8px" onclick="del('${esc(o.name)}')">Eliminar</button>
  <button class="sec" style="float:right" onclick="edit('${esc(o.name)}')">Editar</button></div>`).join(''))||'<small>Ninguno registrado</small>';};
async function save(){const body={name:$('#n_name').value.trim(),url:$('#n_url').value.trim(),
 api_key:$('#n_key').value,username:$('#n_user').value,password:$('#n_pass').value,
 verify_tls:$('#n_tls').value==='true',ssh_user:$('#n_sshuser').value,ssh_password:$('#n_sshpass').value,
 ssh_enable_password:$('#n_enable').value,ssh_host:$('#n_sshhost').value};
 const j=await api('/api/orchestrators',body); msg(j);}
async function del(name){if(!confirm('Eliminar '+name+'?'))return; const j=await api('/api/orchestrators/delete',{name}); msg(j); refresh();}
async function apply(){const name=$('#n_name').value.trim()||undefined; const j=await api('/api/apply',{name}); msg(j);}
function msg(j){$('#msg').innerHTML=j?(j.ok?'<div class="msg ok">'+esc(j.message)+'</div>':'<div class="msg err">'+esc(j.error||j.message)+'</div>'):'';}
render();
</script></body></html>"""


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
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")
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
    "password": "EC_ORCHESTRATOR_PASSWORD",
    "verify_tls": "EC_VERIFY_TLS",
    "ssh_user": "EC_SSH_USER",
    "ssh_password": "EC_SSH_PASSWORD",
    "ssh_enable_password": "EC_SSH_ENABLE_PASSWORD",
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
                "que las tools vean el cambio: sudo systemctl restart ec-mcp"
            ),
        }
    )


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
        ]
    )


def main() -> None:
    import uvicorn

    from .__main__ import _load_env_file

    _load_env_file()
    host = os.environ.get("EC_ADMIN_HOST", "0.0.0.0")
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
