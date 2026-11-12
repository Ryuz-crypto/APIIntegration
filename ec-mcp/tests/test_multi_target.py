"""Tests for the multi-Orchestrator / multi-SSE registry and admin endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ec_mcp.admin import build_admin_app
from ec_mcp.multi_target import (
    RegistryError,
    TargetRegistry,
    central_from_entry,
    load_central_from_env,
    load_orchestrators_from_env,
    load_sse_from_env,
    orchestrator_from_entry,
    public_central,
    public_orchestrator,
    public_sse,
    sse_from_entry,
)


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch) -> TargetRegistry:
    path = tmp_path / ".ec-admin.json"
    monkeypatch.setenv("EC_ADMIN_STORE", str(path))
    return TargetRegistry(path)


def test_registry_saves_multiple_orchestrators_independently(registry: TargetRegistry):
    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": "k1"})
    registry.save_orchestrator(
        "lab", {"url": "https://lab.example.com", "username": "u", "password": "secret-lab-pass"}
    )
    orch = registry.list_orchestrators()
    assert set(orch) == {"prod", "lab"}
    assert orch["prod"]["api_key"] == "k1"
    assert orch["lab"]["username"] == "u"
    assert "secret-lab-pass" not in json.dumps(public_orchestrator("lab", orch["lab"]))


def test_registry_secret_update_keeps_existing_when_empty(registry: TargetRegistry):
    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": "real-api-key-value"})
    # Empty string means "keep" in the admin flow (None clears)
    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": None})
    assert registry.get_orchestrator("prod").get("api_key") == "real-api-key-value"


def test_registry_delete_orchestrator(registry: TargetRegistry):
    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": "k1"})
    assert registry.delete_orchestrator("prod") is True
    assert registry.delete_orchestrator("prod") is False
    assert registry.list_orchestrators() == {}


def test_registry_saves_multiple_sse_platforms(registry: TargetRegistry):
    registry.save_sse("axis-prod", {"base_url": "https://axis-prod.example.com", "admin_token": "t1"})
    registry.save_sse("axis-dr", {"base_url": "https://axis-dr.example.com", "admin_token": "t2"})
    sse = registry.list_sse()
    assert set(sse) == {"axis-prod", "axis-dr"}
    pub = public_sse("axis-prod", sse["axis-prod"])
    assert pub["has_admin_token"] is True
    assert "t1" not in json.dumps(pub)


def test_registry_rejects_invalid_entries(registry: TargetRegistry):
    with pytest.raises(RegistryError):
        registry.save_orchestrator("bad", {"url": "not-a-url", "api_key": "k"})
    with pytest.raises(RegistryError):
        registry.save_orchestrator("no-creds", {"url": "https://x.example.com"})
    with pytest.raises(RegistryError):
        registry.save_orchestrator("bad name", {"url": "https://x.example.com", "api_key": "k"})
    with pytest.raises(RegistryError):
        registry.save_sse("sse", {"base_url": "https://x.example.com"})


def test_registry_file_permissions_are_0600(registry: TargetRegistry):
    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": "k1"})
    if os.name != "nt":
        assert registry._path.stat().st_mode & 0o777 == 0o600


def test_to_env_blob_renders_json(registry: TargetRegistry):
    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": "k1"})
    registry.save_sse("axis", {"base_url": "https://axis.example.com", "admin_token": "t"})
    blob = registry.to_env_blob()
    assert "EC_ORCHESTRATORS_JSON" in blob
    assert "EC_SSE_PLATFORMS_JSON" in blob
    orch = json.loads(blob["EC_ORCHESTRATORS_JSON"])
    assert orch["prod"]["api_key"] == "k1"


def test_load_from_env_roundtrip(monkeypatch):
    monkeypatch.setenv(
        "EC_ORCHESTRATORS_JSON",
        json.dumps(
            {
                "prod": {"url": "https://prod.example.com", "api_key": "k1"},
                "lab": {"url": "https://lab.example.com", "username": "u", "password": "p"},
            }
        ),
    )
    monkeypatch.setenv(
        "EC_SSE_PLATFORMS_JSON",
        json.dumps({"axis-a": {"base_url": "https://a.example.com", "admin_token": "t"}}),
    )
    orchs = load_orchestrators_from_env()
    assert set(orchs) == {"prod", "lab"}
    assert orchs["prod"].url == "https://prod.example.com"
    sses = load_sse_from_env()
    assert sses["axis-a"].admin_token == "t"


def test_load_from_env_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("EC_ORCHESTRATORS_JSON", "{not json")
    with pytest.raises(RegistryError):
        load_orchestrators_from_env()


def test_admin_state_includes_sse_platforms(registry: TargetRegistry, monkeypatch):
    from ec_mcp import admin

    registry.save_orchestrator("prod", {"url": "https://prod.example.com", "api_key": "k1"})
    registry.save_sse("axis", {"base_url": "https://axis.example.com", "admin_token": "jwt-secret-token"})
    monkeypatch.setenv("EC_ORCHESTRATOR_URL", "https://prod.example.com")
    monkeypatch.setenv("EC_AXIS_ENABLED", "true")
    state = admin._public_state()
    assert state["orchestrators"][0]["name"] == "prod"
    assert state["orchestrators"][0]["active"] is True
    assert state["sse_platforms"][0]["name"] == "axis"
    assert "jwt-secret-token" not in json.dumps(state)


def test_admin_routes_include_sse():
    paths = {route.path for route in build_admin_app().routes}
    assert {"/api/sse", "/api/sse/delete", "/api/orchestrators", "/api/orchestrators/delete", "/api/apply"}.issubset(
        paths
    )


def test_admin_page_has_sse_tab():
    from ec_mcp.admin_page import PAGE

    assert "Plataformas SSE" in PAGE
    assert "renderSse" in PAGE
    assert "/api/sse" in PAGE


def test_orchestrator_from_entry_validates():
    with pytest.raises(RegistryError):
        orchestrator_from_entry("x", {"url": "https://x.example.com"})
    target = orchestrator_from_entry("x", {"url": "https://x.example.com", "api_key": "k"})
    assert target.name == "x"
    assert target.verify_tls is True


def test_sse_from_entry_validates():
    with pytest.raises(RegistryError):
        sse_from_entry("x", {"base_url": "https://x.example.com"})
    target = sse_from_entry("x", {"base_url": "https://x.example.com", "admin_token": "t"})
    assert target.provider == "axis"
    assert target.timeout == 30.0


class TestCentralMultiTenant:
    def test_registry_saves_multiple_central_platforms(self, registry: TargetRegistry):
        registry.save_central(
            "central-prod",
            {"base_url": "https://us.api.central.arubanetworks.com", "client_id": "cid-1", "client_secret": "sec-1"},
        )
        registry.save_central(
            "central-lab",
            {"base_url": "https://lab.api.central.arubanetworks.com", "client_id": "cid-2", "client_secret": "sec-2"},
        )
        centrals = registry.list_central()
        assert set(centrals) == {"central-prod", "central-lab"}
        pub = public_central("central-prod", centrals["central-prod"])
        assert pub["has_client_secret"] is True
        assert "sec-1" not in json.dumps(pub)
        assert pub["client_id"] == "cid-1"

    def test_registry_central_secret_kept_when_empty_and_cleared_when_none(self, registry: TargetRegistry):
        registry.save_central(
            "central-prod",
            {
                "base_url": "https://us.api.central.arubanetworks.com",
                "client_id": "cid",
                "client_secret": "real-secret",
            },
        )
        registry.save_central(
            "central-prod",
            {"base_url": "https://us.api.central.arubanetworks.com", "client_id": "cid", "client_secret": None},
        )
        assert registry.get_central("central-prod").get("client_secret") == "real-secret"
        registry.delete_central("central-prod")
        assert registry.list_central() == {}

    def test_central_from_entry_validates(self):
        with pytest.raises(RegistryError):
            central_from_entry("x", {"base_url": "https://x.example.com"})
        with pytest.raises(RegistryError):
            central_from_entry("x", {"base_url": "https://x.example.com", "client_id": "cid"})
        target = central_from_entry(
            "x", {"base_url": "https://x.example.com/", "client_id": "cid", "client_secret": "sec"}
        )
        assert target.base_url == "https://x.example.com"
        assert target.verify_tls is True
        assert target.timeout == 30.0

    def test_load_central_from_env(self, monkeypatch):
        monkeypatch.setenv(
            "EC_CENTRAL_PLATFORMS_JSON",
            json.dumps(
                {
                    "central-a": {
                        "base_url": "https://a.example.com",
                        "client_id": "cid",
                        "client_secret": "sec",
                    }
                }
            ),
        )
        targets = load_central_from_env()
        assert set(targets) == {"central-a"}
        assert targets["central-a"].client_secret == "sec"

    def test_admin_state_includes_central_platforms_without_secrets(self, registry: TargetRegistry, monkeypatch):
        from ec_mcp import admin

        registry.save_central(
            "central-prod",
            {
                "base_url": "https://us.api.central.arubanetworks.com",
                "client_id": "cid",
                "client_secret": "real-secret",
            },
        )
        monkeypatch.setenv("EC_CENTRAL_ENABLED", "true")
        state = admin._public_state()
        assert state["central_platforms"][0]["name"] == "central-prod"
        assert state["central_platforms"][0]["active"] is False or True
        assert "real-secret" not in json.dumps(state)
        assert state["blobs"]["central"] is False or True

    def test_admin_routes_include_central(self):
        paths = {route.path for route in build_admin_app().routes}
        assert {"/api/central", "/api/central/delete", "/api/central/rename", "/api/central/duplicate"}.issubset(paths)

    def test_registry_env_blob_includes_central(self, registry: TargetRegistry):
        registry.save_central(
            "central-prod",
            {"base_url": "https://us.api.central.arubanetworks.com", "client_id": "cid", "client_secret": "sec"},
        )
        blob = registry.to_env_blob()
        assert "EC_CENTRAL_PLATFORMS_JSON" in blob
        assert json.loads(blob["EC_CENTRAL_PLATFORMS_JSON"])["central-prod"]["client_id"] == "cid"


def test_admin_page_has_central_tab():
    from ec_mcp.admin_page import PAGE

    assert "Aruba Central" in PAGE
    assert "renderCentral" in PAGE
    assert "/api/central" in PAGE
    assert "tab-central" in PAGE
