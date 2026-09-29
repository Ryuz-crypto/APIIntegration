import json

from ec_mcp.import_postman import postman_to_profile

COLLECTION = {
    "info": {
        "name": "EdgeConnect SD-WAN API",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [{"key": "baseUrl", "value": "https://orchestrator.example.com"}],
    "item": [
        {
            "name": "Appliances",
            "item": [
                {
                    "name": "Get All Appliances",
                    "request": {"method": "GET", "url": "{{baseUrl}}/gms/rest/appliance"},
                },
                {
                    "name": "Get Appliance Tunnels Stats",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{baseUrl}}/gms/rest/stats/aggregate/tunnel?nePk=3.NE&startTime=0&endTime=0&granularity=minute",
                            "query": [
                                {"key": "nePk", "value": "3.NE"},
                                {"key": "startTime", "value": "0"},
                                {"key": "endTime", "value": "0"},
                                {"key": "granularity", "value": "minute"},
                            ],
                        },
                    },
                },
                {
                    "name": "Suspend Appliance",
                    "request": {
                        "method": "POST",
                        "url": "{{baseUrl}}/gms/rest/appliance/suspend/3.NE",
                        "body": {"mode": "raw", "raw": json.dumps({"suspend": True})},
                    },
                },
            ],
        },
        {
            "name": "Broken Entry",
            "request": {"method": "GET", "url": ""},
        },
    ],
}


def test_postman_import_generates_profile():
    profile = postman_to_profile(COLLECTION, "9.6")
    assert profile["version"] == "9.6"
    assert profile["status"] == "imported"
    ops = profile["operations"]
    assert len(ops) == 3
    tunnels = ops["get_appliance_tunnels_stats"]
    assert tunnels["path"] == "/gms/rest/stats/aggregate/tunnel"
    assert set(tunnels["query_params"]) == {"nePk", "startTime", "endTime", "granularity"}
    suspend = ops["suspend_appliance"]
    assert suspend["method"] == "POST"
    assert suspend["risk"] == "write"
    assert suspend["path"] == "/gms/rest/appliance/suspend/3.NE"
    assert suspend["body_example"] == {"suspend": True}
    assert ops["get_all_appliances"]["risk"] == "read"


def test_postman_rejects_non_collection():
    try:
        postman_to_profile({"openapi": "3.0"}, "9.6")
        raise AssertionError("should have raised")
    except ValueError as error:
        assert "Postman" in str(error)


def test_write_operations_in_builtin_profiles():
    from ec_mcp.compat import load_profiles

    profiles = load_profiles(PROFILES_DIR)
    for profile in profiles:
        ops = profile["operations"]
        for required in ["appliance.interface.set_admin_state", "appliance.suspend_traffic", "policy_group.update"]:
            assert required in ops, f"{required} missing in {profile['version']}"
        assert ops["appliance.suspend_traffic"]["method"] == "POST"
        assert ops["orchestrator.events"]["method"] == "GET"


PROFILES_DIR = __import__("pathlib").Path(__file__).parent.parent / "ec_mcp" / "profiles"
