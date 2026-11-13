"""Locale catalog coverage and placeholder regression checks."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from ec_mcp.admin_page import PAGE


def test_all_panel_locales_cover_catalog_and_placeholders():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    script = PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0].rsplit("boot();", 1)[0]
    harness = r"""
const assert=require('node:assert/strict');
globalThis.localStorage={getItem:()=>null};
globalThis.document={documentElement:{dataset:{},style:{setProperty:()=>{}}},querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}};
globalThis.window=globalThis;
""" + script + r"""
const placeholders=v=>[...String(v).matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map(x=>x[1]).sort();
for(const [code] of LANGS){
 for(const key of Object.keys(I18N.en)){
  assert.equal(typeof I18N[code][key],'string',code+': missing '+key);
  assert(I18N[code][key].length>0,code+': empty '+key);
  assert.deepEqual(placeholders(I18N[code][key]),placeholders(I18N.en[key]),code+': placeholders '+key);
 }
}
assert.equal(I18N.en.tok_close,'Close');
assert.equal(I18N.en.tok_revoke,'Revoke');
assert.equal(I18N.he.save_activate,'שמירה והפעלה');
console.log('locale catalogs verified');
"""
    result = subprocess.run(  # noqa: S603 - repository panel JavaScript under Node
        [node, "-"], input=harness, text=True, capture_output=True, check=False, timeout=20
    )
    assert result.returncode == 0, result.stderr
