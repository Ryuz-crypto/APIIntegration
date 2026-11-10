"""Behavioral tests for the admin connection map."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from ec_mcp.admin_page import PAGE


def test_topology_uses_explicit_status_and_escapes_names() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the panel JavaScript")
    script = PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0].rsplit("boot();", 1)[0]
    harness = r"""
const assert = require('node:assert/strict');
const workspace = {innerHTML:''};
globalThis.localStorage = {getItem:()=>null, setItem:()=>{}};
globalThis.document = {
 documentElement:{style:{setProperty:()=>{}}},
 querySelector: key => key === '#workspace' ? workspace : null,
 addEventListener:()=>{}
};
globalThis.window = globalThis;
""" + script + r"""
STATE = {orchestrators:[{name:'<unsafe>', default:true}], sse_platforms:[{name:'Tenant B'}]};
renderTopology();
assert(workspace.innerHTML.includes('&lt;unsafe&gt;'));
assert(!workspace.innerHTML.includes('<unsafe>'));
assert(workspace.innerHTML.includes('Sin comprobar'));
assert(workspace.innerHTML.includes('sesiones no verificadas'));
assert(!workspace.innerHTML.includes('topology-status up'));
TOPOLOGY_STATUS = {
 checked_at:'2026-01-01T00:00:00Z',
 orchestrators:[{name:'<unsafe>',state:'up',checked_at:'2026-01-01T00:00:00Z'}],
 sse_platforms:[{name:'Tenant B',state:'down',error:'HTTP 403'}],
 mcp_transport:{state:'up'}
};
renderTopology();
assert(workspace.innerHTML.includes('Conectado'));
assert(workspace.innerHTML.includes('Con problemas'));
assert(workspace.innerHTML.includes('HTTP 403'));
assert(workspace.innerHTML.includes('no representan tráfico'));
renderLogin = () => {};
setLang('he');
assert.equal(document.documentElement.lang, 'he');
assert.equal(document.documentElement.dir, 'rtl');
renderTopology();
assert(workspace.innerHTML.includes('מפת חיבורים'));
assert(workspace.innerHTML.includes('עוזרי בינה מלאכותית'));
setLang('es');
assert.equal(document.documentElement.dir, 'ltr');
console.log('topology behavior verified');
"""
    result = subprocess.run(  # noqa: S603 - runs this repository's own panel script
        [node, "-"], input=harness, text=True, capture_output=True, check=False, timeout=20
    )
    assert result.returncode == 0, result.stderr
    assert "topology behavior verified" in result.stdout
