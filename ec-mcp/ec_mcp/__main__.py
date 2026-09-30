from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .server import create_server
from .transport import build_http_app, build_sse_app, resolve_auth_token


def _load_env_file() -> None:
    """Load .env next to the package installation (repo root) if present.

    Values already set in the environment take precedence over the file.
    """
    candidates = []
    env_path = os.environ.get("EC_MCP_ENV_FILE")
    if env_path:
        candidates.append(Path(env_path))
    cwd_env = Path.cwd() / ".env"
    candidates.append(cwd_env)
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


def main() -> None:
    _load_env_file()
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
    parser.add_argument(
        "--json-response",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("EC_MCP_JSON_RESPONSE", "true").lower() == "true",
        help="Answer POSTs with JSON bodies instead of SSE streams (default: true).",
    )
    args = parser.parse_args()

    server = create_server()

    if args.mode == "stdio":
        server.run("stdio")
        return

    token = resolve_auth_token()
    print(f"ec-mcp {args.mode} transport on http://{args.host}:{args.port} (bearer auth enabled)")

    if args.mode == "http":
        app = build_http_app(
            server, token, stateless=args.stateless, host=args.host, json_response=args.json_response
        )
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        app = build_sse_app(server, token)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
