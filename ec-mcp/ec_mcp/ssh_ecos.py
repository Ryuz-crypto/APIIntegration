from __future__ import annotations

import re
import socket

from .security import SecurityError, redact_secrets, sanitize_output, validate_show_command

try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None

FORBIDDEN_CHARS = re.compile(r"[;&`]|\|\||&&|\$\(")


class ApplianceSession:
    def __init__(self, host: str, username: str, password: str, port: int = 22, max_output_chars: int = 12000,
                 enable_password: str = ""):  # nosec B107
        if ConnectHandler is None:
            raise RuntimeError("netmiko is not installed; SSH tools are unavailable")
        self._connection = ConnectHandler(
            device_type="linux_ssh",
            host=host,
            username=username,
            password=password,
            port=port,
        )
        if enable_password:
            enable_result = self._connection.send_command_timing("enable", read_timeout=10)
            if re.search(r"(?i)password", enable_result or ""):
                self._connection.send_command_timing(enable_password, read_timeout=10)
            else:
                self._connection.write(enable_password)
                self._connection.send_command_timing("", read_timeout=10)
            probe = self._connection.send_command_timing("show version", read_timeout=15)
            probe_text = probe or ""
            failed = (
                not probe_text.strip()
                or re.search(r"(?i)permission denied|not authorized|access denied|bad secrets|invalid password", probe_text)
            )
            if failed:
                raise RuntimeError(
                    "Could not enter privileged (enable) mode on the appliance. Verify "
                    "EC_SSH_ENABLE_PASSWORD and the user's permissions. Last output: "
                    f"{probe_text[-500:]!r}"
                )
        self._max_output_chars = max_output_chars

    def run_show(self, command: str) -> str:
        validated = validate_show_command(command)
        self._connection.send_command_timing("page off", read_timeout=10)
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


def resolve_appliance_address(
    target: str,
    settings,
    inventory: list[dict] | None = None,
) -> str:
    """Resolve an appliance reference (nePk, name, IP or serial) to a reachable IP.

    If the reference looks like a host/IP it is used directly; otherwise the
    Orchestrator inventory is consulted (name, nePk, serial, IP, LAN/WAN fields).
    """
    candidate = target.strip()
    if not candidate:
        raise SecurityError("No appliance host given for SSH")
    try:
        socket.getaddrinfo(candidate, None)
        return candidate
    except socket.gaierror:
        pass
    if inventory is None:
        from .compat import CompatibilityEngine, load_profiles
        from .orchestrator_client import OrchestratorClient

        try:
            engine = CompatibilityEngine(load_profiles(settings.profiles_dir))
            client = OrchestratorClient(settings, engine)
            inventory = client.list_appliances()
        except Exception as error:
            raise SecurityError(
                f"Could not resolve appliance '{target}': Orchestrator inventory "
                f"unavailable ({error}). Pass an IP or FQDN instead."
            ) from error
    lowered = candidate.lower()
    address_fields = (
        "ip",
        "lan_ip",
        "wan_ips",
    )
    for appliance in inventory:
        identifiers = {
            str(appliance.get("nePk") or "").lower(),
            str(appliance.get("name") or "").lower(),
            str(appliance.get("serial_number") or "").lower(),
        }
        if lowered in identifiers:
            for field_name in address_fields:
                value = appliance.get(field_name)
                if value:
                    if isinstance(value, list):
                        for item in value:
                            if item:
                                return str(item)
                    else:
                        return str(value)
            raise SecurityError(
                f"Appliance '{candidate}' has no reachable IP in the Orchestrator "
                "inventory. SSH cannot reach it."
            )
    raise SecurityError(
        f"Appliance '{target}' not found in the Orchestrator inventory. "
        "Use list_appliances to discover the registered appliances."
    )


class ApplianceSshPool:
    def __init__(self, settings):
        self._settings = settings
        self._sessions: dict[str, ApplianceSession] = {}
        self._inventory: list[dict] | None = None

    def get(self, host: str | None = None) -> ApplianceSession:
        target = host or self._settings.ssh_host
        if not self._settings.ssh_enabled:
            raise SecurityError("SSH tools are disabled (EC_SSH_ENABLED != true)")
        if not target:
            raise SecurityError(
                "No appliance host configured for SSH. Pass a host/IP/nePk/name, or "
                "set EC_SSH_HOST. Use list_appliances to discover the appliances."
            )
        resolved = resolve_appliance_address(target, self._settings, self._inventory)
        if resolved not in self._sessions:
            self._sessions[resolved] = ApplianceSession(
                host=resolved,
                username=self._settings.ssh_username,
                password=self._settings.ssh_password,
                port=self._settings.ssh_port,
                max_output_chars=self._settings.max_output_chars,
                enable_password=self._settings.ssh_enable_password,
            )
        return self._sessions[resolved]

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
