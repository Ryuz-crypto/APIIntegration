import pytest

from app.compatibility.engine import CompatibilityEngine, CompatibilityError
from app.compatibility.loader import load_builtin_profiles


def test_resolves_versioned_operation_with_path_params():
    engine = CompatibilityEngine(load_builtin_profiles())

    operation = engine.resolve("9.5", "appliance.performance", {"appliance_id": "edge-01"})

    assert operation.method == "GET"
    assert operation.path == "/gms/rest/appliance?nePk=edge-01"


def test_rejects_missing_operation():
    engine = CompatibilityEngine(load_builtin_profiles())

    with pytest.raises(CompatibilityError):
        engine.resolve("9.3", "unknown.operation")


def test_resolves_version_operation():
    engine = CompatibilityEngine(load_builtin_profiles())

    operation = engine.resolve("9.7", "orchestrator.version")

    assert operation.method == "GET"
    assert operation.path == "/gms/rest/gmsserver/ping"


def test_loads_imported_contract_versions():
    engine = CompatibilityEngine(load_builtin_profiles())

    assert engine.versions == ["9.3", "9.4", "9.5", "9.6", "9.7"]
