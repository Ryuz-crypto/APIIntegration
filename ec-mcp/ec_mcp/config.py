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
    ssh_port: int = 22

    allow_write_tools: bool = False
    allow_dangerous_writes: bool = False
    max_output_chars: int = 12000
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
            ssh_port=int(os.environ.get("EC_SSH_PORT", "22")),
            allow_write_tools=os.environ.get("EC_ALLOW_WRITE_TOOLS", "false").lower() == "true",
            allow_dangerous_writes=os.environ.get("EC_ALLOW_DANGEROUS_WRITES", "false").lower() == "true",
            max_writes_per_minute=int(os.environ.get("EC_MAX_WRITES_PER_MINUTE", "10")),
            max_output_chars=int(os.environ.get("EC_MAX_OUTPUT_CHARS", "12000")),
            audit_log_path=Path(audit_path) if audit_path else Path("logs/mcp-audit.jsonl"),
            profiles_dir=Path(profiles_dir) if profiles_dir else Path(__file__).parent / "profiles",
        )
