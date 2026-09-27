from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.api.routes.system import router
from app.db.session import get_session


def test_appearance_defaults_validation_and_persistence():
    database = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(database)

    def session_override():
        with Session(database) as session:
            yield session

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = session_override
    client = TestClient(app)

    defaults = client.get("/appearance")
    assert defaults.status_code == 200
    assert defaults.json()["panel_name"] == "DashboardAPI"

    changed = {**defaults.json(), "primary": "#01A982", "font": "mono", "icon": "gauge"}
    assert client.put("/appearance", json=changed).status_code == 200
    assert client.get("/appearance").json() == changed
    assert client.put("/appearance", json={**changed, "primary": "red"}).status_code == 422
