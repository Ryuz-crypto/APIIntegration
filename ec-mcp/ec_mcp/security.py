from __future__ import annotations

import re


class SecurityError(ValueError):
    pass


ALLOWED_SHOW_COMMANDS = [
    "show aaa",
    "show access-list",
    "show alarms",
    "show application",
    "show application-builtin",
    "show application-group",
    "show arp",
    "show banner",
    "show bgp",
    "show bootvar",
    "show bridge",
    "show cdp",
    "show cifs signing delegation",
    "show cli",
    "show clock",
    "show cluster",
    "show configuration",
    "show email",
    "show excess-flow",
    "show files",
    "show flow-debug",
    "show flow-export",
    "show flow-redirection",
    "show hosts",
    "show iflabels",
    "show image",
    "show interfaces",
    "show interfaces cdp",
    "show interfaces pass-through",
    "show interfaces security",
    "show interfaces tunnel",
    "show interfaces virtual",
    "show interfaces vrrp",
    "show ip",
    "show ip-tracking",
    "show jobs",
    "show licenses",
    "show log",
    "show log audit",
    "show log-files",
    "show log-list matching",
    "show logging",
    "show memory",
    "show nat-map",
    "show nat statistics",
    "show ntp",
    "show opt-map",
    "show overlay",
    "show overlay-common",
    "show pass-through",
    "show preposition",
    "show qos-map",
    "show radius",
    "show route-map",
    "show running-config",
    "show selftest",
    "show shaper",
    "show snmp",
    "show ssh",
    "show ssl",
    "show stats",
    "show stats tunnel",
    "show subif",
    "show subnet",
    "show system",
    "show tacacs",
    "show tca",
    "show tech-support",
    "show terminal",
    "show tunnel",
    "show usernames",
    "show users",
    "show version",
    "show vlan",
    "show vrrp",
    "show wccp",
    "show web",
    "show whoami",
    "show history",
    "show session",
    "show segment",
    "show ospf",
    "show event",
    "show subtended",
]

from ec_mcp.cli_catalog import MONITORING as CATALOG_MONITORING

ALLOWED_SHOW_COMMANDS = list(dict.fromkeys(ALLOWED_SHOW_COMMANDS + CATALOG_MONITORING))

ALLOWED_SHOW_ARGS = re.compile(r"[A-Za-z0-9 ._:/@\-,#()\[\]%]*")
ALLOWED_SHOW_PATTERNS = [
    re.compile(rf"^{re.escape(command)}( {ALLOWED_SHOW_ARGS.pattern})*$")
    for command in ALLOWED_SHOW_COMMANDS
]
SHELL_METACHARS = re.compile(r"[;&`|<>$\\]|\$\(|\|\||&&")
CONTROL_OR_NON_ASCII = re.compile(r"[\x00-\x1f\x7f]|[^\x00-\x7f]")
SECRET_PATTERNS = [
    re.compile(r"(?i)(\b(?:password|passwd|md5password|secret|passphrase|psk|userName)\b[\"']?\s*[:=]\s*[\"']?)[^\"',\s]+"),
    re.compile(r"(?i)(\bcommunity(?:\s+string)?\s+)(?!string\b)\S+"),
]

DENIED_PATTERNS = [
    re.compile(r"\bconfig\b(?!uration)"),
    re.compile(r"\bterminal\s+length\b"),
    re.compile(r"^set\s+"),
    re.compile(r"^clear\s+"),
    re.compile(r"^restart\s+"),
    re.compile(r"^reboot\b"),
    re.compile(r"^reload\b"),
    re.compile(r"^delete\s+"),
    re.compile(r"\bshell\b"),
    re.compile(r"\bpwd\b"),
    re.compile(r"[;&`|<>$\\]"),
    re.compile(r"\$\("),
    re.compile(r"[\x00-\x1f\x7f]"),
    re.compile(r"[^\x00-\x7f]"),
]


def validate_show_command(command: str) -> str:
    normalized = command.strip()
    if not normalized:
        raise SecurityError("Empty command")
    if CONTROL_OR_NON_ASCII.search(normalized) or SHELL_METACHARS.search(normalized):
        raise SecurityError(f"Command contains forbidden characters: {command}")
    lowered = normalized.lower()
    for pattern in DENIED_PATTERNS:
        if pattern.search(lowered):
            raise SecurityError(f"Command rejected by security policy: {command}")
    for pattern in ALLOWED_SHOW_PATTERNS:
        if pattern.match(lowered):
            return normalized
    raise SecurityError(f"Command not in the read-only whitelist: {command}")


def sanitize_output(text: str, max_chars: int) -> str:
    truncated = text[:max_chars]
    if len(text) > max_chars:
        truncated += f"\n... [output truncated at {max_chars} characters]"
    return truncated


def redact_secrets(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***REDACTED***")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "***REDACTED***", text)
    return text
