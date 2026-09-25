import pytest

from app.compatibility.engine import CompatibilityEngine, CompatibilityError
from app.compatibility.loader import load_builtin_profiles


def test_resolves_versioned_operation_with_path_params():
    engine = CompatibilityEngine(load_builtin_profiles())

    operation = engine.resolve("9.5", "appliance.performance", {"appliance_id": "edge-01"})

    assert operation.method == "GET"
    assert operation.path == "/gms/rest/appliances/edge-01/performance"


def test_rejects_missing_operation():
    engine = CompatibilityEngine(load_builtin_profiles())

    with pytest.raises(CompatibilityError):
        engine.resolve("9.3", "unknown.operation")


def test_resolves_version_operation():
    engine = CompatibilityEngine(load_builtin_profiles())

    operation = engine.resolve("9.5", "orchestrator.version")

    assert operation.method == "GET"
    assert operation.path == "/gms/rest/gmsserver/briefInfo"


def test_matches_patch_release_to_supported_profile():
    engine = CompatibilityEngine(load_builtin_profiles())

    assert engine.match_version("9.6.2.0") == "9.6"


def test_does_not_guess_unknown_version():
    engine = CompatibilityEngine(load_builtin_profiles())

    assert engine.match_version("10.0.0") is None
