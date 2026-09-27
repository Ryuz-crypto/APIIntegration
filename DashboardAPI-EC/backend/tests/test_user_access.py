import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.core.security import hash_password, hash_session_token, verify_password
from app.db.session import get_session
from app.services.auth_service import create_session, create_user, require_role, resolve_session


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_passwords_use_scrypt_and_reject_wrong_values():
    encoded = hash_password("a-secure-password")
    assert encoded.startswith("scrypt$")
    assert verify_password("a-secure-password", encoded)
    assert not verify_password("wrong-password", encoded)
    with pytest.raises(ValueError):
        hash_password("too-short")


def test_session_persists_only_token_digest(database):
    with Session(database) as session:
        user = create_user(session, "Admin", "a-secure-password", "Admin", "admin")
        token, auth_session = create_session(session, user)
        session.commit()
        assert auth_session.token_hash == hash_session_token(token)
        assert token not in auth_session.token_hash
        resolved = resolve_session(session, token)
        assert resolved is not None
        assert resolved[0].username == "admin"


def test_duplicate_username_is_case_insensitive(database):
    with Session(database) as session:
        create_user(session, "Operator", "a-secure-password", "", "operator")
        session.commit()
        with pytest.raises(HTTPException) as error:
            create_user(session, "operator", "another-password", "", "viewer")
        assert error.value.status_code == 409


def test_role_hierarchy_blocks_insufficient_permissions(database):
    with Session(database) as session:
        viewer = create_user(session, "viewer", "a-secure-password", "", "viewer")
        require_role(viewer, "viewer")
        with pytest.raises(HTTPException) as error:
            require_role(viewer, "operator")
        assert error.value.status_code == 403


def test_bootstrap_and_login_flow(database, monkeypatch):
    application = FastAPI()
    application.include_router(auth_router, prefix="/auth")

    def test_session():
        with Session(database) as session:
            yield session

    application.dependency_overrides[get_session] = test_session
    monkeypatch.setattr(settings, "tls_admin_token", "installation-token")
    client = TestClient(application)
    created = client.post(
        "/auth/bootstrap",
        json={
            "username": "admin",
            "password": "a-secure-password",
            "display_name": "Administrator",
            "admin_token": "installation-token",
        },
    )
    assert created.status_code == 201
    assert created.json()["user"]["role"] == "admin"
    assert created.json()["token"]
    assert client.post("/auth/bootstrap", json={
        "username": "other", "password": "a-secure-password",
        "display_name": "", "admin_token": "installation-token",
    }).status_code == 409
    logged_in = client.post(
        "/auth/login", json={"username": "ADMIN", "password": "a-secure-password"}
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["username"] == "admin"
