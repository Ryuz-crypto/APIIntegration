from __future__ import annotations

import os
from pathlib import Path

import pytest

from ec_mcp import admin_config, web_update
from ec_mcp.admin import build_admin_app
from ec_mcp.admin_page import PAGE


def test_public_config_never_returns_secrets(tmp_path: Path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        "EC_ORCHESTRATOR_URL=https://orch.example\n"
        "EC_ORCHESTRATOR_API_KEY=super-secret\n"
        "EC_UPDATE_GITHUB_TOKEN=github-secret\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("EC_ORCHESTRATOR_API_KEY", raising=False)
    monkeypatch.delenv("EC_UPDATE_GITHUB_TOKEN", raising=False)
    result = admin_config.public_config(path)
    by_key = {item["key"]: item for item in result["fields"]}
    assert by_key["EC_ORCHESTRATOR_API_KEY"]["value"] == ""
    assert by_key["EC_ORCHESTRATOR_API_KEY"]["configured"] is True
    assert by_key["EC_UPDATE_GITHUB_TOKEN"]["value"] == ""
    assert "super-secret" not in str(result)
    assert "github-secret" not in str(result)


def test_update_env_preserves_comments_and_blank_secret(tmp_path: Path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("# keep me\nEC_UPDATE_GITHUB_TOKEN=existing\nEC_MCP_PORT=8000\n", encoding="utf-8")
    monkeypatch.delenv("EC_UPDATE_GITHUB_TOKEN", raising=False)
    admin_config.update_env(
        {"EC_UPDATE_GITHUB_TOKEN": "", "EC_MCP_PORT": "9000", "EC_VERIFY_TLS": "false"},
        path=path,
    )
    text = path.read_text(encoding="utf-8")
    assert "# keep me" in text
    assert "EC_UPDATE_GITHUB_TOKEN=existing" in text
    assert "EC_MCP_PORT=9000" in text
    assert "EC_VERIFY_TLS=false" in text
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_update_env_can_explicitly_clear_secret(tmp_path: Path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("EC_UPDATE_GITHUB_TOKEN=existing\n", encoding="utf-8")
    monkeypatch.delenv("EC_UPDATE_GITHUB_TOKEN", raising=False)
    admin_config.update_env({}, ["EC_UPDATE_GITHUB_TOKEN"], path)
    assert path.read_text(encoding="utf-8") == "EC_UPDATE_GITHUB_TOKEN=\n"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("EC_MCP_PORT", "70000"),
        ("EC_VERIFY_TLS", "sometimes"),
        ("EC_UPDATE_REPOSITORY", "https://github.com/owner/repo"),
        ("EC_UPDATE_BRANCH", "../main"),
        ("EC_ORCHESTRATOR_URL", "orch.example"),
    ],
)
def test_update_env_rejects_invalid_values(tmp_path: Path, key: str, value: str):
    with pytest.raises(ValueError):
        admin_config.update_env({key: value}, path=tmp_path / ".env")


def test_queue_update_pins_exact_remote_commit(monkeypatch):
    commit = "a" * 40
    recorded = {}
    monkeypatch.setattr(
        web_update,
        "check",
        lambda opener=None: {
            "remote": {"sha": commit},
            "repository": "Ryuz-crypto/APIIntegration",
            "branch": "main",
            "current_commit": "b" * 40,
            "confirmation": "ACTUALIZAR " + commit[:12],
        },
    )
    monkeypatch.setattr(web_update, "_write_request", lambda payload: recorded.update(payload))
    result = web_update.queue_update(commit, "ACTUALIZAR " + commit[:12])
    assert result["state"] == "pending"
    assert recorded == {
        "action": "update",
        "repository": "Ryuz-crypto/APIIntegration",
        "branch": "main",
        "commit": commit,
    }


def test_admin_v3_routes_and_ztp_roadmap_exist():
    paths = {route.path for route in build_admin_app().routes}
    assert {
        "/api/config",
        "/api/update/check",
        "/api/update/status",
        "/api/update/apply",
        "/api/restart",
    }.issubset(paths)
    assert "Discover" in PAGE
    assert "Seleccionar template" in PAGE
    assert "Confirmar y planchar" in PAGE


def test_admin_page_badge_reflects_installed_version():
    from ec_mcp import __version__, admin

    rendered = admin._render_page()
    assert __version__ in rendered
    assert "__EC_MCP_VERSION__" not in rendered
    assert "BASE ZTP" not in rendered
    assert "3.0.0b1" not in rendered


def test_admin_login_lockout_accepts_correct_password_and_resets_counter(monkeypatch):
    from starlette.testclient import TestClient

    from ec_mcp import admin

    admin.LOGIN_FAILURES.clear()
    monkeypatch.setattr(admin, "LOGIN_MAX_FAILURES", 2)
    monkeypatch.setattr(admin, "LOGIN_WINDOW_SECONDS", 60.0)
    monkeypatch.setattr(admin, "_verify_password", lambda candidate, allow_first_run=True: candidate == "correct")

    client = TestClient(admin.build_admin_app())
    first = client.post("/login", json={"password": "wrong"})
    second = client.post("/login", json={"password": "wrong"})
    blocked = client.post("/login", json={"password": "wrong"})

    assert first.status_code == 200
    assert first.json()["remaining_attempts"] == 1
    assert second.status_code == 200
    assert second.json()["remaining_attempts"] == 0
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]
    assert blocked.json()["retry_after_seconds"] <= 60

    recovered = client.post("/login", json={"password": "correct"})
    assert recovered.status_code == 200
    assert recovered.json()["ok"] is True
    assert admin.LOGIN_FAILURES == {}

    after_success = client.post("/login", json={"password": "wrong"})
    assert after_success.status_code == 200
    assert after_success.json()["remaining_attempts"] == 1
    admin.LOGIN_FAILURES.clear()


def test_admin_throttle_settings_are_available_in_web_config(tmp_path: Path):
    result = admin_config.public_config(tmp_path / ".env")
    by_key = {item["key"]: item for item in result["fields"]}
    assert by_key["EC_ADMIN_LOGIN_MAX_FAILURES"]["default"] == "5"
    assert by_key["EC_ADMIN_LOGIN_WINDOW_SECONDS"]["default"] == "60"


def test_admin_installer_preserves_port_from_dotenv():
    script = (Path(__file__).parent.parent / "scripts" / "install_admin_service.sh").read_text(encoding="utf-8")
    assert "ENV_PORT=\"$(grep '^EC_ADMIN_PORT=' .env" in script
    assert 'PORT="${CLI_PORT:-${EC_ADMIN_PORT:-${ENV_PORT:-8080}}}"' in script
    assert 'PORT="${EC_ADMIN_PORT:-8080}"' not in script
    assert script.index('ENV_PORT="$(grep') < script.index('set_env_value EC_ADMIN_PORT "$PORT"')


def test_restart_result_reports_pending_request_and_status(monkeypatch):
    from starlette.testclient import TestClient

    from ec_mcp import admin, web_update

    monkeypatch.setattr(admin, "queue_restart", lambda: {"state": "pending", "action": "restart", "message": "Reinicio programado."})
    captured = {"pending": True, "status": {"state": "success", "action": "restart", "message": "Servicios reiniciados.", "completed_at": "2026-10-22T01:34:29Z"}}
    monkeypatch.setattr(admin, "check_pending_request", lambda: captured["pending"])
    monkeypatch.setattr(admin, "update_status", lambda: captured["status"])
    monkeypatch.setattr(admin, "_verify_password", lambda candidate, allow_first_run=True: True)

    client = TestClient(admin.build_admin_app())
    assert client.post("/login", json={"password": "x"}).status_code == 200
    restart = client.post("/api/restart")
    assert restart.status_code == 200
    assert restart.json()["state"] == "pending"

    while_pending = client.get("/api/restart/result")
    assert while_pending.status_code == 200
    assert while_pending.json()["request_pending"] is True
    assert while_pending.json()["state"] == "success"

    captured["pending"] = False
    finished = client.get("/api/restart/result")
    assert finished.json()["request_pending"] is False
    assert finished.json()["completed_at"] == "2026-10-22T01:34:29Z"


def test_restart_result_requires_auth():
    from starlette.testclient import TestClient

    from ec_mcp import admin

    client = TestClient(admin.build_admin_app())
    assert client.get("/api/restart/result").status_code == 401


def test_admin_page_polls_restart_result():
    from ec_mcp.admin_page import PAGE

    assert "/api/restart/result" in PAGE
    assert "pollRestart" in PAGE
