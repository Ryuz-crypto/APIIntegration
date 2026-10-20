"""Tests for the remote dashboard installer (script builders + SSH deployer with a fake client)."""

from __future__ import annotations

import pytest

from ec_mcp.dashboard_install import (
    DashboardDeployError,
    RemoteDashboardDeployer,
    build_install_script,
    build_nginx_site,
    build_refresh_cron,
)


class TestScriptBuilders:
    def test_nginx_site(self):
        site = build_nginx_site(port=8090, directory="/var/www/ec-mcp-dashboard")
        assert "listen 8090" in site
        assert "root /var/www/ec-mcp-dashboard" in site
        assert "index index.html" in site

    def test_nginx_site_rejects_bad_port(self):
        with pytest.raises(ValueError):
            build_nginx_site(port=0)
        with pytest.raises(ValueError):
            build_nginx_site(port=70000)

    def test_install_script_is_idempotent_and_uses_sudo(self):
        script = build_install_script(port=8090, directory="/var/www/ec-mcp-dashboard")
        assert "set -euo pipefail" in script
        assert "apt-get install -y -qq nginx" in script
        assert "sudo mkdir -p" in script
        assert "systemctl enable --now nginx" in script
        assert "systemctl reload nginx" in script
        assert "listen 8090" in script

    def test_refresh_cron(self):
        line = build_refresh_cron(mcp_bin="ec-mcp", schedule="*/5 * * * *")
        assert line.startswith("*/5 * * * * ec-mcp")
        assert "dashboard refresh-remote" in line


class _FakeChannel:
    def __init__(self, code: int = 0):
        self._code = code

    def recv_exit_status(self):
        return self._code


class _FakeStream:
    def __init__(self, data: bytes, code: int = 0):
        self._data = data
        self.channel = _FakeChannel(code)

    def read(self):
        return self._data


class _FakeSFTPFile:
    def __init__(self, sink: list):
        self._sink = sink

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, data: bytes):
        self._sink.append(data)


class _FakeSFTP:
    def __init__(self, sink: list):
        self._sink = sink
        self.closed = False

    def file(self, path, mode):
        assert mode == "wb"
        return _FakeSFTPFile(self._sink)

    def close(self):
        self.closed = True


class _FakeSSHClient:
    def __init__(self, responses: dict[str, tuple[int, str, str]], sink: list):
        self._responses = responses
        self._sink = sink
        self.commands: list[str] = []
        self.closed = False

    def exec_command(self, command, timeout=None):
        self.commands.append(command)
        for key, response in self._responses.items():
            if key in command:
                code, out, err = response
                return None, _FakeStream(out.encode(), code), _FakeStream(err.encode(), code)
        return None, _FakeStream(b"", 0), _FakeStream(b"", 0)

    def open_sftp(self):
        return _FakeSFTP(self._sink)

    def close(self):
        self.closed = True


def _make_deployer(responses=None, sink=None):
    sink = sink if sink is not None else []
    responses = responses or {}
    client = _FakeSSHClient(responses, sink)
    deployer = RemoteDashboardDeployer(
        host="10.0.0.5",
        user="ubuntu",
        password="secret",  # noqa: S106 - test fixture
        dashboard_port=8090,
        client=client,
    )
    return deployer, client, sink


class TestDeployerValidation:
    def test_requires_host(self):
        with pytest.raises(ValueError):
            RemoteDashboardDeployer(host="", user="u", password="p")  # noqa: S106 - test fixture

    def test_requires_user(self):
        with pytest.raises(ValueError):
            RemoteDashboardDeployer(host="h", user="", password="p")  # noqa: S106 - test fixture

    def test_requires_credentials(self):
        with pytest.raises(ValueError):
            RemoteDashboardDeployer(host="h", user="u")

    def test_rejects_bad_host_key_policy(self):
        with pytest.raises(ValueError, match="host_key_policy"):
            RemoteDashboardDeployer(host="h", user="u", password="p", host_key_policy="bogus")  # noqa: S106

    def test_rejects_relative_dashboard_dir(self):
        with pytest.raises(ValueError, match="absolute path"):
            RemoteDashboardDeployer(host="h", user="u", password="p", dashboard_dir="relative/path")  # noqa: S106

    def test_rejects_shell_hostile_dashboard_dir(self):
        with pytest.raises(ValueError, match="not allowed"):
            RemoteDashboardDeployer(host="h", user="u", password="p", dashboard_dir="/var/www/x; rm -rf /")  # noqa: S106

    def test_rejects_bad_dashboard_port(self):
        with pytest.raises(ValueError, match="dashboard_port"):
            RemoteDashboardDeployer(host="h", user="u", password="p", dashboard_port=0)  # noqa: S106

    def test_accepts_valid_config(self):
        deployer = RemoteDashboardDeployer(
            host="h", user="u", password="p",  # noqa: S106 - test fixture
            dashboard_dir="/var/www/ok", dashboard_port=8090,
        )
        assert deployer.dashboard_dir == "/var/www/ok"
        assert deployer.dashboard_port == 8090
        assert deployer.host_key_policy == "auto_add"

    def test_url(self):
        deployer, _, _ = _make_deployer()
        assert deployer.url() == "http://10.0.0.5:8090/"


class TestDeployerActions:
    def test_install_success(self):
        deployer, client, _ = _make_deployer(
            responses={"bash -s": (0, "[ec-mcp-dashboard] listo: http://10.0.0.5:8090/", "")}
        )
        result = deployer.install()
        assert result.ok is True
        assert result.url == "http://10.0.0.5:8090/"
        assert any("apt-get install" in c for c in client.commands)

    def test_install_failure(self):
        deployer, _, _ = _make_deployer(responses={"bash -s": (1, "", "apt failed")})
        result = deployer.install()
        assert result.ok is False
        assert "apt failed" in result.detail

    def test_deploy_uploads_bytes(self):
        deployer, client, sink = _make_deployer(
            responses={"sudo mkdir -p": (0, "", "")}
        )
        result = deployer.deploy(b"<html>dashboard</html>")
        assert result.ok is True
        assert sink == [b"<html>dashboard</html>"]
        assert any("sudo mv" in c for c in client.commands)
        assert any("/var/www/ec-mcp-dashboard/index.html" in c for c in client.commands)

    def test_deploy_rejects_empty(self):
        deployer, _, _ = _make_deployer()
        with pytest.raises(ValueError):
            deployer.deploy(b"")

    def test_deploy_upload_failure_raises(self):
        deployer, _, _ = _make_deployer(responses={"sudo mkdir -p": (1, "", "permission denied")})
        with pytest.raises(DashboardDeployError):
            deployer.deploy(b"data")

    def test_status_ok(self):
        output = "active\nFILE_PRESENT\nLISTEN 0 511 0.0.0.0:8090"
        deployer, _, _ = _make_deployer(
            responses={"systemctl is-active nginx": (0, output, "")}
        )
        result = deployer.status()
        assert result.ok is True
        assert result.url == "http://10.0.0.5:8090/"

    def test_status_missing_file(self):
        output = "active\nFILE_MISSING\n"
        deployer, _, _ = _make_deployer(
            responses={"systemctl is-active nginx": (0, output, "")}
        )
        result = deployer.status()
        assert result.ok is False

    def test_install_and_deploy(self):
        deployer, _client, sink = _make_deployer(
            responses={
                "bash -s": (0, "listo", ""),
                "sudo mkdir -p": (0, "", ""),
            }
        )
        result = deployer.install_and_deploy(b"<html>x</html>")
        assert result.ok is True
        assert result.action == "install_and_deploy"
        assert sink == [b"<html>x</html>"]
        assert len(result.steps) == 2

    def test_install_and_deploy_install_failure(self):
        deployer, _, sink = _make_deployer(responses={"bash -s": (1, "", "boom")})
        result = deployer.install_and_deploy(b"<html>x</html>")
        assert result.ok is False
        assert sink == []

    def test_context_manager_closes(self):
        deployer, client, _ = _make_deployer()
        with deployer:
            pass
        assert client.closed is True
