from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("has_lock", [False, True])
def test_worker_installs_checkout_dependencies_including_legacy_rollback(monkeypatch, tmp_path, has_lock):
    source = Path(__file__).parents[1] / "scripts" / "apply-web-update.py"
    spec = importlib.util.spec_from_file_location("update_worker", source)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    commands = []
    monkeypatch.setattr(worker, "run_user", lambda command, owner, **kwargs: commands.append((command, owner)))
    lock = tmp_path / "requirements-stable.txt"
    if has_lock:
        lock.write_text("httpx==0.28.1\n")
    python = tmp_path / ".venv" / "bin" / "python"
    worker.install_package(tmp_path, python, "operator")
    expected = [str(python), "-m", "pip", "install"]
    if has_lock:
        expected += ["-r", str(lock)]
    expected += ["-e", str(tmp_path)]
    assert commands == [(expected, "operator")]


def _load_worker():
    source = Path(__file__).parents[1] / "scripts" / "apply-web-update.py"
    spec = importlib.util.spec_from_file_location("update_worker", source)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


class TestEnsureWritableGitDir:
    def test_noop_when_git_dir_missing(self, tmp_path):
        worker = _load_worker()
        worker._ensure_writable_git_dir(tmp_path, "someone")  # no .git -> no-op

    def test_noop_when_already_writable(self, tmp_path, monkeypatch):
        worker = _load_worker()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.setattr(worker.os, "access", lambda path, mode: True)
        called = []
        monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: called.append(a))
        worker._ensure_writable_git_dir(tmp_path, "someone")
        assert called == []

    def test_chowns_when_not_writable_and_root(self, tmp_path, monkeypatch):
        worker = _load_worker()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        # Simular: .git no escribible, corremos como root, chown OK, queda escribible
        access_calls = {"n": 0}

        def fake_access(path, mode):
            access_calls["n"] += 1
            return access_calls["n"] > 1  # primera False (no escribible), luego True

        monkeypatch.setattr(worker.os, "access", fake_access)
        monkeypatch.setattr(worker.os, "geteuid", lambda: 0)

        class Result:
            returncode = 0
            stdout = ""

        run_calls = []
        monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: run_calls.append(a) or Result())
        worker._ensure_writable_git_dir(tmp_path, "axis")
        assert run_calls, "debió llamar chown"
        chown_cmd = run_calls[0][0]
        assert chown_cmd[0] == "/usr/bin/chown"
        assert "axis:" in chown_cmd
        assert str(git_dir) in chown_cmd

    def test_raises_actionable_error_when_not_root(self, tmp_path, monkeypatch):
        worker = _load_worker()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.setattr(worker.os, "access", lambda path, mode: False)
        monkeypatch.setattr(worker.os, "geteuid", lambda: 1000)
        with pytest.raises(RuntimeError, match="chown -R"):
            worker._ensure_writable_git_dir(tmp_path, "axis")

    def test_raises_when_chown_fails(self, tmp_path, monkeypatch):
        worker = _load_worker()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.setattr(worker.os, "access", lambda path, mode: False)
        monkeypatch.setattr(worker.os, "geteuid", lambda: 0)

        class Result:
            returncode = 1
            stdout = "chown: operation not permitted"

        monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: Result())
        with pytest.raises(RuntimeError, match="No se pudo corregir el propietario"):
            worker._ensure_writable_git_dir(tmp_path, "axis")

    def test_raises_when_still_readonly_after_chown(self, tmp_path, monkeypatch):
        worker = _load_worker()
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        monkeypatch.setattr(worker.os, "access", lambda path, mode: False)  # siempre False
        monkeypatch.setattr(worker.os, "geteuid", lambda: 0)

        class Result:
            returncode = 0
            stdout = ""

        monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: Result())
        with pytest.raises(RuntimeError, match="ProtectHome=read-only"):
            worker._ensure_writable_git_dir(tmp_path, "axis")

    def test_install_update_calls_ensure_writable(self, monkeypatch, tmp_path):
        worker = _load_worker()
        project = tmp_path / "proj"
        project.mkdir()
        (project / "pyproject.toml").write_text("[project]\nname='x'\n")
        ensure_calls = []
        monkeypatch.setattr(worker, "_ensure_writable_git_dir", lambda root, owner: ensure_calls.append((str(root), owner)))
        monkeypatch.setattr(worker, "run_user", lambda command, owner, **kwargs: {
            "rev-parse --show-toplevel": str(project),
            "rev-parse HEAD": "a" * 40,
            "status --porcelain": "",
        }.get(" ".join(command[3:5]) if command[1] == "-C" else "", ""))
        monkeypatch.setattr(worker, "backup", lambda state, project, previous: tmp_path / "backup")
        monkeypatch.setattr(worker, "git_environment", lambda settings, state, uid, gid: ({}, None))
        monkeypatch.setattr(worker, "validate_request", lambda request, settings: ("Ryuz-crypto/APIIntegration", "main", "b" * 40))
        monkeypatch.setattr(worker, "install_package", lambda *a, **k: None)
        monkeypatch.setattr(worker, "restart_services", lambda settings: None)
        # detener antes del fetch real: hacer que run_user falle en fetch
        def fake_run_user(command, owner, **kwargs):
            joined = " ".join(command)
            if "rev-parse --show-toplevel" in joined:
                return str(project)
            if "rev-parse HEAD" in joined and "FETCH_HEAD" not in joined:
                return "a" * 40
            if "status --porcelain" in joined:
                return ""
            raise AssertionError(f"unexpected command: {command}")
        monkeypatch.setattr(worker, "run_user", fake_run_user)
        settings = {"EC_UPDATE_PROJECT_DIR": str(project)}
        with pytest.raises(AssertionError, match="unexpected command"):
            worker.install_update({"action": "update", "repository": "Ryuz-crypto/APIIntegration", "branch": "main", "commit": "b" * 40}, settings, tmp_path / "state")
        assert ensure_calls, "install_update debió llamar _ensure_writable_git_dir"
        assert ensure_calls[0][1]  # owner presente
