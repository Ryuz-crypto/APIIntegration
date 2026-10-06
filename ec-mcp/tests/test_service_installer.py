from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("override, expected", [(None, "9123"), ("9345", "9345")])
def test_service_reinstall_preserves_bind_and_port(monkeypatch, tmp_path, override, expected):
    project = tmp_path / "ec-mcp"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    source = Path(__file__).parents[1] / "scripts" / "install_service.sh"
    shutil.copy2(source, scripts / source.name)
    environment = "EC_MCP_HOST=127.0.0.1\nEC_MCP_PORT=9123\n"
    (project / ".env").write_text(environment)
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    capture = tmp_path / "service.unit"
    commands = {
        "sudo": '#!/bin/bash\nif [ "$1" = tee ]; then cat > "$CAPTURE_UNIT"; fi\n',
        "systemctl": "#!/bin/bash\nexit 0\n",
        "sleep": "#!/bin/bash\nexit 0\n",
    }
    for name, content in commands.items():
        command = mock_bin / name
        command.write_text(content)
        command.chmod(0o755)
    monkeypatch.setenv("PATH", f"{mock_bin}:{os.environ['PATH']}")
    monkeypatch.setenv("CAPTURE_UNIT", str(capture))
    monkeypatch.delenv("EC_MCP_PORT", raising=False)
    monkeypatch.delenv("EC_MCP_HOST", raising=False)
    command = ["/bin/bash", str(scripts / source.name)]
    if override:
        command += ["--port", override]
    subprocess.run(command, check=True, capture_output=True, timeout=10)  # noqa: S603
    assert f"--host 127.0.0.1 --port {expected}" in capture.read_text()
    assert (project / ".env").read_text() == environment
