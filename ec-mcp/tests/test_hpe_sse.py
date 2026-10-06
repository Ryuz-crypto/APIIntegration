"""HPE SSE bridge contracts with an in-memory transport; no tenant calls."""

import asyncio
import json

import httpx
import pytest

from ec_mcp.admin_config import public_config, update_env
from ec_mcp.config import Settings
from ec_mcp.hpe_sse import SSE_RESOURCES, SSEAdminClient
from ec_mcp.server import create_server

pytestmark = pytest.mark.security


def test_inventory_tool_reads_only_allowlisted_sdk_paths(monkeypatch, tmp_path):
    from ec_mcp import server as module

    requests = []
    settings = Settings(hpe_sse_api_token="lab-secret", audit_log_path=tmp_path / "audit.jsonl")  # noqa: S106

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer lab-secret"
        return httpx.Response(200, json={"data": [{"id": "category-1", "name": "Lab"}]})

    http = httpx.Client(base_url=settings.hpe_sse_api_url, transport=httpx.MockTransport(handler))
    client = SSEAdminClient(settings, http)
    monkeypatch.setattr(module, "SSEAdminClient", lambda _settings: client)
    server = create_server(settings)
    for resource, path in SSE_RESOURCES.items():
        result = json.loads(asyncio.run(server.call_tool("get_hpe_sse_inventory", {"resource": resource, "page": 2, "page_size": 5})).content[0].text)
        assert result["resource"] == resource
        assert result["response"]["data"][0]["name"] == "Lab"
        assert result["policy_decision_observed"] is False
        assert result["enforcement_verified"] is False
        assert requests[-1].url.path == path
        if resource == "health":
            assert not requests[-1].url.params
        else:
            assert requests[-1].url.params["pagenumber"] == "2"
            assert requests[-1].url.params["pagesize"] == "5"
    assert "lab-secret" not in (tmp_path / "audit.jsonl").read_text()
    http.close()


@pytest.mark.parametrize("resource,page,size", [
    ("arbitrary", 1, 5), ("/api/v1.0/Users", 1, 5),
    ("web_categories", 0, 5), ("web_categories", 1, 101),
    ("web_categories", True, 5),
])
def test_invalid_requests_never_reach_tenant(resource, page, size):
    def fail_if_called(request):
        pytest.fail(f"unexpected outbound request: {request.url}")

    settings = Settings(hpe_sse_api_token="lab-secret")  # noqa: S106
    with httpx.Client(base_url=settings.hpe_sse_api_url, transport=httpx.MockTransport(fail_if_called)) as http:
        client = SSEAdminClient(settings, http)
        with pytest.raises(ValueError):
            client.read(resource, page, size)


@pytest.mark.parametrize("url", ["http://admin-api.axissecurity.com", "https://user:pass@example.com", "https://example.com/api", "https://example.com?token=x"])
def test_sse_origin_requires_https_and_no_url_credentials(url):
    with pytest.raises(ValueError):
        SSEAdminClient(Settings(hpe_sse_api_token="lab-secret", hpe_sse_api_url=url))  # noqa: S106


def test_missing_token_rejects_call_without_orchestrator():
    server = create_server(Settings())
    result = json.loads(asyncio.run(server.call_tool("get_hpe_sse_inventory", {"resource": "health"})).content[0].text)
    assert "EC_HPE_SSE_API_TOKEN" in result["error"]
    assert result["enforcement_verified"] is False


def test_admin_configuration_masks_sse_token_and_rejects_insecure_origin(tmp_path):
    env = tmp_path / ".env"
    update_env({"EC_HPE_SSE_API_TOKEN": "lab-secret", "EC_HPE_SSE_API_URL": "https://sse.example"}, path=env)
    fields = {entry["key"]: entry for entry in public_config(env)["fields"]}
    assert fields["EC_HPE_SSE_API_TOKEN"]["configured"] is True
    assert fields["EC_HPE_SSE_API_TOKEN"]["value"] == ""
    assert "lab-secret" not in str(public_config(env))
    with pytest.raises(ValueError):
        update_env({"EC_HPE_SSE_API_URL": "http://sse.example"}, path=env)


@pytest.mark.parametrize("status,body", [(403, {"detail": "secret-server-response"}), (200, {"success": False, "error": "secret-server-response"}), (200, None)])
def test_errors_fail_closed_without_echoing_body_or_token(status, body):
    settings = Settings(hpe_sse_api_token="lab-secret")  # noqa: S106

    def handler(_request):
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status, text="not JSON")

    with httpx.Client(base_url=settings.hpe_sse_api_url, transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(RuntimeError) as error:
            SSEAdminClient(settings, http).read("web_categories")
        assert "lab-secret" not in str(error.value)
        assert "secret-server-response" not in str(error.value)
