from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.models.appliance import Appliance
from app.models.orchestrator import Orchestrator
from app.services.appliance_service import _upsert_appliance, collect_appliance_metrics
from app.services.edgeconnect_client import EdgeConnectClientError


def _session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


class _FakeResponse:
    operation_id: str = "appliance.performance"
    method: str = "GET"
    path: str = "/gms/rest/appliances/1.NE/performance"
    status_code: int = 200
    duration_ms: int = 42

    def __init__(self):
        self.payload = {"health": {"cpuPercent": 12.5}}


class _StubClient:
    def __init__(self, orchestrator, engine):
        self.orchestrator = orchestrator
        self.engine = engine
        self.calls: list[dict[str, str]] = []

    def call_operation(self, version, operation_id, path_params=None):
        self.calls.append({"operation_id": operation_id, **(path_params or {})})
        return _FakeResponse()


class _StubEngine:
    pass


def test_discovery_persists_ne_pk_identifier():
    with _session() as session:
        orchestrator = Orchestrator(name="Lab", base_url="https://lab.example", api_version="9.6")
        session.add(orchestrator)
        session.flush()

        appliance = _upsert_appliance(
            session,
            orchestrator,
            {
                "id": "1.NE",
                "nePk": "1.NE",
                "hostName": "edge-mty",
                "serialNumber": "00-1B-BC-33-D5-C0",
            },
        )
        session.commit()

        assert appliance.ne_pk == "1.NE"
        assert appliance.serial_number == "00-1B-BC-33-D5-C0"
        assert appliance.hostname == "edge-mty"


def test_discovery_reuses_existing_appliance_by_ne_pk():
    with _session() as session:
        orchestrator = Orchestrator(name="Lab", base_url="https://lab.example", api_version="9.6")
        session.add(orchestrator)
        session.flush()
        session.add(
            Appliance(
                orchestrator_id=orchestrator.id,
                hostname="edge-mty",
                serial_number="00-1B-BC-33-D5-C0",
            )
        )
        session.commit()

        appliance = _upsert_appliance(
            session,
            orchestrator,
            {"id": "1.NE", "nePk": "1.NE", "hostName": "edge-mty", "mac": "00-1B-BC-33-D5-C0"},
        )
        session.commit()

        assert appliance.ne_pk == "1.NE"
        assert len(_all_appliances(session)) == 1


def _all_appliances(session):
    from sqlmodel import select

    return list(session.exec(select(Appliance)).all())


def test_metrics_call_uses_ne_pk_instead_of_mac():
    with _session() as session:
        orchestrator = Orchestrator(name="Lab", base_url="https://lab.example", api_version="9.6")
        session.add(orchestrator)
        session.flush()
        appliance = Appliance(
            orchestrator_id=orchestrator.id,
            hostname="edge-mty",
            serial_number="00-1B-BC-33-D5-C0",
            ne_pk="1.NE",
            selected_for_monitoring=True,
        )
        session.add(appliance)
        session.commit()

        import app.services.appliance_service as service

        original = service.EdgeConnectClient
        service.EdgeConnectClient = lambda orch, engine: _StubClient(orch, engine)
        try:
            payload = collect_appliance_metrics(session, appliance, orchestrator, _StubEngine())
        finally:
            service.EdgeConnectClient = original

        assert payload == {"health": {"cpuPercent": 12.5}}


def test_metrics_fail_when_appliance_has_no_identifier():
    with _session() as session:
        orchestrator = Orchestrator(name="Lab", base_url="https://lab.example", api_version="9.6")
        session.add(orchestrator)
        session.flush()
        appliance = Appliance(orchestrator_id=orchestrator.id, hostname="", serial_number=None)
        session.add(appliance)
        session.commit()

        try:
            collect_appliance_metrics(session, appliance, orchestrator, _StubEngine())
        except EdgeConnectClientError:
            pass
        else:
            raise AssertionError("expected failure for appliance without identifier")
