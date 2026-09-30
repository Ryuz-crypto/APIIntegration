"""HTTP transports for the EdgeConnect MCP server with bearer-token authentication.

Exposes the MCP server over streamable-HTTP (recommended for remote clients)
or legacy SSE, wrapped in a Starlette app that:

- serves a public ``/health`` endpoint for load balancers / ZTNA probes;
- enforces an ``Authorization: Bearer <token>`` header on every other path
  before any MCP session is established;
- supports two valid tokens (primary + rotation) and rate-limits failed
  auth attempts per client IP (429).
"""

from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque
from typing import Any

from starlette.responses import JSONResponse

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as FastMCP

MIN_TOKEN_BYTES = 32
FAILED_AUTH_LIMIT = 5
FAILED_AUTH_WINDOW_SECONDS = 60.0


def validate_token_strength(token: str) -> None:
    if len(token.encode("utf-8")) < MIN_TOKEN_BYTES:
        raise SystemExit(
            f"EC_MCP_AUTH_TOKEN must be at least {MIN_TOKEN_BYTES} bytes of random data. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )


class BearerAuthMiddleware:
    """Serves /health without auth; rejects every other request without a
    valid Authorization: Bearer header. Failed attempts per IP are limited
    to FAILED_AUTH_LIMIT per FAILED_AUTH_WINDOW_SECONDS, then blocked."""

    def __init__(self, app, tokens: list[str], *, auth_limit: int = FAILED_AUTH_LIMIT,
                 auth_window: float = FAILED_AUTH_WINDOW_SECONDS):
        if not tokens:
            raise ValueError("At least one auth token is required")
        for token in tokens:
            validate_token_strength(token)
        self.app = app
        self.tokens = tokens
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._auth_limit = auth_limit
        self._auth_window = auth_window

    def _client_ip(self, scope: dict[str, Any]) -> str:
        client = scope.get("client")
        if client and isinstance(client, tuple):
            return str(client[0])
        forwarded = [
            value for key, value in scope.get("headers", [])
            if key == b"x-forwarded-for"
        ]
        if forwarded:
            return forwarded[0].decode("latin-1").split(",")[0].strip()
        return "unknown"

    def _is_rate_limited(self, ip: str) -> bool:
        now = time.monotonic()
        failures = self._failures[ip]
        while failures and now - failures[0] > self._auth_window:
            failures.popleft()
        return len(failures) >= self._auth_limit

    def _record_failure(self, ip: str) -> None:
        self._failures[ip].append(time.monotonic())

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            response = JSONResponse({"status": "ok"})
            await response(scope, receive, send)
            return

        # MCP clients probe OAuth discovery endpoints on 401; these probes
        # are unauthenticated by protocol design and must not count toward
        # the brute-force rate limit, nor should they return 405/404 noise.
        if path.startswith("/.well-known/"):
            response = JSONResponse(
                {"error": "this server uses static bearer tokens, not OAuth"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ip = self._client_ip(scope)
        if self._is_rate_limited(ip):
            response = JSONResponse({"error": "too many failed attempts"}, status_code=429)
            await response(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        authorization = headers.get("authorization", "")
        provided = authorization[len("Bearer "):].strip() if authorization.startswith("Bearer ") else ""
        if not provided or not any(
            hmac.compare_digest(provided, token) for token in self.tokens
        ):
            self._record_failure(ip)
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def resolve_transport_security(host: str = "127.0.0.1"):
    """Build TransportSecuritySettings that allow the public hostname(s).

    The MCP SDK enables DNS-rebinding protection when the server binds to
    localhost: every POST must then carry a Host header matching
    127.0.0.1/localhost, and any request that arrives through a reverse
    proxy with a public Host is rejected with 421 Misdirected Request.
    Deployments behind a proxy must declare their public hostnames via
    EC_MCP_ALLOWED_HOSTS (comma-separated), e.g. "mcp.example.com:10001".
    """
    from mcp.server.transport_security import TransportSecuritySettings

    extra = [
        h.strip() for h in os.environ.get("EC_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()
    ]
    allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    for entry in extra:
        base, _, port = entry.rpartition(":")
        if port.isdigit():
            allowed_hosts.append(entry)
        else:
            allowed_hosts.append(entry)
            allowed_hosts.append(f"{entry}:*")
    allowed_origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    for entry in extra:
        base = entry[:-2] if entry.endswith(":*") else entry
        allowed_origins.append(f"https://{base}:*")
        allowed_origins.append(f"http://{base}:*")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def build_http_app(
    server: FastMCP,
    token: str,
    *,
    stateless: bool = True,
    host: str = "127.0.0.1",
    json_response: bool | None = None,
):
    """Build the authenticated streamable-HTTP ASGI app with /health.

    ``json_response`` defaults to True: POST replies are plain JSON bodies
    instead of per-request SSE streams, which avoids the SDK's SSE-writer
    race (ClosedResourceError terminating freshly created sessions) behind
    reverse proxies/tunnels that close idle keep-alive connections. Set
    EC_MCP_JSON_RESPONSE=false to restore SSE responses.
    """
    if json_response is None:
        json_response = os.environ.get("EC_MCP_JSON_RESPONSE", "true").lower() == "true"
    mcp_app = server.streamable_http_app(
        stateless_http=stateless,
        json_response=json_response,
        transport_security=resolve_transport_security(host),
    )
    return BearerAuthMiddleware(mcp_app, resolve_auth_tokens(primary=token))


def build_sse_app(server: FastMCP, token: str):
    """Build the authenticated legacy SSE ASGI app with /health."""
    mcp_app = server.sse_app()
    return BearerAuthMiddleware(mcp_app, resolve_auth_tokens(primary=token))


def resolve_auth_tokens(primary: str | None = None) -> list[str]:
    """Return the active auth tokens: a primary (rotation) token plus the
    EC_MCP_AUTH_TOKEN environment token, so rotation can be seamless."""
    tokens: list[str] = []
    env_token = os.environ.get("EC_MCP_AUTH_TOKEN", "")
    for token in (primary, env_token):
        if token and token not in tokens:
            tokens.append(token)
    if not tokens:
        raise SystemExit(
            "EC_MCP_AUTH_TOKEN is required for HTTP/SSE transports. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return tokens


def resolve_auth_token() -> str:
    tokens = resolve_auth_tokens()
    return tokens[0]
