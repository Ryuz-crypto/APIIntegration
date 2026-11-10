
import json as jsonlib
import pathlib
from typing import ClassVar

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.security import SecurityError, validate_show_command

PROFILES = pathlib.Path(__file__).parent.parent / "ec_mcp" / "profiles"


def test_load_profiles():
    profiles = load_profiles(PROFILES)
    versions = {p["version"] for p in profiles}
    assert {"9.3", "9.4", "9.5", "9.6", "10.0"} <= versions


def test_resolve_and_version_match():
    engine = CompatibilityEngine(load_profiles(PROFILES))
    assert engine.match_version("9.6.4") == "9.6"
    assert engine.match_version("9.7.1") == "9.6"
    assert engine.match_version("10.0.0.40204") == "10.0"
    assert engine.match_version("10.1.2.3") == "10.0"
    assert engine.match_version("11.0.0") == "10.0"
    assert engine.match_version("9.2.1") is None
    assert engine.match_version("garbage") is None
    resolved = engine.resolve("9.6", "orchestrator.topology")
    assert resolved.method == "GET"
    resolved_interface = engine.resolve("9.6", "appliance.interfaces", {"appliance_id": "1.NE"})
    assert resolved_interface.path == "/interfaceState/1.NE"


def test_profile_10_0_operations():
    engine = CompatibilityEngine(load_profiles(PROFILES))
    profile = engine._profiles["10.0"]
    operations = profile["operations"]
    expected = [
        ("orchestrator.searchallbondedtunnels889", "GET", "/tunnels2/bonded"),
        ("orchestrator.flows242", "GET", "/flow"),
        ("orchestrator.appliancegetapi70", "GET", "/appliance/rest"),
        ("appliance.health", "POST", "/health"),
        ("orchestrator.getalldiscoveredappliances52", None, None),
    ]
    for operation_id, method, path in expected:
        assert operation_id in operations, operation_id
        if method:
            entry = operations[operation_id]
            assert entry["method"] == method
            assert entry["path"] == path
    resolved = engine.resolve("10.0", "orchestrator.flows242")
    assert resolved.path == "/flow"


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
            server.call_tool(
                "call_read_api",
                {"operation_id": "orchestrator.stats_timeseries_appliance665", "appliance_id": "0.NE", "start_time": "1", "end_time": "2"},
            )
        )
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert payload["error"] == "PARAM_REQUIRED"
    assert "granularity" in payload["required_params"]


def test_call_read_api_static_stats_getter_does_not_demand_granularity():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, *a, **k):
            return {"hostname": "lac-wan-sewan-orchge-useast1.silverpeak.cloud"}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(server.call_tool("call_read_api", {"operation_id": "get_hostname"}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert payload["truncated"] is False
    assert payload["data"]["hostname"].startswith("lac-wan")


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
    client._api_root = "/gms/rest"
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
    client._api_root = "/gms/rest"
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
    client._api_root = "/gms/rest"
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


def test_list_appliances_prefers_full_inventory_and_redacts_credentials():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def __init__(self):
            self.refreshed = False

        def list_appliances(self, refresh=False):
            self.refreshed = refresh
            return [
                {"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"},
                {"nePk": "0.NE", "name": "EC2", "ip": "10.0.0.2"},
            ]

    from ec_mcp import server as server_module

    fake = FakeClient()
    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        result = asyncio.run(server.call_tool("list_appliances", {}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert payload["count"] == 2
    assert fake.refreshed is True
    assert {a["nePk"] for a in payload["appliances"]} == {"1.NE", "0.NE"}


def test_inventory_parser_skips_empty_approved_list():
    from ec_mcp.orchestrator_client import OrchestratorClient

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload
            self.content = json.dumps(payload).encode()

        def json(self):
            return self._payload

    class FakeHttpx:
        def __init__(self):
            self.paths = []

        def get(self, path, headers=None, params=None):
            self.paths.append(path)
            if path == "/gms/rest/appliance":
                return FakeResponse({"data": [
                    {"nePk": "1.NE", "hostName": "EC1", "password": "x", "userName": "admin"},
                ], "truncated": False})
            return FakeResponse([])

    class FakeEngine:
        pass

    class FakeSettings:
        orchestrator_url = "https://orch.example"
        verify_tls = True
        api_cache_ttl = 30.0

    import json

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
    client._api_root = "/gms/rest"
    client._metrics = {}

    appliances = client.list_appliances(refresh=True)
    assert fake.paths[0] == "/gms/rest/appliance"
    assert len(appliances) == 1
    assert appliances[0]["nePk"] == "1.NE"
    assert appliances[0]["name"] == "EC1"


def test_get_active_alarms_all_expands_inventory_and_aggregates():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    COUNTS = {
        "1.NE": {"critical": 1, "warning": 3, "major": 3},
        "0.NE": {"critical": 0, "warning": 2, "major": 2},
        "2.NE": {"critical": 1, "warning": 2, "major": 3},
        "3.NE": {"critical": 1, "warning": 3, "major": 3},
        "14.NE": {"critical": 2, "warning": 3, "major": 2},
        "4.NE": {"critical": 0, "warning": 1, "major": 1},
    }
    LIVE_TOTAL = sum(sum(c.values()) for c in COUNTS.values())

    class FakeClient:
        def list_appliances(self):
            return [{"nePk": k} for k in COUNTS]

        def get_raw(self, path, **query):
            ne_pk = query.get("nePk")
            rows = [{"nePk": ne_pk, "severity": severity, "numOfAlarms": count} for severity, count in COUNTS[ne_pk].items()]
            return {"data": rows}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(server.call_tool("get_active_alarms", {"appliance_id": "all"}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    data = payload["data"]
    assert len(data["per_appliance"]) == 6
    assert data["total_alarms"] == LIVE_TOTAL
    assert data["by_severity"]["critical"] == sum(c["critical"] for c in COUNTS.values())
    assert all(row["total"] > 0 for row in data["per_appliance"])


def test_wan_health_all_expands_inventory():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def list_appliances(self):
            return [{"nePk": "1.NE"}, {"nePk": "0.NE"}]

        def get_raw(self, path, **query):
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(server.call_tool("get_wan_health", {"appliance_id": "all"}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert len(payload["appliances"]) == 2
    assert {row["nePk"] for row in payload["appliances"]} == {"1.NE", "0.NE"}


def test_call_read_api_does_not_inject_ne_pk_for_undeclared_ops():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self):
            return []

        def call(self, version, operation_id, path_params=None, **query):
            self.last_query = dict(query)
            return {"data": {"roleOptions": []}}

    from ec_mcp import server as server_module

    fake = FakeClient()
    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        result = asyncio.run(
            server.call_tool("call_read_api", {"operation_id": "get_role_options", "appliance_id": "1.NE"})
        )
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(text)
    assert payload["truncated"] is False
    assert "nePk" not in fake.last_query


def test_redact_secrets_covers_json_credentials():
    import json as jsonlib

    from ec_mcp.security import redact_secrets

    payload = {
        "data": [
            {"nePk": "1.NE", "hostName": "EC1", "password": "topsecret", "userName": "admin"}
        ],
        "request_echo": {},
    }
    text = redact_secrets(jsonlib.dumps(payload), [])
    assert "topsecret" not in text
    assert "admin" not in text
    assert "***REDACTED***" in text


def test_qa_acceptance_six_tests_against_simulated_97_orchestrator():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    NE_PKS = ["1.NE", "0.NE", "2.NE", "3.NE", "14.NE", "4.NE"]
    ALARM_COUNTS = {"1.NE": 7, "0.NE": 4, "2.NE": 6, "3.NE": 7, "14.NE": 7, "4.NE": 2}
    INVENTORY = [
        {
            "nePk": ne,
            "hostName": f"EC-{ne}",
            "model": "ECV",
            "site": "site",
            "ipAddress": f"10.0.0.{i}",
            "softwareVersion": "9.7.1",
            "state": 1,
            "password": "example-not-a-real-password-token",
            "userName": "admin",
        }
        for i, ne in enumerate(NE_PKS)
    ]

    class Fake97Orchestrator:
        def __init__(self):
            self.alarm_queries = []

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [
                {"nePk": a["nePk"], "name": a["hostName"], "ip": a["ipAddress"]}
                for a in INVENTORY
            ]

        def call(self, version, operation_id, path_params=None, **query):
            self.last_call = {"operation_id": operation_id, "query": dict(query)}
            if operation_id == "orchestrator.inventory.summary":
                return {"data": INVENTORY, "request_echo": {}, "truncated": False}
            return {"data": []}

        def get_raw(self, path, **query):
            self.raw_paths = [*getattr(self, "raw_paths", []), path]
            if path == "/gms/rest/appliance":
                return {"data": INVENTORY, "request_echo": {}, "truncated": False}
            if path in ("/alarm/count/appliance", "/gms/rest/alarm/count/appliance"):
                ne_pk = query.get("nePk")
                if ne_pk and ne_pk not in ALARM_COUNTS:
                    return {"data": []}
                count = ALARM_COUNTS.get(ne_pk, 0)
                return {"data": [
                    {"nePk": ne_pk, "severity": "critical", "numOfAlarms": 1},
                    {"nePk": ne_pk, "severity": "warning", "numOfAlarms": min(2, max(0, count - 2))},
                    {"nePk": ne_pk, "severity": "major", "numOfAlarms": max(0, count - 3)},
                ]}
            if path.startswith("/stats/"):
                return {"data": []}
            return {"data": []}

        def appliance_api_get(self, ne_pk, appliance_path, **query):
            return {"data": []}

    fake = Fake97Orchestrator()

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        async def run(tool, args):
            result = await server.call_tool(tool, args)
            return jsonlib.loads(result.content[0].text)

        qa1 = asyncio.run(run("list_appliances", {}))
        qa2 = asyncio.run(run("get_active_alarms", {"appliance_id": "all"}))
        qa3 = asyncio.run(run("get_wan_health", {"appliance_id": "all"}))
        qa4 = asyncio.run(run("call_read_api", {"operation_id": "get_role_options"}))
        qa5 = asyncio.run(run("call_read_api", {"operation_id": "get_hostname"}))
        qa6 = asyncio.run(run("call_read_api", {"operation_id": "orchestrator.inventory.summary"}))
    finally:
        server_module.OrchestratorClient = original_create

    assert qa1["count"] == 6, qa1
    assert {a["nePk"] for a in qa1["appliances"]} == set(NE_PKS)

    LIVE_TOTAL = sum(
        1 + min(2, max(0, c - 2)) + max(0, c - 3)
        for c in ALARM_COUNTS.values()
    )
    aggregated = qa2["data"]
    assert aggregated["total_alarms"] == LIVE_TOTAL, aggregated
    assert len(aggregated["per_appliance"]) == 6
    assert {row["nePk"] for row in aggregated["per_appliance"]} == set(NE_PKS)
    assert all(row["total"] > 0 for row in aggregated["per_appliance"])

    assert len(qa3["appliances"]) == 6
    assert {row["nePk"] for row in qa3["appliances"]} == set(NE_PKS)
    assert not any(p.endswith("/latency") for p in fake.raw_paths), fake.raw_paths

    assert qa4["truncated"] is False
    assert "nePk" not in qa4["request_echo"]["query_used"]

    assert qa5["truncated"] is False
    assert "granularity" not in qa5["request_echo"]["query_used"]

    qa6_text = jsonlib.dumps(qa6)
    assert "example-not-a-real-password-token" not in qa6_text
    assert '"admin"' not in qa6_text
    assert "***REDACTED***" in qa6_text


def test_get_raw_prefixes_api_root_and_inventory_reads_data():
    import json as jsonlib

    from ec_mcp.orchestrator_client import OrchestratorClient

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload
            self.content = jsonlib.dumps(payload).encode()

        def json(self):
            return self._payload

    class FakeHttpx:
        def __init__(self):
            self.paths = []

        def get(self, path, headers=None, params=None):
            self.paths.append(path)
            if path == "/gms/rest/appliance":
                return FakeResponse({
                    "data": [
                        {"nePk": "1.NE", "hostName": "EC1", "password": "p1", "userName": "admin"},
                        {"nePk": "0.NE", "hostName": "EC2", "password": "p2", "userName": "admin"},
                    ],
                    "request_echo": {},
                    "truncated": False,
                })
            return FakeResponse([])

    class FakeEngine:
        _profiles: ClassVar = {"9.6": {"api_root": "/gms/rest"}}

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
    client._api_root = client._resolve_api_root()
    client._metrics = {}

    appliances = client.list_appliances(refresh=True)
    assert fake.paths == ["/gms/rest/appliance"], fake.paths
    assert len(appliances) == 2
    assert {a["nePk"] for a in appliances} == {"1.NE", "0.NE"}
    assert "password" not in appliances[0]
    assert "userName" not in appliances[0]


def test_alarm_all_mode_equals_sum_of_individual_calls():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    LIVE_COUNTS = {
        "1.NE": {"critical": 2, "major": 2, "warning": 1},
        "0.NE": {"critical": 1, "major": 2, "warning": 1},
        "2.NE": {"critical": 2, "major": 2, "warning": 1},
        "3.NE": {"critical": 3, "major": 2, "warning": 1},
        "14.NE": {"critical": 1, "major": 1, "warning": 0},
        "4.NE": {"critical": 2, "major": 3, "warning": 1},
    }

    class FakeEndpoint:
        def __init__(self):
            self.requests = []

        def list_appliances(self, refresh=False):
            return [{"nePk": k} for k in LIVE_COUNTS]

        def get_raw(self, path, **query):
            ne_pk = query.get("nePk", "")
            self.requests.append((path, ne_pk))
            if path != "/alarm/count/appliance" or ne_pk not in LIVE_COUNTS:
                return {"data": []}
            rows = [
                {"severity": severity, "numOfAlarms": count}
                for severity, count in LIVE_COUNTS[ne_pk].items()
            ]
            return {"data": rows}

    fake = FakeEndpoint()

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        async def run(tool, args):
            result = await server.call_tool(tool, args)
            return jsonlib.loads(result.content[0].text)

        per_appliance_expected = {}
        for ne_pk, _severities in LIVE_COUNTS.items():
            one = asyncio.run(run("get_active_alarms", {"appliance_id": ne_pk}))
            rows = one["data"]["data"] if isinstance(one["data"], dict) and "data" in one["data"] else one["data"]
            per_appliance_expected[ne_pk] = sum(
                row.get("numOfAlarms", 0) for row in rows if isinstance(row, dict)
            )

        all_mode = asyncio.run(run("get_active_alarms", {"appliance_id": "all"}))
    finally:
        server_module.OrchestratorClient = original_create

    aggregated = all_mode["data"]
    for entry in aggregated["per_appliance"]:
        assert entry["total"] == per_appliance_expected[entry["nePk"]], entry
    assert aggregated["total_alarms"] == sum(per_appliance_expected.values())
    assert aggregated["total_alarms"] == sum(sum(c.values()) for c in LIVE_COUNTS.values())
    assert all(entry["total"] > 0 for entry in aggregated["per_appliance"])


def test_call_read_api_final_http_request_has_no_undeclared_params():
    import asyncio
    import json as jsonlib

    from ec_mcp.orchestrator_client import OrchestratorClient
    from ec_mcp.server import create_server

    server = create_server()

    class FakeHttpx:
        def __init__(self):
            self.last_request = None

        def request(self, method, url, headers=None, params=None, json=None):
            self.last_request = {"method": method, "url": url, "params": dict(params or {}), "json": json}
            return FakeResponse()

    class FakeResponse:
        status_code = 200
        content = b'{"data": {"roleOptions": ["admin", "read-only"]}}'

        def json(self):
            return {"data": {"roleOptions": ["admin", "read-only"]}}

    fake_httpx = FakeHttpx()

    class FakeClient(OrchestratorClient):
        def __init__(self):
            self._client = fake_httpx
            self._api_key = "k"
            self._metrics = {}
            self._cached_profile = "9.6"
            self._engine = server_module.CompatibilityEngine(load_profiles(PROFILES))

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(
            server.call_tool("call_read_api", {"operation_id": "get_role_options", "appliance_id": "1.NE"})
        )
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    assert payload["truncated"] is False
    assert fake_httpx.last_request["url"].endswith("/userProfile/options")
    assert "nePk" not in fake_httpx.last_request["params"], fake_httpx.last_request


def test_alarm_extractor_handles_all_documented_orchestrator_shapes():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    SHAPES = {
        "1.NE": {"data": {"critical": 1, "warning": 3, "major": 3}},
        "0.NE": {"data": [{"severity": "critical", "numOfAlarms": 5}]},
        "2.NE": {"data": [{"severity": "major", "numOfAlarms": "3"}, {"severity": "minor", "numOfAlarms": "2"}]},
        "14.NE": {"data": {"alarms": [{"severity": "warning", "numOfAlarms": 4}]}},
    }
    EXPECTED = {"1.NE": 7, "0.NE": 5, "2.NE": 5, "14.NE": 4}

    class FakeClient:
        def list_appliances(self, refresh=False):
            return [{"nePk": k} for k in SHAPES]

        def get_raw(self, path, **query):
            return SHAPES[query.get("nePk")]

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(server.call_tool("get_active_alarms", {"appliance_id": "all"}))
        data = jsonlib.loads(result.content[0].text)["data"]
    finally:
        server_module.OrchestratorClient = original_create

    for entry in data["per_appliance"]:
        assert entry["total"] == EXPECTED[entry["nePk"]], entry
        assert entry["total"] > 0
    assert data["total_alarms"] == sum(EXPECTED.values()) == 21


def test_call_read_api_retries_via_appliance_proxy_on_invalid_nepk():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def call(self, version, operation_id, path_params=None, **query):
            raise RuntimeError(
                "HTTP 400 for GET /gms/rest/userProfile/options: 'Invalid nePk'"
            )

        def appliance_api_get(self, ne_pk, appliance_path, **query):
            self.last_proxy = {"nePk": ne_pk, "path": appliance_path, "query": dict(query)}
            return {"data": {"roleOptions": ["admin", "read-only"]}}

        def get_raw(self, path, **query):
            return {"data": []}

    from ec_mcp import server as server_module

    fake = Fake97Orchestrator()
    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: fake
    try:
        result = asyncio.run(
            server.call_tool("call_read_api", {"operation_id": "get_role_options"})
        )
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    assert payload["data"]["data"]["roleOptions"] == ["admin", "read-only"], payload
    assert fake.last_proxy["nePk"] == "1.NE"
    assert fake.last_proxy["path"] == "/userProfile/options"
    assert "nePk" not in fake.last_proxy["query"]


def test_call_read_api_non_nepk_error_is_not_redirected_to_proxy():
    import asyncio

    from ec_mcp.server import create_server

    server = create_server()

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def call(self, version, operation_id, path_params=None, **query):
            raise RuntimeError("HTTP 400 for GET /gms/rest/someOp: 'Invalid query parameters'")

        def appliance_api_get(self, ne_pk, appliance_path, **query):
            raise AssertionError("proxy must not be used for non-nePk errors")

        def get_raw(self, path, **query):
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(
            server.call_tool("call_read_api", {"operation_id": "get_role_options"})
        )
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    assert "Invalid query parameters" in text


def test_alarm_extractor_maps_num_of_severity_alarms_fields():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    LIVE_COUNTS = {
        "1.NE": {"numOfCriticalAlarms": 1, "numOfWarningAlarms": 2, "numOfMinorAlarms": 0, "numOfMajorAlarms": 2, "numOfAlarms": 5},
        "0.NE": {"numOfCriticalAlarms": 0, "numOfWarningAlarms": 1, "numOfMinorAlarms": 3, "numOfMajorAlarms": 0, "numOfAlarms": 4},
    }

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}, {"nePk": "0.NE", "name": "EC2", "ip": "10.0.0.2"}]

        def get_raw(self, path, **query):
            if path in ("/alarm/count/appliance", "/gms/rest/alarm/count/appliance"):
                ne_pk = query.get("nePk")
                row = dict(LIVE_COUNTS.get(ne_pk, {}))
                row["applianceId"] = ne_pk
                return {"data": row, "note": "counts"}
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(server.call_tool("get_active_alarms", {"appliance_id": "all"}))
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    aggregated = payload["data"]
    by_ne = {row["nePk"]: row for row in aggregated["per_appliance"]}
    assert by_ne["1.NE"]["by_severity"] == {"critical": 1, "warning": 2, "major": 2, "minor": 0}, by_ne["1.NE"]
    assert by_ne["0.NE"]["by_severity"] == {"warning": 1, "minor": 3, "critical": 0, "major": 0}, by_ne["0.NE"]
    for row in aggregated["per_appliance"]:
        assert sum(row["by_severity"].values()) == row["total"]
    assert aggregated["total_alarms"] == 9
    assert aggregated["by_severity"] == {"critical": 1, "warning": 3, "major": 2, "minor": 3}


def test_wan_health_projects_tunnel_kpis_only():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    RAW_TUNNEL = {
        "tunnelName": "bondedTunnel_13",
        "overlayId": 1,
        "MOS": 440,
        "MIN_MOS": 420,
        "AVG_TX_JITTER": 3.2,
        "SUM_OHEAD_WTX_PKTS": 123456,
        "MAX_COMP_L2W": 88,
        "AVG_TX_LATENCY": 12.5,
        "SUM_PKTS_LOST": 7,
    }

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def get_raw(self, path, **query):
            if "/stats/" in path:
                return {"data": [dict(RAW_TUNNEL)]}
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(server.call_tool("get_wan_health", {"appliance_id": "1.NE"}))
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    row = payload["appliances"][0]["stats"][0]
    assert "tunnelName" in row and "MOS" in row and "MIN_MOS" in row and "AVG_TX_JITTER" in row and "AVG_TX_LATENCY" in row, row
    assert "SUM_OHEAD_WTX_PKTS" not in row and "MAX_COMP_L2W" not in row, row


def test_wan_health_fields_projection_keeps_tunnel_kpis():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    RAW_TUNNEL = {
        "tunnelName": "bondedTunnel_13",
        "MOS": 440,
        "MIN_MOS": 420,
        "MAX_JITTER": 3.2,
        "MAX_PRE_PCT_LOSS": 0.5,
        "MIN_LATENCY_MIN": 12.5,
        "SUM_OHEAD_WTX_PKTS": 123456,
        "MAX_COMP_L2W": 88,
    }

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def get_raw(self, path, **query):
            if "/stats/" in path:
                return {"data": [dict(RAW_TUNNEL)]}
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(
            server.call_tool(
                "get_wan_health",
                {"appliance_id": "1.NE", "fields": "mos,min_mos,MAX_JITTER,MAX_PRE_PCT_LOSS,MIN_LATENCY_MIN"},
            )
        )
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    row = payload["appliances"][0]
    assert row["nePk"] == "1.NE", payload
    kpis = row["stats"][0]
    assert kpis == {"MOS": 440, "MIN_MOS": 420, "MAX_JITTER": 3.2, "MAX_PRE_PCT_LOSS": 0.5, "MIN_LATENCY_MIN": 12.5}, kpis


def test_wan_health_tunnel_keyed_dict_shape():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def get_raw(self, path, **query):
            if "/stats/aggregate/tunnel" in path:
                return {
                    "data": {
                        "bondedTunnel_13": {
                            "1.NE": {
                                "MOS": 440,
                                "MIN_MOS": 420,
                                "MAX_JITTER": 3.2,
                                "SUM_OHEAD_WTX_PKTS": 999999,
                                "MAX_COMP_L2W": 88,
                            }
                        }
                    }
                }
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(server.call_tool("get_wan_health", {"appliance_id": "all"}))
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    stats = payload["appliances"][0]["stats"]
    tunnel = stats["bondedTunnel_13"]["1.NE"]
    assert tunnel == {"MOS": 440, "MIN_MOS": 420, "MAX_JITTER": 3.2}, tunnel


def test_call_read_api_proxy_failure_reports_both_errors():
    import asyncio

    from ec_mcp.server import create_server

    server = create_server()

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def call(self, version, operation_id, path_params=None, **query):
            raise RuntimeError("HTTP 400 for GET /gms/rest/userProfile/options: 'Invalid nePk'")

        def appliance_api_get(self, ne_pk, appliance_path, **query):
            raise RuntimeError("HTTP 404 for GET /gms/rest/appliance/rest: not found")

        def get_raw(self, path, **query):
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(server.call_tool("call_read_api", {"operation_id": "get_role_options"}))
        text = result.content[0].text
    finally:
        server_module.OrchestratorClient = original_create

    assert "Invalid nePk" in text and "also failed" in text


def test_orchestrator_info_exposes_build_for_deployment_verification():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()

    class Fake97Orchestrator:
        _api_root = "/gms/rest"

        def resolve_active_profile(self):
            return "9.6"

        def detect_version(self):
            return "9.7.2.40591"

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

        def get_raw(self, path, **query):
            return {"data": []}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: Fake97Orchestrator()
    try:
        result = asyncio.run(server.call_tool("orchestrator_info", {}))
        payload = jsonlib.loads(result.content[0].text)
    finally:
        server_module.OrchestratorClient = original_create

    build = payload["build"]
    assert build["package_version"], build
    assert build["git_commit"] and build["git_commit"] != "unknown", build


def test_stable_package_version_is_consistent():
    from ec_mcp import __version__

    import tomllib
    from pathlib import Path

    metadata = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == metadata["project"]["version"]


def test_large_helper_response_is_closed_valid_json():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()
    large_rows = [
        {
            "nePk": "1.NE",
            "tunnelName": f"bondedTunnel_{index}",
            "MOS": 440,
            "AVG_TX_LATENCY": "x" * 1800,
        }
        for index in range(12)
    ]

    class FakeClient:
        def get_raw(self, path, **query):
            if path == "/stats/aggregate/tunnel":
                return {"data": large_rows}
            if path == "/stats/aggregate/mos":
                return {"data": []}
            if path == "/reachability/appliance":
                return {"data": []}
            return {"data": []}

        def list_appliances(self, refresh=False):
            return [{"nePk": "1.NE", "name": "EC1", "ip": "10.0.0.1"}]

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *a, **k: FakeClient()
    try:
        result = asyncio.run(
            server.call_tool("get_wan_health", {"appliance_id": "1.NE", "granularity": "day"})
        )
    finally:
        server_module.OrchestratorClient = original_create

    payload = jsonlib.loads(result.content[0].text)
    assert payload["truncated"] is True


def test_api_search_understands_business_intent_overlay_synonyms():
    import asyncio
    import json as jsonlib

    from ec_mcp.server import create_server

    server = create_server()
    result = asyncio.run(
        server.call_tool(
            "list_api_operations",
            {"version": "9.6", "search": "business intent", "mode": "index", "page_size": 20},
        )
    )
    operations = jsonlib.loads(result.content[0].text)["versions"]["9.6"]["operations"]
    assert "orchestrator.addnewoverlay315" in operations
    assert all("overlay" in operation.lower() or "overlay" in path.lower() for operation, path in operations.items())


def test_ztp_tool_exposes_pagination_controls():
    import ec_mcp.server as server_module

    tools = {tool.name: tool for tool in server_module.create_server()._tool_manager.list_tools()}
    properties = tools["get_ztp_status"].parameters["properties"]
    assert {"offset", "limit", "fields"} <= set(properties)


def test_wan_health_field_aliases_preserve_raw_latency_kpis():
    import asyncio
    import json as jsonlib

    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    class FakeClient:
        def list_appliances(self):
            return [{"nePk": "0.NE", "name": "ECV-TEST"}]

        def get_raw(self, path, **query):
            if path == "/stats/aggregate/tunnel":
                return {
                    "data": {
                        "tunnel_1": {
                            "0.NE": {
                                "TUNNEL": "tunnel_1",
                                "MAX_LATENCY_MAX": 12,
                                "MAX_JITTER": 3,
                                "MAX_PRE_PCT_LOSS": 1,
                            }
                        }
                    }
                }
            if path == "/stats/aggregate/mos":
                return {"data": []}
            if path == "/reachability/appliance":
                return []
            raise AssertionError(path)

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: FakeClient()
    try:
        result = asyncio.run(
            create_server(Settings(orchestrator_url="https://orch.example")).call_tool(
                "get_wan_health",
                {"appliance_id": "0.NE", "fields": "tunnel,latency,jitter,loss"},
            )
        )
    finally:
        server_module.OrchestratorClient = original_create

    text = result.content[0].text
    payload = jsonlib.loads(text)
    assert "MAX_LATENCY_MAX" in text
    assert "MAX_JITTER" in text
    assert "MAX_PRE_PCT_LOSS" in text
    assert payload["appliances"][0]["stats"]["tunnel_1"]["0.NE"]["TUNNEL"] == "tunnel_1"


def test_confirmed_empty_overlay_write_is_rejected_before_upstream_call():
    import asyncio

    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, *args, **kwargs):
            raise AssertionError("empty confirmed write must not reach Orchestrator")

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: FakeClient()
    try:
        result = asyncio.run(
            create_server(
                Settings(orchestrator_url="https://orch.example", allow_write_tools=True)
            ).call_tool(
                "apply_change",
                {
                    "operation_id": "orchestrator.addnewoverlay315",
                    "body_json": "{}",
                    "confirm": True,
                },
            )
        )
    finally:
        server_module.OrchestratorClient = original_create

    assert "Refusing a confirmed write with an empty JSON body" in result.content[0].text


def test_deployment_replace_guard_rejects_body_without_mode_ifs():
    """Regression (EC3 16.NE live incident): a confirmed POST /deployment that
    omits modeIfs would REPLACE the deployment and wipe every LAN/WAN interface.
    The MCP must refuse the write before it reaches the Orchestrator."""
    import asyncio

    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, *args, **kwargs):
            raise AssertionError("partial deployment body must not reach the appliance")

        def appliance_api_call(self, *args, **kwargs):
            raise AssertionError("partial deployment body must not reach the appliance")

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: FakeClient()
    try:
        result = asyncio.run(
            create_server(
                Settings(orchestrator_url="https://orch.example", allow_write_tools=True)
            ).call_tool(
                "apply_change",
                {
                    "operation_id": "appliance.deploymentpost567554",
                    "appliance_id": "16.NE",
                    "body_json": jsonlib.dumps(
                        {
                            "sysConfig": {
                                "maxBW": 500000,
                                "maxInBW": 500000,
                                "mode": "inline-router",
                                "license": {"ecTier": 500000},
                            }
                        }
                    ),
                    "confirm": True,
                },
            )
        )
    finally:
        server_module.OrchestratorClient = original_create

    text = result.content[0].text
    assert "missing required sections" in text
    assert "modeIfs" in text


def test_deployment_replace_guard_rejects_body_without_sys_config():
    import asyncio

    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, *args, **kwargs):
            raise AssertionError("partial deployment body must not reach the appliance")

        def appliance_api_call(self, *args, **kwargs):
            raise AssertionError("partial deployment body must not reach the appliance")

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: FakeClient()
    try:
        result = asyncio.run(
            create_server(
                Settings(orchestrator_url="https://orch.example", allow_write_tools=True)
            ).call_tool(
                "apply_change",
                {
                    "operation_id": "appliance.deploymentpost567554",
                    "appliance_id": "16.NE",
                    "body_json": jsonlib.dumps({"modeIfs": []}),
                    "confirm": True,
                },
            )
        )
    finally:
        server_module.OrchestratorClient = original_create

    assert "missing required sections" in result.content[0].text
    assert "sysConfig" in result.content[0].text


def test_deployment_replace_guard_accepts_complete_body():
    import asyncio

    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    class FakeClient:
        def resolve_active_profile(self):
            return "9.6"

        def call(self, *args, **kwargs):
            raise AssertionError("appliance-scoped write must go through appliance_api_call")

        def appliance_api_call(self, *args, **kwargs):
            return {"applied": True}

    from ec_mcp import server as server_module

    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: FakeClient()
    try:
        result = asyncio.run(
            create_server(
                Settings(orchestrator_url="https://orch.example", allow_write_tools=True)
            ).call_tool(
                "apply_change",
                {
                    "operation_id": "appliance.deploymentpost567554",
                    "appliance_id": "16.NE",
                    "body_json": jsonlib.dumps(
                        {
                            "modeIfs": [
                                {
                                    "name": "lan0",
                                    "applianceIPs": [],
                                }
                            ],
                            "sysConfig": {
                                "maxBW": 500000,
                                "maxInBW": 500000,
                                "mode": "inline-router",
                                "license": {"ecTier": 500000},
                            },
                            "dhcpFailover": [],
                            "dpRoutes": [],
                        }
                    ),
                    "confirm": True,
                },
            )
        )
    finally:
        server_module.OrchestratorClient = original_create

    assert '"applied": true' in result.content[0].text.lower()


def test_parse_firewall_log_entries_structures_zone_firewall_rows():
    from ec_mcp.security_workflow import parse_firewall_log_entries, summarize_security_log

    payload = {
        "logEntries": [
            [
                "10/04/2026 23:33:17",
                "LogType:Zone Based Firewall, Action:allow, Reason:flow create, Flow-ID:189710, "
                "SrcAddr:172.17.253.1, DstAddr:54.236.159.130, Application:SilverPeakCloud, "
                "FromZone:DATOS, ToZone:WAN_LAB,",
                "host",
                "WARNING",
            ],
            [
                "10/04/2026 23:32:59",
                "LogType:Zone Based Firewall, Action:drop, Reason: Dropped - Local dest interface is down, "
                "Flow-ID:189694, FromZone:DATOS, ToZone:WAN_LAB, Application:SilverPeakCloud,",
                "host",
                "EMERG",
            ],
        ]
    }
    entries = parse_firewall_log_entries(payload)
    assert len(entries) == 2
    assert entries[0]["Action"] == "allow"
    assert entries[0]["Flow-ID"] == "189710"
    assert entries[0]["FromZone"] == "DATOS"
    assert entries[1]["Action"] == "drop"
    summary = summarize_security_log(entries)
    assert summary["total_entries"] == 2
    assert summary["actions"] == {"allow": 1, "drop": 1}
    assert summary["zone_pairs"]["DATOS->WAN_LAB"] == 2
    assert "Dropped - Local dest interface is down" in summary["drop_reasons"]


def test_guard_partial_deployment_body_accepts_full_body():
    from ec_mcp.server import guard_partial_deployment_body

    full = {"modeIfs": [{"interfaceName": "lan0"}], "sysConfig": {"license": {}}}
    guard_partial_deployment_body(full)


def test_guard_partial_deployment_body_refuses_partial():
    from ec_mcp.server import SecurityError, guard_partial_deployment_body

    partial = {"sysConfig": {"license": {}}}
    try:
        guard_partial_deployment_body(partial)
    except SecurityError as error:
        assert "full REPLACE" in str(error)
    else:
        raise AssertionError("expected SecurityError for partial deployment body")


def test_profile_10_0_resolves_ref_parameters():
    engine = CompatibilityEngine(load_profiles(PROFILES))
    operations = engine._profiles["10.0"]["operations"]
    assert "nePk" in operations["orchestrator.flows242"]["query_params"]
    assert "nePk" in operations["orchestrator.bfdsessions139"]["query_params"]
    assert set(operations["orchestrator.appliancegetapi70"]["query_params"]) == {"nePk", "url"}
    assert operations["appliance.realtimestats885790"].get("body_example")


def test_realtime_stats_body_matches_10_0_examples():
    from ec_mcp.telemetry_workflow import build_realtime_stats_body

    tunnel = build_realtime_stats_body("tunnel", "", "all", 10)
    assert tunnel == {"type": "tunnel", "name": "", "filter": 0, "count": 10}
    drops = build_realtime_stats_body("drops", "", "all", 10)
    assert drops == {"type": "drops", "name": ""}
    dscp = build_realtime_stats_body("dscp", "46", "all", 10)
    assert dscp == {"type": "dscp", "name": "46", "filter": 0, "count": 10}


def test_error_message_tolerates_list_json_body():
    import httpx

    from ec_mcp.config import Settings
    from ec_mcp.orchestrator_client import OrchestratorClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json=[{"message": "Invalid nePk"}])

    client = OrchestratorClient(
        Settings(orchestrator_url="https://orch.example", orchestrator_api_key="k"),
        CompatibilityEngine(load_profiles(PROFILES)),
        client=httpx.Client(
            base_url="https://orch.example",
            transport=httpx.MockTransport(handler),
        ),
    )
    try:
        client.call("10.0", "orchestrator.flows242", nePk="4.NE")
    except RuntimeError as error:
        assert "Invalid nePk" in str(error)
    else:
        raise AssertionError("expected RuntimeError")


def _sse_transport(events: list[tuple[str, str]]):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        body_lines = []
        for name, data in events:
            body_lines.append(f"event: {name}")
            body_lines.append(f"data: {data}")
            body_lines.append("")
        content = "\n".join(body_lines)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=content.encode("utf-8"),
        )

    return httpx.MockTransport(handler)


def test_stream_post_sse_consumes_events():
    import httpx

    from ec_mcp.config import Settings
    from ec_mcp.orchestrator_client import OrchestratorClient

    events = [
        ("message", jsonlib.dumps({"chat_id": "chat_1", "delta": "Hello "})),
        ("message", jsonlib.dumps({"delta": "world", "msg_id": "msg_9"})),
    ]
    client = OrchestratorClient(
        Settings(orchestrator_url="https://orch.example", orchestrator_api_key="k"),
        CompatibilityEngine(load_profiles(PROFILES)),
        client=httpx.Client(
            base_url="https://orch.example",
            transport=_sse_transport(events),
        ),
    )
    payload = client.stream_post_sse("/gms/rest/sdwanai/search", json_body={"question": "hi"})
    assert len(payload["events"]) == 2
    assert "Hello " in payload["data"] and "world" in payload["data"]


def test_stream_post_sse_enforces_event_ceiling():
    import httpx

    from ec_mcp.config import Settings
    from ec_mcp.orchestrator_client import OrchestratorClient

    client = OrchestratorClient(
        Settings(orchestrator_url="https://orch.example", orchestrator_api_key="k"),
        CompatibilityEngine(load_profiles(PROFILES)),
        client=httpx.Client(
            base_url="https://orch.example",
            transport=_sse_transport([("message", "one"), ("message", "two")]),
        ),
    )
    payload = client.stream_post_sse("/gms/rest/sdwanai/search", max_events=1)
    assert len(payload["events"]) == 1
    assert payload["truncated"] is True


def test_clear_sdwan_ai_context_requires_write_permission(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module
    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    class FakeClient:
        def resolve_active_profile(self):
            return "10.0"

        def call(self, *args, **kwargs):
            raise AssertionError("write must not reach the Orchestrator")

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: FakeClient())
    server = create_server(Settings(orchestrator_url="https://orch.example", allow_write_tools=False))
    response = asyncio.run(server.call_tool("clear_sdwan_ai_context", {}))
    assert "Write tools are disabled" in response.content[0].text


def test_ask_sdwan_ai_tool_end_to_end(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module
    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    events = [
        ("message", jsonlib.dumps({"chat_id": "chat_abc", "delta": "BGP is configured on 3 neighbors."})),
        ("done", jsonlib.dumps({"msg_id": "msg_1", "status": "done"})),
    ]

    class FakeClient:
        def resolve_active_profile(self):
            return "10.0"

        def stream_post_sse(self, path, json_body=None, max_events=2000, timeout=120.0):
            return {
                "events": [
                    {"event": name, "data": data} for name, data in events
                ],
                "data": "\n".join(data for _, data in events),
                "raw": "",
            }

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: FakeClient())
    server = create_server(Settings())
    response = asyncio.run(server.call_tool("ask_sdwan_ai", {"question": "how is BGP?"}))
    payload = jsonlib.loads(response.content[0].text)
    assert payload["chat_id"] == "chat_abc"
    assert "BGP is configured" in payload["answer"]
    assert payload["msg_id"] == "msg_1"


def test_ask_sdwan_ai_requires_question():
    import asyncio

    from ec_mcp.config import Settings
    from ec_mcp.server import create_server

    server = create_server(Settings())
    response = asyncio.run(server.call_tool("ask_sdwan_ai", {"question": ""}))
    payload = jsonlib.loads(response.content[0].text)
    assert payload["error"] == "PARAM_REQUIRED"
