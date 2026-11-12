"""Tests for the Aruba Central v2 catalog and generic read tool."""

from __future__ import annotations

import json

import pytest

from ec_mcp.central_catalog import (
    CatalogError,
    build_request,
    groups,
    list_operations,
    load_catalog,
    resolve_operation,
    validate_read_operation,
)


def test_catalog_loads_and_is_complete():
    catalog = load_catalog()
    operations = catalog["operations"]
    assert len(operations) > 1000
    reads = [op for op in operations if op["method"] == "GET"]
    assert len(reads) > 500
    for op in operations:
        assert op["id"] and op["method"] and op["path"].startswith("/")
        assert "{" not in op["path"] or op["path_params"]


def test_list_operations_filters():
    all_ops = list_operations(limit=200)
    assert all_ops["total_catalog"] > 1000
    assert all_ops["count"] <= 200
    monitoring = list_operations(search="sites-health", limit=10)
    assert monitoring["count"] >= 1
    assert any(op["path"].endswith("sites-health") for op in monitoring["operations"])
    grouped = list_operations(group="Monitoring/Gateways", limit=10)
    assert grouped["count"] >= 1


def test_groups_list_catalog_families():
    families = groups()
    assert any("Monitoring" in family for family in families)
    assert any("Notifications" in family for family in families)
    assert any("Configuration" in family for family in families)


def test_resolve_operation_and_read_validation():
    sites_health_id = next(
        o["id"] for o in load_catalog()["operations"] if o["path"].endswith("sites-health")
    )
    op = resolve_operation(sites_health_id)
    assert op["path"].endswith("sites-health")
    validate_read_operation(op)
    write_op = next(o for o in load_catalog()["operations"] if o["method"] != "GET")
    with pytest.raises(CatalogError, match="read-only"):
        validate_read_operation(write_op)
    with pytest.raises(CatalogError, match="Unknown Central operation"):
        resolve_operation("does_not_exist")


def test_build_request_path_and_query_params():
    op = next(o for o in load_catalog()["operations"] if o["path_params"] and o["method"] == "GET")
    params = {name: f"value-{name}" for name in op["path_params"]}
    first_query = next((q["key"] for q in op["query"]), None)
    if first_query:
        params[first_query] = "1"
    path, query = build_request(op, params)
    assert "{" not in path
    assert all(f"value-{name}" in path for name in op["path_params"])
    if first_query:
        assert first_query in query
    with pytest.raises(CatalogError, match="Missing required path parameters"):
        build_request(op, {})
    with pytest.raises(CatalogError, match="Unknown query parameters"):
        build_request(op, {**params, "not_a_param": "x"})


def test_v2_tools_registered_and_read_only():
    import asyncio
    import os

    os.environ.setdefault("EC_MCP_ENV_FILE", "/dev/null")
    from ec_mcp import server

    mcp = server.create_server()
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert "central_v2_list_operations" in names
    assert "central_v2_call_read_api" in names

    async def call(name, args):
        return await mcp._tool_manager.call_tool(name, args, None)

    listing = asyncio.run(call("central_v2_list_operations", {"search": "sites-health", "limit": 5}))
    payload = json.loads(listing)
    assert payload["count"] >= 1

    sites_health_id = next(
        o["id"] for o in load_catalog()["operations"] if o["path"].endswith("sites-health")
    )
    refused = asyncio.run(
        call("central_v2_call_read_api", {"operation_id": sites_health_id, "params_json": "{}"})
    )
    assert "Error:" in refused  # Central not configured in the test env

    write_id = next(o["id"] for o in load_catalog()["operations"] if o["method"] == "POST")
    refused_write = asyncio.run(call("central_v2_call_read_api", {"operation_id": write_id, "params_json": "{}"}))
    assert "read-only" in refused_write
