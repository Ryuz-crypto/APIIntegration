"""Behavioral regression tests for the setup wizard."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from ec_mcp.admin_page import PAGE


def test_wizard_reviews_and_saves_same_changed_fields() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the panel JavaScript")
    script = PAGE.split("<script>", 1)[1].rsplit("</script>", 1)[0]
    script = script.rsplit("boot();", 1)[0]
    harness = r"""
const assert = require('node:assert/strict');
const elements = {'#workspace': {innerHTML:''}, '#wiz-diff': {innerHTML:''}, '#notice': {innerHTML:''}};
globalThis.localStorage = {getItem: () => null, setItem: () => {}};
globalThis.document = {querySelector: key => elements[key] || null, addEventListener: () => {}};
globalThis.window = globalThis;
""" + script + r"""
(async () => {
  WIZARD = {env_file: '/example/.env', steps: [{id:'one'}, {id:'two'}], fields: [
    {key:'URL', step:'one', value:'old', secret:false},
    {key:'USER', step:'two', value:'old-user', secret:false},
    {key:'KEY', step:'one', value:'', secret:true, configured:true},
    {key:'UNCHANGED_SECRET', step:'two', value:'', secret:true, configured:true},
    {key:'DISABLED', step:'two', value:'old', secret:false, depends_on:['MODE','true']},
    {key:'MODE', step:'one', value:'false', secret:false}
  ], state:{}};
  WDRAFT = {URL:'new', USER:'new-user', KEY:'new-secret', UNCHANGED_SECRET:'', DISABLED:'hidden-change', MODE:'false'};
  WSTEP = 1;
  const calls = [];
  api = async (path, body) => {
    calls.push({path, body});
    if (path === '/api/config/diff') return {ok:true, errors:[], changes:[]};
    if (path === '/api/config' && body) return {ok:true, message:'saved'};
    if (path === '/api/config') return {fields:[]};
    if (path === '/api/wizard') return {steps:[], fields:[]};
    throw Error('unexpected ' + path);
  };
  await wizReview();
  assert.deepEqual(calls[0].body.values, {URL:'new', USER:'new-user', KEY:'new-secret'});
  await wizSave(false);
  assert.deepEqual(calls[1].body.values, calls[0].body.values);
  assert.deepEqual(WDRAFT, {});
  assert.equal(WREVIEW, null);
  calls.length = 0;
  await wizSave(false);
  assert.equal(calls.length, 0);
  console.log('wizard behavior verified');
})().catch(error => {console.error(error); process.exitCode=1});
"""
    result = subprocess.run(
        [node, "-"],
        input=harness,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "wizard behavior verified" in result.stdout
