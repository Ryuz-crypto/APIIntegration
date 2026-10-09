import json

import pytest

from ec_mcp.config import Settings
from ec_mcp.security_workflow import (
    extract_rows,
    summarize_bgp_neighbors,
    summarize_ddos,
    summarize_ids_state,
    summarize_tunnels,
    summarize_zone_matrix,
    validate_ids_mode,
)

IDS_STATE = {"data": {"mode": "IPS-Inline", "profile": "Default"}}

ZONES = {"data": [{"name": "DATOS"}, {"name": "L2L1"}, {"name": "WAN_INET1"}]}

SECURITY_MAPS = {
    "data": [
        {
            "name": "SecMap",
            "rules": [
                {"zone1": "DATOS", "zone2": "L2L1", "priority": 10, "action": "allow"},
            ],
        }
    ]
}

DDOS_ROWS = {"data": [{"zoneId": 1, "status": "OK", "profile": "Default"}]}

TUNNELS = {
    "data": [
        {"name": "t1", "status": "Up", "overlay": 1},
        {"name": "t2", "status": "Down", "overlay": 2},
    ]
}

BGP_ROWS = {"data": [{"ip": "10.0.0.1", "state": "Established", "remoteAs": 65001}]}


class FakeSecurityClient:
    def resolve_active_profile(self):
        return "9.6"

    def list_appliances(self):
        return [{"nePk": "15.NE", "name": "EC3", "serial_number": "00-1B-BC-46-2C-04", "ip": "172.17.201.87"}]

    def call(self, version, operation_id, path_params=None, json_body=None, **query):
        del version, path_params, json_body
        self.calls.append((operation_id, query))
        if operation_id == "orchestrator.zscalerconnectivityget853":
            return {"data": [{"status": "Connected"}]}
        if operation_id == "orchestrator.zscalerassociationget849":
            return {"data": [{"nePk": "15.NE"}]}
        if operation_id == "orchestrator.netskopeconnectivityget853":
            return {"data": [{"status": "Disconnected"}]}
        if operation_id == "orchestrator.netskopeassociationget849":
            return {"data": []}
        if operation_id == "returns_axis_connectivity_status":
            return {"data": [{"status": "Connected"}]}
        if operation_id == "returns_appliance_to_axis_association":
            return {"data": []}
        if operation_id == "orchestrator.bfdsessions139":
            return {"data": [{"session": "up"}]}
        if operation_id == "orchestrator.getneighbor142":
            return BGP_ROWS
        raise AssertionError(f"unexpected operation {operation_id}")

    def appliance_api_call(self, version, ne_pk, operation_id, path_params=None, json_body=None, **query):
        del version, path_params, json_body, query
        self.calls.append((operation_id, {"nePk": ne_pk}))
        if operation_id == "appliance.getidsipsstate405371":
            return IDS_STATE
        if operation_id == "appliance.getidsipsevents189513":
            return {"data": [{"signature": "SQLi", "severity": "high"}]}
        if operation_id == "appliance.getallzones257534":
            return ZONES
        if operation_id == "appliance.securitymapsget832281":
            return SECURITY_MAPS
        if operation_id == "appliance.thresholdstatusget574729":
            return DDOS_ROWS
        if operation_id == "appliance.protectionprofilesget574729":
            return DDOS_ROWS
        if operation_id == "appliance.deployment729344":
            return {"deploymentMode": "inline-router", "totalOutboundBandwidth": 300000}
        if operation_id == "appliance.tunnelsconfigandstate741932":
            return TUNNELS
        if operation_id == "appliance.tunnelsconfigandstate525522":
            return {"data": []}
        if operation_id == "appliance.tunnelsconfigandstate574637":
            return {"data": []}
        if operation_id == "appliance.getneighbor782866":
            return BGP_ROWS
        raise AssertionError(f"unexpected operation {operation_id}")

    def __init__(self):
        self.calls = []


def _server():
    from ec_mcp.server import create_server

    return create_server(
        Settings(
            orchestrator_url="https://orch.example",
            allow_write_tools=True,
            allow_dangerous_writes=True,
        )
    )


def _set_client(monkeypatch, client):
    import ec_mcp.server as server_module

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: client)


def _run(server_fixture, name, **kwargs):
    import asyncio

    return asyncio.run(server_fixture.call_tool(name, kwargs))


def _parse(result):
    text = result if isinstance(result, str) else result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": text}


def test_extract_rows_common_shapes():
    assert extract_rows({"data": [{"a": 1}]}) == [{"a": 1}]
    assert extract_rows([{"b": 2}]) == [{"b": 2}]
    assert extract_rows({"data": {"result": [{"c": 3}]}}) == [{"c": 3}]
    assert extract_rows(None) == []


def test_summarize_ids_state():
    summary = summarize_ids_state(IDS_STATE)
    assert summary["mode"] == "IPS-Inline"
    assert summary["active"] is True


def test_summarize_ids_state_off_is_inactive():
    assert summarize_ids_state({"data": {"mode": "Off", "profile": "Default"}})["active"] is False
    assert summarize_ids_state({"data": {"mode": "disabled", "profile": "Default"}})["active"] is False
    assert summarize_ids_state({"data": {"mode": "none", "profile": "Default"}})["active"] is False
    assert summarize_ids_state({"data": {"mode": "IPS-Inline", "profile": "Default"}})["active"] is True


def test_summarize_zone_matrix_flags_uncovered_pairs():
    matrix = summarize_zone_matrix(ZONES, SECURITY_MAPS)
    assert matrix["zones"] == ["DATOS", "L2L1", "WAN_INET1"]
    assert matrix["covered_pairs"] == 1
    pairs = {tuple(pair) for pair in matrix["uncovered_pairs"]}
    assert ("DATOS", "WAN_INET1") in pairs


def test_summarize_ddos():
    summary = summarize_ddos(DDOS_ROWS)
    assert summary["zones_checked"] == 1
    assert summary["zones"][0]["status"] == "OK"


def test_summarize_tunnels():
    summary = summarize_tunnels(TUNNELS)
    assert summary["total"] == 2
    assert summary["up"] == 1
    assert summary["down"] == 1


def test_summarize_bgp_neighbors():
    summary = summarize_bgp_neighbors(BGP_ROWS)
    assert summary["total"] == 1
    assert summary["established"] == 1


def test_validate_ids_mode_rejects_unknown():
    with pytest.raises(ValueError, match="mode"):
        validate_ids_mode("IPS-Magic")
    assert validate_ids_mode("Off") == "Off"


def test_get_ids_ips_state_tool(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_ids_ips_state", appliance_id="all"))
    assert payload["appliances"][0]["mode"] == "IPS-Inline"
    assert payload["appliances"][0]["active"] is True


def test_get_zone_matrix_tool(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_zone_matrix", appliance_id="EC3"))
    assert payload["nePk"] == "15.NE"
    assert len(payload["zones"]) == 3
    assert payload["covered_pairs"] == 1


def test_get_ddos_status_tool(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_ddos_status", appliance_id="EC3"))
    assert payload["threshold_status"]["zones_checked"] == 1


def test_get_deployment_config_tool(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_deployment_config", appliance_id="EC3"))
    assert payload["deployment"]["deploymentMode"] == "inline-router"


def test_get_site_to_site_tunnels_tool(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_site_to_site_tunnels", appliance_id="all"))
    entry = payload["appliances"][0]
    assert entry["tunnels"]["total"] == 2
    assert entry["tunnels"]["down"] == 1
    assert "third_party" in entry


def test_get_sse_status_all_providers(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_sse_status", provider="all"))
    providers = {item["provider"]: item for item in payload["providers"]}
    assert set(providers) == {"zscaler", "netskope", "axis"}
    assert providers["zscaler"]["associated_appliances"] == ["15.NE"]
    assert providers["netskope"]["association_count"] == 0


def test_get_sse_status_rejects_unknown_provider(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_sse_status", provider="paloalto"))
    assert "error" in payload or payload.get("providers") is None


def test_get_security_posture_reports_findings(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_security_posture", appliance_id="all"))
    assert payload["finding_count"] >= 1
    severities = [f["severity"] for f in payload["findings"]]
    assert severities == sorted(severities, key={"high": 0, "medium": 1, "low": 2}.get)
    tunnel_down = [f for f in payload["findings"] if "tunnels down" in f["finding"]]
    assert tunnel_down and tunnel_down[0]["severity"] == "high"


def test_get_ids_ips_events_tool(monkeypatch):
    fake = FakeSecurityClient()
    _set_client(monkeypatch, fake)
    payload = _parse(_run(_server(), "get_ids_ips_events", appliance_id="15.NE"))
    assert payload["total_events"] == 1
    assert payload["events"][0]["signature"] == "SQLi"


class TestSecurityCorrelation:
    def test_correlate_ids_inactive_with_drops(self):
        from ec_mcp.security_workflow import correlate_security_signals

        findings = correlate_security_signals(
            "0.NE",
            {"active": False, "mode": "disabled"},
            [],
            {"drop_reasons": {"implicit deny": 5, "policy deny": 1}},
            None,
        )
        assert any(f["severity"] == "high" and "IDS/IPS inactive" in f["finding"] for f in findings)
        assert any("implicit deny" in f["finding"] and f["severity"] == "medium" for f in findings)

    def test_correlate_high_priority_ids_events(self):
        from ec_mcp.security_workflow import correlate_security_signals

        findings = correlate_security_signals(
            "1.NE",
            {"active": True, "mode": "ips_inline"},
            [{"message": "[Inspect] ET ATTACK [Priority: 2] from 203.0.113.5"}],
            {"drop_reasons": {}},
            None,
        )
        assert any("high-priority IDS events" in f["finding"] for f in findings)
        assert any(f["evidence"] for f in findings if "evidence" in f)

    def test_correlate_no_false_positive_on_healthy(self):
        from ec_mcp.security_workflow import correlate_security_signals

        findings = correlate_security_signals(
            "2.NE",
            {"active": True, "mode": "ips_inline"},
            [],
            {"drop_reasons": {"policy deny": 2}},
            {"blocked_by_category": {}},
        )
        assert findings == []

    def test_summarize_web_filtering(self):
        from ec_mcp.security_workflow import summarize_web_filtering

        summary = summarize_web_filtering(
            [
                {"WebCategory": "Malware", "WebReputation": "5", "Action": "drop"},
                {"WebCategory": "Malware", "WebReputation": "5", "Action": "drop"},
                {"WebCategory": "News", "WebReputation": "70", "Action": "allow"},
            ]
        )
        assert summary["blocked_by_category"]["Malware"] == 2
        assert summary["top_web_categories"]["News"] == 1
        assert summary["reputation_distribution"]["5"] == 2


class TestScanAndAlarmCorrelation:
    def test_detects_scan_events(self):
        from ec_mcp.security_workflow import correlate_security_signals

        findings = correlate_security_signals(
            "3.NE",
            {"active": True, "mode": "ips_inline"},
            [{"message": "[Drop] ET SCAN Behavioral Unusually fast Terminal Server Traffic Potential Scan or Infection (Inbound) {TCP} 172.15.2.102:9490 -> 172.15.1.100:3389"}],
            {"drop_reasons": {}},
            None,
        )
        assert any("network scan or infection" in f["finding"] and f["severity"] == "high" for f in findings)

    def test_correlate_active_alarms_critical(self):
        from ec_mcp.security_workflow import correlate_active_alarms

        findings = correlate_active_alarms("1.NE", {"critical": 1, "major": 3, "warning": 3})
        assert any(f["severity"] == "high" and "1 critical alarms" in f["finding"] for f in findings)
        assert any("3 major alarms" in f["finding"] for f in findings)

    def test_correlate_active_alarms_no_false_positive(self):
        from ec_mcp.security_workflow import correlate_active_alarms

        assert correlate_active_alarms("2.NE", {"critical": 0, "major": 1, "warning": 2}) == []
        assert correlate_active_alarms("3.NE", None) == []
