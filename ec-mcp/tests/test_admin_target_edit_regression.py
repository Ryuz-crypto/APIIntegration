"""Regression tests for editing saved targets and preserving the selected tab."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from ec_mcp.admin_page import PAGE


def test_target_edit_and_language_tab_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    script = PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0].rsplit("boot();", 1)[0]
    harness = r"""
const assert = require('node:assert/strict');
globalThis.localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
globalThis.document={documentElement:{dataset:{},style:{setProperty:()=>{}}},querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}};
globalThis.window=globalThis;
""" + script + r"""
const fields={};q=id=>fields[id]||(fields[id]={value:''});
STATE={orchestrators:[{name:'A',url:'https://example',username:'alice',verify_tls:true,ssh_user:'bob',ssh_host:'host'}],sse_platforms:[{name:'S',provider:'axis',base_url:'https://sse',verify_tls:true,timeout:30}]};
fields['#o-key']={value:'previous-secret'};fields['#o-password']={value:'old'};
editOrch('A');assert.equal(q('#o-user').value,'alice');assert.equal(q('#o-key').value,'');assert.equal(q('#o-password').value,'');
fields['#s-token']={value:'previous-secret'};editSse('S');assert.equal(q('#s-token').value,'');
let payload;api=async(path,body)=>{if(body)payload=body;return {ok:true}};notice=()=>{};renderOrchestrators=()=>{};
(async()=>{await saveOrch();assert.equal(payload.username,'alice');assert.equal(payload.ssh_host,'host');assert.equal(payload.api_key,'');
AUTHED=true;CURTAB='users';renderShell=()=>{CURTAB='home'};showTab=name=>{CURTAB=name};setLang('en');assert.equal(CURTAB,'users');
assert.equal(t('diag_memory'),'Memory');console.log('verified');})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(  # noqa: S603 - repository JavaScript under Node
        [node, "-"], input=harness, text=True, capture_output=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout
