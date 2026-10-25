"""Structured remediation proposals for detected security incidents (Phase 3, refs #88).

Every proposal is dry-run by nature: this module never writes. A proposal
carries evidence, scope, risk, reversal plan and a candidate policy, and the
apply step always delegates to the existing confirmed write tools
(block_threat/apply_change/run_cli_command with confirm=true).
"""

from __future__ import annotations

from typing import Any

POLICY_OBSERVATION = "observation"
POLICY_CONTAINMENT = "containment_proposed"
POLICY_CONTROLLED_CHANGE = "controlled_change"
POLICY_EMERGENCY = "emergency"

POLICY_TEMPLATES: dict[str, dict[str, str]] = {
    POLICY_OBSERVATION: {
        "policy": POLICY_OBSERVATION,
        "description": "Solo recopila y correlaciona señales; no propone cambios activos.",
        "allowed": "read-only",
    },
    POLICY_CONTAINMENT: {
        "policy": POLICY_CONTAINMENT,
        "description": "Sugiere clasificación/bloqueo temporal; nunca aplica por sí misma.",
        "allowed": "proposal_only",
    },
    POLICY_CONTROLLED_CHANGE: {
        "policy": POLICY_CONTROLLED_CHANGE,
        "description": "Permite una operación preaprobada para un alcance definido, con ventana, confirmación y reversión.",
        "allowed": "apply_with_confirmation",
    },
    POLICY_EMERGENCY: {
        "policy": POLICY_EMERGENCY,
        "description": "Reservada a operadores autorizados; exige justificación, evidencia y revisión posterior.",
        "allowed": "apply_with_reinforced_confirmation",
    },
}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# Findings whose remediation has high blast radius and therefore require the
# reinforced (emergency/controlled) confirmation path.
HIGH_IMPACT_KEYWORDS = ("isolate", "shutdown", "blackhole", "acl", "route", "restart", "ips mode")


def _is_high_impact(action: str) -> bool:
    lowered = str(action).lower()
    return any(keyword in lowered for keyword in HIGH_IMPACT_KEYWORDS)


def build_remediation_proposal(
    finding: dict[str, Any],
    *,
    policy: str = POLICY_CONTAINMENT,
) -> dict[str, Any] | None:
    """Turn a correlation finding into a structured, dry-run remediation proposal.

    The proposal never executes anything: it returns the evidence, scope,
    risk, reversal plan and the exact read-only next step. Applying always
    requires the existing write tools with confirm=true.
    """
    if not isinstance(finding, dict) or not finding.get("finding"):
        return None
    if policy not in POLICY_TEMPLATES:
        raise ValueError(f"Política desconocida: {policy}")
    template = POLICY_TEMPLATES[policy]
    severity = str(finding.get("severity") or "low").lower()
    ne_pk = str(finding.get("nePk") or "")
    evidence = finding.get("evidence") or [str(finding.get("finding"))[:200]]
    recommendation = str(finding.get("recommendation") or "")
    proposal: dict[str, Any] = {
        "nePk": ne_pk,
        "severity": severity,
        "policy": template["policy"],
        "policy_description": template["description"],
        "finding": str(finding.get("finding")),
        "evidence": [str(item)[:200] for item in evidence[:5]],
        "scope": f"appliance {ne_pk}" if ne_pk else "appliance",
        "risk": "low" if severity == "low" else ("medium" if severity == "medium" else "high"),
        "dry_run": True,
        "applied": False,
        "reversal_plan": (
            "La propuesta no aplica cambios. Si más adelante se aplica una acción "
            "concreta, documenta antes el estado previo con get_security_posture y "
            "conserva el diff de apply_change para revertir con la operación opuesta."
        ),
        "next_step_read_only": (
            "call list_response_options(target=/domain=/context=) para enumerar cada "
            "bloqueo disponible y su dry-run exacto; luego decide con confirmación humana."
        ),
    }
    if recommendation:
        proposal["recommendation"] = recommendation
    if policy == POLICY_OBSERVATION:
        proposal["candidate_action"] = "none"
        proposal["next_step_read_only"] = "Solo observar: usa get_security_posture y correlate_incidents para seguimiento."
        return proposal
    if policy == POLICY_CONTAINMENT:
        proposal["candidate_action"] = "classify_or_block_temporal"
        proposal["apply_with"] = (
            "block_threat(..., confirm=true) tras validación humana; nunca automático."
        )
        proposal["confirmation_required"] = "human_explicit"
        return proposal
    if policy == POLICY_CONTROLLED_CHANGE:
        proposal["candidate_action"] = "preapproved_operation"
        proposal["apply_with"] = "apply_change(..., confirm=true) dentro de la ventana aprobada."
        proposal["confirmation_required"] = "human_explicit_with_window"
        return proposal
    proposal["candidate_action"] = "emergency_operation"
    proposal["apply_with"] = (
        "block_threat/apply_change/run_cli_command con confirm=true, justificación "
        "registrada y revisión posterior obligatoria."
    )
    proposal["confirmation_required"] = "reinforced_human"
    proposal["high_impact"] = _is_high_impact(proposal.get("candidate_action", ""))
    return proposal


def build_remediation_proposals(
    incidents: list[dict[str, Any]],
    *,
    policy: str = POLICY_CONTAINMENT,
) -> list[dict[str, Any]]:
    """Build dry-run proposals for every finding in an incident list."""
    proposals: list[dict[str, Any]] = []
    for incident in incidents or []:
        for finding in (incident or {}).get("findings") or []:
            proposal = build_remediation_proposal(finding, policy=policy)
            if proposal:
                proposals.append(proposal)
    proposals.sort(key=lambda item: SEVERITY_ORDER.get(item.get("severity", "low"), 3))
    return proposals


def summarize_proposals(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact, secret-free summary for the AI/operator."""
    return {
        "total": len(proposals),
        "high": sum(1 for p in proposals if p.get("severity") == "high"),
        "medium": sum(1 for p in proposals if p.get("severity") == "medium"),
        "low": sum(1 for p in proposals if p.get("severity") == "low"),
        "all_dry_run": all(p.get("dry_run") and not p.get("applied") for p in proposals),
        "requires_human_confirmation": True,
    }
