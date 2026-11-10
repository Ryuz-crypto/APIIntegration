"""Axis onboarding regression tests using only local files and mock HTTP."""
from __future__ import annotations

import json
import os

import httpx
import pytest
from starlette.testclient import TestClient

import ec_mcp.admin as admin
from ec_mcp import admin_services


def test_axis_probe_uses_public_admin_health_path(monkeypatch):
    seen = []

    def handle(request):
        seen.append((request.url.path, request.headers.get("authorization")))
        return httpx.Response(200 if request.url.path == "/api/v1.0/Health" else 404)

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    result = admin_services.probe_axis({"base_url": "https://axis.example", "admin_token": "test-token"})
    assert result["status_code"] == 200
    assert seen == [("/api/v1.0/Health", "Bearer test-token")]


def test_axis_probe_does_not_report_unauthorized_as_up(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client",
        lambda **kw: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(401)), **kw),
    )
    with pytest.raises(admin_services.ServiceProbeError, match="HTTP 401"):
        admin_services.probe_axis({"base_url": "https://axis.example", "admin_token": "test-token"})


def test_sse_save_preserves_secret_and_apply_requires_explicit_name(tmp_path, monkeypatch):
    monkeypatch.setenv("EC_ADMIN_STORE", str(tmp_path / "registry.json"))
    monkeypatch.setenv("EC_MCP_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "admin", "role": "admin"})
    monkeypatch.setattr(admin, "_snapshot_backup", lambda label: None)
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    for key in (
        "EC_ORCHESTRATORS_JSON", "EC_SSE_PLATFORMS_JSON", "EC_DEFAULT_SSE",
        "EC_AXIS_ENABLED", "EC_AXIS_ADMIN_TOKEN", "EC_AXIS_BASE_URL", "EC_AXIS_VERIFY_TLS", "EC_AXIS_TIMEOUT",
    ):
        monkeypatch.delenv(key, raising=False)
    with TestClient(admin.build_admin_app()) as client:
        for name in ("a", "z"):
            r = client.post("/api/sse", json={"name": name, "base_url": "https://axis.example", "admin_token": "token-" + name})
            assert r.json()["ok"]
        update = client.post("/api/sse", json={"name": "z", "base_url": "https://axis.example", "admin_token": ""})
        assert update.json()["ok"]
        state = client.get("/api/state").json()
        entry = next(item for item in state["sse_platforms"] if item["name"] == "z")
        assert entry["has_admin_token"] is True
        assert "token-z" not in json.dumps(state)
        before = (tmp_path / ".env").read_bytes()
        empty = client.post("/api/apply", json={"kind": "sse", "name": ""})
        assert empty.status_code == 400
        assert (tmp_path / ".env").read_bytes() == before
        applied = client.post("/api/apply", json={"kind": "sse", "name": "z"})
        assert applied.json()["ok"]
        assert os.environ["EC_AXIS_ADMIN_TOKEN"] == "token-z"


def test_apply_failure_keeps_previous_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER=keep\n", encoding="utf-8")
    monkeypatch.setenv("EC_ADMIN_STORE", str(tmp_path / "registry.json"))
    monkeypatch.setenv("EC_MCP_ENV_FILE", str(env))
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "admin", "role": "admin"})
    monkeypatch.setattr(admin, "_snapshot_backup", lambda label: None)
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    admin.load_registry().save_sse("a", {"base_url": "https://axis.example", "admin_token": "test-token"})

    def fail_replace(source, destination):
        raise OSError("simulated")

    monkeypatch.setattr(admin.os, "replace", fail_replace)
    with TestClient(admin.build_admin_app()) as client:
        response = client.post("/api/apply", json={"kind": "sse", "name": "a"})
    assert response.status_code == 500
    assert not response.json()["ok"]
    assert env.read_text(encoding="utf-8") == "OTHER=keep\n"
