"""Automatic backup failure must not be reported as success."""
import pytest

import ec_mcp.admin as admin


def test_automatic_backup_surfaces_filesystem_error(tmp_path, monkeypatch):
    parent = tmp_path / "not-a-directory"
    parent.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(admin, "_backup_dir", lambda: parent / "backups")
    with pytest.raises(OSError):
        admin._snapshot_backup("manual")
