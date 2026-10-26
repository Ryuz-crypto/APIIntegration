"""Regression tests for the generated administrative page."""

from __future__ import annotations

from ec_mcp.admin_page import PAGE


def test_load_all_is_declared_before_its_body() -> None:
    loader = "async function loadAll(){"
    body = "try{var results=await Promise.all([api('/api/state'),api('/api/config'),api('/api/update/status')])"

    assert loader in PAGE
    assert body in PAGE
    assert PAGE.index(loader) < PAGE.index(body)
    assert "await loadAll();" in PAGE
