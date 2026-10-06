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
