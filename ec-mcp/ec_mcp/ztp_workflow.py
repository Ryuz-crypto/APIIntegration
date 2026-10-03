"""Transactional ZTP adoption helpers for discovered EdgeConnect appliances.

The adoption is modeled after the real Orchestrator preconfiguration flow:
a preconfiguration is a named YAML document created via
``orchestrator.createpreconfiguration247_1`` and applied to a discovered
appliance via ``orchestrator.applydiscoveredpreconfiguration255`` using
``discoveredId`` + the real ``preconfigId`` returned at creation time.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

ZTP_DISCOVERED_READ = "orchestrator.getalldiscoveredappliances52"
ZTP_VALIDATE_OPERATION = "orchestrator.validatediscovereddeployment217"
ZTP_PRECONFIGS_READ = "orchestrator.getpreconfigurations246"
ZTP_PRECONFIG_CREATE = "orchestrator.createpreconfiguration247_1"
ZTP_PRECONFIG_VALIDATE = "orchestrator.getmatchingpreconfiguration250"
ZTP_PRECONFIG_APPLY = "orchestrator.applydiscoveredpreconfiguration255"
ZTP_PRECONFIG_STATUS = "orchestrator.getpreconfigurationapplystatus254"
ZTP_PRECONFIG_DELETE = "orchestrator.deletepreconfiguration251"
ZTP_APPROVE_OPERATION = "orchestrator.approvediscoveredappliances54"
ZTP_DENY_OPERATION = "orchestrator.denydiscoveredappliances55"
TEMPLATE_GROUPS_READ = "orchestrator.template748"

NETWORK_ROLES = {"non-hub", "hub", "nrhub"}
FIREWALL_MODES = {"All", "stateful", "statefulSNAT", "harden"}
INTERFACE_NAME_RE = re.compile(r"^(wan|lan|tlan|twan|twlan|blan|bwan)\d+(\.\d+)?$")
BANDWIDTH_MAX = 100_000_000


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


def _string_list(value: Any, section: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{section} must be a non-empty list")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{section} entries must be non-empty strings")
        names.append(item.strip())
    return names


def _require_section(preconfig: dict[str, Any], key: str) -> dict[str, Any]:
    section = preconfig.get(key)
    if not isinstance(section, dict):
        raise ValueError(f"preconfig_yaml is missing required section {key!r}")
    return section


def _bandwidth(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if not 1 <= value <= BANDWIDTH_MAX:
        raise ValueError(f"{label} must be between 1 and {BANDWIDTH_MAX}")
    return value


def _check_location(location: dict[str, Any]) -> None:
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    lat_set = latitude not in (None, "")
    lon_set = longitude not in (None, "")
    if lat_set != lon_set:
        raise ValueError("location.latitude and location.longitude must both be specified or both be empty")
    for name, value in (("latitude", latitude), ("longitude", longitude)):
        if value not in (None, "") and not isinstance(value, (int, float)):
            raise ValueError(f"location.{name} must be a number in decimal degrees")


def _check_interface(entry: Any, index: int) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"deploymentInterfaces[{index}] must be an object")
    label = f"deploymentInterfaces[{index}]"
    name = entry.get("interfaceName")
    if not isinstance(name, str) or not INTERFACE_NAME_RE.fullmatch(name):
        raise ValueError(f"{label}.interfaceName {name!r} is not a valid interface name")
    side = entry.get("interfaceType")
    if side not in {"lan", "wan"}:
        raise ValueError(f"{label}.interfaceType must be 'lan' or 'wan'")
    addressing = entry.get("addressingMode") or ""
    if addressing and addressing not in {"static", "dhcpv4", "dhcpv6", "slaac"}:
        raise ValueError(f"{label}.addressingMode {addressing!r} is invalid")
    if addressing in {"dhcpv4", "dhcpv6", "slaac"} and side == "wan":
        for field_name in ("ipAddressMask", "nextHop"):
            if str(entry.get(field_name) or "").strip():
                raise ValueError(f"{label}: {field_name} must be empty when addressingMode is {addressing}")
    if side == "lan" and not addressing:
        if not str(entry.get("ipAddressMask") or "").strip():
            raise ValueError(f"{label}: lan interfaces require ipAddressMask")
    if side == "wan":
        if not addressing:
            for field_name in ("nextHop", "inboundMaxBandwidth", "outboundMaxBandwidth", "firewallMode"):
                if entry.get(field_name) in (None, ""):
                    raise ValueError(f"{label}: wan interfaces require {field_name}")
        if entry.get("firewallMode") not in (None, "") and entry.get("firewallMode") not in FIREWALL_MODES:
            raise ValueError(f"{label}.firewallMode {entry.get('firewallMode')!r} is invalid")
        for field_name in ("inboundMaxBandwidth", "outboundMaxBandwidth"):
            value = entry.get(field_name)
            if value in (None, ""):
                continue
            if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < BANDWIDTH_MAX:
                raise ValueError(f"{label}.{field_name} must be an integer in ]0, {BANDWIDTH_MAX}[")


def validate_preconfig_yaml(yaml_text: str) -> dict[str, Any]:
    """Parse and validate a preconfiguration template YAML against the documented rules."""
    if not yaml_text or not yaml_text.strip():
        raise ValueError("preconfig_yaml is empty; refusing to send an empty preconfiguration")
    try:
        preconfig = yaml.safe_load(yaml_text)
    except yaml.YAMLError as error:
        raise ValueError(f"preconfig_yaml is not valid YAML: {error}") from error
    if not isinstance(preconfig, dict):
        raise ValueError("preconfig_yaml must be a YAML mapping at the top level")

    appliance_info = _require_section(preconfig, "applianceInfo")
    group = str(appliance_info.get("group") or "").strip()
    if not group:
        raise ValueError("applianceInfo.group is required and cannot be empty")
    hostname = str(appliance_info.get("hostname") or "").strip()
    if len(hostname) > 60:
        raise ValueError("applianceInfo.hostname must be at most 60 characters")
    role = appliance_info.get("networkRole")
    if role not in NETWORK_ROLES:
        raise ValueError(f"applianceInfo.networkRole must be one of {sorted(NETWORK_ROLES)}")
    _check_location(_require_section(appliance_info, "location"))
    _require_section(appliance_info, "contact")

    deployment = _require_section(preconfig, "deploymentInfo")
    _bandwidth(deployment.get("totalOutboundBandwidth"), "deploymentInfo.totalOutboundBandwidth")
    _bandwidth(deployment.get("totalInboundBandwidth"), "deploymentInfo.totalInboundBandwidth")
    mode = deployment.get("deploymentMode") or "inline-router"
    if mode != "inline-router":
        raise ValueError("deploymentInfo.deploymentMode: 'inline-router' is the only valid value")
    interfaces = deployment.get("deploymentInterfaces")
    if not isinstance(interfaces, list) or not interfaces:
        raise ValueError("deploymentInfo.deploymentInterfaces must be a non-empty list")
    for index, entry in enumerate(interfaces):
        _check_interface(entry, index)

    template_names: list[str] = []
    if "templateGroups" in preconfig:
        template_names = _string_list(_require_section(preconfig, "templateGroups").get("groups"), "templateGroups.groups")
    overlay_names: list[str] = []
    if "businessIntentOverlays" in preconfig:
        overlay_names = _string_list(
            _require_section(preconfig, "businessIntentOverlays").get("overlays"),
            "businessIntentOverlays.overlays",
        )
    return {"preconfig": preconfig, "template_groups": template_names, "overlays": overlay_names}


def verify_referenced_objects(
    parsed: dict[str, Any],
    template_groups_payload: Any,
    overlays_payload: Any,
) -> list[str]:
    """Fail preparation when referenced objects are provably absent.

    Returns warnings for checks that could not be performed (e.g. the overlay
    listing endpoint returns no rows on some Orchestrator versions; the
    Orchestrator itself re-validates overlay names on preconfig apply).
    """
    warnings: list[str] = []
    template_names = parsed.get("template_groups", [])
    if template_names:
        available = {str(row.get("name", "")).strip() for row in extract_template_groups(template_groups_payload)}
        missing = [name for name in template_names if name not in available]
        if missing:
            raise ValueError(f"Template groups referenced by the preconfig were not found: {missing}")

    overlay_names = parsed.get("overlays", [])
    if overlay_names:
        if isinstance(overlays_payload, list):
            overlay_rows = [row for row in overlays_payload if isinstance(row, dict)]
        elif isinstance(overlays_payload, dict):
            overlay_rows = [row for row in overlays_payload.get("data", []) if isinstance(row, dict)]
        else:
            overlay_rows = []
        available = {
            str(row.get("name", row.get("overlayName", ""))).strip()
            for row in overlay_rows
        }
        available.discard("")
        if not available:
            warnings.append(
                "Overlay listing returned no rows; could not verify overlay names "
                f"{overlay_names} locally (the Orchestrator re-validates them on apply)."
            )
        else:
            missing = [name for name in overlay_names if name not in available]
            if missing:
                raise ValueError(f"Business Intent Overlays referenced by the preconfig were not found: {missing}")
    return warnings


@dataclass
class ZtpPlan:
    plan_id: str
    appliance_uuid: str
    appliance_hostname: str
    appliance_serial: str
    preconfig_name: str
    preconfig_yaml: str
    confirmation: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 900)
    status: str = "prepared"
    validate_result: Any = None
    created_preconfig_id: str = ""
    preconfig_result: Any = None
    approve_result: Any = None
    deny_available: bool = False
    health_check: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def public(self, include_details: bool = True) -> dict[str, Any]:
        result = {
            "plan_id": self.plan_id,
            "status": self.status,
            "appliance": {
                "uuid": self.appliance_uuid,
                "hostname": self.appliance_hostname,
                "serial": self.appliance_serial,
            },
            "preconfig_name": self.preconfig_name,
            "confirmation_required": self.confirmation,
            "expires_at_epoch": int(self.expires_at),
            "deny_available": self.deny_available,
        }
        if self.warnings:
            result["warnings"] = self.warnings
        if include_details:
            result["preconfig_yaml"] = self.preconfig_yaml
        if self.validate_result is not None:
            result["validate_result"] = self.validate_result
        if self.created_preconfig_id:
            result["created_preconfig_id"] = self.created_preconfig_id
        if self.preconfig_result is not None:
            result["preconfig_result"] = self.preconfig_result
        if self.approve_result is not None:
            result["approve_result"] = self.approve_result
        if self.deny_available:
            result["rollback_confirmation"] = f"ROLLBACK {self.plan_id}"
        if self.health_check:
            result["health_check"] = self.health_check
        return result


def extract_preconfig_id(payload: Any) -> str:
    """Extract the created preconfiguration ID from common response shapes."""
    candidates: list[Any] = [payload]
    if isinstance(payload, dict):
        candidates.extend(payload.get(key) for key in ("data", "result", "preconfiguration"))
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in ("id", "preconfigId", "preconfigurationId"):
                value = candidate.get(key)
                if value not in (None, "", 0):
                    return str(value)
        if isinstance(candidate, (str, int)) and str(candidate).strip():
            return str(candidate)
    return ""


def find_preconfig_id_by_name(payload: Any, name: str) -> str:
    """Locate a preconfiguration id by name from the listing response."""
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        value = payload.get("data")
        if isinstance(value, list):
            rows = [row for row in value if isinstance(row, dict)]
        elif isinstance(value, dict):
            rows = (find_preconfig_id_by_name(value, name) and []) or []
            for key in ("data", "result", "preconfigurations"):
                inner = value.get(key)
                if isinstance(inner, list):
                    rows = [row for row in inner if isinstance(row, dict)]
                    break
    for row in rows:
        if str(row.get("name", "")).strip() == name.strip():
            return str(row.get("id", row.get("preconfigId", "")))
    return ""


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
                        preconfig_name=payload["preconfig_name"],
                        preconfig_yaml=payload["preconfig_yaml"],
                        confirmation=payload["confirmation"],
                        created_at=payload["created_at"],
                        expires_at=payload["expires_at"],
                        status=payload["status"],
                        validate_result=payload.get("validate_result"),
                        created_preconfig_id=payload.get("created_preconfig_id", ""),
                        preconfig_result=payload.get("preconfig_result"),
                        approve_result=payload.get("approve_result"),
                        deny_available=payload.get("deny_available", False),
                        health_check=payload.get("health_check", {}),
                        warnings=payload.get("warnings", []),
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
    preconfig_yaml_text: str,
    template_groups_payload: Any,
    overlays_payload: Any,
    ttl_seconds: int = 900,
) -> ZtpPlan:
    """Validate the preconfig YAML and its references, then build an immutable plan."""
    parsed = validate_preconfig_yaml(preconfig_yaml_text)
    warnings = verify_referenced_objects(parsed, template_groups_payload, overlays_payload)
    plan_id = secrets.token_hex(6)
    info = discovered_row.get("applianceInfo") or {}
    preconfig_name = f"Codex-ZTP-{plan_id}"
    appliance_uuid = str(discovered_row.get("uuid", ""))
    return ZtpPlan(
        plan_id=plan_id,
        appliance_uuid=appliance_uuid,
        appliance_hostname=str(info.get("hostname") or ""),
        appliance_serial=str(info.get("serial") or ""),
        preconfig_name=preconfig_name,
        preconfig_yaml=preconfig_yaml_text,
        confirmation=f"ADOPTAR {plan_id} {appliance_uuid} {preconfig_name}",
        expires_at=time.time() + ttl_seconds,
        warnings=warnings,
    )
