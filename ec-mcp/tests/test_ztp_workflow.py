from __future__ import annotations

import base64
import json

import pytest

from ec_mcp.config import Settings
from ec_mcp.server import create_server
from ec_mcp.ztp_workflow import (
    ZtpPlanStore,
    extract_preconfig_id,
    prepare_ztp_plan,
    select_discovered,
    validate_preconfig_yaml,
)

UUID = "c3cdb65b-a891-48ed-aeb0-bfe390099d8f"

DISCOVERED_ROW = {
    "id": 54,
    "uuid": UUID,
    "approved": False,
    "denied": False,
    "applianceInfo": {
        "hostname": "silverpeak",
        "model": "EC-V",
        "serial": "00-1B-BC-46-2C-04",
        "softwareVersion": "9.6.2.1_107093",
        "deviceType": "APPLIANCE",
    },
}

TEMPLATE_GROUPS = {"data": [{"name": "Default Template Group", "templates": []}]}
OVERLAYS = {
    "data": [
        {"id": 1, "name": "RealTime"},
        {"id": 2, "name": "CriticalApps"},
        {"id": 3, "name": "BulkApps"},
        {"id": 4, "name": "DefaultOverlay"},
    ]
}

PRECONFIG_YAML = """applianceInfo:
  hostname: "EC3"
  group: "NFR-DemoLive"
  networkRole: "non-hub"
  region:
  location:
    address: ""
    address2: ""
    city: "Calimaya"
    state: "Estado de Mexico"
    zipCode: "52200"
    country: "Mexico"
    latitude:
    longitude:
  contact:
    name: ""
    email: ""
    phoneNumber: ""
ecLicensing:
  useDefaultAccount: true
  bandwidthLevel: base
  boost: 1000000
deploymentInfo:
  deploymentMode: "inline-router"
  totalOutboundBandwidth: 300000
  totalInboundBandwidth: 300000
  deploymentInterfaces:
    - interfaceName: lan0
      interfaceType: lan
      ipAddressMask: 172.16.200.1/24
      zone: DATOS
    - interfaceName: wan0
      interfaceLabel: L2L1
      interfaceType: wan
      ipAddressMask: 10.50.10.1/24
      nextHop: 10.50.10.2
      outboundMaxBandwidth: 100000
      inboundMaxBandwidth: 100000
      firewallMode: statefulSNAT
      behindNat: none
      zone: L2L1
templateGroups:
  groups:
    - "Default Template Group"
businessIntentOverlays:
  overlays:
    - "RealTime"
    - "CriticalApps"
    - "BulkApps"
    - "DefaultOverlay"
"""


class FakeZtpClient:
    def __init__(
        self,
        discovered=None,
        template_groups=None,
        overlays=None,
        validate_error=False,
        create_error=False,
        preconfig_error=False,
        approve_error=False,
        approve_marks=True,
        deny_marks=True,
    ):
        self.discovered = discovered if discovered is not None else [dict(DISCOVERED_ROW)]
        self.template_groups = template_groups if template_groups is not None else TEMPLATE_GROUPS
        self.overlays = overlays if overlays is not None else OVERLAYS
        self.validate_error = validate_error
        self.create_error = create_error
        self.preconfig_error = preconfig_error
        self.approve_error = approve_error
        self.approve_marks = approve_marks
        self.deny_marks = deny_marks
        self.calls: list[str] = []
        self.created_preconfig: dict | None = None

    def resolve_active_profile(self):
        return "9.6"

    def call(self, version, operation_id, path_params=None, json_body=None, **query):
        del version, path_params
        self.calls.append((operation_id, json_body, query))
        if operation_id == "orchestrator.getalldiscoveredappliances52":
            return {"data": self.discovered}
        if operation_id == "orchestrator.template748":
            return self.template_groups
        if operation_id == "orchestrator.getoverlay323":
            return self.overlays
        if operation_id == "orchestrator.getmatchingpreconfiguration250":
            if self.validate_error:
                raise RuntimeError("Invalid preconfiguration")
            return {"valid": True}
        if operation_id == "orchestrator.createpreconfiguration247_1":
            if self.create_error:
                raise RuntimeError("create failed")
            self.created_preconfig = json_body
            return {"id": 77, "name": json_body.get("name")}
        if operation_id == "orchestrator.applydiscoveredpreconfiguration255":
            if self.preconfig_error:
                raise RuntimeError("apply failed")
            return {"applied": True}
        if operation_id == "orchestrator.approvediscoveredappliances54":
            if self.approve_error:
                raise RuntimeError("approve failed")
            if self.approve_marks:
                self.discovered = [dict(row, approved=True) for row in self.discovered]
            return {"approved": True}
        if operation_id == "orchestrator.denydiscoveredappliances55":
            if self.deny_marks:
                self.discovered = [dict(row, denied=True, approved=False) for row in self.discovered]
            return {"denied": True}
        if operation_id == "orchestrator.deletepreconfiguration251":
            return {"deleted": True}
        if operation_id == "orchestrator.getpreconfigurationapplystatus254":
            return {
                "data": {
                    "result": [
                        {"name": "Add Appliance", "completionStatus": True, "taskStatus": 2, "nePk": "15.NE"},
                        {"name": "Rebooting Appliance", "completionStatus": True, "taskStatus": 2, "nePk": "15.NE"},
                    ]
                }
            }
        raise AssertionError(f"unexpected operation {operation_id}")

    def list_appliances(self):
        if "applydiscoveredpreconfiguration255" in [c[0] for c in self.calls]:
            return [
                {
                    "nePk": "15.NE",
                    "name": "EC3",
                    "serial_number": "00-1B-BC-46-2C-04",
                    "state": 1,
                }
            ]
        return []


def _tool(server_fixture, name, **kwargs):
    import asyncio

    return asyncio.run(server_fixture.call_tool(name, kwargs))


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setenv("EC_ALLOW_WRITE_TOOLS", "true")
    monkeypatch.setenv("EC_ALLOW_DANGEROUS_WRITES", "true")
    return create_server(
        Settings(
            orchestrator_url="https://orch.example",
            allow_write_tools=True,
            allow_dangerous_writes=True,
        )
    )


def _set_client(monkeypatch, client):
    import ec_mcp.server as server_module

    monkeypatch.setattr(server_module, "OrchestratorClient", lambda *args, **kwargs: client)


def _parse(result):
    text = result if isinstance(result, str) else result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": text}


def test_extract_preconfig_id_shapes():
    assert extract_preconfig_id({"id": 5}) == "5"
    assert extract_preconfig_id({"data": {"preconfigId": "9"}}) == "9"
    assert extract_preconfig_id(12) == "12"
    assert extract_preconfig_id({"data": None}) == ""


def test_select_discovered_rejects_invalid_uuid():
    with pytest.raises(ValueError, match="Invalid appliance UUID"):
        select_discovered({"data": [DISCOVERED_ROW]}, "not-a-uuid")


def test_select_discovered_rejects_unknown_uuid():
    with pytest.raises(ValueError, match="was not found"):
        select_discovered({"data": [DISCOVERED_ROW]}, "11111111-2222-3333-4444-555555555555")


def test_select_discovered_rejects_approved():
    row = dict(DISCOVERED_ROW, approved=True)
    with pytest.raises(ValueError, match="already approved"):
        select_discovered({"data": [row]}, UUID)


def test_select_discovered_rejects_denied():
    row = dict(DISCOVERED_ROW, denied=True)
    with pytest.raises(ValueError, match="already denied"):
        select_discovered({"data": [row]}, UUID)


def test_validate_preconfig_yaml_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_preconfig_yaml("")
    with pytest.raises(ValueError, match="empty"):
        validate_preconfig_yaml("   \n")


def test_validate_preconfig_yaml_rejects_invalid_yaml():
    with pytest.raises(ValueError, match="not valid YAML"):
        validate_preconfig_yaml("applianceInfo: [unclosed")


def test_validate_preconfig_yaml_requires_group():
    yaml_text = PRECONFIG_YAML.replace('group: "NFR-DemoLive"', "group:")
    with pytest.raises(ValueError, match="group is required"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_bad_network_role():
    yaml_text = PRECONFIG_YAML.replace('networkRole: "non-hub"', 'networkRole: "edge"')
    with pytest.raises(ValueError, match="networkRole"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_single_coordinate():
    yaml_text = PRECONFIG_YAML.replace("    latitude:\n", "    latitude: 36.7\n")
    with pytest.raises(ValueError, match="latitude"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_wan_missing_next_hop():
    yaml_text = PRECONFIG_YAML.replace("      nextHop: 10.50.10.2\n", "      nextHop:\n")
    with pytest.raises(ValueError, match="wan interfaces require nextHop"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_bad_firewall_mode():
    yaml_text = PRECONFIG_YAML.replace("firewallMode: statefulSNAT", "firewallMode: magic")
    with pytest.raises(ValueError, match="firewallMode"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_lan_without_ip():
    yaml_text = PRECONFIG_YAML.replace("      ipAddressMask: 172.16.200.1/24\n", "      ipAddressMask:\n")
    with pytest.raises(ValueError, match="lan interfaces require ipAddressMask"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_bad_bandwidth():
    yaml_text = PRECONFIG_YAML.replace("totalOutboundBandwidth: 300000", "totalOutboundBandwidth: 0")
    with pytest.raises(ValueError, match="totalOutboundBandwidth"):
        validate_preconfig_yaml(yaml_text)


def test_validate_preconfig_yaml_rejects_bad_deployment_mode():
    yaml_text = PRECONFIG_YAML.replace('deploymentMode: "inline-router"', 'deploymentMode: "inline-bridge"')
    with pytest.raises(ValueError, match="inline-router"):
        validate_preconfig_yaml(yaml_text)


def test_prepare_ztp_plan_verifies_template_groups():
    with pytest.raises(ValueError, match=r"Template groups .* not found"):
        prepare_ztp_plan(DISCOVERED_ROW, PRECONFIG_YAML, {"data": [{"name": "Other"}]}, OVERLAYS)


def test_prepare_ztp_plan_rejects_unknown_overlays_when_listing_available():
    partial = {"data": [{"name": "RealTime"}, {"name": "CriticalApps"}]}
    with pytest.raises(ValueError, match=r"Overlays .* not found"):
        prepare_ztp_plan(DISCOVERED_ROW, PRECONFIG_YAML, TEMPLATE_GROUPS, partial)


def test_prepare_ztp_plan_warns_when_overlay_listing_empty():
    plan = prepare_ztp_plan(DISCOVERED_ROW, PRECONFIG_YAML, TEMPLATE_GROUPS, {"data": []})
    assert plan.warnings and "could not verify overlay names" in plan.warnings[0]
    assert plan.confirmation.startswith("ADOPTAR ")


def test_prepare_ztp_plan_builds_confirmation():
    plan = prepare_ztp_plan(DISCOVERED_ROW, PRECONFIG_YAML, TEMPLATE_GROUPS, OVERLAYS)
    assert plan.preconfig_name == f"Codex-ZTP-{plan.plan_id}"
    assert plan.confirmation == f"ADOPTAR {plan.plan_id} 54 {plan.preconfig_name}"
    assert plan.preconfig_yaml == PRECONFIG_YAML


def test_plan_store_roundtrip(tmp_path):
    plan = prepare_ztp_plan(DISCOVERED_ROW, PRECONFIG_YAML, TEMPLATE_GROUPS, OVERLAYS)
    store = ZtpPlanStore(state_dir=str(tmp_path))
    store.put(plan)
    restored = ZtpPlanStore(state_dir=str(tmp_path)).get(plan.plan_id)
    assert restored.preconfig_yaml == PRECONFIG_YAML
    assert restored.preconfig_name == plan.preconfig_name


def _encode_config(yaml_text):
    return base64.b64encode(yaml_text.encode("utf-8")).decode("ascii")


def test_full_transactional_cycle(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module

    fake = FakeZtpClient()
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
                "prepare_ztp_adoption",
                {"appliance_selector": "001BBC462C04", "preconfig_yaml": PRECONFIG_YAML},
            )
        )
        payload = json.loads(prepared.content[0].text)
        plan = payload["plan"]
        assert payload["dry_run"] is True
        assert plan["preconfig_name"] == f"Codex-ZTP-{plan['plan_id']}"
        assert plan["confirmation_required"] == (
            f"ADOPTAR {plan['plan_id']} 54 {plan['preconfig_name']}"
        )

        applied = asyncio.run(
            server.call_tool(
                "apply_ztp_plan",
                {
                    "plan_id": plan["plan_id"],
                    "confirmation": plan["confirmation_required"],
                    "confirm": True,
                },
            )
        )
        applied_payload = json.loads(applied.content[0].text)
        assert applied_payload["applied"] is True
        assert applied_payload["verification"] == "async"
        created_id = applied_payload["plan"]["created_preconfig_id"]
        assert created_id == "77"
        apply_call = next(c for c in fake.calls if c[0] == "orchestrator.applydiscoveredpreconfiguration255")
        assert apply_call[2].get("discoveredId") == "54"
        assert fake.created_preconfig["name"] == plan["preconfig_name"]
        assert base64.b64decode(fake.created_preconfig["preConfig"]).decode() == PRECONFIG_YAML
        assert "orchestrator.applydiscoveredpreconfiguration255" in [c[0] for c in fake.calls]

        rolled_back = asyncio.run(
            server.call_tool(
                "rollback_ztp_plan",
                {
                    "plan_id": plan["plan_id"],
                    "confirmation": f"ROLLBACK {plan['plan_id']}",
                    "confirm": True,
                },
            )
        )
        rollback_payload = json.loads(rolled_back.content[0].text)
        assert rollback_payload["rolled_back"] is True
        assert "orchestrator.deletepreconfiguration251" in [c[0] for c in fake.calls]
    finally:
        server_module.OrchestratorClient = original_create


def test_apply_rejects_wrong_confirmation(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module

    fake = FakeZtpClient()
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
                "prepare_ztp_adoption",
                {"appliance_selector": "001BBC462C04", "preconfig_yaml": PRECONFIG_YAML},
            )
        )
        plan = json.loads(prepared.content[0].text)["plan"]
        applied = asyncio.run(
            server.call_tool(
                "apply_ztp_plan",
                {"plan_id": plan["plan_id"], "confirmation": "wrong phrase", "confirm": True},
            )
        )
        text = applied.content[0].text
        assert text.startswith("Error:")
        write_calls = [
            c[0]
            for c in fake.calls
            if not c[0].endswith(("52", "748", "323"))
        ]
        assert write_calls == []
    finally:
        server_module.OrchestratorClient = original_create


def test_apply_failure_after_create_marks_verification_failed(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module

    fake = FakeZtpClient(preconfig_error=True)
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
                "prepare_ztp_adoption",
                {"appliance_selector": "001BBC462C04", "preconfig_yaml": PRECONFIG_YAML},
            )
        )
        plan = json.loads(prepared.content[0].text)["plan"]
        applied = asyncio.run(
            server.call_tool(
                "apply_ztp_plan",
                {
                    "plan_id": plan["plan_id"],
                    "confirmation": plan["confirmation_required"],
                    "confirm": True,
                },
            )
        )
        assert applied.content[0].text.startswith("Error:")
    finally:
        server_module.OrchestratorClient = original_create


def test_rollback_only_for_reversible_plans(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module

    fake = FakeZtpClient()
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
                "prepare_ztp_adoption",
                {"appliance_selector": "001BBC462C04", "preconfig_yaml": PRECONFIG_YAML},
            )
        )
        plan = json.loads(prepared.content[0].text)["plan"]
        rolled = asyncio.run(
            server.call_tool(
                "rollback_ztp_plan",
                {"plan_id": plan["plan_id"], "confirmation": f"ROLLBACK {plan['plan_id']}", "confirm": True},
            )
        )
        assert rolled.content[0].text.startswith("Error:")
    finally:
        server_module.OrchestratorClient = original_create


def test_select_discovered_by_serial_undashed():
    row = select_discovered({"data": [DISCOVERED_ROW]}, "001BBC462C04")
    assert row["uuid"] == UUID


def test_select_discovered_by_serial_dashed():
    row = select_discovered({"data": [DISCOVERED_ROW]}, "00-1B-BC-46-2C-04")
    assert row["uuid"] == UUID


def test_select_discovered_rejects_unknown_serial():
    with pytest.raises(ValueError, match="was not found"):
        select_discovered({"data": [DISCOVERED_ROW]}, "001BBC999999")


def test_normalize_serial_handles_both_forms():
    from ec_mcp.ztp_workflow import normalize_serial

    assert normalize_serial("001BBC462C04") == normalize_serial("00-1B-BC-46-2C-04")
    assert normalize_serial("001bbc462c04") == "001BBC462C04"


def test_prepare_ztp_plan_carries_discovered_row_id():
    plan = prepare_ztp_plan(DISCOVERED_ROW, PRECONFIG_YAML, TEMPLATE_GROUPS, OVERLAYS)
    assert plan.discovered_row_id == "54"
    assert plan.confirmation.endswith(plan.preconfig_name)
    assert " 54 " in plan.confirmation


def test_render_bulk_yaml_substitutes_placeholders():
    from ec_mcp.ztp_workflow import render_bulk_yaml

    base = PRECONFIG_YAML.replace('hostname: "EC3"', 'hostname: "{{hostname}}"')
    rendered = render_bulk_yaml(base, "EC10", "Calimaya")
    assert 'hostname: "EC10"' in rendered
    assert "{{" not in rendered


def test_render_bulk_yaml_requires_hostname():
    from ec_mcp.ztp_workflow import render_bulk_yaml

    with pytest.raises(ValueError, match="hostname"):
        render_bulk_yaml("hostname: {{hostname}}", "", "")


def test_full_bulk_cycle(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module

    second_row = dict(
        DISCOVERED_ROW,
        id=55,
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        applianceInfo=dict(
            DISCOVERED_ROW["applianceInfo"], serial="00-1B-BC-46-2C-05"
        ),
    )
    fake = FakeZtpClient(discovered=[dict(DISCOVERED_ROW), second_row])
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
        base = PRECONFIG_YAML.replace('hostname: "EC3"', 'hostname: "{{hostname}}"')
        prepared = asyncio.run(
            server.call_tool(
                "prepare_bulk_ztp_adoption",
                {
                    "appliance_selectors": "001BBC462C04, 001BBC462C05",
                    "base_preconfig_yaml": base,
                    "hostnames": "EC10,EC11",
                },
            )
        )
        payload = json.loads(prepared.content[0].text)
        assert payload["dry_run"] is True
        bulk = payload["bulk"]
        assert bulk["appliance_count"] == 2
        assert len(payload["plans"]) == 2
        assert payload["plans"][0]["appliance"]["discovered_row_id"] == "54"
        assert payload["plans"][1]["appliance"]["discovered_row_id"] == "55"

        applied = asyncio.run(
            server.call_tool(
                "apply_bulk_ztp_plan",
                {
                    "bulk_id": bulk["bulk_id"],
                    "confirmation": bulk["confirmation_required"],
                    "confirm": True,
                },
            )
        )
        applied_payload = json.loads(applied.content[0].text)
        assert applied_payload["applied"] == 2
        assert applied_payload["total"] == 2
        assert all(r["applied"] for r in applied_payload["results"])
        apply_calls = [c for c in fake.calls if c[0] == "orchestrator.applydiscoveredpreconfiguration255"]
        assert [c[2].get("discoveredId") for c in apply_calls] == ["54", "55"]
        configs = [base64.b64decode(c[1]["preConfig"]).decode() for c in fake.calls
                   if c[0] == "orchestrator.createpreconfiguration247_1"]
        assert 'hostname: "EC10"' in configs[0]
        assert 'hostname: "EC11"' in configs[1]
    finally:
        server_module.OrchestratorClient = original_create


def test_bulk_prepare_rejects_mismatched_hostnames(monkeypatch):
    import asyncio

    import ec_mcp.server as server_module

    fake = FakeZtpClient()
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
                "prepare_bulk_ztp_adoption",
                {
                    "appliance_selectors": "001BBC462C04",
                    "base_preconfig_yaml": PRECONFIG_YAML,
                    "hostnames": "EC10,EC11",
                },
            )
        )
        assert prepared.content[0].text.startswith("Error:")
    finally:
        server_module.OrchestratorClient = original_create
