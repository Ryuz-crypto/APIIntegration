from __future__ import annotations

import argparse
import os

import uvicorn

from .server import create_server
from .transport import build_http_app, build_sse_app, resolve_auth_token


def main() -> None:
    parser = argparse.ArgumentParser(prog="ec-mcp", description="EdgeConnect SD-WAN MCP server")
    parser.add_argument("mode", nargs="?", default="stdio", choices=["stdio", "http", "sse"])
    parser.add_argument("--host", default=os.environ.get("EC_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("EC_MCP_PORT", "8000")))
    parser.add_argument(
        "--stateless",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("EC_MCP_STATELESS", "false").lower() == "true",
        help="Stateless HTTP (no Mcp-Session-Id). Stateful by default for client compatibility.",
    )
    args = parser.parse_args()

    server = create_server()

    if args.mode == "stdio":
        server.run("stdio")
        return

    token = resolve_auth_token()
    print(f"ec-mcp {args.mode} transport on http://{args.host}:{args.port} (bearer auth enabled)")

    if args.mode == "http":
        app = build_http_app(server, token, stateless=args.stateless, host=args.host)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        app = build_sse_app(server, token)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
