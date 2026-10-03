"""Transactional cloning helpers for Business Intent Overlays."""

from __future__ import annotations

import copy
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

MANAGED_OVERLAY_FIELDS = {
    "id",
    "overlayId",
    "createdAt",
    "createdBy",
    "modifiedAt",
    "modifiedBy",
    "lastModified",
}
OVERLAY_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_. -]{0,63}$")


@dataclass
class OverlayPlan:
    plan_id: str
    source_id: str
    source_name: str
    target_name: str
    source: dict[str, Any]
    candidate: dict[str, Any]
    diff: list[dict[str, Any]]
    confirmation: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 900)
    status: str = "prepared"
    created_overlay_id: str = ""
    apply_result: Any = None

    def public(self, include_candidate: bool = True) -> dict[str, Any]:
        result = {
            "plan_id": self.plan_id,
            "status": self.status,
            "source": {"id": self.source_id, "name": self.source_name},
            "target_name": self.target_name,
            "diff": self.diff,
            "confirmation_required": self.confirmation,
            "expires_at_epoch": int(self.expires_at),
            "rollback_available": bool(self.created_overlay_id),
        }
        if include_candidate:
            result["candidate"] = self.candidate
        if self.created_overlay_id:
            result["created_overlay_id"] = self.created_overlay_id
            result["rollback_confirmation"] = f"ROLLBACK {self.plan_id}"
        if self.apply_result is not None:
            result["apply_result"] = self.apply_result
        return result


class OverlayPlanStore:
    def __init__(self, ttl_seconds: int = 900, max_plans: int = 50):
        self.ttl_seconds = ttl_seconds
        self.max_plans = max_plans
        self._plans: dict[str, OverlayPlan] = {}

    def _purge(self) -> None:
        now = time.time()
        self._plans = {
            plan_id: plan
            for plan_id, plan in self._plans.items()
            if plan.expires_at > now or plan.status in {"applied", "rolled_back"}
        }
        while len(self._plans) > self.max_plans:
            oldest = min(self._plans, key=lambda key: self._plans[key].created_at)
            self._plans.pop(oldest, None)

    def put(self, plan: OverlayPlan) -> None:
        self._purge()
        self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> OverlayPlan:
        self._purge()
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError("Unknown or expired overlay plan")
        if plan.expires_at <= time.time() and plan.status == "prepared":
            raise ValueError("Overlay plan expired; prepare a new plan")
        return plan


def extract_overlays(payload: Any) -> list[dict[str, Any]]:
    """Extract overlay rows from common Orchestrator wrapper shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "overlays", "result"):
        value = payload.get(key)
        rows = extract_overlays(value)
        if rows:
            return rows
    if "name" in payload and ("id" in payload or "topology" in payload):
        return [payload]
    return []


def select_overlay(payload: Any, selector: str) -> dict[str, Any]:
    selector_normalized = selector.strip().lower()
    matches = [
        row
        for row in extract_overlays(payload)
        if selector_normalized in {
            str(row.get("id", "")).lower(),
            str(row.get("overlayId", "")).lower(),
            str(row.get("name", "")).lower(),
        }
    ]
    if not matches:
        raise ValueError(f"Overlay {selector!r} was not found")
    if len(matches) > 1:
        raise ValueError(f"Overlay selector {selector!r} is ambiguous")
    return matches[0]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _rename_overlay_acl(candidate: dict[str, Any], source_name: str, target_name: str) -> None:
    match = candidate.get("match")
    if not isinstance(match, dict):
        return
    acl_raw = match.get("overlayAcl")
    if not isinstance(acl_raw, str) or not acl_raw.strip():
        return
    try:
        acl = json.loads(acl_raw)
    except json.JSONDecodeError:
        return
    data = acl.get("data") if isinstance(acl, dict) else None
    if not isinstance(data, dict):
        return
    source_key = f"Overlay_{source_name}"
    if source_key not in data:
        return
    data[f"Overlay_{target_name}"] = data.pop(source_key)
    match["overlayAcl"] = json.dumps(acl)


def sanitize_overlay(source: dict[str, Any], target_name: str, overrides: dict[str, Any]) -> dict[str, Any]:
    if not OVERLAY_NAME_RE.fullmatch(target_name):
        raise ValueError(
            "target_name must start with a letter and contain at most 64 letters, "
            "numbers, spaces, dots, underscores or hyphens"
        )
    if str(source.get("name", "")).casefold() == target_name.casefold():
        raise ValueError("target_name must differ from the source overlay name")
    candidate = {
        key: copy.deepcopy(value)
        for key, value in source.items()
        if key not in MANAGED_OVERLAY_FIELDS and not key.lower().endswith("timestamp")
    }
    candidate["name"] = target_name
    candidate = deep_merge(candidate, overrides)
    for key in MANAGED_OVERLAY_FIELDS:
        candidate.pop(key, None)
    candidate["name"] = target_name
    _rename_overlay_acl(candidate, str(source.get("name", "")), target_name)
    validate_overlay_candidate(candidate)
    return candidate


def validate_overlay_candidate(candidate: dict[str, Any]) -> None:
    if not isinstance(candidate, dict) or not candidate:
        raise ValueError("Overlay candidate must be a non-empty JSON object")
    if not OVERLAY_NAME_RE.fullmatch(str(candidate.get("name", ""))):
        raise ValueError("Overlay candidate has an invalid or missing name")
    forbidden = sorted(MANAGED_OVERLAY_FIELDS.intersection(candidate))
    if forbidden:
        raise ValueError(f"Overlay candidate contains managed fields: {forbidden}")
    if not isinstance(candidate.get("topology"), dict):
        raise ValueError("Overlay candidate must preserve a topology object")
    if not isinstance(candidate.get("match"), dict):
        raise ValueError("Overlay candidate must preserve a match object")


def structured_diff(source: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    keys = sorted(set(source) | set(candidate))
    diff = []
    for key in keys:
        before = source.get(key)
        after = candidate.get(key)
        if before != after:
            diff.append({"field": key, "before": before, "after": after})
    return diff


def prepare_overlay_plan(
    source: dict[str, Any],
    target_name: str,
    overrides_json: str = "",
    ttl_seconds: int = 900,
) -> OverlayPlan:
    try:
        overrides = json.loads(overrides_json) if overrides_json.strip() else {}
    except json.JSONDecodeError as error:
        raise ValueError(f"overrides_json is invalid: {error}") from error
    if not isinstance(overrides, dict):
        raise ValueError("overrides_json must be a JSON object")
    candidate = sanitize_overlay(source, target_name, overrides)
    plan_id = secrets.token_hex(6)
    return OverlayPlan(
        plan_id=plan_id,
        source_id=str(source.get("id") or source.get("overlayId") or ""),
        source_name=str(source.get("name") or ""),
        target_name=target_name,
        source=copy.deepcopy(source),
        candidate=candidate,
        diff=structured_diff(source, candidate),
        confirmation=f"CREAR OVERLAY {plan_id} {target_name}",
        expires_at=time.time() + ttl_seconds,
    )


def extract_created_overlay_id(result: Any, overlays_after: Any, target_name: str) -> str:
    candidates = extract_overlays(result) + extract_overlays(overlays_after)
    for row in candidates:
        if str(row.get("name", "")).casefold() == target_name.casefold():
            return str(row.get("id") or row.get("overlayId") or "")
    if isinstance(result, dict):
        return str(result.get("id") or result.get("overlayId") or "")
    return ""
