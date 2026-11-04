"""Tests for the admin wizard, config diff, per-target ops and multi-user panel."""

from __future__ import annotations

import json
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
    assert "class=\"sw\"" in PAGE
    assert "label_'+LANG" in PAGE
    assert "title_'+LANG" in PAGE
    assert "renderZtp" not in PAGE and "tab-ztp" not in PAGE
    assert "#01a982" in PAGE and "#00263a" in PAGE
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


def test_new_routes_registered():
    paths = {route.path for route in build_admin_app().routes}
    assert {
        "/api/wizard",
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
