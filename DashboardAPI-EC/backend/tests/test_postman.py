from app.compatibility.postman import is_postman_collection, postman_to_openapi

COLLECTION = {
    "info": {
        "name": "EdgeConnect 9.6",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "variable": [{"key": "host", "value": "https://ec.example/gms/rest"}],
    "item": [
        {
            "name": "Appliances",
            "item": [
                {
                    "name": "Change appliance",
                    "request": {
                        "method": "POST",
                        "url": {"raw": "{{host}}/appliance/{{nePk}}?cached=true"},
                        "header": [{"key": "X-Request-ID", "value": "test"}],
                        "body": {"mode": "raw", "raw": '{"enabled": true}'},
                    },
                }
            ],
        }
    ],
}


def test_postman_21_nested_collection_becomes_openapi_catalog():
    assert is_postman_collection(COLLECTION)
    result = postman_to_openapi(COLLECTION, "9.6")
    operation = result["paths"]["/gms/rest/appliance/{nePk}"]["post"]
    assert operation["tags"] == ["Appliances"]
    assert operation["requestBody"]["content"]["application/json"]["example"] == {"enabled": True}
    assert {(item["in"], item["name"]) for item in operation["parameters"]} == {
        ("path", "nePk"),
        ("query", "cached"),
        ("header", "X-Request-ID"),
    }
