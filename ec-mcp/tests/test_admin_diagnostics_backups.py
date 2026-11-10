"""Safe backup deletion and bounded administrator diagnostics."""
from starlette.testclient import TestClient

import ec_mcp.admin as admin


def test_delete_backup_rejects_traversal_and_symlinks(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "good").mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(admin, "_backup_dir", lambda: root)
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "admin", "role": "admin"})
    with TestClient(admin.build_admin_app()) as client:
        for name in ("../outside", "/tmp", "link", "..", "a\\\\b"):
            assert client.post("/api/backups/delete", json={"name": name}).status_code == 400
        assert client.post("/api/backups/delete", json={"name": "good"}).json()["ok"]
    assert outside.is_dir()
    assert not (root / "good").exists()


def test_admin_only_diagnostics_and_delete(monkeypatch):
    monkeypatch.setattr(admin, "_audit_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "viewer", "role": "viewer"})
    with TestClient(admin.build_admin_app()) as client:
        assert client.post("/api/diagnostics/run", json={"command": "uptime"}).status_code == 403
        assert client.post("/api/backups/delete", json={"name": "x"}).status_code == 403
    monkeypatch.setattr(admin, "_check_session", lambda request: {"user": "admin", "role": "admin"})
    with TestClient(admin.build_admin_app()) as client:
        for command in ("id; touch /tmp/no", [], "../uptime"):
            assert client.post("/api/diagnostics/run", json={"command": command}).status_code == 400
        response = client.post("/api/diagnostics/run", json={"command": "uptime"})
        assert response.status_code == 200
        assert b"[Fin:" in response.content
