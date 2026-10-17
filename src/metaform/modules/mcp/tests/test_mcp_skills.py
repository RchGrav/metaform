"""Universal skill distribution over MCP, BASE-059."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from types import SimpleNamespace

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Implementation

from metaform import prompt_files
from metaform.modules.mcp import server

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-059')]


@pytest.fixture
def folder(run, tmp_path):
    run('enable', 'mcp')
    run('disable', 'workflow')
    server.listing(tmp_path)
    return tmp_path


def test_skill_tool_survives_disabled_workflow_and_separates_discovery_from_address_loading(folder):
    declared = server.listing(folder)
    assert 'metaform_skills' in declared
    assert declared['metaform_skills'].annotations()['read_only_hint']
    error, blocks = server.run_chassis(folder, 'skills', {})
    assert not error
    discovered = json.loads(blocks[-1])['skills']
    assert discovered and all(one['discover'] for one in discovered)
    assert 'sentinel' not in {one['name'] for one in discovered}
    error, blocks = server.run_chassis(folder, 'skills', {'all': True})
    assert not error
    assert 'sentinel' in {one['name'] for one in json.loads(blocks[-1])['skills']}
    loaded = []
    for name in ('sentinel', 'logic.skill.sentinel'):
        error, blocks = server.run_chassis(folder, 'skills', {'op': 'load', 'name': name})
        assert not error, blocks
        loaded.append(json.loads(blocks[-1]))
    assert loaded[0] == loaded[1]
    assert loaded[0]['procedure'] and loaded[0]['libs']
    error, blocks = server.run_chassis(folder, 'skills', {
        'op': 'read', 'name': 'logic.skill.sentinel', 'path': 'SKILL.md'})
    assert not error and 'sentinel' in json.loads(blocks[-1])['text']
    for arguments in ({'op': 'load'}, {'op': 'read', 'name': 'sentinel'},
                      {'op': 'read', 'name': 'sentinel', 'path': '../prompts.xml'}, {'op': 'missing'}):
        assert server.run_chassis(folder, 'skills', arguments)[0]


@pytest.mark.parametrize(('mode', 'deployed', 'shown'), [
    ('auto', False, True), ('auto', True, False), ('on', True, True), ('off', False, False)])
def test_connect_index_uses_deployment_evidence_and_explicit_setting(folder, monkeypatch, mode, deployed, shown):
    from metaform import install, settings
    monkeypatch.setattr(install, 'skills_deployed', lambda client: deployed and client == 'claude-code', raising=False)
    settings.put('skill_index', mode, folder)
    index = server.skill_index(folder, 'claude-code')
    assert bool(index) == shown
    if shown:
        assert 'write-workflow' in index and 'metaform_skills' in index and 'load' in index
        assert 'sentinel' not in index and 'workflow-evaluator' not in index
    if mode == 'auto':
        assert server.skill_index(folder, None)
        assert server.skill_index(folder, 'another-client')


SHIPPED = ('dispatch', 'fork', 'hello', 'intake', 'map', 'mcp', 'memory', 'packet', 'template', 'web', 'workflow')


@pytest.mark.req('MCP-029')
def test_connect_message_and_index_fit_what_the_host_keeps(folder, run):
    """The startup text and the fallback index together stay within the 2,048 characters Claude Code keeps, with
    every shipped module on and the first-run notice; the names alone when the descriptions do not fit."""
    sent = server.connect_instructions(folder, 'unknown-host')
    skills = server.listing(folder, 'unknown-host')['metaform_skills']
    assert len(sent) <= 2048 and 'FIRST RUN' in sent
    assert 'write-workflow' in sent or 'write-workflow' in skills.description + skills.guide()  # else with the tool
    for module in SHIPPED:
        run('enable', module)
    for registered in (False, True):
        if registered:
            run('add', 'project', 'skills', str(folder))
        sent = server.connect_instructions(folder, 'unknown-host')
        assert len(sent) <= 2048 and 'FIRST RUN' in sent, len(sent)
        assert sent.startswith(prompt_files.module('mcp', 'connect_use'))
        skills = server.listing(folder, 'unknown-host')['metaform_skills']
        listed = skills.description + skills.guide()  # the names come with the tool's first use, MCP-039
        assert 'write-workflow' in sent or 'write-workflow' in listed


@pytest.mark.req('MCP-028')
def test_a_stdio_connect_from_an_unrecorded_harness_carries_the_provisioning_notice(folder, run, monkeypatch):
    """The AI tool that started a stdio server is told once to provision it: in the connect message when it fits what
    the host keeps, else with the session's first tool result. An HTTP connect, whose client did not start the
    server, and a recorded harness are not told."""
    from pathlib import Path

    from metaform import harness
    monkeypatch.setattr(server, 'TOLD', set())
    monkeypatch.setattr(harness, 'running', lambda: Path(os.path.abspath(os.sep)) / 'opt' / 'harness' / 'bin' / 'tool')
    notice = f'Notice: {harness.NOTICE}'
    assert notice not in server.connect_instructions(folder, 'unknown-host')  # HTTP: no session of the harness
    sent = server.connect_instructions(folder, 'unknown-host', 'one')
    assert notice in sent and len(sent) <= 2048 and sent.startswith(prompt_files.module('mcp', 'connect_use'))
    assert server.provisioning('one') is None  # told once
    for module in SHIPPED:  # no room left at connect: the first tool result carries it instead
        run('enable', module)
    server.TOLD.add('measured')  # the message without the notice is all the host keeps here
    monkeypatch.setattr(server, 'HOST_KEEPS', len(server.connect_instructions(folder, 'unknown-host', 'measured')))
    sent = server.connect_instructions(folder, 'unknown-host', 'two')
    assert notice not in sent and len(sent) <= 2048
    assert server.provisioning('two') == notice
    harness.done(harness.running())
    assert server.provisioning('three') is None


def test_client_identity_accepts_initialize_params_and_modern_request_metadata():
    def context(params):
        return SimpleNamespace(params=params, session=SimpleNamespace(client_params=None))
    assert server.client_name(context({'clientInfo': {'name': 'claude-code'}})) == 'claude-code'
    assert server.client_name(context({'_meta': {
        'io.modelcontextprotocol/clientInfo': {'name': 'codex-mcp-client'}}})) == 'codex-mcp-client'
    assert server.client_name(context({})) is None


def test_real_wire_serves_skills_and_injects_fallback_at_initialize_and_discover(folder, home, monkeypatch):
    user = folder / 'user'
    user.mkdir()
    monkeypatch.setenv('HOME', str(user))
    monkeypatch.setenv('USERPROFILE', str(user))
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    async def check():
        async with stdio_client(params) as (read, write), ClientSession(
                read, write, client_info=Implementation(name='unknown-skill-host', version='1')) as client:
            init = await client.initialize()
            assert 'write-workflow' in init.instructions and 'sentinel' not in init.instructions
            loaded = await client.call_tool('metaform_skills', {'op': 'load', 'name': 'logic.skill.sentinel'})
            assert not loaded.is_error, loaded
            assert loaded.structured_content['name'] == 'sentinel'
            assert loaded.structured_content['libs']
    asyncio.run(check())
    from metaform.probe import Session
    client = Session([params.command, *params.args], cwd=folder, env=params.env)
    try:
        result = client.request('server/discover', {}, deadline=time.monotonic() + 15)
        assert 'write-workflow' in result['instructions'] and 'sentinel' not in result['instructions']
    finally:
        client.close()

    from metaform import install, probe
    tool = install.tools()['claude']
    plan = install._skill_plan(tool)
    assert plan is not None
    install._deploy_skills(tool, plan, folder / 'backups')

    async def native():
        async with stdio_client(params) as (read, write), ClientSession(
                read, write, client_info=Implementation(name='claude-code', version='1')) as client:
            init = await client.initialize()
            assert 'Skills:' not in init.instructions
            loaded = await client.call_tool('metaform_skills', {'op': 'load', 'name': 'logic.skill.sentinel'})
            assert not loaded.is_error
    asyncio.run(native())
    monkeypatch.setattr(probe, 'CLIENT', {'name': 'claude-code', 'version': '1'})
    client = Session([params.command, *params.args], cwd=folder, env=params.env)
    try:
        result = client.request('server/discover', {}, deadline=time.monotonic() + 15)
        assert 'Skills:' not in result['instructions']
    finally:
        client.close()
