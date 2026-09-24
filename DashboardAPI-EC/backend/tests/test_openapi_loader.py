import pytest

from app.compatibility.loader import document_checksum, profile_from_openapi_document


def test_imports_openapi_and_maps_dashboard_operations():
    document = {
        "openapi": "3.0.3",
        "servers": [{"url": "https://orchestrator.example/gms/rest"}],
        "paths": {
            "/version": {"get": {"operationId": "getVersion"}},
            "/appliance": {"get": {"operationId": "getAppliances"}},
            "/stats/aggregate/interface": {"post": {"operationId": "aggregateInterfaces"}},
        },
    }

    profile = profile_from_openapi_document(document, "9.6")

    assert profile["api_root"] == "/gms/rest"
    assert profile["operations"]["orchestrator.version"]["path"] == "/version"
    assert "orchestrator.inventory.summary" in profile["operations"]
    assert "orchestrator.stats.aggregate.interface" in profile["operations"]
    assert profile["checksum"] == document_checksum(document)


def test_rejects_non_openapi_document():
    with pytest.raises(ValueError, match="OpenAPI or Swagger"):
        profile_from_openapi_document({"paths": {}}, "9.6")
