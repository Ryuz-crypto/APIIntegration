from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.security import decrypt_secret
from app.models.orchestrator import Orchestrator
from app.schemas.orchestrator import OrchestratorCredentialUpdate
from app.services.orchestrator_service import credential_status, update_credentials
from app.workers.tasks import is_due


def _session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_each_orchestrator_keeps_an_independent_encrypted_credential():
    with _session() as session:
        first = Orchestrator(name="Production", base_url="https://prod.example")
        second = Orchestrator(name="Lab", base_url="https://lab.example")
        session.add(first)
        session.add(second)
        session.commit()

        update_credentials(
            session,
            first,
            OrchestratorCredentialUpdate(
                credential_label="Production read only",
                auth_type="api_key",
                api_token="first-secret",
            ),
        )
        update_credentials(
            session,
            second,
            OrchestratorCredentialUpdate(
                credential_label="Lab read only",
                auth_type="api_key",
                api_token="second-secret",
            ),
        )

        assert first.encrypted_api_token != second.encrypted_api_token
        assert decrypt_secret(first.encrypted_api_token) == "first-secret"
        assert decrypt_secret(second.encrypted_api_token) == "second-secret"
        assert credential_status(first).supports_unattended_polling is True


def test_empty_secret_preserves_saved_credential_during_label_update():
    with _session() as session:
        orchestrator = Orchestrator(name="Production", base_url="https://prod.example")
        session.add(orchestrator)
        session.commit()
        update_credentials(
            session,
            orchestrator,
            OrchestratorCredentialUpdate(auth_type="api_key", api_token="saved-secret"),
        )
        encrypted = orchestrator.encrypted_api_token

        update_credentials(
            session,
            orchestrator,
            OrchestratorCredentialUpdate(
                credential_label="Rotated later",
                auth_type="api_key",
            ),
        )

        assert orchestrator.encrypted_api_token == encrypted
        assert decrypt_secret(orchestrator.encrypted_api_token) == "saved-secret"


def test_switching_authentication_requires_the_new_secret_type():
    with _session() as session:
        orchestrator = Orchestrator(name="Production", base_url="https://prod.example")
        session.add(orchestrator)
        session.commit()

        with pytest.raises(ValueError, match="password is required"):
            update_credentials(
                session,
                orchestrator,
                OrchestratorCredentialUpdate(
                    auth_type="session",
                    username="operator",
                ),
            )


def test_polling_due_calculation_accepts_naive_database_timestamps():
    now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

    assert is_due(None, 60, now) is True
    assert is_due((now - timedelta(seconds=61)).replace(tzinfo=None), 60, now) is True
    assert is_due(now - timedelta(seconds=30), 60, now) is False
