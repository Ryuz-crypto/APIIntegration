"""Transactional ZTP adoption helpers for discovered EdgeConnect appliances."""

from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

ZTP_DISCOVERED_READ = "orchestrator.getalldiscoveredappliances52"
ZTP_VALIDATE_OPERATION = "orchestrator.validatediscovereddeployment217"
ZTP_PRECONFIG_OPERATION = "orchestrator.applydiscoveredpreconfiguration255"
ZTP_APPROVE_OPERATION = "orchestrator.approvediscoveredappliances54"
ZTP_DENY_OPERATION = "orchestrator.denydiscoveredappliances55"
TEMPLATE_GROUPS_READ = "orchestrator.template748"


def extract_discovered(payload: Any) -> list[dict[str, Any]]:
    """Extract discovered appliance rows from common Orchestrator wrapper shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "discovered", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            rows = extract_discovered(value)
            if rows:
                return rows
    if "uuid" in payload and "applianceInfo" in payload:
        return [payload]
    return []


def select_discovered(payload: Any, uuid: str) -> dict[str, Any]:
    if not UUID_RE.fullmatch(uuid.strip()):
        raise ValueError(f"Invalid appliance UUID: {uuid!r}")
    matches = [row for row in extract_discovered(payload) if str(row.get("uuid", "")).lower() == uuid.strip().lower()]
    if not matches:
        raise ValueError(f"Discovered appliance with UUID {uuid!r} was not found")
    if len(matches) > 1:
        raise ValueError(f"Discovered appliance UUID {uuid!r} is ambiguous")
    row = matches[0]
    if row.get("approved"):
        raise ValueError("Appliance is already approved; adoption is not applicable")
    if row.get("denied"):
        raise ValueError("Appliance is already denied; remove the deny state before adoption")
    return row


def extract_template_groups(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "templateGroups", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            rows = extract_template_groups(value)
            if rows:
                return rows
    if "name" in payload and "templates" in payload:
        return [payload]
    return []


def select_template_group(payload: Any, group_name: str) -> dict[str, Any]:
    normalized = group_name.strip().casefold()
    matches = [row for row in extract_template_groups(payload) if str(row.get("name", "")).casefold() == normalized]
    if not matches:
        raise ValueError(f"Template group {group_name!r} was not found")
    if len(matches) > 1:
        raise ValueError(f"Template group {group_name!r} is ambiguous")
    return matches[0]


def derive_parameter_schema(template_group: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive an explicit parameter schema from a real template group object.

    The Orchestrator OpenAPI catalog contains placeholders for templates, so the
    real group object is the schema base: every template marked isSelected (or
    isselected) participates in adoption and requires values.
    """
    schema: list[dict[str, Any]] = []
    for template in template_group.get("templates", []):
        if not isinstance(template, dict):
            continue
        name = str(template.get("name") or "")
        if not name:
            continue
        selected = template.get("isSelected", template.get("isselected", False))
        schema.append(
            {
                "name": name,
                "display_name": str(template.get("displayName") or name),
                "selected": bool(selected),
                "build_version": str(template.get("buildVersion") or ""),
                "required": bool(selected),
            }
        )
    if not schema:
        raise ValueError("Template group has no templates; refuse empty schema")
    return schema


def validate_parameters(schema: list[dict[str, Any]], parameters_json: str) -> dict[str, Any]:
    try:
        parameters = json.loads(parameters_json) if parameters_json.strip() else {}
    except json.JSONDecodeError as error:
        raise ValueError(f"parameters_json is invalid: {error}") from error
    if not isinstance(parameters, dict):
        raise ValueError("parameters_json must be a JSON object")
    missing = [
        entry["name"]
        for entry in schema
        if entry["required"] and not str(parameters.get(entry["name"], "")).strip()
    ]
    if missing:
        raise ValueError(f"Missing required parameter values: {sorted(missing)}")
    unknown = sorted(set(parameters) - {entry["name"] for entry in schema})
    if unknown:
        raise ValueError(f"Unknown parameters not present in the template schema: {unknown}")
    return parameters


@dataclass
class ZtpPlan:
    plan_id: str
    appliance_uuid: str
    appliance_hostname: str
    appliance_serial: str
    template_group: str
    schema: list[dict[str, Any]]
    parameters: dict[str, Any]
    confirmation: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 900)
    status: str = "prepared"
    validate_result: Any = None
    preconfig_result: Any = None
    approve_result: Any = None
    adopted_ne_pk: str = ""
    deny_available: bool = False
    health_check: dict[str, Any] = field(default_factory=dict)

    def public(self, include_details: bool = True) -> dict[str, Any]:
        result = {
            "plan_id": self.plan_id,
            "status": self.status,
            "appliance": {
                "uuid": self.appliance_uuid,
                "hostname": self.appliance_hostname,
                "serial": self.appliance_serial,
            },
            "template_group": self.template_group,
            "confirmation_required": self.confirmation,
            "expires_at_epoch": int(self.expires_at),
            "deny_available": self.deny_available,
        }
        if include_details:
            result["schema"] = self.schema
            result["parameters"] = self.parameters
        if self.validate_result is not None:
            result["validate_result"] = self.validate_result
        if self.preconfig_result is not None:
            result["preconfig_result"] = self.preconfig_result
        if self.approve_result is not None:
            result["approve_result"] = self.approve_result
        if self.adopted_ne_pk:
            result["adopted_ne_pk"] = self.adopted_ne_pk
            result["rollback_confirmation"] = f"ROLLBACK {self.plan_id}"
        if self.health_check:
            result["health_check"] = self.health_check
        return result


class ZtpPlanStore:
    """Plan store with optional disk persistence so plans survive restarts."""

    def __init__(self, ttl_seconds: int = 900, max_plans: int = 50, state_dir: str | None = None):
        self.ttl_seconds = ttl_seconds
        self.max_plans = max_plans
        self._plans: dict[str, ZtpPlan] = {}
        self._state_dir = Path(state_dir).expanduser() if state_dir else None
        if self._state_dir:
            try:
                self._state_dir.mkdir(parents=True, exist_ok=True)
                for path in sorted(self._state_dir.glob("*.json")):
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    plan = ZtpPlan(
                        plan_id=payload["plan_id"],
                        appliance_uuid=payload["appliance_uuid"],
                        appliance_hostname=payload["appliance_hostname"],
                        appliance_serial=payload["appliance_serial"],
                        template_group=payload["template_group"],
                        schema=payload["schema"],
                        parameters=payload["parameters"],
                        confirmation=payload["confirmation"],
                        created_at=payload["created_at"],
                        expires_at=payload["expires_at"],
                        status=payload["status"],
                        validate_result=payload.get("validate_result"),
                        preconfig_result=payload.get("preconfig_result"),
                        approve_result=payload.get("approve_result"),
                        adopted_ne_pk=payload.get("adopted_ne_pk", ""),
                        deny_available=payload.get("deny_available", False),
                        health_check=payload.get("health_check", {}),
                    )
                    self._plans[plan.plan_id] = plan
            except (OSError, json.JSONDecodeError, KeyError):
                self._plans = {}

    def _path(self, plan_id: str) -> Path | None:
        if not self._state_dir:
            return None
        return self._state_dir / f"{plan_id}.json"

    def _persist(self, plan: ZtpPlan) -> None:
        path = self._path(plan.plan_id)
        if path is None:
            return
        try:
            path.write_text(json.dumps(plan.__dict__, default=str), encoding="utf-8")
        except OSError:
            pass

    def _purge(self) -> None:
        now = time.time()
        self._plans = {
            plan_id: plan
            for plan_id, plan in self._plans.items()
            if plan.expires_at > now or plan.status in {"applied", "rolled_back", "denied"}
        }
        while len(self._plans) > self.max_plans:
            oldest = min(self._plans, key=lambda key: self._plans[key].created_at)
            plan = self._plans.pop(oldest, None)
            if plan:
                path = self._path(plan.plan_id)
                if path:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass

    def put(self, plan: ZtpPlan) -> None:
        self._purge()
        self._plans[plan.plan_id] = plan
        self._persist(plan)

    def get(self, plan_id: str) -> ZtpPlan:
        self._purge()
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError("Unknown or expired ZTP plan")
        if plan.expires_at <= time.time() and plan.status == "prepared":
            raise ValueError("ZTP plan expired; prepare a new plan")
        return plan


def prepare_ztp_plan(
    discovered_row: dict[str, Any],
    template_group: dict[str, Any],
    group_name: str,
    parameters_json: str,
    ttl_seconds: int = 900,
) -> ZtpPlan:
    info = discovered_row.get("applianceInfo") or {}
    schema = derive_parameter_schema(template_group)
    parameters = validate_parameters(schema, parameters_json)
    plan_id = secrets.token_hex(6)
    hostname = str(info.get("hostname") or "")
    serial = str(info.get("serial") or "")
    confirmation = f"ADOPTAR {plan_id} {discovered_row.get('uuid', '')} {group_name}"
    return ZtpPlan(
        plan_id=plan_id,
        appliance_uuid=str(discovered_row.get("uuid", "")),
        appliance_hostname=hostname,
        appliance_serial=serial,
        template_group=group_name,
        schema=schema,
        parameters=parameters,
        confirmation=confirmation,
        expires_at=time.time() + ttl_seconds,
    )
