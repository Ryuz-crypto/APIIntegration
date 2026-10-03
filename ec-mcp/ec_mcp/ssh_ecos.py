from __future__ import annotations

import re
import socket
import time

from .security import SecurityError, redact_secrets, sanitize_output, validate_show_command

try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None

try:
    import paramiko
except ImportError:
    paramiko = None

FORBIDDEN_CHARS = re.compile(r"[;&`]|\|\||&&|\$\(")


class _KeyboardInteractiveConnection:
    """Small command-timing adapter for appliances that only allow keyboard-interactive."""

    def __init__(self, host: str, username: str, password: str, port: int = 22):
        if paramiko is None:
            raise RuntimeError("paramiko is required for keyboard-interactive SSH")

        sock = socket.create_connection((host, port), timeout=30)
        self._transport = paramiko.Transport(sock)
        self._transport.banner_timeout = 30
        self._transport.auth_timeout = 30
        self._transport.start_client(timeout=30)
        self._transport.auth_interactive(username, _keyboard_interactive_handler(password))
        if not self._transport.is_authenticated():
            raise RuntimeError("Keyboard-interactive SSH authentication failed")
        self._channel = self._transport.open_session()
        self._channel.get_pty(term="vt100", width=200, height=50)
        self._channel.invoke_shell()
        self._read_until_quiet(2)

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

    @staticmethod
    def _connect(host: str, username: str, password: str, port: int, auth_method: str):
        if auth_method == "keyboard-interactive":
            return _KeyboardInteractiveConnection(host, username, password, port)

        if ConnectHandler is None:
            if auth_method == "password":
                raise RuntimeError("netmiko is not installed; SSH tools are unavailable")
            return _KeyboardInteractiveConnection(host, username, password, port)

        try:
            return ConnectHandler(
                device_type="linux_ssh",
                host=host,
                username=username,
                password=password,
                port=port,
                ssh_strict=False,
                banner_timeout=30,
                auth_timeout=30,
            )
        except Exception as error:
            if auth_method != "auto" or not _AUTH_METHOD_ERROR_RE.search(str(error)):
                raise
            return _KeyboardInteractiveConnection(host, username, password, port)

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
                auth_method=self._settings.ssh_auth_method,
            )
        return self._sessions[resolved]

    def close_all(self) -> None:
        for session in self._sessions.values():
            session.close()
        self._sessions.clear()
