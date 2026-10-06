"""Security and troubleshooting workflow helpers for EdgeConnect.

Curated, read-oriented helpers over the raw Orchestrator/appliance API
catalog: IDS/IPS posture, zone-based security maps, DDoS thresholds,
site-to-site tunnel state, BGP/BFD health and SSE (Zscaler, Netskope,
Axis) integration status. Operation ids are the stable catalog ids from
the compatibility profiles (9.3-9.6).
"""

from __future__ import annotations

import re
from typing import Any

IDS_IPS_STATE_READ = "appliance.getidsipsstate405371"
IDS_IPS_EVENTS_READ = "appliance.getidsipsevents189513"
IDS_IPS_STATS_READ = "appliance.getidsipsstat757454"
IDS_PROFILE_STATE_READ = "orchestrator.idpsprofilestateget"
IDS_SIGNATURES_READ = "orchestrator.idpssignaturesget"
IDS_SIGNATURE_PROFILES_READ = "orchestrator.idpssignaturesprofilesget"

ZONE_LIST_READ = "appliance.getallzones257534"
SECURITY_MAPS_READ = "appliance.securitymapsget832281"
SECURITY_MAP_SETTINGS_READ = "appliance.securitymapssettingsget818893"
DDOS_PROTECTION_PROFILE_READ = "appliance.protectionprofilesget574729"
DDOS_THRESHOLD_STATUS_READ = "appliance.thresholdstatusget574729"

DEPLOYMENT_CONFIG_READ = "appliance.deployment729344"
TUNNELS_CONFIG_AND_STATE_READ = "appliance.tunnelsconfigandstate741932"
BONDED_TUNNELS_STATE_READ = "appliance.tunnelsconfigandstate525522"
THIRD_PARTY_TUNNELS_STATE_READ = "appliance.tunnelsconfigandstate574637"
BGP_STATE_READ = "orchestrator.bgpstate145"
BGP_NEIGHBOR_READ = "orchestrator.getneighbor142"
BFD_SESSIONS_READ = "orchestrator.bfdsessions139"

SSE_PROVIDERS = {
    "zscaler": {
        "connectivity": "orchestrator.zscalerconnectivityget853",
        "association": "orchestrator.zscalerassociationget849",
    },
    "netskope": {
        "connectivity": "orchestrator.netskopeconnectivityget853",
        "association": "orchestrator.netskopeassociationget849",
    },
    "axis": {
        "connectivity": "returns_axis_connectivity_status",
        "association": "returns_appliance_to_axis_association",
    },
}

IDS_IPS_MODES = {"Off", "IDS Only", "IPS-Performant", "IPS-Inline"}

LOG_VIEWER_DATE_RANGE_READ = "appliance.getdaterange457535"
LOG_VIEWER_FILE_READ = "appliance.getlogfile458377"
LOG_VIEWER_TYPES = ("Firewall", "Alarm", "Audit", "Event")


def unwrap_payload(payload: Any) -> Any:
    """Unwrap responses without treating false, zero or empty lists as absent."""
    for _ in range(8):
        if not isinstance(payload, dict):
            break
        wrapper = next((key for key in ("data", "result", "items", "configData") if key in payload), None)
        if wrapper is None:
            break
        payload = payload[wrapper]
    return payload


def parse_firewall_log_entries(payload: Any) -> list[dict[str, Any]]:
    """Parse raw or structured logViewer rows, preserving IPv6 and quoted commas."""
    payload = unwrap_payload(payload)
    rows = payload.get("logEntries", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    entries = []
    for row in rows:
        if isinstance(row, dict):
            entries.append(dict(row))
            continue
        if not isinstance(row, list) or len(row) < 2 or not isinstance(row[1], str):
            continue
        # A separator begins a new key:value field. Commas within quoted values
        # or plain-text reasons are data, not additional fields.
        parts = re.split(r',(?=\s*[A-Za-z][\w -]*\s*:)(?=(?:[^"\']|"[^"]*"|\'[^\']*\')*$)', row[1].rstrip(","))
        fields = {"timestamp": row[0]}
        for part in parts:
            key, separator, value = part.partition(":")
            if separator and key.strip():
                fields[key.strip()] = value.strip().strip('"').strip("'")
        entries.append(fields)
    return entries


def summarize_security_log(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a security summary: actions, drops, zones and applications."""
    actions: dict[str, int] = {}
    drop_reasons: dict[str, int] = {}
    zone_pairs: dict[str, int] = {}
    applications: dict[str, int] = {}
    for entry in entries:
        action = str(entry.get("Action") or "unknown")
        actions[action] = actions.get(action, 0) + 1
        if action.lower().startswith("drop"):
            reason = str(entry.get("Reason") or "unspecified").strip()
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
        from_zone = entry.get("FromZone", "-")
        to_zone = entry.get("ToZone", "-")
        pair = f"{from_zone}->{to_zone}"
        zone_pairs[pair] = zone_pairs.get(pair, 0) + 1
        app = str(entry.get("Application") or "unknown")
        applications[app] = applications.get(app, 0) + 1
    return {
        "total_entries": len(entries),
        "actions": actions,
        "drop_reasons": drop_reasons,
        "zone_pairs": zone_pairs,
        "top_applications": dict(sorted(applications.items(), key=lambda kv: -kv[1])[:10]),
    }


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    """Extract records from wrappers, singletons and keyed record dictionaries."""
    payload = unwrap_payload(payload)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    markers = {
        "mode",
        "zone",
        "zoneId",
        "zone_id",
        "state",
        "status",
        "name",
        "zoneName",
        "mapName",
        "rules",
        "policies",
        "zonePolicies",
        "profile_name",
        "profileName",
        "signature",
        "nePk",
    }
    if markers & payload.keys():
        return [payload]
    return [item for item in payload.values() if isinstance(item, dict) and markers & item.keys()]


def first_present(row: dict, *keys: str) -> Any:
    return next((row[key] for key in keys if key in row and row[key] is not None), None)


def summarize_ids_state(payload: Any) -> dict[str, Any]:
    """Report configured detection and prevention only for recognized evidence."""
    rows = extract_rows(payload)
    canonical = {mode.casefold(): mode for mode in IDS_IPS_MODES}
    canonical.update({"disabled": "Off", "none": "Off"})
    modes = {
        canonical.get(row["mode"].casefold(), "unknown") if isinstance(row.get("mode"), str) else "unknown"
        for row in rows
    }
    conflicting = len(modes) > 1 or any(
        row.get("enable") is False and str(row.get("mode", "")).casefold() not in {"off", "disabled", "none", ""}
        for row in rows
    )
    mode = next(iter(modes)) if len(modes) == 1 and not conflicting else "unknown"
    evidence = "conflicting" if conflicting else "observed" if mode != "unknown" else "unknown"
    profiles = {
        str(first_present(row, "profile", "profileName"))
        for row in rows
        if first_present(row, "profile", "profileName") is not None
    }
    detection = evidence == "observed" and mode in {"IDS Only", "IPS-Performant", "IPS-Inline"}
    prevention = evidence == "observed" and mode in {"IPS-Performant", "IPS-Inline"}
    return {
        "mode": mode,
        "profile": next(iter(profiles)) if len(profiles) == 1 else "unknown",
        "active": detection,
        "detection_enabled": detection,
        "prevention_enabled": prevention,
        "evidence_status": evidence,
        "enforcement_verified": False,
        "raw_rows": len(rows),
    }


def summarize_zone_matrix(zones_payload: Any, maps_payload: Any, settings_payload: Any = None) -> dict[str, Any]:
    """Inventory explicit directional pairs; absence is not proof of permitted traffic."""
    zones = extract_rows(zones_payload)
    zone_names = list(
        dict.fromkeys(
            str(first_present(zone, "name", "zoneName"))
            for zone in zones
            if first_present(zone, "name", "zoneName") is not None
        )
    )
    zone_ids = {}
    raw_zones = unwrap_payload(zones_payload)
    if isinstance(raw_zones, dict):
        zone_ids.update(
            {
                str(key): str(first_present(value, "name", "zoneName"))
                for key, value in raw_zones.items()
                if isinstance(value, dict) and first_present(value, "name", "zoneName") is not None
            }
        )
    for zone in zones:
        zone_id = first_present(zone, "zoneId", "zone_id", "id")
        if zone_id is not None:
            zone_ids[str(zone_id)] = str(first_present(zone, "name", "zoneName"))
    policies = []
    covered_pairs = set()
    invalid_rules = 0
    ambiguous_priorities = 0
    for row in extract_rows(maps_payload):
        rules = first_present(row, "rules", "policies", "zonePolicies")
        entry = {"map_name": first_present(row, "name", "mapName"), "rules": []}
        seen_priorities = set()
        for rule in rules if isinstance(rules, list) else []:
            if not isinstance(rule, dict):
                invalid_rules += 1
                continue
            z1 = first_present(rule, "zone1")
            z2 = first_present(rule, "zone2")
            source = zone_ids.get(str(z1), str(z1)) if z1 is not None else None
            destination = zone_ids.get(str(z2), str(z2)) if z2 is not None else None
            action = first_present(rule, "action", "permission")
            priority = rule.get("priority")
            entry["rules"].append({"zone1": source, "zone2": destination, "priority": priority, "action": action})
            if (
                source not in zone_names
                or destination not in zone_names
                or not isinstance(action, str)
                or action.casefold() not in {"allow", "deny", "drop", "reject", "permit", "accept"}
            ):
                invalid_rules += 1
                continue
            covered_pairs.add((source, destination))
            if priority is not None:
                key = (source, destination, str(priority))
                ambiguous_priorities += int(key in seen_priorities)
                seen_priorities.add(key)
        policies.append(entry)
    uncovered = [[a, b] for a in zone_names for b in zone_names if a != b and (a, b) not in covered_pairs]
    config = unwrap_payload(settings_payload)
    default_action = first_present(config, "defaultAction", "default_action") if isinstance(config, dict) else None
    if not isinstance(default_action, str) or default_action.casefold() not in {
        "allow",
        "deny",
        "drop",
        "reject",
        "permit",
        "accept",
    }:
        default_action = None
    return {
        "zones": zone_names,
        "maps": policies,
        "covered_pairs": len(covered_pairs),
        "uncovered_pairs": uncovered[:40],
        "uncovered_pair_count": len(uncovered),
        "uncovered_pairs_truncated": len(uncovered) > 40,
        "invalid_rules": invalid_rules,
        "ambiguous_priorities": ambiguous_priorities,
        "default_action": default_action if default_action is not None else "unknown",
        "evidence_status": "observed"
        if zone_names
        and policies
        and any(p["rules"] for p in policies)
        and not invalid_rules
        and not ambiguous_priorities
        else "unknown",
        "coverage_is_enforcement": False,
        "enforcement_verified": False,
    }


def summarize_ddos(payload: Any) -> dict[str, Any]:
    """Summarize profile assignments and explicit enable flags, not mitigation efficacy."""
    raw = unwrap_payload(payload)
    rows = extract_rows(raw)
    zones = []
    if isinstance(raw, dict) and "profiles" in raw and "profileMaps" in raw:
        profiles = raw["profiles"] if isinstance(raw["profiles"], list) else []
        assignments = raw["profileMaps"] if isinstance(raw["profileMaps"], list) else []
        by_name = {}
        duplicate_names = set()
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            name = profile.get("profile_name")
            if not isinstance(name, str) or not name.strip():
                continue
            if name in by_name:
                duplicate_names.add(name)
            by_name[name] = profile
        for assignment in assignments:
            if not isinstance(assignment, dict):
                continue
            name = assignment.get("profile_name")
            profile = by_name.get(name, {}) if isinstance(name, str) and name not in duplicate_names else {}
            enabled = profile.get("enable")
            zones.append(
                {
                    "zoneId": first_present(assignment, "zone_id", "zoneId"),
                    "status": None,
                    "profile": name,
                    "enabled": enabled if isinstance(enabled, bool) else None,
                    "profile_found": bool(profile),
                }
            )
    else:
        for row in rows:
            enabled = first_present(row, "enable", "enabled")
            zones.append(
                {
                    "zoneId": first_present(row, "zoneId", "zone_id", "zone"),
                    "status": first_present(row, "status", "thresholdStatus"),
                    "profile": first_present(row, "profileName", "profile_name", "protectionProfile", "profile"),
                    "enabled": enabled if isinstance(enabled, bool) else None,
                }
            )
    identifiers = [zone["zoneId"] for zone in zones if type(zone["zoneId"]) is int and zone["zoneId"] >= 0]
    duplicate_zones = {zone_id for zone_id in identifiers if identifiers.count(zone_id) > 1}
    for zone in zones:
        if type(zone["zoneId"]) is not int or zone["zoneId"] < 0 or zone["zoneId"] in duplicate_zones:
            zone["enabled"] = None
    disabled = [zone["zoneId"] for zone in zones if zone["enabled"] is False]
    unknown = sum(zone["enabled"] is None or zone["zoneId"] is None for zone in zones)
    enabled = False if disabled else True if zones and not unknown else None
    return {
        "zones_checked": len(zones),
        "zones": zones,
        "disabled_zones": disabled,
        "unknown_zones": unknown,
        "protection_enabled": enabled,
        "evidence_status": "observed" if zones and not unknown else "unknown",
        "enforcement_verified": False,
    }


def summarize_tunnels(payload: Any) -> dict[str, Any]:
    """Separate observed up/down from unknown instead of inventing failures."""
    rows = extract_rows(payload)
    states = [str(first_present(row, "status", "state") or "").casefold() for row in rows]
    up = states.count("up")
    down = states.count("down")
    return {
        "total": len(rows),
        "up": up,
        "down": down,
        "unknown": len(rows) - up - down,
        "tunnels": [
            {
                "name": first_present(row, "name", "TUNNEL", "tunnelName"),
                "status": first_present(row, "status", "state"),
                "admin": row.get("admin"),
                "overlay": first_present(row, "overlay", "overlayid"),
                "destination": first_present(row, "destination", "destNePk"),
            }
            for row in rows
        ][:80],
    }


def summarize_bgp_neighbors(payload: Any) -> dict[str, Any]:
    """Summarize BGP neighbor state for troubleshooting."""
    rows = extract_rows(payload)
    established = sum(1 for row in rows if str(row.get("state", "")).lower() in {"established", "estab"})
    return {
        "total": len(rows),
        "established": established,
        "neighbors": [
            {
                "ip": row.get("ip") or row.get("neighbor") or row.get("IP"),
                "state": row.get("state") or row.get("neighborState"),
                "asn": row.get("remoteAs") or row.get("asn"),
                "uptime": row.get("uptime") or row.get("upTime"),
            }
            for row in rows
        ][:60],
    }


def validate_ids_mode(mode: str) -> str:
    """Validate an IDS/IPS mode change before it reaches the appliance."""
    if mode not in IDS_IPS_MODES:
        raise ValueError(f"idsIps mode must be one of {sorted(IDS_IPS_MODES)}")
    return mode


def extract_sse_status(provider: str, connectivity_payload: Any, association_payload: Any) -> dict[str, Any]:
    """Summarize SSE provider connectivity and appliance associations."""
    connectivity_rows = extract_rows(connectivity_payload)
    association_rows = extract_rows(association_payload)
    return {
        "provider": provider,
        "connectivity": connectivity_rows[0] if connectivity_rows else connectivity_payload,
        "associated_appliances": [
            row.get("nePk") or row.get("appliance") or row.get("name") for row in association_rows
        ],
        "association_count": len(association_rows),
        "association_evidence_status": "observed"
        if isinstance(unwrap_payload(association_payload), list)
        and all(
            re.fullmatch(r"\d+\.NE", str(first_present(row, "nePk", "appliance") or "")) for row in association_rows
        )
        else "unknown",
        "evidence_scope": "connectivity_and_association_only",
        "web_filter_policy_status": "not_observed",
        "enforcement_verified": False,
    }
