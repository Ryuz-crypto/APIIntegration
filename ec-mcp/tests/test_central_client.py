"""Tests for the Aruba Central client and workflow helpers."""

from __future__ import annotations

import json

import httpx
import pytest

from ec_mcp.central_client import ArubaCentralClient, ArubaCentralError
from ec_mcp.central_workflow import (
    extract_task_id,
    parse_commands,
    parse_ports,
    resolve_family,
    resolve_troubleshooting_device_type,
    summarize_devices,
    summarize_health,
    trend_metric,
)


def make_client(handler, token_handler=None) -> ArubaCentralClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://us.api.central.arubanetworks.com",
        transport=transport,
    )
    client = ArubaCentralClient(
        client_id="client-id",
        client_secret="client-secret",  # noqa: S106 - test fixture
        client=http_client,
    )
    if token_handler:
        client._fetch_token = token_handler
        client._access_token = "test-token"
        client._expires_at = 1e12
    return client


def token_ok(payload=None):
    def handler():
        return payload or {"access_token": "test-token", "expires_in": 3600}

    return handler


class TestCentralClient:
    def test_requires_credentials(self):
        with pytest.raises(ValueError, match="credentials are required"):
            ArubaCentralClient(client_id="", client_secret="")

    def test_auth_header_sent(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"items": []})

        client = make_client(handler)
        client.sites_health()
        assert captured["auth"] == "Bearer t"

    def test_sites_health_path(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["query"] = str(request.url.query)
            return httpx.Response(200, json={"items": []})

        client = make_client(handler)
        client.sites_health(params={"limit": 1})
        assert captured["path"] == "/network-monitoring/v1/sites-health"
        assert "limit=1" in captured["query"]

    def test_list_devices_family_validation(self):
        client = make_client(lambda request: httpx.Response(200, json={}))
        with pytest.raises(ValueError, match="Unsupported device family"):
            client.list_devices("routers")

    def test_list_devices_paths(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        paths = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            return httpx.Response(200, json={})

        client = make_client(handler)
        for family in ("aps", "switches", "gateways"):
            client.list_devices(family)
        assert paths == [
            "/network-monitoring/v1/aps",
            "/network-monitoring/v1/switches",
            "/network-monitoring/v1/gateways",
        ]

    def test_run_show_commands_posts_body(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content)
            return httpx.Response(202, json={"taskId": "abc-123"})

        client = make_client(handler)
        payload = client.run_show_commands("cx", "SG1234567", ["show version"])
        assert captured["path"] == "/network-troubleshooting/v1/cx/SG1234567/showCommands"
        assert captured["body"] == {"commands": ["show version"]}
        assert payload["taskId"] == "abc-123"

    def test_bounce_port_mode(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content)
            return httpx.Response(202, json={"taskId": "t1"})

        client = make_client(handler)
        client.bounce_port("cx", "SG1234567", ["1/1/6"], mode="poe")
        assert captured["path"] == "/network-troubleshooting/v1/cx/SG1234567/poeBounce"
        assert captured["body"] == {"ports": ["1/1/6"]}

    def test_api_error_raises(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        client = make_client(handler)
        with pytest.raises(ArubaCentralError, match="HTTP 500"):
            client.get_alerts()

    def test_token_failure_raises(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(401, text="bad credentials"),
        )
        client = make_client(lambda request: httpx.Response(200, json={}))
        with pytest.raises(ArubaCentralError, match="token request failed"):
            client.sites_health()


class TestCentralWorkflow:
    def test_resolve_family(self):
        assert resolve_family("AP") == "aps"
        assert resolve_family("cx") == "switches"
        assert resolve_family("Gateway") == "gateways"
        with pytest.raises(ValueError, match="Unsupported device_type"):
            resolve_family("router")

    def test_resolve_troubleshooting_device_type(self):
        assert resolve_troubleshooting_device_type("ap") == "aps"
        assert resolve_troubleshooting_device_type("switch") == "cx"
        assert resolve_troubleshooting_device_type("aos-s") == "aos-s"
        with pytest.raises(ValueError, match="Unsupported device_type"):
            resolve_troubleshooting_device_type("router")

    def test_trend_metric(self):
        assert trend_metric("gateways", "cpu-utilization") == "cpu-utilization-trends"
        with pytest.raises(ValueError, match="Unsupported trend metric"):
            trend_metric("aps", "cpu-utilization")

    def test_parse_commands(self):
        assert parse_commands('["show version"]') == ["show version"]
        with pytest.raises(ValueError, match="must start with 'show '"):
            parse_commands('["reload"]')
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_commands("no-json")

    def test_parse_ports(self):
        assert parse_ports('["1/1/6"]') == ["1/1/6"]
        with pytest.raises(ValueError, match="non-empty JSON list"):
            parse_ports("[]")

    def test_extract_task_id(self):
        assert extract_task_id({"taskId": "t-1"}) == "t-1"
        assert extract_task_id({"task": {"id": "t-2"}}) == "t-2"
        with pytest.raises(ValueError, match="task id"):
            extract_task_id({"unexpected": 1})

    def test_summarize_health(self):
        payload = {
            "items": [
                {"siteId": "s1", "siteName": "HQ", "health": "GOOD", "deviceHealth": 98},
                {"site_id": "s2", "site_name": "Branch", "healthCategory": "POOR"},
            ],
            "total": 2,
        }
        result = summarize_health(payload)
        assert result["count"] == 2
        assert result["sites"][0]["site_id"] == "s1"
        assert result["sites"][1]["site_name"] == "Branch"

    def test_summarize_devices(self):
        payload = {"devices": [{"serialNumber": "SG1", "deviceName": "AP-1", "status": "UP"}]}
        result = summarize_devices(payload)
        assert result["count"] == 1
        assert result["devices"][0]["serial"] == "SG1"


class TestNetworkTests:
    def test_run_network_test_paths(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured[request.url.path] = json.loads(request.content)
            return httpx.Response(202, json={"taskId": "t"})

        client = make_client(handler)
        client.run_network_test("cx", "SG1", "ping", {"destination": "8.8.8.8", "count": 3})
        client.run_network_test("gateways", "SG2", "tcp", {"destination": "10.0.0.1", "port": 443})
        assert captured["/network-troubleshooting/v1/cx/SG1/ping"] == {"destination": "8.8.8.8", "count": 3}
        assert captured["/network-troubleshooting/v1/gateways/SG2/tcp"] == {"destination": "10.0.0.1", "port": 443}

    def test_get_task_result_operations(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        paths = []

        def handler(request: httpx.Request) -> httpx.Response:
            paths.append(request.url.path)
            return httpx.Response(200, json={"status": "COMPLETED"})

        client = make_client(handler)
        client.get_task_result("cx", "SG1", "task-1")
        client.get_task_result("cx", "SG1", "task-1", operation="ping")
        assert paths == [
            "/network-troubleshooting/v1/cx/SG1/showCommands/async-operations/task-1",
            "/network-troubleshooting/v1/cx/SG1/ping/async-operations/task-1",
        ]
        with pytest.raises(ValueError, match="Unsupported operation"):
            client.get_task_result("cx", "SG1", "task-1", operation="bogus")

    def test_build_network_test_body(self):
        from ec_mcp.central_workflow import build_network_test_body

        assert build_network_test_body("ping", "8.8.8.8", count=3) == (
            "ping",
            {"destination": "8.8.8.8", "count": 3},
        )
        assert build_network_test_body("nslookup", "example.com") == ("nslookup", {"host": "example.com"})
        assert build_network_test_body("https", "example.com") == (
            "https",
            {"destination": "example.com", "protocol": "HTTPS"},
        )
        assert build_network_test_body("tcp", "10.0.0.1", port=443) == (
            "tcp",
            {"destination": "10.0.0.1", "port": 443},
        )
        with pytest.raises(ValueError, match="Unsupported test_type"):
            build_network_test_body("speedtest", "x")
        with pytest.raises(ValueError, match="port is required"):
            build_network_test_body("tcp", "10.0.0.1")
        with pytest.raises(ValueError, match="count must be"):
            build_network_test_body("ping", "8.8.8.8", count=200)

    def test_validate_operation(self):
        from ec_mcp.central_workflow import validate_operation

        assert validate_operation("") == "showCommands"
        assert validate_operation("ping") == "ping"
        with pytest.raises(ValueError, match="Unsupported operation"):
            validate_operation("bogus")


class TestClientAnalytics:
    def test_analytics_paths(self, monkeypatch):
        monkeypatch.setattr(
            "ec_mcp.central_client.httpx.post",
            lambda *a, **k: httpx.Response(200, json={"access_token": "t", "expires_in": 3600}),
        )
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured[request.url.path] = str(request.url.query)
            return httpx.Response(200, json={"items": []})

        client = make_client(handler)
        client.clients_usage(params={"filter": "timestamp gt a"})
        client.clients_top_usage(params={"start-at": "a", "end-at": "b"})
        client.clients_trend(params={"start-at": "a", "end-at": "b"})
        client.client_onboarding("reasons", params={"start-at": "a", "end-at": "b"})
        client.client_mobility_trail("AA:BB:CC:DD:EE:FF", params={"limit": 20})
        assert set(captured) == {
            "/network-monitoring/v1/clients-usage",
            "/network-monitoring/v1/clients-topn-usage",
            "/network-monitoring/v1/clients-trend",
            "/network-monitoring/v1/client-onboarding-stage/reasons",
            "/network-monitoring/v1/clients/AA:BB:CC:DD:EE:FF/mobility-trail",
        }
        with pytest.raises(ValueError, match="view must be"):
            client.client_onboarding("bogus")

    def test_analytics_helpers(self):
        from ec_mcp.central_workflow import (
            analytics_time_window,
            build_analytics_params,
            build_usage_filter,
            resolve_analytics_view,
        )

        assert resolve_analytics_view("TOP") == "top"
        with pytest.raises(ValueError, match="Unsupported view"):
            resolve_analytics_view("bogus")
        start, end = analytics_time_window("", "")
        assert start and end
        assert analytics_time_window("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z") == (
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
        )
        assert build_usage_filter("s", "e", site_id="site1", mac_address="AA:BB") == (
            "timestamp gt s and timestamp lt e and siteId eq 'site1' and macAddress eq 'AA:BB'"
        )
        params = build_analytics_params("s", "e", site_id="site1", serial_number="SG1", limit=10)
        assert params == {"start-at": "s", "end-at": "e", "site-id": "site1", "serial-number": "SG1", "limit": 10}
