from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.api.routes.realtime import router
from app.db.session import get_session
from app.models.orchestrator import Orchestrator
from app.services.auth_service import create_session, create_user


def test_authenticated_websocket_sends_dashboard_snapshot():
    database = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(database)
    with Session(database) as session:
        user = create_user(session, "viewer", "long-enough-password", "Viewer", "viewer")
        token, _ = create_session(session, user)
        orchestrator = Orchestrator(name="Lab", base_url="https://lab.example", api_version="9.6")
        session.add(orchestrator)
        session.commit()
        orchestrator_id = orchestrator.id

    def session_override():
        with Session(database) as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = session_override
    client = TestClient(app)
    with client.websocket_connect(
        f"/dashboard/{orchestrator_id}", subprotocols=["dashboardapi", token]
    ) as socket:
        message = socket.receive_json()
        assert message["type"] == "dashboard.snapshot"
        assert message["data"]["orchestrator_name"] == "Lab"
        assert socket.accepted_subprotocol == "dashboardapi"
