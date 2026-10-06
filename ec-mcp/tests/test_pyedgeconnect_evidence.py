"""Read-only EdgeConnect evidence contracts across supported Orchestrator profiles."""

import json

import httpx
import pytest

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.config import Settings
from ec_mcp.edgeconnect_evidence import (
    ENDPOINT_ASSOCIATIONS,
    FLOW_DETAILS,
    IPSLA_SETTINGS,
    REMOTE_ENDPOINTS,
    SERVICE_PROVIDERS,
    bounded_id,
    flow_evidence,
    service_evidence,
)
from ec_mcp.orchestrator_client import OrchestratorClient

pytestmark = pytest.mark.security


@pytest.mark.parametrize("version", ["9.3", "9.4", "9.5", "9.6"])
def test_read_evidence_scoped_and_secrets_excluded(version):
    requests = []
    secret = "DO-NOT-RETURN-ME"
    responses = {
        "/thirdPartyServices/serviceOrchestration/serviceProviders": [
            {"serviceId": 7, "serviceName": "SSE", "tunnelSettings": json.dumps({"preSharedKey": secret})},
        ],
        "/thirdPartyServices/serviceOrchestration/remoteEndpoints": {
            "remoteEndpoints": [{"remoteEndpointId": 19, "remoteEndpointName": "POP", "ipAddress": "192.0.2.10", "preSharedKey": secret}],
        },
        "/thirdPartyServices/serviceOrchestration/remoteEndPointAssociations": {"19": ["2.NE"]},
        "/thirdPartyServices/serviceOrchestration/ipslaSetting": {"data": {"enable": True, "secret": secret}},
        "/flow/flowDetails2": {"data": {"srcIp": "192.0.2.20", "dstIp": "192.0.2.30", "action": "deny", "nested": {"password": secret}}},
    }

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path.startswith("/gms/rest/")
        path = request.url.path.removeprefix("/gms/rest")
        return httpx.Response(200, json=responses[path])

    settings = Settings(orchestrator_url="https://orchestrator.example", orchestrator_api_key="test-token")
    transport = httpx.Client(base_url=settings.orchestrator_url, transport=httpx.MockTransport(handler))
    client = OrchestratorClient(settings, CompatibilityEngine(load_profiles(settings.profiles_dir)), transport)
    client._cached_profile = version
    service = service_evidence(7, "2.NE", client.call(version, SERVICE_PROVIDERS),
        client.call(version, REMOTE_ENDPOINTS, serviceId=7),
        client.call(version, ENDPOINT_ASSOCIATIONS, serviceId=7),
        client.call(version, IPSLA_SETTINGS, serviceId=7))
    assert service["associated_endpoints"][0]["remoteEndpointId"] == 19
    assert service["enforcement_verified"] is False
    assert service["tunnel_state_observed"] is False
    assert len(requests) == 4
    assert all(request.url.params.get("serviceId") == "7" for request in requests[1:])

    flow = flow_evidence("2.NE", 42, 0, client.call(version, FLOW_DETAILS, nePk="2.NE", id=42, seq=0))
    assert flow["flow_details"]["action"] == "deny"
    assert flow["policy_decision_observed"] is True
    assert flow["enforcement_verified"] is False
    assert dict(requests[-1].url.params) == {"nePk": "2.NE", "id": "42", "seq": "0"}
    assert secret not in json.dumps([service, flow])
    transport.close()


@pytest.mark.parametrize("value", [-1, True, 2_147_483_648, "7"])
def test_invalid_ids_rejected(value):
    with pytest.raises(ValueError):
        bounded_id(value, "flow_id")


def test_unrecognized_association_does_not_claim_disconnected():
    from ec_mcp.edgeconnect_evidence import service_evidence

    with pytest.raises(ValueError, match="association response shape"):
        service_evidence(7, "2.NE", [{"serviceId": 7}], {"remoteEndpoints": []}, {"unexpected": "unknown"}, {})
