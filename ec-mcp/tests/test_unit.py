
import pathlib

from ec_mcp.compat import CompatibilityEngine, load_profiles
from ec_mcp.security import SecurityError, validate_show_command

PROFILES = pathlib.Path(__file__).parent.parent / "ec_mcp" / "profiles"


def test_load_profiles():
    profiles = load_profiles(PROFILES)
    versions = {p["version"] for p in profiles}
    assert {"9.3", "9.4", "9.5", "9.6"} <= versions


def test_resolve_and_version_match():
    engine = CompatibilityEngine(load_profiles(PROFILES))
    assert engine.match_version("9.6.4") == "9.6"
    assert engine.match_version("9.7.1") == "9.6"
    resolved = engine.resolve("9.6", "orchestrator.topology")
    assert resolved.method == "GET"
    resolved_interface = engine.resolve("9.6", "appliance.interfaces", {"appliance_id": "1.NE"})
    assert resolved_interface.path == "/interfaceState/1.NE"


def test_path_rendering():
    from ec_mcp.compat import render_path
    assert render_path("/interfaceState/{appliance_id}", {"appliance_id": "3.NE"}) == "/interfaceState/3.NE"
    try:
        render_path("/interfaceState/{appliance_id}", {})
        raise AssertionError("should have raised")
    except Exception as error:
        assert "Missing" in str(error)


def test_whitelist_accepts_show():
    for command in ("show bgp neighbors", "show ipsec sa", "show vrrp interface", "show mpls ldp session"):
        assert validate_show_command(command).startswith("show")
    assert validate_show_command("show version").startswith("show")
    assert validate_show_command("  show tunnel stats ").startswith("show")


def test_whitelist_rejects_dangerous():
    for command in [
        "terminal length 0",
        "config",
        "set admin password x",
        "reboot",
        "clear session all",
        "show version; reboot",
        "show version && whoami",
    ]:
        try:
            validate_show_command(command)
            raise AssertionError(f"should have rejected: {command}")
        except SecurityError:
            pass


def test_official_show_catalog_accepted():
    assert validate_show_command("show interfaces tunnel").startswith("show")
    assert validate_show_command("show stats tunnel").startswith("show")
    assert validate_show_command("show overlay").startswith("show")
    assert validate_show_command("show tech-support").startswith("show")
    assert validate_show_command("show ip-tracking").startswith("show")


def test_show_unknown_command_rejected():
    for command in ["show supersecret", "showx version"]:
        try:
            validate_show_command(command)
            raise AssertionError(f"should have rejected: {command}")
        except SecurityError:
            pass


def test_denied_patterns_still_reject():
    for command in [
        "show version; reboot",
        "show version && whoami",
        "show config",
        "show version | terminal length 0",
    ]:
        try:
            validate_show_command(command)
            raise AssertionError(f"should have rejected: {command}")
        except SecurityError:
            pass


def test_cli_catalog_over_1000_commands():
    from ec_mcp.cli_catalog import catalog_entries, total_commands

    assert total_commands() >= 1000
    entries = catalog_entries()
    assert len(entries) == total_commands()
    risks = {e["risk"] for e in entries}
    assert risks == {"read", "diagnostic", "write"}
    categories = {e["category"] for e in entries}
    assert categories == {"monitoring", "troubleshooting", "alarm", "administration", "configuration", "negation"}


def test_classify_cli_command():
    from ec_mcp.cli_catalog import catalog_entries

    risk_by_command = {e["command"]: e["risk"] for e in catalog_entries()}

    def classify(command: str) -> str | None:
        lowered = command.strip().lower()
        for entry in sorted(risk_by_command, key=len, reverse=True):
            if lowered == entry or lowered.startswith(entry + " "):
                return risk_by_command[entry]
        return None

    assert classify("show version") == "read"
    assert classify("show interfaces tunnel 1/2") == "read"
    assert classify("ping 10.0.0.1") == "diagnostic"
    assert classify("interface shutdown 1") == "write"
    assert classify("no interface shutdown 1") == "write"
    assert classify("configure terminal") == "write"
    assert classify("show fakecommand123") is None
    assert classify("rm -rf /") is None


def test_list_api_operations_tool():
    import asyncio

    from ec_mcp.server import create_server

    server = create_server()
    result = asyncio.run(server.call_tool("list_api_operations", {}))
    text = result.content[0].text
    assert text.startswith("{")
    assert '"operation"' in text and '"method"' in text and '"path"' in text
    assert not text.startswith("Error")
