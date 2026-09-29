"""Security tests for phases 1-2 of the hardening recommendations."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from ec_mcp.security import (
    ALLOWED_SHOW_COMMANDS,
    SecurityError,
    redact_secrets,
    validate_show_command,
)
from ec_mcp.transport import BearerAuthMiddleware, validate_token_strength

LONG_TOKEN = "x" * 40


def _expect_rejected(command: str) -> None:
    with pytest.raises(SecurityError):
        validate_show_command(command)


def test_injection_semicolon_rejected():
    _expect_rejected("show version; reboot")


def test_injection_and_rejected():
    _expect_rejected("show version && id")


def test_injection_command_substitution_rejected():
    _expect_rejected("show $(id)")


def test_injection_newline_rejected():
    _expect_rejected("show version\nreboot")


def test_injection_backtick_rejected():
    _expect_rejected("show version`id`")


def test_injection_pipe_rejected():
    _expect_rejected("show version | id")


def test_injection_unicode_rejected():
    _expect_rejected("show version｠")


def test_allowlist_no_shell_metacharacters():
    for command in ALLOWED_SHOW_COMMANDS:
        assert not any(c in command for c in ";|&`$()\n\\"), command


def test_show_args_still_accepted():
    assert validate_show_command("show interfaces tunnel 1").startswith("show")
    assert validate_show_command("show log-list matching 10").startswith("show")


def test_show_trailing_metachar_args_rejected():
    _expect_rejected("show interfaces tunnel 1; reboot")
    _expect_rejected("show log-list matching 10 && reboot")


def test_redact_secrets_password():
    out = redact_secrets("admin password: SuperSecret123 end", [])
    assert "SuperSecret123" not in out
    assert "***REDACTED***" in out


def test_redact_secrets_snmp_community():
    out = redact_secrets("snmp community public123", [])
    assert "public123" not in out
    assert "***REDACTED***" in out


def test_redact_secrets_explicit_values():
    out = redact_secrets("my api key mykey123", ["mykey123"])
    assert "mykey123" not in out


def test_token_minimum_length_enforced():
    with pytest.raises(SystemExit):
        validate_token_strength("short")
    validate_token_strength("a" * 32)


def _make_scope(path: str = "/mcp", headers: list | None = None, ip: str = "1.2.3.4"):
    body = b""
    return {
        "type": "http",
        "path": path,
        "method": "POST",
        "headers": headers or [],
        "client": (ip, 12345),
        "body": body,
    }


class _Capture:
    def __init__(self):
        self.status = None

    async def __call__(self, scope, receive, send):
        self.status = scope.get("_status")
        scope["_capture"] = self


def _receive():
    async def receive():
        return {"type": "http.request", "body": b""}
    return receive


def _send_status(status):
    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
    return send


@pytest.mark.asyncio
async def test_middleware_401_without_token():
    middleware = BearerAuthMiddleware(_Capture(), [LONG_TOKEN])
    statuses: list = []
    await middleware(_make_scope(), _receive(), _send_status(statuses))
    assert statuses == [401]


@pytest.mark.asyncio
async def test_middleware_401_bad_token_then_429():
    middleware = BearerAuthMiddleware(_Capture(), [LONG_TOKEN])
    statuses: list = []
    for _ in range(5):
        await middleware(
            _make_scope(headers=[(b"authorization", b"Bearer wrong")]),
            None,
            _send_status(statuses),
        )
    assert statuses == [401] * 5
    statuses.clear()
    await middleware(_make_scope(), _receive(), _send_status(statuses))
    assert statuses == [429]


@pytest.mark.asyncio
async def test_middleware_rate_limit_window_expires():
    middleware = BearerAuthMiddleware(
        _Capture(), [LONG_TOKEN], auth_window=0.05
    )
    statuses: list = []
    for _ in range(5):
        await middleware(
            _make_scope(headers=[(b"authorization", b"Bearer wrong")]),
            None,
            _send_status(statuses),
        )
    time.sleep(0.06)
    statuses.clear()
    await middleware(_make_scope(), _receive(), _send_status(statuses))
    assert statuses == [401]


@pytest.mark.asyncio
async def test_middleware_valid_token_passes():
    downstream = _Capture()

    async def app(scope, receive, send):
        downstream.called = True

    middleware = BearerAuthMiddleware(app, [LONG_TOKEN])
    statuses: list = []
    scope = _make_scope(headers=[(b"authorization", f"Bearer {LONG_TOKEN}".encode())])
    await middleware(scope, _receive(), _send_status(statuses))
    assert statuses == []
    assert downstream.called


@pytest.mark.asyncio
async def test_middleware_rotation_second_token_valid():
    downstream = _Capture()

    async def app(scope, receive, send):
        downstream.called = True

    rotation = "y" * 40
    middleware = BearerAuthMiddleware(app, [LONG_TOKEN, rotation])
    statuses: list = []
    scope = _make_scope(headers=[(b"authorization", f"Bearer {rotation}".encode())])
    await middleware(scope, _receive(), _send_status(statuses))
    assert downstream.called


@pytest.mark.asyncio
async def test_health_has_no_sensitive_data():
    middleware = BearerAuthMiddleware(_Capture(), [LONG_TOKEN])
    captured: dict = {}

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        if message["type"] == "http.response.start":
            captured["status"] = message["status"]
        if message["type"] == "http.response.body":
            captured["body"] = message.get("body", b"")

    await middleware(_make_scope(path="/health"), receive, send)
    assert captured["status"] == 200
    payload = json.loads(captured["body"])
    assert set(payload.keys()) == {"status"}
    assert payload == {"status": "ok"}


def test_audit_log_never_contains_credentials():
    from ec_mcp.audit import AuditLog

    tmp = Path("/tmp/audit-security-test")
    tmp.mkdir(exist_ok=True)
    log = AuditLog(tmp / "audit.jsonl")
    entry = log.record(
        "apply_change",
        "setApplianceDescription",
        "/appliance/1",
        "ok",
        details={"body_keys": ["description"]},
    )
    text = log._path.read_text()
    for leak in ("Bearer", "password", "token", "secret"):
        assert leak not in text.lower()
    assert entry["dry_run"] is False
