"""Regression coverage for preventing invalid admin TLS restarts."""

from __future__ import annotations

import asyncio
import json

import pytest

import ec_mcp.admin as admin
import ec_mcp.admin_config as config


def test_tls_preflight_rejects_missing_or_invalid_pair(tmp_path):
    assert config.tls_preflight_errors({"EC_ADMIN_TLS_ENABLED": "false"}) == []
    assert "EC_ADMIN_TLS_CERT" in config.tls_preflight_errors({"EC_ADMIN_TLS_ENABLED": "true"})[0]
    missing = {"EC_ADMIN_TLS_ENABLED": "true", "EC_ADMIN_TLS_CERT": str(tmp_path / "cert"),
               "EC_ADMIN_TLS_KEY": str(tmp_path / "key")}
    assert "no existe" in config.tls_preflight_errors(missing)[0]
    (tmp_path / "cert").write_text("not a certificate")
    (tmp_path / "key").write_text("not a private key")
    assert "No se pudo cargar" in config.tls_preflight_errors(missing)[0]


def test_update_rejects_invalid_tls_without_writing(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    original = "EC_ADMIN_HOST=127.0.0.1\nEC_ADMIN_TLS_ENABLED=false\n"
    path.write_text(original)
    for key in ("EC_ADMIN_HOST", "EC_ADMIN_TLS_ENABLED", "EC_ADMIN_TLS_CERT", "EC_ADMIN_TLS_KEY"):
        monkeypatch.delenv(key, raising=False)
    result = config.diff_env({"EC_ADMIN_TLS_ENABLED": "true"}, path=path)
    assert result["ok"] is False
    with pytest.raises(ValueError, match="EC_ADMIN_TLS_CERT"):
        config.update_env({"EC_ADMIN_TLS_ENABLED": "true"}, path=path)
    assert path.read_text() == original


def test_valid_tls_pair_reaches_ssl_loader(tmp_path, monkeypatch):
    cert, key = tmp_path / "cert", tmp_path / "key"
    cert.write_text("fixture")
    key.write_text("fixture")
    calls = []

    class Context:
        def load_cert_chain(self, *, certfile, keyfile):
            calls.append((certfile, keyfile))

    monkeypatch.setattr(config.ssl, "SSLContext", lambda protocol: Context())
    errors = config.tls_preflight_errors(
        {"EC_ADMIN_TLS_ENABLED": "true", "EC_ADMIN_TLS_CERT": str(cert), "EC_ADMIN_TLS_KEY": str(key)}
    )
    assert errors == []
    assert calls == [(str(cert), str(key))]


def test_restart_does_not_queue_when_tls_invalid(monkeypatch):
    queued = []
    monkeypatch.setattr(admin, "_authorize", lambda request, permission: ({"user": "test"}, None))
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "_has_password_configured", lambda: False)
    monkeypatch.setattr(admin, "restart_tls_errors", lambda: ["TLS invalid"])
    monkeypatch.setattr(admin, "queue_restart", lambda: queued.append(True))
    response = asyncio.run(admin.api_restart(None))
    assert response.status_code == 400
    assert json.loads(response.body)["state"] == "error"
    assert queued == []


class _RestartBody:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        if self._payload is None:
            raise ValueError("bad body")
        return self._payload


def test_restart_requires_password_when_configured(monkeypatch):
    queued = []
    monkeypatch.setattr(admin, "_authorize", lambda request, permission: ({"user": "test"}, None))
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "_has_password_configured", lambda: True)
    monkeypatch.setattr(
        admin, "_verify_password", lambda candidate, allow_first_run=True: candidate == "right"
    )
    monkeypatch.setattr(admin, "restart_tls_errors", lambda: [])
    monkeypatch.setattr(admin, "queue_restart", lambda: queued.append(True) or {"state": "pending"})

    wrong = asyncio.run(admin.api_restart(_RestartBody({"password": "wrong"})))
    assert wrong.status_code == 403
    assert json.loads(wrong.body)["error"] == "Contrase\u00f1a del panel incorrecta"
    assert queued == []

    ok = asyncio.run(admin.api_restart(_RestartBody({"password": "right"})))
    assert ok.status_code == 200
    assert queued == [True]
