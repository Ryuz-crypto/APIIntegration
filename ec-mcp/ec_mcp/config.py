from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    orchestrator_url: str = ""
    orchestrator_api_key: str = ""
    orchestrator_username: str = ""
    orchestrator_password: str = ""
    verify_tls: bool = True

    ssh_enabled: bool = False
    ssh_host: str = ""
    ssh_username: str = ""
    ssh_password: str = ""
    ssh_enable_password: str = ""
    ssh_port: int = 22
    ssh_auth_method: str = "auto"
    ssh_connect_timeout: int = 30
    ssh_command_timeout: int = 30
    ssh_retries: int = 1

    axis_enabled: bool = False
    axis_admin_token: str = ""
    axis_base_url: str = "https://admin-api.axissecurity.com"
    axis_verify_tls: bool = True
    axis_timeout: float = 30.0

    orchestrators_json: str = ""
    sse_platforms_json: str = ""

    dashboard_remote_enabled: bool = False
    dashboard_remote_host: str = ""
    dashboard_remote_user: str = ""
    dashboard_remote_password: str = ""
    dashboard_remote_port: int = 22
    dashboard_remote_key_path: str = ""
    dashboard_port: int = 8090
    dashboard_dir: str = "/var/www/ec-mcp-dashboard"
    dashboard_refresh_seconds: int = 30

    allow_write_tools: bool = False
    allow_dangerous_writes: bool = False
    max_output_chars: int = 12000
    api_cache_ttl: float = 30.0
    max_writes_per_minute: int = 10

    audit_log_path: Path = field(default_factory=lambda: Path("logs/mcp-audit.jsonl"))

    profiles_dir: Path = field(default_factory=lambda: Path(__file__).parent / "profiles")

    @classmethod
    def from_env(cls) -> Settings:
        profiles_dir = os.environ.get("EC_MCP_PROFILES_DIR")
        audit_path = os.environ.get("EC_MCP_AUDIT_LOG")
        return cls(
            orchestrator_url=os.environ.get("EC_ORCHESTRATOR_URL", "").rstrip("/"),
            orchestrator_api_key=os.environ.get("EC_ORCHESTRATOR_API_KEY", ""),
            orchestrator_username=os.environ.get("EC_ORCHESTRATOR_USER", ""),
            orchestrator_password=os.environ.get("EC_ORCHESTRATOR_PASSWORD", ""),
            verify_tls=os.environ.get("EC_VERIFY_TLS", "true").lower() != "false",
            ssh_enabled=os.environ.get("EC_SSH_ENABLED", "false").lower() == "true",
            ssh_host=os.environ.get("EC_SSH_HOST", ""),
            ssh_username=os.environ.get("EC_SSH_USER", ""),
            ssh_password=os.environ.get("EC_SSH_PASSWORD", ""),
            ssh_enable_password=os.environ.get("EC_SSH_ENABLE_PASSWORD", ""),
            ssh_port=int(os.environ.get("EC_SSH_PORT", "22")),
            ssh_auth_method=os.environ.get("EC_SSH_AUTH_METHOD", "auto").strip().lower(),
            ssh_connect_timeout=int(os.environ.get("EC_SSH_CONNECT_TIMEOUT", "30")),
            ssh_command_timeout=int(os.environ.get("EC_SSH_COMMAND_TIMEOUT", "30")),
            ssh_retries=max(0, int(os.environ.get("EC_SSH_RETRIES", "1"))),
            axis_enabled=os.environ.get("EC_AXIS_ENABLED", "false").lower() == "true",
            axis_admin_token=os.environ.get("EC_AXIS_ADMIN_TOKEN", ""),
            axis_base_url=os.environ.get("EC_AXIS_BASE_URL", "https://admin-api.axissecurity.com"),
            axis_verify_tls=os.environ.get("EC_AXIS_VERIFY_TLS", "true").lower() != "false",
            axis_timeout=float(os.environ.get("EC_AXIS_TIMEOUT", "30")),
            orchestrators_json=os.environ.get("EC_ORCHESTRATORS_JSON", ""),
            sse_platforms_json=os.environ.get("EC_SSE_PLATFORMS_JSON", ""),
            dashboard_remote_enabled=os.environ.get("EC_DASHBOARD_REMOTE_ENABLED", "false").lower() == "true",
            dashboard_remote_host=os.environ.get("EC_DASHBOARD_REMOTE_HOST", ""),
            dashboard_remote_user=os.environ.get("EC_DASHBOARD_REMOTE_USER", ""),
            dashboard_remote_password=os.environ.get("EC_DASHBOARD_REMOTE_PASSWORD", ""),
            dashboard_remote_port=int(os.environ.get("EC_DASHBOARD_REMOTE_PORT", "22")),
            dashboard_remote_key_path=os.environ.get("EC_DASHBOARD_REMOTE_KEY_PATH", ""),
            dashboard_port=int(os.environ.get("EC_DASHBOARD_PORT", "8090")),
            dashboard_dir=os.environ.get("EC_DASHBOARD_DIR", "/var/www/ec-mcp-dashboard"),
            dashboard_refresh_seconds=int(os.environ.get("EC_DASHBOARD_REFRESH_SECONDS", "30")),
            allow_write_tools=os.environ.get("EC_ALLOW_WRITE_TOOLS", "false").lower() == "true",
            allow_dangerous_writes=os.environ.get("EC_ALLOW_DANGEROUS_WRITES", "false").lower() == "true",
            max_writes_per_minute=int(os.environ.get("EC_MAX_WRITES_PER_MINUTE", "10")),
            max_output_chars=int(os.environ.get("EC_MAX_OUTPUT_CHARS", "12000")),
            api_cache_ttl=float(os.environ.get("EC_API_CACHE_TTL", "30")),
            audit_log_path=Path(audit_path) if audit_path else Path("logs/mcp-audit.jsonl"),
            profiles_dir=Path(profiles_dir) if profiles_dir else Path(__file__).parent / "profiles",
        )
