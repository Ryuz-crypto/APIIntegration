from app.services.orchestrator_service import _extract_version


def test_extracts_full_patch_version_from_nested_payload():
    payload = {"system": {"release": "Orchestrator 9.6.1.3 build 44210"}}

    assert _extract_version(payload) == "9.6.1.3"


def test_returns_none_when_payload_has_no_version():
    assert _extract_version({"status": "ok"}) is None


def test_prefers_version_field_over_ip_addresses():
    payload = {"managementIp": "172.16.3.20", "releaseVersion": "9.6.2.1"}

    assert _extract_version(payload) == "9.6.2.1"
