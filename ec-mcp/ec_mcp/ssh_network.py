"""SSH network path selection and inbound-forwarding helpers for EdgeConnect.

When the MCP server runs on the same LAN as the appliances (or reachable via
the Orchestrator's managed network), SSH can go directly to the appliance LAN IP.
When the server is on the WAN side, SSH must target the IP configured on the
appliance's WAN interface (not the public/NAT egress IP). If the connection is
refused, the appliance likely lacks an inbound forwarding (port-forwarding /
DNAT) rule for SSH; this module can detect that and offer to create one via
the Orchestrator API.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any

SSH_PORT = 22

_REJECT_PATTERNS = re.compile(
    r"(?i)"
    r"connection refused|"
    r"no route to host|"
    r"network is unreachable|"
    r"timed?\s*out|"
    r"timeout|"
    r"unreachable|"
    r"filtered|"
    r"denied|"
    r"rejected"
)


@dataclass
class NetworkPath:
    """Describes how to reach an appliance over SSH."""

    target_ip: str
    network: str  # "lan" | "wan"
    via: str  # "direct" | "wan-interface" | "port-forward"
    source_ip: str = ""
    notes: list[str] | None = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


def _is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _same_subnet(ip_a: str, ip_b: str) -> bool:
    """True if both IPs are in the same /24 (simple LAN heuristic)."""
    try:
        a = ipaddress.ip_address(ip_a)
        b = ipaddress.ip_address(ip_b)
        if a.version != b.version:
            return False
        return ipaddress.ip_network(f"{a}/24", strict=False).network_address == ipaddress.ip_network(
            f"{b}/24", strict=False
        ).network_address
    except ValueError:
        return False


def _get_local_ips() -> list[str]:
    """Best-effort enumeration of local interface IPs (non-loopback)."""
    ips: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except OSError:
        pass
    return ips


def classify_network_path(
    appliance: dict[str, Any],
    orchestrator_url: str = "",
    local_ips: list[str] | None = None,
) -> NetworkPath:
    """Decide whether to reach an appliance via LAN or WAN and which IP to use.

    Priority:
    1. If the appliance's management/LAN IP is on the same subnet as a local
       interface, use the LAN IP (direct).
    2. Otherwise, use the appliance's WAN interface IP (the IP configured on
       the WAN interface, NOT the public/NAT egress IP). This is reachable
       from the WAN only if an inbound forwarding rule exists.
    3. Fall back to the management IP if nothing else is available.
    """
    notes: list[str] = []
    lan_ip = str(appliance.get("lan_ip") or appliance.get("ip") or "").strip()
    mgmt_ip = str(appliance.get("ip") or "").strip()
    wan_ips = [str(v).strip() for v in (appliance.get("wan_ips") or []) if v]

    local = local_ips if local_ips is not None else _get_local_ips()

    # 1. Same-subnet check -> LAN direct
    if lan_ip:
        for lip in local:
            if _same_subnet(lan_ip, lip):
                notes.append(f"LAN IP {lan_ip} is on the same subnet as local interface {lip}")
                return NetworkPath(
                    target_ip=lan_ip,
                    network="lan",
                    via="direct",
                    source_ip=lip,
                    notes=notes,
                )

    # 2. WAN interface IP (not the public egress IP)
    if wan_ips:
        wan_ip = wan_ips[0]
        notes.append(
            f"Using WAN interface IP {wan_ip} (configured on the appliance WAN interface, "
            "not the public/NAT egress IP)"
        )
        notes.append(
            "WAN path requires an inbound forwarding rule (port-forward/DNAT) for TCP/22 "
            "on the appliance; if the connection is refused, use ensure_ssh_inbound_forwarding"
        )
        return NetworkPath(
            target_ip=wan_ip,
            network="wan",
            via="wan-interface",
            notes=notes,
        )

    # 3. Fall back to management IP
    if mgmt_ip:
        notes.append(f"Falling back to management IP {mgmt_ip}")
        return NetworkPath(
            target_ip=mgmt_ip,
            network="lan" if _is_private(mgmt_ip) else "wan",
            via="direct",
            notes=notes,
        )

    raise ValueError(
        f"Appliance '{appliance.get('name') or appliance.get('nePk')}' has no usable IP "
        "(lan_ip, wan_ips, or management ip missing)"
    )


def is_connection_rejected(error: BaseException | str) -> bool:
    """True if the error looks like a network-level rejection (refused/timeout)."""
    text = str(error)
    return bool(_REJECT_PATTERNS.search(text))


def build_inbound_forwarding_rule(
    appliance_ne_pk: str,
    wan_ip: str,
    external_port: int = SSH_PORT,
    internal_port: int = SSH_PORT,
    protocol: str = "tcp",
    source_ip: str = "",
    comment: str = "ec-mcp SSH access",
) -> dict[str, Any]:
    """Build the body for a port-forwarding (inbound) rule via the Orchestrator.

    Mirrors the shape used by POST /portForwarding (orchestrator.portforwardingpost*).
    The Orchestrator applies this to the appliance's WAN interface so that
    TCP traffic to <wan_ip>:<external_port> is forwarded to the appliance's
    internal SSH port.
    """
    rule: dict[str, Any] = {
        "nePk": appliance_ne_pk,
        "wanIp": wan_ip,
        "protocol": protocol,
        "externalPort": external_port,
        "internalPort": internal_port,
        "comment": comment,
    }
    if source_ip:
        rule["sourceIp"] = source_ip
    return rule


def summarize_inbound_forwarding_need(
    appliance: dict[str, Any],
    error: BaseException | str,
) -> dict[str, Any]:
    """Explain why SSH failed and what rule would fix it."""
    wan_ips = [str(v).strip() for v in (appliance.get("wan_ips") or []) if v]
    ne_pk = appliance.get("nePk") or appliance.get("id") or ""
    lan_ip = appliance.get("lan_ip") or appliance.get("ip") or ""
    return {
        "appliance": appliance.get("name") or ne_pk,
        "nePk": ne_pk,
        "error": str(error),
        "diagnosis": "inbound forwarding missing for TCP/22 on the WAN interface",
        "wan_ip": wan_ips[0] if wan_ips else None,
        "lan_ip": lan_ip,
        "suggested_rule": build_inbound_forwarding_rule(ne_pk, wan_ips[0]) if wan_ips else None,
        "remediation": (
            "Create a port-forwarding (inbound) rule on the Orchestrator for this appliance: "
            "WAN IP -> TCP/22 -> appliance internal SSH port. "
            "Use apply_change with the operation id for portForwarding (POST), or run the "
            "equivalent ECOS CLI: 'port-forwarding add <wan-if> tcp <ext-port> <int-ip> <int-port>'."
        ),
    }


def find_port_forwarding_operations(profiles: dict[str, Any]) -> list[dict[str, str]]:
    """Scan loaded profiles for port-forwarding / DNAT operations usable for SSH."""
    found: list[dict[str, str]] = []
    for version, profile in profiles.items():
        for op_id, op in (profile.get("operations") or {}).items():
            path = (op.get("path") or "").lower()
            if "portforward" in path or "portforward" in op_id.lower():
                found.append(
                    {
                        "version": version,
                        "operation_id": op_id,
                        "method": op.get("method", "GET"),
                        "path": op.get("path", ""),
                        "description": op.get("description", ""),
                    }
                )
            elif "dnat" in path and ("map" in path or "rule" in path):
                found.append(
                    {
                        "version": version,
                        "operation_id": op_id,
                        "method": op.get("method", "GET"),
                        "path": op.get("path", ""),
                        "description": op.get("description", ""),
                    }
                )
    return found
