"""Security and troubleshooting workflow helpers for EdgeConnect.

Curated, read-oriented helpers over the raw Orchestrator/appliance API
catalog: IDS/IPS posture, zone-based security maps, DDoS thresholds,
site-to-site tunnel state, BGP/BFD health and SSE (Zscaler, Netskope,
Axis) integration status. Operation ids are the stable catalog ids from
the compatibility profiles (9.3-9.6).
"""

from __future__ import annotations

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


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    """Extract row lists from the common Orchestrator response wrappers."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            rows = extract_rows(value)
            if rows:
                return rows
    if any(marker in payload for marker in ("mode", "zone", "state", "status")):
        return [payload]
    return []


def summarize_ids_state(payload: Any) -> dict[str, Any]:
    """Summarize the appliance IDS/IPS state payload into a compact posture."""
    rows = extract_rows(payload)
    mode = None
    profile = None
    for row in rows:
        mode = row.get("mode") or mode
        profile = row.get("profile") or row.get("profileName") or profile
    inactive_modes = {"off", "disabled", "", "unknown"}
    active = bool(mode and str(mode).lower() not in inactive_modes)
    return {
        "mode": mode or "unknown",
        "profile": profile or "unknown",
        "active": active,
        "raw_rows": len(rows),
    }


def summarize_zone_matrix(zones_payload: Any, maps_payload: Any) -> dict[str, Any]:
    """Combine zones and security maps into a zone-to-zone policy matrix."""
    zones = extract_rows(zones_payload)
    zone_names: list[str] = []
    for zone in zones:
        name = zone.get("name") or zone.get("zoneName")
        if name:
            zone_names.append(str(name))
    maps = extract_rows(maps_payload)
    policies: list[dict[str, Any]] = []
    for row in maps:
        entry = {
            "map_name": row.get("name") or row.get("mapName"),
        }
        rules = row.get("rules") or row.get("policies") or row.get("zonePolicies")
        if isinstance(rules, list):
            entry["rules"] = [
                {
                    "zone1": rule.get("zone1"),
                    "zone2": rule.get("zone2"),
                    "priority": rule.get("priority"),
                    "action": rule.get("action") or rule.get("permission"),
                }
                for rule in rules
                if isinstance(rule, dict)
            ]
        policies.append(entry)
    covered_pairs: set[tuple[str, str]] = set()
    for policy in policies:
        for rule in policy.get("rules", []):
            covered_pairs.add((str(rule.get("zone1")), str(rule.get("zone2"))))
    uncovered: list[list[str]] = []
    for zone_a in zone_names:
        for zone_b in zone_names:
            if zone_a != zone_b and (zone_a, zone_b) not in covered_pairs and (zone_b, zone_a) not in covered_pairs:
                uncovered.append([zone_a, zone_b])
    return {
        "zones": zone_names,
        "maps": policies,
        "covered_pairs": len(covered_pairs),
        "uncovered_pairs": uncovered[:40],
    }


def summarize_ddos(payload: Any) -> dict[str, Any]:
    """Summarize DDoS protection/threshold status rows per zone."""
    rows = extract_rows(payload)
    return {
        "zones_checked": len(rows),
        "zones": [
            {
                "zoneId": row.get("zoneId") or row.get("zone"),
                "status": row.get("status") or row.get("thresholdStatus"),
                "profile": row.get("profileName") or row.get("protectionProfile"),
            }
            for row in rows
        ],
    }


def summarize_tunnels(payload: Any) -> dict[str, Any]:
    """Summarize tunnel config-and-state rows for site-to-site visibility."""
    rows = extract_rows(payload)
    up = sum(1 for row in rows if str(row.get("status", "")).lower() == "up")
    return {
        "total": len(rows),
        "up": up,
        "down": len(rows) - up,
        "tunnels": [
            {
                "name": row.get("name") or row.get("TUNNEL") or row.get("tunnelName"),
                "status": row.get("status"),
                "admin": row.get("admin"),
                "overlay": row.get("overlay") or row.get("overlayid"),
                "destination": row.get("destination") or row.get("destNePk"),
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
            row.get("nePk") or row.get("appliance") or row.get("name")
            for row in association_rows
        ],
        "association_count": len(association_rows),
    }
