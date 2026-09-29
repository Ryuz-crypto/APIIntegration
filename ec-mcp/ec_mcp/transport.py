"""HTTP transports for the EdgeConnect MCP server with bearer-token authentication.

Exposes the MCP server over streamable-HTTP (recommended for remote clients)
or legacy SSE, wrapped in a Starlette middleware that enforces an
Authorization: Bearer <token> header before any MCP session is established.
"""
from __future__ import annotations

import hmac
import os
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as FastMCP


class BearerAuthMiddleware:
    """Rejects requests without a valid Authorization: Bearer header."""

    def __init__(self, app, token: str, exempt_paths: tuple[str, ...] = ("/health",)):
        self.app = app
        self.token = token
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or not hmac.compare_digest(
            authorization[len("Bearer "):].strip(), self.token
        ):
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def build_http_app(server: FastMCP, token: str, *, stateless: bool = True) -> Any:
    """Build the authenticated streamable-HTTP Starlette app."""
    app = server.streamable_http_app(stateless_http=stateless)
    return BearerAuthMiddleware(app, token)


def build_sse_app(server: FastMCP, token: str) -> Any:
    """Build the authenticated legacy SSE Starlette app."""
    app = server.sse_app()
    return BearerAuthMiddleware(app, token)


def resolve_auth_token() -> str:
    token = os.environ.get("EC_MCP_AUTH_TOKEN", "")
    if not token:
        raise SystemExit(
            "EC_MCP_AUTH_TOKEN is required for HTTP/SSE transports. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return token
