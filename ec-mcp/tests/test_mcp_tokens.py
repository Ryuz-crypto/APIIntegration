"""Tests for named MCP auth tokens (EC_MCP_AUTH_TOKENS_JSON) and panel endpoints."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest

from ec_mcp import admin
from ec_mcp.transport import (
    BearerAuthMiddleware,
    load_named_auth_tokens,
    resolve_auth_tokens,
)


def _strong() -> str:
    return secrets.token_urlsafe(48)


def test_load_named_auth_tokens(monkeypatch):
    monkeypatch.setenv("EC_MCP_AUTH_TOKENS_JSON", json.dumps({"Vibe": _strong(), "Claude": _strong()}))
    tokens = load_named_auth_tokens()
    assert set(tokens) == {"Vibe", "Claude"}
    monkeypatch.setenv("EC_MCP_AUTH_TOKENS_JSON", "{invalid")
    with pytest.raises(SystemExit, match="not valid JSON"):
        load_named_auth_tokens()
    monkeypatch.setenv("EC_MCP_AUTH_TOKENS_JSON", json.dumps({"bad": 123}))
    with pytest.raises(SystemExit, match="non-empty string"):
        load_named_auth_tokens()


def test_resolve_auth_tokens_includes_named_tokens(monkeypatch):
    env_token = _strong()
    vibe = _strong()
    monkeypatch.setenv("EC_MCP_AUTH_TOKEN", env_token)
    monkeypatch.setenv("EC_MCP_AUTH_TOKENS_JSON", json.dumps({"Vibe": vibe}))
    tokens = resolve_auth_tokens()
    assert env_token in tokens and vibe in tokens


def test_bearer_middleware_accepts_named_tokens(monkeypatch):
    import asyncio

    env_token = _strong()
    claude = _strong()
    monkeypatch.setenv("EC_MCP_AUTH_TOKEN", env_token)
    monkeypatch.setenv("EC_MCP_AUTH_TOKENS_JSON", json.dumps({"Claude": claude}))
    reached = []

    class _App:
        async def __call__(self, scope, receive, send):
            reached.append(scope.get("path"))

    middleware = BearerAuthMiddleware(_App(), resolve_auth_tokens())

    async def _send(message):
        pass

    def run(token: str):
        reached.clear()
        scope = {
            "type": "http",
            "path": "/mcp",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 1),
        }
        asyncio.run(middleware(scope, None, _send))

    run(claude)
    assert reached == ["/mcp"]
    run(_strong())
    assert reached == []
    run(env_token)
    assert reached == ["/mcp"]


def test_mcp_tokens_endpoints(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("EC_MCP_AUTH_TOKEN=env-token-value-0123456789abcdef\n", encoding="utf-8")
    monkeypatch.setenv("EC_MCP_ENV_FILE", str(env_file))
    monkeypatch.setenv("EC_MCP_AUTH_TOKEN", "env-token-value-0123456789abcdef")
    monkeypatch.delenv("EC_MCP_AUTH_TOKENS_JSON", raising=False)

    from starlette.testclient import TestClient

    app = admin.build_admin_app()
    client = TestClient(app)
    client.cookies.set("ec_admin_session", "test-session")
    monkeypatch.setattr(
        admin, "_check_session", lambda request: request.cookies.get("ec_admin_session") == "test-session"
    )
    monkeypatch.setattr(admin, "_authorize", lambda request, action: ({"user": "admin", "role": "admin"}, None))

    r = client.get("/api/mcp-tokens")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    names = [t["name"] for t in data["tokens"]]
    assert "Principal" in names
    assert "env-token-value" not in json.dumps(data)

    r = client.post("/api/mcp-tokens", json={"name": "Vibe"})
    assert r.status_code == 200
    created = r.json()
    assert created["ok"] is True
    token = created["token"]
    assert len(token) >= 32
    assert "EC_MCP_AUTH_TOKENS_JSON=" in env_file.read_text(encoding="utf-8")
    assert token in env_file.read_text(encoding="utf-8")

    r = client.post("/api/mcp-tokens", json={"name": "Vibe"})
    assert r.json()["ok"] is False

    r = client.get("/api/mcp-tokens")
    hints = {t["name"]: t for t in r.json()["tokens"]}
    assert hints["Vibe"]["revocable"] is True
    assert token not in json.dumps(hints)

    r = client.post("/api/mcp-tokens/delete", json={"name": "Vibe"})
    assert r.json()["ok"] is True
    assert "Vibe" not in env_file.read_text(encoding="utf-8")
    r = client.post("/api/mcp-tokens/delete", json={"name": "Vibe"})
    assert r.status_code == 404


def test_admin_page_has_tokens_tab():
    from ec_mcp.admin_page import PAGE

    assert "Tokens MCP" in PAGE
    assert "renderTokensMcp" in PAGE
    assert "/api/mcp-tokens" in PAGE
    assert "tab-tokens" in PAGE


def test_tools_filter_includes_central_domain():
    from ec_mcp.admin_page import PAGE

    assert 'value="central"' in PAGE
    assert "dom_central" in PAGE
