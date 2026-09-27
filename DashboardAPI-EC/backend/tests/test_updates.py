import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.system import router
from app.core.config import settings
from app.services import update_service


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [
            {"name": "v1.2.0-stable"},
            {"name": "v1.3.0-stable"},
            {"name": "latest"},
        ]


def test_release_channel_filters_and_orders_official_tags(monkeypatch):
    monkeypatch.setattr(update_service.httpx, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(settings, "app_version", "1.2.0")

    result = update_service.release_status()

    assert result["ok"] is True
    assert result["current_release"] == "v1.2.0-stable"
    assert result["latest_stable"] == "v1.3.0-stable"
    assert result["releases"] == [
        "v1.3.0-stable",
        "v1.2.0-stable",
    ]
    assert result["update_available"] is True


def test_update_queue_is_atomic_and_rejects_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "1.2.0")
    monkeypatch.setattr(settings, "update_state_dir", str(tmp_path))
    monkeypatch.setattr(
        update_service,
        "release_status",
        lambda: {"ok": True, "releases": ["v1.3.0-stable"]},
    )

    assert update_service.queue_update("v1.3.0-stable")["state"] == "pending"
    assert json.loads((tmp_path / "request.json").read_text())["version"] == "v1.3.0-stable"
    try:
        update_service.queue_update("v1.3.0-stable")
        raise AssertionError("A duplicate request must fail")
    except ValueError as exc:
        assert "pendiente" in str(exc)


def test_update_endpoints_use_official_channel_without_second_key(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "update_enabled", True)
    monkeypatch.setattr(settings, "update_state_dir", str(tmp_path))
    monkeypatch.setattr(
        update_service.httpx,
        "get",
        lambda *args, **kwargs: Response(),
    )
    app = FastAPI()
    app.include_router(router)
    local = TestClient(app, client=("127.0.0.1", 12345))

    assert local.get("/releases").status_code == 200
    assert local.get("/update").json()["state"] == "idle"
    monkeypatch.setattr(settings, "update_enabled", False)
    assert local.get("/update").status_code == 503
