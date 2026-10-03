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
