from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.api_sample import ApiSample
from app.models.appliance import Appliance
from app.models.network_resource import MetricPoint, NetworkResource
from app.models.orchestrator import Orchestrator
from app.services.dashboard_service import compose_dashboard
from app.services.normalization_service import normalize_inventory, normalize_metrics
from app.services.trace_service import build_trace


def _session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_normalization_preserves_source_lineage():
    with _session() as session:
        orchestrator = Orchestrator(
            name="Lab", base_url="https://lab.example", api_version="9.6"
        )
        session.add(orchestrator)
        session.flush()
        appliance = Appliance(
            orchestrator_id=orchestrator.id,
            hostname="edge-01",
            serial_number="EC-001",
            site="MTY",
        )
        session.add(appliance)
        session.flush()
        sample = ApiSample(
            orchestrator_id=orchestrator.id,
            appliance_id=appliance.id,
            api_version="9.6",
            operation_id="orchestrator.inventory.summary",
            method="GET",
            path="/appliance",
            status_code=200,
            ok=True,
        )
        session.add(sample)
        session.flush()

        summary = normalize_inventory(
            session,
            orchestrator.id,
            [appliance],
            [{"serialNumber": "EC-001", "site": "MTY"}],
            sample,
        )
        points = normalize_metrics(
            session,
            orchestrator.id,
            appliance,
            {"health": {"cpuPercent": 42, "latencyMs": 8.5}, "connected": True},
            sample,
        )
        session.commit()

        resources = list(session.exec(select(NetworkResource)).all())
        metrics = list(session.exec(select(MetricPoint)).all())
        assert summary == {"appliances": 1, "sites": 1}
        assert {resource.resource_type for resource in resources} == {"appliance", "site"}
        assert points == {"health.cpuPercent": 42.0, "health.latencyMs": 8.5}
        assert all(point.source_sample_id == sample.id for point in metrics)


def test_dashboard_uses_detected_capabilities_and_latest_sample():
    with _session() as session:
        orchestrator = Orchestrator(
            name="Production",
            base_url="https://prod.example",
            api_version="9.6",
            capabilities={
                "operations": {
                    "orchestrator.inventory.summary": True,
                    "appliance.performance": True,
                    "appliance.tunnels": False,
                }
            },
        )
        session.add(orchestrator)
        session.flush()
        sample = ApiSample(
            orchestrator_id=orchestrator.id,
            api_version="9.6",
            operation_id="orchestrator.inventory.summary",
            method="GET",
            path="/appliance",
            status_code=200,
            ok=True,
        )
        session.add(sample)
        session.commit()

        dashboard = compose_dashboard(session, orchestrator)
        widgets = {widget.id: widget for section in dashboard.sections for widget in section.widgets}
        assert widgets["appliances"].status == "ready"
        assert widgets["appliances"].provenance.sample_id == sample.id
        assert widgets["performance"].status == "waiting"
        assert widgets["tunnels"].status == "unavailable"


def test_trace_redacts_secrets_and_generates_reusable_examples():
    sample = ApiSample(
        orchestrator_id="3545f754-0225-4f71-883a-130ecc82ca96",
        api_version="9.6",
        operation_id="appliance.performance",
        method="GET",
        path="/appliances/edge-01/performance",
        status_code=200,
        ok=True,
        request_params={"appliance_id": "edge-01", "apiToken": "request-secret"},
        payload={"cpu": 31, "nested": {"password": "response-secret"}},
        extracted_values={"cpu": 31},
        transformations=["Flatten numeric fields"],
    )

    trace = build_trace(sample)

    assert trace.request_params["apiToken"] == "[REDACTED]"
    assert trace.sanitized_payload["nested"]["password"] == "[REDACTED]"
    assert "request-secret" not in trace.code_examples.curl
    assert "$EDGECONNECT_API_KEY" in trace.code_examples.curl
