from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import load_builtin_profiles
from app.core.security import encrypt_secret
from app.models.orchestrator import Orchestrator
from app.services.edgeconnect_client import EdgeConnectClient


def test_api_key_uses_edgeconnect_auth_header():
    orchestrator = Orchestrator(
        name="OaaS",
        base_url="https://orchestrator.example.com/gms/rest",
        auth_type="api_key",
        encrypted_api_token=encrypt_secret("secret"),
    )
    client = EdgeConnectClient(orchestrator, CompatibilityEngine(load_builtin_profiles()))

    assert client._headers() == {"X-Auth-Token": "secret"}
    assert client._url("/gms/rest/version") == "https://orchestrator.example.com/gms/rest/version"
