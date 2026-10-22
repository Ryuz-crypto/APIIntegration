"""Regression tests for the public ec-mcp stable installation documentation."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
EC_README = (REPO_ROOT / "ec-mcp" / "README.md").read_text(encoding="utf-8")
ENV_EXAMPLE = (REPO_ROOT / "ec-mcp" / ".env.example").read_text(encoding="utf-8")


def _ec_mcp_root_section() -> str:
    start = ROOT_README.index("## ec-mcp 5.0")
    end = ROOT_README.index("\n---\n\n## DashboardAPI-EC", start)
    return ROOT_README[start:end]


def test_root_readme_uses_env_file_as_single_source() -> None:
    section = _ec_mcp_root_section()

    assert "6.0.0" in section
    assert '"EC_MCP_ENV_FILE"' in section
    assert '"EC_ORCHESTRATOR_API_KEY"' not in section
    assert "./scripts/install_admin_service.sh --port 9090" in section
    assert "EC_UPDATE_GITHUB_TOKEN" in section
    assert 'run_show_api(command="show arp", appliance_id="0.NE")' in section


def test_internal_readme_documents_dynamic_admin_port_and_upgrade() -> None:
    assert "http://<servidor>:<EC_ADMIN_PORT>" in EC_README
    assert "## Upgrade por terminal" in EC_README
    assert "Fuente única de configuración" in EC_README
    assert "EC_ADMIN_LOGIN_WINDOW_SECONDS" in EC_README


def test_env_example_has_no_duplicate_active_keys() -> None:
    keys = [
        line.split("=", 1)[0].removeprefix("export ").strip()
        for line in ENV_EXAMPLE.splitlines()
        if line.strip().startswith("EC_") and "=" in line
    ]

    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    assert duplicates == []


def test_critical_v3_variables_are_in_template_and_documentation() -> None:
    required = {
        "EC_ORCHESTRATOR_URL",
        "EC_ORCHESTRATOR_API_KEY",
        "EC_VERIFY_TLS",
        "EC_SSH_ENABLED",
        "EC_ALLOW_WRITE_TOOLS",
        "EC_ALLOW_DANGEROUS_WRITES",
        "EC_MCP_AUTH_TOKEN",
        "EC_MCP_HOST",
        "EC_MCP_PORT",
        "EC_MCP_ALLOWED_HOSTS",
        "EC_ADMIN_HOST",
        "EC_ADMIN_PORT",
        "EC_ADMIN_PASSWORD",
        "EC_ADMIN_LOGIN_MAX_FAILURES",
        "EC_ADMIN_LOGIN_WINDOW_SECONDS",
        "EC_UPDATE_ALLOW_WEB",
        "EC_UPDATE_REPOSITORY",
        "EC_UPDATE_BRANCH",
        "EC_UPDATE_GITHUB_USER",
        "EC_UPDATE_GITHUB_TOKEN",
        "EC_UPDATE_STATE_DIR",
        "EC_UPDATE_SERVICE_NAME",
        "EC_UPDATE_ADMIN_SERVICE_NAME",
    }

    for key in required:
        assert key in ENV_EXAMPLE, f"{key} missing from .env.example"
        assert key in EC_README, f"{key} missing from ec-mcp/README.md"
