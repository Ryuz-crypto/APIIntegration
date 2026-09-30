
import pathlib
from typing import ClassVar

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.security import SecurityError, validate_show_command

PROFILES = pathlib.Path(__file__).parent.parent / "ec_mcp" / "profiles"


def test_load_profiles():
    profiles = load_profiles(PROFILES)
    versions = {p["version"] for p in profiles}
    assert {"9.3", "9.4", "9.5", "9.6"} <= versions


def test_resolve_and_version_match():
    engine = CompatibilityEngine(load_profiles(PROFILES))
    assert engine.match_version("9.6.4") == "9.6"
    assert engine.match_version("9.7.1") == "9.6"
    resolved = engine.resolve("9.6", "orchestrator.topology")
    assert resolved.method == "GET"
    resolved_interface = engine.resolve("9.6", "appliance.interfaces", {"appliance_id": "1.NE"})
    assert resolved_interface.path == "/interfaceState/1.NE"


def test_path_rendering():
    from ec_mcp.compat import render_path
    assert render_path("/interfaceState/{appliance_id}", {"appliance_id": "3.NE"}) == "/interfaceState/3.NE"
    try:
        render_path("/interfaceState/{appliance_id}", {})
        raise AssertionError("should have raised")
    except Exception as error:
        assert "Missing" in str(error)


def test_whitelist_accepts_show():
    for command in ("show bgp neighbors", "show ipsec sa", "show vrrp interface", "show mpls ldp session"):
        assert validate_show_command(command).startswith("show")
    assert validate_show_command("show version").startswith("show")
    assert validate_show_command("  show tunnel stats ").startswith("show")


def test_whitelist_rejects_dangerous():
    for command in [
        "terminal length 0",
        "config",
        "set admin password x",
        "reboot",
        "clear session all",
        "show version; reboot",
        "show version && whoami",
    ]:
        try:
            validate_show_command(command)
            raise AssertionError(f"should have rejected: {command}")
        except SecurityError:
            pass


def test_official_show_catalog_accepted():
    assert validate_show_command("show interfaces tunnel").startswith("show")
    assert validate_show_command("show stats tunnel").startswith("show")
    assert validate_show_command("show overlay").startswith("show")
    assert validate_show_command("show tech-support").startswith("show")
    assert validate_show_command("show ip-tracking").startswith("show")


def test_show_unknown_command_rejected():
    for command in ["show supersecret", "showx version"]:
        try:
            validate_show_command(command)
            raise AssertionError(f"should have rejected: {command}")
        except SecurityError:
            pass


def test_denied_patterns_still_reject():
    for command in [
        "show version; reboot",
        "show version && whoami",
        "show config",
        "show version | terminal length 0",
    ]:
        try:
            validate_show_command(command)
            raise AssertionError(f"should have rejected: {command}")
        except SecurityError:
            pass


def test_cli_catalog_over_1000_commands():
    from ec_mcp.cli_catalog import catalog_entries, total_commands

    assert total_commands() >= 1000
    entries = catalog_entries()
    assert len(entries) == total_commands()
    risks = {e["risk"] for e in entries}
    assert risks == {"read", "diagnostic", "write"}
    categories = {e["category"] for e in entries}
    assert categories == {"monitoring", "troubleshooting", "alarm", "administration", "configuration", "negation"}


def test_classify_cli_command():
    from ec_mcp.cli_catalog import catalog_entries

    risk_by_command = {e["command"]: e["risk"] for e in catalog_entries()}

    def classify(command: str) -> str | None:
        lowered = command.strip().lower()
        for entry in sorted(risk_by_command, key=len, reverse=True):
            if lowered == entry or lowered.startswith(entry + " "):
                return risk_by_command[entry]
        return None

    assert classify("show version") == "read"
    assert classify("show interfaces tunnel 1/2") == "read"
    assert classify("ping 10.0.0.1") == "diagnostic"
    assert classify("interface shutdown 1") == "write"
    assert classify("no interface shutdown 1") == "write"
    assert classify("configure terminal") == "write"
    assert classify("show fakecommand123") is None
    assert classify("rm -rf /") is None


def test_list_api_operations_tool():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server
    server = create_server()
    result = asyncio.run(server.call_tool("list_api_operations", {"version": "9.6", "page_size": 20}))
    text = result.content[0].text
    payload = jsonlib.loads(text)
    assert '"operation"' in text and '"method"' in text and '"path"' in text
    assert payload["truncated"] is False
    assert "body_example" not in text
    assert not text.startswith("Error")


def test_list_api_operations_paginated():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()
    result = asyncio.run(server.call_tool("list_api_operations", {"version": "9.6", "page_size": 50, "page": 0}))
    payload = jsonlib.loads(result.content[0].text)
    body = payload["versions"]["9.6"]
    assert body["page"] == 0
    assert body["total_operations"] > 500
    assert len(body["operations"]) == 50
    assert body["has_more_page"] is True
    next_result = asyncio.run(
        server.call_tool("list_api_operations", {"version": "9.6", "page_size": 50, "page": 0, "search": "licensed"})
    )
    next_body = jsonlib.loads(next_result.content[0].text)["versions"]["9.6"]
    assert "retrieves_portal_licensed_appliances" in next_body["operations"]
    assert next_body["page"] == 0


def test_list_appliances_ne_pk_resolution():
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def __init__(self):
            self.last_proxy_call = None

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self):
            return [
                {"nePk": "0.NE", "name": "ECV-CALIMAYA", "ip": "192.168.1.40"},
                {"nePk": "14.NE", "name": "ECV-BOGOTA", "ip": "192.168.2.10"},
            ]

        def appliance_api_get(self, ne_pk, appliance_path, **query):
            self.last_proxy_call = {"nePk": ne_pk, "url": appliance_path, **query}
            return {"ok": True, "interfaces": []}

        def call(self, *args, **kwargs):
            raise AssertionError("should have been proxied via appliance_api_get")

    from ec_mcp import server as server_module

    fake = FakeClient()
    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        import asyncio

        result = asyncio.run(server.call_tool("call_read_api", {"operation_id": "appliance.interfaces", "appliance_id": "ecv-bogota"}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert fake.last_proxy_call["nePk"] == "14.NE"
    assert fake.last_proxy_call["url"] == "/interfaceState/14.NE"
    assert "{appliance_id}" not in fake.last_proxy_call["url"]
    assert payload["truncated"] is False
    assert payload["request_echo"]["operation_id"] == "appliance.interfaces"
    assert payload["data"]["ok"] is True


def test_call_read_api_operation_not_found_suggestions():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(server.call_tool("call_read_api", {"operation_id": "get_all_appliances"}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert payload["error"] == "OPERATION_NOT_FOUND"
    assert isinstance(payload["suggestions"], list) and payload["suggestions"]


def test_call_read_api_param_required_preflight():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, *a, **k):
            raise AssertionError("preflight should have prevented the upstream call")

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(
            server.call_tool("call_read_api", {"operation_id": "appliance.applianceaggregate608094"})
        )
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert payload["error"] == "PARAM_REQUIRED"
    assert "granularity" in payload["required_params"]


def test_get_raw_caches_and_collects_metrics(monkeypatch):
    from ec_mcp.orchestrator_client import OrchestratorClient

    class FakeEngine:
        pass

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.content = b"x" * 16

        def json(self):
            return self._payload

    class FakeHttpx:
        def __init__(self):
            self.calls = []

        def get(self, path, headers=None, params=None):
            self.calls.append((path, dict(params or {})))
            return FakeResponse(200, {"data": [self.calls.count((path, dict(params or {})))]})

    class FakeSettings:
        orchestrator_url = "https://orch.example"
        verify_tls = True
        api_cache_ttl = 30.0

    fake = FakeHttpx()
    client = OrchestratorClient.__new__(OrchestratorClient)
    client._settings = FakeSettings()
    client._engine = FakeEngine()
    client._api_key = "k"
    client._client = fake
    client._cached_profile = None
    client._appliances_cache = None
    client._response_cache = {}
    client._cache_ttl = 30.0
    client._cache_max_entries = 128
    client._metrics = {}

    first = client.get_raw("/flow", nePk="0.NE")
    second = client.get_raw("/flow", nePk="0.NE")
    assert first == second
    assert len(fake.calls) == 1
    metrics = client.metrics()["/flow"]
    assert metrics["calls"] == 2
    assert metrics["cache_hits"] == 1


def test_get_raw_raises_on_http_error():
    from ec_mcp.orchestrator_client import OrchestratorClient

    class FakeResponse:
        status_code = 404
        content = b"not found"
        text = "not found"
        headers: ClassVar[dict] = {"content-type": "text/plain"}

        class request:
            url = type("U", (), {"params": {}})()

    class FakeHttpx:
        def get(self, path, headers=None, params=None):
            return FakeResponse()

    client = OrchestratorClient.__new__(OrchestratorClient)
    client._client = FakeHttpx()
    client._api_key = "k"
    client._response_cache = {}
    client._cache_ttl = 30.0
    client._cache_max_entries = 128
    client._metrics = {}
    try:
        client.get_raw("/missing")
        raise AssertionError("should have raised")
    except RuntimeError as error:
        assert "404" in str(error)


def test_kpi_tools_registered():
    import ec_mcp.server as server_module

    mcp = server_module.create_server()
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    for expected in (
        "get_wan_health",
        "get_mos",
        "get_brownout_state",
        "get_tunnel_state",
        "get_top_talkers",
        "get_availability",
        "orchestrator_metrics",
        "list_appliances",
    ):
        assert expected in tools, f"{expected} not registered; got {tools}"


def test_catalog_index_mode_and_default_version():
    import ec_mcp.server as server_module

    mcp = server_module.create_server()
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert "get_active_alarms" in tools
    schema = tools["list_api_operations"].parameters
    assert "mode" in schema.get("properties", {})


def test_empty_404_semantics():
    from ec_mcp.orchestrator_client import OrchestratorClient

    class FakeResponse:
        status_code = 404
        content = b"No application groups configured"
        text = "No application groups configured"
        headers: ClassVar[dict] = {"content-type": "text/plain"}

        class request:
            url = type("U", (), {"params": {}})()

    class FakeHttpx:
        def get(self, path, headers=None, params=None):
            return FakeResponse()

    client = OrchestratorClient.__new__(OrchestratorClient)
    client._client = FakeHttpx()
    client._api_key = "k"
    client._response_cache = {}
    client._cache_ttl = 30.0
    client._cache_max_entries = 128
    client._metrics = {}
    result = client.get_raw("/applicationGroups")
    assert result.get("data") is None
    assert "empty" in result.get("reason", "")


def test_new_kpi_tools_registered():
    import ec_mcp.server as server_module

    mcp = server_module.create_server()
    tools = [t.name for t in mcp._tool_manager.list_tools()]
    for expected in ("get_ha_status", "get_firmware_compliance", "get_ztp_status", "get_active_alarms"):
        assert expected in tools, f"{expected} missing; got {tools}"
