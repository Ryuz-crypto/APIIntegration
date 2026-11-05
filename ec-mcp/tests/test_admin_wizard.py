"""Tests for the admin wizard, config diff, per-target ops and multi-user panel."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ec_mcp import admin, admin_config, admin_users
from ec_mcp.admin import build_admin_app
from ec_mcp.admin_page import PAGE
from ec_mcp.multi_target import RegistryError, TargetRegistry, resolve_default_name


@pytest.fixture()
def env(tmp_path: Path, monkeypatch):
    for key in [*admin_config.BY_KEY, "EC_ORCHESTRATORS_JSON", "EC_SSE_PLATFORMS_JSON"]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EC_ADMIN_STORE", str(tmp_path / "reg.json"))
    monkeypatch.setenv("EC_ADMIN_USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setenv("EC_MCP_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("EC_MCP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EC_ADMIN_TLS_DIR", str(tmp_path / ".ec-admin-tls"))
    (tmp_path / ".env").write_text("EC_MCP_PORT=8000\n", encoding="utf-8")
    admin.SESSIONS.clear()
    admin.LOGIN_FAILURES.clear()
    monkeypatch.setattr(admin, "_verify_password", lambda candidate, allow_first_run=True: candidate == "pw")
    return tmp_path


@pytest.fixture()
def client(env):
    c = TestClient(build_admin_app())
    assert c.post("/login", json={"password": "pw"}).json()["ok"] is True
    return c


def test_public_config_exposes_wizard_metadata(env):
    config = admin_config.public_config(env / ".env")
    by_key = {f["key"]: f for f in config["fields"]}
    assert by_key["EC_ORCHESTRATOR_URL"]["required"] is True
    assert by_key["EC_ORCHESTRATOR_URL"]["step"] == "orchestrator"
    assert by_key["EC_SSH_USER"]["depends_on"] == ["EC_SSH_ENABLED", "true"]
    assert by_key["EC_AXIS_ADMIN_TOKEN"]["depends_on"] == ["EC_AXIS_ENABLED", "true"]
    assert by_key["EC_DASHBOARD_REMOTE_HOST"]["depends_on"] == ["EC_DASHBOARD_REMOTE_ENABLED", "true"]
    assert [s["id"] for s in config["steps"]] == [
        "orchestrator", "ssh", "sse", "targets", "security", "transport", "panel", "updates", "dashboard",
    ]


def test_diff_env_previews_without_writing_and_reports_cross_field_errors(env):
    path = env / ".env"
    result = admin_config.diff_env({"EC_MCP_PORT": "9000"}, path=path)
    assert result["ok"] is True
    assert result["changes"] == [
        {"key": "EC_MCP_PORT", "old": "8000", "new": "9000", "secret": False, "cleared": False}
    ]
    assert "EC_MCP_PORT=8000" in path.read_text(encoding="utf-8")

    bad = admin_config.diff_env({"EC_ORCHESTRATOR_URL": "https://orch.example.com"}, path=path)
    assert bad["ok"] is False
    assert any("EC_ORCHESTRATOR_API_KEY" in error for error in bad["errors"])

    ok = admin_config.diff_env(
        {"EC_ORCHESTRATOR_URL": "https://orch.example.com", "EC_ORCHESTRATOR_API_KEY": "k"}, path=path
    )
    assert ok["ok"] is True
    secret_change = next(c for c in ok["changes"] if c["key"] == "EC_ORCHESTRATOR_API_KEY")
    assert secret_change["old"] == "***" and secret_change["new"] == "***" and secret_change["secret"] is True


def test_update_env_enforces_cross_field_rules(env):
    path = env / ".env"
    with pytest.raises(ValueError, match="EC_ORCHESTRATOR_API_KEY"):
        admin_config.update_env({"EC_ORCHESTRATOR_URL": "https://orch.example.com"}, path=path)
    admin_config.update_env(
        {"EC_ORCHESTRATOR_URL": "https://orch.example.com", "EC_ORCHESTRATOR_API_KEY": "k"}, path=path
    )
    with pytest.raises(ValueError, match="EC_AXIS_ADMIN_TOKEN"):
        admin_config.update_env({"EC_AXIS_ENABLED": "true"}, path=path)


def test_config_diff_endpoint(client, env):
    ok = client.post("/api/config/diff", json={"values": {"EC_MCP_PORT": "9000"}})
    assert ok.status_code == 200
    assert ok.json()["changes"][0]["key"] == "EC_MCP_PORT"
    bad = client.post("/api/config/diff", json={"values": {"EC_ORCHESTRATOR_URL": "https://x.example.com"}})
    assert bad.status_code == 400
    assert bad.json()["ok"] is False
    assert client.post("/api/config/diff", json={"values": {"EC_NOPE": "1"}}).status_code == 400
    unauth = TestClient(build_admin_app())
    assert unauth.post("/api/config/diff", json={"values": {}}).status_code == 401


def test_wizard_endpoint_returns_steps_fields_and_state(client):
    r = client.get("/api/wizard")
    assert r.status_code == 200
    data = r.json()
    assert [s["id"] for s in data["steps"]] == [
        "orchestrator", "ssh", "sse", "targets", "security", "transport", "panel", "updates", "dashboard",
    ]
    by_key = {f["key"]: f for f in data["fields"]}
    assert by_key["EC_ORCHESTRATOR_URL"]["required"] is True
    assert "session" in data["state"]


def test_registry_rename_and_duplicate(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EC_ADMIN_STORE", str(tmp_path / "reg.json"))
    registry = TargetRegistry(tmp_path / "reg.json")
    registry.save_orchestrator("prod", {"url": "https://p.example.com", "api_key": "k"})
    registry.save_sse("axis", {"base_url": "https://a.example.com", "admin_token": "t"})
    registry.duplicate_orchestrator("prod", "lab")
    registry.rename_orchestrator("lab", "dr")
    assert set(registry.list_orchestrators()) == {"prod", "dr"}
    assert registry.get_orchestrator("dr")["api_key"] == "k"
    registry.duplicate_sse("axis", "axis-dr")
    registry.rename_sse("axis-dr", "axis2")
    assert set(registry.list_sse()) == {"axis", "axis2"}
    with pytest.raises(RegistryError):
        registry.rename_orchestrator("prod", "dr")
    with pytest.raises(RegistryError):
        registry.duplicate_sse("axis", "axis")
    with pytest.raises(RegistryError):
        registry.rename_orchestrator("missing", "x")


def test_rename_duplicate_endpoints(client):
    client.post("/api/orchestrators", json={"name": "prod", "url": "https://p.example.com", "api_key": "k"})
    assert client.post("/api/orchestrators/duplicate", json={"name": "prod", "new_name": "lab"}).json()["ok"]
    r = client.post("/api/orchestrators/rename", json={"name": "lab", "new_name": "dr"})
    assert r.json()["ok"] is True
    assert client.post("/api/orchestrators/rename", json={"name": "prod", "new_name": "dr"}).status_code == 400
    client.post("/api/sse", json={"name": "axis", "base_url": "https://a.example.com", "admin_token": "t"})
    assert client.post("/api/sse/duplicate", json={"name": "axis", "new_name": "axis2"}).json()["ok"]
    assert client.post("/api/sse/rename", json={"name": "axis2", "new_name": "axis3"}).json()["ok"]
    state = client.get("/api/state").json()
    assert {o["name"] for o in state["orchestrators"]} == {"prod", "dr"}
    assert {s["name"] for s in state["sse_platforms"]} == {"axis", "axis3"}


def test_probe_endpoint(client, monkeypatch):
    client.post("/api/orchestrators", json={"name": "prod", "url": "https://p.example.com", "api_key": "k"})
    monkeypatch.setattr(admin, "probe_orchestrator", lambda entry: {"latency": 0.05, "status_code": 200})
    r = client.post("/api/probe", json={"kind": "orchestrator", "name": "prod"})
    assert r.status_code == 200 and r.json()["state"] == "up"
    monkeypatch.setattr(
        admin, "probe_orchestrator", lambda entry: (_ for _ in ()).throw(admin.ServiceProbeError("HTTP 500"))
    )
    r = client.post("/api/probe", json={"kind": "orchestrator", "name": "prod"})
    assert r.json()["state"] == "down" and "HTTP 500" in r.json()["error"]
    assert client.post("/api/probe", json={"kind": "sse", "name": "nope"}).status_code == 404


def test_default_target_endpoint_persists_and_validates(client, env):
    client.post("/api/orchestrators", json={"name": "prod", "url": "https://p.example.com", "api_key": "k"})
    client.post("/api/sse", json={"name": "axis", "base_url": "https://a.example.com", "admin_token": "t"})
    r = client.post("/api/default", json={"kind": "orchestrator", "name": "prod"})
    assert r.json()["ok"] is True
    assert "EC_DEFAULT_ORCHESTRATOR=prod" in (env / ".env").read_text(encoding="utf-8")
    assert client.post("/api/default", json={"kind": "sse", "name": "axis"}).json()["ok"] is True
    assert client.post("/api/default", json={"kind": "sse", "name": "missing"}).status_code == 404
    state = client.get("/api/state").json()
    assert state["default_orchestrator"] == "prod"
    assert state["default_sse"] == "axis"
    assert [o["default"] for o in state["orchestrators"]] == [True]
    assert [s["default"] for s in state["sse_platforms"]] == [True]


def test_resolve_default_name():
    assert resolve_default_name(["prod", "lab"], "lab") == "lab"
    assert resolve_default_name(["prod", "default"], "") == "default"
    assert resolve_default_name(["prod", "lab"], "missing") == "lab"
    assert resolve_default_name([], "") == ""


def test_multi_user_login_roles_and_guards(env):
    admin_users.upsert_user("alice", "alicepw", "admin")
    admin_users.upsert_user("bob", "bobpw", "viewer")
    assert (env / "users.json").stat().st_mode & 0o777 == 0o600

    c = TestClient(build_admin_app())
    assert c.post("/login", json={"username": "bob", "password": "wrong"}).status_code == 200
    r = c.post("/login", json={"username": "bob", "password": "bobpw"})
    assert r.json() == {"ok": True, "user": "bob", "role": "viewer"}
    assert c.get("/api/state").status_code == 200
    assert c.post("/api/config", json={"values": {"EC_MCP_PORT": "9000"}}).status_code == 403
    assert c.post("/api/orchestrators", json={"name": "x", "url": "https://x.example.com", "api_key": "k"}).status_code == 403
    assert c.get("/api/users").status_code == 403
    assert c.post("/api/restart").status_code == 403

    a = TestClient(build_admin_app())
    assert a.post("/login", json={"username": "alice", "password": "alicepw"}).json()["role"] == "admin"
    r = a.post("/api/users", json={"username": "carol", "password": "cpw", "role": "operator"})
    assert r.status_code == 200 and r.json()["role"] == "operator"
    listed = a.get("/api/users").json()["users"]
    assert {u["username"]: u["role"] for u in listed} == {"alice": "admin", "bob": "viewer", "carol": "operator"}
    assert "password_hash" not in json.dumps(listed)
    assert a.post("/api/users/delete", json={"username": "alice"}).json()["ok"] is False
    assert a.post("/api/users/delete", json={"username": "carol"}).json()["deleted"] is True
    assert a.post("/api/users", json={"username": "bad name", "password": "x", "role": "admin"}).status_code == 400
    assert a.post("/api/users", json={"username": "dave", "password": "x", "role": "superuser"}).status_code == 400


def test_login_legacy_password_still_works_when_users_file_exists(env, monkeypatch):
    # El server del usuario tiene .ec-admin-users.json en cwd: sin username debe
    # seguir funcionando la contraseña única (retrocompatible).
    admin_users.upsert_user("alice", "alicepw", "admin")
    assert admin_users.has_users() is True
    monkeypatch.setattr(admin, "_verify_password", lambda candidate, allow_first_run=True: candidate == "legacy-pw")
    c = TestClient(build_admin_app())
    r = c.post("/login", json={"password": "legacy-pw"})
    assert r.status_code == 200 and r.json()["user"] == "admin"
    r2 = c.post("/login", json={"username": "alice", "password": "alicepw"})
    assert r2.status_code == 200 and r2.json()["user"] == "alice" and r2.json()["role"] == "admin"
    r3 = c.post("/login", json={"username": "alice", "password": "mala"})
    assert r3.status_code == 200 and r3.json()["ok"] is False


def test_password_change_requires_current_password(env):
    admin_users.upsert_user("bob", "bobpw", "viewer")
    c = TestClient(build_admin_app())
    assert c.post("/login", json={"username": "bob", "password": "bobpw"}).json()["ok"] is True
    bad = c.post("/api/users/password", json={"old_password": "nope", "new_password": "newpw"})
    assert bad.status_code == 400
    ok = c.post("/api/users/password", json={"old_password": "bobpw", "new_password": "newpw"})
    assert ok.json()["ok"] is True
    fresh = TestClient(build_admin_app())
    assert fresh.post("/login", json={"username": "bob", "password": "bobpw"}).json()["ok"] is False
    assert fresh.post("/login", json={"username": "bob", "password": "newpw"}).json()["ok"] is True
    viewer = TestClient(build_admin_app())
    viewer.post("/login", json={"username": "bob", "password": "newpw"})
    assert viewer.post("/api/users/password", json={"username": "alice", "new_password": "x"}).status_code == 403


def test_panel_actions_are_audited_with_user(env, client):
    client.post("/api/orchestrators", json={"name": "prod", "url": "https://p.example.com", "api_key": "k"})
    client.post("/api/config", json={"values": {"EC_MCP_PORT": "9001"}})
    lines = [json.loads(line) for line in (env / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    actions = {(e["action"], e.get("user")) for e in lines if e["tool"] == "admin_panel"}
    assert ("save_orchestrator", "admin") in actions
    assert ("save_config", "admin") in actions
    assert all(e["tool"] != "admin_panel" or "user" in e for e in lines)


def test_page_has_wizard_users_and_target_actions():
    assert "renderWizard" in PAGE
    assert "Asistente" in PAGE
    assert "/api/wizard" in PAGE
    assert "/api/config/diff" in PAGE
    assert "/api/probe" in PAGE
    assert "/api/users" in PAGE
    assert "probeTarget" in PAGE
    assert "setDefaultTarget" in PAGE
    assert "login-user" in PAGE
    assert "tab-users" in PAGE


def test_page_has_i18n_and_theme_picker_and_no_ztp():
    assert "var I18N=" in PAGE
    assert "function setLang(" in PAGE
    assert "function setAccent(" in PAGE
    assert "setAccent" in PAGE
    assert "label_'+LANG" in PAGE
    assert "title_'+LANG" in PAGE
    assert "renderZtp" not in PAGE and "tab-ztp" not in PAGE
    assert "#01a982" in PAGE and "#073b4c" in PAGE
    assert "es:" in PAGE and "en:" in PAGE


def test_public_config_has_english_labels_and_step_titles(env):
    config = admin_config.public_config(env / ".env")
    by_key = {f["key"]: f for f in config["fields"]}
    assert by_key["EC_ORCHESTRATOR_URL"]["label_en"] == "Orchestrator URL"
    assert by_key["EC_ADMIN_PASSWORD"]["label_en"] == "Administrator password"
    assert by_key["EC_ORCHESTRATOR_URL"]["help_en"]
    titles = {s["id"]: s for s in config["steps"]}
    assert titles["orchestrator"]["title_en"] == "Orchestrator"
    assert titles["panel"]["title_en"] == "Web panel"


def test_i18n_literal_has_no_runtime_calls():
    import re

    line = next(row for row in PAGE.splitlines() if row.startswith("var I18N="))
    assert not re.search(r":(''\s*\+\s*t\(|t\()", line), "el literal I18N no debe llamar a t() en su evaluación"


def test_page_script_executes_cleanly_in_node(tmp_path):
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node no disponible")
    import re

    match = re.search(r"<script>(.*)</script>", PAGE, re.S)
    script = tmp_path / "page.js"
    script.write_text(match.group(1), encoding="utf-8")
    stub = tmp_path / "stub.js"
    stub.write_text(
        "var el={};function mk(){return{innerHTML:'',value:'',textContent:'',style:{},addEventListener:function(){},classList:{add:function(){},remove:function(){}}}}\n"
        "global.document={documentElement:{style:{setProperty:function(){}}},querySelector:function(s){return el[s]||(el[s]=mk())},querySelectorAll:function(){return[]},getElementById:function(){return mk()}};\n"
        "global.window=global;global.localStorage={getItem:function(){return null},setItem:function(){}};\n"
        "global.fetch=function(){return Promise.reject(new Error('offline'))};\n"
        "global.confirm=function(){return true};global.prompt=function(){return ''};\n",
        encoding="utf-8",
    )
    tail = (
        "global.fetch=function(p){var d={ok:true};if(p==='/login')d={ok:true,user:'admin',role:'admin'};"
        "if(p==='/api/state')d={orchestrators:[],sse_platforms:[],session:{},blobs:{}};"
        "var F={key:'K',group:'G',label:'l',kind:'text',secret:false,required:false,depends_on:null,step:'x',value:'',choices:[],configured:true,minimum:null,maximum:null,help:''};"
        "if(p==='/api/config')d={fields:[F],steps:[{id:'x',title:'X',title_en:'X'}],env_file:'.env'};"
        "if(p==='/api/update/status')d={state:'idle'};"
        "if(p==='/api/wizard')d={steps:[{id:'x',title:'X',title_en:'X'}],fields:[F],state:{},env_file:'.env'};"
        "if(p==='/api/tools')d={ok:true,total:0,disabled:[],tools:[]};"
        "if(p==='/api/tls')d={ok:true,enabled:false,cert_present:false,key_present:false};"
        "return Promise.resolve({status:200,json:function(){return Promise.resolve(d)}})};"
        "(async function(){await login();await new Promise(function(r){setTimeout(r,30)});"
        "var tabs=['wizard','orch','sse','svc','config','tls','tools','update','users'];"
        "for(var i=0;i<tabs.length;i++){showTab(tabs[i]);await new Promise(function(r){setTimeout(r,10)});"
        "var ih=String(document.querySelector('#workspace').innerHTML||'');"
        "if(ih.charAt(0)!=='<'){console.error('TAB '+tabs[i]+' no renderiza: '+ih.slice(0,40));process.exit(1)}}\n"
        "console.log('ALL TABS RENDER HTML')})();\n"
    )
    run = tmp_path / "run.js"
    run.write_text(stub.read_text(encoding="utf-8") + script.read_text(encoding="utf-8") + tail, encoding="utf-8")
    result = subprocess.run([node, str(run)], capture_output=True, text=True, timeout=30)  # noqa: S603 - node binario local sobre fixture propio
    assert result.returncode == 0, result.stderr[-2000:]
    assert "ALL TABS RENDER HTML" in result.stdout


def _openssl():
    import shutil

    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("openssl no disponible")
    return openssl


def _run(openssl, args, data=None):
    import subprocess

    proc = subprocess.run([openssl, *args], input=data, capture_output=True, timeout=30)  # noqa: S603 - argv fijo
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return proc.stdout


@pytest.fixture()
def pem_pair(tmp_path: Path):
    openssl = _openssl()
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    _run(openssl, ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                   "-subj", "/CN=ec-mcp-test", "-keyout", str(key), "-out", str(cert)])
    return cert.read_text(encoding="utf-8"), key.read_text(encoding="utf-8")


def test_tls_pem_upload_requires_confirmation_and_matching_key(client, env, pem_pair):
    import base64

    cert_pem, key_pem = pem_pair
    assert client.get("/api/tls").json()["cert_present"] is False
    no_confirm = client.post("/api/tls/upload", json={"mode": "pem", "certificateData": base64.b64encode(cert_pem.encode()).decode(), "keyData": base64.b64encode(key_pem.encode()).decode(), "confirmation": "mal"})
    assert no_confirm.status_code == 400
    bad = client.post("/api/tls/upload", json={"mode": "pem", "cert": "no pem", "key": key_pem, "confirmation": "INSTALAR CERTIFICADO"})
    assert bad.status_code == 400
    ok = client.post("/api/tls/upload", json={"mode": "pem", "cert": cert_pem, "key": key_pem, "confirmation": "INSTALAR CERTIFICADO"})
    assert ok.json()["ok"] is True
    assert ok.json()["fingerprint"] and "ec-mcp-test" in ok.json()["subject"]
    cert_path = env / ".ec-admin-tls" / "cert.pem"
    key_path = env / ".ec-admin-tls" / "key.pem"
    assert cert_path.is_file() and key_path.is_file()
    if os.name != "nt":
        assert cert_path.stat().st_mode & 0o777 == 0o600
        assert key_path.stat().st_mode & 0o777 == 0o600
    status = client.get("/api/tls").json()
    assert status["cert_present"] and status["key_present"] and status["valid"] is True
    assert "ec-mcp-test" in status["subject"] and status["expires_at"]
    assert "EC_ADMIN_TLS_CERT=" in (env / ".env").read_text(encoding="utf-8")
    deleted = client.post("/api/tls/delete")
    assert deleted.json()["ok"] is True
    assert not cert_path.exists() and not key_path.exists()
    assert client.get("/api/tls").json()["cert_present"] is False


def test_tls_pfx_mode_and_key_mismatch(client, env, pem_pair, tmp_path):
    import base64

    openssl = _openssl()
    cert_pem, _key_pem = pem_pair
    # primera instalación PEM correcta
    first = client.post("/api/tls/upload", json={"mode": "pem", "cert": cert_pem, "key": (tmp_path / "key.pem").read_text(encoding="utf-8"), "confirmation": "INSTALAR CERTIFICADO"})
    assert first.json()["ok"] is True
    pfx = tmp_path / "cert.pfx"
    _run(openssl, ["pkcs12", "-export", "-out", str(pfx), "-inkey", str(tmp_path / "key.pem"), "-in", str(tmp_path / "cert.pem"), "-passout", "pass:secreto123"])
    pfx_b64 = base64.b64encode(pfx.read_bytes()).decode()
    r = client.post("/api/tls/upload", json={"mode": "pfx", "certificateData": pfx_b64, "password": "secreto123", "confirmation": "INSTALAR CERTIFICADO"})
    assert r.json()["ok"] is True and r.json()["mode"] == "pfx"
    # el certificado anterior quedó respaldado
    assert (env / ".ec-admin-tls" / "cert.pem.bak").is_file()
    # llave que no corresponde
    other_key = tmp_path / "other.key"
    _run(openssl, ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=otro", "-keyout", str(other_key), "-out", str(tmp_path / "other.pem")])
    wrong = client.post("/api/tls/upload", json={"mode": "pem", "cert": cert_pem, "key": other_key.read_text(encoding="utf-8"), "confirmation": "INSTALAR CERTIFICADO"})
    assert wrong.status_code == 400 and "no corresponde" in wrong.json()["error"]


def test_tls_upload_forbidden_for_viewer(env, pem_pair):
    cert_pem, key_pem = pem_pair
    admin_users.upsert_user("bob", "bobpw", "viewer")
    c = TestClient(build_admin_app())
    assert c.post("/login", json={"username": "bob", "password": "bobpw"}).json()["ok"] is True
    assert c.post("/api/tls/upload", json={"mode": "pem", "cert": cert_pem, "key": key_pem, "confirmation": "INSTALAR CERTIFICADO"}).status_code == 403
    assert c.get("/api/tls").status_code == 200


def test_page_has_tls_tab_branding_and_per_target_selector():
    assert "renderTls" in PAGE
    assert "/api/tls" in PAGE
    assert "nav_tls" in PAGE
    assert "fmt_pfx" in PAGE and "tls_confirm_code" in PAGE
    assert "siteName" in PAGE and "siteLogo" in PAGE and "openCustom" in PAGE
    assert "userChip" in PAGE and "topbar" in PAGE
    assert "ACCENTS.map" not in PAGE
    assert "cfgTargets" in PAGE and "targetPanelHtml" in PAGE
    assert "wiz_step" in PAGE
    assert "group_'+LANG" in PAGE
    assert "ntc.innerHTML" in PAGE
    assert "#073b4c" in PAGE and "#01a982" in PAGE and "details class=\"group\"" in PAGE


def test_public_config_has_group_en_and_tls_settings(env):
    config = admin_config.public_config(env / ".env")
    by_key = {f["key"]: f for f in config["fields"]}
    assert by_key["EC_ORCHESTRATOR_URL"]["group_en"] == "Orchestrator"
    assert by_key["EC_SSH_USER"]["group_en"] == "Optional SSH"
    assert by_key["EC_ADMIN_TLS_ENABLED"]["label_en"] == "Enable HTTPS on the panel"
    assert by_key["EC_ADMIN_TLS_CERT"]["depends_on"] == ["EC_ADMIN_TLS_ENABLED", "true"]


def test_tools_list_toggle_and_runtime_filter(client, env, monkeypatch):
    admin._TOOLS_CACHE = None
    r = client.get("/api/tools")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 125
    assert data["disabled"] == []
    name = data["tools"][0]["name"]
    off = client.post("/api/tools/toggle", json={"name": name, "enabled": False})
    assert off.json()["ok"] is True and name in off.json()["disabled"]
    assert f"EC_MCP_DISABLED_TOOLS={name}" in (env / ".env").read_text(encoding="utf-8")
    assert client.post("/api/tools/toggle", json={"name": "no-existe", "enabled": False}).status_code == 404
    from ec_mcp import server

    mcp = server.create_server()
    assert name not in {t.name for t in mcp._tool_manager.list_tools()}
    assert len(mcp._tool_manager.list_tools()) == 124
    on = client.post("/api/tools/toggle", json={"name": name, "enabled": True})
    assert on.json()["disabled"] == []
    mcp2 = server.create_server()
    assert len(mcp2._tool_manager.list_tools()) == 125
    admin._TOOLS_CACHE = None


def test_agent_prompt_endpoint_includes_skills(client):
    r = client.get("/api/agent-prompt")
    assert r.status_code == 200
    data = r.json()
    assert data["tools_total"] == 125
    assert "EDGECONNECT_NOC_OPS_SKILL.md" in data["prompt"]
    assert "AI_AGENT_SKILL_RECOMMENDATIONS.md" in data["prompt"]
    assert "sugerencia" in data["prompt"].lower()


def test_page_has_tools_tab_and_clean_chrome():
    assert "renderTools" in PAGE
    assert "/api/tools/toggle" in PAGE
    assert "showAgentPrompt" in PAGE
    assert "cfgTab" in PAGE and "global_vars" in PAGE
    assert "t('yes')" in PAGE
    assert "ACCENTS.map" not in PAGE
    assert 'class="slider"' in PAGE and "tools-grid" in PAGE
    assert "brand-preview" in PAGE and "icon-picker" in PAGE and "applySavedTheme" in PAGE
    assert 'onclick="applyOrch()">' in PAGE and 'onclick="applySse()">' in PAGE
    assert '()"' + chr(39) + '>' not in PAGE  # patrón del bug "false": comilla antes del >


def test_debug_events_export_clear(client, env):
    from ec_mcp.audit import AuditLog

    admin.DEBUG_EVENTS.clear()
    client.get("/api/state")
    client.get("/api/tools")
    r = client.get("/api/debug/events?limit=50")
    assert r.status_code == 200
    events = r.json()["events"]
    api_events = [e for e in events if e["source"] == "panel-api"]
    assert any("GET /api/state" in e["action"] for e in api_events)
    # tool MCP desde el audit log
    audit = AuditLog(env / "audit.jsonl")
    audit.record("my_tool", "read", "orch:prod", "ok", user="admin")
    r = client.get("/api/debug/events?limit=50&q=my_tool")
    tool_events = [e for e in r.json()["events"] if e["source"] == "mcp-tool"]
    assert tool_events and tool_events[0]["tool"] == "my_tool" and tool_events[0]["user"] == "admin"
    # export
    ex = client.get("/api/debug/export")
    assert ex.status_code == 200
    assert "attachment" in ex.headers.get("content-disposition", "")
    assert "my_tool" in ex.text
    ex_csv = client.get("/api/debug/export?format=csv")
    assert ex_csv.headers["content-type"].startswith("text/csv")
    assert "mcp-tool" in ex_csv.text
    # clear
    assert (env / "audit.jsonl").stat().st_size > 0
    cleared = client.post("/api/debug/clear")
    assert cleared.json()["ok"] is True
    assert cleared.json()["bytes_before"] > 0
    assert (env / "audit.jsonl").read_text(encoding="utf-8") == ""
    # el middleware registra el propio clear tras ejecutarse: solo quedan eventos panel-api
    remaining = client.get("/api/debug/events").json()["events"]
    assert all(e["source"] == "panel-api" for e in remaining)


def test_debug_clear_forbidden_for_viewer(env):
    admin_users.upsert_user("bob", "bobpw", "viewer")
    c = TestClient(build_admin_app())
    c.post("/login", json={"username": "bob", "password": "bobpw"})
    assert c.post("/api/debug/clear").status_code == 403
    assert c.get("/api/debug/events").status_code == 200


def test_page_has_debug_tab():
    assert "renderDebug" in PAGE
    assert "nav_debug" in PAGE
    assert "/api/debug/events" in PAGE and "/api/debug/export" in PAGE and "/api/debug/clear" in PAGE
    assert ".tool-card>div{min-width:0" in PAGE


def test_mcp_probe_url_uses_loopback_for_wildcard_host(monkeypatch):
    from ec_mcp import admin_services

    monkeypatch.setenv("EC_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("EC_MCP_PORT", "8000")
    monkeypatch.delenv("EC_MCP_TLS_CERT", raising=False)
    assert admin_services.mcp_probe_url() == "http://127.0.0.1:8000/health"
    monkeypatch.setenv("EC_MCP_HOST", "10.0.0.5")
    assert admin_services.mcp_probe_url() == "http://10.0.0.5:8000/health"


def test_tools_have_human_spanish_descriptions(client, env):
    admin._TOOLS_CACHE = None
    data = client.get("/api/tools").json()
    by_name = {t["name"]: t for t in data["tools"]}
    assert by_name["list_appliances"]["description_es"].startswith("Inventario real")
    assert by_name["apply_change"]["description_es"]
    assert by_name["axis_commit"]["description_es"]
    assert by_name["list_cli_commands"]["description_es"] == ""
    admin._TOOLS_CACHE = None


def test_page_polish_fixes():
    assert "opcional si hay varios" not in PAGE
    assert "MCP para SASE" in PAGE
    assert "resetCustom" in PAGE and "app_reset" in PAGE
    assert "role!=='admin'" in PAGE
    assert "cfg-target-sel" in PAGE
    assert "accentbar" in PAGE
    assert "description_es" in PAGE


def test_panel_responses_are_not_cached(client):
    for path in ("/", "/login"):
        r = client.get(path)
        assert r.status_code in (200, 303)
        if r.status_code == 200:
            assert r.headers.get("cache-control") == "no-store, max-age=0"
    r = client.get("/api/state")
    assert r.headers.get("cache-control") == "no-store, max-age=0"


def test_new_routes_registered():
    paths = {route.path for route in build_admin_app().routes}
    assert {
        "/api/wizard",
        "/api/tls",
        "/api/tls/upload",
        "/api/tls/delete",
        "/api/tools",
        "/api/tools/toggle",
        "/api/agent-prompt",
        "/api/debug/events",
        "/api/debug/export",
        "/api/debug/clear",
        "/api/config/diff",
        "/api/probe",
        "/api/default",
        "/api/orchestrators/rename",
        "/api/orchestrators/duplicate",
        "/api/sse/rename",
        "/api/sse/duplicate",
        "/api/users",
        "/api/users/delete",
        "/api/users/password",
    }.issubset(paths)
