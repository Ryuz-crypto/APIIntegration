from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models
from app.db.session import get_session
from app.main import app


def test_setup_api_stores_secret_without_returning_it():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/orchestrators",
            json={
                "name": "OaaS Lab",
                "base_url": "https://orchestrator.example.com",
                "deployment_type": "oaas",
                "auth_type": "api_key",
                "api_token": "super-secret-value",
                "api_key_header": "X-Auth-Token",
                "login_type": 0,
                "verify_tls": True,
                "timeout_seconds": 20,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["deployment_type"] == "oaas"
        assert body["has_secret"] is True
        assert "api_token" not in body
        assert "encrypted_api_token" not in body
    finally:
        app.dependency_overrides.clear()
