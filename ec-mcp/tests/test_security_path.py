"""Security regressions exercised through public MCP tools and real HTTP routing.

All addresses are documentation-only; MockTransport never contacts an appliance.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import httpx
import pytest

from ec_mcp.compat import CompatibilityEngine, load_profiles, render_path
from ec_mcp.config import Settings
from ec_mcp.orchestrator_client import OrchestratorClient
from ec_mcp.security_workflow import summarize_ddos, summarize_ids_state, summarize_tunnels, summarize_zone_matrix
from ec_mcp.server import create_server

pytestmark = pytest.mark.security


def invoke(server, name, **arguments):
    result = asyncio.run(server.call_tool(name, arguments)).content[0].text
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": result}


@pytest.fixture()
def security_lab(monkeypatch, tmp_path):
    import ec_mcp.server as module

    requests = []
    state = {
        "version": "9.6.1",
        "ids": {"mode": "IPS-Inline", "profile": "Default"},
        "ids_global": {"ips_inline": ["2.NE"], "ips_lookaside": [], "ids": [], "disabled": ["1.NE"]},
        "profiles": {
            "profiles": [{"profile_name": "edge", "enable": True}],
            "profileMaps": [{"zone_id": 0, "profile_name": "edge"}],
        },
        "thresholds": [{"zoneId": 0, "status": False}],
        "zones": {"0": {"name": "LAN"}, "1": {"name": "WAN"}},
        "maps": [{"name": "default", "rules": [{"zone1": "LAN", "zone2": "WAN", "action": "allow", "priority": 1}]}],
        "settings": {"defaultAction": "deny"},
        "tunnels": [],
        "errors": {},
        "per_ne_errors": {},
        "events": [{"signature": "lab-signature", "severity": "high"}],
        "associations": [{"nePk": "2.NE"}],
        "log": {"logEntries": []},
        "inventory": [
            {"nePk": "1.NE", "name": "lab-a", "ip": "192.0.2.1"},
            {"nePk": "2.NE", "name": "lab-b", "ip": "192.0.2.2"},
        ],
    }
    routes = {
        "/ids/state": "ids_global",
        "/idsips/state": "ids",
        "/idsips/events": "events",
        "/security/ddos/protectionProfile": "profiles",
        "/security/ddos/thresholdStatus": "thresholds",
        "/zones": "zones",
        "/securityMaps": "maps",
        "/securityMapsSettings": "settings",
        "/tunnelsConfigAndState": "tunnels",
    }

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("briefInfo"):
            return httpx.Response(200, json={"version": state["version"]})
        if request.url.path.endswith("/appliance"):
            return httpx.Response(200, json=state["inventory"])
        path = request.url.params.get("url", request.url.path.removeprefix("/gms/rest"))
        per_ne_error = state["per_ne_errors"].get((request.url.params.get("nePk"), path))
        if per_ne_error:
            return httpx.Response(per_ne_error, json={"error": "appliance unreachable"})
        if path in state["errors"]:
            return httpx.Response(state["errors"][path], json={"error": "unavailable"})
        if request.method != "GET":
            status = state.get("write_status", 204)
            if status >= 400:
                return httpx.Response(status, json={"error": "write rejected"})
            if path in routes and not state.get("ignore_write"):
                candidate = json.loads(request.content)
                if "write_transform" in state:
                    candidate = state["write_transform"](candidate)
                state[routes[path]] = candidate
            if state.get("verification_error"):
                state["errors"][path] = state["verification_error"]
            if state.get("write_timeout"):
                raise httpx.ReadTimeout("lab transport lost response", request=request)
            return httpx.Response(status, json={"saved": True}) if status == 200 else httpx.Response(status)
        if path in routes:
            return httpx.Response(200, json=state[routes[path]])
        if "logViewer" in path:
            return httpx.Response(200, json=state["log"])
        if path.endswith("/connectivity"):
            return httpx.Response(200, json={"status": "Connected"})
        if path.endswith("/applianceAssociation"):
            return httpx.Response(200, json=state["associations"])
        return httpx.Response(200, json={"data": []})

    settings = Settings(
        orchestrator_url="https://orch.example",
        orchestrator_api_key="fixture",
        allow_write_tools=True,
        audit_log_path=tmp_path / "audit.jsonl",
    )
    engine = CompatibilityEngine(load_profiles(settings.profiles_dir))
    http = httpx.Client(base_url=settings.orchestrator_url, transport=httpx.MockTransport(handler))
    client = OrchestratorClient(settings, engine, http)
    monkeypatch.setattr(module, "OrchestratorClient", lambda *args: client)
    yield create_server(settings), client, state, requests, settings
    client.close()


@pytest.mark.parametrize("mode", ["Off", "IDS Only", "IPS-Performant", "IPS-Inline", "IPS-Magic", None, False])
def test_ids_modes_never_confuse_detection_and_prevention(mode):
    result = summarize_ids_state({"mode": mode, "profile": "edge"})
    assert result["detection_enabled"] is (mode in {"IDS Only", "IPS-Performant", "IPS-Inline"})
    assert result["prevention_enabled"] is (mode in {"IPS-Performant", "IPS-Inline"})
    assert result["evidence_status"] == (
        "observed" if mode in {"Off", "IDS Only", "IPS-Performant", "IPS-Inline"} else "unknown"
    )


def test_conflicting_ids_rows_do_not_report_protection():
    result = summarize_ids_state([{"mode": "IPS-Inline"}, {"mode": "Off"}])
    assert result["active"] is False
    assert result["evidence_status"] == "conflicting"


def test_zone_matrix_preserves_direction_and_keyed_zones():
    zones = {"0": {"name": "LAN"}, "1": {"name": "WAN"}}
    maps = {"name": "default", "rules": [{"zone1": "LAN", "zone2": "WAN", "action": "allow"}]}
    result = summarize_zone_matrix(zones, maps)
    assert result["zones"] == ["LAN", "WAN"]
    assert result["uncovered_pairs"] == [["WAN", "LAN"]]
    assert result["coverage_is_enforcement"] is False


def test_ddos_contract_profiles_and_zero_false_are_preserved():
    result = summarize_ddos(
        {
            "profiles": [{"profile_name": "edge", "enable": False}],
            "profileMaps": [{"zone_id": 0, "profile_name": "edge"}],
        }
    )
    assert result["zones"][0]["zoneId"] == 0
    assert result["zones"][0]["enabled"] is False
    assert result["disabled_zones"] == [0]
    threshold = summarize_ddos([{"zoneId": 0, "status": False, "profile": "edge"}])
    assert threshold["zones"][0]["status"] is False
    assert threshold["zones"][0]["profile"] == "edge"


def test_unknown_tunnel_state_is_not_counted_as_down():
    result = summarize_tunnels([{"status": "Up"}, {"status": "Down"}, {"name": "unknown"}])
    assert (result["up"], result["down"], result["unknown"]) == (1, 1, 1)


@pytest.mark.parametrize("version", ["9.3", "9.4", "9.5", "9.6"])
def test_signature_update_get_is_classified_as_write(version):
    engine = CompatibilityEngine(load_profiles(Settings().profiles_dir))
    assert engine._profiles[version]["operations"]["orchestrator.idpsupdatesignaturefromportalpost"]["risk"] == "write"


def test_read_only_tool_blocks_signature_update_before_http(security_lab):
    server, _client, _state, requests, settings = security_lab
    settings.allow_write_tools = False
    result = invoke(server, "call_read_api", operation_id="orchestrator.idpsupdatesignaturefromportalpost")
    assert "not read-only" in result["error"]
    assert not any("updateSignatureFromPortal" in str(r.url) for r in requests)


@pytest.mark.parametrize("target", ["all", "", "1.NE,2.NE"])
def test_security_write_requires_one_explicit_target(security_lab, target):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id=target,
        body_json='{"enable":true}',
        confirm=True,
    )
    assert "error" in result
    assert not any(r.method != "GET" for r in requests)


def test_options_only_ngfw_replace_is_blocked(security_lab):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.securitymapspost612075",
        appliance_id="1.NE",
        body_json='{"options":{"merge":false,"templateApply":false}}',
        confirm=True,
    )
    assert "error" in result
    assert not any(r.method != "GET" for r in requests)


def test_posture_reads_ddos_and_marks_missing_evidence(security_lab):
    server, _client, state, requests, _settings = security_lab
    state["errors"]["/idsips/state"] = 503
    result = invoke(server, "get_security_posture", appliance_id="1.NE")
    assert result["coverage_complete"] is False
    assert result["finding_count"] > 0
    assert "ddos" in result["appliances"][0]
    paths = {r.url.params.get("url") for r in requests}
    assert {"/security/ddos/protectionProfile", "/security/ddos/thresholdStatus"} <= paths


@pytest.mark.parametrize("value", ["../WAN", "x?y", "x#y", "x\\y", "%2F", "..", "\n"])
def test_route_parameters_cannot_escape_the_security_path(value):
    with pytest.raises(ValueError):
        render_path("/securityMaps/{mapName}", {"mapName": value})


def test_postman_colon_paths_are_rendered():
    assert render_path("/zones/:zoneId", {"zoneId": "0"}) == "/zones/0"


def test_unsupported_ids_event_window_is_not_silently_ignored(security_lab):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(server, "get_ids_ips_events", appliance_id="1.NE", start_time="100", end_time="200")
    assert "error" in result
    assert not any(r.url.params.get("url") == "/idsips/events" for r in requests)


@pytest.mark.parametrize("version", ["9.3", "9.4", "9.5", "9.6"])
@pytest.mark.parametrize("tool", ["get_ids_ips_state", "get_ddos_status", "get_zone_matrix", "get_security_posture"])
def test_security_read_tools_use_real_profile_proxy_and_explicit_target(security_lab, version, tool):
    server, _client, state, requests, settings = security_lab
    state["version"] = version + ".1"
    settings.allow_write_tools = False
    result = invoke(server, tool, appliance_id="1.NE")
    assert "error" not in result
    proxy = [r for r in requests if r.url.path.endswith("/appliance/rest")]
    assert proxy
    assert all(r.method == "GET" and r.url.params["nePk"] == "1.NE" for r in proxy)
    assert all("{" not in r.url.params["url"] and "/:" not in r.url.params["url"] for r in proxy)
    assert all(r.headers["X-Auth-Token"] == "fixture" for r in requests)


def test_ids_fanout_preserves_other_appliance_when_one_fails(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["per_ne_errors"][("1.NE", "/idsips/state")] = 503
    result = invoke(server, "get_ids_ips_state", appliance_id="all")
    assert len(result["appliances"]) == 2
    assert result["appliances"][0]["evidence_status"] == "error"
    assert result["appliances"][1]["prevention_enabled"] is True
    assert result["coverage_complete"] is False


def test_posture_empty_inventory_is_a_coverage_gap(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["inventory"] = []
    result = invoke(server, "get_security_posture", appliance_id="all")
    assert result["appliances"] == []
    assert result["coverage_complete"] is False
    assert result["findings"][0]["kind"] == "coverage_gap"


@pytest.mark.parametrize(
    "path",
    [
        "/idsips/state",
        "/zones",
        "/securityMaps",
        "/securityMapsSettings",
        "/security/ddos/protectionProfile",
        "/security/ddos/thresholdStatus",
        "/tunnelsConfigAndState",
    ],
)
@pytest.mark.parametrize("status", [403, 503])
def test_posture_read_errors_are_findings_and_other_controls_continue(security_lab, path, status):
    server, _client, state, requests, _settings = security_lab
    state["errors"][path] = status
    result = invoke(server, "get_security_posture", appliance_id="1.NE")
    assert result["coverage_complete"] is False
    assert any(
        item["kind"] == "collection_error" and f"HTTP {status}" in item["finding"] for item in result["findings"]
    )
    assert len({r.url.params.get("url") for r in requests if r.url.params.get("url")}) >= 4


@pytest.mark.parametrize("mode,severity", [("Off", "high"), ("IDS Only", "medium"), ("IPS-Magic", "medium")])
def test_posture_exposes_disabled_detection_prevention_and_unknown(security_lab, mode, severity):
    server, _client, state, _requests, _settings = security_lab
    state["ids"]["mode"] = mode
    result = invoke(server, "get_security_posture", appliance_id="1.NE")
    ids_findings = [item for item in result["findings"] if item["control"] == "ids_ips"]
    assert ids_findings and ids_findings[0]["severity"] == severity


def test_ddos_disabled_zone_zero_is_reported(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["profiles"]["profiles"][0]["enable"] = False
    result = invoke(server, "get_security_posture", appliance_id="1.NE")
    assert result["appliances"][0]["ddos"]["protection_profiles"]["disabled_zones"] == [0]
    assert any(item["control"] == "ddos" and item["severity"] == "high" for item in result["findings"])


@pytest.mark.parametrize("provider", ["zscaler", "netskope", "axis"])
def test_sse_connectivity_never_claims_web_filter_protection(security_lab, provider):
    server, _client, _state, _requests, _settings = security_lab
    result = invoke(server, "get_web_filter_status", appliance_id="1.NE", provider=provider)
    assert result["policy_status"] == "not_observed"
    assert result["coverage_complete"] is False
    assert result["enforcement_verified"] is False
    assert result["appliance_associated"] is False


def test_web_filter_errors_do_not_become_a_protected_state(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["errors"]["/thirdPartyServices/zscaler/connectivity"] = 403
    result = invoke(server, "get_web_filter_status", appliance_id="1.NE", provider="zscaler")
    assert "error" in result
    assert result["enforcement_verified"] is False


@pytest.mark.parametrize(
    "date,lines", [("../WAN", 10), ("2026-02-30", 10), ("2026-1-1", 10), ("2026-10-06", 0), ("2026-10-06", 1001)]
)
def test_security_log_rejects_bad_date_and_unbounded_lines(security_lab, date, lines):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(server, "get_security_log", appliance_id="1.NE", date=date, lines=lines)
    assert "error" in result
    assert not any("logViewer" in r.url.params.get("url", "") for r in requests)


def test_firewall_log_preserves_ipv6_quotes_actions_and_flow_ids(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["log"] = {
        "data": {
            "logEntries": [
                [
                    "t1",
                    'Action:drop, Reason:"blocked, category:lab", SrcAddr:2001:db8::1, Flow-ID:0, FromZone:LAN, ToZone:WAN, Application:lab,',
                ],
                {"timestamp": "t2", "Action": "allow", "FromZone": "LAN", "ToZone": "WAN"},
            ]
        }
    }
    result = invoke(server, "get_security_log", appliance_id="1.NE", date="2026-10-06", lines=2)
    assert result["entries"][0]["SrcAddr"] == "2001:db8::1"
    assert result["entries"][0]["Reason"] == "blocked, category:lab"
    assert result["entries"][0]["Flow-ID"] == "0"
    assert result["summary"]["actions"] == {"drop": 1, "allow": 1}
    assert result["summary"]["zone_pairs"] == {"LAN->WAN": 2}


@pytest.mark.parametrize("limit", [0, -1, 1001])
def test_ids_events_have_bounded_results(security_lab, limit):
    server, _client, _state, requests, _settings = security_lab
    assert "error" in invoke(server, "get_ids_ips_events", appliance_id="1.NE", limit=limit)
    assert not any(r.url.params.get("url") == "/idsips/events" for r in requests)


def test_ids_events_truncation_is_explicit(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["events"] *= 3
    result = invoke(server, "get_ids_ips_events", appliance_id="1.NE", limit=1)
    assert (result["total_events"], result["returned"], result["truncated"], result["time_filter_applied"]) == (
        3,
        1,
        True,
        False,
    )


@pytest.mark.parametrize("tool", ["get_ids_ips_events", "get_ddos_status", "get_zone_matrix", "get_security_log"])
def test_single_target_security_reads_reject_all(security_lab, tool):
    server, _client, _state, requests, _settings = security_lab
    assert "error" in invoke(server, tool, appliance_id="all")
    assert not any(r.url.path.endswith("/appliance/rest") for r in requests)


def test_ambiguous_appliance_name_never_writes_first_match(security_lab):
    server, _client, state, requests, _settings = security_lab
    state["inventory"][1]["name"] = "lab-a"
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id="lab-a",
        body_json='{"enable":true}',
        confirm=True,
    )
    assert "ambiguous" in result["error"]
    assert not any(r.method != "GET" for r in requests)


@pytest.mark.parametrize("enable", ["false", 0, 1, None])
def test_ids_engine_enable_requires_boolean(security_lab, enable):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id="1.NE",
        body_json=json.dumps({"enable": enable}),
        confirm=True,
    )
    assert "error" in result
    assert not any(r.method != "GET" for r in requests)


def test_disabling_ids_requires_dangerous_permission(security_lab):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id="1.NE",
        body_json='{"enable":false}',
        confirm=True,
    )
    assert "EC_ALLOW_DANGEROUS_WRITES=true" in result["error"]
    assert not any(r.method != "GET" for r in requests)


@pytest.mark.parametrize("parameter", [{"nePk": "2.NE"}, {"url": "/zones"}])
def test_proxy_routing_cannot_be_overridden(security_lab, parameter):
    _server, client, _state, requests, _settings = security_lab
    with pytest.raises(ValueError, match="cannot be overridden"):
        client.appliance_api_call("9.6", "1.NE", "appliance.getidsipsstate405371", **parameter)
    assert requests == []


def prepare_plan(lab, control="ids_ips", **arguments):
    server, _client, _state, _requests, _settings = lab
    if control == "ids_ips":
        arguments.setdefault("mode", "IPS-Inline")
    else:
        arguments.setdefault("profile_name", "edge")
    result = invoke(server, "prepare_security_remediation", appliance_id="1.NE", control=control, **arguments)
    assert "error" not in result, result
    return result["plan"]


@pytest.fixture()
def remediation_lab(security_lab):
    _server, _client, state, _requests, _settings = security_lab
    state["profiles"] = {
        "profiles": [
            {"profile_name": "edge", "enable": False, "udp_verify": False, "aggr_age_time": 30},
            {"profile_name": "other", "enable": True},
        ],
        "profileMaps": [{"zone_id": 0, "profile_name": "edge"}, {"zone_id": 1, "profile_name": "other"}],
    }
    return security_lab


def apply_plan(lab, plan, **arguments):
    return invoke(
        lab[0],
        "apply_security_remediation",
        plan_id=plan["plan_id"],
        confirmation=plan["confirmation_required"],
        confirm=True,
        **arguments,
    )


@pytest.mark.parametrize("version", ["9.3", "9.4", "9.5", "9.6"])
@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_remediation_preserves_complete_scope_and_verifies_real_http(remediation_lab, version, control):
    _server, _client, state, requests, _settings = remediation_lab
    state["version"] = version + ".1"
    before = deepcopy(state["ids_global"] if control == "ids_ips" else state["profiles"])
    plan = prepare_plan(remediation_lab, control)
    assert plan["api_profile"] == version
    assert plan["change"]["affected_appliances"] == ["1.NE"]
    assert not any(r.method != "GET" for r in requests)
    result = apply_plan(remediation_lab, plan)
    assert result["applied"] is result["verified"] is True
    assert result["enforcement_verified"] is False
    writes = [r for r in requests if r.method != "GET"]
    assert len(writes) == 1
    body = json.loads(writes[0].content)
    if control == "ids_ips":
        assert writes[0].method == "PUT"
        assert writes[0].url.path.endswith("/ids/state")
        assert set(body) == {"ips_inline", "ips_lookaside", "ids", "disabled"}
        assert body["ips_inline"] == ["1.NE", "2.NE"]
        assert body["disabled"] == []
    else:
        assert writes[0].method == "POST"
        assert writes[0].url.params["nePk"] == "1.NE"
        assert writes[0].url.params["url"] == "/security/ddos/protectionProfile"
        assert body["profileMaps"] == before["profileMaps"]
        assert body["profiles"][0]["enable"] is True
        assert body["profiles"][0]["udp_verify"] is False
        assert body["profiles"][1] == before["profiles"][1]


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_prepare_and_dry_run_work_with_writes_disabled(remediation_lab, control):
    server, _client, _state, requests, settings = remediation_lab
    settings.allow_write_tools = False
    plan = prepare_plan(remediation_lab, control)
    assert invoke(server, "apply_security_remediation", plan_id=plan["plan_id"])["dry_run"] is True
    assert "Write tools are disabled" in apply_plan(remediation_lab, plan)["error"]
    assert not any(r.method != "GET" for r in requests)


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
@pytest.mark.parametrize("confirmation", ["", "APPLY another-plan", "ROLLBACK another-plan"])
def test_remediation_confirmation_is_bound_to_plan(remediation_lab, control, confirmation):
    server, _client, _state, requests, _settings = remediation_lab
    plan = prepare_plan(remediation_lab, control)
    result = invoke(
        server, "apply_security_remediation", plan_id=plan["plan_id"], confirmation=confirmation, confirm=True
    )
    assert "Confirmation phrase" in result["error"]
    assert not any(r.method != "GET" for r in requests)


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_remediation_conflict_blocks_write_and_does_not_consume_quota(remediation_lab, control):
    _server, _client, state, requests, settings = remediation_lab
    settings.max_writes_per_minute = 1
    plan = prepare_plan(remediation_lab, control)
    if control == "ids_ips":
        state["ids_global"]["ips_inline"] = []
        state["ids_global"]["ids"] = ["2.NE"]
    else:
        state["profiles"]["profiles"][1]["comment"] = "changed by another operator"
    assert "conflict" in apply_plan(remediation_lab, plan)["error"]
    assert not any(r.method != "GET" for r in requests)
    fresh = prepare_plan(remediation_lab, control)
    assert apply_plan(remediation_lab, fresh)["verified"] is True
    assert len([r for r in requests if r.method != "GET"]) == 1


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_accepted_write_without_desired_state_is_not_verified_or_repeated(remediation_lab, control):
    _server, _client, state, requests, _settings = remediation_lab
    plan = prepare_plan(remediation_lab, control)
    state["ignore_write"] = True
    result = apply_plan(remediation_lab, plan)
    assert result["applied"] is True and result["verified"] is False
    assert result["plan"]["status"] == "verification_failed"
    assert "only prepared" in apply_plan(remediation_lab, plan)["error"]
    assert len([r for r in requests if r.method != "GET"]) == 1


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_failed_read_after_write_keeps_applied_and_recovers_by_verify(remediation_lab, control):
    server, _client, state, requests, _settings = remediation_lab
    plan = prepare_plan(remediation_lab, control)
    state["verification_error"] = 503
    result = apply_plan(remediation_lab, plan)
    assert result["applied"] is True and result["verified"] is False
    assert "HTTP 503" in result["verification_error"]
    state["errors"].clear()
    assert invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])["verified"] is True
    assert len([r for r in requests if r.method != "GET"]) == 1


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_lost_write_response_is_unknown_until_verified_without_replay(remediation_lab, control):
    server, _client, state, requests, _settings = remediation_lab
    plan = prepare_plan(remediation_lab, control)
    state["write_timeout"] = True
    result = apply_plan(remediation_lab, plan)
    assert result["applied"] is None and result["verified"] is False
    assert result["plan"]["status"] == "apply_unknown"
    assert "error" in apply_plan(remediation_lab, plan)
    assert invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])["verified"] is True
    assert len([r for r in requests if r.method != "GET"]) == 1


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_rollback_requires_second_lock_and_restores_complete_snapshot(remediation_lab, control):
    server, _client, state, requests, settings = remediation_lab
    before = deepcopy(state["ids_global"] if control == "ids_ips" else state["profiles"])
    plan = prepare_plan(remediation_lab, control)
    assert apply_plan(remediation_lab, plan)["verified"] is True
    arguments = {"plan_id": plan["plan_id"], "confirmation": plan["rollback_confirmation_required"], "confirm": True}
    assert "EC_ALLOW_DANGEROUS_WRITES=true" in invoke(server, "rollback_security_remediation", **arguments)["error"]
    assert invoke(server, "rollback_security_remediation", plan_id=plan["plan_id"])["dry_run"] is True
    settings.allow_dangerous_writes = True
    result = invoke(server, "rollback_security_remediation", **arguments)
    assert result["rolled_back"] is result["verified"] is True
    assert state["ids_global" if control == "ids_ips" else "profiles"] == before
    assert invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])["verified"] is True
    assert len([r for r in requests if r.method != "GET"]) == 2


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_rollback_conflict_preserves_another_operators_changes(remediation_lab, control):
    server, _client, state, requests, settings = remediation_lab
    settings.allow_dangerous_writes = True
    plan = prepare_plan(remediation_lab, control)
    assert apply_plan(remediation_lab, plan)["verified"] is True
    if control == "ids_ips":
        state["ids_global"]["ips_inline"].remove("2.NE")
        state["ids_global"]["disabled"].append("2.NE")
    else:
        state["profiles"]["profiles"][1]["comment"] = "another operator"
    result = invoke(
        server,
        "rollback_security_remediation",
        plan_id=plan["plan_id"],
        confirmation=plan["rollback_confirmation_required"],
        confirm=True,
    )
    assert "drifted" in result["error"]
    assert len([r for r in requests if r.method != "GET"]) == 1


def test_security_plan_expiry_prevents_write(remediation_lab, monkeypatch):
    import ec_mcp.security_remediation as module

    plan = prepare_plan(remediation_lab)
    clock = module.time.monotonic()
    monkeypatch.setattr(module.time, "monotonic", lambda: clock + 601)
    assert "expired" in apply_plan(remediation_lab, plan)["error"]
    assert not any(r.method != "GET" for r in remediation_lab[3])


def test_appliance_disappearing_before_prepare_is_not_remediated(remediation_lab):
    server, _client, state, requests, _settings = remediation_lab
    state["inventory"] = []
    result = invoke(server, "prepare_security_remediation", appliance_id="1.NE", control="ids_ips", mode="IPS-Inline")
    assert "refreshed appliance inventory" in result["error"]
    assert not any(r.method != "GET" for r in requests)


def test_profile_change_after_preparation_blocks_remediation(remediation_lab):
    _server, client, _state, requests, _settings = remediation_lab
    plan = prepare_plan(remediation_lab)
    client._cached_profile = "9.5"
    assert "profile changed" in apply_plan(remediation_lab, plan)["error"]
    assert not any(r.method != "GET" for r in requests)


def test_downgrading_ips_requires_extra_permission(remediation_lab):
    server, _client, state, requests, settings = remediation_lab
    state["ids_global"] = {"ips_inline": ["1.NE", "2.NE"], "ips_lookaside": [], "ids": [], "disabled": []}
    plan = prepare_plan(remediation_lab, mode="IDS Only")
    assert plan["requires_dangerous_writes"] is True
    assert "EC_ALLOW_DANGEROUS_WRITES=true" in apply_plan(remediation_lab, plan)["error"]
    assert not any(r.method != "GET" for r in requests)
    settings.allow_dangerous_writes = True
    assert apply_plan(remediation_lab, plan)["verified"] is True
    assert invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])["verified"] is True


@pytest.mark.parametrize("control", ["ngfw", "web_filtering", "arbitrary"])
def test_unsupported_remediation_is_blocked_before_any_http(remediation_lab, control):
    server, _client, _state, requests, _settings = remediation_lab
    result = invoke(server, "prepare_security_remediation", appliance_id="1.NE", control=control)
    assert "validated contracts" in result["error"]
    assert requests == []


def test_concurrent_requests_for_one_plan_make_at_most_one_write(remediation_lab):
    plan = prepare_plan(remediation_lab)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: apply_plan(remediation_lab, plan), range(2)))
    assert sum(result.get("verified", False) for result in results) == 1
    assert len([r for r in remediation_lab[3] if r.method != "GET"]) == 1


def test_two_global_ids_plans_cannot_overwrite_each_others_updates(remediation_lab):
    server, _client, state, requests, settings = remediation_lab
    settings.allow_dangerous_writes = True
    first = prepare_plan(remediation_lab)
    second = invoke(server, "prepare_security_remediation", appliance_id="2.NE", control="ids_ips", mode="IDS Only")[
        "plan"
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda plan: apply_plan(remediation_lab, plan), [first, second]))
    assert sum(result.get("verified", False) for result in results) == 1
    assert any("conflict" in result.get("error", "") for result in results)
    assert len([r for r in requests if r.method != "GET"]) == 1
    assert sorted(member for members in state["ids_global"].values() for member in members) == ["1.NE", "2.NE"]


def test_security_plan_snapshots_and_secrets_stay_out_of_public_output_and_audit(remediation_lab):
    _server, _client, state, _requests, settings = remediation_lab
    sentinel = "lab-sensitive-value"
    state["profiles"]["profiles"][0]["password"] = sentinel
    plan = prepare_plan(remediation_lab, "ddos")
    result = apply_plan(remediation_lab, plan)
    assert result["verified"] is True
    assert sentinel not in json.dumps(plan)
    assert sentinel not in json.dumps(result)
    assert sentinel not in settings.audit_log_path.read_text()
    assert "before" not in plan and "candidate" not in plan


@pytest.mark.parametrize("target", ["all", "1.NE,2.NE"])
def test_generic_security_read_expands_each_appliance_through_proxy(security_lab, target):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(server, "call_read_api", operation_id="appliance.getidsipsstate405371", appliance_id=target)
    assert "error" not in result
    proxy = [r for r in requests if r.url.params.get("url") == "/idsips/state"]
    assert {r.url.params["nePk"] for r in proxy} == {"1.NE", "2.NE"}
    assert not any(r.url.path.endswith("/idsips/state") for r in requests)


def test_sse_association_is_scoped_without_proving_web_filtering(security_lab):
    server, _client, _state, _requests, _settings = security_lab
    result = invoke(server, "get_web_filter_status", appliance_id="2.NE", provider="zscaler")
    assert result["appliance_associated"] is True
    assert result["policy_status"] == "not_observed"
    assert result["enforcement_verified"] is False


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
@pytest.mark.parametrize("status", [403, 503])
def test_remediation_http_errors_are_uncertain_and_are_not_retried(remediation_lab, control, status):
    plan = prepare_plan(remediation_lab, control)
    remediation_lab[2]["write_status"] = status
    result = apply_plan(remediation_lab, plan)
    assert result["applied"] is None
    assert result["verified"] is False
    assert f"HTTP {status}" in result["error"]
    assert "error" in apply_plan(remediation_lab, plan)
    assert len([r for r in remediation_lab[3] if r.method != "GET"]) == 1


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_rollback_verification_error_preserves_accepted_write(remediation_lab, control):
    server, _client, state, requests, settings = remediation_lab
    plan = prepare_plan(remediation_lab, control)
    assert apply_plan(remediation_lab, plan)["verified"] is True
    settings.allow_dangerous_writes = True
    state["verification_error"] = 503
    result = invoke(
        server,
        "rollback_security_remediation",
        plan_id=plan["plan_id"],
        confirmation=plan["rollback_confirmation_required"],
        confirm=True,
    )
    assert result["rolled_back"] is True and result["verified"] is False
    assert result["plan"]["status"] == "rollback_verification_failed"
    state["errors"].clear()
    assert invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])["verified"] is True
    assert len([r for r in requests if r.method != "GET"]) == 2


def test_security_plan_verification_does_not_assume_ownership_before_apply(remediation_lab):
    server, _client, _state, _requests, _settings = remediation_lab
    plan = prepare_plan(remediation_lab)
    result = invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])
    assert result["verified"] is False
    assert result["plan"]["status"] == "prepared"


def test_security_read_error_response_does_not_expose_credentials(security_lab, monkeypatch):
    _server, client, _state, _requests, _settings = security_lab
    sentinel = "lab-only-password"
    client._settings.orchestrator_password = sentinel
    response = httpx.Response(403, json={"message": f"denied password={sentinel}; token=fixture"})
    text = client._error_message(response, "GET /idsips/state")
    assert sentinel not in text and "fixture" not in text
    assert "HTTP 403" in text


@pytest.mark.parametrize("status", [200, 204, 404])
def test_side_effecting_get_never_retries_and_invalidates_cache(status):
    requests = []
    engine = CompatibilityEngine(load_profiles(Settings().profiles_dir))

    def handler(request):
        requests.append(request)
        return httpx.Response(status)

    http = httpx.Client(base_url="https://orch.example", transport=httpx.MockTransport(handler))
    client = OrchestratorClient(
        Settings(orchestrator_url="https://orch.example", orchestrator_api_key="fixture"), engine, http
    )
    try:
        client._appliances_cache = [{"nePk": "1.NE"}]
        if status == 404:
            with pytest.raises(RuntimeError, match="HTTP 404"):
                client.call("9.6", "orchestrator.idpsupdatesignaturefromportalpost")
        else:
            assert client.call("9.6", "orchestrator.idpsupdatesignaturefromportalpost") == {"ok": True}
        assert len(requests) == 1
        assert client._appliances_cache is None
    finally:
        client.close()


@pytest.mark.parametrize("route", ["raw", "proxy", "raw_proxy"])
def test_side_effecting_get_cannot_enter_cached_read_transports(security_lab, route):
    _server, client, _state, requests, _settings = security_lab
    with pytest.raises(ValueError, match="Side-effecting"):
        if route == "raw":
            client.get_raw("/ids/updateSignatureFromPortal")
        elif route == "proxy":
            client.appliance_api_get("1.NE", "/ids/updateSignatureFromPortal")
        else:
            client.get_raw("/appliance/rest", nePk="1.NE", url="/ids/updateSignatureFromPortal")
    assert requests == []


def test_signature_update_get_requires_confirmed_write_tool(security_lab):
    server, _client, _state, requests, settings = security_lab
    operation = "orchestrator.idpsupdatesignaturefromportalpost"
    assert invoke(server, "apply_change", operation_id=operation)["dry_run"] is True
    assert not any("updateSignatureFromPortal" in str(r.url) for r in requests)
    settings.allow_write_tools = False
    assert "Write tools are disabled" in invoke(server, "apply_change", operation_id=operation, confirm=True)["error"]
    settings.allow_write_tools = True
    assert invoke(server, "apply_change", operation_id=operation, confirm=True)["applied"] is True
    assert len([r for r in requests if "updateSignatureFromPortal" in str(r.url)]) == 1


def test_write_verification_cannot_mutate_ids_signatures(security_lab):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id="1.NE",
        body_json='{"enable":true}',
        verify_operation_id="orchestrator.idpsupdatesignaturefromportalpost",
        confirm=True,
    )
    assert "verify_operation_id" in result["error"]
    assert not any(r.method != "GET" or "updateSignatureFromPortal" in str(r.url) for r in requests)


def test_unrecognized_sse_association_is_unknown_not_false(security_lab):
    server, _client, state, _requests, _settings = security_lab
    state["associations"] = {"unknownVendorShape": {"opaque": True}}
    result = invoke(server, "get_web_filter_status", appliance_id="1.NE", provider="zscaler")
    assert result["appliance_associated"] is None
    assert result["association_evidence_status"] == "unknown"


def test_target_disappearing_after_prepare_blocks_apply(remediation_lab):
    plan = prepare_plan(remediation_lab)
    remediation_lab[2]["inventory"] = []
    assert "disappeared" in apply_plan(remediation_lab, plan)["error"]
    assert not any(r.method != "GET" for r in remediation_lab[3])


@pytest.mark.parametrize("control", ["ids_ips", "ddos"])
def test_lost_rollback_response_is_verified_without_replaying(remediation_lab, control):
    server, _client, state, requests, settings = remediation_lab
    plan = prepare_plan(remediation_lab, control)
    assert apply_plan(remediation_lab, plan)["verified"] is True
    settings.allow_dangerous_writes = True
    state["write_timeout"] = True
    result = invoke(
        server,
        "rollback_security_remediation",
        plan_id=plan["plan_id"],
        confirmation=plan["rollback_confirmation_required"],
        confirm=True,
    )
    assert result["rolled_back"] is None and result["verified"] is False
    assert result["plan"]["status"] == "rollback_unknown"
    assert invoke(server, "verify_security_remediation", plan_id=plan["plan_id"])["verified"] is True
    assert len([r for r in requests if r.method != "GET"]) == 2


@pytest.mark.parametrize("appliance", [False, True])
def test_timeout_after_mutation_also_invalidates_read_caches(appliance):
    engine = CompatibilityEngine(load_profiles(Settings().profiles_dir))

    def handler(request):
        raise httpx.ReadTimeout("uncertain mutation", request=request)

    http = httpx.Client(base_url="https://orch.example", transport=httpx.MockTransport(handler))
    client = OrchestratorClient(
        Settings(orchestrator_url="https://orch.example", orchestrator_api_key="fixture"), engine, http
    )
    try:
        client._appliances_cache = [{"nePk": "1.NE"}]
        client._response_cache[("/resource", ())] = (1.0, {"old": True})
        with pytest.raises(httpx.ReadTimeout):
            if appliance:
                client.appliance_api_call(
                    "9.6", "1.NE", "appliance.updateidsipsstate857090", json_body={"enable": True}
                )
            else:
                client.call("9.6", "orchestrator.idpsstateput", json_body={})
        assert client._appliances_cache is None and client._response_cache == {}
    finally:
        client.close()


def test_audit_failure_before_security_write_blocks_transport_without_consuming_quota(remediation_lab, monkeypatch):
    from ec_mcp.audit import AuditLog

    plan = prepare_plan(remediation_lab)
    remediation_lab[4].max_writes_per_minute = 1
    original = AuditLog.record

    def fail_attempt(self, tool, action, target, result, **kwargs):
        if result == "attempt":
            raise OSError("lab audit unavailable")
        return original(self, tool, action, target, result, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(AuditLog, "record", fail_attempt)
        assert "Cannot record security write attempt" in apply_plan(remediation_lab, plan)["error"]
        assert not any(r.method != "GET" for r in remediation_lab[3])
    assert apply_plan(remediation_lab, plan)["verified"] is True


def test_audit_failure_after_security_write_keeps_applied_and_verified(remediation_lab, monkeypatch):
    from ec_mcp.audit import AuditLog

    plan = prepare_plan(remediation_lab)
    original = AuditLog.record

    def fail_after_write(self, tool, action, target, result, **kwargs):
        if tool == "apply_security_remediation" and result == "verified":
            raise OSError("lab audit unavailable after apply")
        return original(self, tool, action, target, result, **kwargs)

    monkeypatch.setattr(AuditLog, "record", fail_after_write)
    result = apply_plan(remediation_lab, plan)
    assert result["applied"] is True and result["verified"] is True
    assert "audit unavailable" in result["audit_error"]
    assert len([r for r in remediation_lab[3] if r.method != "GET"]) == 1


@pytest.mark.parametrize(
    "operation,body",
    [
        ("orchestrator.idpsconfigput", {"auto": "on"}),
        ("orchestrator.idpsprofilestateput", {"edge": ["1.NE"]}),
        ("orchestrator.idpssignaturesprofilesput", [{"name": "edge", "signatureIds": [1]}]),
        ("appliance.updateidsipsconfig513306", {"opaque": True}),
        ("appliance.updateidsipssignature369665", {"opaque": True}),
        ("appliance.securitymapssettingspost825047", {"defaultAction": "allow"}),
    ],
)
def test_unvalidated_global_or_firewall_payloads_are_blocked(security_lab, operation, body):
    server, _client, _state, requests, _settings = security_lab
    result = invoke(
        server, "apply_change", operation_id=operation, appliance_id="1.NE", body_json=json.dumps(body), confirm=True
    )
    assert "unsupported" in result["error"]
    assert not any(r.method != "GET" for r in requests)


def test_generic_security_write_timeout_is_explicitly_unknown(security_lab):
    server, _client, state, requests, _settings = security_lab
    state["write_timeout"] = True
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id="1.NE",
        body_json='{"enable":true}',
        confirm=True,
    )
    assert result["applied"] is None
    assert result["write_status"] == "unknown"
    assert len([r for r in requests if r.method != "GET"]) == 1


def test_generic_write_post_audit_failure_preserves_applied(security_lab, monkeypatch):
    from ec_mcp.audit import AuditLog

    server, _client, _state, requests, _settings = security_lab
    original = AuditLog.record

    def fail_after_write(self, tool, action, target, result, **kwargs):
        if tool == "apply_change" and result == "ok":
            raise OSError("lab audit unavailable after generic apply")
        return original(self, tool, action, target, result, **kwargs)

    monkeypatch.setattr(AuditLog, "record", fail_after_write)
    result = invoke(
        server,
        "apply_change",
        operation_id="appliance.updateidsipsstate857090",
        appliance_id="1.NE",
        body_json='{"enable":true}',
        confirm=True,
    )
    assert result["applied"] is True
    assert "audit unavailable" in result["audit_error"]
    assert len([r for r in requests if r.method != "GET"]) == 1
