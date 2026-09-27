import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models
from app.core.config import settings
from app.db.session import get_session
from app.main import app


@pytest.fixture
def client(monkeypatch):
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
    monkeypatch.setattr("app.services.access_guard.has_users", lambda session: False)
    monkeypatch.setattr(settings, "tls_admin_token", "test-admin-token", raising=False)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_session, None)


PASSWORD = "correct-horse-battery"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_status_reports_open_mode(client):
    response = client.get("/api/v1/auth/status")
    assert response.status_code == 200
    body = response.json()
    assert body["users_configured"] is False
    assert body["login_required"] is True


def test_bootstrap_requires_admin_token(client, monkeypatch):
    monkeypatch.setattr(settings, "tls_admin_token", "other-admin-token", raising=False)
    response = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
    )
    assert response.status_code == 403
    response = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "wrong"},
    )
    assert response.status_code == 403


def test_login_and_me_and_logout(client):
    response = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 201, response.text

    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["token"]
    assert login.json()["user"]["role"] == "admin"

    me = client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    logout = client.post("/api/v1/auth/logout", headers=_auth(token))
    assert logout.status_code == 200

    me = client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 401


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "test-admin-token"},
    )
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password-xx"}
    )
    assert response.status_code == 401


def test_admin_can_manage_users_with_rbac(client):
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "test-admin-token"},
    )
    admin_token = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["token"]

    created = client.post(
        "/api/v1/auth/users",
        json={"username": "viewer1", "password": PASSWORD, "role": "viewer"},
        headers=_auth(admin_token),
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    listed = client.get("/api/v1/auth/users", headers=_auth(admin_token))
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    viewer_token = client.post(
        "/api/v1/auth/login", json={"username": "viewer1", "password": PASSWORD}
    ).json()["token"]

    forbidden = client.get("/api/v1/auth/users", headers=_auth(viewer_token))
    assert forbidden.status_code == 403

    updated = client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"role": "operator"},
        headers=_auth(admin_token),
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "operator"


def test_cannot_remove_last_admin(client):
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "test-admin-token"},
    )
    admin_token = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["token"]
    admin_id = client.get("/api/v1/auth/me", headers=_auth(admin_token)).json()["id"]

    demote = client.patch(
        f"/api/v1/auth/users/{admin_id}", json={"role": "viewer"}, headers=_auth(admin_token)
    )
    assert demote.status_code == 409

    disable = client.patch(
        f"/api/v1/auth/users/{admin_id}", json={"enabled": False}, headers=_auth(admin_token)
    )
    assert disable.status_code == 409

    deleted = client.delete(f"/api/v1/auth/users/{admin_id}", headers=_auth(admin_token))
    assert deleted.status_code == 409


def test_password_change_revokes_sessions(client):
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "test-admin-token"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["token"]

    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "new-strong-password-1"},
        headers=_auth(token),
    )
    assert changed.status_code == 200

    old_session = client.get("/api/v1/auth/me", headers=_auth(token))
    assert old_session.status_code == 401

    relogin = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "new-strong-password-1"}
    )
    assert relogin.status_code == 200


def test_api_requires_session_once_users_exist(client, monkeypatch):
    client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "admin", "password": PASSWORD, "role": "admin"},
        headers={"X-TLS-Admin-Token": "test-admin-token"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["token"]

    monkeypatch.setattr("app.services.access_guard.has_users", lambda session: True)
    response = client.get("/api/v1/orchestrators")
    assert response.status_code == 401

    response = client.get("/api/v1/orchestrators", headers=_auth(token))
    assert response.status_code == 200
