"""Vendor SDK actions must retain their write classification in every profile."""

import pytest

from ec_mcp.compat import is_read_only_operation, load_profiles
from ec_mcp.config import Settings

pytestmark = pytest.mark.security

FLOW_ACTIONS = {
    "orchestrator.flowsreset241": "/flow/flowReset",
    "orchestrator.flowsreclassification240": "/flow/flowReClassification",
}


@pytest.mark.parametrize("version", ["9.3", "9.4", "9.5", "9.6"])
def test_flow_actions_are_writes_in_every_supported_profile(version):
    profiles = {profile["version"]: profile for profile in load_profiles(Settings().profiles_dir)}
    for operation_id, path in FLOW_ACTIONS.items():
        operation = profiles[version]["operations"][operation_id]
        assert (operation["method"], operation["path"], operation["risk"]) == ("POST", path, "write")
        assert not is_read_only_operation(operation)
        assert all("safe to execute without the write safeguard" not in note for note in operation["notes"])
