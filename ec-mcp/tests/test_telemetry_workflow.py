"""Tests for the infrastructure and real-time telemetry layer.

Covers:
- realtime stats body building and validation
- payload normalizers (realtime rows, interface state, disks, timeseries)
- MCP tool registration and end-to-end tool calls with a fake client
- operation id stability across the shipped profiles (9.3-9.6)
"""
import asyncio
import json

import pytest

from ec_mcp.compat import load_profiles
from ec_mcp.config import Settings
from ec_mcp.telemetry_workflow import (
    APPLIANCE_DISK_USAGE_READ,
    APPLIANCE_DISKS_READ,
    APPLIANCE_HEALTH_READ,
    APPLIANCE_REALTIME_STATS_READ,
    APPLIANCE_SYSTEM_INFO_READ,
    ORCHESTRATOR_APPLIANCE_PERFORMANCE_READ,
    ORCHESTRATOR_CPU_TIMESERIES_READ,
    ORCHESTRATOR_DB_PARTITION_READ,
    ORCHESTRATOR_DISK_SPACE_READ,
    ORCHESTRATOR_GMS_SERVER_INFO_READ,
    ORCHESTRATOR_INTERFACE_STATE_READ,
    ORCHESTRATOR_STATS_COLLECTOR_STATUS_READ,
    ORCHESTRATOR_STATS_RETENTION_READ,
    ORCHESTRATOR_VERSIONS_READ,
    build_realtime_stats_body,
    summarize_cpu_timeseries,
    summarize_disks,
    summarize_interface_state,
    summarize_performance_timeseries,
    summarize_realtime_stats,
)


def test_realtime_stats_body_defaults():
    body = build_realtime_stats_body("tunnel", "", "all", 10)
    assert body == {"filter": 0, "name": "", "type": "tunnel", "count": 10}


def test_realtime_stats_body_normalization():
    body = build_realtime_stats_body("  PORT ", "t1", "Average", 3)
    assert body["type"] == "port"
    assert body["name"] == "t1"
    assert body["filter"] == 1
    assert body["count"] == 3


@pytest.mark.parametrize("bad_type", ["bogus", "tunnels"])
def test_realtime_stats_body_rejects_invalid_type(bad_type):
    with pytest.raises(ValueError):
        build_realtime_stats_body(bad_type, "", "all", 5)


@pytest.mark.parametrize("bad_filter", ["median", "max"])
def test_realtime_stats_body_rejects_invalid_filter(bad_filter):
    with pytest.raises(ValueError):
        build_realtime_stats_body("tunnel", "", bad_filter, 5)


def test_realtime_stats_body_empty_type_defaults_to_tunnel():
    assert build_realtime_stats_body("", "", "all", 5)["type"] == "tunnel"


def test_realtime_stats_count_floor():
    assert build_realtime_stats_body("tunnel", "", "all", 0)["count"] == 1


def test_summarize_realtime_stats_unwraps_data():
    payload = {"data": [{"bps": 1}, {"bps": 2}]}
    assert summarize_realtime_stats(payload) == [{"bps": 1}, {"bps": 2}]


def test_summarize_realtime_stats_accepts_raw_list_and_scalar():
    assert summarize_realtime_stats([{"a": 1}]) == [{"a": 1}]
    assert summarize_realtime_stats({"stats": [{"b": 2}]}) == [{"b": 2}]


def test_summarize_interface_state():
    payload = {"interfaceState": [{"interfaceName": "1/1", "adminStatus": "up"}]}
    rows = summarize_interface_state(payload)
    assert rows == [{"interfaceName": "1/1", "adminStatus": "up"}]


def test_summarize_interface_state_falls_back_to_dict():
    rows = summarize_interface_state({"linkState": "up"})
    assert len(rows) == 1 and rows[0]["linkState"] == "up"


def test_summarize_disks():
    rows = summarize_disks({"disks": [{"name": "sda"}]})
    assert rows == [{"name": "sda"}]
    assert summarize_disks([{"name": "sdb"}]) == [{"name": "sdb"}]


def test_summarize_cpu_timeseries_keeps_latest_samples():
    payload = [{"nePk": "1.NE", "cpuUtilization": [1, 2, 3, 4, 5]}]
    rows = summarize_cpu_timeseries(payload, limit=2)
    assert rows[0]["latest_samples"] == [4, 5]
    assert "cpuUtilization" not in rows[0]


def test_summarize_performance_timeseries_keeps_latest_samples():
    payload = [{"nePk": "1.NE", "data": [{"t": 1}, {"t": 2}, {"t": 3}]}]
    rows = summarize_performance_timeseries(payload, limit=1)
    assert rows[0]["latest_samples"] == [{"t": 3}]
    assert "data" not in rows[0]


def test_operation_ids_stable_across_profiles():
    profiles = load_profiles(Settings.from_env().profiles_dir)
    versions = {p["version"] for p in profiles}
    assert {"9.3", "9.4", "9.5", "9.6"} <= versions
    required = {
        APPLIANCE_REALTIME_STATS_READ,
        APPLIANCE_HEALTH_READ,
        APPLIANCE_DISK_USAGE_READ,
        APPLIANCE_DISKS_READ,
        APPLIANCE_SYSTEM_INFO_READ,
        ORCHESTRATOR_APPLIANCE_PERFORMANCE_READ,
        ORCHESTRATOR_CPU_TIMESERIES_READ,
        ORCHESTRATOR_DB_PARTITION_READ,
        ORCHESTRATOR_DISK_SPACE_READ,
        ORCHESTRATOR_GMS_SERVER_INFO_READ,
        ORCHESTRATOR_INTERFACE_STATE_READ,
        ORCHESTRATOR_STATS_COLLECTOR_STATUS_READ,
        ORCHESTRATOR_STATS_RETENTION_READ,
        ORCHESTRATOR_VERSIONS_READ,
    }
    for profile in profiles:
        missing = required - set(profile["operations"])
        assert not missing, f"{profile['version']} missing: {sorted(missing)}"


def test_realtime_stats_operation_is_not_read_risk():
    """POST /stats/realtimeStats is catalogued as write-risk upstream; the MCP
    tool must call it with an explicit json_body (read-only semantics)."""
    profiles = load_profiles(Settings.from_env().profiles_dir)
    for profile in profiles:
        op = profile["operations"][APPLIANCE_REALTIME_STATS_READ]
        assert op["method"] == "POST"
        assert op["path"] == "/stats/realtimeStats"


def test_telemetry_tools_registered():
    from ec_mcp.server import create_server

    tools = [t.name for t in create_server()._tool_manager.list_tools()]
    for expected in (
        "get_orchestrator_infrastructure",
        "get_appliance_infrastructure",
        "get_realtime_stats",
        "get_appliance_health",
    ):
        assert expected in tools, f"{expected} missing; got {tools}"


class FakeTelemetryClient:
    """Fake OrchestratorClient recording every call for assertion."""

    def __init__(self):
        self.appliance_calls = []
        self.calls = []
        self.raw_paths = []

    def resolve_active_profile(self):
        return "9.6"

    def list_appliances(self, refresh=False):
        return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1", "serial_number": "001B"}]

    def call(self, version, operation_id, path_params=None, **query):
        self.calls.append((operation_id, query))
        if operation_id == ORCHESTRATOR_CPU_TIMESERIES_READ:
            return [{"nePk": query.get("nePk"), "cpuUtilization": [1, 2, 3]}]
        if operation_id == ORCHESTRATOR_APPLIANCE_PERFORMANCE_READ:
            return [{"nePk": query.get("nePk"), "data": [{"t": 1}, {"t": 2}]}]
        if operation_id == ORCHESTRATOR_INTERFACE_STATE_READ:
            return {"interfaceState": [{"interfaceName": "1/1"}]}
        if operation_id == "get_platforminfo":
            return {"platform": "ecs"}
        return {"data": []}

    def get_raw(self, path, **query):
        self.raw_paths.append(path)
        return {"value": "stub"}

    def appliance_api_call(self, version, ne_pk, operation_id, path_params=None, json_body=None, **query):
        self.appliance_calls.append((ne_pk, operation_id, json_body))
        if operation_id == APPLIANCE_REALTIME_STATS_READ:
            return {"stats": [{"name": "t1", "bps": 100}]}
        if operation_id == APPLIANCE_HEALTH_READ:
            return {"loss": 0, "latency": 2, "jitter": 1, "mos": 440}
        if operation_id == APPLIANCE_DISK_USAGE_READ:
            return {"used": 10}
        if operation_id == APPLIANCE_DISKS_READ:
            return {"disks": [{"name": "sda"}]}
        return {"info": "ok"}


def _run_tool(tool_name, arguments, fake):
    import ec_mcp.server as server_module

    original = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        result = asyncio.run(server_module.create_server().call_tool(tool_name, arguments))
    finally:
        server_module.OrchestratorClient = original
    return result.content[0].text


def test_get_realtime_stats_tool_end_to_end():
    fake = FakeTelemetryClient()
    text = _run_tool(
        "get_realtime_stats",
        {"appliance_id": "EC1", "target_type": "tunnel", "name": "t1", "filter_mode": "average", "count": 5},
        fake,
    )
    payload = json.loads(text)
    assert payload["nePk"] == "1.NE"
    assert payload["samples"] == [{"name": "t1", "bps": 100}]
    assert fake.appliance_calls == [
        ("1.NE", APPLIANCE_REALTIME_STATS_READ, {"filter": 1, "name": "t1", "type": "tunnel", "count": 5})
    ]


def test_get_realtime_stats_tool_rejects_invalid_type():
    fake = FakeTelemetryClient()
    text = _run_tool("get_realtime_stats", {"appliance_id": "EC1", "target_type": "bogus"}, fake)
    assert text.startswith("Error")
    assert fake.appliance_calls == []


def test_get_appliance_health_tool_end_to_end():
    fake = FakeTelemetryClient()
    text = _run_tool("get_appliance_health", {"appliance_id": "all"}, fake)
    payload = json.loads(text)
    assert payload["appliances"][0]["health"]["mos"] == 440
    assert payload["appliances"][0]["disk_usage"] == {"used": 10}
    assert payload["appliances"][0]["disks"] == [{"name": "sda"}]
    operations = {op for _, op, _ in fake.appliance_calls}
    assert {APPLIANCE_HEALTH_READ, APPLIANCE_SYSTEM_INFO_READ, APPLIANCE_DISK_USAGE_READ, APPLIANCE_DISKS_READ} <= operations


def test_get_appliance_infrastructure_tool_end_to_end():
    fake = FakeTelemetryClient()
    text = _run_tool("get_appliance_infrastructure", {"appliance_id": "1.NE"}, fake)
    payload = json.loads(text)
    entry = payload["appliances"][0]
    assert entry["cpu_timeseries"][0]["latest_samples"] == [1, 2, 3]
    assert entry["performance_timeseries"][0]["latest_samples"] == [{"t": 1}, {"t": 2}]
    assert entry["interfaces"] == [{"interfaceName": "1/1"}]


def test_get_orchestrator_infrastructure_tool_end_to_end():
    fake = FakeTelemetryClient()
    text = _run_tool("get_orchestrator_infrastructure", {}, fake)
    payload = json.loads(text)
    assert "gms_server" in payload
    assert "versions" in payload
    assert "disk_space" in payload
    assert "db_partitions" in payload
    assert "stats_collectors" in payload
    assert payload["platform"]["platform_info"] == {"platform": "ecs"}
    called = {op for op, _ in fake.calls}
    assert {ORCHESTRATOR_GMS_SERVER_INFO_READ, ORCHESTRATOR_VERSIONS_READ} <= called


def test_get_orchestrator_infrastructure_falls_back_to_raw_for_older_versions():
    class FakeOldClient(FakeTelemetryClient):
        def resolve_active_profile(self):
            return "9.5"

        def call(self, version, operation_id, path_params=None, **query):
            self.calls.append((operation_id, query))
            return {"data": []}

    fake = FakeOldClient()
    text = _run_tool("get_orchestrator_infrastructure", {}, fake)
    payload = json.loads(text)
    assert payload["platform"]["platform_info"] == {"value": "stub"}
    assert any("/stats/infrastructure/" in p for p in fake.raw_paths)
