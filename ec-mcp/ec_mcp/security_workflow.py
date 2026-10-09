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

LOG_VIEWER_DATE_RANGE_READ = "appliance.getdaterange457535"
LOG_VIEWER_FILE_READ = "appliance.getlogfile458377"
LOG_VIEWER_TYPES = ("Firewall", "Alarm", "Audit", "Event")


def parse_firewall_log_entries(payload: Any) -> list[dict[str, Any]]:
    """Parse raw logViewer rows into structured security log entries.

    Each raw row is a list whose second element is a comma-separated
    key:value string produced by the zone-based firewall logger.
    """
    entries: list[dict[str, Any]] = []
    rows = payload.get("logEntries") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return entries
    for row in rows:
        if not isinstance(row, list) or len(row) < 2:
            continue
        raw = row[1]
        fields: dict[str, str] = {}
        for part in str(raw).split(","):
            if ":" in part:
                key, _, value = part.partition(":")
                fields[key.strip()] = value.strip()
        entry = {"timestamp": row[0] if row else None}
        entry.update(fields)
        entries.append(entry)
    return entries


def summarize_security_log(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a security summary: actions, drops, zones and applications."""
    actions: dict[str, int] = {}
    drop_reasons: dict[str, int] = {}
    zone_pairs: dict[str, int] = {}
    applications: dict[str, int] = {}
    for entry in entries:
        action = entry.get("Action", "unknown")
        actions[action] = actions.get(action, 0) + 1
        if action.lower().startswith("drop"):
            reason = entry.get("Reason", "unspecified").strip()
            drop_reasons[reason] = drop_reasons.get(reason, 0) + 1
        from_zone = entry.get("FromZone", "-")
        to_zone = entry.get("ToZone", "-")
        pair = f"{from_zone}->{to_zone}"
        zone_pairs[pair] = zone_pairs.get(pair, 0) + 1
        app = entry.get("Application", "unknown")
        applications[app] = applications.get(app, 0) + 1
    return {
        "total_entries": len(entries),
        "actions": actions,
        "drop_reasons": drop_reasons,
        "zone_pairs": zone_pairs,
        "top_applications": dict(sorted(applications.items(), key=lambda kv: -kv[1])[:10]),
    }


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
    inactive_modes = {"off", "disabled", "none", "", "unknown"}
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
    """Summarize DDoS protection/threshold status rows per zone.

    Handles both the flat row shapes (zoneId/status) and the protectionProfile
    payload (profiles[] + profileMaps[] with zone_id/profile_name), live-validated
    on Orchestrator 9.7 where the POST/GET payloads use snake_case keys.
    """
    rows = extract_rows(payload)
    zones = [
        {
            "zoneId": row.get("zoneId") or row.get("zone"),
            "status": row.get("status") or row.get("thresholdStatus"),
            "profile": row.get("profileName") or row.get("protectionProfile"),
        }
        for row in rows
    ]
    profile_maps = []
    if isinstance(payload, dict):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        for mapping in data.get("profileMaps") or []:
            if isinstance(mapping, dict) and mapping.get("profile_name"):
                profile_maps.append(
                    {
                        "zoneId": mapping.get("zone_id"),
                        "profile": mapping.get("profile_name"),
                    }
                )
    return {
        "zones_checked": max(len(rows), len(profile_maps)),
        "zones": zones or profile_maps,
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


def summarize_web_filtering(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate web filtering signals from firewall log entries."""
    categories: dict[str, int] = {}
    reputations: dict[str, int] = {}
    blocked_categories: dict[str, int] = {}
    for entry in entries:
        category = entry.get("WebCategory") or "Unknown"
        categories[category] = categories.get(category, 0) + 1
        reputation = str(entry.get("WebReputation") or "0")
        reputations[reputation] = reputations.get(reputation, 0) + 1
        action = entry.get("Action", "")
        if str(action).lower().startswith("drop"):
            blocked_categories[category] = blocked_categories.get(category, 0) + 1
    return {
        "top_web_categories": dict(sorted(categories.items(), key=lambda kv: -kv[1])[:10]),
        "reputation_distribution": dict(sorted(reputations.items(), key=lambda kv: -kv[1])[:5]),
        "blocked_by_category": dict(sorted(blocked_categories.items(), key=lambda kv: -kv[1])[:10]),
    }


def correlate_security_signals(
    ne_pk: str,
    ids_state: dict[str, Any] | None,
    ids_events: list[dict[str, Any]],
    drop_summary: dict[str, Any] | None,
    web_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Cross-correlate per-appliance security signals into incident findings.

    Correlations applied (evidence-backed, live-validated on Orchestrator 9.7):
    - IDS/IPS inactive while firewall drops exist -> protection gap.
    - IDS inspection events (priority <= 2) plus drops from the same source
      zone -> suspected incident, investigate src/dst in the events.
    - implicit-deny drops dominating the drop reasons -> policy gap to review.
    - Blocked web categories concentrated in few categories -> web filtering
      working but tune/review the blocked categories.
    """
    findings: list[dict[str, Any]] = []
    ids_active = bool(ids_state and ids_state.get("active"))
    drops = 0
    drop_reasons: dict[str, int] = {}
    if drop_summary:
        drop_reasons = drop_summary.get("drop_reasons") or {}
        drops = sum(drop_reasons.values())
    if not ids_active and drops > 0:
        findings.append(
            {
                "nePk": ne_pk,
                "severity": "high",
                "finding": f"IDS/IPS inactive while {drops} firewall drops were logged",
                "recommendation": "Enable IDS/IPS on this appliance before the implicit-deny traffic grows.",
            }
        )
    high_priority_events = [
        event
        for event in ids_events
        if "priority: 1" in str(event.get("message", "")).lower()
        or "priority: 2" in str(event.get("message", "")).lower()
    ]
    if high_priority_events:
        findings.append(
            {
                "nePk": ne_pk,
                "severity": "high" if not ids_active else "medium",
                "finding": f"{len(high_priority_events)} high-priority IDS events matched inspection policy",
                "evidence": [event.get("message", "")[:200] for event in high_priority_events[:3]],
                "recommendation": "Review the IDS events; if the sources are unknown, quarantine the zone policy.",
            }
        )
    scan_events = [
        event
        for event in ids_events
        if "scan" in str(event.get("message", "")).lower()
        or "infection" in str(event.get("message", "")).lower()
    ]
    if scan_events:
        findings.append(
            {
                "nePk": ne_pk,
                "severity": "high",
                "finding": f"{len(scan_events)} IDS events classified as network scan or infection behavior",
                "evidence": [event.get("message", "")[:200] for event in scan_events[:3]],
                "recommendation": "Investigate the source/destination pairs in the evidence; scans targeting RDP/SMB usually precede lateral movement.",
            }
        )
    if drops > 0:
        implicit = sum(
            count
            for reason, count in drop_reasons.items()
            if "implicit" in str(reason).lower()
        )
        if implicit and implicit / drops >= 0.5:
            findings.append(
                {
                    "nePk": ne_pk,
                    "severity": "medium",
                    "finding": f"{implicit}/{drops} drops come from implicit deny (no explicit zone policy)",
                    "recommendation": "Add explicit zone-to-zone policies for the impacted zone pairs.",
                }
            )
    if web_summary and web_summary.get("blocked_by_category"):
        top_blocked = max(web_summary["blocked_by_category"].values())
        if top_blocked >= 3:
            findings.append(
                {
                    "nePk": ne_pk,
                    "severity": "low",
                    "finding": f"Web filtering blocked {top_blocked}+ flows in one category",
                    "recommendation": "Review blocked_by_category to confirm the filtering policy is intended.",
                }
            )
    return findings


def correlate_active_alarms(
    ne_pk: str,
    alarm_counts: dict[str, int] | None,
) -> list[dict[str, Any]]:
    """Correlate per-appliance active alarm counts into incident findings.

    Live-validated against /alarm/count/appliance severity aggregates on
    Orchestrator 9.7 (critical/major/minor/warning per appliance).
    """
    findings: list[dict[str, Any]] = []
    if not alarm_counts:
        return findings
    critical = int(alarm_counts.get("critical") or 0)
    major = int(alarm_counts.get("major") or 0)
    if critical > 0:
        findings.append(
            {
                "nePk": ne_pk,
                "severity": "high",
                "finding": f"{critical} critical alarms active right now",
                "recommendation": "Triage critical alarms first; use get_active_alarms and the Alarm security log for details.",
            }
        )
    if major >= 3:
        findings.append(
            {
                "nePk": ne_pk,
                "severity": "medium",
                "finding": f"{major} major alarms active; multiple majors often share a root cause",
                "recommendation": "Check whether the major alarms started at the same time (correlate with tunnel/WAN state).",
            }
        )
    return findings
