"""Documentation sync: every registered MCP tool must be documented in README.md."""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def _registered_tools() -> set[str]:
    import re as _re

    server_src = (Path(__file__).resolve().parents[1] / "ec_mcp" / "server.py").read_text(encoding="utf-8")
    return set(_re.findall(r"@mcp\.tool\(\)\s*\n\s*def ([a-zA-Z_][a-zA-Z0-9_]*)\(", server_src))


def test_every_registered_tool_is_documented_in_readme():
    readme = README.read_text(encoding="utf-8")
    tools = _registered_tools()
    assert tools, "No tools found in server.py; the extractor is broken."
    missing = sorted(name for name in tools if f"`{name}`" not in readme)
    assert not missing, (
        f"These registered MCP tools are not documented in README.md: {missing}. "
        "Add them to the 'Herramientas MCP' table (or the relevant section)."
    )


def test_readme_declares_tool_count_consistently():
    readme = README.read_text(encoding="utf-8")
    tools = _registered_tools()
    counts = {int(m) for m in re.findall(r"\*\*(\d+) tools?\*\*", readme)}
    assert counts, "README does not state a tool count with the '**N tools**' marker."
    assert str(len(tools)) in {str(c) for c in counts}, (
        f"README tool count(s) {sorted(counts)} do not match the {len(tools)} tools registered in server.py."
    )


def test_readme_version_header_matches_package():
    from ec_mcp import __version__

    readme = README.read_text(encoding="utf-8")
    assert f"**Versión estable: {__version__}**" in readme, (
        f"README header must state the installed version {__version__}."
    )
