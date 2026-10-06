"""Validate vendor-described replacement shapes; missing schemas stay blocked."""

from __future__ import annotations

from copy import deepcopy

import pytest

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.config import Settings
from ec_mcp.security_remediation import prepare_security_plan, validate_ddos_snapshot, validate_ids_snapshot
from ec_mcp.security_workflow import (
    DDOS_PROTECTION_PROFILE_READ,
    DDOS_THRESHOLD_STATUS_READ,
    IDS_IPS_EVENTS_READ,
    IDS_IPS_STATE_READ,
    LOG_VIEWER_FILE_READ,
    SECURITY_MAP_SETTINGS_READ,
    SECURITY_MAPS_READ,
    ZONE_LIST_READ,
    summarize_ddos,
    summarize_zone_matrix,
)

pytestmark = pytest.mark.security

IDS = {"ips_inline": ["2.NE"], "ips_lookaside": [], "ids": [], "disabled": ["1.NE"]}
DDOS = {
    "profiles": [
        {
            "profile_name": "edge",
            "enable": False,
            "aggr_age_time": 30,
            "embryonic_time": 30,
            "embryonic_non_tcp_time": 30,
        }
    ],
    "profileMaps": [{"zone_id": 0, "profile_name": "edge"}],
}


@pytest.mark.parametrize("version", ["9.3", "9.4", "9.5", "9.6"])
def test_curated_security_operations_exist_in_all_compatibility_profiles(version):
    engine = CompatibilityEngine(load_profiles(Settings().profiles_dir))
    ops = engine._profiles[version]["operations"]
    for operation in (
        IDS_IPS_STATE_READ,
        IDS_IPS_EVENTS_READ,
        ZONE_LIST_READ,
        SECURITY_MAPS_READ,
        SECURITY_MAP_SETTINGS_READ,
        DDOS_PROTECTION_PROFILE_READ,
        DDOS_THRESHOLD_STATUS_READ,
        LOG_VIEWER_FILE_READ,
    ):
        assert ops[operation]["method"] == "GET"
    assert ops["orchestrator.idpsstateput"]["method"] == "PUT"
    assert ops["appliance.protectionprofilespost168495"]["method"] == "POST"


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"ips_inline": ["1.NE"]},
        {**IDS, "disabled": "1.NE"},
        {**IDS, "disabled": [1]},
        {**IDS, "disabled": ["1.ne"]},
        {**IDS, "disabled": ["2.NE"]},
        {**IDS, "ids": ["1.NE"]},
        {**IDS, "other": []},
    ],
)
def test_ids_replace_rejects_partial_duplicate_and_invalid_memberships(body):
    with pytest.raises(ValueError):
        validate_ids_snapshot(body)


@pytest.mark.parametrize("mode", ["IDS Only", "IPS-Performant", "IPS-Inline"])
def test_ids_remediation_changes_only_selected_membership(mode):
    before = deepcopy(IDS)
    plan = prepare_security_plan("1.NE", "9.6", "ids_ips", {"data": IDS}, mode=mode)
    assert IDS == before
    assert plan.candidate["ips_inline"].count("2.NE") == 1
    assert sorted(member for members in plan.candidate.values() for member in members) == ["1.NE", "2.NE"]
    assert plan.change["affected_appliances"] == ["1.NE"]


@pytest.mark.parametrize("target,mode", [("99.NE", "IPS-Inline"), ("1.NE", "IPS-Magic"), ("1.NE", "Off")])
def test_ids_remediation_rejects_unknown_target_mode_and_noop(target, mode):
    with pytest.raises(ValueError):
        prepare_security_plan(target, "9.6", "ids_ips", IDS, mode=mode)


@pytest.mark.parametrize(
    "key,value",
    [
        ("enable", "false"),
        ("enable", 0),
        ("profile_name", ""),
        ("profile_name", 1),
        ("spoof_check", "true"),
        ("udp_verify", 1),
        ("aggr_age_time", 14),
        ("aggr_age_time", 46),
        ("aggr_age_time", True),
        ("embryonic_time", 19),
        ("embryonic_time", 46),
        ("embryonic_non_tcp_time", 19),
        ("embryonic_non_tcp_time", 46),
    ],
)
def test_ddos_profile_rejects_wrong_types_and_vendor_range_violations(key, value):
    body = deepcopy(DDOS)
    body["profiles"][0][key] = value
    with pytest.raises(ValueError):
        validate_ddos_snapshot(body)


@pytest.mark.parametrize(
    "key,values", [("aggr_age_time", (15, 45)), ("embryonic_time", (20, 45)), ("embryonic_non_tcp_time", (20, 45))]
)
def test_ddos_profile_accepts_vendor_range_boundaries(key, values):
    for value in values:
        body = deepcopy(DDOS)
        body["profiles"][0][key] = value
        assert validate_ddos_snapshot(body)["profiles"][0][key] == value


@pytest.mark.parametrize("zone_id", [-1, True, "0", None])
def test_ddos_zone_assignment_requires_integer_including_zero(zone_id):
    body = deepcopy(DDOS)
    body["profileMaps"][0]["zone_id"] = zone_id
    with pytest.raises(ValueError):
        validate_ddos_snapshot(body)
    assert validate_ddos_snapshot(DDOS)["profileMaps"][0]["zone_id"] == 0


@pytest.mark.parametrize(
    "mutation", ["missing_maps", "missing_profiles", "duplicate_profile", "duplicate_zone", "unknown_profile"]
)
def test_ddos_replace_requires_complete_unambiguous_assignments(mutation):
    body = deepcopy(DDOS)
    if mutation == "missing_maps":
        body.pop("profileMaps")
    elif mutation == "missing_profiles":
        body.pop("profiles")
    elif mutation == "duplicate_profile":
        body["profiles"] *= 2
    elif mutation == "duplicate_zone":
        body["profileMaps"] *= 2
    else:
        body["profileMaps"][0]["profile_name"] = "absent"
    with pytest.raises(ValueError):
        validate_ddos_snapshot(body)


@pytest.mark.parametrize("case", ["missing_profile", "unassigned_profile", "already_enabled"])
def test_ddos_remediation_rejects_missing_unassigned_and_noop_profiles(case):
    body = deepcopy(DDOS)
    name = "absent" if case == "missing_profile" else "edge"
    if case == "unassigned_profile":
        body["profileMaps"] = []
    if case == "already_enabled":
        body["profiles"][0]["enable"] = True
    with pytest.raises(ValueError):
        prepare_security_plan("1.NE", "9.6", "ddos", body, profile_name=name)


def test_ddos_ambiguous_profile_never_reports_enabled_protection():
    body = deepcopy(DDOS)
    body["profiles"].append({"profile_name": "edge", "enable": True})
    result = summarize_ddos(body)
    assert result["protection_enabled"] is None
    assert result["evidence_status"] == "unknown"


def test_ngfw_inventory_is_directional_and_missing_policy_is_not_an_allow():
    zones = [{"name": "LAN"}, {"name": "WAN"}]
    maps = [{"name": "edge", "rules": [{"zone1": "LAN", "zone2": "WAN", "action": "deny", "priority": 0}]}]
    result = summarize_zone_matrix(zones, maps, {"defaultAction": "deny"})
    assert result["uncovered_pairs"] == [["WAN", "LAN"]]
    assert result["default_action"] == "deny"
    assert result["maps"][0]["rules"][0]["priority"] == 0
    assert result["coverage_is_enforcement"] is False


def test_ngfw_priority_conflicts_and_invalid_zones_are_explicit():
    rule = {"zone1": "LAN", "zone2": "WAN", "action": "allow", "priority": 1}
    result = summarize_zone_matrix(
        [{"name": "LAN"}, {"name": "WAN"}], [{"name": "edge", "rules": [rule, rule, {**rule, "zone1": "absent"}]}]
    )
    assert result["ambiguous_priorities"] == 1
    assert result["invalid_rules"] == 1


def test_ngfw_large_matrix_retains_total_and_truncation_evidence():
    result = summarize_zone_matrix([{"name": str(i)} for i in range(10)], [])
    assert result["uncovered_pair_count"] == 90
    assert len(result["uncovered_pairs"]) == 40
    assert result["uncovered_pairs_truncated"] is True


def test_ngfw_unrecognized_vendor_policy_shape_stays_unknown():
    result = summarize_zone_matrix([{"name": "LAN"}], {"opaqueVendorPayload": "unvalidated"})
    assert result["evidence_status"] == "unknown"
    assert result["enforcement_verified"] is False


@pytest.mark.parametrize("action", [False, 0, None, "magic"])
def test_ngfw_unknown_actions_do_not_invent_policy_coverage(action):
    result = summarize_zone_matrix(
        [{"name": "LAN"}, {"name": "WAN"}],
        [{"name": "edge", "rules": [{"zone1": "LAN", "zone2": "WAN", "action": action}]}],
    )
    assert result["covered_pairs"] == 0
    assert result["invalid_rules"] == 1
    assert result["evidence_status"] == "unknown"


def test_ddos_duplicate_zone_assignment_is_unknown():
    body = deepcopy(DDOS)
    body["profiles"][0]["enable"] = True
    body["profileMaps"] *= 2
    result = summarize_ddos(body)
    assert result["protection_enabled"] is None
    assert result["evidence_status"] == "unknown"
