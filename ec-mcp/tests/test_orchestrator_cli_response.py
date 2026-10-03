from __future__ import annotations

import pathlib

import httpx

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.orchestrator_client import OrchestratorClient

PROFILES = pathlib.Path(__file__).parent.parent / "ec_mcp" / "profiles"


def _client_with_transport(handler) -> OrchestratorClient:
    client = OrchestratorClient.__new__(OrchestratorClient)
    client._engine = CompatibilityEngine(load_profiles(PROFILES))
    client._api_root = "/gms/rest"
    client._api_key = "test-token"
    client._metrics = {}
    client._client = httpx.Client(
        base_url="https://orchestrator.example",
        transport=httpx.MockTransport(handler),
    )
    return client


def test_appliance_cli_proxy_returns_plain_text_without_json_decode_error():
    cli_output = "false Address         HWtype  HWaddress           Flags Mask Iface"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/gms/rest/appliance/rest"
        assert request.url.params["nePk"] == "0.NE"
        assert request.url.params["url"] == "/cli"
        assert request.read() == b'{"command":"show arp"}'
        return httpx.Response(200, text=cli_output, headers={"content-type": "text/plain"})

    client = _client_with_transport(handler)
    try:
        result = client.appliance_api_call(
            "9.6",
            "0.NE",
            "appliance.clipost13533",
            json_body={"command": "show arp"},
        )
    finally:
        client.close()

    assert result == cli_output


def test_appliance_cli_proxy_keeps_valid_json_responses():
    expected = {"output": "Address HWaddress Iface"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=expected)

    client = _client_with_transport(handler)
    try:
        result = client.appliance_api_call(
            "9.6",
            "0.NE",
            "appliance.clipost13533",
            json_body={"command": "show arp"},
        )
    finally:
        client.close()

    assert result == expected
