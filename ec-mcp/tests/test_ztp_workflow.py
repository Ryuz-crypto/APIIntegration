from __future__ import annotations

import asyncio
import json

import pytest

from ec_mcp.config import Settings
from ec_mcp.server import create_server
from ec_mcp.ztp_workflow import (
    ZtpPlanStore,
    derive_parameter_schema,
    extract_discovered,
    prepare_ztp_plan,
    select_discovered,
    select_template_group,
    validate_parameters,
)

UUID = "9e91cc5d-45e2-43a5-aea7-cb3f02fc42b9"

DISCOVERED_ROW = {
    "id": 6,
    "uuid": UUID,
    "approved": False,
    "denied": False,
    "applianceInfo": {
        "hostname": "K-4-EC-1B",
        "model": "EC-V",
        "serial": "001BBC1F5777",
        "softwareVersion": "9.1.4.2_92345",
        "deviceType": "APPLIANCE",
    },
}

TEMPLATE_GROUP = {
    "name": "Default Template Group",
    "templates": [
        {
            "name": "datetime",
            "displayName": "Date/Time",
            "isSelected": True,
            "buildVersion": "6.2.3.0_0000",
        },
        {"name": "banners", "displayName": "Banner Messages", "isSelected": False},
    ],
}


class FakeZtpClient:
    def __init__(
        self,
        discovered=None,
        template_groups=None,
        validate_error=False,
        preconfig_error=False,
        approve_error=False,
        approve_marks=True,
        deny_marks=True,
    ):
        self.discovered = discovered if discovered is not None else [dict(DISCOVERED_ROW)]
        self.template_groups = (
            template_groups
            if template_groups is not None
            else [{"name": "Default Template Group", "templates": TEMPLATE_GROUP["templates"]}]
        )
        self.validate_error = validate_error
        self.preconfig_error = preconfig_error
        self.approve_error = approve_error
        self.approve_marks = approve_marks
        self.deny_marks = deny_marks
        self.calls: list[str] = []

    def resolve_active_profile(self):
        return "9.6"

    def call(self, version, operation_id, path_params=None, json_body=None, **query):
        del version, path_params, json_body
        self.calls.append(operation_id)
        if operation_id == "orchestrator.getalldiscoveredappliances52":
            return {"data": {"data": [dict(row) for row in self.discovered]}}
        if operation_id == "orchestrator.template748":
            return {"data": [dict(group) for group in self.template_groups]}
        if operation_id == "orchestrator.validatediscovereddeployment217":
            if self.validate_error:
                raise RuntimeError("validation failed")
            return {"valid": True}
        if operation_id == "orchestrator.applydiscoveredpreconfiguration255":
            if self.preconfig_error:
                raise RuntimeError("preconfiguration failed")
            return {"ok": True}
        if operation_id == "orchestrator.approvediscoveredappliances54":
            if self.approve_error:
                raise RuntimeError("adoption failed")
            for row in self.discovered:
                if str(row.get("uuid", "")).lower() == str(query.get("id", "")).lower():
                    row["approved"] = self.approve_marks
            return {"ok": True}
        if operation_id == "orchestrator.denydiscoveredappliances55":
            if not self.deny_marks:
                return {"ok": False}
            for row in self.discovered:
                if str(row.get("uuid", "")).lower() == str(query.get("id", "")).lower():
                    row["denied"] = True
                    row["approved"] = False
            return {"ok": True}
        raise AssertionError(operation_id)


def _build_server(fake):
    from ec_mcp import server as server_module

    original = server_module.OrchestratorClient
    server_module.OrchestratorClient = lambda *args, **kwargs: fake
    server = create_server(
        Settings(
            orchestrator_url="https://orch.example",
            allow_write_tools=True,
            allow_dangerous_writes=True,
        )
    )
    return server, original


def _tool(server, name, arguments):
    text = asyncio.run(server.call_tool(name, arguments)).content[0].text
    if text.startswith("Error:"):
        return text
    return json.loads(text)


def test_extract_discovered_handles_nested_wrappers():
    assert extract_discovered({"data": {"data": [DISCOVERED_ROW]}}) == [DISCOVERED_ROW]
    assert extract_discovered({"result": {"discovered": [DISCOVERED_ROW]}}) == [DISCOVERED_ROW]


def test_select_discovered_rejects_invalid_uuid():
    with pytest.raises(ValueError, match="Invalid appliance UUID"):
        select_discovered({"data": [DISCOVERED_ROW]}, "not-a-uuid")


def test_select_discovered_rejects_unknown_uuid():
    with pytest.raises(ValueError, match="was not found"):
        select_discovered({"data": [DISCOVERED_ROW]}, "11111111-2222-3333-4444-555555555555")


def test_select_discovered_rejects_already_approved():
    row = {**DISCOVERED_ROW, "approved": True}
    with pytest.raises(ValueError, match="already approved"):
        select_discovered({"data": [row]}, UUID)


def test_select_template_group_rejects_unknown_group():
    with pytest.raises(ValueError, match="was not found"):
        select_template_group({"data": []}, "Missing Group")


def test_derive_parameter_schema_rejects_empty_group():
    with pytest.raises(ValueError, match="empty schema"):
        derive_parameter_schema({"name": "Empty", "templates": []})


def test_validate_parameters_rejects_missing_required_values():
    schema = derive_parameter_schema(TEMPLATE_GROUP)
    with pytest.raises(ValueError, match="Missing required parameter values"):
        validate_parameters(schema, "{}")
    with pytest.raises(ValueError, match="Missing required parameter values"):
        validate_parameters(schema, '{"datetime": ""}')


def test_validate_parameters_rejects_unknown_parameters():
    schema = derive_parameter_schema(TEMPLATE_GROUP)
    with pytest.raises(ValueError, match="Unknown parameters"):
        validate_parameters(schema, '{"datetime": {"zone": "UTC"}, "ghost": 1}')


def test_prepare_ztp_plan_binds_confirmation_to_uuid_template_and_plan():
    row = dict(DISCOVERED_ROW)
    plan = prepare_ztp_plan(row, TEMPLATE_GROUP, "Default Template Group", '{"datetime": {"zone": "UTC"}}')
    assert plan.plan_id in plan.confirmation
    assert UUID in plan.confirmation
    assert "Default Template Group" in plan.confirmation
    store = ZtpPlanStore()
    store.put(plan)
    assert store.get(plan.plan_id) is plan


def test_ztp_plan_store_persists_to_disk(tmp_path):
    row = dict(DISCOVERED_ROW)
    plan = prepare_ztp_plan(row, TEMPLATE_GROUP, "Default Template Group", '{"datetime": {"zone": "UTC"}}')
    store = ZtpPlanStore(state_dir=str(tmp_path))
    store.put(plan)
    restored = ZtpPlanStore(state_dir=str(tmp_path))
    assert restored.get(plan.plan_id).plan_id == plan.plan_id
    assert restored.get(plan.plan_id).appliance_uuid == UUID


def test_transactional_ztp_adoption_verify_and_rollback():
    fake = FakeZtpClient()
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        applied = _tool(
            server,
            "apply_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": plan["confirmation_required"],
                "confirm": True,
            },
        )
        assert applied["applied"] is True
        assert applied["verified"] is True
        verified = _tool(server, "verify_ztp_plan", {"plan_id": plan["plan_id"]})
        assert verified["verified"] is True
        rolled_back = _tool(
            server,
            "rollback_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": f'ROLLBACK {plan["plan_id"]}',
                "confirm": True,
            },
        )
        assert rolled_back["rolled_back"] is True
        assert rolled_back["verified_denied"] is True
    finally:
        server_module.OrchestratorClient = original


def test_apply_ztp_plan_rejects_wrong_confirmation():
    fake = FakeZtpClient()
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        result = _tool(
            server,
            "apply_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": "wrong phrase",
                "confirm": True,
            },
        )
        assert result.startswith("Error:")
        assert "Confirmation phrase" in result
        write_calls = [call for call in fake.calls if "getall" not in call and "template748" not in call]
        assert write_calls == []
    finally:
        server_module.OrchestratorClient = original


def test_apply_ztp_plan_fails_when_validation_fails():
    fake = FakeZtpClient(validate_error=True)
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        result = _tool(
            server,
            "apply_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": plan["confirmation_required"],
                "confirm": True,
            },
        )
        assert result.startswith("Error:")
        assert "validation failed" in result
        assert "orchestrator.applydiscoveredpreconfiguration255" not in fake.calls
    finally:
        server_module.OrchestratorClient = original


def test_apply_ztp_plan_fails_after_preconfiguration_error():
    fake = FakeZtpClient(preconfig_error=True)
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        result = _tool(
            server,
            "apply_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": plan["confirmation_required"],
                "confirm": True,
            },
        )
        assert result.startswith("Error:")
        assert "preconfiguration failed" in result
        assert "orchestrator.approvediscoveredappliances54" not in fake.calls
    finally:
        server_module.OrchestratorClient = original


def test_apply_ztp_plan_reports_verification_failure_and_allows_deny():
    fake = FakeZtpClient(approve_marks=False)
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        applied = _tool(
            server,
            "apply_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": plan["confirmation_required"],
                "confirm": True,
            },
        )
        assert applied["applied"] is True
        assert applied["verified"] is False
        assert applied["deny_available"] is True
    finally:
        server_module.OrchestratorClient = original


def test_rollback_ztp_plan_fails_when_not_reversible():
    fake = FakeZtpClient()
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        result = _tool(
            server,
            "rollback_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": f'ROLLBACK {plan["plan_id"]}',
                "confirm": True,
            },
        )
        assert result.startswith("Error:")
        assert "nothing to roll back" in result
    finally:
        server_module.OrchestratorClient = original


def test_rollback_ztp_plan_detects_failed_deny():
    fake = FakeZtpClient(deny_marks=False)
    server, original = _build_server(fake)
    from ec_mcp import server as server_module

    try:
        prepared = _tool(
            server,
            "prepare_ztp_adoption",
            {
                "appliance_uuid": UUID,
                "template_group": "Default Template Group",
                "parameters_json": '{"datetime": {"zone": "UTC"}}',
            },
        )
        plan = prepared["plan"]
        _tool(
            server,
            "apply_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": plan["confirmation_required"],
                "confirm": True,
            },
        )
        result = _tool(
            server,
            "rollback_ztp_plan",
            {
                "plan_id": plan["plan_id"],
                "confirmation": f'ROLLBACK {plan["plan_id"]}',
                "confirm": True,
            },
        )
        assert result["rolled_back"] is False
        assert result["plan"]["status"] == "rollback_failed"
    finally:
        server_module.OrchestratorClient = original
