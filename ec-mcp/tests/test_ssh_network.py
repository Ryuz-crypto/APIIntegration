"""Tests for SSH network path selection and inbound-forwarding helpers."""

from __future__ import annotations

import pytest

from ec_mcp.ssh_network import (
    build_inbound_forwarding_rule,
    classify_network_path,
    find_port_forwarding_operations,
    is_connection_rejected,
    summarize_inbound_forwarding_need,
)


class TestClassifyNetworkPath:
    def test_lan_same_subnet_uses_lan_ip(self):
        appliance = {
            "nePk": "1.NE",
            "name": "branch-1",
            "lan_ip": "192.168.10.5",
            "ip": "192.168.10.5",
            "wan_ips": ["203.0.113.10"],
        }
        path = classify_network_path(appliance, local_ips=["192.168.10.100"])
        assert path.network == "lan"
        assert path.via == "direct"
        assert path.target_ip == "192.168.10.5"
        assert path.source_ip == "192.168.10.100"
        assert any("same subnet" in n for n in path.notes)

    def test_wan_when_not_same_subnet_uses_wan_interface_ip(self):
        appliance = {
            "nePk": "2.NE",
            "name": "branch-2",
            "lan_ip": "10.20.30.5",
            "ip": "10.20.30.5",
            "wan_ips": ["198.51.100.20"],
        }
        path = classify_network_path(appliance, local_ips=["192.168.1.50"])
        assert path.network == "wan"
        assert path.via == "wan-interface"
        assert path.target_ip == "198.51.100.20"
        assert any("WAN interface IP" in n for n in path.notes)
        assert any("inbound forwarding" in n for n in path.notes)

    def test_wan_ip_is_not_public_egress(self):
        """The WAN interface IP must be the configured interface IP, not the NAT egress."""
        appliance = {
            "nePk": "3.NE",
            "name": "hq",
            "lan_ip": "172.16.0.1",
            "wan_ips": ["100.64.0.5"],
        }
        path = classify_network_path(appliance, local_ips=["8.8.8.8"])
        assert path.target_ip == "100.64.0.5"
        assert path.network == "wan"

    def test_fallback_to_management_ip_when_no_wan(self):
        appliance = {
            "nePk": "4.NE",
            "name": "standalone",
            "ip": "192.168.50.10",
            "lan_ip": "",
            "wan_ips": [],
        }
        path = classify_network_path(appliance, local_ips=["10.0.0.1"])
        assert path.target_ip == "192.168.50.10"
        assert any("Falling back" in n for n in path.notes)

    def test_raises_when_no_ip_available(self):
        appliance = {"nePk": "5.NE", "name": "empty"}
        with pytest.raises(ValueError, match="no usable IP"):
            classify_network_path(appliance, local_ips=["10.0.0.1"])

    def test_multiple_wan_ips_uses_first(self):
        appliance = {
            "nePk": "6.NE",
            "name": "dual-wan",
            "lan_ip": "10.0.0.1",
            "wan_ips": ["203.0.113.1", "203.0.113.2"],
        }
        path = classify_network_path(appliance, local_ips=["192.168.1.1"])
        assert path.target_ip == "203.0.113.1"


class TestIsConnectionRejected:
    @pytest.mark.parametrize("error", [
        "Connection refused",
        "connection timed out",
        "No route to host",
        "Network is unreachable",
        "Connection rejected by server",
        "Permission denied (filtered)",
        OSError("Connection refused"),
        Exception("TimeoutError: timed out"),
    ])
    def test_rejected_patterns(self, error):
        assert is_connection_rejected(error) is True

    @pytest.mark.parametrize("error", [
        "Authentication failed",
        "Bad password",
        "Invalid credentials",
        "Host key verification failed",
        "",
    ])
    def test_non_rejected_patterns(self, error):
        assert is_connection_rejected(error) is False


class TestBuildInboundForwardingRule:
    def test_basic_rule(self):
        rule = build_inbound_forwarding_rule("1.NE", "203.0.113.10")
        assert rule["nePk"] == "1.NE"
        assert rule["wanIp"] == "203.0.113.10"
        assert rule["protocol"] == "tcp"
        assert rule["externalPort"] == 22
        assert rule["internalPort"] == 22
        assert "sourceIp" not in rule

    def test_rule_with_source_ip_and_custom_ports(self):
        rule = build_inbound_forwarding_rule(
            "2.NE", "198.51.100.5", external_port=2222, internal_port=22,
            source_ip="192.0.2.0/24", comment="mcp access",
        )
        assert rule["externalPort"] == 2222
        assert rule["internalPort"] == 22
        assert rule["sourceIp"] == "192.0.2.0/24"
        assert rule["comment"] == "mcp access"


class TestSummarizeInboundForwardingNeed:
    def test_summary_contains_diagnosis_and_rule(self):
        appliance = {
            "nePk": "7.NE",
            "name": "site-a",
            "lan_ip": "10.1.1.1",
            "wan_ips": ["203.0.113.50"],
        }
        summary = summarize_inbound_forwarding_need(appliance, "Connection refused")
        assert summary["appliance"] == "site-a"
        assert summary["nePk"] == "7.NE"
        assert summary["wan_ip"] == "203.0.113.50"
        assert summary["lan_ip"] == "10.1.1.1"
        assert "inbound forwarding missing" in summary["diagnosis"]
        assert summary["suggested_rule"]["wanIp"] == "203.0.113.50"
        assert "port-forwarding" in summary["remediation"]

    def test_summary_without_wan_ip(self):
        appliance = {"nePk": "8.NE", "name": "no-wan", "lan_ip": "10.0.0.1", "wan_ips": []}
        summary = summarize_inbound_forwarding_need(appliance, "Timeout")
        assert summary["wan_ip"] is None
        assert summary["suggested_rule"] is None


class TestFindPortForwardingOperations:
    def test_finds_port_forwarding_ops(self):
        profiles = {
            "9.6": {
                "operations": {
                    "orchestrator.portforwardingget123": {
                        "method": "GET",
                        "path": "/portForwarding",
                        "description": "Get port forwarding rules",
                    },
                    "orchestrator.portforwardingpost124": {
                        "method": "POST",
                        "path": "/portForwarding",
                        "description": "Create port forwarding rule",
                    },
                    "orchestrator.dnatmapsconfig227": {
                        "method": "GET",
                        "path": "/dnatMaps",
                        "description": "DNAT maps",
                    },
                    "orchestrator.getappliances999": {
                        "method": "GET",
                        "path": "/appliance",
                        "description": "List appliances",
                    },
                }
            }
        }
        found = find_port_forwarding_operations(profiles)
        ids = [f["operation_id"] for f in found]
        assert "orchestrator.portforwardingget123" in ids
        assert "orchestrator.portforwardingpost124" in ids
        assert "orchestrator.dnatmapsconfig227" in ids
        assert "orchestrator.getappliances999" not in ids

    def test_empty_profiles(self):
        assert find_port_forwarding_operations({}) == []
