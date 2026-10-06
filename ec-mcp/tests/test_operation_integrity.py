from __future__ import annotations

import asyncio
import json

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

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args: FakeClient())
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
