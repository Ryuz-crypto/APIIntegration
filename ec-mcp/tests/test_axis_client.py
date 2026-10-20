"""Tests for the Axis Security client and workflow helpers."""

from __future__ import annotations

import json

import httpx
import pytest

from ec_mcp.axis_client import AxisSecurityClient, AxisSecurityError
from ec_mcp.axis_workflow import (
    build_application_body,
    build_connector_body,
    build_connector_zone_body,
    build_group_body,
    build_ip_category_body,
    build_location_body,
    build_network_range_body,
    build_ssl_exclusion_body,
    build_sub_location_body,
    build_tag_body,
    build_tunnel_body,
    build_user_body,
    build_web_category_body,
    summarize_connector_status,
    summarize_health,
    summarize_ipsec_locations,
    summarize_paged,
    summarize_tunnel_status,
    unwrap_paged,
)


def make_client(handler) -> AxisSecurityClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://admin-api.axissecurity.com",
        transport=transport,
    )
    return AxisSecurityClient(token="test-token", client=http_client)  # noqa: S106 - test fixture


class TestAxisClient:
    def test_requires_token(self):
        with pytest.raises(ValueError, match="token is required"):
            AxisSecurityClient(token="")

    def test_auth_header_sent(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(200, json={"status": "Healthy"})

        client = make_client(handler)
        client.health()
        assert captured["auth"] == "Bearer test-token"

    def test_health(self):
        def handler(request):
            assert request.url.path == "/api/v1.0/Health"
            return httpx.Response(200, json={"status": "Healthy", "timestamp": "2024-01-01T00:00:00Z"})

        client = make_client(handler)
        result = client.health()
        assert result["status"] == "Healthy"

    def test_list_tags_pagination_params(self):
        captured = {}

        def handler(request):
            captured["query"] = str(request.url.query)
            return httpx.Response(200, json={"pageNumber": 2, "pageSize": 10, "totalRecords": 0, "data": []})

        client = make_client(handler)
        client.list_tags(page_number=2, page_size=10)
        assert "pageNumber=2" in captured["query"]
        assert "pageSize=10" in captured["query"]

    def test_create_tag_posts_body(self):
        captured = {}

        def handler(request):
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content)
            return httpx.Response(201, json={"id": "abc", "name": "grp"})

        client = make_client(handler)
        result = client.create_tag({"name": "grp"})
        assert captured["method"] == "POST"
        assert captured["path"] == "/api/v1.0/Tags"
        assert captured["body"] == {"name": "grp"}
        assert result["id"] == "abc"

    def test_delete_returns_none_on_204(self):
        def handler(request):
            assert request.method == "DELETE"
            return httpx.Response(204)

        client = make_client(handler)
        assert client.delete_tag("abc") is None

    def test_error_raises_axis_error(self):
        def handler(request):
            return httpx.Response(401, json={"status": "Unauthorized", "details": "bad token"})

        client = make_client(handler)
        with pytest.raises(AxisSecurityError, match="401"):
            client.health()

    def test_connector_status_path(self):
        def handler(request):
            assert request.url.path == "/api/v1.0/Connectors/conn-1/status"
            return httpx.Response(200, json={"id": "conn-1", "status": "Available"})

        client = make_client(handler)
        result = client.connector_status("conn-1")
        assert result["status"] == "Available"

    def test_commit_path(self):
        def handler(request):
            assert request.method == "POST"
            assert request.url.path == "/api/v1.0/Commit"
            return httpx.Response(204)

        client = make_client(handler)
        assert client.commit_changes() is None

    def test_sub_location_path(self):
        def handler(request):
            assert request.url.path == "/api/v1.0/Locations/loc-1/SubLocations"
            return httpx.Response(200, json={"data": []})

        client = make_client(handler)
        client.list_sub_locations("loc-1")

    def test_metrics_recorded(self):
        def handler(request):
            return httpx.Response(200, json={"status": "Healthy"})

        client = make_client(handler)
        client.health()
        client.health()
        metrics = client.metrics()
        assert metrics["GET /Health"]["calls"] == 2


class TestUnwrapPaged:
    def test_unwraps_data(self):
        payload = {"data": [{"id": "1"}, {"id": "2"}], "totalRecords": 2}
        assert len(unwrap_paged(payload)) == 2

    def test_accepts_raw_list(self):
        assert len(unwrap_paged([{"id": "1"}])) == 1

    def test_empty(self):
        assert unwrap_paged(None) == []
        assert unwrap_paged({}) == []

    def test_summarize_paged(self):
        payload = {"pageNumber": 1, "pageSize": 50, "totalRecords": 3, "totalPages": 1, "data": [{"id": "1"}]}
        summary = summarize_paged(payload)
        assert summary["total_records"] == 3
        assert summary["returned"] == 1


class TestSummarizeConnectorStatus:
    def test_full_snapshot(self):
        payload = {
            "id": "c1",
            "status": "Available",
            "version": "1.2.3",
            "enabled": True,
            "primaryPublicIP": "1.2.3.4",
            "systemStatusCheckTime": "2024-01-01T00:00:00Z",
            "networkStatus": {"incomingKB": 100, "outgoingKB": 200},
            "memoryStatus": {"totalKB": 1000, "usedKB": 250, "freeKB": 750, "totalSwapKB": 0, "usedSwapKB": 0, "freeSwapKB": 0},
            "diskSpaceStatus": {"totalKB": 10000, "usedKB": 5000, "freeKB": 5000},
            "cpuStatus": {"numOfCpus": 4, "totalUsedPercentage": 25},
            "machineStatus": {"hostname": "conn-1", "operationSystem": "Linux"},
        }
        summary = summarize_connector_status(payload)
        assert summary["status"] == "Available"
        assert summary["memory"]["used_pct"] == 25.0
        assert summary["disk"]["used_pct"] == 50.0
        assert summary["cpu"]["used_pct"] == 25
        assert summary["machine"]["hostname"] == "conn-1"

    def test_non_dict(self):
        assert summarize_connector_status(None)["status"] == "unknown"


class TestSummarizeHealth:
    def test_unhealthy_components(self):
        payload = {
            "status": "Degraded",
            "service": "admin-api",
            "timestamp": "2024-01-01",
            "components": {
                "db": {"status": "Unhealthy", "details": "conn refused"},
                "cache": {"status": "Healthy"},
            },
        }
        summary = summarize_health(payload)
        assert summary["status"] == "Degraded"
        assert summary["unhealthy_components"] == ["db"]


class TestSummarizeTunnelStatus:
    def test_basic(self):
        assert summarize_tunnel_status({"id": "t1", "status": "Online"})["status"] == "Online"
        assert summarize_tunnel_status(None)["status"] == "unknown"


class TestSummarizeIpsecLocations:
    def test_flatten(self):
        payload = {
            "ipSecLocations": [
                {
                    "country": "US",
                    "locations": [
                        {
                            "city": "NYC",
                            "latitude": "40.7",
                            "longitude": "-74",
                            "provider": "AWS",
                            "fqdn": [{"name": "pop1.example.com", "ip": ["1.2.3.4", "5.6.7.8"]}],
                        }
                    ],
                }
            ]
        }
        summary = summarize_ipsec_locations(payload)
        assert summary["total"] == 1
        loc = summary["locations"][0]
        assert loc["country"] == "US"
        assert loc["fqdns"] == ["pop1.example.com"]
        assert loc["ips"] == ["1.2.3.4", "5.6.7.8"]

    def test_empty(self):
        assert summarize_ipsec_locations(None)["total"] == 0


class TestBodyBuilders:
    def test_tag_body_requires_name(self):
        with pytest.raises(ValueError):
            build_tag_body("")

    def test_tag_body(self):
        body = build_tag_body("grp", [{"id": "a", "value": "v"}])
        assert body["name"] == "grp"
        assert body["applications"] == [{"id": "a", "value": "v"}]

    def test_application_body_validates_type(self):
        with pytest.raises(ValueError, match="type must be one of"):
            build_application_body("app", "InvalidType", "zone-1")

    def test_application_body_requires_zone(self):
        with pytest.raises(ValueError, match="connectorZoneId"):
            build_application_body("app", "Web", "")

    def test_application_body_full(self):
        body = build_application_body("web-app", "Web", "zone-1", enabled=True, tags=[{"id": "t"}])
        assert body["type"] == "Web"
        assert body["connectorZoneId"] == "zone-1"

    def test_network_range_body(self):
        body = build_network_range_body(ip_ranges=["10.0.0.0/8"], enable_icmp=False)
        assert body["ipRangesOrCIDRs"] == ["10.0.0.0/8"]
        assert body["enableIcmp"] is False

    def test_connector_body_requires_zone(self):
        with pytest.raises(ValueError):
            build_connector_body("conn", "")

    def test_connector_zone_validates_enums(self):
        with pytest.raises(ValueError):
            build_connector_zone_body("z", "BadType", "Access")
        with pytest.raises(ValueError):
            build_connector_zone_body("z", "Regular", "BadPurpose")

    def test_ip_category_body(self):
        body = build_ip_category_body("cat", included_ips=["1.2.3.4"], description="d")
        assert body["includedIps"] == ["1.2.3.4"]
        assert body["description"] == "d"

    def test_web_category_body(self):
        body = build_web_category_body("web", included_domains=["example.com"])
        assert body["includedDomainsOrUrls"] == ["example.com"]

    def test_ssl_exclusion_validates_type(self):
        with pytest.raises(ValueError):
            build_ssl_exclusion_body("ex", "Bad")

    def test_group_body_requires_name(self):
        with pytest.raises(ValueError):
            build_group_body(" ")

    def test_user_body_validation(self):
        with pytest.raises(ValueError, match="userName"):
            build_user_body("ab", "e@e.com", "f", "l")
        with pytest.raises(ValueError, match="email"):
            build_user_body("user", "", "f", "l")
        with pytest.raises(ValueError, match="firstName"):
            build_user_body("user", "e@e.com", "", "l")
        body = build_user_body("user", "e@e.com", "f", "l")
        assert body["enabled"] is True

    def test_location_body(self):
        body = build_location_body("loc")
        assert body["name"] == "loc"

    def test_sub_location_requires_ip_ranges(self):
        with pytest.raises(ValueError, match="ipRanges"):
            build_sub_location_body("sub", "loc-1", [])

    def test_tunnel_body_requires_psk(self):
        with pytest.raises(ValueError, match="authenticationPsk"):
            build_tunnel_body("t", "loc-1", "id", "")

    def test_tunnel_body(self):
        body = build_tunnel_body("t", "loc-1", "id", "secret")
        assert body["authenticationPsk"] == "secret"
