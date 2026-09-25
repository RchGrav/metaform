"""The mcp module: every surfaced module verb as a tool, live instructions, MCP-001 to MCP-008 and MCP-025."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform.data import Store

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"
BASE = ("Metaform keeps this project's functional map: what each part is for, who receives what it does, and how. "
        'Read the map before you change the project, so you work from the purpose of each part. Each tool comes '
        'from a module; the sections below say what each module is for. A tool named <module>_<verb> takes the '
        "verb's nouns and switches as named arguments. A tool error ends with the one next step to take. For any "
        "module's full help, run metaform help <module>.")


def session(home, folder, fn):
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    async def go():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                init = await client.initialize()
                return await fn(client, init)
    return asyncio.run(go())


def text(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None]


async def tool_names(client):
    return {tool.name: tool for tool in (await client.list_tools()).tools}


@pytest.fixture
def mapped(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                            provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.timer.kitchen', name='kitchen timer', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name='audible alarm', name_length=2, role='SE')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       function='Plays a tone.', relation='The alarm rings.', observation='A piezo.')
    return folder


@pytest.mark.req('MCP-001')
def test_mcp_is_a_module_and_off_means_no_server(run, module_row, tmp_path):
    assert module_row('mcp')[1] == 'on'
    run('disable', 'mcp')
    refused = run('mcp', 'serve', ok=False)
    assert refused.returncode == 2 and refused.stderr.splitlines()[-1] == 'Next: metaform enable mcp'
    run('list', 'projects')


@pytest.mark.req('MCP-002')
@pytest.mark.req('MCP-003')
@pytest.mark.req('MCP-007')
@pytest.mark.req('MCP-008')
def test_the_server_lists_each_surfaced_verb_as_a_tool_and_composes_its_instructions(run, home, mapped):
    async def check(client, init):
        return init.instructions, await tool_names(client)
    instructions, tools = session(home, mapped, check)
    assert instructions.startswith(BASE + '\n\n## intake\n') or instructions.startswith(BASE + '\n\n## map\n')
    sections = [line[3:] for line in instructions.splitlines() if line.startswith('## ')]
    assert sections == sorted(sections) and {'map', 'mcp', 'memory'} <= set(sections)
    assert "## map\nReads and writes this project's functional map." in instructions
    assert ('## memory\nNotes that agents keep at the map\'s own nodes, in the reference memory server\'s operations.'
            in instructions)
    assert '## mcp\nServes Metaform\'s tools to AI tools over MCP. Every tool is also a metaform command on the CLI. ' \
           'Details: metaform help mcp.' in instructions
    assert 'mcp_serve' not in tools and 'map_approve' not in tools
    schema = tools['map_joins'].input_schema
    assert schema['properties']['element'] == {'type': 'string'} and schema['required'] == ['element']
    assert schema['properties']['project']['type'] == 'string' and schema['additionalProperties'] is False
    assert schema['properties']['raw'] == {'type': 'boolean'}
    assert tools['memory_add-observations'].input_schema['properties']['text'] == {'type': 'array',
                                                                               'items': {'type': 'string'}}


@pytest.mark.req('MCP-003')
@pytest.mark.req('BASE-036')
@pytest.mark.req('STORE-023')
@pytest.mark.req('LAYER-016')
def test_a_tool_returns_what_the_cli_returns(run, home, mapped):
    cli = json.loads(run('map', 'joins', 'code.timer.kitchen', '--json', cwd=mapped).stdout)

    async def call(client, init):
        return text(await client.call_tool('map_joins', {'element': 'code.timer.kitchen'}))
    blocks = session(home, mapped, call)
    assert json.loads(blocks[-1]) == cli
    assert cli['results'][0]['layer'] == 'intake-1'


@pytest.mark.req('MCP-003')
def test_a_verb_added_to_a_module_is_a_tool_with_no_mcp_code(run, home, mapped, user_module):
    user_module('added', f'''
        from metaform.module import Module, Noun, Verb
        {OS}
        async def twice(ctx):
            return {{'twice': ctx.nouns['n'] * 2}}
        MODULE = Module(id='added', summary='x', purpose='Adds. Details: metaform help added.',
                        verbs=(Verb('twice', twice, 'Double a number.', nouns=(Noun('n', 'A number.', kind='int'),)),))
    ''')

    async def call(client, init):
        tools = await tool_names(client)
        result = await client.call_tool('added_twice', {'n': 21})
        return tools['added_twice'].description, text(result)
    description, blocks = session(home, mapped, call)
    assert description == 'Double a number.' and json.loads(blocks[-1]) == {'twice': 42}


@pytest.mark.req('MCP-004')
@pytest.mark.req('LAYER-018')
@pytest.mark.req('CLI-022')
def test_the_tool_list_follows_the_folders_command_surface(run, home, mapped):
    run('set', '--modules', 'memory,mcp', cwd=mapped)

    async def narrowed(client, init):
        tools = await tool_names(client)
        refused = await client.call_tool('map_knowledge', {'op': 'create', 'layer': 'x'})
        return set(tools), refused.is_error, text(refused)
    names, error, message = session(home, mapped, narrowed)
    assert 'map_knowledge' not in names and 'memory_open-nodes' in names
    assert error and message[0].splitlines() == ['Error: No tool map_knowledge on this surface.',
                                                 'Next: metaform help commands']
    run('unset', '--modules', cwd=mapped)

    async def restored(client, init):
        return 'map_knowledge' in await tool_names(client)
    assert session(home, mapped, restored)


@pytest.mark.req('MCP-005')
@pytest.mark.req('CLI-011')
def test_a_boolean_false_on_one_call_overrides_a_glued_true(run, home, mapped, user_module):
    user_module('tmuxed', f'''
        from metaform import settings
        from metaform.module import Module, Verb
        {OS}
        settings.boolean('tmux', False, help='Use tmux.')
        MODULE = Module(id='tmuxed', summary='x', purpose='Tmux. Details: metaform help tmuxed.',
                        verbs=(Verb('show', lambda ctx: {{'tmux': ctx.setting('tmux')}}, 'Show tmux.',
                                    switches=('tmux',)),))
    ''')
    run('set', '--tmux', '--glue', cwd=mapped)

    async def call(client, init):
        tools = await tool_names(client)
        off = text(await client.call_tool('tmuxed_show', {'tmux': False}))
        stored = text(await client.call_tool('tmuxed_show', {}))
        return tools['tmuxed_show'].input_schema['properties']['tmux'], off, stored
    schema, off, stored = session(home, mapped, call)
    assert schema == {'type': 'boolean'}
    assert json.loads(off[-1]) == {'tmux': False} and json.loads(stored[-1]) == {'tmux': True}
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert (shown['tmux']['value'], shown['tmux']['state']) == (True, 'glued')


@pytest.mark.req('MCP-006')
@pytest.mark.req('BASE-013')
def test_tool_errors_end_with_the_one_next_step_the_cli_gives(run, home, mapped):
    run('enable', 'helloworld')
    cli = run('map', 'element', 'code.nothing', cwd=mapped, ok=False).stderr.splitlines()

    async def call(client, init):
        missing = await client.call_tool('map_element', {'element': 'code.nothing'})
        caution = await client.call_tool('helloworld_forget', {})
        return missing.is_error, text(missing), caution.is_error, text(caution)
    error, missing, caution_error, caution = session(home, mapped, call)
    assert error and missing[0].splitlines() == cli
    assert caution_error and caution[0].splitlines() == [
        'Error: This deletes the greeting history.', 'Next: If you are sure: call helloworld_forget with confirm true']


@pytest.mark.req('MCP-007')
def test_instructions_change_with_the_modules_on_the_next_connection(run, home, mapped):
    async def sections(client, init):
        return [line[3:] for line in init.instructions.splitlines() if line.startswith('## ')]
    assert 'helloworld' not in session(home, mapped, sections)
    run('enable', 'helloworld')
    assert 'helloworld' in session(home, mapped, sections)


@pytest.mark.req('MCP-025')
@pytest.mark.req('BASE-028')
def test_every_tool_takes_a_project_and_concurrent_calls_stay_apart(run, home, mapped, tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))

    async def call(client, init):
        create = [client.call_tool('map_knowledge', {'op': 'create', 'layer': 'notes', 'variable': 'Notes.',
                                                     'mutable': True, 'hideable': True, 'module': 'test',
                                                     'project': project}) for project in ('proj', 'other')]
        await asyncio.gather(*create)
        added = [client.call_tool('map_knowledge', {'op': 'add-element', 'layer': 'notes', 'address': f'code.{project}',
                                                    'project': project}) for project in ('proj', 'other')]
        results = await asyncio.gather(*added)
        ghost = await client.call_tool('map_layers', {'project': 'ghost'})
        return [result.is_error for result in results], ghost.is_error, text(ghost)
    errors, ghost_error, ghost = session(home, mapped, call)
    assert errors == [False, False]
    assert Store('proj').element('code.proj', raw=True) is not None
    assert Store('proj').element('code.other', raw=True) is None
    assert Store('other').element('code.other', raw=True) is not None
    assert ghost_error and ghost[0].splitlines()[-1] == 'Next: metaform list projects'


@pytest.mark.req('PROJ-005')
@pytest.mark.req('MCP-011')
def test_a_server_started_outside_every_project_selects_one_with_set(run, home, mapped, tmp_path):
    outside = tmp_path / 'desktop'
    outside.mkdir()

    async def call(client, init):
        before = await client.call_tool('map_layers', {})
        chosen = await client.call_tool('set', {'project': 'proj'})
        after = await client.call_tool('map_layers', {})
        return init.instructions, before.is_error, text(before), chosen.is_error, after.is_error, text(after)
    instructions, before_error, before, chosen_error, after_error, after = session(home, outside, call)
    assert instructions.rstrip().endswith('To register one: metaform add project <id> <path>')
    assert before_error and before[0].splitlines()[-1] == 'Next: metaform set --project <id>'
    assert not chosen_error and not after_error
    assert [layer['name'] for layer in json.loads(after[-1])['results']] == ['intake-1']


@pytest.mark.req('BASE-009')
@pytest.mark.req('BASE-036')
def test_an_async_verb_and_a_string_result_over_mcp(run, home, mapped):
    run('enable', 'helloworld')

    async def call(client, init):
        return text(await client.call_tool('helloworld_wait', {'seconds': 0}))
    assert session(home, mapped, call) == ['waited 0 s\n']
