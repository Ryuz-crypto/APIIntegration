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
TOKEN_REFRESH_SECONDS = 3.0


def validate_token_strength(token: str) -> None:
    if len(token.encode("utf-8")) < MIN_TOKEN_BYTES:
        raise SystemExit(
            f"EC_MCP_AUTH_TOKEN must be at least {MIN_TOKEN_BYTES} bytes of random data. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


def _env_file_path() -> str:
    """Resolve the .env file the same way the CLI loader does."""
    candidates = []
    env_path = os.environ.get("EC_MCP_ENV_FILE")
    if env_path:
        candidates.append(env_path)
    candidates.append(os.path.join(os.getcwd(), ".env"))
    candidates.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


def _env_file_value(key: str) -> str:
    """Return a raw value from the .env file without touching os.environ."""
    path = _env_file_path()
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as stream:
            lines = stream.read().splitlines()
    except OSError:
        return ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        if name.strip() == key:
            return value.strip().strip('"').strip("'")
    return ""


class TokenStore:
    """Auth token set with hot reload.

    The initial set (primary rotation token + EC_MCP_AUTH_TOKEN + named
    tokens) is resolved at startup; every TOKEN_REFRESH_SECONDS the named
    tokens are re-read from the .env file so the panel can create or
    revoke tokens without restarting the service. A broken file keeps
    the last known-good set (fail-closed, never open).
    """

    def __init__(self, tokens: list[str], *, ttl: float = TOKEN_REFRESH_SECONDS):
        if not tokens:
            raise ValueError("At least one auth token is required")
        for token in tokens:
            validate_token_strength(token)
        self._static = list(tokens)
        self._named: list[str] = []
        self._ttl = ttl
        self._at = 0.0

    def current(self) -> list[str]:
        now = time.monotonic()
        if now - self._at >= self._ttl:
            self._at = now
            blob = _env_file_value("EC_MCP_AUTH_TOKENS_JSON") or os.environ.get("EC_MCP_AUTH_TOKENS_JSON", "")
            try:
                named = load_named_auth_tokens(blob)
            except SystemExit:
                named = {}
                for token in self._named:
                    named[str(len(named))] = token
            self._named = [token for token in named.values() if token not in self._static]
        tokens = list(self._static)
        for token in self._named:
            if token not in tokens:
                tokens.append(token)
        return tokens

    def force_refresh(self) -> None:
        self._at = 0.0


class BearerAuthMiddleware:
    """Serves /health without auth; rejects every other request without a
    valid Authorization: Bearer header. Failed attempts per IP are limited
    to FAILED_AUTH_LIMIT per FAILED_AUTH_WINDOW_SECONDS, then blocked."""

    def __init__(
        self,
        app,
        tokens,
        *,
        auth_limit: int = FAILED_AUTH_LIMIT,
        auth_window: float = FAILED_AUTH_WINDOW_SECONDS,
    ):
        if isinstance(tokens, TokenStore):
            self.store = tokens
        else:
            self.store = TokenStore(list(tokens))
        self.app = app
        self.tokens = self.store.current()
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._auth_limit = auth_limit
        self._auth_window = auth_window

    def _client_ip(self, scope: dict[str, Any]) -> str:
        client = scope.get("client")
        if client and isinstance(client, tuple):
            return str(client[0])
        forwarded = [value for key, value in scope.get("headers", []) if key == b"x-forwarded-for"]
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
            import os

            orch_url = os.environ.get("EC_ORCHESTRATOR_URL", "")
            orch_auth = bool(
                os.environ.get("EC_ORCHESTRATOR_API_KEY", "") or os.environ.get("EC_ORCHESTRATOR_USER", "")
            )
            response = JSONResponse(
                {
                    "status": "ok",
                    "service": "ec-mcp",
                    "orchestrator_configured": bool(orch_url and orch_auth),
                    "missing_config": [
                        kind
                        for kind, configured in (
                            ("orchestrator_url", bool(orch_url)),
                            ("orchestrator_credentials", orch_auth),
                        )
                        if not configured
                    ],
                }
            )
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

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        authorization = headers.get("authorization", "")
        provided = authorization[len("Bearer ") :].strip() if authorization.startswith("Bearer ") else ""
        if not provided or not any(hmac.compare_digest(provided, token) for token in self.store.current()):
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

    extra = [h.strip() for h in os.environ.get("EC_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
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
    return BearerAuthMiddleware(mcp_app, TokenStore(resolve_auth_tokens(primary=token)))


def build_sse_app(server: FastMCP, token: str):
    """Build the authenticated legacy SSE ASGI app with /health."""
    mcp_app = server.sse_app()
    return BearerAuthMiddleware(mcp_app, TokenStore(resolve_auth_tokens(primary=token)))


def resolve_auth_tokens(primary: str | None = None) -> list[str]:
    """Return the active auth tokens: a primary (rotation) token, the
    EC_MCP_AUTH_TOKEN environment token and every named token from
    EC_MCP_AUTH_TOKENS_JSON (independent tokens per AI platform, e.g.
    Vibe, Claude, ChatGPT), so rotation can be seamless."""
    tokens: list[str] = []
    env_token = os.environ.get("EC_MCP_AUTH_TOKEN", "")
    for token in (primary, env_token):
        if token and token not in tokens:
            tokens.append(token)
    for token in load_named_auth_tokens().values():
        if token and token not in tokens:
            tokens.append(token)
    if not tokens:
        raise SystemExit(
            "EC_MCP_AUTH_TOKEN is required for HTTP/SSE transports. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    return tokens


def load_named_auth_tokens(blob: str = "") -> dict[str, str]:
    """Load the named MCP tokens from EC_MCP_AUTH_TOKENS_JSON.

    Format: {"<name>": "<token>", ...}. Invalid JSON or non-string values
    are rejected so a broken file cannot silently disable authentication.
    """
    import json

    raw = blob.strip() or os.environ.get("EC_MCP_AUTH_TOKENS_JSON", "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SystemExit(f"EC_MCP_AUTH_TOKENS_JSON is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise SystemExit("EC_MCP_AUTH_TOKENS_JSON must be a JSON object name -> token")
    tokens: dict[str, str] = {}
    for name, token in data.items():
        if not isinstance(token, str) or not token.strip():
            raise SystemExit(f"EC_MCP_AUTH_TOKENS_JSON[{name}] must be a non-empty string")
        tokens[str(name)] = token.strip()
    return tokens


def resolve_auth_token() -> str:
    tokens = resolve_auth_tokens()
    return tokens[0]
