"""Tests for atomic bulk tool enablement and bilingual agent guidance."""
from starlette.testclient import TestClient

import ec_mcp.admin as admin


def test_enable_all_requires_write_and_uses_one_update(monkeypatch):
    calls = []
    monkeypatch.setattr(admin, "update_env", lambda values: calls.append(values))
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "v", "role": "viewer"})
    with TestClient(admin.build_admin_app()) as client:
        assert client.post("/api/tools/enable-all", json={}).status_code == 403
    assert calls == []
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "o", "role": "operator"})
    with TestClient(admin.build_admin_app()) as client:
        result = client.post("/api/tools/enable-all", json={})
    assert result.status_code == 200
    assert result.json()["restart_required"] is True
    assert calls == [{"EC_MCP_DISABLED_TOOLS": ""}]


def test_agent_prompt_contains_english_and_spanish_guidance():
    assert "Reglas de oro" in admin.AGENT_PROMPT_HEADER
    assert "AI agent guidance (English)" in admin.AGENT_PROMPT_HEADER
    assert "Write tools are disabled by default" in admin.AGENT_PROMPT_HEADER
