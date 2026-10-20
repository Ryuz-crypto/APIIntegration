"""Remote dashboard deployment over SSH (Ubuntu target).

The MCP generates a self-contained HTML dashboard locally (dashboard.py)
and pushes it to a remote Ubuntu server over SSH/SFTP (paramiko). On the
remote side a small idempotent install script provisions nginx and serves
the dashboard directory, so the dashboard stays up and stable without any
Python runtime on the target.

Typical flow:
    deployer = RemoteDashboardDeployer(host=..., user=..., password=...)
    deployer.install()                 # apt-get nginx + site config (idempotent)
    deployer.deploy(html_bytes)        # SFTP upload index.html
    deployer.status()                  # verify nginx + file present
    deployer.close()

Script builders (build_nginx_site, build_install_script) are pure and
unit-tested without SSH.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ec_mcp.dashboard_install")

try:
    import paramiko
except ImportError:  # pragma: no cover - paramiko is a hard dependency in requirements
    paramiko = None  # type: ignore[assignment]

DEFAULT_DASHBOARD_DIR = "/var/www/ec-mcp-dashboard"
DEFAULT_DASHBOARD_PORT = 8090
DEFAULT_DASHBOARD_FILE = "index.html"


class DashboardDeployError(RuntimeError):
    """Raised when the remote dashboard deployment fails."""


def _validate_remote_path(label: str, value: str) -> None:
    """Reject shell-hostile remote paths (they are interpolated into sudo commands)."""
    if not value or not value.startswith("/"):
        raise ValueError(f"{label} must be an absolute path")
    if any(ch in value for ch in (";", "&", "|", "$", "`", "\n", "\r", "'", '"', " ", "\t")):
        raise ValueError(f"{label} contains characters not allowed in a remote path")


def build_nginx_site(port: int = DEFAULT_DASHBOARD_PORT, directory: str = DEFAULT_DASHBOARD_DIR) -> str:
    """nginx site config serving the dashboard directory."""
    if not (1 <= int(port) <= 65535):
        raise ValueError("port must be 1-65535")
    return f"""server {{
    listen {int(port)} default_server;
    listen [::]:{int(port)} default_server;
    server_name _;
    root {directory};
    index index.html;
    location / {{
        try_files $uri $uri/ =404;
    }}
}}
"""


def build_install_script(
    port: int = DEFAULT_DASHBOARD_PORT,
    directory: str = DEFAULT_DASHBOARD_DIR,
) -> str:
    """Idempotent bash script that installs nginx and serves the dashboard dir."""
    if not (1 <= int(port) <= 65535):
        raise ValueError("port must be 1-65535")
    nginx_site = build_nginx_site(port, directory)
    return f"""#!/bin/bash
set -euo pipefail
DASH_DIR="{directory}"
DASH_PORT="{int(port)}"
echo "[ec-mcp-dashboard] instalando en $DASH_DIR (puerto $DASH_PORT)"
if ! command -v nginx >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx
fi
sudo mkdir -p "$DASH_DIR"
sudo tee /etc/nginx/sites-available/ec-mcp-dashboard >/dev/null <<'NGINX_EOF'
{nginx_site}NGINX_EOF
sudo ln -sf /etc/nginx/sites-available/ec-mcp-dashboard /etc/nginx/sites-enabled/ec-mcp-dashboard
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl enable --now nginx
sudo systemctl reload nginx
echo "[ec-mcp-dashboard] listo: http://$(hostname -I | awk '{{print $1}}'):$DASH_PORT/"
"""


def build_refresh_cron(mcp_bin: str = "ec-mcp", schedule: str = "*/5 * * * *") -> str:
    """Example cron line (for the LOCAL host) that regenerates and re-uploads
    the dashboard every N minutes."""
    return f"{schedule} {mcp_bin} dashboard refresh-remote >> /var/log/ec-mcp-dashboard-refresh.log 2>&1"


@dataclass
class DeployResult:
    ok: bool
    action: str
    detail: str = ""
    url: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)


class RemoteDashboardDeployer:
    """SSH/SFTP deployer for the dashboard on an Ubuntu host."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str | None = None,
        *,
        port: int = 22,
        key_path: str = "",
        dashboard_port: int = DEFAULT_DASHBOARD_PORT,
        dashboard_dir: str = DEFAULT_DASHBOARD_DIR,
        timeout: float = 30.0,
        host_key_policy: str = "auto_add",
        client: Any = None,
    ):
        if not host:
            raise ValueError("host is required")
        if not user:
            raise ValueError("user is required")
        if not password and not key_path:
            raise ValueError("password or key_path is required")
        if host_key_policy not in ("auto_add", "reject"):
            raise ValueError("host_key_policy must be 'auto_add' or 'reject'")
        _validate_remote_path("dashboard_dir", dashboard_dir)
        if not (1 <= int(dashboard_port) <= 65535):
            raise ValueError("dashboard_port must be 1-65535")
        self.host = host
        self.user = user
        self.password = password or ""
        self.port = port
        self.key_path = key_path
        self.dashboard_port = dashboard_port
        self.dashboard_dir = dashboard_dir
        self.timeout = timeout
        self.host_key_policy = host_key_policy
        self._client = client
        self._sftp: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if paramiko is None:
            raise DashboardDeployError("paramiko is not installed; cannot deploy over SSH")
        client = paramiko.SSHClient()
        if self.host_key_policy == "reject":
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            # First-contact to a lab/ops server: trust on first use. For strict
            # environments pass host_key_policy="reject" and pre-seed known_hosts.
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507 - trust-on-first-use for ops hosts; use host_key_policy="reject" for strict envs
        kwargs: dict[str, Any] = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user,
            "timeout": self.timeout,
            "banner_timeout": self.timeout,
            "auth_timeout": self.timeout,
        }
        if self.key_path:
            kwargs["key_filename"] = self.key_path
        if self.password:
            kwargs["password"] = self.password
            kwargs["look_for_keys"] = False
            kwargs["allow_agent"] = False
        client.connect(**kwargs)
        self._client = client
        return client

    def run(self, command: str, timeout: float = 120.0) -> tuple[int, str, str]:
        """Execute a command; returns (exit_code, stdout, stderr)."""
        client = self._ensure_client()
        # Commands are built internally from validated constants/paths; never raw user input.
        _, stdout, stderr = client.exec_command(command, timeout=timeout)  # nosec B601
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err

    def _ensure_sftp(self) -> Any:
        if self._sftp is None:
            self._sftp = self._ensure_client().open_sftp()
        return self._sftp

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        """Upload bytes to a remote path via SFTP (creates parent dirs with sudo)."""
        sftp = self._ensure_sftp()
        directory = remote_path.rsplit("/", 1)[0] if "/" in remote_path else "."
        filename = remote_path.rsplit("/", 1)[-1]
        # Unique temp name avoids collisions; filename comes from a fixed
        # constant (DEFAULT_DASHBOARD_FILE) or the caller, never user input.
        tmp_path = f"/tmp/.ec-mcp-{filename}-{secrets.token_hex(6)}.upload"  # nosec B108 - randomized SFTP staging file
        with sftp.file(tmp_path, "wb") as remote_file:
            remote_file.write(data)
        code, _, err = self.run(
            f"sudo mkdir -p {directory} && sudo mv {tmp_path} {remote_path} && sudo chmod 644 {remote_path}"
        )
        if code != 0:
            raise DashboardDeployError(f"upload failed for {remote_path}: {err.strip()[:300]}")

    def install(self) -> DeployResult:
        """Run the idempotent install script (nginx + site config)."""
        script = build_install_script(self.dashboard_port, self.dashboard_dir)
        code, out, err = self.run(f"bash -s <<'EC_MCP_DASHBOARD_EOF'\n{script}EC_MCP_DASHBOARD_EOF", timeout=600.0)
        ok = code == 0
        return DeployResult(
            ok=ok,
            action="install",
            detail=(out + err).strip()[-2000:],
            url=self.url(),
            steps=[{"step": "install_script", "exit_code": code, "output_tail": (out + err).strip()[-500:]}],
        )

    def deploy(self, html_bytes: bytes, filename: str = DEFAULT_DASHBOARD_FILE) -> DeployResult:
        """Upload the dashboard HTML to the remote directory."""
        if not html_bytes:
            raise ValueError("html_bytes is empty")
        remote_path = f"{self.dashboard_dir.rstrip('/')}/{filename}"
        self.upload_bytes(html_bytes, remote_path)
        return DeployResult(
            ok=True,
            action="deploy",
            detail=f"subido {len(html_bytes)} bytes a {remote_path}",
            url=self.url(),
            steps=[{"step": "sftp_upload", "remote_path": remote_path, "bytes": len(html_bytes)}],
        )

    def install_and_deploy(self, html_bytes: bytes, filename: str = DEFAULT_DASHBOARD_FILE) -> DeployResult:
        install_result = self.install()
        if not install_result.ok:
            return DeployResult(
                ok=False,
                action="install_and_deploy",
                detail=f"install failed: {install_result.detail}",
                steps=install_result.steps,
            )
        deploy_result = self.deploy(html_bytes, filename)
        return DeployResult(
            ok=deploy_result.ok,
            action="install_and_deploy",
            detail=deploy_result.detail,
            url=deploy_result.url,
            steps=install_result.steps + deploy_result.steps,
        )

    def status(self) -> DeployResult:
        """Check nginx is active and the dashboard file exists on the remote."""
        code, out, _err = self.run(
            "systemctl is-active nginx; "
            f"test -f {self.dashboard_dir}/{DEFAULT_DASHBOARD_FILE} && echo FILE_PRESENT || echo FILE_MISSING; "
            f"ss -ltnp 2>/dev/null | grep ':{self.dashboard_port} ' || true"
        )
        output = out.strip()
        ok = code == 0 and "active" in output and "FILE_PRESENT" in output
        return DeployResult(
            ok=ok,
            action="status",
            detail=output,
            url=self.url(),
            steps=[{"step": "status", "exit_code": code, "output": output}],
        )

    def url(self) -> str:
        return f"http://{self.host}:{self.dashboard_port}/"

    def close(self) -> None:
        if self._sftp is not None:
            try:
                self._sftp.close()
            except Exception as error:  # nosec B110 - best-effort cleanup
                logger.debug("sftp close failed: %s", error)
            self._sftp = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception as error:  # nosec B110 - best-effort cleanup
                logger.debug("ssh client close failed: %s", error)
            self._client = None

    def __enter__(self) -> RemoteDashboardDeployer:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
