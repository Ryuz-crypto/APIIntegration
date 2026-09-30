from __future__ import annotations

import re

from .security import SecurityError, redact_secrets, sanitize_output, validate_show_command

try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None

FORBIDDEN_CHARS = re.compile(r"[;&`]|\|\||&&|\$\(")


class ApplianceSession:
    def __init__(self, host: str, username: str, password: str, port: int = 22, max_output_chars: int = 12000):
        if ConnectHandler is None:
            raise RuntimeError("netmiko is not installed; SSH tools are unavailable")
        self._connection = ConnectHandler(
            device_type="linux_ssh",
            host=host,
            username=username,
            password=password,
            port=port,
        )
        self._max_output_chars = max_output_chars

    def run_show(self, command: str) -> str:
        validated = validate_show_command(command)
        raw = self._connection.send_command_timing(validated, read_timeout=30)
        return redact_secrets(sanitize_output(raw, self._max_output_chars), [])

    def run_raw(self, command: str) -> str:
        normalized = command.strip()
        if not normalized:
            raise SecurityError("Empty command")
        if FORBIDDEN_CHARS.search(normalized):
            raise SecurityError("Command contains forbidden characters")
        if re.search(r"[\x00-\x1f\x7f]|[^\x00-\x7f]", normalized):
            raise SecurityError("Command contains forbidden characters")
        raw = self._connection.send_command_timing(normalized, read_timeout=60)
        return redact_secrets(sanitize_output(raw, self._max_output_chars), [])

    def close(self) -> None:
        self._connection.disconnect()


class ApplianceSshPool:
    def __init__(self, settings):
        self._settings = settings
        self._sessions: dict[str, ApplianceSession] = {}

    def get(self, host: str | None = None) -> ApplianceSession:
        target = host or self._settings.ssh_host
        if not target:
            raise SecurityError("No appliance host configured for SSH (EC_SSH_HOST)")
        if target not in self._sessions:
            if not self._settings.ssh_enabled:
                raise SecurityError("SSH tools are disabled (EC_SSH_ENABLED != true)")
            self._sessions[target] = ApplianceSession(
                host=target,
                username=self._settings.ssh_username,
                password=self._settings.ssh_password,
                port=self._settings.ssh_port,
                max_output_chars=self._settings.max_output_chars,
            )
        return self._sessions[target]

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
