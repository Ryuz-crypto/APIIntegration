from __future__ import annotations

import asyncio
import json

import pytest

from ec_mcp.config import Settings
from ec_mcp.overlay_workflow import (
    OverlayPlanStore,
    extract_overlays,
    prepare_overlay_plan,
    sanitize_overlay,
)
from ec_mcp.server import create_server

SOURCE = {
    "id": 1,
    "name": "RealTime",
    "topology": {"topologyType": 1, "hubs": ["1.NE", "2.NE"]},
    "match": {"overlayAcl": "{}"},
    "brownoutThresholds": {"loss": 1.0, "latency": 100, "jitter": 50},
}


def test_sanitize_overlay_removes_managed_fields_and_deep_merges() -> None:
    source = {**SOURCE, "overlayId": 1, "createdBy": "admin"}
    candidate = sanitize_overlay(
        source,
        "Codex-Transactional-Test",
        {"brownoutThresholds": {"latency": 80}},
    )

    assert candidate["name"] == "Codex-Transactional-Test"
    assert "id" not in candidate
    assert "overlayId" not in candidate
    assert "createdBy" not in candidate
    assert candidate["brownoutThresholds"] == {
        "loss": 1.0,
        "latency": 80,
        "jitter": 50,
    }


def test_overlay_plan_has_expiring_plan_specific_confirmation() -> None:
    plan = prepare_overlay_plan(SOURCE, "Codex-Test")

    assert plan.plan_id in plan.confirmation
    assert plan.target_name in plan.confirmation
    assert plan.diff
    store = OverlayPlanStore()
    store.put(plan)
    assert store.get(plan.plan_id) is plan


def test_overlay_validation_rejects_empty_or_same_name() -> None:
    with pytest.raises(ValueError, match="differ"):
        sanitize_overlay(SOURCE, "RealTime", {})
    with pytest.raises(ValueError, match="topology"):
        sanitize_overlay({"id": 1, "name": "Source", "match": {}}, "Target", {})


def test_extract_overlays_handles_nested_orchestrator_wrappers() -> None:
    assert extract_overlays({"data": {"data": [SOURCE]}}) == [SOURCE]
    assert extract_overlays({"result": {"overlays": [SOURCE]}}) == [SOURCE]


def test_transactional_overlay_create_verify_and_rollback() -> None:
    class FakeClient:
        def __init__(self):
            self.overlays = [dict(SOURCE)]

        def resolve_active_profile(self):
            return "9.6"

        def call(self, version, operation_id, path_params=None, json_body=None, **query):
            del version, path_params
            if operation_id == "orchestrator.getoverlay323":
                return {"data": {"data": list(self.overlays)}}
            if operation_id == "orchestrator.addnewoverlay315":
                created = {**json_body, "id": 99}
                self.overlays.append(created)
                return created
            if operation_id == "orchestrator.deleteexistingoverlay322":
                overlay_id = str(query["overlayId"])
                self.overlays = [
                    row for row in self.overlays if str(row.get("id")) != overlay_id
                ]
                return {"deleted": overlay_id}
            raise AssertionError(operation_id)

    from ec_mcp import server as server_module

    fake = FakeClient()
    original_create = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: fake
    try:
        server = create_server(
            Settings(
                orchestrator_url="https://orch.example",
                allow_write_tools=True,
                allow_dangerous_writes=True,
            )
        )
        prepared = asyncio.run(
            server.call_tool(
                "prepare_overlay_clone",
                {
                    "source_overlay": "RealTime",
                    "target_name": "Codex-Transactional-Test",
                    "overrides_json": '{"brownoutThresholds":{"latency":80}}',
                },
            )
        )
        prepared_payload = json.loads(prepared.content[0].text)
        plan = prepared_payload["plan"]

        applied = asyncio.run(
            server.call_tool(
                "apply_overlay_plan",
                {
                    "plan_id": plan["plan_id"],
                    "confirmation": plan["confirmation_required"],
                    "confirm": True,
                },
            )
        )
        applied_payload = json.loads(applied.content[0].text)
        assert applied_payload["applied"] is True
        assert applied_payload["verified"] is True
        assert applied_payload["health_check"]["overlay_id"] == "99"

        rolled_back = asyncio.run(
            server.call_tool(
                "rollback_overlay_plan",
                {
                    "plan_id": plan["plan_id"],
                    "confirmation": f'ROLLBACK {plan["plan_id"]}',
                    "confirm": True,
                },
            )
        )
        rollback_payload = json.loads(rolled_back.content[0].text)
        assert rollback_payload["rolled_back"] is True
        assert all(row["name"] != "Codex-Transactional-Test" for row in fake.overlays)
    finally:
        server_module.OrchestratorClient = original_create


def test_exact_operation_search_does_not_return_entire_orchestrator_catalog() -> None:
    server = create_server()
    result = asyncio.run(
        server.call_tool(
            "list_api_operations",
            {
                "version": "9.6",
                "search": "orchestrator.addnewoverlay315",
                "page_size": 20,
            },
        )
    )
    body = json.loads(result.content[0].text)["versions"]["9.6"]
    assert list(body["operations"]) == ["orchestrator.addnewoverlay315"]
    assert body["total_operations"] == 1

def test_sanitize_overlay_renames_acl_key_to_target_name() -> None:
    acl = json.dumps(
        {
            "options": {"merge": True, "delDependent": True},
            "data": {
                "Overlay_RealTime": {
                    "entry": {"1010": {"permit": True, "dscp": "ef"}}
                }
            },
        }
    )
    source = {**SOURCE, "match": {"overlayAcl": acl}}
    candidate = sanitize_overlay(source, "Codex-Lab-Test", {})
    renamed = json.loads(candidate["match"]["overlayAcl"])
    assert "Overlay_RealTime" not in renamed["data"]
    assert renamed["data"]["Overlay_Codex-Lab-Test"]["entry"]["1010"]["dscp"] == "ef"
