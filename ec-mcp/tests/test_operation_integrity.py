from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ec_mcp.config import Settings
from ec_mcp.server import create_server


@pytest.mark.parametrize("confirm", [False, True])
def test_apply_change_array_body_reaches_transport_and_audit(monkeypatch, tmp_path, confirm):
    import ec_mcp.server as server_module

    calls = []

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, version, operation_id, path_params=None, json_body=None, **query):
            calls.append((operation_id, json_body))
            return {"saved": True}

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: FakeClient())
    audit_path = tmp_path / "audit.jsonl"
    server = create_server(Settings(allow_write_tools=True, audit_log_path=audit_path))
    body = [{"id": 7, "name": "Application", "services": ["HTTPS"], "dscpTags": []}]
    response = asyncio.run(server.call_tool("apply_change", {
        "operation_id": "orchestrator.apptagspost90",
        "body_json": json.dumps(body),
        "confirm": confirm,
    }))
    payload = json.loads(response.content[0].text)
    if confirm:
        assert payload["applied"] is True
        assert calls == [("orchestrator.apptagspost90", body)]
    else:
        assert payload["dry_run"] is True
        assert calls == []
        assert payload["would_execute"]["body"] == body
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["details"]["body_items"] == 1
    assert entry["dry_run"] is not confirm


def _make_client(handler):
    from pathlib import Path

    import httpx

    from ec_mcp.compat import CompatibilityEngine, load_profiles
    from ec_mcp.config import Settings
    from ec_mcp.orchestrator_client import OrchestratorClient

    engine = CompatibilityEngine(load_profiles(Path(__file__).parent.parent / "ec_mcp" / "profiles"))
    settings = Settings(orchestrator_url="https://orch.example", orchestrator_api_key="k")
    client = OrchestratorClient(settings, engine, client=httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://orch.example"))
    return client


def test_write_not_retried_on_empty_response():
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        return httpx.Response(204)

    client = _make_client(handler)
    result = client.call("9.6", "orchestrator.apptagspost90", json_body={"id": 1})
    assert result == {"ok": True}
    write_calls = [r for r in requests if r[0] != "GET"]
    assert len(write_calls) == 1


def test_write_not_retried_on_404_fallback():
    import pytest

    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        return httpx.Response(404, json={"message": "not found"})

    client = _make_client(handler)
    with pytest.raises(RuntimeError):
        client.call("9.6", "orchestrator.apptagspost90", json_body={"id": 1})
    write_calls = [r for r in requests if r[0] != "GET"]
    assert len(write_calls) == 1


def test_apply_change_reports_applied_when_read_after_write_fails(monkeypatch, tmp_path):
    import ec_mcp.server as server_module

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, version, operation_id, path_params=None, json_body=None, **query):
            if operation_id == "orchestrator.apptagsget89":
                raise RuntimeError("GET apptags: transient 503")
            return {"saved": True}

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: FakeClient())
    audit_path = tmp_path / "audit.jsonl"
    server = create_server(Settings(allow_write_tools=True, audit_log_path=audit_path))
    response = asyncio.run(server.call_tool("apply_change", {
        "operation_id": "orchestrator.apptagspost90",
        "body_json": json.dumps({"id": 1, "name": "App"}),
        "verify_operation_id": "orchestrator.apptagsget89",
        "confirm": True,
    }))
    payload = json.loads(response.content[0].text)
    assert payload["applied"] is True
    assert payload["read_after_write_failed"] is True
    assert "transient 503" in payload["read_after_write_error"]
    assert "Do not retry" in payload["warning"]
    entries = [json.loads(line) for line in audit_path.read_text().splitlines()]
    assert any(e["result"] == "ok" for e in entries)
    assert any("read-after-write failed" in e["result"] for e in entries)


def test_apply_change_rejects_non_get_verify_before_write(monkeypatch, tmp_path):
    import ec_mcp.server as server_module

    calls = []

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, version, operation_id, path_params=None, json_body=None, **query):
            calls.append(operation_id)
            return {"saved": True}

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: FakeClient())
    audit_path = tmp_path / "audit.jsonl"
    server = create_server(Settings(allow_write_tools=True, audit_log_path=audit_path))
    response = asyncio.run(server.call_tool("apply_change", {
        "operation_id": "orchestrator.apptagspost90",
        "body_json": json.dumps({"id": 1, "name": "App"}),
        "verify_operation_id": "orchestrator.apptagspost90",
        "confirm": True,
    }))
    text = response.content[0].text
    assert "verify_operation_id must be a GET operation" in text
    assert calls == []
