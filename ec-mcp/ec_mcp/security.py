from __future__ import annotations

import re


class SecurityError(ValueError):
    pass


ALLOWED_SHOW_PATTERNS = [
    r"^show\s+version",
    r"^show\s+system\s+info",
    r"^show\s+interface\s+.*",
    r"^show\s+ip\s+route",
    r"^show\s+ip\s+arp",
    r"^show\s+session",
    r"^show\s+tunnel\s+.*",
    r"^show\s+flow\s+.*",
    r"^show\s+bgp",
    r"^show\s+ospf",
    r"^show\s+alarm",
    r"^show\s+event\s+.*",
    r"^show\s+subtended",
    r"^show\s+history",
    r"^show\s+clock",
]

DENIED_PATTERNS = [
    r"\bconfig\b",
    r"\bterminal\s+length\s+0\b",
    r"^set\s+",
    r"^clear\s+",
    r"^restart\s+",
    r"^reboot",
    r"^reload",
    r"^delete\s+",
    r"\bshell\b",
    r"\bpwd\b",
    r";",
    r"\|\|",
    r"&&",
    r"`",
    r"\$\(",
]


def validate_show_command(command: str) -> str:
    normalized = command.strip()
    if not normalized:
        raise SecurityError("Empty command")
    lowered = normalized.lower()
    for pattern in DENIED_PATTERNS:
        if re.search(pattern, lowered):
            raise SecurityError(f"Command rejected by security policy: {command}")
    for pattern in ALLOWED_SHOW_PATTERNS:
        if re.fullmatch(pattern, lowered):
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
    return text
