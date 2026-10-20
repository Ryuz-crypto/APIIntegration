"""Axis Security SSE workflow helpers.

Curated helpers over the Axis PublicAdminApi: paged-response normalization,
connector status summarization, tunnel health, application/category builders,
and a commit helper. All helpers are read-oriented unless they explicitly
build a write body (create/update/delete go through the client).
"""

from __future__ import annotations

from typing import Any

PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200


def _clamp_page_size(page_size: int) -> int:
    try:
        value = int(page_size)
    except (TypeError, ValueError):
        return PAGE_SIZE_DEFAULT
    return max(1, min(value, PAGE_SIZE_MAX))


def _clamp_page_number(page_number: int) -> int:
    try:
        value = int(page_number)
    except (TypeError, ValueError):
        return 1
    return max(1, value)


def unwrap_paged(payload: Any) -> list[dict[str, Any]]:
    """Extract the data rows from a PagedApiResponse payload."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def summarize_paged(payload: Any) -> dict[str, Any]:
    """Compact view of a paged response: counts + rows."""
    rows = unwrap_paged(payload)
    summary: dict[str, Any] = {
        "total_records": payload.get("totalRecords") if isinstance(payload, dict) else len(rows),
        "total_pages": payload.get("totalPages") if isinstance(payload, dict) else None,
        "page_number": payload.get("pageNumber") if isinstance(payload, dict) else None,
        "page_size": payload.get("pageSize") if isinstance(payload, dict) else None,
        "returned": len(rows),
        "rows": rows,
    }
    return summary


def summarize_connector_status(payload: Any) -> dict[str, Any]:
    """Summarize a ConnectorStatusResponseModelV1 into a health snapshot."""
    if not isinstance(payload, dict):
        return {"status": "unknown", "raw": payload}
    network = payload.get("networkStatus") or {}
    memory = payload.get("memoryStatus") or {}
    disk = payload.get("diskSpaceStatus") or {}
    cpu = payload.get("cpuStatus") or {}
    machine = payload.get("machineStatus") or {}

    def pct(used: Any, total: Any) -> float | None:
        try:
            used_i, total_i = int(used), int(total)
        except (TypeError, ValueError):
            return None
        if total_i <= 0:
            return None
        return round(used_i / total_i * 100, 1)

    return {
        "id": payload.get("id"),
        "status": payload.get("status"),
        "version": payload.get("version"),
        "enabled": payload.get("enabled"),
        "primary_public_ip": payload.get("primaryPublicIP"),
        "system_status_check_time": payload.get("systemStatusCheckTime"),
        "network": {
            "incoming_kb": network.get("incomingKB"),
            "outgoing_kb": network.get("outgoingKB"),
        },
        "memory": {
            "used_pct": pct(memory.get("usedKB"), memory.get("totalKB")),
            "total_kb": memory.get("totalKB"),
            "free_kb": memory.get("freeKB"),
            "swap_used_pct": pct(memory.get("usedSwapKB"), memory.get("totalSwapKB")),
        },
        "disk": {
            "used_pct": pct(disk.get("usedKB"), disk.get("totalKB")),
            "total_kb": disk.get("totalKB"),
            "free_kb": disk.get("freeKB"),
        },
        "cpu": {
            "num_cpus": cpu.get("numOfCpus"),
            "used_pct": cpu.get("totalUsedPercentage"),
        },
        "machine": {
            "hostname": machine.get("hostname"),
            "os": machine.get("operationSystem"),
        },
    }


def summarize_tunnel_status(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "unknown", "raw": payload}
    return {"id": payload.get("id"), "status": payload.get("status")}


def summarize_health(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "unknown", "raw": payload}
    components = payload.get("components") or {}
    unhealthy = [
        name for name, comp in components.items()
        if isinstance(comp, dict) and comp.get("status", "").lower() in ("unhealthy", "degraded")
    ]
    return {
        "status": payload.get("status"),
        "service": payload.get("service"),
        "timestamp": payload.get("timestamp"),
        "components": {
            name: (comp.get("status") if isinstance(comp, dict) else None)
            for name, comp in components.items()
        },
        "unhealthy_components": unhealthy,
    }


def summarize_ipsec_locations(payload: Any) -> dict[str, Any]:
    """Flatten IPSec PoP locations into a list of {country, city, provider, fqdn, ips}."""
    rows: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return {"total": 0, "locations": rows}
    for country in payload.get("ipSecLocations") or []:
        country_name = country.get("country")
        for loc in country.get("locations") or []:
            fqdns = loc.get("fqdn") or []
            rows.append({
                "country": country_name,
                "city": loc.get("city"),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "provider": loc.get("provider"),
                "fqdns": [f.get("name") for f in fqdns if isinstance(f, dict)],
                "ips": [ip for f in fqdns if isinstance(f, dict) for ip in (f.get("ip") or [])],
            })
    return {"total": len(rows), "locations": rows}


# ------------------------------------------------------------------
# Body builders (validate required fields before sending)
# ------------------------------------------------------------------

def build_tag_body(name: str, applications: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Tag name is required")
    body: dict[str, Any] = {"name": name.strip()}
    if applications:
        body["applications"] = applications
    return body


def build_application_body(
    name: str,
    app_type: str,
    connector_zone_id: str,
    *,
    enabled: bool = True,
    tags: list[dict[str, Any]] | None = None,
    identity_provider_id: str = "",
    network_range: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Application name is required")
    if not connector_zone_id:
        raise ValueError("connectorZoneId is required")
    valid_types = {
        "Web", "Rdp", "RdpPool", "Ssh", "Database", "NetworkRange",
        "SshRange", "Git", "Saas", "Vnc", "ActiveDirectory", "Saml",
    }
    if app_type not in valid_types:
        raise ValueError(f"type must be one of {sorted(valid_types)}")
    body: dict[str, Any] = {
        "name": name.strip(),
        "type": app_type,
        "enabled": enabled,
        "connectorZoneId": connector_zone_id,
    }
    if tags:
        body["tags"] = tags
    if identity_provider_id:
        body["identityProviderId"] = identity_provider_id
    if network_range:
        body["networkRangeApplicationData"] = network_range
    return body


def build_network_range_body(
    ip_ranges: list[str] | None = None,
    dns_searches: list[str] | None = None,
    excluded_dns_searches: list[str] | None = None,
    ports_and_protocols: list[str] | None = None,
    *,
    enable_icmp: bool = True,
    enforce_resolved_dns_to_ip: bool = False,
    server_initiated_ports: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "dnsSearches": dns_searches or [],
        "ipRangesOrCIDRs": ip_ranges or [],
        "excludedDnsSearches": excluded_dns_searches or [],
        "portsAndProtocols": ports_and_protocols or [],
        "enableIcmp": enable_icmp,
        "serverInitiatedPorts": server_initiated_ports or [],
        "enforceResolvedDnsToIp": enforce_resolved_dns_to_ip,
    }


def build_connector_body(name: str, connector_zone_id: str, *, enabled: bool = True, primary_public_ip: str = "") -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Connector name is required")
    if not connector_zone_id:
        raise ValueError("connectorZoneId is required")
    body: dict[str, Any] = {
        "name": name.strip(),
        "connectorZoneId": connector_zone_id,
        "enabled": enabled,
    }
    if primary_public_ip:
        body["primaryPublicIP"] = primary_public_ip
    return body


def build_connector_zone_body(name: str, zone_type: str, purpose: str, *, description: str = "", connectors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Connector zone name is required")
    valid_types = {"Regular", "InternetZone", "ExternalPublicZone"}
    valid_purposes = {"Access", "LogStreaming"}
    if zone_type not in valid_types:
        raise ValueError(f"type must be one of {sorted(valid_types)}")
    if purpose not in valid_purposes:
        raise ValueError(f"purpose must be one of {sorted(valid_purposes)}")
    body: dict[str, Any] = {"name": name.strip(), "type": zone_type, "purpose": purpose}
    if description:
        body["description"] = description
    if connectors:
        body["connectors"] = connectors
    return body


def build_ip_category_body(name: str, *, included_ips: list[str] | None = None, excluded_ips: list[str] | None = None, connector_zone_id: str = "", description: str = "") -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("IP category name is required")
    body: dict[str, Any] = {"name": name.strip()}
    if description:
        body["description"] = description
    if included_ips:
        body["includedIps"] = included_ips
    if excluded_ips:
        body["excludedIps"] = excluded_ips
    if connector_zone_id:
        body["connectorZoneId"] = connector_zone_id
    return body


def build_web_category_body(name: str, *, included_domains: list[str] | None = None, excluded_domains: list[str] | None = None, connector_zone_id: str = "", description: str = "") -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Web category name is required")
    body: dict[str, Any] = {"name": name.strip()}
    if description:
        body["description"] = description
    if included_domains:
        body["includedDomainsOrUrls"] = included_domains
    if excluded_domains:
        body["excludedDomainsOrUrls"] = excluded_domains
    if connector_zone_id:
        body["connectorZoneId"] = connector_zone_id
    return body


def build_ssl_exclusion_body(name: str, exclusion_type: str, *, excluded_domains: list[str] | None = None, enabled: bool = True) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("SSL exclusion name is required")
    if exclusion_type not in {"Predefined", "Custom"}:
        raise ValueError("type must be Predefined or Custom")
    body: dict[str, Any] = {"name": name.strip(), "type": exclusion_type, "enabled": enabled}
    if excluded_domains:
        body["excludedDomains"] = excluded_domains
    return body


def build_group_body(name: str, *, users: list[dict[str, Any]] | None = None, description: str = "") -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Group name is required")
    body: dict[str, Any] = {"name": name.strip()}
    if description:
        body["description"] = description
    if users:
        body["users"] = users
    return body


def build_user_body(user_name: str, email: str, first_name: str, last_name: str, *, enabled: bool = True, groups: list[dict[str, Any]] | None = None, expiration: str = "") -> dict[str, Any]:
    if not user_name or len(user_name.strip()) < 3:
        raise ValueError("userName is required (min 3 chars)")
    if not email or not email.strip():
        raise ValueError("email is required")
    if not first_name or not first_name.strip():
        raise ValueError("firstName is required")
    if not last_name or not last_name.strip():
        raise ValueError("lastName is required")
    body: dict[str, Any] = {
        "userName": user_name.strip(),
        "email": email.strip(),
        "firstName": first_name.strip(),
        "lastName": last_name.strip(),
        "enabled": enabled,
    }
    if expiration:
        body["expiration"] = expiration
    if groups:
        body["groups"] = groups
    return body


def build_location_body(name: str, *, sub_locations: list[dict[str, Any]] | None = None, tunnels: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Location name is required")
    body: dict[str, Any] = {"name": name.strip()}
    if sub_locations:
        body["subLocations"] = sub_locations
    if tunnels:
        body["tunnels"] = tunnels
    return body


def build_sub_location_body(name: str, location_id: str, ip_ranges: list[str], *, sub_location_type: str = "") -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("SubLocation name is required")
    if not location_id:
        raise ValueError("locationId is required")
    if not ip_ranges:
        raise ValueError("ipRanges is required (at least one CIDR/IP)")
    body: dict[str, Any] = {
        "name": name.strip(),
        "locationId": location_id,
        "ipRanges": ip_ranges,
    }
    if sub_location_type:
        body["type"] = sub_location_type
    return body


def build_tunnel_body(name: str, location_id: str, auth_id: str, auth_psk: str) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Tunnel name is required")
    if not location_id:
        raise ValueError("locationID is required")
    if not auth_id:
        raise ValueError("authenticationID is required")
    if not auth_psk:
        raise ValueError("authenticationPsk is required")
    return {
        "name": name.strip(),
        "locationID": location_id,
        "authenticationID": auth_id,
        "authenticationPsk": auth_psk,
    }


def build_certificate_body(
    name: str,
    valid_from: str,
    valid_until: str,
    *,
    common_name: str = "",
    certificate_base64: str = "",
    certificate_password: str = "",
    description: str = "",
) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Certificate name is required")
    if not valid_from:
        raise ValueError("validFrom is required (date-time)")
    if not valid_until:
        raise ValueError("validUntil is required (date-time)")
    body: dict[str, Any] = {
        "name": name.strip(),
        "validFrom": valid_from,
        "validUntil": valid_until,
    }
    if description:
        body["description"] = description
    if common_name:
        body["commonName"] = common_name
    if certificate_base64:
        body["certificateBase64"] = certificate_base64
    if certificate_password:
        body["certificatePassword"] = certificate_password
    return body
