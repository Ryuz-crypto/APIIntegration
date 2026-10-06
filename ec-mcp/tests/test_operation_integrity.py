from __future__ import annotations

import asyncio
import json

import pytest

from ec_mcp.config import Settings
from ec_mcp.server import create_server


def invoke(server, name, **arguments):
    return asyncio.run(server.call_tool(name, arguments)).content[0].text


@pytest.fixture()
def client_and_server(monkeypatch, tmp_path):
    import ec_mcp.server as server_module

    class FakeClient:
        def __init__(self):
            self.calls = []
            self.fail_reads = False

        def resolve_active_profile(self):
            return "9.6"

        def call(self, version, operation_id, path_params=None, json_body=None, **query):
            self.calls.append((operation_id, json_body, path_params, query))
            if self.fail_reads and operation_id == "orchestrator.getoverlay323":
                raise RuntimeError("status unavailable")
            return {"saved": True}

        def appliance_api_call(self, version, ne_pk, operation_id, **arguments):
            return self.call(version, operation_id, **arguments)

    fake = FakeClient()
    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args: fake)
    settings = Settings(allow_write_tools=True, max_writes_per_minute=1, audit_log_path=tmp_path / "audit.jsonl")
    return fake, create_server(settings), settings


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


@pytest.mark.parametrize("command", ["show version ; reboot", "show version\nreboot", "show version && reboot", "show version $(reboot)"])
def test_read_only_api_rejects_injection_before_transport(client_and_server, command):
    fake, server, settings = client_and_server
    settings.allow_write_tools = False
    response = invoke(server, "run_show_api", command=command, appliance_id="1.NE")
    assert response.startswith("Error:")
    assert fake.calls == []


def test_read_only_api_allows_safe_command_with_writes_disabled(client_and_server):
    fake, server, settings = client_and_server
    settings.allow_write_tools = False
    response = json.loads(invoke(server, "run_show_api", command="show version", appliance_id="1.NE"))
    assert response["transport"] == "orchestrator"
    assert fake.calls[0][1] == {"command": "show version"}


@pytest.mark.parametrize("operation,body", [
    ("appliance.clipost13533", {"command": "reboot"}),
    ("appliance.clipostmultiple548090", {"commands": ["show version", "reboot"]}),
    ("orchestrator.broadcastclipost154", {"command": "reboot", "nePks": ["1.NE"]}),
])
def test_every_cli_write_path_requires_dangerous_permission(client_and_server, operation, body):
    fake, server, _settings = client_and_server
    response = invoke(server, "apply_change", operation_id=operation, body_json=json.dumps(body), appliance_id="1.NE", confirm=True)
    assert "EC_ALLOW_DANGEROUS_WRITES=true" in response
    assert fake.calls == []


def test_cli_dangerous_permission_allows_one_confirmed_write(client_and_server):
    fake, server, settings = client_and_server
    settings.allow_dangerous_writes = True
    response = json.loads(invoke(server, "apply_change", operation_id="appliance.clipost13533", body_json='{"command":"reboot"}', appliance_id="1.NE", confirm=True))
    assert response["applied"] is True
    assert len(fake.calls) == 1


def test_ssh_reboot_rejected_before_connect(monkeypatch, client_and_server):
    import ec_mcp.server as server_module

    _fake, server, _settings = client_and_server

    class FakePool:
        def __init__(self, settings):
            pass

        def get(self, host):
            raise AssertionError("rejected command must not open an SSH session")

        def close_all(self):
            pass

    monkeypatch.setattr(server_module, "ApplianceSshPool", FakePool)
    response = invoke(server, "run_cli_command", command="reboot", host="192.0.2.1", confirm=True)
    assert "EC_ALLOW_DANGEROUS_WRITES=true" in response


@pytest.mark.parametrize("value,expected", [(0, "0"), (False, "false")])
def test_false_and_zero_query_values_survive_preflight(client_and_server, value, expected):
    _fake, server, _settings = client_and_server
    response = json.loads(invoke(server, "apply_change", operation_id="orchestrator.apptagspost90", extra_query_params_json=json.dumps({"mode": value})))
    assert response["would_execute"]["query"] == {"mode": expected}


def test_dry_runs_and_rejected_preflight_do_not_consume_quota(client_and_server):
    fake, server, _settings = client_and_server
    arguments = {"operation_id": "orchestrator.apptagspost90", "body_json": '[{"name":"Example"}]'}
    for _ in range(3):
        assert json.loads(invoke(server, "apply_change", **arguments))["dry_run"] is True
    rejected = invoke(server, "apply_change", **arguments, verify_operation_id="orchestrator.apptagspost90", confirm=True)
    assert "must be a GET" in rejected
    assert fake.calls == []
    assert json.loads(invoke(server, "apply_change", **arguments, confirm=True))["applied"] is True
    assert "Write rate limit reached" in invoke(server, "apply_change", **arguments, confirm=True)
    assert len(fake.calls) == 1


def test_failed_read_after_write_preserves_applied_result(client_and_server):
    fake, server, _settings = client_and_server
    fake.fail_reads = True
    response = json.loads(invoke(server, "apply_change", operation_id="orchestrator.apptagspost90", body_json='[{"name":"Example"}]', verify_operation_id="orchestrator.getoverlay323", confirm=True))
    assert response["applied"] is True
    assert response["read_after_write_status"] == "error"
    assert response["read_after_write_error"] == "status unavailable"
    assert [call[0] for call in fake.calls] == ["orchestrator.apptagspost90", "orchestrator.getoverlay323"]


def test_audit_redacts_cli_credentials_and_nested_details(tmp_path):
    from ec_mcp.audit import AuditLog

    log_path = tmp_path / "audit.jsonl"
    credentials = ["fixture-password-value", "fixture-psk-value", "fixture-api-value"]
    AuditLog(log_path).record(
        "run_cli_command", f'username admin password "{credentials[0]}"', "1.NE", "ok",
        details={"nested": [{"psk": credentials[1], "api_key": credentials[2]}]},
    )
    text = log_path.read_text()
    assert all(value not in text for value in credentials)
    assert json.loads(text)["target"] == "1.NE"


@pytest.mark.parametrize("tool", ["run_cli_command", "apply_change"])
@pytest.mark.parametrize("max_chars", [200, 12000])
def test_redacted_cli_dry_run_stays_valid_json(client_and_server, tool, max_chars):
    fake, server, settings = client_and_server
    settings.max_output_chars = max_chars
    credential = "fixture-command-credential"
    command = f'username admin password "{credential}"'
    if tool == "run_cli_command":
        response = invoke(server, tool, command=command)
    else:
        response = invoke(server, tool, operation_id="appliance.clipost13533", appliance_id="1.NE", body_json=json.dumps({"command": command}))
    assert json.loads(response)
    assert credential not in response
    assert credential not in settings.audit_log_path.read_text()
    assert fake.calls == []
