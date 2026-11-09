"""Regression tests for the QA remediation findings (H1-H5, H10).

Covers:
- H10: call_read_api/apply_change route to the explicitly selected target and
  reject unknown targets without silently falling back to the default.
- H1: get_orchestrator_infrastructure survives payloads whose "versions"
  section is a dict of lists and exceeds the output budget.
- H2: propose_remediation records audit entries with the required `result`
  argument and never raises the AuditLog signature error.
- H3: get_brownout_state reports ERROR/PARTIAL when upstream queries fail
  instead of labelling the failure SKIPPED_NO_ENTITY.
- H4: SSH appliance resolution matches management/LAN/WAN IPs from the
  inventory, not only nePk/name/serial.
- H5: call_read_api maps start_time/end_time to from/to for alarm endpoints.
"""

from __future__ import annotations

import asyncio
import json

import pytest

import ec_mcp.server as server_module
from ec_mcp.config import Settings
from ec_mcp.security import SecurityError
from ec_mcp.ssh_ecos import resolve_appliance_network_path

TARGETS_BLOB = json.dumps(
    {
        "orch-a": {"url": "https://a.example.com", "api_key": "key-a"},
        "orch-b": {"url": "https://b.example.com", "api_key": "key-b"},
    }
)


class FakeTargetClient:
    """Fake OrchestratorClient that identifies its target by settings URL."""

    def __init__(self, settings, engine=None, client=None, *, target_name="default"):
        self.settings = settings
        self.target_name = target_name
        self.calls: list[tuple[str, dict]] = []
        self.raw_calls: list[str] = []

    @property
    def is_b(self) -> bool:
        return "b.example" in (self.settings.orchestrator_url or "")

    def resolve_active_profile(self) -> str:
        return "9.6"

    def detect_version(self) -> str:
        return "9.7.0.1"

    def list_appliances(self, refresh=False):
        if self.is_b:
            return [{"nePk": "9.NE", "name": "B-APPLIANCE", "ip": "10.9.0.9", "serial_number": "SB"}]
        return [{"nePk": "1.NE", "name": "A-APPLIANCE", "ip": "10.0.0.1", "serial_number": "SA"}]

    def call(self, version, operation_id, path_params=None, json_body=None, **query):
        self.calls.append((operation_id, dict(query)))
        if operation_id == "orchestrator.inventory.summary":
            return self.list_appliances()
        if operation_id == "orchestrator.versioninfo357":
            return {"versions": [{"v": "9.7", "pad": "y" * 200}] * 300}
        if operation_id == "orchestrator.getapproximatediskspace333":
            return {"partitions": [{"p": i, "pad": "z" * 200} for i in range(500)]}
        return {"data": []}

    def get_raw(self, path, **query):
        self.raw_calls.append(path)
        if "brownout" in path:
            raise RuntimeError("Orchestrator returned HTTP 403 for GET /gms/rest/stats/aggregate/brownout")
        return {"data": []}

    def appliance_api_get(self, ne_pk, path, **query):
        self.raw_calls.append(path)
        if "brownout" in path or path == "/tunnelsConfigAndState":
            raise RuntimeError("Orchestrator returned HTTP 403")
        return {"data": []}

    def appliance_api_call(self, version, ne_pk, operation_id, path_params=None, json_body=None, **query):
        self.calls.append((operation_id, dict(query)))
        return {"data": []}


def _run_tool(tool_name, arguments, monkeypatch, *, allow_writes=False):
    monkeypatch.setenv("EC_ORCHESTRATORS_JSON", TARGETS_BLOB)
    if allow_writes:
        monkeypatch.setenv("EC_ALLOW_WRITE_TOOLS", "true")
    created = []

    def factory(settings, engine=None, client=None, *, target_name="default"):
        fake = FakeTargetClient(settings, target_name=target_name)
        created.append(fake)
        return fake

    original = server_module.OrchestratorClient
    server_module.OrchestratorClient = factory
    try:
        result = asyncio.run(server_module.create_server().call_tool(tool_name, arguments))
    finally:
        server_module.OrchestratorClient = original
    return result.content[0].text, created


def test_call_read_api_routes_to_selected_target(monkeypatch):
    text, _ = _run_tool(
        "call_read_api",
        {"operation_id": "orchestrator.inventory.summary", "target": "orch-b"},
        monkeypatch,
    )
    payload = json.loads(text)
    ne_pks = {row["nePk"] for row in payload["data"]}
    names = {row.get("name") or row.get("hostName") for row in payload["data"]}
    assert ne_pks == {"9.NE"}
    assert names == {"B-APPLIANCE"}


def test_call_read_api_rejects_unknown_target_without_fallback(monkeypatch):
    text, _ = _run_tool(
        "call_read_api",
        {"operation_id": "orchestrator.inventory.summary", "target": "does-not-exist"},
        monkeypatch,
    )
    assert "does-not-exist" in text
    assert "not configured" in text
    assert "A-APPLIANCE" not in text
    assert "B-APPLIANCE" not in text


def test_apply_change_dry_run_includes_target(monkeypatch):
    text, _ = _run_tool(
        "apply_change",
        {
            "operation_id": "orchestrator.savechanges73",
            "body_json": json.dumps({"nePks": ["9.NE"]}),
            "target": "orch-b",
        },
        monkeypatch,
        allow_writes=True,
    )
    payload = json.loads(text)
    assert payload["dry_run"] is True
    assert payload["would_execute"]["target"] == "orch-b"


def test_get_orchestrator_infrastructure_tolerates_list_versions(monkeypatch):
    text, _ = _run_tool("get_orchestrator_infrastructure", {"target": "orch-a"}, monkeypatch)
    assert not text.startswith("Error:")
    payload = json.loads(text)
    assert "gms_server" in payload or payload.get("truncated") is True


def test_propose_remediation_records_audit_without_signature_error(monkeypatch):
    text, _ = _run_tool(
        "propose_remediation",
        {"appliance_id": "1.NE", "target": "orch-a"},
        monkeypatch,
    )
    assert not text.startswith("Error:")
    payload = json.loads(text)
    assert payload["applied"] is False
    assert payload["requires_human_confirmation"] is True


def test_get_brownout_state_reports_error_not_absence(monkeypatch):
    text, _ = _run_tool(
        "get_brownout_state",
        {"appliance_id": "1.NE", "target": "orch-a"},
        monkeypatch,
    )
    payload = json.loads(text)
    assert payload["status"] == "ERROR"
    assert "error" in payload["appliances"][0]
    assert payload["status"] != "SKIPPED_NO_ENTITY"


def test_call_read_api_maps_alarm_window_params(monkeypatch):
    text, created = _run_tool(
        "call_read_api",
        {
            "operation_id": "orchestrator.alarmgms25",
            "start_time": "1762651200",
            "end_time": "1762737600",
            "target": "orch-a",
        },
        monkeypatch,
    )
    payload = json.loads(text)
    assert payload["request_echo"]["query_used"].get("from") == "1762651200"
    assert payload["request_echo"]["query_used"].get("to") == "1762737600"
    queries = [dict(query) for _, query in created[0].calls]
    assert any(query.get("from") == "1762651200" and query.get("to") == "1762737600" for query in queries)


def test_resolve_appliance_network_path_matches_inventory_ips():
    settings = Settings()
    inventory = [
        {
            "nePk": "1.NE",
            "name": "EC1",
            "ip": "10.0.0.1",
            "serial_number": "001B",
            "wan_ips": ["203.0.113.10"],
        }
    ]
    path = resolve_appliance_network_path("10.0.0.1", settings, inventory)
    assert path.target_ip in {"10.0.0.1", "203.0.113.10"}
    path_by_wan = resolve_appliance_network_path("203.0.113.10", settings, inventory)
    assert path_by_wan.target_ip == "203.0.113.10"
    with pytest.raises(SecurityError):
        resolve_appliance_network_path("198.51.100.99", settings, inventory)


def test_apply_change_omitted_target_warns_in_multi_target(monkeypatch):
    text, _ = _run_tool(
        "apply_change",
        {"operation_id": "orchestrator.savechanges73", "body_json": "{}"},
        monkeypatch,
        allow_writes=True,
    )
    payload = json.loads(text)
    assert payload["dry_run"] is True
    assert "target omitted in a multi-target deployment" in payload["would_execute"]["warning"]
    assert payload["would_execute"]["target"] in {"orch-a", "orch-b"}


def test_apply_change_simulated_confirm_uses_same_client(monkeypatch):
    created = []

    def factory(settings, engine=None, client=None, *, target_name="default"):
        fake = FakeTargetClient(settings, target_name=target_name)
        created.append(fake)
        return fake

    monkeypatch.setenv("EC_ORCHESTRATORS_JSON", TARGETS_BLOB)
    monkeypatch.setenv("EC_ALLOW_WRITE_TOOLS", "true")
    original = server_module.OrchestratorClient
    server_module.OrchestratorClient = factory
    try:
        result = asyncio.run(
            server_module.create_server().call_tool(
                "apply_change",
                {
                    "operation_id": "orchestrator.savechanges73",
                    "body_json": json.dumps({"nePks": ["9.NE"]}),
                    "verify_operation_id": "orchestrator.getalarmsconfig7",
                    "confirm": True,
                    "target": "orch-b",
                },
            )
        )
    finally:
        server_module.OrchestratorClient = original
    payload = json.loads(result.content[0].text)
    assert payload["applied"] is True
    assert payload["read_after_write"] is not None
    write_clients = {c.target_name for c in created if any(op == "orchestrator.savechanges73" for op, _ in c.calls)}
    verify_clients = {c.target_name for c in created if any(op == "orchestrator.getalarmsconfig7" for op, _ in c.calls)}
    assert write_clients == {"orch-b"}
    assert verify_clients == {"orch-b"}


def test_orchestrator_info_reports_effective_ssh_state_per_target(monkeypatch):
    monkeypatch.setenv("EC_SSH_ENABLED", "true")
    text, _ = _run_tool("orchestrator_info", {"target": "orch-a"}, monkeypatch)
    payload = json.loads(text)
    assert payload["ssh_enabled"] is False
    assert payload["ssh_enabled_global"] is True

    blob_with_ssh = json.dumps(
        {
            "orch-a": {"url": "https://a.example.com", "api_key": "k", "ssh_user": "u", "ssh_password": "p"},
        }
    )
    monkeypatch.setenv("EC_ORCHESTRATORS_JSON", blob_with_ssh)
    original = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeTargetClient(*a, **k)
    try:
        result = asyncio.run(server_module.create_server().call_tool("orchestrator_info", {"target": "orch-a"}))
    finally:
        server_module.OrchestratorClient = original
    payload = json.loads(result.content[0].text)
    assert payload["ssh_enabled"] is True
    assert payload["ssh_enabled_global"] is True


def test_call_read_api_warns_on_seconds_scale_alarm_window(monkeypatch):
    text, _ = _run_tool(
        "call_read_api",
        {"operation_id": "orchestrator.alarmgms25", "start_time": "1780348800", "end_time": "1788297600", "target": "orch-a"},
        monkeypatch,
    )
    payload = json.loads(text)
    assert "epoch SECONDS" in payload["request_echo"]["warning"]

    text, _ = _run_tool(
        "call_read_api",
        {"operation_id": "orchestrator.alarmgms25", "start_time": "1780348800000", "end_time": "1788297600000", "target": "orch-a"},
        monkeypatch,
    )
    payload = json.loads(text)
    assert "warning" not in payload["request_echo"]


def test_get_appliance_infrastructure_sends_traffictype(monkeypatch):
    text, created = _run_tool(
        "get_appliance_infrastructure",
        {"appliance_id": "1.NE", "target": "orch-a"},
        monkeypatch,
    )
    assert not text.startswith("Error:")
    queries = [dict(query) for _, query in created[0].calls]
    assert any(
        query.get("trafficType") == "all_traffic" and query.get("granularity") == "hour"
        for query in queries
    )
