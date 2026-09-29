TOKEN = "test-token-123-test-token-123-test-token-123"

import json
import threading
import time
import urllib.request

import pytest
import uvicorn

from ec_mcp.server import create_server
from ec_mcp.transport import build_http_app

PORT = 8931
BASE = f"http://127.0.0.1:{PORT}/mcp"


@pytest.fixture(scope="module")
def http_server():
    server = create_server()
    global TOKEN

    app = build_http_app(server, TOKEN)
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(40):
        time.sleep(0.25)
        try:
            urllib.request.urlopen(BASE, timeout=2)
        except urllib.error.HTTPError:
            break
        except Exception:
            continue
    yield srv
    srv.should_exit = True


def _post(body: dict, token: str | None) -> urllib.request.Request:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(BASE, method="POST", data=json.dumps(body).encode(), headers=headers)


def test_http_rejects_missing_token(http_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(
            _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}, None),
            timeout=5,
        )
    assert excinfo.value.code == 401


def test_http_rejects_bad_token(http_server):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(
            _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}, "wrong"),
            timeout=5,
        )
    assert excinfo.value.code == 401


def test_http_accepts_valid_token(http_server):
    resp = urllib.request.urlopen(
        _post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}, TOKEN),
        timeout=10,
    )
    assert resp.status == 200
    body = resp.read().decode()
    assert "edgeconnect" in body.lower() or "serverinfo" in body.lower()


def test_health_endpoint_public(http_server):
    resp = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5)
    assert resp.status == 200
    assert b"ok" in resp.read()
