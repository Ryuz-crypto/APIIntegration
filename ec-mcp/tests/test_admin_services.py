"""Phase 2 service probes: real status, audit, no fabricated readiness (refs #88)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ec_mcp import admin_services
from ec_mcp.admin import build_admin_app
from ec_mcp.admin_services import ServiceProbeError, services_status


class _StubResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code


class _StubClient:
    def __init__(self, response: _StubResponse | Exception, recorded: list | None = None):
        self._response = response
        self._recorded = recorded

    def __call__(self, *args, **kwargs):
        if self._recorded is not None:
            self._recorded.append(kwargs.get("base_url", ""))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, path, headers=None):
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.fixture(autouse=True)
def _clear_status_cache():
    import ec_mcp.admin_services as admin_services

    admin_services.clear_status_cache()
    yield
    admin_services.clear_status_cache()


def test_probe_orchestrator_reports_real_latency(monkeypatch):
    recorded = []
    monkeypatch.setattr(httpx, "Client", _StubClient(_StubResponse(200), recorded))
    result = admin_services.probe_orchestrator({"url": "https://orch.example.com", "verify_tls": True, "api_key": "k"})
    assert result["status_code"] == 200
    assert result["latency"] >= 0
    assert recorded == ["https://orch.example.com"]


def test_probe_orchestrator_requires_url():
    with pytest.raises(ServiceProbeError):
        admin_services.probe_orchestrator({})


def test_probe_orchestrator_fails_on_http_error(monkeypatch):
    monkeypatch.setattr(httpx, "Client", _StubClient(_StubResponse(503)))
    with pytest.raises(ServiceProbeError):
        admin_services.probe_orchestrator({"url": "https://orch.example.com"})


def test_probe_axis_requires_token():
    with pytest.raises(ServiceProbeError):
        admin_services.probe_axis({"base_url": "https://admin-api.example.com"})


def test_probe_axis_reports_real_latency(monkeypatch):
    recorded = []
    monkeypatch.setattr(httpx, "Client", _StubClient(_StubResponse(200), recorded))
    result = admin_services.probe_axis(
        {"base_url": "https://admin-api.example.com", "admin_token": "t", "verify_tls": True}
    )
    assert result["status_code"] == 200
    assert recorded == ["https://admin-api.example.com"]


def test_services_status_marks_down_without_fabricating_ready(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EC_MCP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(httpx, "Client", _StubClient(_StubResponse(200)))

    class _Registry:
        def list_orchestrators(self):
            return {"prod": {"url": "https://orch.example.com", "api_key": "k"}}

        def list_sse(self):
            return {"axis": {"base_url": "https://axis.example.com", "admin_token": "tok"}}

        def list_central(self):
            return {}

    monkeypatch.setattr(admin_services, "load_registry", lambda: _Registry())
    monkeypatch.setattr(admin_services, "probe_update_service", lambda: {"state": "idle"})

    def _fail_transport():
        raise ServiceProbeError("no listener")

    monkeypatch.setattr(admin_services, "probe_mcp_transport", _fail_transport)
    report = services_status(probe=True)
    assert report["orchestrators"][0]["state"] == "up"
    assert report["sse_platforms"][0]["state"] == "up"
    assert report["mcp_transport"]["state"] == "down"
    assert report["update_worker"]["state"] == "idle"
    assert report["checked_at"]
    entries = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert entries and entries[-1]["tool"] == "admin_panel"


def test_services_status_reports_errors_not_ready(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EC_MCP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))

    class _Registry:
        def list_orchestrators(self):
            return {"prod": {"url": "https://orch.example.com"}}

        def list_sse(self):
            return {}

        def list_central(self):
            return {}

    monkeypatch.setattr(admin_services, "load_registry", lambda: _Registry())

    def _down(entry):
        raise ServiceProbeError("HTTP 503 al consultar el orquestador.")

    monkeypatch.setattr(admin_services, "probe_orchestrator", _down)
    monkeypatch.setattr(admin_services, "probe_update_service", lambda: {"state": "idle"})
    monkeypatch.setattr(
        admin_services,
        "probe_mcp_transport",
        lambda: {"latency": 0.01, "status_code": 200, "url": "http://127.0.0.1:8000/health"},
    )
    report = services_status(probe=True)
    assert report["orchestrators"][0]["state"] == "down"
    assert "503" in report["orchestrators"][0]["error"]
    assert report["mcp_transport"]["latency"] >= 0


def test_services_endpoint_requires_auth():
    from starlette.testclient import TestClient

    app = build_admin_app()
    client = TestClient(app)
    response = client.get("/api/services/status")
    assert response.status_code == 401


def test_services_endpoint_returns_real_report(tmp_path: Path, monkeypatch):
    from starlette.testclient import TestClient

    monkeypatch.setenv("EC_MCP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))

    class _Registry:
        def list_orchestrators(self):
            return {}

        def list_sse(self):
            return {}

        def list_central(self):
            return {}

    monkeypatch.setattr(admin_services, "load_registry", lambda: _Registry())
    monkeypatch.setattr(admin_services, "probe_update_service", lambda: {"state": "idle"})
    monkeypatch.setattr(
        admin_services, "probe_mcp_transport", _fail := (lambda: {"latency": 0.0, "status_code": 200, "url": "u"})
    )
    app = build_admin_app()
    client = TestClient(app)
    client.cookies.set("ec_admin_session", "test-session")
    monkeypatch.setattr(
        "ec_mcp.admin._check_session",
        lambda request: request.cookies.get("ec_admin_session") == "test-session",
    )
    response = client.get("/api/services/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["probe"] is True
    assert isinstance(payload["orchestrators"], list)
    assert payload["mcp_transport"]["status_code"] == 200


def test_request_restart_audits_pending(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EC_MCP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(
        "ec_mcp.web_update.queue_restart", lambda: {"state": "pending", "action": "restart", "message": "m"}
    )
    result = admin_services.request_restart("apply config")
    assert result["state"] == "pending"
    entries = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert any(e["action"] == "restart_requested" and e["result"] == "pending" for e in entries)


def test_request_update_audits_commit(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("EC_MCP_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr("ec_mcp.web_update.queue_update", lambda sha, conf: {"state": "pending", "commit": sha})
    result = admin_services.request_update("a" * 40, "ACTUALIZAR aaa")
    assert result["state"] == "pending"
    entries = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert any(e["action"] == "update_requested" for e in entries)


def test_admin_page_has_services_tab():
    from ec_mcp.admin_page import PAGE

    assert "tab-svc" in PAGE
    assert "Servicios" in PAGE
    assert "/api/services/status" in PAGE


def test_apply_orchestrator_handles_none_fields(tmp_path: Path, monkeypatch):
    """Regression: applying an orchestrator with unset optional fields must not 500."""
    from starlette.testclient import TestClient

    monkeypatch.setenv("EC_MCP_ENV_FILE", str(tmp_path / ".env"))

    class _Registry:
        def get_orchestrator(self, name):
            return {
                "url": "https://orch.example.com",
                "api_key": "key",
                "username": None,
                "password": None,
                "ssh_user": None,
                "ssh_password": None,
                "ssh_enable_password": None,
                "ssh_host": None,
            }

        def list_orchestrators(self):
            return {"prod": {}}

        def to_env_blob(self):
            return {}

    monkeypatch.setattr("ec_mcp.admin.load_registry", lambda: _Registry())
    monkeypatch.setattr("ec_mcp.admin.public_orchestrator", lambda name, entry: {"verify_tls": True})
    app = build_admin_app()
    client = TestClient(app)
    client.cookies.set("ec_admin_session", "s")
    monkeypatch.setattr("ec_mcp.admin._check_session", lambda request: True)
    response = client.post("/api/apply", json={"name": "prod", "kind": "orchestrator"})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    env = (tmp_path / ".env").read_text()
    assert "EC_ORCHESTRATOR_URL=https://orch.example.com" in env


def test_services_status_cache_reuses_recent_report_and_can_clear():
    import ec_mcp.admin_services as admin_services

    admin_services.clear_status_cache()
    monkey = pytest.MonkeyPatch()

    class _Registry:
        def list_orchestrators(self):
            return {}

        def list_sse(self):
            return {}

        def list_central(self):
            return {}

    monkey.setattr(admin_services, "load_registry", lambda: _Registry())
    monkey.setattr(admin_services, "probe_update_service", lambda: {"state": "idle"})
    monkey.setattr(admin_services, "probe_mcp_transport", lambda: {"latency": 0.01, "status_code": 200, "url": "u"})
    first = admin_services.services_status(probe=True)
    second = admin_services.services_status(probe=True)
    assert first["checked_at"] == second["checked_at"]
    admin_services.clear_status_cache()
    third = admin_services.services_status(probe=True)
    assert third["checked_at"] != first["checked_at"]
    monkey.undo()
    admin_services.clear_status_cache()
