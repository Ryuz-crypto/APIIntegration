"""Login input and cookie regression tests."""

from __future__ import annotations

from starlette.testclient import TestClient

import ec_mcp.admin as admin


def test_login_rejects_oversized_fields_and_marks_https_cookie_secure(monkeypatch, tmp_path):
    monkeypatch.setenv("EC_ADMIN_SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(admin.admin_users, "has_users", lambda: False)
    monkeypatch.setattr(admin, "_verify_password", lambda candidate, allow_first_run=True: candidate == "good")
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    admin.LOGIN_FAILURES.clear()
    with TestClient(admin.build_admin_app(), base_url="https://testserver") as client:
        response = client.post("/login", json={"username": "u", "password": "x" * 1025})
        assert response.status_code == 400
        response = client.post("/login", json={"username": "", "password": "good"})
        assert response.status_code == 200
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "secure" in cookie
        assert "samesite=lax" in cookie


def test_lockout_precedes_password_verification_and_expires(monkeypatch, tmp_path):
    monkeypatch.setenv("EC_ADMIN_SESSIONS_FILE", str(tmp_path / "sessions.json"))
    monkeypatch.setattr(admin.admin_users, "has_users", lambda: False)
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "LOGIN_MAX_FAILURES", 2)
    monkeypatch.setattr(admin, "LOGIN_WINDOW_SECONDS", 60.0)
    clock = [1000.0]
    monkeypatch.setattr(admin.time, "time", lambda: clock[0])
    attempts = []
    def verify(candidate, allow_first_run=True):
        attempts.append(candidate)
        return candidate == "good"
    monkeypatch.setattr(admin, "_verify_password", verify)
    admin.LOGIN_FAILURES.clear()
    with TestClient(admin.build_admin_app()) as client:
        assert client.post("/login", json={"password": "bad"}).json()["ok"] is False
        assert client.post("/login", json={"password": "bad"}).json()["ok"] is False
        assert client.post("/login", json={"password": "good"}).status_code == 429
        assert attempts == ["bad", "bad"]
        clock[0] += 61
        assert client.post("/login", json={"password": "good"}).status_code == 200
