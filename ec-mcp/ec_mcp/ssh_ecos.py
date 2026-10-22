from __future__ import annotations

import re
import socket
import time
from typing import Any

from .security import SecurityError, redact_secrets, sanitize_output, validate_show_command
from .ssh_network import (
    NetworkPath,
    classify_network_path,
    is_connection_rejected,
    summarize_inbound_forwarding_need,
)

try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None

try:
    import paramiko
except ImportError:
    paramiko = None

FORBIDDEN_CHARS = re.compile(r"[;&`]|\|\||&&|\$\(")
_TRANSIENT_SSH_ERROR_RE = re.compile(
    r"(?i)timeout|timed out|temporarily unavailable|connection reset|"
    r"ssh protocol banner|channel closed|socket is closed"
)


def is_transient_ssh_error(error: BaseException) -> bool:
    """Return true only for connection failures that are safe to retry once."""
    return bool(_TRANSIENT_SSH_ERROR_RE.search(str(error)))


class _KeyboardInteractiveConnection:
    """Small command-timing adapter for appliances that only allow keyboard-interactive."""

    def __init__(self, host: str, username: str, password: str, port: int = 22, connect_timeout: int = 30, command_timeout: int = 30):
        if paramiko is None:
            raise RuntimeError("paramiko is required for keyboard-interactive SSH")

        sock = socket.create_connection((host, port), timeout=connect_timeout)
        self._transport = paramiko.Transport(sock)
        self._transport.banner_timeout = connect_timeout
        self._transport.auth_timeout = connect_timeout
        self._command_timeout = command_timeout
        self._transport.start_client(timeout=connect_timeout)
        self._transport.auth_interactive(username, _keyboard_interactive_handler(password))
        if not self._transport.is_authenticated():
            raise RuntimeError("Keyboard-interactive SSH authentication failed")
        self._channel = self._transport.open_session()
        self._channel.get_pty(term="vt100", width=200, height=50)
        self._channel.invoke_shell()
        self._read_until_quiet(min(2, self._command_timeout))

    def _read_until_quiet(self, read_timeout: float, quiet_period: float = 0.4) -> str:
        deadline = time.monotonic() + read_timeout
        last_data = time.monotonic()
        chunks: list[bytes] = []
        while time.monotonic() < deadline:
            if self._channel.recv_ready():
                chunks.append(self._channel.recv(65535))
                last_data = time.monotonic()
                continue
            if chunks and time.monotonic() - last_data >= quiet_period:
                break
            time.sleep(0.05)
        return b"".join(chunks).decode("utf-8", errors="replace")

    def send_command_timing(self, command: str, read_timeout: int = 30) -> str:
        self._channel.send(command.rstrip() + "\n")
        return self._read_until_quiet(read_timeout)

    def write(self, data: str) -> None:
        self._channel.send(data)

    def disconnect(self) -> None:
        self._channel.close()
        self._transport.close()


def _keyboard_interactive_handler(password: str):
    def handler(_title: str, _instructions: str, prompts):
        responses = []
        for prompt, _echo in prompts:
            lowered = prompt.strip().lower()
            is_confirmation = (
                ("yes/no" in lowered or "y/n" in lowered)
                and any(word in lowered for word in ("accept", "continue", "confirm", "fingerprint"))
            )
            responses.append("yes" if is_confirmation else password)
        return responses

    return handler


_AUTH_METHOD_ERROR_RE = re.compile(
    r"(?i)bad authentication type|allowed types|no authentication methods available|"
    r"error reading ssh protocol banner|banner_timeout|authentication failed|authentication failure"
)


class ApplianceSession:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        max_output_chars: int = 12000,
        enable_password: str = "",
        auth_method: str = "auto",
        connect_timeout: int = 30,
        command_timeout: int = 30,
    ):  # nosec B107
        auth_method = auth_method.strip().lower()
        if auth_method not in {"auto", "password", "keyboard-interactive"}:
            raise ValueError(
                "Unsupported EC_SSH_AUTH_METHOD; use auto, password, or keyboard-interactive"
            )
        self._connection = self._connect(
            host=host,
            username=username,
            password=password,
            port=port,
            auth_method=auth_method,
            connect_timeout=connect_timeout,
            command_timeout=command_timeout,
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
        self._command_timeout = command_timeout

    @staticmethod
    def _connect(host: str, username: str, password: str, port: int, auth_method: str, connect_timeout: int, command_timeout: int):
        if auth_method == "keyboard-interactive":
            return _KeyboardInteractiveConnection(host, username, password, port, connect_timeout, command_timeout)

        if ConnectHandler is None:
            if auth_method == "password":
                raise RuntimeError("netmiko is not installed; SSH tools are unavailable")
            return _KeyboardInteractiveConnection(host, username, password, port, connect_timeout, command_timeout)

        try:
            return ConnectHandler(
                device_type="linux_ssh",
                host=host,
                username=username,
                password=password,
                port=port,
                ssh_strict=False,
                banner_timeout=connect_timeout,
                auth_timeout=connect_timeout,
                conn_timeout=connect_timeout,
            )
        except Exception as error:
            if auth_method != "auto" or not _AUTH_METHOD_ERROR_RE.search(str(error)):
                raise
            return _KeyboardInteractiveConnection(host, username, password, port)

    def run_show(self, command: str) -> str:
        validated = validate_show_command(command)
        self._connection.send_command_timing("page off", read_timeout=min(10, self._command_timeout))
        raw = self._connection.send_command_timing(validated, read_timeout=self._command_timeout)
        return redact_secrets(sanitize_output(raw, self._max_output_chars), [])

    def run_raw(self, command: str) -> str:
        normalized = command.strip()
        if not normalized:
            raise SecurityError("Empty command")
        if FORBIDDEN_CHARS.search(normalized):
            raise SecurityError("Command contains forbidden characters")
        if re.search(r"[\x00-\x1f\x7f]|[^\x00-\x7f]", normalized):
            raise SecurityError("Command contains forbidden characters")
        raw = self._connection.send_command_timing(normalized, read_timeout=max(60, self._command_timeout))
        return redact_secrets(sanitize_output(raw, self._max_output_chars), [])

    def close(self) -> None:
        self._connection.disconnect()


def resolve_appliance_address(
    target: str,
    settings,
    inventory: list[dict] | None = None,
    prefer_network: str = "auto",
) -> str:
    """Resolve an appliance reference (nePk, name, IP or serial) to a reachable IP.

    If the reference looks like a host/IP it is used directly; otherwise the
    Orchestrator inventory is consulted (name, nePk, serial, IP, LAN/WAN fields).

    When prefer_network is "auto" (default) the LAN/WAN path is classified:
    - Same subnet as a local interface -> LAN IP (direct).
    - Otherwise -> WAN interface IP (the IP configured on the appliance WAN
      interface, NOT the public/NAT egress IP). Requires inbound forwarding.
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
    for appliance in inventory:
        identifiers = {
            str(appliance.get("nePk") or "").lower(),
            str(appliance.get("name") or "").lower(),
            str(appliance.get("serial_number") or "").lower(),
        }
        if lowered in identifiers:
            if prefer_network == "lan":
                for field in ("lan_ip", "ip"):
                    value = appliance.get(field)
                    if value:
                        return str(value)
            elif prefer_network == "wan":
                wan_ips = appliance.get("wan_ips") or []
                if wan_ips:
                    return str(wan_ips[0])
                raise SecurityError(
                    f"Appliance '{candidate}' has no WAN interface IP in the Orchestrator "
                    "inventory. SSH over WAN requires the appliance WAN interface IP "
                    "(not the public/NAT egress IP)."
                )
            else:
                path = classify_network_path(appliance, settings.orchestrator_url)
                return path.target_ip
    raise SecurityError(
        f"Appliance '{target}' not found in the Orchestrator inventory. "
        "Use list_appliances to discover the registered appliances."
    )


def resolve_appliance_network_path(
    target: str,
    settings,
    inventory: list[dict] | None = None,
) -> NetworkPath:
    """Resolve an appliance reference to a full NetworkPath (IP + LAN/WAN + notes)."""
    candidate = target.strip()
    if not candidate:
        raise SecurityError("No appliance host given for SSH")
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
    for appliance in inventory:
        identifiers = {
            str(appliance.get("nePk") or "").lower(),
            str(appliance.get("name") or "").lower(),
            str(appliance.get("serial_number") or "").lower(),
        }
        if lowered in identifiers:
            return classify_network_path(appliance, settings.orchestrator_url)
    raise SecurityError(
        f"Appliance '{target}' not found in the Orchestrator inventory. "
        "Use list_appliances to discover the registered appliances."
    )


def find_appliance(
    target: str,
    inventory: list[dict],
) -> dict[str, Any] | None:
    """Find an appliance dict in the inventory by nePk, name, serial, or IP."""
    lowered = target.strip().lower()
    if not lowered:
        return None
    for appliance in inventory:
        identifiers = {
            str(appliance.get("nePk") or "").lower(),
            str(appliance.get("name") or "").lower(),
            str(appliance.get("serial_number") or "").lower(),
            str(appliance.get("ip") or "").lower(),
            str(appliance.get("lan_ip") or "").lower(),
        }
        if lowered in identifiers:
            return appliance
        for wan_ip in appliance.get("wan_ips") or []:
            if str(wan_ip).lower() == lowered:
                return appliance
    return None


class ApplianceSshPool:
    def __init__(self, settings):
        self._settings = settings
        self._sessions: dict[str, ApplianceSession] = {}
        self._inventory: list[dict] | None = None
        self._network_paths: dict[str, NetworkPath] = {}

    def _load_inventory(self) -> list[dict]:
        if self._inventory is None:
            from .compat import CompatibilityEngine, load_profiles
            from .orchestrator_client import OrchestratorClient

            engine = CompatibilityEngine(load_profiles(self._settings.profiles_dir))
            client = OrchestratorClient(self._settings, engine)
            self._inventory = client.list_appliances()
        return self._inventory

    def get(self, host: str | None = None) -> ApplianceSession:
        target = host or self._settings.ssh_host
        if not self._settings.ssh_enabled:
            raise SecurityError("SSH tools are disabled (EC_SSH_ENABLED != true)")
        if not target:
            raise SecurityError(
                "No appliance host configured for SSH. Pass a host/IP/nePk/name, or "
                "set EC_SSH_HOST. Use list_appliances to discover the appliances."
            )
        inventory = self._load_inventory()
        path = resolve_appliance_network_path(target, self._settings, inventory)
        self._network_paths[target] = path
        resolved = path.target_ip
        if resolved not in self._sessions:
            retries = max(0, int(self._settings.ssh_retries))
            for attempt in range(retries + 1):
                try:
                    self._sessions[resolved] = ApplianceSession(
                        host=resolved,
                        username=self._settings.ssh_username,
                        password=self._settings.ssh_password,
                        port=self._settings.ssh_port,
                        max_output_chars=self._settings.max_output_chars,
                        enable_password=self._settings.ssh_enable_password,
                        auth_method=self._settings.ssh_auth_method,
                        connect_timeout=self._settings.ssh_connect_timeout,
                        command_timeout=self._settings.ssh_command_timeout,
                    )
                    break
                except Exception as error:
                    if attempt < retries and is_transient_ssh_error(error):
                        time.sleep(min(0.25 * (2**attempt), 1.0))
                        continue
                    if is_connection_rejected(error):
                        appliance = find_appliance(target, inventory)
                        if appliance and path.network == "wan":
                            diagnosis = summarize_inbound_forwarding_need(appliance, error)
                            raise SecurityError(
                                "SSH connection to the appliance WAN interface was rejected. "
                                f"Diagnosis: {diagnosis['diagnosis']}. "
                                f"WAN IP: {diagnosis['wan_ip']}, LAN IP: {diagnosis['lan_ip']}. "
                                f"Remediation: {diagnosis['remediation']}"
                            ) from error
                    raise
        return self._sessions[resolved]

    def get_network_path(self, host: str | None = None) -> NetworkPath | None:
        """Return the resolved NetworkPath for a host (if already resolved)."""
        target = host or self._settings.ssh_host
        return self._network_paths.get(target)

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
        self._network_paths.clear()
