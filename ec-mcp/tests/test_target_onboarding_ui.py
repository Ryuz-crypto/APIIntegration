"""Regression tests for one-step target onboarding."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from ec_mcp.admin_page import PAGE


def test_target_activation_only_restarts_after_success():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    script = PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0].rsplit("boot();", 1)[0]
    harness = r"""
const assert = require('node:assert/strict');
globalThis.localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
globalThis.document={documentElement:{dataset:{},style:{setProperty:()=>{}}},querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}};
globalThis.window=globalThis;globalThis.confirm=()=>true;globalThis.prompt=()=>'panel-pass';
""" + script + r"""
const fields={};q=id=>fields[id]||(fields[id]={value:''});
q('#o-name').value='new';q('#o-url').value='https://example';q('#o-user').value='alice';q('#o-password').value='test';q('#o-tls').value='true';
let calls=[],fail=true;api=async(path,body)=>{calls.push(path);if(path==='/api/orchestrators')return fail?{ok:false,error:'failed'}:{ok:true,message:'saved'};if(path==='/api/restart')return {state:'pending'};return {orchestrators:[],sse_platforms:[]}};
notice=()=>{};renderOrchestrators=()=>{};pollRestart=()=>{};
(async()=>{await saveOrch(true);assert(!calls.includes('/api/restart'));assert.equal(q('#o-password').value,'test');fail=false;calls=[];await saveOrch(true);assert(calls.includes('/api/restart'));console.log('verified')})().catch(e=>{console.error(e);process.exit(1)});
"""
    result = subprocess.run(  # noqa: S603 - repository panel script under Node
        [node, "-"], input=harness, text=True, capture_output=True, timeout=20, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout
