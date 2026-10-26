"""Tests for the dashboard payload collector and HTML renderer."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from ec_mcp.axis_client import AxisSecurityClient
from ec_mcp.dashboard import collect_dashboard_payload, render_dashboard_html


def make_axis_client(handler) -> AxisSecurityClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(
        base_url="https://admin-api.axissecurity.com",
        transport=transport,
    )
    return AxisSecurityClient(token="test-token", client=http_client)  # noqa: S106 - test fixture


class TestRenderDashboardHtml:
    def test_renders_empty_sections(self):
        payload = {
            "generated_at": 1700000000,
            "title": "ec-mcp NOC Dashboard",
            "edgeconnect": {"available": False, "reason": "Orchestrator is not configured"},
            "axis": {"available": False, "reason": "Axis Security is not enabled"},
        }
        page = render_dashboard_html(payload, refresh_seconds=30)
        assert "<!doctype html>" in page
        assert "EdgeConnect" in page
        assert "Axis Security" in page
        assert 'http-equiv="refresh" content="30"' in page
        assert "Orchestrator is not configured" in page

    def test_renders_appliance_rows(self):
        payload = {
            "generated_at": 1700000000,
            "title": "t",
            "edgeconnect": {
                "available": True,
                "appliances": [
                    {
                        "nePk": "1.NE",
                        "name": "EC1",
                        "model": "EC-10104",
                        "software_version": "9.6.0",
                        "ip": "10.0.0.1",
                        "reachability": "ok",
                    }
                ],
                "counts": {"appliances": 1, "reachable": 1},
            },
            "axis": {"available": False, "reason": "disabled"},
        }
        page = render_dashboard_html(payload)
        assert "EC1" in page
        assert "1.NE" in page
        assert "EC-10104" in page

    def test_escapes_html_in_names(self):
        payload = {
            "generated_at": 1700000000,
            "title": "t",
            "edgeconnect": {
                "available": True,
                "appliances": [{"nePk": "1.NE", "name": "<script>alert(1)</script>", "reachability": "bad"}],
                "counts": {"appliances": 1, "reachable": 0},
            },
            "axis": {"available": False, "reason": "disabled"},
        }
        page = render_dashboard_html(payload)
        # El nombre debe aparecer escapado en la tabla HTML
        assert "&lt;script&gt;" in page
        # Y en el JSON embebido no debe poder cerrar el tag </script> del bloque
        assert "alert(1)</script>" not in page
        assert "alert(1)<\\/script>" in page

    def test_embeds_raw_json(self):
        payload = {
            "generated_at": 1700000000,
            "title": "t",
            "edgeconnect": {"available": False, "reason": "x"},
            "axis": {"available": False, "reason": "y"},
        }
        page = render_dashboard_html(payload)
        assert 'id="raw"' in page
        assert "JSON.stringify(" in page


class TestCollectDashboardPayload:
    def test_no_clients_degrades(self):
        payload = collect_dashboard_payload(None, None)
        assert payload["edgeconnect"]["available"] is False
        assert payload["axis"]["available"] is False
        assert "generated_at" in payload

    def test_collects_axis_with_mock(self):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/Health"):
                return httpx.Response(
                    200,
                    json={
                        "status": "Healthy",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "components": {"db": {"status": "Healthy"}},
                    },
                )
            if path.endswith("/Connectors"):
                return httpx.Response(200, json={"data": [{"id": "c1", "name": "conn-a", "enabled": True}], "totalRecords": 1})
            if path.endswith("/Connectors/c1/status"):
                return httpx.Response(
                    200,
                    json={
                        "id": "c1",
                        "status": "Available",
                        "systemStatusCheckTime": "2026-01-01T00:00:00Z",
                        "networkStatus": {"incomingKB": 10, "outgoingKB": 20},
                        "memoryStatus": {"totalKB": 1000, "usedKB": 500, "freeKB": 500, "totalSwapKB": 0, "usedSwapKB": 0, "freeSwapKB": 0},
                        "diskSpaceStatus": {"totalKB": 1000, "usedKB": 250, "freeKB": 750},
                        "cpuStatus": {"numOfCpus": 4, "totalUsedPercentage": 12},
                        "machineStatus": {"hostname": "h", "operationSystem": "linux"},
                    },
                )
            if path.endswith("/Tunnels"):
                return httpx.Response(200, json={"data": [{"id": "t1", "name": "tun-a"}], "totalRecords": 1})
            if path.endswith("/Tunnels/t1/status"):
                return httpx.Response(200, json={"id": "t1", "status": "Online"})
            return httpx.Response(404, json={"message": "not found"})

        axis = make_axis_client(handler)
        payload = collect_dashboard_payload(None, axis)
        section = payload["axis"]
        assert section["available"] is True
        assert section["health"]["status"] == "Healthy"
        assert section["counts"]["connectors"] == 1
        assert section["connectors"][0]["status"]["status"] == "Available"
        assert section["counts"]["tunnels"] == 1
        assert section["tunnels"][0]["status"]["status"] == "Online"

    def test_axis_error_degrades(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"message": "boom"})

        axis = make_axis_client(handler)
        payload = collect_dashboard_payload(None, axis)
        section = payload["axis"]
        assert section["available"] is False
        assert "boom" in section["error"]

    def test_collects_edgeconnect_with_mock(self):
        class FakeClient:
            def list_appliances(self, refresh: bool = False):
                return [
                    {
                        "nePk": "1.NE",
                        "name": "EC1",
                        "model": "EC-10104",
                        "software_version": "9.6.0",
                        "ip": "10.0.0.1",
                        "lan_ip": "192.168.1.1",
                        "wan_ips": ["203.0.113.5"],
                        "state": "up",
                        "reachability": "ok",
                    }
                ]

            def get_raw(self, path, **query):
                if path == "/alarm/count/appliance":
                    return {"numOfCriticalAlarms": 0}
                raise RuntimeError(f"unexpected {path}")

        def fake_kpi_get(client, kpi, ne_pk="", granularity="", start_time="", end_time=""):
            return {"rows": []}

        def fake_project(payload):
            return {"projected": True}

        def fake_reachability(client):
            return {"1.NE": "ok"}

        payload = collect_dashboard_payload(
            FakeClient(),
            None,
            kpi_get=fake_kpi_get,
            project_wan_health_stats=fake_project,
            reachability_map=fake_reachability,
        )
        ec = payload["edgeconnect"]
        assert ec["available"] is True
        assert ec["counts"]["appliances"] == 1
        assert ec["appliances"][0]["name"] == "EC1"
        assert ec["appliances"][0]["tunnel_state"] == {"rows": []}
        assert ec["wan_health"][0]["latency"] == {"projected": True}

    def test_edgeconnect_list_error_degrades(self):
        class FailingClient:
            def list_appliances(self, refresh: bool = False):
                raise RuntimeError("connection refused")

        def fake_kpi_get(client, kpi, ne_pk="", granularity="", start_time="", end_time=""):
            return {}

        def fake_project(payload):
            return payload

        def fake_reachability(client):
            return {}

        payload = collect_dashboard_payload(
            FailingClient(),
            None,
            kpi_get=fake_kpi_get,
            project_wan_health_stats=fake_project,
            reachability_map=fake_reachability,
        )
        assert payload["edgeconnect"]["available"] is False
        assert "connection refused" in payload["edgeconnect"]["error"]


class TestRedaction:
    def test_payload_is_redacted(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/Health"):
                return httpx.Response(200, json={"status": "Healthy", "timestamp": "t", "components": {}})
            if request.url.path.endswith("/Connectors"):
                return httpx.Response(200, json={"data": [], "totalRecords": 0})
            if request.url.path.endswith("/Tunnels"):
                return httpx.Response(200, json={"data": [], "totalRecords": 0})
            return httpx.Response(404)

        axis = make_axis_client(handler)
        payload = collect_dashboard_payload(None, axis)
        page = render_dashboard_html(payload)
        assert "test-token" not in page


    def test_requires_injected_edgeconnect_helpers(self):
        class FakeClient:
            pass

        with pytest.raises(ValueError, match="helpers must be supplied"):
            collect_dashboard_payload(FakeClient(), None)


def test_server_binds_dashboard_helpers_to_server_instance():
    server_path = Path(__file__).resolve().parents[1] / "ec_mcp" / "server.py"
    source = server_path.read_text(encoding="utf-8")

    assert "def collect_current_dashboard_payload(" in source
    assert "kpi_get=kpi_get" in source
    assert "project_wan_health_stats=project_wan_health_stats" in source
    assert "reachability_map=reachability_map" in source
    assert source.count("collect_current_dashboard_payload(client, axis)") == 4
