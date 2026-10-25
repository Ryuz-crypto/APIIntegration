"""Phase 3 remediation proposals: dry-run, evidence, scope, risk, reversal (refs #88)."""

from __future__ import annotations

import pytest

from ec_mcp.remediation_workflow import (
    POLICY_CONTAINMENT,
    POLICY_CONTROLLED_CHANGE,
    POLICY_EMERGENCY,
    POLICY_OBSERVATION,
    POLICY_TEMPLATES,
    build_remediation_proposal,
    build_remediation_proposals,
    summarize_proposals,
)


def _finding(severity: str = "high", ne: str = "3") -> dict:
    return {
        "nePk": ne,
        "severity": severity,
        "finding": "IDS/IPS inactive while 42 firewall drops were logged",
        "evidence": ["drop reason=implicit-deny count=42"],
        "recommendation": "Enable IDS/IPS on this appliance.",
    }


def test_proposal_is_always_dry_run_and_not_applied():
    proposal = build_remediation_proposal(_finding(), policy=POLICY_CONTAINMENT)
    assert proposal["dry_run"] is True
    assert proposal["applied"] is False
    assert proposal["confirmation_required"] == "human_explicit"


def test_proposal_carries_evidence_scope_risk_reversal():
    proposal = build_remediation_proposal(_finding(), policy=POLICY_CONTAINMENT)
    assert proposal["evidence"]
    assert proposal["scope"] == "appliance 3"
    assert proposal["risk"] == "high"
    assert proposal["reversal_plan"]
    assert proposal["policy"] == POLICY_CONTAINMENT
    assert proposal["next_step_read_only"].startswith("call list_response_options")


def test_proposal_rejects_unknown_policy():
    with pytest.raises(ValueError):
        build_remediation_proposal(_finding(), policy="apply_directly")


def test_proposal_requires_finding():
    assert build_remediation_proposal({}) is None
    assert build_remediation_proposal(None) is None


def test_observation_policy_proposes_no_action():
    proposal = build_remediation_proposal(_finding(), policy=POLICY_OBSERVATION)
    assert proposal["candidate_action"] == "none"
    assert proposal["policy"] == POLICY_OBSERVATION


def test_controlled_change_and_emergency_policies():
    controlled = build_remediation_proposal(_finding(), policy=POLICY_CONTROLLED_CHANGE)
    assert controlled["confirmation_required"] == "human_explicit_with_window"
    emergency = build_remediation_proposal(_finding(), policy=POLICY_EMERGENCY)
    assert emergency["confirmation_required"] == "reinforced_human"
    assert emergency["policy"] == POLICY_EMERGENCY


def test_build_proposals_sorts_by_severity_and_covers_all_incidents():
    incidents = [
        {"nePk": "1", "findings": [_finding("low", "1"), _finding("high", "1")]},
        {"nePk": "2", "findings": [_finding("medium", "2")]},
    ]
    proposals = build_remediation_proposals(incidents, policy=POLICY_CONTAINMENT)
    assert [p["severity"] for p in proposals] == ["high", "medium", "low"]
    assert all(p["dry_run"] for p in proposals)


def test_summarize_reports_all_dry_run():
    incidents = [{"nePk": "1", "findings": [_finding("high", "1"), _finding("low", "1")]}]
    summary = summarize_proposals(build_remediation_proposals(incidents))
    assert summary["total"] == 2
    assert summary["high"] == 1
    assert summary["low"] == 1
    assert summary["all_dry_run"] is True
    assert summary["requires_human_confirmation"] is True


def test_policy_templates_cover_roadmap():
    assert set(POLICY_TEMPLATES) == {
        POLICY_OBSERVATION,
        POLICY_CONTAINMENT,
        POLICY_CONTROLLED_CHANGE,
        POLICY_EMERGENCY,
    }


def test_propose_remediation_tool_registered_and_never_writes():
    import inspect

    from ec_mcp import server

    src = inspect.getsource(server)
    assert "def propose_remediation" in src
    tool_block = src.split("def propose_remediation")[1].split("def apply_change")[0]
    assert "dry_run=True" in tool_block
    assert "audit.record" in tool_block
    assert "confirm=true" in tool_block or "confirm" in tool_block
    assert "block_threat/apply_change/run_cli_command" in tool_block
