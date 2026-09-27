from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.api.routes.tryme import router
from app.core.config import settings
from app.db.session import get_session
from app.models.compatibility import ApiCompatibilityProfile
from app.models.orchestrator import Orchestrator
from app.services.compatibility_service import store_openapi_profile
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectResponse

DOCUMENT = {
    "openapi": "3.0.3",
    "info": {"title": "Full EdgeConnect test API", "version": "9.6"},
    "servers": [{"url": "https://orchestrator.example/gms/rest"}],
    "paths": {
        "/appliance": {
            "get": {
                "operationId": "getAppliances",
                "summary": "List appliances",
                "tags": ["inventory"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 25},
                    }
                ],
            }
        },
        "/configuration/{nePk}": {
            "post": {
                "operationId": "changeConfiguration",
                "summary": "Change configuration",
                "tags": ["configuration"],
                "parameters": [
                    {"name": "nePk", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"enabled": {"type": "boolean", "default": True}},
                            }
                        }
                    }
                },
            }
        },
    },
}


def setup_app(monkeypatch):
    database = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(database)
    with Session(database) as session:
        orchestrator = Orchestrator(
            name="Lab",
            base_url="https://orchestrator.example",
            api_version="9.7.1.42046",
            swagger_version="9.6",
            auth_type="api_key",
        )
        session.add(orchestrator)
        session.commit()
        session.refresh(orchestrator)
        orchestrator_id = orchestrator.id
        store_openapi_profile(session, DOCUMENT, "9.6")

    def session_override():
        with Session(database) as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = session_override
    monkeypatch.setattr(settings, "tls_admin_token", "admin-test")
    return TestClient(app, client=("127.0.0.1", 12345)), orchestrator_id, database


def test_catalog_exposes_every_swagger_operation(monkeypatch):
    client, orchestrator_id, _ = setup_app(monkeypatch)
    response = client.get(f"/catalog/{orchestrator_id}")
    assert response.status_code == 200
    result = response.json()
    assert result["title"] == "Full EdgeConnect test API"
    assert [item["operation_id"] for item in result["operations"]] == [
        "changeConfiguration",
        "getAppliances",
    ]
    mutation = result["operations"][0]
    assert mutation["path"] == "/gms/rest/configuration/{nePk}"
    assert mutation["mutating"] is True
    assert mutation["request_example"] == {"enabled": True}


def test_catalog_can_be_synchronized_from_orchestrator(monkeypatch):
    client, orchestrator_id, database = setup_app(monkeypatch)
    with Session(database) as session:
        profile = session.get(ApiCompatibilityProfile, "9.6")
        profile.is_active = True
        profile.status = "supported"
        session.add(profile)
        session.commit()

    def fake_call(self, operation_id, method, path, *args, **kwargs):
        return EdgeConnectResponse(
            operation_id=operation_id,
            method=method,
            path=path,
            status_code=200,
            duration_ms=5,
            payload=DOCUMENT,
        )

    monkeypatch.setattr(EdgeConnectClient, "call_custom", fake_call)
    response = client.post(f"/catalog/{orchestrator_id}/sync")
    assert response.status_code == 200
    assert len(response.json()["operations"]) == 2
    assert response.json()["source"].startswith("Swagger importado")
    with Session(database) as session:
        assert session.get(ApiCompatibilityProfile, "9.6").is_active is True


def test_mutation_requires_admin_confirmation_and_can_be_snapshotted(monkeypatch):
    client, orchestrator_id, _ = setup_app(monkeypatch)

    def fake_call(self, operation_id, method, path, query_params, body, extra_headers):
        return EdgeConnectResponse(
            operation_id=operation_id,
            method=method,
            path=path,
            status_code=200,
            duration_ms=12,
            payload={"changed": True, "body": body},
            response_headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(EdgeConnectClient, "call_custom", fake_call)
    path = "/gms/rest/configuration/{nePk}"
    payload = {
        "orchestrator_id": str(orchestrator_id),
        "method": "POST",
        "path": path,
        "path_params": {"nePk": "1.NE"},
        "body": {"enabled": True, "password": "must-not-be-stored"},
        "confirmation": f"EJECUTAR POST {path}",
    }
    assert client.post("/execute", json=payload).status_code == 403
    headers = {"X-TLS-Admin-Token": "admin-test"}
    changed = client.post("/execute", json=payload, headers=headers)
    assert changed.status_code == 200
    assert changed.json()["path"].endswith("/configuration/1.NE")
    assert changed.json()["response"] == {
        "changed": True,
        "body": {"enabled": True, "password": "[REDACTED]"},
    }
    assert changed.json()["request"]["body"]["password"] == "[REDACTED]"

    snapshot = client.post(
        "/snapshots", json={"sample_id": changed.json()["sample_id"], "name": "Before policy change"}
    )
    assert snapshot.status_code == 201
    listed = client.get(f"/snapshots/{orchestrator_id}").json()
    assert listed[0]["name"] == "Before policy change"
    assert listed[0]["response_data"]["payload"]["changed"] is True
    assert listed[0]["request_data"]["body"]["password"] == "[REDACTED]"
    assert client.delete(f"/snapshots/{listed[0]['id']}").status_code == 204
