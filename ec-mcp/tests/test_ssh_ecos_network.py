"""Integration tests for ssh_ecos network-path resolution."""

from __future__ import annotations

import pytest

from ec_mcp.config import Settings
from ec_mcp.security import SecurityError
from ec_mcp.ssh_ecos import (
    ApplianceSshPool,
    find_appliance,
    resolve_appliance_address,
    resolve_appliance_network_path,
)
from ec_mcp.ssh_network import NetworkPath

INVENTORY = [
    {
        "nePk": "1.NE",
        "name": "branch-lan",
        "serial_number": "SN001",
        "ip": "192.168.10.5",
        "lan_ip": "192.168.10.5",
        "wan_ips": ["203.0.113.10"],
    },
    {
        "nePk": "2.NE",
        "name": "branch-wan",
        "serial_number": "SN002",
        "ip": "10.20.30.5",
        "lan_ip": "10.20.30.5",
        "wan_ips": ["198.51.100.20"],
    },
    {
        "nePk": "3.NE",
        "name": "no-wan",
        "serial_number": "SN003",
        "ip": "172.16.0.10",
        "lan_ip": "",
        "wan_ips": [],
    },
]


def make_settings(**overrides) -> Settings:
    base = dict(
        orchestrator_url="https://orch.example",
        orchestrator_api_key="test-key",
        ssh_enabled=True,
        ssh_username="mcp",
        ssh_password="secret",  # noqa: S106 - test fixture
        ssh_port=22,
    )
    base.update(overrides)
    return Settings(**base)


class TestResolveApplianceAddress:
    def test_resolve_by_name_lan(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["192.168.10.100"]
        )
        addr = resolve_appliance_address("branch-lan", settings, INVENTORY)
        assert addr == "192.168.10.5"

    def test_resolve_by_name_wan(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["192.168.1.1"]
        )
        addr = resolve_appliance_address("branch-wan", settings, INVENTORY)
        assert addr == "198.51.100.20"

    def test_resolve_by_nepk(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["192.168.10.1"]
        )
        addr = resolve_appliance_address("1.NE", settings, INVENTORY)
        assert addr == "192.168.10.5"

    def test_resolve_by_serial(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["10.20.30.1"]
        )
        addr = resolve_appliance_address("SN002", settings, INVENTORY)
        assert addr == "10.20.30.5"

    def test_prefer_lan_overrides_wan(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["192.168.1.1"]
        )
        addr = resolve_appliance_address(
            "branch-wan", settings, INVENTORY, prefer_network="lan"
        )
        assert addr == "10.20.30.5"

    def test_prefer_wan_uses_wan_ip(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["10.20.30.1"]
        )
        addr = resolve_appliance_address(
            "branch-wan", settings, INVENTORY, prefer_network="wan"
        )
        assert addr == "198.51.100.20"

    def test_prefer_wan_raises_when_no_wan_ip(self):
        settings = make_settings()
        with pytest.raises(SecurityError, match="no WAN interface IP"):
            resolve_appliance_address("no-wan", settings, INVENTORY, prefer_network="wan")

    def test_unknown_appliance_raises(self):
        settings = make_settings()
        with pytest.raises(SecurityError, match="not found"):
            resolve_appliance_address("unknown", settings, INVENTORY)

    def test_direct_ip_passthrough(self):
        settings = make_settings()
        addr = resolve_appliance_address("8.8.8.8", settings, INVENTORY)
        assert addr == "8.8.8.8"


class TestResolveApplianceNetworkPath:
    def test_lan_path(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["192.168.10.1"]
        )
        path = resolve_appliance_network_path("branch-lan", settings, INVENTORY)
        assert isinstance(path, NetworkPath)
        assert path.network == "lan"
        assert path.via == "direct"
        assert path.target_ip == "192.168.10.5"

    def test_wan_path(self, monkeypatch):
        settings = make_settings()
        monkeypatch.setattr(
            "ec_mcp.ssh_network._get_local_ips", lambda: ["192.168.1.1"]
        )
        path = resolve_appliance_network_path("branch-wan", settings, INVENTORY)
        assert path.network == "wan"
        assert path.via == "wan-interface"
        assert path.target_ip == "198.51.100.20"
        assert any("inbound forwarding" in n for n in path.notes)


class TestFindAppliance:
    def test_by_name(self):
        assert find_appliance("branch-lan", INVENTORY)["nePk"] == "1.NE"

    def test_by_nepk(self):
        assert find_appliance("2.NE", INVENTORY)["name"] == "branch-wan"

    def test_by_serial(self):
        assert find_appliance("SN003", INVENTORY)["name"] == "no-wan"

    def test_by_wan_ip(self):
        assert find_appliance("198.51.100.20", INVENTORY)["nePk"] == "2.NE"

    def test_by_lan_ip(self):
        assert find_appliance("192.168.10.5", INVENTORY)["nePk"] == "1.NE"

    def test_not_found(self):
        assert find_appliance("missing", INVENTORY) is None

    def test_empty_target(self):
        assert find_appliance("", INVENTORY) is None


class TestApplianceSshPoolNetworkPath:
    def test_pool_rejects_when_ssh_disabled(self):
        settings = make_settings(ssh_enabled=False)
        pool = ApplianceSshPool(settings)
        with pytest.raises(SecurityError, match="disabled"):
            pool.get("branch-lan")

    def test_pool_rejects_when_no_host(self):
        settings = make_settings(ssh_host="")
        pool = ApplianceSshPool(settings)
        with pytest.raises(SecurityError, match="No appliance host"):
            pool.get(None)
