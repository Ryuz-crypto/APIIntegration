import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models
from app.api.routes import orchestrators as routes
from app.compatibility.engine import CompatibilityEngine
from app.compatibility.loader import load_builtin_profiles
from app.core.security import encrypt_secret
from app.db.session import get_session
from app.main import app
from app.models.orchestrator import Orchestrator
from app.services import interactive_auth
from app.services.edgeconnect_client import EdgeConnectClient, EdgeConnectClientError


class Cache:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key):
        return self.values.get(key)

    def getdel(self, key):
        return self.values.pop(key, None)

    def delete(self, key):
        self.values.pop(key, None)


@pytest.fixture
def mfa(monkeypatch):
    cache = Cache()
    monkeypatch.setattr(interactive_auth, "store", lambda: cache)
    engine = CompatibilityEngine(load_builtin_profiles())
    orch = Orchestrator(
        name="MFA test",
        base_url="https://orch.example/gms/rest",
        auth_type="session_otp",
        username="test-user",
        encrypted_password=encrypt_secret("private-password"),
    )
    calls = []
    outcome = {"start": 200, "login": 200, "data": 200}

    def remote(request):
        calls.append(request)
        path = request.url.path
        if path.endswith("/loginToken"):
            if outcome["start"] != 200:
                return httpx.Response(outcome["start"], json={"raw": "private-password"})
            assert json.loads(request.content) == {
                "user": "test-user",
                "password": "private-password",
                "TempCode": False,
            }
            return httpx.Response(
                200,
                json=True,
                headers={"set-cookie": "preauth=private-challenge; Path=/gms/rest; Secure"},
            )
        if path.endswith("/login"):
            assert "preauth=private-challenge" in request.headers["cookie"]
            assert json.loads(request.content)["token"] == "123456"
            if outcome["login"] != 200:
                return httpx.Response(outcome["login"], json={"raw": "private-password 123456"})
            return httpx.Response(
                200,
                json=True,
                headers=[
                    ("set-cookie", "orchCsrfToken=private-csrf; Path=/gms/rest; Secure"),
                    ("set-cookie", "JSESSIONID=private-session; Path=/gms/rest; Secure"),
                ],
            )
        assert request.headers["x-xsrf-token"] == "private-csrf"
        assert "JSESSIONID=private-session" in request.headers["cookie"]
        if path.endswith("/briefInfo"):
            return httpx.Response(outcome["data"], json={"release": outcome.get("release", "9.6.2.0")})
        if path.endswith("/appliance"):
            return httpx.Response(200, json=[])
        pytest.fail(f"Unexpected request: {request.method} {path}")

    original = httpx.Client
    transport = httpx.MockTransport(remote)
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=transport, **kwargs))
    return orch, engine, cache, calls, outcome


def test_mfa_wait_then_single_login_shared_across_clients(mfa):
    orch, engine, cache, calls, _ = mfa
    pending = interactive_auth.start(orch, engine)
    assert pending["status"] == "otp_required"
    assert len(calls) == 1
    assert list(cache.ttls.values()) == [300]
    assert "private-challenge" not in str(cache.values)
    interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    assert "123456" not in str(cache.values)
    assert "private-session" not in str(cache.values)
    # Independent clients emulate independent Uvicorn workers and HTTP requests.
    version = EdgeConnectClient(orch, engine).detect_version()
    inventory = EdgeConnectClient(orch, engine).call_operation(
        "9.6", "orchestrator.inventory.summary"
    )
    assert version.payload["release"] == "9.6.2.0"
    assert inventory.payload == {"items": []}
    assert [r.url.path for r in calls] == [
        "/gms/rest/authentication/loginToken",
        "/gms/rest/authentication/login",
        "/gms/rest/gmsserver/briefInfo",
        "/gms/rest/appliance",
    ]
    with pytest.raises(interactive_auth.InteractiveAuthError):
        interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    assert len(calls) == 4


def test_cancel_expiry_and_credential_binding(mfa):
    orch, engine, cache, calls, _ = mfa
    pending = interactive_auth.start(orch, engine)
    interactive_auth.cancel(orch, pending["challenge_id"])
    with pytest.raises(interactive_auth.InteractiveAuthError):
        interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    pending = interactive_auth.start(orch, engine)
    cache.values.clear()  # Redis TTL eviction
    with pytest.raises(interactive_auth.InteractiveAuthError):
        interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    pending = interactive_auth.start(orch, engine)
    orch.encrypted_password = encrypt_secret("changed")
    with pytest.raises(interactive_auth.InteractiveAuthError, match="cambiaron"):
        interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    assert len(calls) == 3  # Never submit an OTP for an invalid challenge.


def test_rejected_otp_is_not_retried_or_recorded(mfa):
    orch, engine, cache, calls, outcome = mfa
    pending = interactive_auth.start(orch, engine)
    outcome["login"] = 401
    with pytest.raises(EdgeConnectClientError) as failure:
        interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    assert failure.value.payload == {}
    assert "123456" not in str(failure.value)
    assert len(calls) == 2
    assert not cache.values


def test_failed_first_factor_does_not_enter_otp_wait(mfa):
    orch, engine, cache, calls, outcome = mfa
    outcome["start"] = 404
    with pytest.raises(
        EdgeConnectClientError, match="POST /gms/rest/authentication/loginToken: HTTP 404"
    ) as failure:
        interactive_auth.start(orch, engine)
    assert failure.value.payload == {}
    assert not cache.values
    assert len(calls) == 1


def test_404_reports_actual_path_and_expired_session_does_not_relogin(mfa):
    orch, engine, cache, calls, outcome = mfa
    pending = interactive_auth.start(orch, engine)
    interactive_auth.complete(orch, engine, pending["challenge_id"], "123456")
    outcome["data"] = 404
    with pytest.raises(EdgeConnectClientError, match="GET /gms/rest/gmsserver/briefInfo: HTTP 404"):
        EdgeConnectClient(orch, engine).detect_version()
    assert len(calls) == 3
    outcome["data"] = 401
    with pytest.raises(EdgeConnectClientError):
        EdgeConnectClient(orch, engine).detect_version()
    assert interactive_auth.active_key(orch) not in cache.values
    with pytest.raises(EdgeConnectClientError, match="expiró"):
        EdgeConnectClient(orch, engine).detect_version()
    assert len(calls) == 4


@pytest.mark.parametrize("release", ["9.6.2.0", "9.7.1.42046"])
def test_api_start_complete_validate_and_discover(mfa, monkeypatch, release):
    orch, engine, _, calls, outcome = mfa
    outcome["release"] = release
    database = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(database)
    with Session(database) as db:
        db.add(orch)
        db.commit()
        db.refresh(orch)
        orch_id = orch.id

    def session():
        with Session(database) as db:
            yield db

    app.dependency_overrides[get_session] = session
    monkeypatch.setattr(routes, "build_compatibility_engine", lambda session: engine)
    try:
        client = TestClient(app)
        url = f"/api/v1/orchestrators/{orch_id}"
        start = client.post(f"{url}/auth/start")
        assert start.status_code == 200
        assert len(calls) == 1
        complete = client.post(
            f"{url}/auth/complete",
            json={"challenge_id": start.json()["challenge_id"], "otp": "123456"},
        )
        assert complete.status_code == 200
        assert complete.json()["status"] == "validated"
        assert complete.json()["detected_version"] == release
        assert complete.json()["compatibility_profile"] == "9.6"
        assert complete.json()["capabilities"]["orchestrator.inventory.summary"]
        assert "123456" not in complete.text
        assert client.post(f"{url}/discover-appliances").status_code == 200
        assert len(calls) == 4
    finally:
        app.dependency_overrides.clear()
