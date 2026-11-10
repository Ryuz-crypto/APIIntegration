"""Audit-readiness tests: bounded digests, permissions and retention."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

import ec_mcp.admin as admin
import ec_mcp.audit_evidence as evidence
from ec_mcp.audit import AuditLog


def test_audit_events_have_unique_ids(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    first = log.record("tool", "read", "target", "ok")
    second = log.record("tool", "read", "target", "ok")
    assert first["schema"] == "ec-mcp.audit.v1"
    assert first["event_id"] != second["event_id"]


def test_digest_is_bounded_and_explicitly_unsigned(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    path.write_bytes(b"test\n")
    snap = evidence.audit_snapshot(path)
    assert snap["sha256"] == hashlib.sha256(b"test\n").hexdigest()
    assert snap["bytes"] == 5
    assert snap["signed"] is False
    assert snap["non_repudiation_established"] is False
    path.write_bytes(b"modified\n")
    assert evidence.audit_snapshot(path)["sha256"] != snap["sha256"]
    monkeypatch.setattr(evidence, "MAX_SNAPSHOT_BYTES", 2)
    with pytest.raises(ValueError):
        evidence.audit_snapshot(path)


def test_clear_keeps_active_and_rotated_audit(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    path.write_bytes(b"active\n")
    rotated = tmp_path / "audit.jsonl.1"
    rotated.write_bytes(b"rotated\n")
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "op", "role": "operator"})
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin.Settings, "from_env", lambda: SimpleNamespace(audit_log_path=path))
    with TestClient(admin.build_admin_app()) as client:
        response = client.post("/api/debug/clear", json={})
    assert response.status_code == 200
    assert path.read_bytes() == b"active\n"
    assert rotated.read_bytes() == b"rotated\n"


def test_snapshot_requires_admin(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    path.write_bytes(b"test\n")
    monkeypatch.setattr(admin.Settings, "from_env", lambda: SimpleNamespace(audit_log_path=path))
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "v", "role": "viewer"})
    with TestClient(admin.build_admin_app()) as client:
        assert client.post("/api/audit/snapshot", json={}).status_code == 403
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "a", "role": "admin"})
    with TestClient(admin.build_admin_app()) as client:
        response = client.post("/api/audit/snapshot", json={})
    assert response.status_code == 200
    assert response.json()["snapshot"]["sha256"] == hashlib.sha256(b"test\n").hexdigest()
