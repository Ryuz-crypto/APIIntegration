import pytest
from pydantic import ValidationError

from app.schemas.orchestrator import OrchestratorCreate
from app.services.appliance_service import _summarize_metrics


def test_basic_auth_requires_username_and_password():
    with pytest.raises(ValidationError):
        OrchestratorCreate(
            name="Lab Orchestrator",
            base_url="https://orchestrator.example.local",
            auth_type="basic",
            username="admin",
        )


def test_api_key_auth_requires_token_and_header():
    with pytest.raises(ValidationError):
        OrchestratorCreate(
            name="Lab Orchestrator",
            base_url="https://orchestrator.example.local",
            auth_type="api_key",
            api_token="secret",
        )


def test_accepts_complete_bearer_parameters():
    payload = OrchestratorCreate(
        name="Lab Orchestrator",
        base_url="https://orchestrator.example.local",
        api_version="9.5",
        auth_type="bearer",
        api_token="secret",
        timeout_seconds=30,
    )

    assert payload.auth_type == "bearer"
    assert payload.api_version == "9.5"


def test_summarizes_preferred_metric_fields():
    summary = _summarize_metrics(
        {
            "cpuUtilization": 17.4,
            "memoryUtilization": 51.2,
            "tunnelCount": 84,
            "nested": {"ignored": True},
        }
    )

    assert summary == {
        "cpuUtilization": 17.4,
        "memoryUtilization": 51.2,
        "tunnelCount": 84,
    }
