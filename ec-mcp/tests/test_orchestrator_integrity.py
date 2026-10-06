from __future__ import annotations

import httpx
import pytest

from ec_mcp.compat import CompatibilityEngine
from ec_mcp.config import Settings
from ec_mcp.orchestrator_client import OrchestratorClient


def make_client(handler, method="POST"):
    engine = CompatibilityEngine([{
        "version": "9.6", "api_root": "/gms/rest",
        "operations": {"test": {"method": method, "path": "/resource"}},
    }])
    http = httpx.Client(base_url="https://orch.example", transport=httpx.MockTransport(handler))
    return OrchestratorClient(Settings(orchestrator_url="https://orch.example", orchestrator_api_key="fixture"), engine, http)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("status", [200, 204, 404])
def test_write_never_retries_alternate_route(method, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status)

    client = make_client(handler, method)
    try:
        if status == 404:
            with pytest.raises(RuntimeError, match="HTTP 404"):
                client.call("9.6", "test", json_body={"value": 1})
        else:
            assert client.call("9.6", "test", json_body={"value": 1}) == {"ok": True}
        assert len(requests) == 1
        assert requests[0].method == method
    finally:
        client.close()


def test_read_fallback_remains_available():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(404) if len(paths) == 1 else httpx.Response(200, json={"found": True})

    client = make_client(handler, "GET")
    try:
        assert client.call("9.6", "test") == {"found": True}
        assert paths == ["/gms/rest/resource", "/resource"]
    finally:
        client.close()


def test_inventory_refresh_ttl_and_caller_mutation(monkeypatch):
    import ec_mcp.orchestrator_client as module

    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    reads = []
    state = {"name": "Before"}

    def handler(request):
        reads.append(request.url.path)
        return httpx.Response(200, json={"data": [{"nePk": "1.NE", "name": state["name"], "state": 0, "reachability": False}]})

    client = make_client(handler)
    try:
        first = client.list_appliances()
        assert first[0]["state"] == 0
        assert first[0]["reachability"] is False
        first[0]["name"] = "Corrupted by caller"
        assert client.list_appliances()[0]["name"] == "Before"
        assert len(reads) == 1
        state["name"] = "Refreshed"
        assert client.list_appliances(refresh=True)[0]["name"] == "Refreshed"
        assert len(reads) == 2
        state["name"] = "After TTL"
        clock[0] += 31
        assert client.list_appliances()[0]["name"] == "After TTL"
        assert len(reads) == 3
        raw = client.get_raw("/appliance")
        raw["data"].clear()
        assert len(client.get_raw("/appliance")["data"]) == 1
    finally:
        client.close()


@pytest.mark.parametrize("appliance", [False, True])
def test_write_invalidates_response_and_inventory_caches(appliance):
    state = {"name": "Before"}

    def handler(request):
        if request.method == "POST":
            state["name"] = "After"
            return httpx.Response(204)
        return httpx.Response(200, json={"data": [{"nePk": "1.NE", "name": state["name"]}]})

    client = make_client(handler)
    try:
        assert client.list_appliances()[0]["name"] == "Before"
        if appliance:
            client.appliance_api_call("9.6", "1.NE", "test", json_body={"value": 1})
        else:
            client.call("9.6", "test", json_body={"value": 1})
        assert client.list_appliances()[0]["name"] == "After"
    finally:
        client.close()
