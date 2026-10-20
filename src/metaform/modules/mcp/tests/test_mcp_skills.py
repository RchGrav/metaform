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
    for name in ('sentinel', 'prompt.skill.sentinel'):
        error, blocks = server.run_chassis(folder, 'skills', {'op': 'load', 'name': name})
        assert not error, blocks
        loaded.append(json.loads(blocks[-1]))
    assert loaded[0] == loaded[1]
    assert loaded[0]['procedure'] and loaded[0]['libs']
    error, blocks = server.run_chassis(folder, 'skills', {
        'op': 'read', 'name': 'prompt.skill.sentinel', 'path': 'SKILL.md'})
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
def test_the_skill_index_is_in_the_role_block_whole_and_the_connect_message_stays_a_few_links(folder, run):
    """The connect message is the directive and its links, with every shipped module on, registered or not and before
    an intake; the fallback skill index comes whole in the person's role block, never cut to fit."""
    for module in SHIPPED:
        run('enable', module)
    for registered in (False, True):
        if registered:
            run('add', 'project', 'skills', str(folder))
        sent = server.connect_instructions(folder)
        assert len(sent) <= 512 and 'metaform://firstrun' in sent and 'Skills:' not in sent, sent
        assert sent.startswith(prompt_files.module('mcp', 'connect_directive') + '\nmetaform://rules\n')
        role = server.role_text(folder, 'unknown-host')
        assert server.skill_index(folder, 'unknown-host') in role and 'write-workflow' in role


@pytest.mark.req('MCP-028')
def test_a_stdio_session_from_an_unrecorded_harness_is_told_to_provision_with_its_first_tool_result(folder, run,
                                                                                                    monkeypatch):
    """The AI tool that started a stdio server is told once to provision it, with the session's first tool result;
    the connect message holds only the directive and its links. A recorded harness is not told."""
    from pathlib import Path

    from metaform import harness
    monkeypatch.setattr(server, 'TOLD', set())
    monkeypatch.setattr(harness, 'running', lambda: Path(os.path.abspath(os.sep)) / 'opt' / 'harness' / 'bin' / 'tool')
    notice = f'Notice: {harness.NOTICE}'
    assert notice not in server.connect_instructions(folder)
    assert server.provisioning('one') == notice
    harness.done(harness.running())
    assert server.provisioning('two') is None


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
            skills = server.listing(folder, 'unknown-skill-host')['metaform_skills']
            described = skills.description + skills.guide()  # the names come with the tool's first use, MCP-039
            role = (await client.read_resource('metaform://role/person')).contents[0].text
            assert 'metaform://role/person' in init.instructions and 'write-workflow' in role  # whole, BASE-059
            assert 'write-workflow' in described and 'sentinel' not in role
            loaded = await client.call_tool('metaform_skills', {'op': 'load', 'name': 'prompt.skill.sentinel'})
            assert not loaded.is_error, loaded
            assert loaded.structured_content['name'] == 'sentinel'
            assert loaded.structured_content['libs']
    asyncio.run(check())
    from metaform.probe import Session
    client = Session([params.command, *params.args], cwd=folder, env=params.env)
    try:
        result = client.request('server/discover', {}, deadline=time.monotonic() + 15)
        assert 'sentinel' not in result['instructions']
        assert result['instructions'].startswith(prompt_files.module('mcp', 'connect_directive') + '\n')
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
            await client.initialize()
            assert 'Skills:' not in (await client.read_resource('metaform://role/person')).contents[0].text
            loaded = await client.call_tool('metaform_skills', {'op': 'load', 'name': 'prompt.skill.sentinel'})
            assert not loaded.is_error
    asyncio.run(native())
    monkeypatch.setattr(probe, 'CLIENT', {'name': 'claude-code', 'version': '1'})
    client = Session([params.command, *params.args], cwd=folder, env=params.env)
    try:
        result = client.request('server/discover', {}, deadline=time.monotonic() + 15)
        assert 'Skills:' not in result['instructions'] and 'metaform://role/person' in result['instructions']
    finally:
        client.close()
