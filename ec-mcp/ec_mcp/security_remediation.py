"""Scoped IDS/IPS and DDoS changes with complete snapshots and conflict checks.

Plans are deliberately process-local and expire; secrets and complete snapshots
are kept out of their public representation and the audit log.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from .security import SecurityError
from .security_workflow import unwrap_payload, validate_ids_mode

IDS_STATE_READ = "orchestrator.idpsstateget"
IDS_STATE_WRITE = "orchestrator.idpsstateput"
DDOS_READ = "appliance.protectionprofilesget574729"
DDOS_WRITE = "appliance.protectionprofilespost168495"
MODE_KEYS = {"Off": "disabled", "IDS Only": "ids", "IPS-Performant": "ips_lookaside", "IPS-Inline": "ips_inline"}
MODE_RANK = {"Off": 0, "IDS Only": 1, "IPS-Performant": 2, "IPS-Inline": 3}


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def validate_ids_snapshot(payload: Any) -> dict:
    value = unwrap_payload(payload)
    if not isinstance(value, dict) or set(value) != set(MODE_KEYS.values()):
        raise SecurityError("IDS state requires all four mode lists from GET /ids/state")
    seen = set()
    for members in value.values():
        if not isinstance(members, list):
            raise SecurityError("IDS mode assignments must be lists")
        for member in members:
            if not isinstance(member, str) or not re.fullmatch(r"\d+\.NE", member):
                raise SecurityError("IDS assignments require canonical nePk values")
            if member in seen:
                raise SecurityError("Every appliance must occur in exactly one IDS mode list")
            seen.add(member)
    return {key: sorted(members) for key, members in value.items()}


def validate_ddos_snapshot(payload: Any) -> dict:
    value = unwrap_payload(payload)
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("profiles"), list)
        or not isinstance(value.get("profileMaps"), list)
    ):
        raise SecurityError("DDoS requires complete profiles[] and profileMaps[] from GET")
    names = set()
    for profile in value["profiles"]:
        if (
            not isinstance(profile, dict)
            or not isinstance(profile.get("profile_name"), str)
            or not profile["profile_name"].strip()
        ):
            raise SecurityError("DDoS profile_name must be a nonempty string")
        if profile["profile_name"] in names or not isinstance(profile.get("enable"), bool):
            raise SecurityError("DDoS profiles require unique names and boolean enable")
        names.add(profile["profile_name"])
        for key, item in profile.items():
            if key in {
                "spoof_check",
                "icmp_verify",
                "dpi_app_verify",
                "ftp_bounce_attack",
                "udp_verify",
                "rst_verify",
                "strict_3way_tcp",
                "discard_non_syn_tcp",
                "is_asymmetric",
            } and not isinstance(item, bool):
                raise SecurityError(f"DDoS {key} must be boolean")
        for key, low, high in (
            ("aggr_age_time", 15, 45),
            ("embryonic_time", 20, 45),
            ("embryonic_non_tcp_time", 20, 45),
        ):
            if key in profile and (type(profile[key]) is not int or not low <= profile[key] <= high):
                raise SecurityError(f"DDoS {key} must be an integer in [{low}, {high}]")
    zones = set()
    for assignment in value["profileMaps"]:
        if not isinstance(assignment, dict) or type(assignment.get("zone_id")) is not int or assignment["zone_id"] < 0:
            raise SecurityError("DDoS zone_id must be a nonnegative integer")
        if assignment["zone_id"] in zones or assignment.get("profile_name") not in names:
            raise SecurityError("DDoS assignments require unique zones and existing profiles")
        zones.add(assignment["zone_id"])
    result = deepcopy(value)
    result["profiles"].sort(key=lambda profile: profile["profile_name"])
    result["profileMaps"].sort(key=lambda assignment: assignment["zone_id"])
    return result


@dataclass
class SecurityPlan:
    ne_pk: str
    version: str
    control: str
    before: dict
    candidate: dict
    read_operation: str
    write_operation: str
    change: dict
    dangerous: bool = False
    plan_id: str = field(default_factory=lambda: secrets.token_hex(12))
    created_at: float = field(default_factory=time.monotonic)
    status: str = "prepared"
    lock: Any = field(default_factory=RLock, repr=False, compare=False)

    def public(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "nePk": self.ne_pk,
            "api_profile": self.version,
            "control": self.control,
            "status": self.status,
            "change": self.change,
            "read_operation": self.read_operation,
            "write_operation": self.write_operation,
            "before_sha256": fingerprint(self.before),
            "candidate_sha256": fingerprint(self.candidate),
            "requires_dangerous_writes": self.dangerous,
            "confirmation_required": f"APPLY {self.plan_id}",
            "rollback_confirmation_required": f"ROLLBACK {self.plan_id}",
            "expires_in_seconds": max(0, int(600 - (time.monotonic() - self.created_at))),
            "verification_scope": "configuration_only",
            "enforcement_verified": False,
        }


class SecurityPlanStore:
    def __init__(self):
        self._plans: dict[str, SecurityPlan] = {}
        self._lock = RLock()
        self._scope_locks: dict[str, Any] = {}

    def scope_lock(self, plan: SecurityPlan):
        # PUT /ids/state replaces global assignments: serialize *all* IDS plans.
        key = "ids_global" if plan.control == "ids_ips" else f"ddos:{plan.ne_pk}"
        with self._lock:
            return self._scope_locks.setdefault(key, RLock())

    def put(self, plan: SecurityPlan) -> None:
        with self._lock:
            self._plans = {
                key: value for key, value in self._plans.items() if time.monotonic() - value.created_at < 600
            }
            if len(self._plans) >= 100:
                raise SecurityError("Security plan limit reached; wait for expiry")
            self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> SecurityPlan:
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None or time.monotonic() - plan.created_at >= 600:
                raise SecurityError("Security plan is unknown or expired; prepare it again")
            return plan


def prepare_security_plan(
    ne_pk: str, version: str, control: str, payload: Any, mode: str = "", profile_name: str = ""
) -> SecurityPlan:
    if control == "ids_ips":
        mode = validate_ids_mode(mode)
        before = validate_ids_snapshot(payload)
        previous = next((name for name, key in MODE_KEYS.items() if ne_pk in before[key]), None)
        if previous is None:
            raise SecurityError("Target is absent from GET /ids/state; refusing to add unknown scope")
        candidate = deepcopy(before)
        for members in candidate.values():
            if ne_pk in members:
                members.remove(ne_pk)
        candidate[MODE_KEYS[mode]].append(ne_pk)
        candidate = validate_ids_snapshot(candidate)
        # Unchanged list order makes a no-op distinguishable without a write.
        if previous == mode:
            raise SecurityError("Target already has the requested IDS/IPS mode")
        return SecurityPlan(
            ne_pk,
            version,
            control,
            before,
            candidate,
            IDS_STATE_READ,
            IDS_STATE_WRITE,
            {"from_mode": previous, "to_mode": mode, "affected_appliances": [ne_pk]},
            MODE_RANK[mode] < MODE_RANK[previous],
        )
    if control == "ddos":
        before = validate_ddos_snapshot(payload)
        candidate = deepcopy(before)
        profile = next((p for p in candidate["profiles"] if p["profile_name"] == profile_name), None)
        zones = [m["zone_id"] for m in candidate["profileMaps"] if m["profile_name"] == profile_name]
        if profile is None or not zones:
            raise SecurityError("DDoS profile must exist and be assigned to a zone on this appliance")
        if profile["enable"] is True:
            raise SecurityError("DDoS profile is already enabled")
        profile["enable"] = True
        return SecurityPlan(
            ne_pk,
            version,
            control,
            before,
            candidate,
            DDOS_READ,
            DDOS_WRITE,
            {"profile_name": profile_name, "enable": True, "affected_zones": zones, "affected_appliances": [ne_pk]},
        )
    raise SecurityError(
        "Supported remediation controls: ids_ips, ddos. NGFW policy and web-filter enforcement require a validated vendor contract and lab evidence"
    )


def security_write_guard(path: str, method: str, body: Any, query: dict) -> bool:
    """Block unsafe generic replacements; return whether a second lock is required."""
    path = path.removeprefix("/gms/rest").removeprefix("/rest/json")
    security_path = path.startswith(("/ids/", "/idsips/", "/security/", "/securityMaps", "/zones"))
    if method in {"POST", "PUT", "PATCH"}:
        if path in {"/ids/state", "/security/ddos/protectionProfile"}:
            raise SecurityError(
                "Complete replacement requires prepare_security_remediation and conflict-checked apply_security_remediation"
            )
        if path == "/securityMaps":
            raise SecurityError(
                "NGFW full REPLACE is blocked: options alone are not policies; capture and validate the complete vendor schema before enabling this write"
            )
        if path in {
            "/ids/config",
            "/ids/profilestate",
            "/ids/signatures/profiles",
            "/idsips/configfile",
            "/idsips/signature",
            "/securityMapsSettings",
        } or path.startswith("/securityMapsSettings/"):
            raise SecurityError(
                "Security configuration/profile write is unsupported until a complete vendor payload and snapshot workflow are validated; use a dry-run for review"
            )
        if path in {"/zones/config/eeenable", "/zones/eeEnable"} and (
            not isinstance(body, dict) or set(body) != {"enable"} or not isinstance(body["enable"], bool)
        ):
            raise SecurityError("End-to-end firewall toggle requires exactly a boolean enable")
        if path == "/idsips/state" and (
            not isinstance(body, dict) or set(body) != {"enable"} or not isinstance(body["enable"], bool)
        ):
            raise SecurityError(
                "POST /idsips/state requires exactly a boolean enable; use the IDS mode workflow for mode changes"
            )
    disabled = isinstance(body, dict) and body.get("enable") is False
    return method == "DELETE" or (
        security_path and (disabled or str(query.get("deleteDependencies", "")).casefold() == "true")
    )
