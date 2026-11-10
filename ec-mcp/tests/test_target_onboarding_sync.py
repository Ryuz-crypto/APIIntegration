"""Safe onboarding: atomic registry sync and explicit failure reporting."""
from __future__ import annotations

import json
import os

import pytest
from starlette.testclient import TestClient

import ec_mcp.admin as admin


class FakeRegistry:
    def to_env_blob(self):
        return {"EC_ORCHESTRATORS_JSON": json.dumps({"one": {"url": "https://example.test"}})}

    def save_orchestrator(self, name, entry):
        return entry


def test_registry_sync_is_atomic_and_preserves_other_settings(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("OTHER=keep\nEC_ORCHESTRATORS_JSON=old\nEC_SSE_PLATFORMS_JSON=old\n")
    monkeypatch.setenv("EC_MCP_ENV_FILE", str(path))
    monkeypatch.setenv("EC_ORCHESTRATORS_JSON", "old")
    monkeypatch.setenv("EC_SSE_PLATFORMS_JSON", "old")
    monkeypatch.setattr(admin, "load_registry", lambda: FakeRegistry())
    before = path.read_bytes()
    replace = os.replace

    def fail_replace(source, destination):
        raise OSError("simulated failure")

    monkeypatch.setattr(admin.os, "replace", fail_replace)
    with pytest.raises(OSError):
        admin._sync_registry_blob()
    assert path.read_bytes() == before
    assert os.environ["EC_ORCHESTRATORS_JSON"] == "old"
    assert not list(tmp_path.glob("..env.*"))
    monkeypatch.setattr(admin.os, "replace", replace)
    admin._sync_registry_blob()
    result = path.read_text()
    assert "OTHER=keep" in result
    assert "EC_SSE_PLATFORMS_JSON=" not in result
    assert json.loads(os.environ["EC_ORCHESTRATORS_JSON"])["one"]["url"] == "https://example.test"
    assert "EC_SSE_PLATFORMS_JSON" not in os.environ


def test_save_reports_sync_failure_without_false_success(monkeypatch):
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "admin", "role": "admin"})
    monkeypatch.setattr(admin, "load_registry", lambda: FakeRegistry())
    monkeypatch.setattr(admin, "_snapshot_backup", lambda label: None)

    def fail_sync():
        raise OSError("simulated")

    monkeypatch.setattr(admin, "_sync_registry_blob", fail_sync)
    with TestClient(admin.build_admin_app()) as client:
        result = client.post("/api/orchestrators", json={"name": "one", "url": "https://example.test"})
    assert result.status_code == 500
    assert result.json()["ok"] is False
    assert "sincronización" in result.json()["error"]
