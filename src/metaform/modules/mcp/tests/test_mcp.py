"""The mcp module: surfaced tools, calls and project selection."""
from __future__ import annotations

import ast
import asyncio
import contextlib
import dataclasses
import functools
import importlib
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import textwrap
import time
import typing

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform.data import Node, Store
from metaform.modules.mcp.server import mcp_next, startup_instructions


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"
CHASSIS_TOOLS = {'metaform_set', 'metaform_feedback', 'metaform_list_reports', 'metaform_read_report',
                 'metaform_instructions', 'metaform_register', 'metaform_skills'}
REGISTERED_TOOLS = CHASSIS_TOOLS - {'metaform_register'}  # registering is listed until the folder has a project


@pytest.fixture(autouse=True)
def whole_context(request):
    """The server gives context whole, every tool listed and every result as JSON, as the tests written before
    2026-10-17 read it; the catalog's tests ask for tight, the default since, with `session(..., tight=True)`."""
    if 'home' not in request.fixturenames:
        return
    request.getfixturevalue('home')
    request.getfixturevalue('run')('set', '--mcp-context', 'whole')


def session(home, folder, fn, heard=None, tight=False, env=None):
    """A real MCP client on `metaform mcp serve` in the folder; the methods of the notifications it hears go in
    `heard`. The server gives context whole, as the tests written before 2026-10-17 read it, the other modules' tests
    that use this helper among them; with `tight`, as it does by default."""
    from metaform import settings as stored
    wanted = 'tight' if tight else 'whole'
    try:
        held = stored.value('mcp_context', folder)
    except KeyError:  # the mcp module is not loaded in this process: ask the command line
        held = None
    person = {key: value for key, value in os.environ.items() if key not in ('METAFORM_ROLE', 'METAFORM_SESSION',
                                                                             'METAFORM_WORK', 'METAFORM_NODE')}
    if held != wanted:  # stored once, so a test that counts the home's changes hears no setting of its own
        subprocess.run([sys.executable, '-m', 'metaform', 'set', '--mcp-context', wanted], cwd=str(folder),
                       env={**person, 'METAFORM_HOME': str(home)}, check=True, capture_output=True)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home), **(env or {})})

    async def hear(message):
        method = getattr(message, 'method', None)
        if heard is not None and method:
            heard.append(method)

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write, message_handler=hear) as client:
            init = await client.initialize()
            return await fn(client, init)
    return asyncio.run(go())


@pytest.mark.req('MCP-034')
@pytest.mark.req('MCP-032')
def test_workflow_skills_read_the_same_skill_by_tool_and_prompt(run, home, mapped):
    run('enable', 'workflow')
    from metaform.modules.workflow import SKILLS
    names = tuple(name for name in SKILLS if name not in ('sentinel', 'workflow_evaluator'))

    async def check(client, init):
        assert 'workflow_skill' in await listed(client)
        declared = {one.name for one in (await client.list_prompts()).prompts}
        assert set(names) <= declared
        assert not {'sentinel', 'workflow_evaluator'} & declared
        results = {}
        for name in names:
            tool = await called(client, 'workflow_skill', {'name': name})
            assert not tool.is_error
            skill = text(tool)[-1].strip()
            prompt = await client.get_prompt(name, {})
            results[name] = (skill, prompt.messages[0].content.text)
        return results

    from metaform import prompt_files
    from metaform.modules.workflow import PACKAGE
    declared = {name: (before, after) for name, _, before, after, _ in prompt_files.commands(PACKAGE)}
    for name, (skill, prompt) in session(home, mapped, check).items():
        before, after = declared[name]
        assert prompt == (before + skill + after).strip()
        assert skill == run('workflow', 'skill', name, cwd=mapped).stdout.strip()


# A tool's guidance, given once per session with the first result, MCP-039: tested on its own, so the other tests read
# the result without it.
GUIDED = re.compile(r"^(How to use \S+|The \S+ module's rules), given once in this session")


def text(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None
            and not GUIDED.match(item.text)]


class Command:
    """One command of a tool, with what it takes."""

    def __init__(self, description, input_schema):
        self.description, self.input_schema = description, input_schema


async def listed(client):
    return {tool.name: tool for tool in (await client.list_tools()).tools}


async def tool_names(client):
    """Every command the server offers, by its tool's name, `<module>_<command>` or `metaform_<command>`, with the
    description and input schema it is listed with, MCP-003."""
    return {name: Command(tool.description, tool.input_schema) for name, tool in (await listed(client)).items()}


async def called(client, name, arguments):
    """Run a command as an agent does: the tool named for it, with its arguments."""
    return await client.call_tool(name, arguments)


@pytest.fixture
def mapped(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                            provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE', name='audible alarm')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
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
def test_the_server_lists_each_surfaced_verb_as_a_tool(run, home, mapped):
    async def check(client, init):
        return await tool_names(client)
    tools = session(home, mapped, check)
    assert 'mcp_serve' not in tools and 'map_approve' not in tools
    schema = tools['map_joins'].input_schema
    element, raw = schema['properties']['element'], schema['properties']['raw']
    assert element['type'] == 'string' and schema['required'] == ['element']
    assert schema['properties']['project']['type'] == 'string' and schema['additionalProperties'] is False
    assert raw['type'] == 'boolean'
    assert element['description']
    assert raw['description'] and raw['description'] in run('help', 'map', 'joins', cwd=mapped).stdout
    names = tools['memory_open_nodes'].input_schema['properties']['names']
    assert (names['type'], names['items']) == ('array', {'type': 'string'}) and names['description']
    assert 'add-item' in tools['map_knowledge'].input_schema['properties']['op']['description']
    for name in ('metaform_feedback', 'metaform_list_reports', 'metaform_read_report', 'metaform_set'):
        undescribed = [key for key, value in tools[name].input_schema['properties'].items() if not value.get('description')]
        assert undescribed == [], (name, undescribed)


@pytest.mark.req('MCP-003')
@pytest.mark.req('BASE-036')
@pytest.mark.req('STORE-023')
@pytest.mark.req('LAYER-016')
def test_a_tool_returns_what_the_cli_returns(run, home, mapped):
    cli = json.loads(run('map', 'joins', 'code.timer.kitchen', '--json', cwd=mapped).stdout)

    async def call(client, init):
        return text(await called(client, 'map_joins', {'element': 'code.timer.kitchen'}))
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
        result = await called(client, 'added_twice', {'n': 21})
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
        return set(tools) | set(await listed(client)), refused.is_error, text(refused)
    names, error, message = session(home, mapped, narrowed)
    assert 'map' not in names and 'map_knowledge' not in names and 'memory_open_nodes' in names
    assert error and message[0].splitlines() == ['Error: No tool map_knowledge on this surface.', 'Next: list the tools']
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
        off = text(await called(client, 'tmuxed_show', {'tmux': False}))
        stored = text(await called(client, 'tmuxed_show', {}))
        return tools['tmuxed_show'].input_schema['properties']['tmux'], off, stored
    schema, off, stored = session(home, mapped, call)
    assert schema == {'type': 'boolean', 'description': 'Use tmux.'}
    assert json.loads(off[-1]) == {'tmux': False} and json.loads(stored[-1]) == {'tmux': True}
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert (shown['tmux']['value'], shown['tmux']['state']) == (True, 'glued')


@pytest.mark.req('MCP-006')
@pytest.mark.req('BASE-013')
def test_tool_errors_end_with_the_one_next_step_the_cli_gives(run, home, mapped):
    run('enable', 'hello')
    run('hello', 'greet', 'ada', cwd=mapped)
    cli = run('map', 'element', 'code.nothing', cwd=mapped, ok=False).stderr.splitlines()

    async def call(client, init):
        missing = await called(client, 'map_element', {'element': 'code.nothing'})
        caution = await called(client, 'hello_forget', {})
        return missing.is_error, text(missing), caution.is_error, text(caution)
    error, missing, caution_error, caution = session(home, mapped, call)
    # The CLI's next step, read over MCP as the tool call it stands for, MCP-038.
    assert error and missing[0].splitlines() == [mcp_next(line, mapped) for line in cli]
    assert missing[0].splitlines()[-1].startswith('Next: call map_where')
    assert caution_error and caution[0].splitlines() == [
        'Error: This deletes the greeting history.', 'Next: If you are sure: call hello_forget with confirm true']
    assert run('hello', 'history', cwd=mapped).stdout.split() == ['ada']


@pytest.mark.req('MCP-025')
@pytest.mark.req('BASE-028')
def test_every_tool_takes_a_project_and_concurrent_calls_stay_apart(run, home, mapped, tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))

    async def call(client, init):
        create = [called(client, 'map_knowledge', {'op': 'create', 'layer': 'notes', 'variable': 'Notes.',
                                                     'mutable': True, 'hideable': True, 'module': 'test',
                                                     'project': project}) for project in ('proj', 'other')]
        await asyncio.gather(*create)
        added = [called(client, 'map_knowledge', {'op': 'add-element', 'layer': 'notes', 'address': f'code.{project}',
                                                    'project': project}) for project in ('proj', 'other')]
        results = await asyncio.gather(*added)
        ghost = await called(client, 'map_layers', {'project': 'ghost'})
        return [result.is_error for result in results], ghost.is_error, text(ghost)
    errors, ghost_error, ghost = session(home, mapped, call)
    assert errors == [False, False]
    assert Store('proj').element('code.proj', raw=True) is not None
    assert Store('proj').element('code.other', raw=True) is None
    assert Store('other').element('code.other', raw=True) is not None
    assert ghost_error and ghost[0].splitlines()[-1] == 'Next: metaform list projects'


@pytest.mark.req('PROJ-005')
def test_a_server_started_outside_every_project_selects_one_with_set(run, home, mapped, tmp_path):
    outside = tmp_path / 'desktop'
    outside.mkdir()

    async def call(client, init):
        before = await called(client, 'map_layers', {})
        chosen = await called(client, 'metaform_set', {'project': 'proj'})
        after = await called(client, 'map_layers', {})
        return init.instructions, before.is_error, text(before), chosen.is_error, after.is_error, text(after)
    instructions, before_error, before, chosen_error, after_error, after = session(home, outside, call)
    # At connect only the short pointer to the bootstrap; the folder's state comes in tool results
    assert 'metaform://metaform' in instructions and len(startup_instructions(outside)) <= 2048
    assert before_error and before[0].splitlines()[-1] == ('Next: call metaform_register for this folder, or '
                                                           'metaform set --project <id> for a registered one')
    assert not chosen_error and not after_error
    assert [layer['name'] for layer in json.loads(after[-1])['results']] == ['intake-1']


@pytest.mark.req('BASE-009')
@pytest.mark.req('BASE-036')
def test_an_async_verb_and_a_string_result_over_mcp(run, home, mapped):
    run('enable', 'hello')

    async def call(client, init):
        return text(await called(client, 'hello_wait', {'seconds': 0}))
    assert session(home, mapped, call) == ['waited 0 s\n']


@pytest.mark.req('MCP-003')
@pytest.mark.req('LAYER-017')
def test_map_where_over_mcp_shows_what_relies_on_an_address_and_what_it_relies_on(run, home, mapped):
    run('map', 'work', 'op=add', 'node=code.timer.kitchen', 'task=wire it', 'title=Wire it', cwd=mapped)
    cli = json.loads(run('map', 'where', 'code.timer.kitchen', '--json', cwd=mapped).stdout)

    async def call(client, init):
        small = text(await called(client, 'map_where', {'address': 'code.timer.kitchen'}))
        full = text(await called(client, 'map_where', {'address': 'code.timer.kitchen', 'full': True}))
        return json.loads(small[-1]), json.loads(full[-1])
    small, full = session(home, mapped, call)
    assert set(small) == {'kind', 'element', 'receives', 'around'}
    assert {key: value for key, value in small.items() if key != 'around'} == {
        key: value for key, value in cli.items() if key != 'around'}
    assert small['receives'] == [{'providers': ['code.alarm.audible'], 'purpose': 'Get attention.'}]
    # The calls in the counts are named as each surface calls them, MCP-038 and MCP-039.
    assert 'map_work node=code.timer.kitchen' in small['around'] and 'metaform map' not in small['around']
    assert 'metaform map work node=code.timer.kitchen' in cli['around']
    assert 'join_id' not in small['receives'][0] and full['receives'][0]['id'] and full['receives'][0]['ef']


@pytest.mark.req('STORE-028')
@pytest.mark.req('LAYER-007')
def test_a_masked_layer_is_absent_from_the_tool_read_too(run, home, mapped):
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=mapped)
    run('map', 'knowledge', 'op=add-item', 'layer=notes', 'node=element:code.timer.kitchen', 'value="n"', cwd=mapped)
    run('map', 'knowledge', 'op=finish', 'layer=notes', cwd=mapped)
    run('map', 'mask', 'code.timer', 'notes', cwd=mapped)

    async def call(client, init):
        return text(await called(client, 'map_node', {'node': 'element:code.timer.kitchen'}))
    view = json.loads(session(home, mapped, call)[-1])
    assert 'notes' not in [group['layer'] for group in view['layers']]


@pytest.mark.req('BASE-006')
@pytest.mark.req('BASE-035')
@pytest.mark.req('BASE-016')
@pytest.mark.req('BASE-009')
def test_a_declared_verb_is_a_tool_with_its_summary_unless_it_is_cli_only_or_elsewhere(run, home, mapped,
                                                                                        user_module):
    user_module('declared', '''
        import asyncio
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows', 'plan9')
        async def later(ctx):
            await asyncio.sleep(0)
            return {'done': True}
        MODULE = Module(id='declared', summary='x', purpose='Declares. Details: metaform help declared.',
                        verbs=(Verb('later', later, 'Finish later.'),
                               Verb('local', later, 'Only here.', surfaces=('cli',)),
                               Verb('far', later, 'Only on plan9.', supported_os=('plan9',))))
    ''')
    cli = json.loads(run('declared', 'later', '--json', cwd=mapped).stdout)

    async def call(client, init):
        tools = await tool_names(client)
        return tools, text(await called(client, 'declared_later', {}))
    tools, result = session(home, mapped, call)
    assert tools['declared_later'].description == 'Finish later.'
    assert 'declared_local' not in tools and 'declared_far' not in tools
    assert json.loads(result[-1]) == cli == {'done': True}


@pytest.mark.req('CLI-027')
@pytest.mark.req('PROJ-005')
def test_a_value_set_through_the_set_tool_reads_back_as_the_cli_writes_it(run, home, mapped, tmp_path):
    other = mapped / 'cli-folder'
    other.mkdir()
    run('set', '--modules', 'map,mcp', '--layers', 'intake-1', cwd=other)

    async def call(client, init):
        return (await called(client, 'metaform_set', {'modules': ['map', 'mcp'], 'layers': ['intake-1']})).is_error
    assert session(home, mapped, call) is False

    def values(folder):
        rows = json.loads(run('config', '--show', '--json', cwd=folder).stdout)
        return {row['key']: (row['value'], row['state']) for row in rows if row['key'] in ('modules', 'layers')}
    assert values(mapped) == values(other)


@pytest.mark.req('MCP-004')
@pytest.mark.req('CLI-022')
@pytest.mark.req('BASE-045')
def test_the_server_starts_on_any_surface_and_keeps_the_chassis_tools(run, home, mapped, user_module):
    user_module('solo', f'''
        from metaform.module import Module, Verb
        {OS}
        MODULE = Module(id='solo', summary='x', purpose='Solo. Details: metaform help solo.',
                        verbs=(Verb('hi', lambda ctx: 'hi', 'Say hi.'),))
    ''')
    run('set', '--modules', 'solo', cwd=mapped)

    async def narrowed(client, init):
        names = set(await tool_names(client))
        said = await called(client, 'metaform_feedback', {'text': 'Narrowed to solo.'})
        listed = await called(client, 'metaform_list_reports', {})
        name = json.loads(text(said)[-1])['files'][0]
        read = await called(client, 'metaform_read_report', {'name': name})
        refused = await called(client, 'map_where', {'address': 'code'})
        return names, said.is_error, json.loads(text(listed)[-1]), text(read), refused.is_error
    names, said_error, listed, read, refused = session(home, mapped, narrowed)
    assert names == {'solo_hi'} | REGISTERED_TOOLS
    assert not said_error and read == ['Narrowed to solo.'] and refused
    assert [row['kind'] for row in listed['results']] == ['feedback']


@pytest.mark.req('MCP-005')
@pytest.mark.req('MCP-006')
@pytest.mark.req('BASE-035')
@pytest.mark.req('CLI-027')
def test_tool_arguments_are_checked_by_kind_with_the_clis_next_step(run, home, mapped):
    run('enable', 'hello')
    missing_cli = run('hello', 'greet', cwd=mapped, ok=False).stderr.splitlines()[-1]

    async def call(client, init):
        missing = await called(client, 'hello_greet', {})
        as_text = await called(client, 'hello_greet', {'name': 'x', 'loud': 'no'})
        not_number = await called(client, 'hello_wait', {'seconds': 'abc'})
        bad_set = await called(client, 'metaform_set', {'loud': 'no'})
        return [(result.is_error, text(result)) for result in (missing, as_text, not_number, bad_set)]
    results = session(home, mapped, call)
    assert all(error for error, _ in results)
    assert all(len([line for line in blocks[0].splitlines() if line.startswith('Next: ')]) == 1
               for _, blocks in results)
    assert missing_cli == 'Next: metaform hello greet --help'  # the CLI's next step, read over MCP as its resource
    assert results[0][1][0].splitlines()[-1] == 'Next: call hello_greet with the arguments its input schema lists'
    assert run('hello', 'history', cwd=mapped).stdout.startswith('No greetings')
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert shown['loud']['state'] == 'default'


@pytest.mark.req('CLI-027')
@pytest.mark.req('BASE-044')
@pytest.mark.req('MCP-005')
def test_a_text_switch_sent_another_json_value_is_kept_as_its_json_text_with_a_notice(run, home, mapped):
    """A switch is read by its kind as a noun is, BASE-035: text takes what was sent as its JSON text and says so;
    a whole number and true or false cannot be read from another kind and stop the call as the command line does."""
    from metaform import grammar
    from metaform.module import Noun, Verb
    run('enable', 'hello')

    async def call(client, init):
        stored = await called(client, 'metaform_set', {'greeting': 5})
        return stored.is_error, text(stored)
    error, blocks = session(home, mapped, call)
    assert not error
    result = json.loads(blocks[-1])
    assert [(change['key'], change['new']) for change in result['updated']] == [('greeting', '5')]
    assert result['notices'] == [{'where': 'greeting', 'message': 'greeting is text; what was sent was kept as its '
                                                                   'JSON text.'}]
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert (shown['greeting']['value'], shown['greeting']['state']) == ('5', 'set')
    verb = Verb('greet', lambda ctx: None, 'x', nouns=(Noun('name', 'x'),), switches=('modules', 'loud'))
    parsed = grammar.from_json('hello', verb, {'name': 'x', 'modules': ['map', 7]}, folder=mapped)
    assert parsed.switches['modules'] == ['map', '7']
    assert parsed.notices == [('modules', 'modules is text; what was sent was kept as its JSON text.')]
    with pytest.raises(Exception) as stopped:
        grammar.from_json('hello', verb, {'name': 'x', 'modules': 'map'}, folder=mapped)
    assert 'modules is a list' in str(stopped.value)


@pytest.mark.req('MCP-005')
@pytest.mark.req('BASE-044')
@pytest.mark.req('BASE-045')
def test_a_chassis_tool_reads_a_text_argument_sent_another_json_value_as_its_json_text(run, home, mapped):
    """Every tool on the MCP surface reads a call one way, MCP-005: the chassis's own tools, like a module's verbs,
    keep a text argument sent another JSON type as its JSON text and say so; a list stays a list."""
    async def call(client, init):
        said = await called(client, 'metaform_feedback', {'text': 12})
        listed = await called(client, 'metaform_list_reports', {'kind': ['feedback']})
        return (said.is_error, text(said)), (listed.is_error, text(listed))
    (said_error, said), (listed_error, listed) = session(home, mapped, call)
    assert not said_error and not listed_error
    assert said[0] == 'Notice: text: text is text; what was sent was kept as its JSON text.'
    name = json.loads(said[-1])['files'][0]
    assert run('read', 'report', name, cwd=mapped).stdout == '12'
    assert listed[0] == 'Notice: kind: kind is text; what was sent was kept as its JSON text.'
    assert json.loads(listed[-1])['results'] == []


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-002')
def test_an_intake_is_recorded_over_mcp_one_object_per_call_and_read_back_while_building(run, home, tmp_path):
    folder = tmp_path / 'fresh'
    folder.mkdir()
    run('add', 'project', 'fresh', str(folder))

    async def call(client, init):
        before = set(await tool_names(client))
        started = await called(client, 'intake_start', {'model': 'claude', 'role': 'intake agent'})
        names = set(await tool_names(client))  # the tools that record an intake, listed once one is being recorded
        assert 'intake_element' not in before and 'intake_start' in before
        described = await called(client, 'intake_element', {'namespace_address': 'code.timer.kitchen', 'role': 'DE',
                                                              'name': 'kitchen timer', 'name_length': 2,
                                                              'refs': [{'key': 'path', 'value': 'src/main.c'}]})
        named = json.loads(text(described)[-1])['notices']
        await called(client, 'intake_element', {'namespace_address': 'code.loop.tick', 'role': 'SE'})
        made = await called(client, 'intake_purpose', {'receiver': 'code.timer.kitchen', 'elements': ['code.alarm.audible'],
                                                      'purpose': 'Get attention.', 'ef': 'rings', 'ifd': 'receives'})
        # Recorded again with an element it holds, the join takes the new elements: parts annealed into one join.
        annealed = await called(client, 'intake_purpose', {'receiver': 'code.timer.kitchen',
                                                          'elements': ['code.alarm.audible', 'code.loop.tick',
                                                                       'code.loop.beat']})
        shown = json.loads(text(await called(client, 'intake_show', {}))[-1])
        one = json.loads(text(await called(client, 'intake_show', {'receiver': 'code.timer.kitchen'}))[-1])
        finished = json.loads(text(await called(client, 'intake_finish', {'report': 'Fine.'}))[-1])
        return (names, started.is_error, shown, finished, named, described.is_error,
                (annealed.is_error, json.loads(text(made)[-1])), one)
    names, error, shown, finished, named, described_error, joined, one = session(home, folder, call)
    assert joined[0] is False and set(joined[1]) == {'receiver', 'elements', 'layer', 'notices'}
    assert [row['elements'] for row in one['purposes']] == [['code.alarm.audible', 'code.loop.tick', 'code.loop.beat']]
    assert {'intake_start', 'intake_element', 'intake_purpose', 'intake_show', 'intake_remove', 'intake_finish'} <= names
    assert not names & {'intake_join', 'intake_add_purpose', 'intake_subtype', 'intake_absorb', 'intake_edit'}
    assert error is False and described_error is False
    assert named == []  # the element's name is its own field
    assert [(row['purpose'], row['ef'], row['ifd']) for row in shown['purposes']] == [('Get attention.', 'rings',
                                                                                     'receives')]
    assert [(row['namespace_address'], row['role']) for row in shown['elements']] == [
        ('code.alarm.audible', None), ('code.loop.beat', None), ('code.loop.tick', 'SE'), ('code.timer.kitchen', 'DE')]
    assert shown['undescribed'] == ['code.alarm.audible', 'code.loop.beat']
    assert (finished['elements'], finished['purposes']) == (4, 1)
    store = Store('fresh')
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.short_name, kitchen.name) == ('kitchen timer', 'kitchen timer')
    sources = store.layer_items('sources', Node('element', 'code.timer.kitchen'), limit=0).results
    assert [[(ref.key, ref.value) for ref in item.refs] for item in sources] == [[('path', 'src/main.c')]]


@pytest.mark.req('VIEW-018')
@pytest.mark.req('MCP-002')
def test_a_tool_call_that_changes_the_map_is_announced_and_a_read_is_not(run, home, mapped, tmp_path, user_module):
    log = tmp_path / 'heard.jsonl'
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=mapped)
    user_module('watcher', f'''
        import json
        from pathlib import Path
        from metaform.module import Module, Subscription
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def saw(payload, ctx):
            with Path({str(log)!r}).open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(payload) + '\\n')
        MODULE = Module(id='watcher', summary='x', purpose='Watches the map. Details: metaform help watcher.',
                        subscriptions=(Subscription('map.changed', saw),))
    ''')

    def lines():
        return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []

    async def call(client, init):
        await called(client, 'map_layers', {})
        read = lines()
        await called(client, 'map_knowledge', {'op': 'add-item', 'layer': 'notes', 'node': 'element:code.timer.kitchen',
                                               'value': 'The countdown drifts.'})
        written = lines()
        await called(client, 'map_layers', {})  # in the same server process: a read after a write
        return read, written, lines()
    read, written, after = session(home, mapped, call)
    active = Store('proj').active_base()
    assert read == []
    assert [{key: value for key, value in event.items() if key != 'seq'} for event in written] == [
        {'project': 'proj', 'base_id': active.id, 'tables': ['objects', 'op:item', 'ops']}]  # once, for the one write
    assert written[0]['seq'] > 0  # the sequence the base reached, which a page applies the ops up to, STORE-046
    assert after == written  # the notes were taken once: the read announces nothing, not the write again


@pytest.mark.req('VIEW-018')
@pytest.mark.req('BASE-037')
@pytest.mark.req('MCP-002')
def test_a_module_enabled_or_disabled_after_the_server_started_is_loaded_or_dropped_before_a_write_is_announced(
        run, home, mapped, tmp_path, user_module):
    """Ticket 8f039057: the watcher stands in for dispatch's subscriber. Off when the server announces its first
    write, enabled on the command line in the same session and it hears the next write, disabled again and it hears
    no more."""
    log = tmp_path / 'heard.jsonl'
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=mapped)
    user_module('watcher', f'''
        import json
        from pathlib import Path
        from metaform.module import Module, Subscription
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def saw(payload, ctx):
            with Path({str(log)!r}).open('a', encoding='utf-8') as handle:
                handle.write(json.dumps({{**payload, 'surface': ctx.surface}}) + '\\n')
        MODULE = Module(id='watcher', summary='x', purpose='Watches the map. Details: metaform help watcher.',
                        subscriptions=(Subscription('map.changed', saw),))
    ''')
    run('disable', 'watcher')

    def lines():
        return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []

    async def note(client, value):
        written = await called(client, 'map_knowledge', {'op': 'add-item', 'layer': 'notes',
                                                         'node': 'element:code.timer.kitchen', 'value': value})
        return written.is_error, lines()

    async def call(client, init):
        off = await note(client, 'Before the watcher is on.')
        await asyncio.to_thread(run, 'enable', 'watcher')
        on = await note(client, 'After the watcher is on.')
        await asyncio.to_thread(run, 'disable', 'watcher')
        return off, on, await note(client, 'After the watcher is off again.')
    off, on, dropped = session(home, mapped, call)
    active = Store('proj').active_base()
    assert (off[0], on[0], dropped[0]) == (False, False, False)  # each of the three notes was written
    assert off[1] == []
    assert [{key: value for key, value in event.items() if key != 'seq'} for event in on[1]] == [
        {'project': 'proj', 'base_id': active.id, 'surface': 'mcp', 'tables': ['objects', 'op:item', 'ops']}]  # heard
    assert dropped[1] == on[1]


HISTORY_TOOLS = {'metaform_add_origin', 'metaform_list_origins', 'metaform_add_variant', 'metaform_list_variants',
                 'metaform_extract'}


@pytest.mark.req('PROJ-024')
@pytest.mark.req('MCP-003')
@pytest.mark.req('MCP-004')
def test_the_history_commands_are_tools_while_the_chassis_is_on_the_surface(run, home, mapped, tmp_path):
    import shutil
    (mapped / 'notes.txt').write_text('first\n', encoding='utf-8')
    work = tmp_path / 'work'
    shutil.copytree(mapped, work)
    (work / 'notes.txt').write_text('second\n', encoding='utf-8')
    out = tmp_path / 'out'

    async def check(client, init):
        tools = await tool_names(client)
        origin = json.loads(text(await called(client, 'metaform_add_origin', {}))[-1])
        variant = json.loads(text(await called(client, 'metaform_add_variant', {'folder': str(work), 'workflow': 'mutate',
                                                                           'blinded': False}))[-1])
        listed = json.loads(text(await called(client, 'metaform_list_variants', {}))[-1])
        written = json.loads(text(await called(client, 'metaform_extract', {'variants': [variant['variant_id']],
                                                                     'folder': str(out)}))[-1])
        return tools, origin, variant, listed, written
    tools, origin, variant, listed, written = session(home, mapped, check)
    assert HISTORY_TOOLS <= set(tools)
    for name in HISTORY_TOOLS:
        assert all(value.get('description') for value in tools[name].input_schema['properties'].values()), name
    assert origin['added'] is True and origin['origin']['kind'] == 'folder'
    assert (variant['variant_id'], variant['workflow'], variant['blinded']) == ('v000001', 'mutate', False)
    assert [item['variant_id'] for item in listed] == ['v000001'] and written == [str(out)]
    assert (out / 'notes.txt').read_text(encoding='utf-8') == 'second\n'
    run('set', '--modules', 'map', cwd=mapped)

    async def narrowed(client, init):
        return set(await tool_names(client))
    assert not HISTORY_TOOLS & session(home, mapped, narrowed)


@pytest.mark.req('STORE-044')
@pytest.mark.req('MCP-003')
def test_the_prompt_reads_are_tools(run, home, mapped):
    from metaform.data import prompts
    prompts.add_prompt('practices', 'markdown', 'one\n')
    prompts.add_prompt_version('practices', 'two\n', 1)

    async def check(client, init):
        listed = json.loads(text(await called(client, 'metaform_prompts', {}))[-1])
        newest = json.loads(text(await called(client, 'metaform_prompt', {'name': 'practices'}))[-1])
        first = json.loads(text(await called(client, 'metaform_prompt', {'name': 'practices', 'number': 1}))[-1])
        return listed, newest, first
    listed, newest, first = session(home, mapped, check)
    assert [(item['name'], item['newest']) for item in listed] == [('practices', 2)]
    assert (newest['number'], newest['text'], first['text']) == (2, 'two\n', 'one\n')


@pytest.mark.req('STORE-044')
@pytest.mark.req('MCP-003')
@pytest.mark.req('BASE-044')
def test_save_prompt_creates_and_versions_exact_text_through_mcp(run, home, mapped):
    from metaform.data import prompts
    original = '  First prompt.\n\n'
    revised = 'Second prompt.\n'

    async def check(client, init):
        schema = (await tool_names(client))['metaform_save_prompt'].input_schema
        results = []
        for arguments in ({'name': 'personal', 'text': original, 'format': 'markdown'},
                          {'name': 'personal', 'text': revised},
                          {'name': 'personal', 'text': revised},
                          {'name': 'personal', 'text': 'A separate revision.', 'parent': 1},
                          {'name': 'plain', 'text': 'Plain prompt.'}):
            result = await called(client, 'metaform_save_prompt', arguments)
            assert not result.is_error, text(result)
            results.append(json.loads(text(result)[-1]))
        first = json.loads(text(await called(client, 'metaform_prompt', {'name': 'personal', 'number': 1}))[-1])
        return schema, results, first

    schema, (created, updated, repeated, branch, plain), first = session(home, mapped, check)
    assert schema['required'] == ['name', 'text'] and schema['additionalProperties'] is False
    assert schema['properties']['format']['enum'] == ['xml', 'markdown', 'text']
    assert schema['properties']['parent']['minimum'] == 1
    assert (created['number'], created['parent_id'], created['text']) == (1, None, original)
    assert (updated['number'], updated['parent_id'], updated['text']) == (2, created['version_id'], revised)
    assert updated['format'] == 'markdown'
    assert repeated['version_id'] == updated['version_id']
    assert repeated['notices'] and 'no version was added' in repeated['notices'][0]['message']
    assert (branch['number'], branch['parent_id']) == (3, created['version_id'])
    assert (plain['number'], plain['format']) == (1, 'text')
    assert first == created
    assert [version.number for version in prompts.prompt_versions('personal')] == [3, 2, 1]


@pytest.mark.req('STORE-044')
@pytest.mark.req('MCP-005')
@pytest.mark.req('MCP-006')
def test_save_prompt_rejects_invalid_arguments_without_adding_versions(run, home, mapped):
    from metaform.data import prompts
    initial = prompts.add_prompt('personal', 'text', 'Original.')

    async def check(client, init):
        for arguments in ({'name': 'personal'},
                          {'name': 'personal', 'text': 'Changed.', 'format': 'html'},
                          {'name': 'personal', 'text': 'Changed.', 'parent': 99},
                          {'name': 'personal', 'text': 'Changed.', 'parent': 0},
                          {'name': 'personal', 'text': 'Changed.', 'parent': True},
                          {'name': 'personal', 'text': 'Changed.', 'parent': '1'},
                          {'name': 'new', 'text': 'Changed.', 'parent': 1}):
            result = await called(client, 'metaform_save_prompt', arguments)
            assert result.is_error, arguments
            assert text(result)[-1].startswith('Error: ') and '\nNext: ' in text(result)[-1]

    session(home, mapped, check)
    assert prompts.prompt_versions('personal') == (initial,)
    assert [prompt.name for prompt in prompts.prompts()] == ['personal']


def consenting(home, folder, fn, answers=('accept',), env=None):
    """A real MCP client on the 2025 handshake that shows forms: each form the server asks is answered with the next
    of `answers`, as the person answers it in their AI tool."""
    from mcp import types
    given = iter(answers)

    async def elicit(context, params):
        action = next(given)
        return types.ElicitResult(action=action, content={'go': True} if action == 'accept' else None)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home), **(env or {})})

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write,
                                                                        elicitation_callback=elicit) as client:
            await client.initialize()
            return await fn(client)
    return asyncio.run(go())


@pytest.mark.req('PROJ-025')
@pytest.mark.req('MCP-006')
@pytest.mark.req('CLI-011')
def test_clear_project_is_a_caution_tool_while_the_chassis_is_on_the_surface(run, home, mapped):
    """metaform_clear_project is declared as every other tool: its description says what it removes, that a backup is
    made first and that restore brings it back, and it is destructive. It is the person's decision: an agent's
    confirm never clears, its refusal names what goes, the backup and the command the person runs; only the person's
    yes to the form clears it, and the result names the backup in the restore command, UX review round 1."""
    run('feedback', 'A note.', cwd=mapped)
    run('map', 'work', 'op=add', 'address=code.timer.kitchen', 'task=Ring louder', 'title=Ring louder', cwd=mapped)

    async def check(client, init):
        tools = await listed(client)
        refused = await called(client, 'metaform_clear_project', {})
        still = await called(client, 'map_where', {'address': 'code.timer.kitchen'})
        confirmed = await called(client, 'metaform_clear_project', {'confirm': True})
        return tools, refused, still, confirmed
    tools, refused, still, confirmed = session(home, mapped, check)
    declared = tools['metaform_clear_project']
    assert declared.input_schema['properties'].keys() == {'project'}  # no confirm an agent could give
    assert declared.annotations.destructive_hint is True
    guided = refused.content[0].text  # the rest of its description comes with its first use, MCP-039
    assert 'backup is made first' in guided and 'metaform restore project' in guided
    assert refused.is_error is True
    said = '\n'.join(text(refused))
    assert 'Clearing proj removes' in said and 'main holds one open ticket' in said
    assert 'A backup is made first' in said and "This is the person's decision" in said
    assert 'Next: ask the person in chat; to do it they use Clear project on the page, or paste into their own ' \
        'terminal window' in said and said.endswith(': metaform clear project proj --confirm')
    assert 'with confirm true' not in said
    assert still.is_error is False  # the caution alone changed nothing
    assert confirmed.is_error is True and "the person's decision" in '\n'.join(text(confirmed))
    assert run('list', 'bases', cwd=mapped).stdout.split()[:1] == ['main']  # an agent's confirm cleared nothing

    async def clear(client):
        return await called(client, 'metaform_clear_project', {})
    cleared = consenting(home, mapped, clear)
    assert cleared.is_error is False
    told = json.loads(text(cleared)[-1])
    backup = told.pop('backup')
    assert backup and told.pop('restore') == f'metaform restore project proj {backup}'  # PROJ-030, by its name
    assert told == {'project': 'proj', 'bases': ['main'], 'reports': 1}
    assert run('list', 'bases', cwd=mapped).stdout == ''
    assert not (own('proj') / 'reports').exists()

    # person-consent F2: the undo is on the same surface, the person's too; an agent alone is told what it brings back
    async def restore(client):
        return await called(client, 'metaform_restore_project', {'backup': backup})
    asked = session(home, mapped, lambda client, init: restore(client))  # no form to show: the agent is refused
    assert asked.is_error is True and f'Restoring proj from backup {backup} brings back one base' in text(asked)[-1]
    assert run('list', 'bases', cwd=mapped).stdout == ''
    restored = consenting(home, mapped, restore)
    assert restored.is_error is False, text(restored)
    assert json.loads(text(restored)[-1])['backup'] == backup
    assert run('list', 'bases', cwd=mapped).stdout.split()[:1] == ['main']


@pytest.mark.req('CLI-011')
@pytest.mark.req('MCP-006')
@pytest.mark.parametrize('tool, arguments', [('metaform_clear_project', {'confirm': True}),
                                             ('map_add-base', {'name': 'fresh', 'confirm': True}),
                                             ('memory_delete_entities', {'entityNames': ['kept'], 'confirm': True})])
def test_a_dispatched_agent_gets_the_persons_decision_never_its_own_confirm(run, home, mapped, tool, arguments):
    """UX review round 1, fresh-start-intake F1, settings F5, web F1: a dispatched agent, the system agent among them,
    whose client shows forms, cannot clear the project, switch the map or delete memories with its own confirm; it is
    told the decision is the person's and given the command the person runs, never a call for itself, and the tools
    are marked destructive."""
    run('enable', 'memory', cwd=mapped)
    run('memory', 'create_entities',
        'entities=[{"name": "kept", "entityType": "note", "observations": ["It rings."], "why": "A test."}]',
        'node=element:code.timer.kitchen', cwd=mapped)

    async def check(client):
        return await listed(client), await called(client, tool, arguments)
    tools, refused = consenting(home, mapped, check, answers=(), env={'METAFORM_ROLE': 'system', 'METAFORM_WORK': 'x'})
    said = '\n'.join(text(refused))
    assert refused.is_error is True, said
    assert "This is the person's decision, not an agent's" in said and '\nNext: ask the person in chat; ' in said
    assert 'paste into their own terminal window' in said and ': metaform ' in said
    assert 'with confirm true' not in said and 'call ' not in said.split('\nNext: ')[1]
    assert tools[tool].annotations.destructive_hint is True
    assert Store('proj').active_base().name == 'main' and len(Store('proj').bases().results) == 1
    assert 'It rings.' in run('memory', 'open_nodes', 'names=["kept"]', cwd=mapped).stdout


@pytest.mark.req('CLI-011')
@pytest.mark.req('MCP-006')
def test_a_dispatched_system_agents_switch_runs_once_on_the_persons_allow_in_its_chat(run, home, mapped, tmp_path):
    """UX review round 2, person-consent F5: the person's own system agent, dispatched, asks for a switch of the map
    and its call waits on a consent card in its chat; the person's Allow runs it once, their Decline runs nothing, and
    the map changes exactly once. Every agent the runner could start is the fake agent."""
    import threading

    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually, read
    made = Dispatch(run, home, mapped, tmp_path)
    try:
        made.start('hold', 'system=true')
        runner = eventually(lambda: next((row['runner'] for row in read(run, made)['sessions']
                                          if row.get('state') == 'running' and row.get('runner')), None))
        cards: list[dict] = []

        def person():  # on the page: Allow the first card, Decline the second
            for choice in ('accept', 'decline'):
                card = eventually(lambda: next((one['data'] for one in read(run, made)['lines']
                                                if one['kind'] == 'elicitation' and one['data'].get('consent')
                                                and one['data']['state'] == 'waiting'), None), limit=60)
                run('dispatch', 'permit', made.id, card['request'], '--', choice, cwd=mapped, isolated=True)
                cards.append(card)
        answering = threading.Thread(target=person)
        answering.start()

        async def check(client):
            return (await called(client, 'map_add-base', {'name': 'fresh'}),
                    await called(client, 'map_add-base', {'name': 'other'}))
        allowed, declined = consenting(home, mapped, check, answers=(), env={
            'METAFORM_ROLE': 'system', 'METAFORM_WORK': made.id, 'METAFORM_SESSION': runner})
        answering.join(timeout=60)
        assert allowed.is_error is False, text(allowed)
        assert declined.is_error is True, text(declined)
        assert [card['consent']['command'] for card in cards] == ['metaform map add-base name=fresh --confirm',
                                                                  'metaform map add-base name=other --confirm']
        assert [one.name for one in Store('proj').bases().results] == ['main', 'fresh']
    finally:
        made.stop()
        made.close()


@pytest.mark.req('MCP-006')
def test_switching_the_active_base_asks_for_confirm(run, home, mapped):
    """map activate, add-base and collapse change the active map for every agent and the page of a project, and any
    project is named with `project`, so each is a caution tool: without confirm the call stops with its caution."""
    async def check(client, init):
        return await client.call_tool('map_activate', {'name': 'x'}), await listed(client)
    refused, tools = session(home, mapped, check)
    said = '\n'.join(text(refused))
    assert refused.is_error and 'confirm' in said and 'active map for every agent' in said
    assert all('Caution:' in tools[name].description for name in ('map_activate', 'map_add-base', 'map_collapse'))
    assert Store('proj').active_base().name == 'main'  # the caution alone changed nothing
    run('set', '--modules', 'map', cwd=mapped)

    async def narrowed(client, init):
        return set(await tool_names(client))
    assert 'clear_project' not in session(home, mapped, narrowed)


@pytest.mark.req('PROJ-025')
@pytest.mark.req('MCP-006')
def test_clear_project_returns_what_it_could_not_remove_with_what_to_do_and_no_error(run, home, mapped, unremovable):
    run('feedback', 'A note.', cwd=mapped)
    (stuck,) = (own('proj') / 'reports').iterdir()

    async def check(client):
        return await called(client, 'metaform_clear_project', {})
    with unremovable(stuck):
        cleared = consenting(home, mapped, check)  # the person's yes, UX review round 1
        assert stuck.is_file()
    assert cleared.is_error is False
    result = json.loads(text(cleared)[-1])
    assert (result['project'], result['bases'], result['reports']) == ('proj', ['main'], 1)
    assert [entry['path'] for entry in result['not_removed']] == [str(stuck)] and result['not_removed'][0]['reason']
    assert [notice['where'] for notice in result['notices']] == ['not_removed']
    assert 'ask the person to clear proj again' in result['notices'][0]['message']
    assert run('list', 'bases', cwd=mapped).stdout == ''


@pytest.mark.req('BASE-035')
@pytest.mark.req('BASE-044')
@pytest.mark.req('MCP-005')
def test_a_text_noun_sent_another_json_value_reaches_the_tool_as_its_json_text_with_a_notice(run, home, mapped):
    run('enable', 'hello')

    async def call(client, init):
        greeted = await called(client, 'hello_greet', {'name': {'a': 1}})
        joined = await called(client, 'map_knowledge', {
            'op': 'add-join', 'layer': 'notes', 'receiver': 'code.timer.kitchen', 'elements': ['code.alarm.audible'],
            'purpose': 12, 'ef': ['r']})
        observed = await called(client, 'memory_create_entities', {
            'node': 'element:code.timer.kitchen',
            'entities': [{'name': 'kitchen', 'entityType': 'part', 'observations': ['fine', 7],
                          'why': 'The kitchen is where the timer is used.'}]})
        return [(result.is_error, text(result)) for result in (greeted, joined, observed)]
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=mapped)
    (greet_error, greeted), (join_error, joined), (observe_error, observed) = session(home, mapped, call)
    assert not greet_error and not join_error and not observe_error
    assert greeted == ['Notice: name: name is text; what was sent was kept as its JSON text.\nhello, {"a": 1}\n']
    assert joined[0].splitlines() == ['Notice: purpose: purpose is text; what was sent was kept as its JSON text.',
                                      'Notice: ef: ef is text; what was sent was kept as its JSON text.']
    join = json.loads(joined[1])
    assert (join['purpose'], join['ef'], join['notices']) == ('12', '["r"]', [])
    # a memory write answers one line over MCP, its notices each on a line after it
    assert observed[-1].splitlines()[1:] == [
        'observations: observations is text; what was sent was kept as its JSON text.']
    graph = json.loads(run('memory', 'read_graph', '--json', cwd=mapped).stdout)
    assert graph['entities'][0]['observations'] == ['fine', '7']


@pytest.mark.req('CLI-037')
@pytest.mark.req('MCP-003')
def test_each_command_is_its_own_tool_described_once_with_typed_arguments_and_annotations(run, home, mapped):
    """Every command an agent can run is one tool, named `<module>_<command>` or `metaform_<command>`, described by its
    summary where it is listed, with its arguments typed and described in its input schema and what it does in its
    annotations, so an agent plans a call from the list alone; the list is sorted and the same on every connection."""
    async def check(client, init):
        tools = await listed(client)
        unknown = await client.call_tool('map_nothing', {})
        ran = await client.call_tool('map_joins', {'element': 'code.timer.kitchen'})
        return tools, unknown, ran
    tools, unknown, ran = session(home, mapped, check)
    again = session(home, mapped, lambda client, init: listed(client))
    from metaform import loader
    from metaform.module import on_this_system
    wanted = {f'{module.id}_{verb.name}' for module in loader.enabled() for verb in module.verbs
              if 'mcp' in verb.surfaces and on_this_system(verb) and (verb.listed is None or verb.listed(mapped))}
    assert set(tools) == wanted | REGISTERED_TOOLS | HISTORY_TOOLS | {
        'metaform_prompts', 'metaform_prompt', 'metaform_save_prompt', 'metaform_clear_project',
        'metaform_restore_project'}
    assert 'mcp_serve' not in tools and 'map' not in tools                   # no tool for a module, no wrapper
    assert list(tools) == sorted(tools) and list(again) == list(tools)
    assert [tool.model_dump() for tool in again.values()] == [tool.model_dump() for tool in tools.values()]
    page = run('help', 'map', 'joins', cwd=mapped).stdout
    joins = tools['map_joins']
    assert joins.description == page.splitlines()[0].split(': ', 1)[1]          # the verb's summary, once
    assert joins.input_schema['required'] == ['element'] and joins.input_schema['additionalProperties'] is False
    assert joins.input_schema['properties']['raw']['description'] in page
    for name, tool in tools.items():
        assert tool.description and 'command' not in tool.input_schema['properties'], name
        assert all(value.get('description') for value in tool.input_schema['properties'].values()), name
        hints = tool.annotations
        assert None not in (hints.read_only_hint, hints.destructive_hint, hints.idempotent_hint, hints.open_world_hint), name
    assert tools['map_where'].annotations.read_only_hint and not tools['map_where'].annotations.open_world_hint
    assert not tools['map_work'].annotations.read_only_hint and not tools['map_work'].annotations.destructive_hint
    assert tools['memory_delete_entities'].annotations.destructive_hint
    assert tools['metaform_clear_project'].annotations.destructive_hint
    assert 'Caution:' in tools['map_hide'].description
    assert unknown.is_error and text(unknown)[0].splitlines() == [
        'Error: No tool map_nothing on this surface.', 'Next: list the tools']
    assert json.loads(text(ran)[-1]) == json.loads(run('map', 'joins', 'code.timer.kitchen', '--json', cwd=mapped).stdout)
    assert ran.structured_content == json.loads(text(ran)[-1])                  # an object result is also data


LOOPBACK = ('127.0.0.1', 'localhost', '::1')
# web's calls to its own page server, at the address its run record holds: Metaform's own process, not the open world
OWN_SERVER = ('answering', 'held_open', 'ask_page')
# home functions that open a write transaction for bookkeeping: the first base made on first use, the chassis meta
HOME_BOOKKEEPING = ('ensure_base', 'set_meta')
# functions whose module-table writes are bookkeeping: memory carries the old memory layer into its graph once
TABLE_BOOKKEEPING = ('_carry',)
# files written as bookkeeping: a store made 0600 before SQLite opens it, a module's resources copied, the page token
FILE_BOOKKEEPING = ('metaform.sqlite.private', 'metaform.loader._copy_resources', 'metaform_module_system_web.token')
# read verbs that write only on a surface the MCP server is not: the note is written from the web page alone
WEB_ONLY_WRITES = {'memory_note': 'writes only from the web page; a call from any other surface with text is refused'}
# These reads save only the screenshot the caller requests, rather than changing the map or the viewed page.
SCREENSHOT_ONLY_WRITES = {
    'web_look': 'reads the page through Playwright and saves only an explicitly requested screenshot',
    'web_capture': 'reads a frame of the page and saves the requested screenshot',
}


class Reach:
    """What a verb reaches, read from the source of each function it can call: names through the function's globals,
    closure and the imports inside it; `ctx.`, `store.` and `self.` methods through their classes; a published topic
    through its subscribers; a `metaform <module> <verb>` process it starts through that verb. A sink is `network`, a
    connection that is not to this machine; `write`, a Store method that writes the map, or a change to the settings;
    `send`, project text sent to a third party through `metaform.jev`, which spends the person's credit. Bookkeeping
    is no write: a module's tables made or upgraded on first use, a cache, what a session was shown. Three more kinds
    say a verb does something without making it a write of the map: `local`, a request to Metaform's own process on
    this machine; `process`, a process started; `file`, a file written outside the stores. Calls on any other object,
    a module's table rows among them, are not followed, so a reach found is certain and one missed is possible."""

    def __init__(self, modules):
        import http.client
        import shutil
        import socket
        import urllib.request

        from metaform import home, jev
        from metaform.module import Context
        self.modules = modules
        self.subscribers = {}
        for module in modules:
            for subscription in module.subscriptions:
                self.subscribers.setdefault(subscription.topic, []).append(subscription.handler)
        self.typed = {'ctx': Context, 'store': Store}
        self.network = {urllib.request.urlopen, http.client.HTTPConnection, http.client.HTTPSConnection,
                        socket.create_connection}
        self.writes = {*(method for name, method in vars(Store).items()
                         if inspect.isfunction(method) and not name.startswith('_')
                         and 'self._write()' in inspect.getsource(method)),
                       *(function for name, function in vars(home).items()
                         if inspect.isfunction(function) and function.__module__ == home.__name__
                         and not name.startswith('_') and name not in HOME_BOOKKEEPING
                         and 'write=True)' in inspect.getsource(function))}
        # a module's data operations, which Store runs by name: a write operation is a write of the map
        self.operations = {name: declared for module in modules if module.data is not None
                           for name, declared in module.data.operations.items()}
        self.writes |= {declared.run for declared in self.operations.values() if declared.write}
        # an edit of a prompt in the home's prompt store changes what agents are sent; `shipped`, the version of what a
        # module serves, is bookkeeping of what was served, as a table made on first use is
        from metaform.data import prompts
        self.writes |= {prompts.add_prompt, prompts.add_prompt_version, prompts.save_prompt}
        self.send = jev.post
        self.processes = {subprocess.run, subprocess.call, subprocess.check_call, subprocess.check_output}
        self.files = {os.replace, os.rename, os.remove, os.unlink, shutil.copy, shutil.copy2, shutil.copyfile,
                      shutil.copytree, shutil.move, shutil.rmtree}
        self.read = {}

    def verb(self, module_id, name):
        return next((verb.run for module in self.modules if module.id == module_id
                     for verb in module.verbs if verb.name == name), None)

    def sinks(self, start):
        """Each sink the function reaches, with the calls that lead to it."""
        found, seen, queue = {}, set(), [(start, [])]
        while queue:
            fn, path = queue.pop(0)
            if fn in seen:
                continue
            seen.add(fn)
            here = [*path, f'{fn.__module__}.{fn.__qualname__}']
            callees, sinks = self.parsed(fn)
            for kind, what in sinks:
                found.setdefault(kind, [*here, what])
            queue += [(callee, here) for callee in callees]
        return found

    def parsed(self, fn):
        if fn not in self.read:
            self.read[fn] = self._parse(fn)
        return self.read[fn]

    def _parse(self, fn):
        fn = inspect.unwrap(fn)
        fn = getattr(fn.func if isinstance(fn, functools.partial) else fn, '__func__', fn)
        try:
            tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            scope = {**fn.__globals__, **inspect.getclosurevars(fn).nonlocals, **self.imported(tree, fn)}
        except (OSError, TypeError, SyntaxError, ValueError, AttributeError):
            return [], []
        owner = scope.get(fn.__qualname__.split('.')[0]) if '.' in fn.__qualname__ else None
        local = {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)} | {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
        scope = {name: value for name, value in scope.items() if name not in local}
        assigned = {target.id: node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                    for target in node.targets if isinstance(target, ast.Name)}
        callees, sinks = [], []
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            targets = [self.resolved(call.func, scope, owner)]
            targets += [self.resolved(arg, scope, owner) for arg in [*call.args, *(k.value for k in call.keywords)]
                        if isinstance(arg, (ast.Name, ast.Attribute))]  # a function handed on, to a thread or a hook
            if isinstance(call.func, ast.Attribute) and call.func.attr in ('publish', 'publish_async') and call.args \
                    and isinstance(call.args[0], ast.Constant):
                callees += self.subscribers.get(call.args[0].value, [])
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'tables' \
                    and fn.__name__ not in TABLE_BOOKKEEPING and not any(
                    k.arg == 'write' and isinstance(k.value, ast.Constant) and k.value.value is False
                    for k in call.keywords):
                sinks.append(('write', f'{ast.unparse(call.func)}()'))  # a module's tables, written
            if f'{fn.__module__}.{fn.__qualname__}' not in FILE_BOOKKEEPING and self.writes_file(call, targets[0]):
                sinks.append(('file', ast.unparse(call.func)))
            for target in filter(None, targets):
                if target in self.network:
                    said = [ast.unparse(arg) for arg in call.args[:1]]
                    said += [ast.unparse(assigned[arg.id]) for arg in call.args[:1]
                             if isinstance(arg, ast.Name) and arg.id in assigned]
                    if fn.__name__ not in OWN_SERVER and not any(host in one for one in said for host in LOOPBACK):
                        sinks.append(('network', target.__qualname__))
                    else:
                        sinks.append(('local', target.__qualname__))
                elif target in self.processes:
                    sinks.append(('process', target.__qualname__))
                elif target in self.writes:
                    sinks.append(('write', target.__qualname__))
                elif target is self.send:
                    sinks += [('send', 'jev.post'), ('network', 'jev.post')]
                elif target is subprocess.Popen and call.args:
                    sinks.append(('process', 'Popen'))
                    command = assigned.get(call.args[0].id) if isinstance(call.args[0], ast.Name) else call.args[0]
                    words = [one.value for one in getattr(command, 'elts', []) if isinstance(one, ast.Constant)]
                    at = words.index('metaform') if 'metaform' in words else -1
                    run = self.verb(*words[at + 1:at + 3]) if 0 <= at < len(words) - 2 else None
                    callees += [run] if run else []
                elif inspect.isfunction(target) and target.__module__.startswith('metaform') and not any(
                        k.arg in ('create', 'write') and isinstance(k.value, ast.Constant) and k.value.value is False
                        for k in call.keywords):  # create=False and write=False are this code's reads
                    callees.append(target)
        return callees, sinks

    def writes_file(self, call, target):
        """Whether the call writes a file: a Path's write_text or write_bytes, open or os.open for writing, or a copy,
        move or removal through os and shutil."""
        if isinstance(call.func, ast.Attribute) and call.func.attr in ('write_text', 'write_bytes'):
            return True
        if isinstance(call.func, ast.Name) and call.func.id == 'open':
            mode = [*call.args[1:2], *(k.value for k in call.keywords if k.arg == 'mode')]
            return any(isinstance(one, ast.Constant) and set(str(one.value)) & set('wax+') for one in mode)
        if target is os.open:
            return any(flag in ast.unparse(call) for flag in ('O_WRONLY', 'O_RDWR', 'O_CREAT'))
        return target in self.files

    def resolved(self, node, scope, owner):
        """The function a call's target names, or None."""
        names = []
        while isinstance(node, ast.Attribute):
            names.insert(0, node.attr)
            node = node.value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'require_store':
            found = Store
        elif isinstance(node, ast.Call) and self.returns(self.resolved(node.func, scope, owner)) is Store:
            found = Store  # `_other_project(ctx).add_base(...)`, a call that gives a Store
        elif isinstance(node, ast.Name) and node.id == 'self' and isinstance(owner, type):
            found = owner
        elif isinstance(node, ast.Name):
            found = self.typed.get(node.id, scope.get(node.id))
        else:
            return None
        for name in names:
            operation = self.operations.get(name) if found is Store and not hasattr(Store, name) else None
            found = operation.run if operation else getattr(found, name, None)
        found = inspect.unwrap(found) if callable(found) else found
        found = getattr(found.func if isinstance(found, functools.partial) else found, '__func__', found)
        return found if inspect.isroutine(found) or isinstance(found, type) else None

    @staticmethod
    def returns(fn):
        """What the function's return annotation names, or None."""
        try:
            return typing.get_type_hints(fn).get('return') if inspect.isfunction(fn) else None
        except (NameError, TypeError):  # an annotation that names what the module does not import at run time
            return None

    @staticmethod
    def imported(tree, fn):
        """The names the function imports inside its body, as `from . import jev`."""
        package = fn.__module__ if hasattr(sys.modules.get(fn.__module__), '__path__') else fn.__module__.rpartition('.')[0]
        names = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            source = importlib.util.resolve_name('.' * node.level + (node.module or ''), package) if node.level \
                else node.module or ''
            try:
                held = importlib.import_module(source)
            except ImportError:
                continue
            for alias in node.names:
                one = getattr(held, alias.name, None)
                if one is None:
                    with contextlib.suppress(ImportError):
                        one = importlib.import_module(f'{source}.{alias.name}')
                names[alias.asname or alias.name] = one
        return names


@pytest.mark.req('MCP-003')
@pytest.mark.req('BASE-006')
def test_every_verb_that_reaches_the_network_or_writes_declares_it_in_its_annotation(home):
    """The annotations come from what each verb declares, so a declaration that hides a reach misleads every host,
    H17: a verb that reaches external services or agents declares open_world. Map, settings and file writes and
    third-party sends cannot be declared read without a reasoned exception. Every module is enabled and walked."""
    modules = every_module()
    wrong = undeclared(Reach(modules), modules)
    assert len(modules) > 10 and not wrong, '\n'.join(wrong)


# Write/remove verbs without write, send or file evidence, even when the walk sees network, local or process sinks.
# Keep the set exact so losing a declaration or a previously visible write cannot silently pass.
UNSEEN = {
    'cloud_logout': 'revokes at the broker through an httpx client and forgets the sign-in through the login module',
    'dispatch_permit': 'answers an agent permission or question through the local runner control socket',
    'dispatch_configure': 'changes a live agent setting through the local runner control socket',
    'dispatch_message': 'queues a new agent turn through the local runner control socket',
    'dispatch_fork': 'forks or prompts an agent session through the local runner control socket',
    'dispatch_timer': 'sets or cancels a runner-held timer which queues a future agent turn',
    'dispatch_interrupt': 'cancels the current agent turn through the local runner control socket',
    'dispatch_login': 'starts and authenticates an agent through an ACP Session object',
    'dispatch_options': 'prime=true starts each agent once through a runner object to read the options it offers',
    'dispatch_serve': 'serves ACP and forwards requests through stateful frontend and agent objects',
    'node_invite': 'creates an account and invitation through the auth store object, locally or through SSH',
    'node_revoke': 'disables an account through the auth store object, locally or through SSH',
    'node_signout': 'bumps an account generation through the auth store object, invalidating sessions and tokens',
    'node_rotate-key': 'writes signing keys through the Keys object, locally or through SSH',
    'node_relay-enrol': "writes the relay's enrolments file through an Enrolments object",
    'node_relay-gate': 'starts the relay gate server, uvicorn, in the foreground',
    'twilio_call': 'places a paid call through the local bridge, whose Phone object sends it to Twilio',
    'twilio_text': 'sends a paid text through the local bridge or a Twilio Client object',
    'web_stop': 'asks the local page server to shut down through its control endpoint',
    'hello_follow': 'waits for the next map change and shows it; it writes nothing',
    'packet_check': 'reads a packet and says whether it is as sealed; it writes nothing',
    'workflow_resume': 'reads a workflow run by its id; it writes nothing',
    'workflow_serve': 'reads a skill whole, as dispatch sends it; it writes nothing',
}


@pytest.mark.req('MCP-003')
@pytest.mark.req('BASE-006')
def test_a_write_declared_read_is_caught_by_the_network_or_writes_check(home):
    """Every write/remove declaration must be protected by observed evidence or the exact fallback registry."""
    modules = every_module()
    reach = Reach(modules)
    declared = {f'{module.id}_{verb.name}': verb for module in modules for verb in module.verbs}
    sinks = {tool: reach.sinks(verb.run) for tool, verb in declared.items()}
    unseen = unseen_writes(declared, sinks)
    missed = []
    for module in modules:
        for verb in module.verbs:
            if verb.effect not in ('write', 'remove'):
                continue
            tool = f'{module.id}_{verb.name}'
            changed = {tool: dataclasses.replace(verb, effect='read')}
            one = dataclasses.replace(module, verbs=(verb,), resources=(), toolbar=(), panes=())
            wrong = undeclared(reach, [one], changed)
            if not any(line.startswith(f'{tool} declared read,') for line in wrong) and (
                    unseen_writes({**declared, **changed}, sinks) == unseen):
                missed.append(tool)
    assert not missed, 'write/remove mutations missed: ' + ', '.join(missed)
    assert unseen == set(UNSEEN), f'Write evidence registry differs: {sorted(unseen ^ set(UNSEEN))}'
    assert all(UNSEEN.values())


def unseen_writes(declared, sinks):
    return {tool for tool, verb in declared.items()
            if verb.effect in ('write', 'remove') and not {'write', 'send', 'file'} & sinks[tool].keys()}


# These verbs reach beyond the home and map through objects, callbacks or local runners rather than a direct
# network sink the walk recognizes. This is evidence of open-world behavior, not an exemption from declaring it.
UNSEEN_OPEN_WORLD = {
    'cloud_login': 'signs in through an httpx Client object',
    'cloud_connect': 'connects to the broker through a Connection object and its nested async entry point',
    'cloud_logout': 'revokes the sign-in through an httpx Client object',
    'dispatch_recover': 'signals verified agent process groups through platform process handles',
    'dispatch_permit': 'answers the agent through the local runner, which resolves the ACP permission or question',
    'dispatch_configure': 'the local runner applies a setting through ACP session mode or config methods',
    'dispatch_message': 'the local runner sends a new ACP prompt to the agent',
    'dispatch_broadcast': 'each running session\'s local runner sends a new ACP prompt to its agent',
    'dispatch_fork': 'the local runner forks or prompts an ACP agent session',
    'dispatch_timer': 'the local runner queues a new agent turn when the timer expires',
    'dispatch_interrupt': 'the local runner cancels the ACP agent turn',
    'dispatch_stop': 'the local runner cancels the agent and ends its process group',
    'dispatch_stop-all': 'each running session\'s local runner cancels its agent and ends its process group',
    'dispatch_options': 'prime=true starts an ACP agent through a Session object',
    'dispatch_tune': 'the local runner applies model and effort to the live ACP agent',
    'dispatch_cancel': 'the local runner cancels and ends the ACP agent session',
    'dispatch_login': 'opens an ACP agent Session and invokes its authentication method',
    'dispatch_serve': 'forwards editor requests to agents through stateful ACP frontend and adapter objects',
    'fork_wheel': 'selects dispatch.run dynamically from the loaded module to start a review agent',
    'fork_upkeep': 'selects dispatch.run dynamically from the loaded module to start upkeep agents',
    'mcp_a2a_send': 'sends to the remote agent through a factory-built A2A Client object',
    'mcp_a2a_exchanges': 'polls remote agents through factory-built A2A Client objects',
    'mcp_a2a_cancel': 'cancels remote work through a factory-built A2A Client object',
    'node_logs': 'reads logs on the remote host through an SSH subprocess',
    'node_relay': 'builds the relay wheel through plan callbacks and subprocesses that resolve external dependencies',
    'paperclip_status': 'reads the external Paperclip service through a Client object and injected opener',
    'paperclip_brief': 'reads the external Paperclip service through a Client object and injected opener',
    'paperclip_link': 'reads the external issue before linking it through a Client object and injected opener',
    'paperclip_sync': 'synchronizes external issues through a Client object and injected opener',
    'paperclip_watch': 'runs sync on a timer, synchronizing external issues through a Client object and injected opener',
    'twilio_serve': 'serves phone callbacks whose Phone object reaches Twilio and the selected voice engine',
    'twilio_call': 'the local bridge places the outbound call through a Phone object',
    'twilio_text': 'the local bridge or a Client object sends the outbound text to Twilio',
    'voice_speak': 'selects a module-provided engine callback, which can use an external speech service',
}


@pytest.mark.req('MCP-003')
@pytest.mark.req('BASE-006')
def test_an_open_world_verb_declared_closed_is_caught_by_the_annotation_check(home):
    """Removing open_world from any verb must be observable, including agent control through a local runner."""
    modules = every_module()
    reach = Reach(modules)
    declared = {f'{module.id}_{verb.name}': verb for module in modules for verb in module.verbs}
    sinks = {tool: reach.sinks(verb.run) for tool, verb in declared.items()}
    unseen = unseen_open_world(declared, sinks)
    missed = []
    for module in modules:
        for verb in module.verbs:
            if not verb.open_world:
                continue
            tool = f'{module.id}_{verb.name}'
            changed = {tool: dataclasses.replace(verb, open_world=False)}
            one = dataclasses.replace(module, verbs=(verb,), resources=(), toolbar=(), panes=())
            wrong = undeclared(reach, [one], changed)
            if not any(line.startswith(f'{tool} ') for line in wrong) and (
                    unseen_open_world({**declared, **changed}, sinks) == unseen):
                missed.append(tool)
    assert not missed, 'open_world mutations missed: ' + ', '.join(missed)
    assert unseen == set(UNSEEN_OPEN_WORLD), (
        f'Open-world evidence registry differs: {sorted(unseen ^ set(UNSEEN_OPEN_WORLD))}')
    assert all(UNSEEN_OPEN_WORLD.values())


def unseen_open_world(declared, sinks):
    return {tool for tool, verb in declared.items() if verb.open_world and 'network' not in sinks[tool]}


def every_module():
    from metaform import loader
    for found in loader.discover():
        loader.set_enabled(found.id, True)
    return loader.enabled()


def undeclared(reach, modules, changed=None):
    """Each verb whose declaration hides what it reaches, with the calls that lead there; `changed` swaps in a verb's
    declaration by tool name, as a wrong one would be written."""
    wrong = []
    for module in modules:
        for verb in module.verbs:
            tool = f'{module.id}_{verb.name}'
            verb = (changed or {}).get(tool, verb)
            sinks = reach.sinks(verb.run)
            if 'network' in sinks and not verb.open_world:
                wrong.append(f'{tool} reaches the network, open_world False: ' + ' > '.join(sinks['network']))
            if tool in UNSEEN_OPEN_WORLD and not verb.open_world:
                wrong.append(f'{tool} reaches outside the home and map, open_world False: ' + UNSEEN_OPEN_WORLD[tool])
            for kind in ('write', 'send', 'file'):
                exempt = (kind == 'write' and tool in WEB_ONLY_WRITES) or (
                    kind == 'file' and tool in SCREENSHOT_ONLY_WRITES)
                if kind in sinks and verb.effect == 'read' and not exempt:
                    wrong.append(f'{tool} declared read, {kind}s: ' + ' > '.join(sinks[kind]))
    return wrong


@pytest.mark.req('CLI-039')
def test_an_alias_adds_no_tool_since_its_modules_commands_are_each_a_tool(run, home, mapped):
    """An alias is one name at the top menu of the command line. Over MCP every command of its modules is already a
    tool of its own, so the alias adds none, and the commands it stands for run as their own tools."""
    run('memory', 'create_entities',
        '[{"name": "kitchen", "entityType": "timer", "observations": ["loud"], "why": "Agents need to know."}]',
        cwd=mapped)
    before = set(session(home, mapped, lambda client, init: listed(client)))
    run('alias', 'mapping', 'memory', 'map', cwd=mapped)

    async def check(client, init):
        tools = await listed(client)
        ran = await client.call_tool('map_joins', {'element': 'code.timer.kitchen'})
        graph = await client.call_tool('memory_read_graph', {})
        return tools, ran, graph
    tools, ran, graph = session(home, mapped, check)
    assert set(tools) == before and not any(name.startswith('mapping') for name in tools)
    assert json.loads(text(ran)[-1]) == json.loads(run('map', 'joins', 'code.timer.kitchen', '--json',
                                                       cwd=mapped).stdout)
    assert json.loads(text(graph)[-1]) == json.loads(run('memory', 'read_graph', '--json', cwd=mapped).stdout)


@pytest.mark.req('CLI-039')
@pytest.mark.req('CLI-022')
@pytest.mark.req('MCP-004')
@pytest.mark.cli_process
def test_the_tool_list_follows_the_folders_surface_in_a_running_session_and_an_alias_changes_nothing(run, home, mapped):
    heard = []

    async def check(client, init):
        before = set(await listed(client))
        run('alias', 'mapping', 'map', 'memory', cwd=mapped)
        await client.call_tool('map_layers', {})
        defined = set(await listed(client))
        run('set', '--modules', 'chassis,map', cwd=mapped)
        await client.call_tool('map_layers', {})
        await client.call_tool('map_layers', {})                      # nothing changed since: nothing more is said
        return before, defined, set(await listed(client))
    before, defined, narrowed = session(home, mapped, check, heard)
    assert defined == before                                          # the alias is no tool
    assert heard.count('notifications/tools/list_changed') == 1      # the narrowing; a tools/list is the new list itself
    assert 'memory_read_graph' in before and 'memory_read_graph' not in narrowed and 'map_where' in narrowed


@pytest.mark.req('CLI-037')
def test_a_commands_arguments_are_the_tools_own_arguments(run, home, mapped):
    """Found in the intake run of 2026-09-29: an agent sent a join's fields beside `command`, not inside `arguments`,
    and the call was refused though every field it needed was there. A command's tool takes its arguments as they
    are, so there is no wrapper for them to be sent beside."""
    async def check(client, init):
        return await client.call_tool('map_joins', {'element': 'code.timer.kitchen'})
    ran = session(home, mapped, check)
    wanted = json.loads(run('map', 'joins', 'code.timer.kitchen', '--json', cwd=mapped).stdout)
    assert not ran.is_error and json.loads(text(ran)[-1]) == wanted


@pytest.mark.req('MCP-032')
@pytest.mark.req('MCP-033')
def test_the_slash_commands_are_mcp_prompts_whose_text_is_what_the_command_line_prints(run, home, mapped):
    """Metaform still doesn't have its : commands, none for intake. Each command is an XML element
    of its owner's prompts.xml naming the verb it runs; /metaform:intake puts into the conversation exactly what
    metaform intake prompt prints for the same folder."""
    from metaform import prompt_files
    from metaform.data import prompts
    prompts.add_prompt('practices', 'markdown', 'one\n')
    prompts.add_prompt_version('practices', 'two\n', 1)

    async def call(client, init):
        listed = {prompt.name: prompt for prompt in (await client.list_prompts()).prompts}
        got = {name: await client.get_prompt(name, {}) for name in ('intake', 'tasks', 'status', 'refine')}
        got['prompt'] = await client.get_prompt('prompt', {'name': 'practices'})
        got['prompt 1'] = await client.get_prompt('prompt', {'name': 'practices', 'version': '1'})
        return listed, {name: [message.content.text for message in result.messages] for name, result in got.items()}, \
            {name: [message.role for message in result.messages] for name, result in got.items()}
    listed, texts, roles = session(home, mapped, call)
    assert {'intake', 'status', 'config', 'web', 'messages', 'tasks', 'refine', 'prompt'} <= set(listed)
    assert 'correct' not in listed                                     # dropped, D106
    assert listed['intake'].description and listed['config'].description and listed['prompt'].description
    assert all(role == ['user'] for role in roles.values())
    assert texts['intake'] == [run('intake', 'prompt', cwd=mapped).stdout.strip()]
    assert texts['tasks'] == [run('map', 'work', 'open=true', cwd=mapped).stdout.strip()]
    assert texts['status'] == [run(cwd=mapped).stdout.strip()]
    declared = {name: before for name, _, before, _, _ in prompt_files.module_commands('map')}
    assert texts['refine'] == [declared['refine'].strip()]             # the survey instruction as declared, D107
    assert not listed['refine'].arguments
    # D105: the stored prompt's exact text, the newest or the version named, as metaform prompt prints it
    assert [(one.name, one.required) for one in listed['prompt'].arguments] == [('name', True), ('version', False)]
    assert texts['prompt'] == ['two'] and texts['prompt 1'] == ['one']
    run('set', '--modules', 'intake,mcp', cwd=mapped)                  # map and web off the surface

    async def narrowed(client, init):
        names = {prompt.name for prompt in (await client.list_prompts()).prompts}
        try:
            await client.get_prompt('web', {})
            refused = False
        except Exception:  # noqa: BLE001  the server answers with an error
            refused = True
        return names, refused
    names, refused = session(home, mapped, narrowed)
    assert 'intake' in names and not {'web', 'tasks', 'messages', 'refine'} & names and refused


def help_agents(run, folder):
    return run('help', 'agents', cwd=folder).stdout


def over_mcp(folder):
    """The connect message the MCP server sends for the folder, MCP-029: mcp's instructions prompt as written, each
    module's connect line, mcp's closing line, then what the folder's state calls for; and, in a fresh session of a
    stdio server, the provisioning notice when the AI tool these tests run under is one the home has not recorded,
    MCP-028, since the server these tests start runs under it too."""
    import uuid

    from metaform.modules.mcp.server import connect_instructions
    return connect_instructions(folder, None, f'test:{uuid.uuid4().hex}')


@pytest.mark.req('CLI-037')
@pytest.mark.req('MCP-003')
def test_a_commands_tool_carries_its_schema_and_a_call_missing_an_argument_names_it(run, home, mapped):
    """A command's arguments, descriptions and schema are in its tool as listed, from the same declaration as its
    command line; a call that leaves out a required argument is refused with that tool as the next step."""
    async def check(client, init):
        opened = await client.call_tool('intake_start', {'model': 'claude', 'role': 'intake agent'})  # lists the rest
        assert not opened.is_error, text(opened)
        tools = await listed(client)
        missing = await client.call_tool('map_joins', {})
        return tools, missing
    tools, missing = session(home, mapped, check)
    page = run('help', 'map', 'joins', cwd=mapped).stdout
    joins = tools['map_joins'].input_schema
    assert joins['required'] == ['element'] and joins['additionalProperties'] is False
    assert joins['properties']['raw']['description'] in page
    fields = tools['intake_element'].input_schema['properties']
    assert fields['role']['enum'] and fields['namespace_address']['type'] == 'string'
    assert missing.is_error and text(missing)[0].splitlines()[-1] == (
        'Next: call map_joins with the arguments its input schema lists')


@pytest.mark.req('MCP-007')
@pytest.mark.req('MCP-031')
@pytest.mark.req('CLI-029')
@pytest.mark.cli_process
def test_the_instructions_are_composed_for_each_request_and_read_with_the_instructions_command(run, home, mapped):
    """The server composed its instructions once, at process start, so a session kept a stale snapshot. Each request
    that carries them composes them again, and the always-available instructions command, on the command line and
    over MCP, returns what metaform help agents prints at that moment."""
    from metaform.probe import Session, discover
    before = help_agents(run, mapped)
    assert run('instructions', cwd=mapped).stdout == before
    july = Session([sys.executable, '-m', 'metaform', 'mcp', 'serve'], cwd=mapped,
                   env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        run('set', '--debug', cwd=mapped)                               # changed after the server started
        after = help_agents(run, mapped)
        assert after != before
        assert discover(july)['instructions'].strip() == over_mcp(mapped).strip()
    finally:
        july.close()
    run('set', '--no-debug', cwd=mapped)

    async def check(client, init):
        first = text(await client.call_tool('metaform_instructions', {}))
        run('set', '--debug', cwd=mapped)
        second = text(await client.call_tool('metaform_instructions', {}))
        return init.instructions, first, second
    started, first, second = session(home, mapped, check)
    assert started.strip() == over_mcp(mapped).strip()
    assert first != second  # the guide the instructions command gives is composed again for each request
    run('set', '--modules', 'intake', cwd=mapped)                     # the chassis off the surface
    assert run('instructions', cwd=mapped).stdout == help_agents(run, mapped)


@pytest.mark.req('MCP-029')
@pytest.mark.req('MCP-032')
def test_a_module_s_full_instructions_come_on_entering_its_tool_and_skills_are_told_apart(run, home, mapped):
    """The compact connect-time text names each module in one line, so its full instructions come when an agent
    enters its tool or asks the instructions command for it; the workflow skills all ran one verb and showed one
    description, so each declares its own."""
    run('enable', 'workflow')
    full = run('help', 'agents', 'map', cwd=mapped).stdout.strip()

    async def check(client, init):
        entered = {'instructions': (await client.read_resource('metaform://instructions/map')).contents[0].text}
        asked = text(await client.call_tool('metaform_instructions', {'module': 'map'}))
        wrong = await client.call_tool('metaform_instructions', {'module': 'nope'})
        prompts = {one.name: one.description for one in (await client.list_prompts()).prompts}
        return init.instructions, entered, asked, wrong, prompts
    started, entered, asked, wrong, prompts = session(home, mapped, check)
    assert full not in started and len(startup_instructions(mapped)) <= 2048
    assert entered['instructions'].strip() == full and [block.strip() for block in asked] == [full]
    assert wrong.is_error
    from metaform.modules.workflow import SKILLS
    described = [prompts[name] for name in SKILLS if name not in ('sentinel', 'workflow_evaluator')]
    assert len(set(described)) == len(SKILLS) - 2 and all(described)
    assert not {'sentinel', 'workflow_evaluator'} & prompts.keys()


@pytest.mark.req('MCP-004')
@pytest.mark.req('MCP-007')
@pytest.mark.cli_process
def test_a_change_to_the_surface_reaches_a_running_session_as_a_list_change(run, home, mapped):
    """Enabling a module did not reach a running session: the tool list was announced as unchanging. Where the
    protocol allows, a session is told when its tools or slash commands change, at its next request."""
    heard = []

    async def check(client, init):
        listed_before = set(await listed(client))
        await client.list_prompts()
        run('set', '--modules', 'intake,map,mcp', cwd=mapped)         # web and memory leave the surface
        await client.call_tool('map_layers', {})
        await client.call_tool('map_layers', {})                      # nothing changed since: nothing more is said
        return init.capabilities, listed_before, set(await listed(client))
    capabilities, before, after = session(home, mapped, check, heard)
    assert capabilities.tools.list_changed is True and capabilities.prompts.list_changed is True
    assert 'web_start' in before and 'web_start' not in after
    assert heard.count('notifications/tools/list_changed') == 1
    assert heard.count('notifications/prompts/list_changed') == 1


@pytest.mark.req('MCP-003')
@pytest.mark.req('MCP-004')
@pytest.mark.cli_process
def test_a_folder_with_no_project_lists_only_what_runs_and_registering_announces_the_rest(run, home, tmp_path):
    """Before registration, 62 of 123 listed tools could do nothing but say there was no project, and every tool
    carried project and layers. Now only what runs without a project is listed, registering lists the rest as a
    change, and project and layers are on the tools that use them."""
    folder = tmp_path / 'loose'
    folder.mkdir()
    heard = []

    async def check(client, init):
        before = {one.name: one for one in (await client.list_tools()).tools}
        await client.call_tool('metaform_register', {'id': 'loose'})
        after = {one.name: one for one in (await client.list_tools()).tools}
        refused = await client.call_tool('web_start', {'layers': ['base']})
        return before, after, refused
    before, after, refused = session(home, folder, check, heard)
    assert not any(name.startswith(('map_', 'memory_')) for name in before)
    assert {'metaform_register', 'metaform_skills', 'web_start', 'fork_init', 'intake_schema'} <= before.keys()
    assert not {'intake_start', 'metaform_add_origin', 'mcp_a2a_send'} & before.keys()
    assert heard.count('notifications/tools/list_changed') == 1        # registering, once
    assert {'map_where', 'memory_read_graph', 'intake_start', 'metaform_add_origin'} <= after.keys()
    where, web = after['map_where'].input_schema['properties'], after['web_start'].input_schema['properties']
    assert {'project', 'layers'} <= where.keys() and not {'project', 'layers'} & web.keys()
    assert 'web_emote' not in after                                      # listed only while the web GUI runs
    assert 'layers' not in after['intake_start'].input_schema['properties']  # a project, but not the map's layers
    assert 'layers' not in after['memory_note'].input_schema['properties'] and 'project' in after['memory_note'].input_schema['properties']
    assert refused.is_error and 'takes no layers' in text(refused)[0]


@pytest.mark.req('MCP-003')
@pytest.mark.req('MCP-039')
def test_what_the_list_cuts_comes_once_with_the_first_use_of_a_tool_and_its_module(run, home, mapped):
    """Every tool's long description and argument help were paid by every agent before its first call. The list now
    gives a sentence and a clause, and the first call of a tool in a session carries the rest, and the first call of
    any tool of a module that module's rules, each once."""
    from metaform import prompt_files
    async def check(client, init):
        tools = await listed(client)
        first, second = (await client.call_tool('map_work', {}), await client.call_tool('map_work', {}))
        memory = [await client.call_tool(name, {'node': 'element:code.timer.kitchen'})
                  for name in ('memory_read_graph', 'memory_note')]
        settings = await client.call_tool('metaform_set', {})
        return tools, first, second, memory, settings
    tools, first, second, memory, settings = session(home, mapped, check)
    work = tools['map_work']
    assert 'op=plan' not in work.description and len(work.description) <= 200
    assert all(len(one.get('description', '').encode()) <= 80 for one in work.input_schema['properties'].values())
    assert first.content[0].text.startswith('How to use map_work, given once in this session:')
    assert 'op=plan' in first.content[0].text and json.loads(text(first)[-1]) == json.loads(text(second)[-1])
    assert not any(GUIDED.match(block.text) for block in second.content)
    rule = prompt_files.module_rules('memory')[0][0]
    assert sum(rule in block.text for one in memory for block in one.content) == 1  # the module's rules, once
    named = {one['name'] for one in settings.structured_content['settings']}
    assert 'write_layer' in named and 'dispatch_prompts' not in named and len(json.dumps(
        tools['metaform_set'].input_schema)) < 600  # listed when called, not in the schema


@pytest.mark.req('MCP-004')
@pytest.mark.cli_process
def test_listing_the_prompts_then_calling_a_tool_announces_no_change(run, home, mapped):
    """The prompts listed were kept in another shape than the one compared, so every call announced a change."""
    heard = []

    async def check(client, init):
        await client.list_prompts()
        await client.call_tool('map_layers', {})
        await client.call_tool('map_layers', {})
    session(home, mapped, check, heard)
    assert 'notifications/prompts/list_changed' not in heard


class Served:
    """`metaform mcp serve --http`'s app for the folder, on 127.0.0.1 in a thread of its own."""

    def __init__(self, folder):
        import socket
        import threading

        import uvicorn

        from metaform.modules.mcp.server import http_app
        with socket.socket() as held:
            held.bind(('127.0.0.1', 0))
            port = held.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}/mcp'
        self.server = uvicorn.Server(uvicorn.Config(http_app(folder), host='127.0.0.1', port=port,
                                                    log_level='warning'))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert self.server.started

    def stop(self):
        self.server.should_exit = True
        self.thread.join(10)


@pytest.mark.parametrize('background', [False, True])
def test_gateway_identity_and_delivery_are_per_run(run, home, mapped, user_module, monkeypatch, background):
    """A shared HTTP connection carries fresh identity per call, including calls executed as tasks."""
    import httpx

    user_module('gatewayprobe', '''
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def read(ctx):
            return {'identity': ctx.identity, 'session': ctx.session, 'before': ctx.seen('gateway-proof', 1)}
        MODULE = Module('gatewayprobe', 'Observe call context.', 'Verify per-call delivery.', verbs=(
            Verb('read', read, 'Read context.', effect='read', task=True),))
    ''')
    run('enable', 'gatewayprobe', cwd=mapped)
    run('enable', 'paperclip', cwd=mapped)
    from metaform.module import context
    from metaform.modules import paperclip
    paperclip._keep(context('paperclip', mapped).require_store(), {
        'issue_id': 'gateway-issue', 'address': 'code.alarm.audible', 'work_id': 'gateway-work', 'works': 'paperclip'})
    monkeypatch.setenv('METAFORM_SESSION', 'server-process')
    served = Served(mapped)

    async def go():
        async with httpx.AsyncClient() as client:
            async def request(method, params, headers):
                params = {**params, '_meta': {'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                    'io.modelcontextprotocol/clientCapabilities': {}, **params.get('_meta', {})}}
                response = await client.post(served.url, headers={
                    'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2026-07-28',
                    'MCP-Method': method, **({'MCP-Name': params['name']} if 'name' in params else {}),
                    **headers}, json={'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})
                assert response.is_success, response.text
                response.raise_for_status()
                if response.headers.get('mcp-session-id'):
                    client.headers['mcp-session-id'] = response.headers['mcp-session-id']
                if response.headers['content-type'].startswith('text/event-stream'):
                    return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith('data: ')))
                return response.json()

            async def read(run_id=None, issue='i-1', agent='a-1'):
                headers = {} if run_id is None else {'X-Paperclip-Agent-Id': agent,
                    'X-Paperclip-Issue-Id': issue, 'X-Paperclip-Run-Id': run_id}
                capabilities = {'extensions': {'io.modelcontextprotocol/tasks': {}}} if background else {}
                reply = await request('tools/call', {'name': 'gatewayprobe_read', 'arguments': {},
                    '_meta': {'io.modelcontextprotocol/clientCapabilities': capabilities}}, headers)
                assert 'error' not in reply, reply
                result = reply['result']
                if background:
                    assert result['resultType'] == 'task', result
                    deadline = time.monotonic() + 10
                    while result['status'] == 'working':
                        assert time.monotonic() < deadline
                        await asyncio.sleep(0.02)
                        result = (await request('tasks/get', {'taskId': result['taskId'],
                            '_meta': {'io.modelcontextprotocol/clientCapabilities': capabilities}}, {}))['result']
                    assert result['status'] == 'completed', result
                    result = result['result']
                assert not result.get('isError'), result
                return result['structuredContent']

            first = await read('r-1')
            assert first['identity'] == {'agent_id': 'a-1', 'issue_id': 'i-1', 'run_id': 'r-1'}
            assert first['before'] is None
            assert (await read('r-1', issue='i-2'))['before'] == 1
            assert (await read('r-2'))['before'] is None
            assert (await read('r-1', agent='a-2'))['before'] is None
            concurrent = await asyncio.gather(read('r-3'), read('r-4'))
            assert [one['identity']['run_id'] for one in concurrent] == ['r-3', 'r-4']
            assert all(one['before'] is None for one in concurrent)
            plain = await read()
            assert plain['identity'] == {} and plain['session'] == 'server-process'
            assert os.environ['METAFORM_SESSION'] == 'server-process'
            brief = (await request('tools/call', {'name': 'paperclip_brief', 'arguments': {}}, {
                'X-Paperclip-Issue-Id': 'gateway-issue', 'X-Paperclip-Run-Id': 'r-5'}))['result']
            assert not brief.get('isError'), brief
            assert 'code.alarm.audible' in '\n'.join(block['text'] for block in brief['content'])

    try:
        asyncio.run(go())
    finally:
        served.stop()


def test_paperclip_brief_resolves_explicit_issue_then_call_identity_then_environment(run, mapped, monkeypatch):
    from metaform.module import context
    from metaform.modules import paperclip

    run('enable', 'paperclip', cwd=mapped)
    store = context('paperclip', mapped).require_store()
    for issue, address in [('explicit', 'code.timer.kitchen'), ('header', 'code.alarm.audible'),
                           ('environment', 'code.timer.kitchen')]:
        paperclip._keep(store, {'issue_id': issue, 'address': address, 'work_id': issue, 'works': 'paperclip'})
    monkeypatch.setenv('PAPERCLIP_TASK_ID', 'environment')
    monkeypatch.setattr(paperclip, 'node_brief', lambda folder, address: address)
    ctx = context('paperclip', mapped, surface='mcp')
    ctx.identity = {'issue_id': 'header'}
    assert paperclip.brief(ctx) == 'code.alarm.audible\n'
    ctx.nouns['issue'] = 'explicit'
    assert paperclip.brief(ctx) == 'code.timer.kitchen\n'
    ctx.nouns.clear()
    ctx.identity.clear()
    assert paperclip.brief(ctx) == 'code.timer.kitchen\n'


async def heard_until(heard, method, count, limit=5):
    """Wait for `count` of `method` in `heard`, written by the client's GET stream task, or the limit."""
    deadline = time.monotonic() + limit
    while heard.count(method) < count and time.monotonic() < deadline:
        await asyncio.sleep(0.05)


@pytest.mark.req('MCP-002')
@pytest.mark.req('MCP-004')
def test_over_http_each_client_that_connected_with_initialize_hears_a_list_change_once(run, home, mapped):
    """Over HTTP one server answers every client. Its initialize declared no list changes, and what was last shown
    was one record for all of them, so the first client to list again took the change from every other."""
    from contextlib import AsyncExitStack

    from mcp.client.streamable_http import streamable_http_client
    served = Served(mapped)
    heard = {'a': [], 'b': []}

    async def go():
        async with AsyncExitStack() as stack:
            clients = {}
            for name in ('a', 'b'):
                async def hear(message, name=name):
                    method = getattr(message, 'method', None)
                    if method:
                        heard[name].append(method)
                read, write = await stack.enter_async_context(streamable_http_client(served.url))
                clients[name] = await stack.enter_async_context(ClientSession(read, write, message_handler=hear))
                init = await clients[name].initialize()
                assert init.capabilities.tools.list_changed is True
                assert init.capabilities.prompts.list_changed is True
                await clients[name].list_tools()
            run('set', '--modules', 'intake,map,mcp', cwd=mapped)
            await clients['a'].list_tools()
            await clients['a'].call_tool('map_layers', {})
            await clients['b'].call_tool('map_layers', {})
            await clients['b'].call_tool('map_layers', {})
            await heard_until(heard['b'], 'notifications/tools/list_changed', 2, limit=2)
    try:
        asyncio.run(go())
    finally:
        served.stop()
    assert heard['b'].count('notifications/tools/list_changed') == 1
    assert heard['a'].count('notifications/tools/list_changed') <= 1


@pytest.mark.req('MCP-002')
@pytest.mark.req('MCP-004')
def test_on_the_july_wire_a_listen_stream_hears_the_list_change(run, home, mapped):
    """MCP 2026-07-28 has no connection to announce on: change notifications ride a subscriptions/listen stream, and
    each list says how long a client may keep it before asking again."""
    from metaform.probe import Session, discover
    july = Session([sys.executable, '-m', 'metaform', 'mcp', 'serve'], cwd=mapped,
                   env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        found = discover(july)
        assert found['capabilities']['tools']['listChanged'] is True
        assert '2026-07-28' in found['supportedVersions']
        for method in ('tools/list', 'prompts/list', 'resources/list', 'resources/templates/list'):
            listed = july.request(method, {}, deadline=time.monotonic() + 30)  # a client may keep it a minute
            assert (listed['ttlMs'], listed['cacheScope']) == (60_000, 'private'), method
        listen = july.open('subscriptions/listen', {'notifications': {'toolsListChanged': True}})
        assert july.call('map_layers', {})['resultType'] == 'complete'
        run('set', '--modules', 'intake,map,mcp', cwd=mapped)
        july.request('tools/list', {}, deadline=time.monotonic() + 30)  # the stream hears it though this client listed
        july.call('map_layers', {})

        def changed():
            return [notice['params']['_meta']['io.modelcontextprotocol/subscriptionId'] for notice in july.notices
                    if notice['method'] == 'notifications/tools/list_changed']
        deadline = time.monotonic() + 10                                # the stream is written by its own task
        while not changed() and time.monotonic() < deadline:
            july.request('ping', {}, deadline=deadline)
        assert changed() == [listen]
    finally:
        july.close()


@pytest.mark.req('MCP-017')
def test_the_install_proof_passes_the_real_server_on_the_july_wire(home, mapped):
    from metaform.probe import probe
    proof = probe([sys.executable, '-m', 'metaform', 'mcp', 'serve'], cwd=mapped,
                  env={**os.environ, 'METAFORM_HOME': str(home)})
    assert proof.ok and proof.tools >= 2, proof.reason
    assert proof.instructions.strip() == over_mcp(mapped).strip()


@pytest.mark.req('MAP-058')
def test_a_direct_claim_over_mcp_is_honored_by_the_agent_the_client_names_at_initialize(run, home, mapped):
    """Ticket bd96cbd1: over MCP the claiming agent is the one the client names at initialize, the harness the agent
    runs in, so a by that names another agent changes nothing. Claude Code takes a ticket for claude; Codex is
    refused it, whatever its by says, and the ticket stays untaken."""
    from mcp.types import Implementation

    from metaform.data import Node
    store = Store('proj')
    gui = store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='GUI work').id
    run('map', 'work', 'op=edit', f'id={gui}', 'eligible=["claude"]', cwd=mapped)
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(mapped),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    def take(client_name, by):
        async def go():
            async with stdio_client(params) as (read, write), ClientSession(
                    read, write, client_info=Implementation(name=client_name, version='1')) as client:
                await client.initialize()
                return await called(client, 'map_work', {'op': 'take', 'id': gui, 'by': by})
        return asyncio.run(go())
    for client_name in ('codex-mcp-client', 'unknown-client'):
        refused = take(client_name, 'claude 41ab')
        assert refused.is_error and 'claude' in text(refused)[0], text(refused)
        assert store.ticket(gui).work.taken is None
    took = take('claude-code', 'the agent')
    assert not took.is_error, text(took)
    assert store.ticket(gui).work.taken_by == 'the agent'


@pytest.mark.req('MCP-037')
def test_resources_serve_the_instructions_and_what_a_module_declares(run, home, mapped):
    """What an agent reads at discovery, before any tool runs: the instructions, a module's instructions, and the
    resources a module declares, each read through one of its verbs; a command's arguments are in its tool. The intake module
    declares its procedure and its forms. A URI nothing serves is refused with a next step."""
    async def check(client, init):
        fixed = {one.uri: one for one in (await client.list_resources()).resources}
        templates = {one.uri_template for one in (await client.list_resource_templates()).resource_templates}
        texts = {uri: (await client.read_resource(uri)).contents[0].text for uri in (
            'metaform://instructions', 'metaform://instructions/intake', 'metaform://intake/procedure',
            'metaform://intake/schema')}
        try:
            await client.read_resource('metaform://instructions/nothing')
            refused = None
        except Exception as error:  # noqa: BLE001
            refused = str(error)
        return init.capabilities.resources.list_changed, fixed, templates, texts, refused
    changed, fixed, templates, texts, refused = session(home, mapped, check)
    assert changed and set(fixed) == {'metaform://metaform', 'metaform://proj', 'metaform://tools',
                                      'metaform://runtime/compaction-state',
                                      'metaform://instructions', 'metaform://intake/procedure',
                                      'metaform://intake/schema'}
    assert all(one.description and one.name for one in fixed.values())
    assert templates == {'metaform://instructions/{module}', 'metaform://prompts/{name}', 'metaform://reports/{name}',
                         'metaform://{address}', 'metaform://{address}/items/{n}'}
    from metaform import prompt_files
    assert texts['metaform://instructions'].startswith(prompt_files.chassis('surface_mcp'))  # the guide, served
    assert texts['metaform://instructions/intake'] == run('help', 'agents', 'intake', cwd=mapped).stdout.strip()
    assert texts['metaform://intake/procedure'].strip() == run('intake', 'prompt', cwd=mapped).stdout.strip()
    assert texts['metaform://intake/schema'].strip() == run('intake', 'schema', cwd=mapped).stdout.strip()
    assert refused and 'No resource metaform://instructions/nothing' in refused and 'Next:' in refused


@pytest.mark.req('CLI-011')
@pytest.mark.req('MCP-006')
@pytest.mark.req('BASE-052')
def test_an_agent_over_mcp_cannot_set_what_decides_its_own_permissions(run, home, mapped):
    """dispatch_prompts and every other person_only setting is written by the person, on the command line or the
    page; `set` over MCP refuses it with one next step and stores nothing of the call, and is not offered it."""
    run('enable', 'dispatch')

    async def call(client, init):
        refused = await called(client, 'metaform_set', {'debug': True, 'dispatch_prompts': 'approve-all'})
        offered = await called(client, 'metaform_set', {})  # the settings it takes, listed when called with none
        return refused.is_error, text(refused)[0], {one['name'] for one in offered.structured_content['settings']}
    error, said, offered = session(home, mapped, call)
    assert error and 'dispatch_prompts is set only by the person' in said
    assert [line for line in said.splitlines() if line.startswith('Next: ')] == [  # the person's way, person-consent F2
        ('Next: ask the person in chat; to do it they use the settings screen on the page, or paste into their own '
        'terminal window (an AI tool runs commands without the consent a terminal carries): '
        'metaform set --dispatch-prompts approve-all')]
    assert 'dispatch_prompts' not in offered and 'debug' in offered
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert shown['dispatch_prompts']['state'] == shown['debug']['state'] == 'default'
    run('set', '--dispatch-prompts', 'approve-reads', cwd=mapped)    # the person still sets it on the command line
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert shown['dispatch_prompts']['value'] == 'approve-reads'


@pytest.mark.req('CLI-011')
@pytest.mark.req('MCP-006')
def test_a_person_only_setting_given_for_one_call_over_mcp_is_refused_before_the_verb_runs(run, home, mapped):
    """A per-call switch is a write of that call's value: autostart given dispatch_autostart and dispatch_agents over
    MCP would start agents the person has not allowed, so the call stops before it runs, and they are not offered."""
    run('enable', 'dispatch')

    async def call(client, init):
        refused = await called(client, 'dispatch_autostart', {'dispatch_autostart': True, 'dispatch_agents': 9})
        offered = (await listed(client))['dispatch_autostart'].input_schema
        return refused.is_error, text(refused)[0], offered['properties']
    error, said, offered = session(home, mapped, call)
    assert error and said.startswith('Error: dispatch_agents, dispatch_autostart are set only by the person')
    assert not {'dispatch_autostart', 'dispatch_agents', 'dispatch_recovery'} & set(offered)


@pytest.mark.req('CLI-011')
def test_the_person_can_let_agents_set_control_settings_over_mcp(run, home, mapped):
    """Control is a permission the person holds: with agents_may_set_control on, which only the person sets, an agent
    over MCP may set dispatch_prompts; off, the default, it is refused, as the test above shows."""
    run('enable', 'dispatch')
    run('set', '--agents-may-set-control', cwd=mapped)

    async def call(client, init):
        said = await called(client, 'metaform_set', {'dispatch_prompts': 'approve-reads'})
        return said.is_error, text(said)[0]
    error, said = session(home, mapped, call)
    assert not error, said
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert shown['dispatch_prompts']['value'] == 'approve-reads'


@pytest.mark.req('MAP-050')
def test_ticket_authority_lets_a_session_with_no_role_write_a_ticket_over_mcp(run, home, mapped):
    """A session the person runs outside dispatch has no role, and assigns work through Metaform over MCP."""
    async def call(client, init):
        said = await called(client, 'map_work', {'op': 'add', 'node': 'code.timer.kitchen', 'task': 'Wire the alarm.',
                                                 'title': 'Wire the alarm'})
        return said.is_error, text(said)[0]
    error, said = session(home, mapped, call)
    assert not error, said
    assert [record.task for record in Store('proj').work(open=True, limit=0).results] == ['Wire the alarm.']


@pytest.mark.req('MAP-050')
def test_ticket_authority_refuses_a_worker_over_mcp_and_on_the_command_line(run, home, mapped, monkeypatch):
    """A worker writes no ticket, by the role its runner gave it, on either surface; the refusal names the role."""
    monkeypatch.setenv('METAFORM_ROLE', 'worker')

    async def call(client, init):
        said = await called(client, 'map_work', {'op': 'add', 'node': 'code.timer.kitchen', 'task': 'More work.'})
        return said.is_error, text(said)[0]
    error, said = session(home, mapped, call)
    assert error and 'A worker agent writes no ticket' in said
    refused = run('map', 'work', 'op=add', 'node=code.timer.kitchen', 'task=More work.', cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'A worker agent writes no ticket' in refused.stderr + refused.stdout
    assert not Store('proj').work(open=True, limit=0).results


@pytest.mark.req('MAP-050')
@pytest.mark.req('CLI-011')
def test_ticket_authority_is_lifted_when_the_person_holds_no_role_back(run, home, mapped, monkeypatch):
    """The rule is the person's setting, not a refusal they cannot get past: set to none, a worker writes a ticket."""
    run('set', '--roles-without-authority', 'none', cwd=mapped)
    monkeypatch.setenv('METAFORM_ROLE', 'worker')

    async def call(client, init):
        said = await called(client, 'map_work', {'op': 'add', 'node': 'code.timer.kitchen', 'task': 'Child work.',
                                                 'title': 'Child work'})
        return said.is_error, text(said)[0]
    error, said = session(home, mapped, call)
    assert not error, said
    assert [record.task for record in Store('proj').work(open=True, limit=0).results] == ['Child work.']


@pytest.mark.req('MCP-007')
def test_connect_points_to_the_glossary_and_the_glossary_resource_serves_it_whole(run, home, mapped):
    from metaform import prompt_files
    glossary = prompt_files.module('mcp', 'glossary')

    async def check(client, init):
        listed = [str(one.uri) for one in (await client.list_resources()).resources]
        read = await client.read_resource('metaform://metaform')
        return init.instructions, listed, read.contents[0].text
    started, listed, served = session(home, mapped, check)
    assert 'metaform://metaform, then metaform://proj' in started and len(startup_instructions(mapped)) <= 2048
    assert listed[:3] == ['metaform://metaform', 'metaform://proj', 'metaform://tools']
    assert served == glossary.strip() + '\n' and len(served) > 2048  # whole and alone, past the connect text's cut


@pytest.mark.req('MCP-003')
def test_the_glossary_is_one_text_by_tool_resource_and_command_line(run, home, mapped):
    """metaform_instructions with module metaform is the glossary the resource serves and the command line prints."""
    async def check(client, init):
        tool = await called(client, 'metaform_instructions', {'module': 'metaform'})
        assert not tool.is_error, text(tool)
        described = tool.content[0].text  # the argument's whole help, with the tool's first use, MCP-039
        return ''.join(text(tool)), (await client.read_resource('metaform://metaform')).contents[0].text, described
    by_tool, by_resource, described = session(home, mapped, check)
    assert by_tool == by_resource == run('instructions', 'metaform', cwd=mapped).stdout
    assert 'metaform://metaform' in described  # found with the tool by a model that cannot read resources


SHIPPED = ('dispatch', 'fork', 'hello', 'intake', 'map', 'mcp', 'memory', 'packet', 'template', 'web', 'workflow')


@pytest.mark.req('MCP-029')
def test_the_connect_message_is_an_order_with_a_line_per_module_and_fits_what_the_host_keeps(run, home, mapped,
                                                                                            tmp_path):
    """Connect says Metaform must be used, then one phrase per enabled module from its connect prompt, then the
    closing line pointing at the glossary and the tools, then the folder's notices; with every shipped module on it
    stays well under the 2,048 characters Claude Code keeps, with an intake and before one."""
    from metaform import prompt_files
    from metaform.instructions import startup
    for module in SHIPPED:
        run('enable', module)
    sent = startup(mapped)
    order = prompt_files.module('mcp', 'instructions')
    end = prompt_files.module('mcp', 'instructions_end', terms=prompt_files.module('mcp', 'instructions_terms',
                                                                                     project='proj'))
    lines = sent.splitlines()
    assert lines[0] == order
    uses = [line for line in (prompt_files.module(module, 'connect') for module in sorted(SHIPPED)) if line]
    assert lines[1:1 + len(uses)] == uses and all(line.startswith('– ') for line in uses)
    assert [line.split(':')[0] for line in uses] == [f'– {module}' for module in sorted(SHIPPED)
                                                    if module not in ('mcp', 'template')]  # empty adds nothing
    assert sent.index(end) > sent.index(uses[-1]) and 'metaform://metaform' in end
    assert len(sent) <= 1500, len(sent)
    bare = tmp_path / 'bare'
    bare.mkdir()
    run('add', 'project', 'bare', str(bare))
    before = startup(bare)  # no intake: intake's notice follows the order
    end = end.replace('metaform://proj', 'metaform://bare')
    assert before.startswith(order) and before.index(end) < len(before) - len(end) - 2 and len(before) <= 2048
    run('set', '--modules', 'map', cwd=mapped)  # what the folder's surface leaves out says nothing
    assert startup(mapped).splitlines()[1:2] == [prompt_files.module('map', 'connect')]


@pytest.mark.req('MCP-037')
def test_every_address_resolves_to_its_brief_and_each_numbered_item_with_the_july_code_when_missing(run, home,
                                                                                                    mapped):
    """metaform://<address> is the node's brief, map's first where read; metaform://<address>#<n> the one item numbered
    n there, upper-case hex read too, its links shown as <address>#<n> and title; a missing address or item is
    refused with a next step, -32602 on the July wire and -32002 on the 2025 handshake, whose resources page names it;
    the fixed resources are never read as addresses."""
    run('memory', 'create_entities', json.dumps([
        {'name': 'tone', 'entityType': 'finding', 'observations': ['The tone is too quiet.'],
         'why': 'The cook misses it.'},
        {'name': 'piezo', 'entityType': 'part', 'title': 'The piezo drives the tone',
         'observations': ['Rated 3 V.\nFed 5 V.'], 'why': 'It explains the quiet tone.'}]), 'node=code.alarm.audible',
        cwd=mapped)
    run('memory', 'create_relations', json.dumps([{'from': 'tone', 'to': 'piezo', 'relationType': 'comes from'}]),
        cwd=mapped)
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'task=Feed the piezo 3 V.', 'title=Feed the piezo 3 V',
        cwd=mapped)

    async def check(client, init):
        read = {}
        for uri in ('metaform://code.alarm.audible', 'metaform://code.alarm.audible#1',
                    'metaform://code.alarm.audible#2', 'metaform://code.alarm.audible#3', 'metaform://metaform',
                    'metaform://code.alarm.audible/items/1'):
            read[uri] = (await client.read_resource(uri)).contents[0].text
        refused = {}
        for uri in ('metaform://code.nosuch.node', 'metaform://code.alarm.audible#FF',
                    'metaform://code.alarm.audible#0'):
            try:
                await client.read_resource(uri)
                refused[uri] = None
            except Exception as error:  # noqa: BLE001
                refused[uri] = (getattr(getattr(error, 'error', None), 'code', None), str(error))
        return read, refused
    read, refused = session(home, mapped, check)
    brief = read['metaform://code.alarm.audible']  # map's where read as it gives it the first time, whatever its layout
    assert 'code.alarm.audible' in brief and 'code.timer.kitchen' in brief  # the node and what relies on it
    first = read['metaform://code.alarm.audible#1'].splitlines()
    assert first[:2] == ['code.alarm.audible#1  The tone is too quiet.', 'memory · why: The cook misses it.']
    assert '  comes from → code.alarm.audible#2  The piezo drives the tone' in first
    assert read['metaform://code.alarm.audible/items/1'] == read['metaform://code.alarm.audible#1'], 'the path form'
    assert read['metaform://code.alarm.audible#2'].startswith('code.alarm.audible#2  The piezo drives the tone\n')
    assert read['metaform://code.alarm.audible#3'].splitlines()[:2] == ['code.alarm.audible#3  Feed the piezo 3 V',
                                                                        'work']
    assert read['metaform://metaform'].startswith('@STATE_INIT')
    for uri, (code, said) in refused.items():
        assert code == -32002 and 'Next:' in said, (uri, said)
    july = july_wire(home, mapped)
    try:
        from metaform.probe import discover
        discover(july)
        with pytest.raises(RuntimeError, match='-32602'):
            july.request('resources/read', {'uri': 'metaform://code.nosuch.node'}, deadline=time.monotonic() + 30)
    finally:
        july.close()


def a2a(folder, calls):
    """The A2A routes on an app of their own, as metaform mcp serve --http attaches them to MCP's, driven in-process
    over httpx; `calls` gets the client and the bearer token."""
    import httpx
    from starlette.applications import Starlette

    from metaform.modules.mcp import a2a as served

    app = Starlette()
    served.attach(app, folder, 7434)

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1:7434') as client:
            return await calls(client, served.token())
    return asyncio.run(go())


def rpc(method, params, number=1):
    return {'jsonrpc': '2.0', 'id': number, 'method': method, 'params': params}


@pytest.mark.req('MCP-002')
def test_a2a_card_is_public_and_names_no_project_and_everything_else_needs_its_own_token(run, home, mapped):
    async def calls(client, token):
        card = await client.get('/.well-known/agent-card.json')
        bare = await client.post('/a2a', json=rpc('GetExtendedAgentCard', {}), headers={'A2A-Version': '1.0'})
        wrong = await client.post('/a2a', json=rpc('GetExtendedAgentCard', {}),
                                  headers={'A2A-Version': '1.0', 'Authorization': 'Bearer not-it'})
        extended = await client.post('/a2a', json=rpc('GetExtendedAgentCard', {}),
                                     headers={'A2A-Version': '1.0', 'Authorization': f'Bearer {token}'})
        rebound = await client.get('/.well-known/agent-card.json', headers={'Host': 'evil.example'})
        return card, bare, wrong, extended, rebound
    card, bare, wrong, extended, rebound = a2a(mapped, calls)
    assert card.status_code == 200 and '"proj"' not in card.text and 'tenant' not in card.text  # no project, P005
    shown = card.json()
    assert shown['capabilities']['extendedAgentCard'] is True and not shown['capabilities'].get('pushNotifications')
    assert [skill['id'] for skill in shown['skills']] == ['ticket']  # the one thing A2A does here; no tool catalogue
    assert '30 seconds' in shown['skills'][0]['description']  # the cap on a waiting send, stated where clients read
    assert not shown['capabilities']['extensions'][0].get('required')  # works without it: Metaform asks
    assert bare.status_code == 401 and bare.headers['www-authenticate'] == 'Bearer realm="metaform-a2a"'
    assert wrong.status_code == 401 and 'invalid_token' in wrong.headers['www-authenticate']
    assert rebound.status_code == 421  # the MCP endpoint's DNS-rebinding guard, on the card too
    interfaces = extended.json()['result']['supportedInterfaces']
    assert {(one['protocolBinding'], one.get('tenant', '')) for one in interfaces} >= {('JSONRPC', 'proj'),
                                                                                       ('HTTP+JSON', 'proj')}


@pytest.mark.req('MCP-002')
def test_an_a2a_message_opens_one_numbered_ticket_at_its_address_and_the_task_follows_the_ticket(run, home, mapped):
    message = {'messageId': 'm-1', 'role': 'ROLE_USER', 'contextId': 'code.alarm.audible',
               'parts': [{'text': 'Make the alarm louder\nThe cook misses it over the fan.'}]}
    sent = {'message': message, 'configuration': {'returnImmediately': True}}

    async def calls(client, token):
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}', 'User-Agent': 'peer/1'}
        first = (await client.post('/a2a', json=rpc('SendMessage', sent), headers=headers)).json()
        again = (await client.post('/a2a', json=rpc('SendMessage', sent), headers=headers)).json()
        nowhere = (await client.post('/a2a', json=rpc('SendMessage', {
            'message': {**message, 'messageId': 'm-2', 'contextId': 'code.no.such'}}), headers=headers)).json()
        unaddressed = (await client.post('/a2a', json=rpc('SendMessage', {
            'message': {**message, 'messageId': 'm-3', 'contextId': ''}}), headers=headers)).json()
        task_id = first['result']['task']['id']
        run('map', 'work', 'op=take', f'id={task_id}', 'steps=2', cwd=mapped)
        working = (await client.post('/a2a', json=rpc('GetTask', {'id': task_id}), headers=headers)).json()
        run('map', 'work', 'op=done', f'id={task_id}', 'resolution=Louder now', 'why=The cook hears it', cwd=mapped)
        done = (await client.get(f'/a2a/rest/tasks/{task_id}', headers=headers)).json()
        cancel = (await client.post('/a2a', json=rpc('CancelTask', {'id': task_id}), headers=headers)).json()
        tenant = await client.get(f'/a2a/rest/proj/tasks/{task_id}', headers=headers)
        stranger = await client.get(f'/a2a/rest/nosuch/tasks/{task_id}', headers=headers)
        return first, again, nowhere, unaddressed, working, done, cancel, tenant, stranger
    first, again, nowhere, unaddressed, working, done, cancel, tenant, stranger = a2a(mapped, calls)
    assert tenant.json()['id'] == first['result']['task']['id'] and stranger.status_code == 400  # a project by its id
    task = first['result']['task']
    assert task['contextId'] == 'code.alarm.audible' and task['status']['state'] == 'TASK_STATE_SUBMITTED'
    detail = task['metadata']['https://metaform.ing/a2a/address-context/v1']
    assert detail['item'] == 'code.alarm.audible#1' and detail['title'] == 'Make the alarm louder'
    assert again['result']['task']['id'] == task['id']  # a retried message opens no second ticket
    assert nowhere['error']['code'] == -32602 and 'code.no.such' in nowhere['error']['message']
    assert unaddressed['result']['task']['status']['state'] == 'TASK_STATE_INPUT_REQUIRED'  # asked for an Address
    stored = Store('proj').ticket(task['id']).work
    assert stored.address == 'code.alarm.audible' and 'peer/1' in (stored.note or '')  # who sent it, on the ticket
    assert working['result']['status']['state'] == 'TASK_STATE_WORKING'
    assert '0 of 2 steps done' in working['result']['status']['message']['parts'][0]['text']
    assert done['status']['state'] == 'TASK_STATE_COMPLETED'
    assert done['artifacts'][0]['parts'][0]['text'] == 'Louder now'
    assert done['artifacts'][0]['metadata'] == {'why': 'The cook hears it'}
    assert cancel['error']['code'] == -32002  # TaskNotCancelableError: a done ticket cannot be cancelled


@pytest.mark.req('MCP-002')
def test_a2a_push_webhooks_are_only_those_the_person_allows(run, home, mapped):
    from metaform.modules.mcp.a2a import allowed
    run('set', '--mcp-a2a-webhooks', 'https://agent.example/hooks/', cwd=mapped)
    assert allowed('https://agent.example/hooks/a2a', mapped)
    assert allowed('https://AGENT.example/hooks/', mapped)
    assert not allowed('https://agent.example.evil/hooks/a2a', mapped)  # compared parsed, never as a prefix
    assert not allowed('https://agent.example:8443/hooks/a2a', mapped)
    assert not allowed('http://agent.example/hooks/a2a', mapped)
    assert not allowed('https://agent.example/hooksmith', mapped)
    assert not allowed('file:///etc/passwd', mapped)


@pytest.mark.req('MCP-002')
def test_a2a_push_resume_sends_where_an_ended_task_stands_and_drops_its_configuration(run, home, mapped, monkeypatch):
    """A task that ended while the server was down was never pushed, and its configuration was kept for ever. A task
    whose ticket is gone is told as failed; a watched task that ends while the server runs drops its configuration."""
    import anyio
    import httpx
    from starlette.applications import Starlette

    from metaform.modules.mcp import a2a as served
    from metaform.modules.mcp import a2a_records as records
    run('set', '--mcp-a2a-webhooks', 'https://agent.example/hooks/', cwd=mapped)
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'task=Make it louder.', 'title=Louder', cwd=mapped)
    work_id = next(one.id for one in Store('proj').work(limit=0).results if one.task == 'Make it louder.')
    records.record('proj', work_id, 'm-1', 'code.alarm.audible', None)
    records.set_push('proj', records.Push(work_id, 'c-1', 'https://agent.example/hooks/a2a', None, None, None, None))
    run('map', 'work', 'op=take', f'id={work_id}', cwd=mapped)
    run('map', 'work', 'op=done', f'id={work_id}', 'resolution=Louder now', 'why=The cook hears it', cwd=mapped)
    records.record('proj', 'w-gone', 'm-2', 'code.alarm.audible', None)  # its ticket no longer exists
    records.set_push('proj', records.Push('w-gone', 'c-2', 'https://agent.example/hooks/a2a', None, None, None, None))
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'task=Make it flash.', 'title=Flash', cwd=mapped)
    watched = next(one.id for one in Store('proj').work(limit=0).results if one.task == 'Make it flash.')
    records.record('proj', watched, 'm-3', 'code.alarm.audible', None)
    records.set_push('proj', records.Push(watched, 'c-3', 'https://agent.example/hooks/a2a', None, None, None, None))
    posted = []

    async def post(self, url, json=None, headers=None):
        posted.append(json)
        return httpx.Response(200, request=httpx.Request('POST', url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    app = Starlette()
    served.attach(app, mapped, 7434)

    async def go():
        async with app.router.lifespan_context(app):
            # done from another process, as a person or agent does it, heard through the home's change relay
            await anyio.to_thread.run_sync(lambda: run('map', 'work', 'op=done', f'id={watched}', 'resolution=Flashing',
                                                       'why=The cook sees it', cwd=mapped, isolated=True))
            with anyio.fail_after(15):
                while records.pushes('proj', watched):
                    await anyio.sleep(0.05)
    asyncio.run(go())

    def told(task_id):
        return [one['statusUpdate']['status']['state'] for one in posted
                if one.get('statusUpdate', {}).get('taskId') == task_id]
    assert [one['artifactUpdate']['artifact']['parts'][0]['text'] for one in posted
            if one.get('artifactUpdate', {}).get('taskId') == work_id] == ['Louder now']
    assert told(work_id) == ['TASK_STATE_COMPLETED']
    assert records.pushes('proj', work_id) == []
    assert told('w-gone') == ['TASK_STATE_FAILED'] and records.pushes('proj', 'w-gone') == []
    assert told(watched)[-1] == 'TASK_STATE_COMPLETED' and records.pushes('proj', watched) == []


def july_wire(home, folder, **extra_env):
    """A client on the 2026-07-28 wire, whose requests declare the capabilities a check gives them."""
    from metaform.probe import Session
    return Session([sys.executable, '-m', 'metaform', 'mcp', 'serve'], cwd=folder,
                   env={**os.environ, 'METAFORM_HOME': str(home), **extra_env})


def declaring(wire, method, params, capabilities, limit=30):
    """One request declaring `capabilities` in its `_meta`, as a July client sends them on every request."""
    return wire.request(method, {**params, '_meta': {'io.modelcontextprotocol/clientCapabilities': capabilities}},
                        deadline=time.monotonic() + limit)


FORMS = {'elicitation': {'form': {}}}


@pytest.mark.req('MCP-031')
def test_enabled_modules_rules_close_the_glossary_and_a_rule_without_its_why_stops_its_module(run, home, mapped,
                                                                                               user_module,
                                                                                               module_row):
    """`<rules>` in a module's prompts.xml: each rule of each enabled module is one line after the tool index in
    metaform://tools, prefixed with its module; a rule without a why is refused as any faulty declaration is."""
    from metaform import prompt_files
    from metaform.modules.mcp.server import tools_text as glossary
    run('enable', 'memory')
    served = glossary(mapped)
    rules = served[served.index(prompt_files.module('mcp', 'rules_heading')):]
    assert served.index(prompt_files.module('mcp', 'tool_index')) < served.index(rules)
    assert '\n[memory] Record each memory at the RE whose goal it serves, never at a PE that provides for it. ' \
           'Why: The Join rule attaches all knowledge to the RE' in rules
    folder = user_module('ruled', '''
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        MODULE = Module(id='ruled', summary='Rules.', purpose='Shows a rule.')
    ''')
    (folder / 'resources').mkdir()
    (folder / 'resources' / 'prompts.xml').write_text('<prompts><rules><rule>No reason given.</rule></rules></prompts>')
    run('enable', 'ruled', ok=False)
    assert 'has no why' in ' '.join(module_row('ruled', cwd=mapped))
    run('disable', 'memory')
    assert '[memory]' not in glossary(mapped)


@pytest.mark.req('MCP-006')
@pytest.mark.req('CLI-011')
def test_a_caution_and_a_person_only_change_are_asked_of_the_person_by_form_on_the_july_wire(run, home, mapped):
    """Where the client shows forms, a caution tool answers input_required with the form; the retry with the
    person's yes and the sealed state runs it, the same answer again is asked anew, a no refuses with a next step, and
    other arguments are refused by the state's binding. A person-only setting asked for is set to what the person
    gave. Without forms, and for a dispatched agent, the plain rules stand."""
    run('enable', 'hello')
    wire = july_wire(home, mapped)
    try:
        asked = declaring(wire, 'tools/call', {'name': 'hello_forget', 'arguments': {}}, FORMS)
        form = asked['inputRequests']['consent']
        assert asked['resultType'] == 'input_required' and form['method'] == 'elicitation/create'
        assert 'hello_forget' in form['params']['message'] and form['params']['requestedSchema']['required'] == ['go']
        yes = {'consent': {'action': 'accept', 'content': {'go': True}}}
        ran = declaring(wire, 'tools/call', {'name': 'hello_forget', 'arguments': {}, 'inputResponses': yes,
                                             'requestState': asked['requestState']}, FORMS)
        assert ran['isError'] is False and 'deleted' in ran['content'][0]['text']
        again = declaring(wire, 'tools/call', {'name': 'hello_forget', 'arguments': {}, 'inputResponses': yes,
                                               'requestState': asked['requestState']}, FORMS)
        assert again['resultType'] == 'input_required'  # an answer counts once
        no = declaring(wire, 'tools/call', {'name': 'hello_forget', 'arguments': {}, 'requestState': again['requestState'],
                                            'inputResponses': {'consent': {'action': 'decline'}}}, FORMS)
        assert no['isError'] is True and 'declined' in no['content'][0]['text']
        with pytest.raises(RuntimeError, match='-32602'):
            declaring(wire, 'tools/call', {'name': 'hello_forget', 'arguments': {'confirm': False}, 'inputResponses': yes,
                                           'requestState': no.get('requestState') or again['requestState']}, FORMS)
        plain = declaring(wire, 'tools/call', {'name': 'hello_forget', 'arguments': {}}, {})
        assert plain['isError'] is True and 'with confirm true' in plain['content'][0]['text']
        setting = declaring(wire, 'tools/call', {'name': 'metaform_set',
                                                 'arguments': {'roles_without_authority': ['worker']}}, FORMS)
        field = setting['inputRequests']['consent']['params']['requestedSchema']['properties']['roles_without_authority']
        assert field['default'] == 'worker' and field['description'].startswith('The roles of the agents')
        made = declaring(wire, 'tools/call', {
            'name': 'metaform_set', 'arguments': {'roles_without_authority': ['worker']},
            'requestState': setting['requestState'],
            'inputResponses': {'consent': {'action': 'accept', 'content': {'roles_without_authority': 'worker, sentinel'}}}},
            FORMS)
        assert made['structuredContent']['updated'][0]['new'] == ['worker', 'sentinel']
    finally:
        wire.close()
    dispatched = july_wire(home, mapped, METAFORM_ROLE='worker')
    try:
        refused = declaring(dispatched, 'tools/call', {'name': 'hello_forget', 'arguments': {}}, FORMS)
        assert refused['isError'] is True and 'with confirm true' in refused['content'][0]['text']
    finally:
        dispatched.close()


@pytest.mark.req('MCP-006')
def test_on_the_2025_handshake_the_person_answers_the_form_while_the_call_waits(run, home, mapped):
    """A client that connected with initialize and declares elicitation gets elicitation/create while the call
    waits; the person's yes runs the caution tool, a no leaves it undone."""
    run('enable', 'hello')
    from mcp import types
    answers = iter(['accept', 'decline'])

    async def elicit(context, params):
        action = next(answers)
        return types.ElicitResult(action=action, content={'go': True} if action == 'accept' else None)

    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'],
                                   cwd=str(mapped), env={**os.environ, 'METAFORM_HOME': str(home)})

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write,
                                                                        elicitation_callback=elicit) as client:
            await client.initialize()
            return (await called(client, 'hello_forget', {}), await called(client, 'hello_forget', {}))
    accepted, declined = asyncio.run(go())
    assert accepted.is_error is False and 'deleted' in text(accepted)[0]
    assert declined.is_error is True and 'declined' in text(declined)[0]


@pytest.mark.req('BASE-030')
def test_a_long_verb_and_a_workflow_run_are_tasks_for_a_client_that_declares_the_extension(run, home, mapped,
                                                                                            user_module):
    """hello_wait, declared task=True, answers a client that declares the tasks extension with a task at once:
    tasks/get gives it working, then completed with the tool's result; tasks/cancel stops one, and a verb run in a
    thread, which cannot be stopped, completes with its result after a cancel. The task is kept in the project, so a
    server started after the one that ran it still answers for it, failed when its owner stopped. A verb declared
    task='run' answers with its run as the task; a run paused on the person asks its question under a key of that one
    pause, answered through tasks/update, and a second pause with the same question asks under a new key.
    workflow_assign, whose run id the calling agent acts on, is never a task. An unknown task is -32602; a client that
    does not declare the extension is refused -32021 and gets the result as before."""
    from metaform.modules.mcp import task_records
    from metaform.modules.workflow import executor
    user_module('driven', '''
        import time
        from metaform.data import Store
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')

        def follow(ctx):  # stands for a run the server advances by itself, as an agent dispatch steers
            from metaform.modules.workflow import runs  # loaded by then, as the workflow module
            store = Store(ctx.require_store().project_id, module='workflow')
            return {'run': runs.start(store, 'assign', {'assignment': {'skill': 'scan', 'input': None}})}

        def slow(ctx):
            time.sleep(2)
            return {'slept': True}

        MODULE = Module(id='driven', summary='Runs as tasks.', purpose='Shows task=run.', verbs=(
            Verb('follow', follow, 'Start a run the server advances.', task='run'),
            Verb('slow', slow, 'Sleep two seconds in a thread.', effect='read', task=True)))
    ''')
    run('enable', 'hello')
    run('enable', 'workflow')
    run('enable', 'driven')
    tasks = {'extensions': {'io.modelcontextprotocol/tasks': {}}}
    wire = july_wire(home, mapped)
    try:
        assert 'io.modelcontextprotocol/tasks' in declaring(wire, 'server/discover', {}, {})['capabilities']['extensions']
        made = declaring(wire, 'tools/call', {'name': 'hello_wait', 'arguments': {'seconds': 1}}, tasks)
        assert made['resultType'] == 'task' and made['status'] == 'working' and made['pollIntervalMs'] == 1000
        assert made['ttlMs'] == task_records.TTL_MS
        assert declaring(wire, 'tasks/get', {'taskId': made['taskId']}, tasks)['status'] == 'working'
        deadline = time.monotonic() + 20
        while (done := declaring(wire, 'tasks/get', {'taskId': made['taskId']}, tasks))['status'] == 'working':
            assert time.monotonic() < deadline
            time.sleep(0.2)
        assert done['status'] == 'completed' and done['result']['content'][0]['text'] == 'waited 1 s\n'
        def settled(task_id):
            deadline = time.monotonic() + 20
            while (got := declaring(wire, 'tasks/get', {'taskId': task_id}, tasks))['status'] == 'working':
                assert time.monotonic() < deadline
                time.sleep(0.1)
            return got
        long = declaring(wire, 'tools/call', {'name': 'hello_wait', 'arguments': {'seconds': 60}}, tasks)
        assert declaring(wire, 'tasks/cancel', {'taskId': long['taskId']}, tasks)['resultType'] == 'complete'
        assert settled(long['taskId'])['status'] == 'cancelled'  # an async verb stops at its await
        slow = declaring(wire, 'tools/call', {'name': 'driven_slow', 'arguments': {}}, tasks)
        declaring(wire, 'tasks/cancel', {'taskId': slow['taskId']}, tasks)
        finished = settled(slow['taskId'])  # a thread runs to its end: its effect landed, so its result is kept
        assert finished['status'] == 'completed' and finished['result']['structuredContent'] == {'slept': True}
        stranded = declaring(wire, 'tools/call', {'name': 'hello_wait', 'arguments': {'seconds': 60}}, tasks)

        assigned = declaring(wire, 'tools/call', {'name': 'driven_follow', 'arguments': {}}, tasks)
        assert assigned['resultType'] == 'task' and assigned['status'] == 'working' and assigned['ttlMs'] is None
        word = assigned['taskId']
        workflow = Store('proj', module='workflow')
        executor.pause(workflow, word, 'Which folder should the scan read?')
        asked = declaring(wire, 'tasks/get', {'taskId': word}, tasks)
        assert asked['status'] == 'input_required'
        (first,) = asked['inputRequests']
        assert declaring(wire, 'tasks/update', {'taskId': word, 'inputResponses': {first: {
            'action': 'accept', 'content': {'answer': 'src/'}}}}, tasks)['resultType'] == 'complete'
        assert declaring(wire, 'tasks/get', {'taskId': word}, tasks)['status'] == 'working'
        executor.working(workflow, word)
        executor.pause(workflow, word, 'Which folder should the scan read?')
        (second,) = declaring(wire, 'tasks/get', {'taskId': word}, tasks)['inputRequests']
        assert second != first  # the same question, asked again, under a key of its own
        declaring(wire, 'tasks/update', {'taskId': word, 'inputResponses': {first: {
            'action': 'accept', 'content': {'answer': 'stale'}}}}, tasks)  # a spent key is ignored
        assert declaring(wire, 'tasks/get', {'taskId': word}, tasks)['status'] == 'input_required'
        declaring(wire, 'tasks/cancel', {'taskId': word}, tasks)
        cancelled = declaring(wire, 'tasks/get', {'taskId': word}, tasks)
        assert cancelled['status'] == 'cancelled' and cancelled['statusMessage'] == 'Cancelled through tasks/cancel.'
        plain_assign = declaring(wire, 'tools/call', {'name': 'workflow_assign', 'arguments': {'skill': 'scan'}}, tasks)
        assert plain_assign['resultType'] == 'complete' and 'resume run=' in plain_assign['structuredContent']['read']

        with pytest.raises(RuntimeError, match='-32602'):
            declaring(wire, 'tasks/get', {'taskId': 'no-such-task'}, tasks)
        with pytest.raises(RuntimeError, match='-32021'):
            declaring(wire, 'tasks/get', {'taskId': made['taskId']}, {})
        plain = declaring(wire, 'tools/call', {'name': 'hello_wait', 'arguments': {'seconds': 0}}, {})
        assert plain['resultType'] == 'complete' and plain['content'][0]['text'] == 'waited 0 s\n'
    finally:
        wire.process.kill()  # stopped with no chance to mark what it ran, as a crash or a lost machine stops it
        wire.close()
    # The server that ran the stranded call has stopped: a new one finds the task, and, its owner's process gone,
    # reads it as failed at once rather than leaving the client to wait.
    wire = july_wire(home, mapped)
    try:
        assert declaring(wire, 'tasks/get', {'taskId': made['taskId']}, tasks)['status'] == 'completed'
        lost = declaring(wire, 'tasks/get', {'taskId': stranded['taskId']}, tasks)
        assert lost['status'] == 'failed' and lost['error']['message'] == task_records.STOPPED
    finally:
        wire.close()


# Changes that concern no task, no followed ticket t1 and no exchange of the project 'proj': another project's, an
# agent's thread lines and signals, another ticket's, its sessions'.
UNRELATED = (
    {'project': 'other', 'tables': ['work', 'mcp.tool_tasks'], 'work_ids': ['t1'], 'kinds': ['task']},
    {'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines'], 'work_ids': ['t2'],
     'session_ids': ['s2'], 'kinds': ['line']},
    {'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.signals'], 'work_ids': ['t2'],
     'session_ids': ['s2'], 'kinds': ['signal']},
    {'project': 'proj', 'tables': ['work', 'work_steps'], 'work_ids': ['t2'], 'session_ids': [], 'kinds': ['ticket']},
    {'project': 'proj', 'tables': ['dispatch.sessions'], 'work_ids': ['t2'], 'session_ids': ['s2'], 'kinds': ['session']},
)


@pytest.mark.req('BASE-030')
def test_a_task_hears_a_cancel_from_another_process_and_reads_nothing_for_changes_that_name_no_task(monkeypatch):
    """The owner of a running task reads its own task rows only on a change naming the tool tasks, CLAUDE.md
    Architecture section 2: a burst of changes that do not costs no read, and nothing wakes on a clock."""
    import anyio
    import anyio.lowlevel

    from metaform.modules.mcp import task_records, tasks
    reads: list[list[str]] = []
    monkeypatch.setattr(task_records, 'ended', lambda project, running: reads.append(list(running)) or list(running))

    async def main() -> bool:
        scope = anyio.CancelScope()
        running = tasks.Running(scopes={'t1': scope}, project='proj', token=anyio.lowlevel.current_token())

        def burst() -> None:  # on another thread, as the listener hears them
            for _ in range(20):
                for payload in UNRELATED:
                    tasks.heard(running, payload)
        await anyio.to_thread.run_sync(burst)
        assert reads == []
        await anyio.to_thread.run_sync(tasks.heard, running, {'project': 'proj', 'tables': ['mcp.tool_tasks'],
                                                              'work_ids': [], 'session_ids': [], 'kinds': ['task']})
        return scope.cancel_called
    assert anyio.run(main) is True
    assert reads == [['t1']]


@pytest.mark.req('MCP-004')
def test_the_resource_watcher_reads_nothing_for_changes_that_number_nothing_at_its_nodes(mapped):
    """A watched node is read again only for a change that can number an item there; a burst of changes of another
    project, of an agent's threads and signals, or of the mcp module's records reads nothing."""
    import anyio

    from metaform.module import project_for
    from metaform.modules.mcp import server
    project = project_for(mapped)
    reads: list[str] = []

    class Bus:
        async def publish(self, message):
            pass

    async def main() -> None:
        watch = server.Watch(mapped, Bus(), lambda **given: given)
        await watch.open(['metaform://code.alarm.audible', 'metaform://code.loop.tick'])
        number, check, checked = watch._number, watch.check, anyio.Event()
        watch._number = lambda uri: reads.append(uri) or number(uri)

        async def counted() -> None:
            await check()
            checked.set()
        watch.check = counted
        async with anyio.create_task_group() as group:
            watch.group = group

            def burst() -> None:  # on another thread, as the listener hears them; a ticket's change can number one
                for _ in range(20):
                    for payload in UNRELATED[:3] + UNRELATED[4:]:
                        watch._heard({**payload, 'project': project if payload['project'] == 'proj' else 'other'})
                    watch._heard({'project': project, 'tables': ['mcp.tool_tasks', 'mcp.a2a_exchanges']})
            await anyio.to_thread.run_sync(burst)
            await anyio.wait_all_tasks_blocked()
            assert reads == []
            await anyio.to_thread.run_sync(watch._heard, {'project': project, 'tables': ['memory.entities']})
            with anyio.fail_after(10):
                await checked.wait()
            watch.stop()
    anyio.run(main)
    assert sorted(reads) == ['metaform://code.alarm.audible', 'metaform://code.loop.tick']


@pytest.mark.req('MCP-043')
def test_a_followed_a2a_task_and_the_exchange_followers_read_only_for_changes_that_concern_them(monkeypatch, tmp_path):
    """An A2A task followed for its client is read again only for a change naming its ticket, and the exchange
    followers read open exchanges only for a change to the exchanges; a burst of other changes reads nothing, and
    nothing is read on a clock."""
    import threading

    import anyio
    from a2a.types import Task

    from metaform.modules.mcp import a2a, a2a_out
    monkeypatch.setattr(a2a, 'refresh_modules', lambda: None)
    first = a2a.Read(Task(id='t1', context_id='code.alarm'), 'running', '')
    first.work_id = 't1'
    tasks_read: list[str] = []
    exchanges_read: list[set[str] | None] = []
    task_was_read, exchanges_were_read = threading.Semaphore(0), threading.Semaphore(0)

    def read(project, folder, task_id, length=None):
        tasks_read.append(task_id)
        task_was_read.release()
        return first

    def open_exchanges(projects=None):
        exchanges_read.append(projects)
        exchanges_were_read.release()
        return []
    monkeypatch.setattr(a2a, 'read', read)
    monkeypatch.setattr(a2a_out, '_open_exchanges', open_exchanges)

    async def reads() -> None:  # one more of each, signalled by the reads themselves
        for signal in (task_was_read, exchanges_were_read):
            assert await anyio.to_thread.run_sync(signal.acquire, True, 10)

    async def main() -> None:
        changes, wakes = a2a.Changes(), a2a_out.Wakes()
        changes.bind()
        followers = a2a_out.Followers(tmp_path, wakes)

        async def follow() -> None:
            async for _ in a2a.follow(changes, 'proj', tmp_path, first):
                pass
        async with anyio.create_task_group() as group:
            group.start_soon(follow)
            group.start_soon(followers.run)
            await reads()  # the reads at the start
            await anyio.wait_all_tasks_blocked()
            for _ in range(20):
                for payload in UNRELATED:
                    changes.heard(payload)
                    wakes.heard(payload)
            await anyio.wait_all_tasks_blocked()
            assert (len(tasks_read), len(exchanges_read)) == (1, 1)
            changes.heard({'project': 'proj', 'tables': ['work'], 'work_ids': ['t1'], 'kinds': ['ticket']})
            wakes.heard({'project': 'proj', 'tables': ['mcp.a2a_exchanges']})
            await reads()
            await anyio.wait_all_tasks_blocked()
            group.cancel_scope.cancel()
    anyio.run(main)
    assert tasks_read == ['t1', 't1'] and exchanges_read[1:] == [{'proj'}]


@pytest.mark.req('MCP-037')
def test_a_trace_views_mark_moves_only_for_a_change_to_its_ticket():
    """A trace view's next read reads the store only after a change to its ticket: a burst of changes that do not
    concern the ticket leaves its mark as it was, so the read is answered unchanged without reading; a change that
    does moves it."""
    import anyio

    from metaform.modules.mcp import views

    async def main() -> None:
        traces = views.Traces()
        mark = traces.track('proj', 't1')
        for _ in range(20):
            for payload in UNRELATED:
                traces.heard(payload)
        assert traces.mark('proj', 't1') == mark
        traces.heard({'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines'],
                      'work_ids': ['t1'], 'session_ids': ['s1'], 'kinds': ['line']})
        assert traces.mark('proj', 't1') != mark
        traces.stop()
    anyio.run(main)


@pytest.mark.req('MCP-037')
def test_addresses_and_item_numbers_complete_and_a_listener_hears_items_added_at_its_node(run, home, mapped):
    """completion/complete fills an Address a segment at a time and the numbers at an address; a client listening on
    metaform://<address> is told when an item is numbered there by another process, the URI and nothing more."""
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'finding', 'why': 'The cook misses it.',
                                                   'observations': ['The tone is too quiet.']}]),
        'node=code.alarm.audible', cwd=mapped)
    wire = july_wire(home, mapped)
    try:
        def complete(uri, name, value, known=None):
            return declaring(wire, 'completion/complete', {
                'ref': {'type': 'ref/resource', 'uri': uri}, 'argument': {'name': name, 'value': value},
                **({'context': {'arguments': known}} if known else {})}, {})['completion']['values']
        assert complete('metaform://{address}', 'address', '') == ['code']
        assert complete('metaform://{address}', 'address', 'code.a') == ['code.alarm']
        assert complete('metaform://{address}', 'address', 'code.alarm') == ['code.alarm', 'code.alarm.audible']
        assert complete('metaform://{address}#{n}', 'n', '', {'address': 'code.alarm.audible'}) == ['1']
        assert complete('metaform://{address}/items/{n}', 'n', '', {'address': 'code.alarm.audible'}) == ['1']
        listening = wire.open('subscriptions/listen', {'notifications': {
            'resourceSubscriptions': ['metaform://code.alarm.audible']}})
        declaring(wire, 'resources/templates/list', {}, {})  # the stream is open once a later request is answered
        run('memory', 'create_entities', json.dumps([{'name': 'piezo', 'entityType': 'part', 'why': 'Rated 3 V.',
                                                       'observations': ['Fed 5 V.']}]), 'node=code.alarm.audible',
            cwd=mapped)

        def heard():
            return [notice['params'] for notice in wire.notices if notice['method'] == 'notifications/resources/updated']
        deadline = time.monotonic() + 15
        while not heard() and time.monotonic() < deadline:
            declaring(wire, 'resources/templates/list', {}, {})
            time.sleep(0.2)
        (notice,) = heard()
        assert notice['uri'] == 'metaform://code.alarm.audible'
        assert notice['_meta'] == {'io.modelcontextprotocol/subscriptionId': listening}
    finally:
        wire.close()


@pytest.mark.req('MCP-037')
def test_map_views_are_offered_only_to_a_client_that_renders_mcp_apps(run, home, mapped, monkeypatch, tmp_path):
    """A client declaring MCP Apps sees map_where and map_item linked to their views and the views' own tool, marked
    app only; it reads the views as mcp-app HTML, and the views read through that tool. Any other client sees the
    tools as they always were, with no view and no views' tool."""
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'finding', 'why': 'The cook misses it.',
                                                   'observations': ['The tone is too quiet.']}]),
        'node=code.alarm.audible', cwd=mapped)
    apps = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}
    wire = july_wire(home, mapped)
    try:
        shown = {tool['name']: tool for tool in declaring(wire, 'tools/list', {}, apps)['tools']}
        assert shown['map_where']['_meta'] == {'ui': {'resourceUri': 'ui://metaform/map'}}
        assert shown['map_item']['_meta'] == {'ui': {'resourceUri': 'ui://metaform/node'}}
        assert shown['metaform_view']['_meta'] == {'ui': {'visibility': ['app']}}
        assert list(shown) == sorted(shown)
        plain = {tool['name']: tool for tool in declaring(wire, 'tools/list', {}, {})['tools']}
        assert 'metaform_view' not in plain and '_meta' not in plain['map_where']
        assert 'io.modelcontextprotocol/ui' in declaring(wire, 'server/discover', {}, {})['capabilities']['extensions']
        node = declaring(wire, 'resources/read', {'uri': 'ui://metaform/node'}, apps)['contents'][0]
        assert node['mimeType'] == 'text/html;profile=mcp-app' and 'window.MetaformView' in node['text']
        assert 'window.McpApps' in node['text'] and '"themed": true' in node['text']  # the official SDK, inline
        assert '"tool": "metaform_view"' in node['text'] and '--signal' in node['text']  # the page's own tokens
        read = declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {
            'read': 'items', 'params': {'address': 'code.alarm.audible'}}}, apps)
        assert [block['text'] for block in read['content']] == ['Read items for the Metaform view.']  # data once
        items = read['structuredContent']
        assert [(one['item'], one['title'], one['why']) for one in items['items']] == [
            ('code.alarm.audible#1', 'The tone is too quiet.', 'The cook misses it.')]
        graph = declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {
            'read': 'graph', 'params': {'project': 'proj', 'limit': 500}}}, apps)['structuredContent']
        assert {entry['element']['address'] for entry in graph['elements']} >= {'code.timer.kitchen',
                                                                                'code.alarm.audible'}
        refused = declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {
            'read': 'graph', 'params': {'project': 'other'}}}, apps)
        assert refused['isError'] is True
    finally:
        wire.close()
    # The built map view is served only while the files it records still hash as it records them; CI builds it.
    from metaform.modules.mcp import views
    if os.environ.get('METAFORM_BUILD_VIEWS') == '1':
        assert views.built()
    page = 'web/page/theme.js'
    held = (tmp_path / 'views')
    held.mkdir()
    monkeypatch.setattr(views, '_views', lambda: held)
    source = views.resources.files('metaform.modules').joinpath(*page.split('/')).read_bytes()
    for digest, served in ((views.hashlib.sha256(page.encode() + b'\0' + source + b'\0').hexdigest(), True),
                           ('0' * 64, False)):
        (held / views.BUILT).write_text('<script type="application/json" id="metaform-view-inputs">'
                                        + json.dumps({'sha256': digest, 'files': [page]}) + '</script>')
        views._checked.clear()
        assert views.built() is served


@pytest.fixture
def chromium():
    """Headless Chromium through Playwright, a dev dependency, for the views in a frame."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        launched = driver.chromium.launch()
        yield launched
        launched.close()


# A host page as the MCP Apps specification describes one, written for this check: the view in a sandboxed frame
# under the specification's restrictive default content policy, the view's requests checked against the official
# SDK's own schemas, its tool calls carried to the real server, and a light conversation with style variables.
HOST = '''<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">
<iframe id="frame" sandbox="allow-scripts" style="width:900px;height:700px;border:0"></iframe>
<script>SDK</script>
<script>
window.told = []; window.refused = []; window.initialized = false;
const frame = document.getElementById('frame');
const send = message => frame.contentWindow.postMessage({jsonrpc: '2.0', ...message}, '*');
window.open_view = (html, args, result) => {
  const policy = "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data:; media-src 'self' data:; connect-src 'none'";
  addEventListener('message', async event => {
    if (event.source !== frame.contentWindow) return;
    const m = event.data;
    if (m.method === 'ui/initialize') {
      const checked = McpApps.McpUiInitializeRequestSchema.safeParse({method: m.method, params: m.params});
      if (!checked.success) window.refused.push(JSON.stringify(checked.error.issues));
      window.initialize = m.params;
      return send({id: m.id, result: {protocolVersion: '2026-01-26', hostInfo: {name: 'check-host', version: '1'},
        hostCapabilities: {serverTools: {}, updateModelContext: {text: {}}},
        hostContext: {theme: 'light', displayMode: 'inline',
                      styles: {variables: {'--color-background-primary': 'rgb(250, 250, 250)'}}}}});
    }
    if (m.method === 'ui/notifications/initialized') {
      window.initialized = true;
      send({method: 'ui/notifications/tool-input', params: {arguments: args}});
      return send({method: 'ui/notifications/tool-result', params: result});
    }
    if (m.method === 'ui/update-model-context') {
      const checked = McpApps.McpUiUpdateModelContextRequestSchema.safeParse({method: m.method, params: m.params});
      if (!checked.success) window.refused.push(JSON.stringify(checked.error.issues));
      window.told.push(m.params.content[0].text);
      return send({id: m.id, result: {}});
    }
    if (m.method === 'tools/call') return send({id: m.id, result: JSON.parse(await window.rpc(JSON.stringify(m.params)))});
    if (m.id !== undefined && m.method !== undefined) send({id: m.id, error: {code: -32601, message: 'not here'}});
  });
  frame.srcdoc = html.replace('<head>', `<head><meta http-equiv="Content-Security-Policy" content="${policy}">`);
};
</script></body></html>'''


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_node_view_connects_through_the_official_sdk_and_tells_the_agent_what_the_person_selects(
        run, home, mapped, chromium):
    """The node view, served to a client that renders MCP Apps, makes the handshake the specification asks for, as
    the official SDK's own schema checks it (appInfo, appCapabilities, protocolVersion), only then hears the call's
    input and result, paints the result it was handed, reads the rest through metaform_view, wears the host's light
    theme and style variables, and tells the agent in one line which item the person selected."""
    from metaform import prompt_files
    from metaform.modules.mcp import views
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'finding', 'why': 'The cook misses it.',
                                                   'observations': ['The tone is too quiet.']}]),
        'node=code.alarm.audible', cwd=mapped)
    apps = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/node'}, apps)['contents'][0]['text']
        args = {'item': 'code.alarm.audible#1'}
        result = declaring(wire, 'tools/call', {'name': 'map_item', 'arguments': args}, apps)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page()
        page.set_default_timeout(10_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), apps)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>'))
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        assert page.evaluate('window.refused') == []
        assert page.evaluate('window.initialize.appInfo')['name'] == 'metaform-node'
        view = page.frame_locator('#frame')
        view.locator('.row').first.wait_for()
        assert 'The tone is too quiet.' in view.locator('#item').inner_text()  # the call's own result, painted first
        assert view.locator('#reliedOnList').inner_text().startswith('code.timer.kitchen')
        root = view.locator('html')
        assert root.get_attribute('data-theme') == 'light'
        assert root.evaluate('el => getComputedStyle(document.body).backgroundColor') == 'rgb(250, 250, 250)'
        assert page.evaluate('window.told') == []  # nothing is told until the person selects
        view.locator('.row').first.click()
        page.wait_for_function('window.told.length === 1')
        line = prompt_files.module('mcp', 'view_selected', address='code.alarm.audible#1')
        assert page.evaluate('window.told') == [line] and page.evaluate('window.refused') == []
    finally:
        wire.close()


@pytest.mark.req('MCP-002')
def test_an_a2a_message_naming_no_address_is_asked_for_one_and_a_refused_webhook_opens_nothing(run, home, mapped):
    run('set', '--mcp-a2a-webhooks', 'https://agent.example/hooks/', cwd=mapped)
    asking = {'messageId': 'q-1', 'role': 'ROLE_USER', 'parts': [{'text': 'The alarm is too quiet for the cook'}]}

    async def calls(client, token):
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}'}

        async def send(message, **configuration):
            params = {'message': message, 'configuration': {'returnImmediately': True, **configuration}}
            return (await client.post('/a2a', json=rpc('SendMessage', params), headers=headers)).json()
        asked = (await send(asking))['result']['task']
        reply = {'messageId': 'r-1', 'role': 'ROLE_USER', 'taskId': asked['id'], 'contextId': asked['contextId'],
                 'parts': [{'text': 'code.alarm.audible'}]}
        elsewhere = await send({**reply, 'contextId': 'a2a-other'})
        nowhere = await send({**reply, 'parts': [{'text': 'code.no.such'}]})
        opened = await send(reply)
        again = await send(reply)
        hooked = await send({'messageId': 'p-1', 'role': 'ROLE_USER', 'contextId': 'code.alarm.audible',
                             'parts': [{'text': 'Another'}]},
                            taskPushNotificationConfig={'url': 'https://agent.example.evil/hooks/x'})
        unkind = await send({'messageId': 'k-1', 'role': 'ROLE_USER', 'contextId': 'code.alarm.audible',
                             'parts': [{'text': 'Another'}], 'metadata': {
                                 'https://metaform.ing/a2a/address-context/v1': {'kind': 'urgent', 'agent': 'x'}}})
        withdrawn = (await send({**asking, 'messageId': 'q-2'}))['result']['task']
        cancelled = (await client.post('/a2a', json=rpc('CancelTask', {'id': withdrawn['id']}), headers=headers)).json()
        return asked, elsewhere, nowhere, opened, again, hooked, unkind, cancelled
    asked, elsewhere, nowhere, opened, again, hooked, unkind, cancelled = a2a(mapped, calls)
    assert asked['status']['state'] == 'TASK_STATE_INPUT_REQUIRED' and asked['contextId'].startswith('a2a-')
    offered = asked['metadata']['https://metaform.ing/a2a/address-context/v1']['candidates']
    assert offered[0] == 'code.alarm.audible' and 'code.alarm.audible' in asked['status']['message']['parts'][0]['text']
    assert elsewhere['error']['code'] == -32602 and asked['contextId'] in elsewhere['error']['message']
    assert nowhere['error']['code'] == -32602 and 'code.alarm.audible' in nowhere['error']['message']
    task = opened['result']['task']
    assert (task['id'], task['contextId']) == (asked['id'], asked['contextId'])  # the same task, now its ticket
    assert task['status']['state'] == 'TASK_STATE_SUBMITTED'
    assert task['metadata']['https://metaform.ing/a2a/address-context/v1']['item'] == 'code.alarm.audible#1'
    assert again['result']['task']['id'] == asked['id']  # a retried reply opens no second ticket
    tickets = [one for one in Store('proj').work(limit=0).results if (one.task or '').strip()]
    assert [one.task for one in tickets] == ['The alarm is too quiet for the cook']  # nothing from the refusals
    assert hooked['error']['code'] == -32602 and 'mcp_a2a_webhooks' in hooked['error']['message']
    assert unkind['error']['code'] == -32602 and 'enhancement' in unkind['error']['message']
    assert cancelled['result']['status']['state'] == 'TASK_STATE_CANCELED'


@pytest.mark.req('MCP-002')
def test_a2a_reaches_only_its_own_tickets_reads_a_cancel_as_canceled_and_a_wait_on_the_person_as_working(run, home,
                                                                                                         mapped):
    from metaform.modules.dispatch.signals import record
    from metaform.modules.workflow import runs
    run('enable', 'workflow')
    run('enable', 'dispatch')
    run('map', 'work', 'op=add', 'node=code.timer.kitchen', 'task=The person\'s own.', 'title=Mine', cwd=mapped)
    own = next(one.id for one in Store('proj').work(limit=0).results if one.task == "The person's own.")
    a_run = runs.start(Store('proj'), 'call', {})
    extension = 'https://metaform.ing/a2a/address-context/v1'

    async def calls(client, token):
        import anyio
        headers = {'A2A-Version': '1.0', 'Authorization': f'Bearer {token}'}

        async def send(text, number, **message):
            params = {'message': {'messageId': f'w-{number}', 'role': 'ROLE_USER', 'parts': [{'text': text}],
                                  **message}, 'configuration': {'returnImmediately': True}}
            return (await client.post('/a2a', json=rpc('SendMessage', params), headers=headers)).json()
        followed = (await send('Make it louder', 1, contextId='code.alarm.audible'))['result']['task']['id']
        waiting = (await send('Make it flash', 2, contextId='code.alarm.audible'))['result']['task']['id']
        streamed = {}

        async def subscribe():
            streamed['response'] = await client.post('/a2a', json=rpc('SubscribeToTask', {'id': followed}),
                                                     headers=headers)
        with anyio.fail_after(10):  # well inside the slow read: the stream wakes on the cancel's announcement
            async with anyio.create_task_group() as group:
                group.start_soon(subscribe)
                await anyio.sleep(0.5)
                cancel = (await client.post('/a2a', json=rpc('CancelTask', {'id': followed}), headers=headers)).json()
            asking = await client.post('/a2a', headers=headers, json=rpc('SendStreamingMessage', {'message': {
                'messageId': 'w-3', 'role': 'ROLE_USER', 'parts': [{'text': 'The alarm is too quiet'}]}}))
        listed = (await client.post('/a2a', json=rpc('ListTasks', {'status': 'TASK_STATE_CANCELED'}),
                                    headers=headers)).json()
        every = (await client.post('/a2a', json=rpc('ListTasks', {}), headers=headers)).json()
        record(Store('proj'), 'login-needed', work_id=waiting, key='login')
        login = (await client.post('/a2a', json=rpc('GetTask', {'id': waiting}), headers=headers)).json()
        theirs = [(await client.post('/a2a', json=rpc(method, {'id': one}), headers=headers)).json()
                  for method in ('GetTask', 'CancelTask') for one in (own, a_run)]
        # a ticket whose runner died holding it, one the person holds, and one taken with no session yet
        died, held, taken = [(await send(f'Make it {how}', number, contextId='code.alarm.audible'))['result']['task']['id']
                             for number, how in ((4, 'ring'), (5, 'buzz'), (6, 'chime'))]
        run('map', 'work', 'op=take', f'id={died}', cwd=mapped)
        with Store('proj', module='dispatch').tables() as tx:
            tx.insert('agent_sessions', {'session_id': 's-died', 'work_id': died, 'agent': 'claude', 'state': 'ended',
                                   'how': 'the runner is no longer running', 'started': '2026-10-11T00:00:00Z',
                                   'seq': 1})
        run('map', 'work', 'op=edit', f'id={held}', 'held=true', cwd=mapped)
        run('map', 'work', 'op=take', f'id={taken}', cwd=mapped)
        read = {one: (await client.post('/a2a', json=rpc('GetTask', {'id': one}), headers=headers)).json()['result']
                for one in (died, held, taken)}
        return streamed['response'].text, cancel, asking.text, listed, every, login, theirs, [read[died], read[held],
                                                                                              read[taken]]
    stream, cancel, asking, listed, every, login, theirs, (died, held, taken) = a2a(mapped, calls)
    told = [json.loads(line[5:])['result'] for line in stream.splitlines() if line.startswith('data:')]
    assert told[-1]['statusUpdate']['status']['state'] == 'TASK_STATE_CANCELED'  # and then the stream closed
    ended = cancel['result']
    assert ended['status']['state'] == 'TASK_STATE_CANCELED' and not ended.get('artifacts')  # never a resolution
    assert Store('proj').ticket(ended['id']).work.outcome == 'cancelled'
    asked = [json.loads(line[5:])['result'] for line in asking.splitlines() if line.startswith('data:')]
    assert [one['task']['status']['state'] for one in asked] == ['TASK_STATE_INPUT_REQUIRED']  # it closed there
    assert [one['id'] for one in listed['result']['tasks']] == [ended['id']]
    assert own not in {one['id'] for one in every['result']['tasks']} and a_run not in str(every)
    shown = login['result']
    assert shown['status']['state'] == 'TASK_STATE_WORKING'  # the client cannot log Metaform's agent in
    assert shown['metadata'][extension]['waitingOn'] == 'person' and shown['metadata'][extension]['reason'] == 'login'
    assert 'log it in' in shown['status']['message']['parts'][0]['text']
    assert [one['error']['code'] for one in theirs] == [-32001] * 4  # TaskNotFoundError: the person's, not A2A's
    assert Store('proj').ticket(own).work.done is None and runs.read(Store('proj'), a_run).state == 'running'
    # dispatch's own reason for the ticket, not one worked out again from its last session
    assert died['status']['state'] == 'TASK_STATE_WORKING'
    assert died['metadata'][extension]['reason'] == 'runner died' and died['metadata'][extension]['waitingOn'] == 'person'
    assert held['status']['state'] == 'TASK_STATE_SUBMITTED' and taken['status']['state'] == 'TASK_STATE_WORKING'
    assert 'waitingOn' not in held['metadata'][extension] and 'waitingOn' not in taken['metadata'][extension]
    from metaform.modules.dispatch import ticket_work_status
    from metaform.modules.mcp.a2a import ticket_state
    work = Store('proj').ticket(taken['id']).work
    idle = ticket_work_status(work, [{'session_id': 's-idle', 'state': 'running', 'activity': 'idle'}], [])
    assert ticket_state(work, {'dispatch': idle}, False) == ('running', None, 'a2a_working')  # idle between turns
    # dispatch's own status for a ticket it keeps nothing on yet: taken and starting, or held, wait on no one
    starting = ticket_work_status(work, [], [])
    assert starting == {'status': 'running', 'reason': 'starting'}
    assert ticket_state(work, {'dispatch': starting}, False) == ('running', None, 'a2a_working')
    kept = Store('proj').ticket(held['id']).work
    holding = ticket_work_status(kept, [], [])
    assert holding == {'status': 'submitted', 'reason': 'held'}
    assert ticket_state(kept, {'dispatch': holding}, False) == ('submitted', None, 'a2a_held')


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_map_view_in_an_ai_tool_draws_the_brief_and_its_items_as_the_web_gui_does(run, home, mapped, chromium):
    """The map view's Brief tab reads metaform_view's `brief`, the answer the web GUI's /api/brief gives, so it lists
    the items numbered at the node; the agent view and the Mermaid copy, which are the web GUI's, are not drawn."""
    from metaform.modules.mcp import views
    run('memory', 'create_entities', json.dumps([{'name': 'tone', 'entityType': 'finding', 'why': 'The cook misses it.',
                                                   'observations': ['The tone is too quiet.']}]),
        'node=code.alarm.audible', cwd=mapped)
    apps = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}
    # a view older than the page is not served and the node view, which has no Brief tab, stands in, `views.built`
    assert views.built(), 'the map view is older than the page: node scripts/build_map_view.mjs, as CI runs first'
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/map'}, apps)['contents'][0]['text']
        args = {'address': 'code.alarm.audible'}
        result = declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': args}, apps)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page(viewport={'width': 1280, 'height': 800})
        page.set_default_timeout(30_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), apps)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>')
                         .replace('width:900px;height:700px', 'width:1260px;height:760px'))
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        view = page.frame_locator('#frame')
        view.locator('#t-brief').click()
        row = view.locator('#p-brief ul.items .itemrow')
        row.first.wait_for()
        assert 'The tone is too quiet.' in row.first.inner_text() and 'The cook misses it.' in row.first.inner_text()
        assert view.locator('#p-brief .seeall').count() == 0 and view.locator('#p-brief .acts').count() == 0
        row.first.locator('.itemhead').click()                              # opened through metaform_view's item
        view.locator('#p-brief .itemopen pre.itemtext').wait_for()
        assert 'tone (finding)' in view.locator('#p-brief .itemopen pre.itemtext').inner_text()
        assert page.evaluate('window.refused') == []
    finally:
        wire.close()


APPS = {'extensions': {'io.modelcontextprotocol/ui': {'mimeTypes': ['text/html;profile=mcp-app']}}}


def seed_thread(work_id, lines, first=1):
    """A recorded agent thread for a ticket, written into dispatch's own tables as its runner writes them, and
    announced as its runner announces them; no agent is started."""
    import threading
    from pathlib import Path

    from metaform import events, home
    store = Store('proj', module='dispatch')
    with store.tables() as tx:
        if not tx.rows('agent_sessions', {'session_id': 's-1'}, limit=1).results:
            tx.insert('agent_sessions', {'session_id': 's-1', 'work_id': work_id, 'agent': 'claude', 'state': 'ended',
                                   'started': '2026-10-12T06:30:00Z', 'seq': 1})
        for seq, (kind, text) in enumerate(lines, start=first):
            tx.insert('session_lines', {'session_id': 's-1', 'name': f'line:{seq}', 'work_id': work_id, 'kind': kind,
                                'text': text, 'seq': seq})
    project = home.project('proj')
    assert project is not None
    # from a thread of its own: a browser check calls this inside Playwright's event loop
    announcing = threading.Thread(target=events.announce, args=(Path(project.path), 'cli'))
    announcing.start()
    announcing.join()


@pytest.mark.req('MCP-037')
def test_each_view_is_linked_from_its_tools_and_reviewed_by_its_meta_and_the_agents_address_is_kept_for_the_views(
        run, home, mapped):
    """The tools that open a view carry its URI; the views are listed with their content policy, permissions and
    border, the same _meta.ui their read carries with a cache hint; a node's and an item's templates point at the node
    view. A model's call naming an Address is what the views' `focus` read gives, map_node's element: taken off; the
    glossary read gives each quoted term exactly as written; the trace read answers `unchanged` to a view holding it."""
    from metaform.modules.mcp import views
    run('enable', 'dispatch')
    ticket = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'title=Make the alarm louder',
                 'task=Make the alarm louder', cwd=mapped)
    work_id = next(line.split(': ', 1)[1] for line in ticket.stdout.splitlines() if line.startswith('id: '))
    seed_thread(work_id, [('agent_message_chunk', 'I will raise the tone.')])
    wire = july_wire(home, mapped)
    try:
        shown = {tool['name']: tool.get('_meta') for tool in declaring(wire, 'tools/list', {}, APPS)['tools']}
        assert {name: shown[name] for name in views.SHOWN_BY if name in shown} == {
            name: {'ui': {'resourceUri': uri}} for name, uri in views.SHOWN_BY.items() if name in shown}
        assert {'map_where', 'map_item', 'dispatch_sessions', 'metaform_instructions'} <= set(shown)
        listed = {one['uri']: one for one in declaring(wire, 'resources/list', {}, APPS)['resources']}
        meta = {'ui': {'csp': {'connectDomains': [], 'resourceDomains': [], 'frameDomains': [], 'baseUriDomains': []},
                       'permissions': {'clipboardWrite': {}}, 'prefersBorder': True}}
        assert listed['ui://metaform/trace']['_meta'] == meta and listed['ui://metaform/trace']['mimeType'] == views.MIME
        assert listed['ui://metaform/map']['_meta']['ui']['prefersBorder'] is False
        assert not any(uri.startswith('ui://') for uri in (one['uri'] for one in declaring(
            wire, 'resources/list', {}, {})['resources']))
        read = declaring(wire, 'resources/read', {'uri': 'ui://metaform/trace'}, APPS)
        assert read['contents'][0]['_meta'] == meta and read['ttlMs'] == 60_000 and read['cacheScope'] == 'private'
        assert '/*view*/' not in read['contents'][0]['text'] and '"modes": ["inline", "fullscreen", "pip"]' in \
            read['contents'][0]['text']
        templates = {one['uriTemplate']: one.get('_meta') for one in declaring(
            wire, 'resources/templates/list', {}, APPS)['resourceTemplates']}
        assert templates['metaform://{address}'] == {'ui': {'resourceUri': 'ui://metaform/node'}}

        def focus():
            return declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {'read': 'focus'}},
                             APPS)['structuredContent']
        assert focus() == {'address': None, 'tool': None, 'seq': 0}
        declaring(wire, 'tools/call', {'name': 'map_node', 'arguments': {'node': 'element:code.timer.kitchen'}}, APPS)
        assert focus() == {'address': 'code.timer.kitchen', 'tool': 'map_node', 'seq': 1}
        declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': {'address': 'nowhere.at.all'}}, APPS)
        assert focus()['seq'] == 1  # a call refused names nothing

        glossary = declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {'read': 'glossary'}},
                             APPS)['structuredContent']
        terms = {one['term']: one['definition'] for one in glossary['terms']}
        assert f'{{RE}} := "{terms["RE"]}"' in glossary['text'] and 'Mode' not in terms
        assert {'name': 'map_where', 'summary': 'Read one address on the map: its element, what relies on it, and '
                                                'what it relies on, each with its purpose.'} in glossary['tools']

        def trace(digest='', mark=''):
            return declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {
                'read': 'trace', 'params': {'id': work_id, 'digest': digest, 'mark': mark}}}, APPS)['structuredContent']
        trace()
        held = trace()
        assert [line['text'] for line in held['lines']] == ['I will raise the tone.']
        assert held['ticket']['map']['title'] == 'Make the alarm louder'
        assert trace(held['digest']) == {'digest': held['digest'], 'unchanged': True, 'mark': held['mark']}
        # nothing changed since its mark: answered unchanged before the store is read
        assert trace(held['digest'], held['mark']) == {'digest': held['digest'], 'unchanged': True,
                                                       'mark': held['mark']}
        seed_thread(work_id, [('tool_call', 'Edit src/alarm.py (completed)')], first=2)
        assert [line['text'] for line in trace(held['digest'])['lines']][-1] == 'Edit src/alarm.py (completed)'
    finally:
        wire.close()
    run('set', '--mcp-apps-offer', 'always', cwd=mapped)
    wire = july_wire(home, mapped)
    try:  # a host that shows the views without declaring the extension, as basic-host does
        plain = {tool['name']: tool.get('_meta') for tool in declaring(wire, 'tools/list', {}, {})['tools']}
        assert plain['map_where'] == {'ui': {'resourceUri': 'ui://metaform/map'}}
        assert plain['metaform_view'] == {'ui': {'visibility': ['app']}}
    finally:
        wire.close()


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_node_view_turns_to_the_address_the_agent_names_and_its_own_tool_turns_it_without_telling_the_agent(
        run, home, mapped, chromium):
    """The shared picture, agent to person: an open node view turns to the Address a later Metaform call names, read
    through `focus`; a host that calls a view's own tools (App-Provided Tools) lists metaform_view_show and
    metaform_view_state and turns the view with the first. Neither turn is told to the agent as the person's; the
    person's own selection still is, as one line with the Address as structured content."""
    from metaform import prompt_files
    from metaform.modules.mcp import views
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/node'}, APPS)['contents'][0]['text']
        args = {'address': 'code.alarm.audible'}
        result = declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': args}, APPS)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page()
        page.set_default_timeout(15_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), APPS)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>'))
        page.evaluate('''() => {  // the view's answers to the host's own requests, and every context update whole
          window.answers = {}; window.contexts = [];
          addEventListener('message', event => {
            const m = event.data;
            if (m && m.id !== undefined && m.method === undefined) window.answers[m.id] = m;
            if (m && m.method === 'ui/update-model-context') window.contexts.push(m.params);
          });
          window.ask = (id, method, params) => send({id, method, params});
        }''')
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        assert page.evaluate('window.initialize.appCapabilities.tools') == {'listChanged': False}
        view = page.frame_locator('#frame')
        view.locator('#address', has_text='code.alarm.audible').wait_for()
        view.locator('#reliedOnList', has_text='code.timer.kitchen').wait_for()

        declaring(wire, 'tools/call', {'name': 'map_where', 'arguments': {'address': 'code.timer.kitchen'}}, APPS)
        view.locator('#address', has_text='code.timer.kitchen').wait_for()  # the agent named it: the view turned

        page.evaluate("window.ask(901, 'tools/list', {})")
        page.wait_for_function('window.answers[901]')
        assert [tool['name'] for tool in page.evaluate('window.answers[901].result.tools')] == [
            'metaform_view_show', 'metaform_view_state']
        page.evaluate("window.ask(902, 'tools/call', {name: 'metaform_view_show', arguments: {address: "
                      "'code.alarm.audible'}})")
        page.wait_for_function('window.answers[902]')
        shown = page.evaluate('window.answers[902].result')
        assert shown['content'][0]['text'] == prompt_files.module('mcp', 'view_shown', address='code.alarm.audible')
        view.locator('#address', has_text='code.alarm.audible').wait_for()
        assert page.evaluate('window.contexts') == []  # neither turn was the person's

        view.locator('#node').click()
        page.wait_for_function('window.contexts.length === 1')
        assert page.evaluate('window.contexts') == [{'content': [{'type': 'text', 'text': prompt_files.module(
            'mcp', 'view_selected', address='code.alarm.audible')}], 'structuredContent': {'address': 'code.alarm.audible'}}]
        page.evaluate("window.ask(903, 'tools/call', {name: 'metaform_view_state', arguments: {}})")
        page.wait_for_function('window.answers[903]')
        assert page.evaluate('window.answers[903].result.structuredContent') == {
            'view': 'node', 'shows': 'code.alarm.audible', 'selected': 'code.alarm.audible'}
        assert page.evaluate('window.refused') == []
    finally:
        wire.close()


@pytest.mark.browser
@pytest.mark.req('MCP-037')
def test_the_trace_view_follows_a_tickets_thread_as_lines_are_added(run, home, mapped, chromium):
    """The trace view, opened by dispatch_sessions for a ticket, shows its title, its node and the agent's thread,
    and draws a line the agent adds while it is open, read again through the views' tool."""
    from metaform.modules.mcp import views
    run('enable', 'dispatch')
    ticket = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'title=Make the alarm louder',
                 'task=Make the alarm louder', cwd=mapped)
    work_id = next(line.split(': ', 1)[1] for line in ticket.stdout.splitlines() if line.startswith('id: '))
    seed_thread(work_id, [('agent_message_chunk', 'I will raise the tone.')])
    wire = july_wire(home, mapped)
    try:
        html = declaring(wire, 'resources/read', {'uri': 'ui://metaform/trace'}, APPS)['contents'][0]['text']
        args = {'id': work_id}
        result = declaring(wire, 'tools/call', {'name': 'dispatch_sessions', 'arguments': args}, APPS)
        sdk = (views.resources.files('metaform.modules.mcp') / 'resources' / 'views' / 'ext-apps.js').read_text()
        page = chromium.new_page()
        page.set_default_timeout(15_000)
        page.expose_function('rpc', lambda params: json.dumps(declaring(wire, 'tools/call', json.loads(params), APPS)))
        page.set_content(HOST.replace('<script>SDK</script>', f'<script>{sdk}</script>'))
        page.evaluate('([html, args, result]) => window.open_view(html, args, result)', [html, args, result])
        page.wait_for_function('window.initialized')
        view = page.frame_locator('#frame')
        view.locator('#thread .line', has_text='I will raise the tone.').wait_for()
        assert view.locator('#title').inner_text() == 'Make the alarm louder'
        assert view.locator('#address').inner_text() == 'code.alarm.audible'
        seed_thread(work_id, [('tool_call', 'Edit src/alarm.py (completed)')], first=2)
        view.locator('#thread .line', has_text='Edit src/alarm.py (completed)').wait_for()
        assert page.evaluate('window.refused') == []
    finally:
        wire.close()


@pytest.mark.req('MCP-037')
def test_metaform_serves_its_glossary_alone_the_projects_own_and_the_tools_in_a_line_each(run, home, mapped):
    """metaform://metaform is the mcp glossary prompt as written and nothing more, metaform://glossary is gone with no
    alias, metaform://<project> is the map module's glossary of the project after the register standard, or the
    standard and a note while map is off, and metaform://tools gives each tool one line under its module with the
    rules after it."""
    import asyncio

    from metaform import prompt_files
    from metaform.modules.mcp import server
    run('enable', 'memory')

    def read(uri):
        return asyncio.run(server.read_resource_text(mapped, uri))[0]
    assert read('metaform://metaform') == prompt_files.module('mcp', 'glossary').strip() + '\n'
    with pytest.raises(server.Missing):
        read('metaform://glossary')
    standard = prompt_files.module('map', 'register_standard')
    project = read('metaform://proj')
    assert project.startswith(standard) and '@STATE_INIT' in project and 'audible alarm' in project
    tools = read('metaform://tools')
    assert '\nmap_\n  activate: ' in tools and '\n  where: Read one address on the map\n' in tools
    assert tools.index('\nmemory_\n') < tools.index(prompt_files.module('mcp', 'rules_heading'))
    run('set', '--modules', 'memory', cwd=mapped)  # map off: the standard as written, and why no terms follow
    assert read('metaform://proj') == standard + '\n\n' + prompt_files.module('mcp', 'project_glossary_absent') + '\n'


@pytest.mark.req('MCP-037')
def test_a_write_over_mcp_answers_one_line_with_its_number_not_the_record(run, home, mapped):
    """A ticket's add, plan, step and done, a memory recorded and a term added each answer an agent one line naming
    the new <address>#<n>; the command line still gets the record."""
    import asyncio

    from metaform.modules.mcp import server

    def call(name, **given):
        error, blocks = asyncio.run(server.run_tool(mapped, name, given))
        assert not error, blocks
        return blocks[-1]
    added = call('map_work', op='add', node='code.timer.kitchen', task='Make the alarm louder.', title='Louder alarm')
    work_id = added.rsplit('id ', 1)[1].rstrip('.')
    assert added == f'code.timer.kitchen#1 Louder alarm: added, id {work_id}.'
    assert call('map_work', op='take', id=work_id, by='claude') == 'code.timer.kitchen#1 Louder alarm: taken by claude.'
    assert call('map_work', op='plan', id=work_id, steps=2) == 'code.timer.kitchen#1 Louder alarm: 2 steps planned.'
    assert call('map_work', op='step', id=work_id, said='Found the gain.') == (
        'code.timer.kitchen#1 Louder alarm: step 1 of 2 recorded.')
    assert call('map_work', op='done', id=work_id, resolution='Gain raised.', why='The cook hears it.') == (
        'code.timer.kitchen#1 Louder alarm: done.')
    assert call('memory_create_entities', node='element:code.timer.kitchen', entities=[
        {'name': 'gain', 'entityType': 'fact', 'observations': ['The gain was low.'], 'why': 'It explains the tone.'}]
    ) == 'Recorded: code.timer.kitchen#2  The gain was low.'
    assert call('map_term', op='add', term='tone', definition='The alarm sound.', why='Cooks say tone.',
                source='alarm.c:3', node='code.timer.kitchen') == 'tone: added at code.timer.kitchen#3.'
    record = json.loads(run('map', 'work', 'op=edit', f'id={work_id}', 'note=kept', '--json', cwd=mapped).stdout)
    assert record['id'] == work_id and record['task'] == 'Make the alarm louder.'  # the command line keeps the record



@pytest.mark.req('MCP-040')
def test_a2a_peers_are_records_the_person_adds_and_removes_one_at_a_time(run, home, mapped):
    """Settings cleanup 2026-10-15: the peers are records, not the list setting mcp_a2a_peers, so adding one keeps
    the others; a stored list carries over once as mcp starts; add and remove are refused in an agent's session."""
    from metaform import home as homes
    from metaform import settings
    from metaform.modules.mcp import a2a_peers
    homes.save('global', 'mcp', 'mcp_a2a_peers', ['old=http://127.0.0.1:7440/.well-known/agent-card.json OLD_TOKEN',
                                                  'not a peer'])
    with homes.chassis(write=True) as db:  # the test home's own start carried nothing and marked it; undo the mark
        db.execute("DELETE FROM meta WHERE key='carried:mcp-a2a-peers'")
    settings._carried.clear()
    assert a2a_peers.carry() == ['peer old', "'not a peer' cannot be read as a peer and was left out"]
    assert a2a_peers.carry() == [], 'once per home'
    listed = lambda: {one['name']: one for one in json.loads(run('mcp', 'a2a_peers', '--json', cwd=mapped).stdout)['peers']}
    assert listed()['old']['token_env'] == 'OLD_TOKEN' and len(listed()) == 1  # carried; the malformed one left out
    assert homes.stored('global', 'mcp', 'mcp_a2a_peers') is None
    run('mcp', 'a2a_peer_add', 'other', 'http://127.0.0.1:7441/.well-known/agent-card.json', cwd=mapped)
    assert set(listed()) == {'old', 'other'}, 'adding one keeps the others'
    run('mcp', 'a2a_peer_remove', 'old', cwd=mapped)
    assert set(listed()) == {'other'}
    refused = run('mcp', 'a2a_peer_add', 'mine', 'http://127.0.0.1:7442/', cwd=mapped, ok=False,
                  env={'METAFORM_ROLE': 'worker'})
    assert refused.returncode != 0 and "never run from an agent's session" in refused.stdout + refused.stderr


@pytest.mark.req('MCP-041')
@pytest.mark.req('MCP-042')
@pytest.mark.req('MCP-043')
def test_an_a2a_send_carries_its_address_and_sender_and_what_the_peer_does_lands_at_the_address(run, home, mapped,
                                                                                               monkeypatch):
    import httpx
    from a2a.types import Message, Part, Role, TaskState, TaskStatus
    from starlette.applications import Starlette

    from metaform.module import Stop, context
    run('enable', 'dispatch')
    card_url = 'http://127.0.0.1:7491/.well-known/agent-card.json'  # never reached: the peer is in-process
    run('mcp', 'a2a_peer_add', 'peer', card_url, 'token=PEER_TOKEN', cwd=mapped)
    # imported after the last command, which may load the modules again, so the stub reaches the code that runs
    from metaform.modules.mcp import a2a as served
    from metaform.modules.mcp import a2a_out, a2a_records
    from metaform.modules.mcp.server import gateway_session
    app = Starlette()  # the stubbed peer: Metaform's own A2A routes
    served.attach(app, mapped, 7491)
    monkeypatch.setattr(a2a_out, 'TRANSPORT', httpx.ASGITransport(app=app))
    monkeypatch.setenv('PEER_TOKEN', served.token() or '')

    def verb(name, **nouns):  # a child agent's own session, never its parent's, MCP-042
        return getattr(a2a_out, name)(context('mcp', mapped, nouns=nouns, surface='mcp', session='child-session'))
    with pytest.raises(Stop, match=r'\(peer\)'):  # the list, in its refusal, MCP-040
        verb('send', peer='stranger', address='code.alarm.audible', text='Make it louder')
    sent = verb('send', peer='peer', address='code.alarm.audible', text='Make it louder\nThe cook misses it.')
    assert sent['state'] == 'submitted' and sent['sender'] == 'child-session'
    ticket = Store('proj').ticket(sent['peer_task']).work  # the peer's task is the ticket the message opened there
    assert ticket.address == 'code.alarm.audible' and 'child-session' in (ticket.note or '')
    assert a2a_records.kept_card('proj', 'peer', card_url)
    run('map', 'work', 'op=take', f'id={sent["peer_task"]}', cwd=mapped)
    run('map', 'work', 'op=done', f'id={sent["peer_task"]}', 'resolution=Louder now', 'why=The cook hears it',
        cwd=mapped)
    assert verb('exchanges', id=sent['exchange'])['state'] == 'completed'  # read again: no server follows it here
    held = Store('proj').messages(Node('element', 'code.alarm.audible'), limit=0).results
    assert [one.text for one in held if one.by == 'a2a peer'] == ['Louder now']  # the artifact, an item there
    flash = json.loads(run('map', 'work', 'op=add', 'node=code.alarm.audible', 'task=Make it flash', 'title=Flash',
                           '--json', cwd=mapped).stdout)['id']
    other = verb('send', peer='peer', address='code.alarm.audible', text='Make it flash', work=flash)
    question = TaskStatus(state=TaskState.TASK_STATE_INPUT_REQUIRED, message=Message(
        message_id='q-1', role=Role.ROLE_AGENT, parts=[Part(text='Which fan is it?')]))
    for _ in range(2):  # heard twice, by two followers: asked once
        a2a_out.heard('proj', other['exchange'], question)
    held = Store('proj').messages(Node('element', 'code.alarm.audible'), limit=0).results
    assert [one.kind for one in held if one.text == 'Which fan is it?'] == ['question']
    # the exchange keeps the ticket; the question is no permission request, so an agent may answer it too
    assert a2a_records.exchange('proj', other['exchange']).work_id == flash
    assert [one.work_id for one in held if one.text == 'Which fan is it?'] == [None]
    posts = []  # what reaches the peer from here on

    class Recording(httpx.ASGITransport):
        async def handle_async_request(self, request):
            if request.method == 'POST':
                posts.append(json.loads(await request.aread() or b'null'))
            return await super().handle_async_request(request)
    monkeypatch.setattr(a2a_out, 'TRANSPORT', Recording(app=app))
    asked = next(one.id for one in held if one.text == 'Which fan is it?')
    def answers():
        return [post['params']['message'] for post in posts if isinstance(post, dict)
                and post.get('method') == 'SendMessage']
    reached = []  # a call from the copy of a2a_out the command line loads again, which the stub never sees

    async def unreached(self, request):
        reached.append(str(request.url))
        raise httpx.ConnectError('no peer here', request=request)
    with monkeypatch.context() as patched:
        patched.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', unreached)
        run('map', 'reply', asked, 'answer=Red', cwd=mapped)
    assert answers() == [] and reached == []  # the reply is a local write; it never waits on the peer
    verb('exchanges', id=other['exchange'])
    assert [(one.get('taskId'), [part.get('text') for part in one['parts']]) for one in answers()] \
        == [(other['peer_task'], ['Red'])]  # the answer, once, on the peer's task, MCP-041
    assert a2a_records.exchange('proj', other['exchange']).asked is None
    cancelled = verb('cancel', id=other['exchange'])
    assert cancelled['state'] == 'cancelled' and Store('proj').ticket(other['peer_task']).work.outcome == 'cancelled'
    gateway = {'x-paperclip-agent-id': 'a-7', 'x-paperclip-run-id': 'r-9'}
    assert gateway_session(gateway) == 'paperclip:agent=a-7,run=r-9' and gateway_session({}) is None


# Tight context, the default since 2026-10-17: tools found by purpose, results trimmed, each piece at its moment.

def blocks(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None]


@pytest.mark.req('MCP-003')
@pytest.mark.req('MCP-039')
def test_a_worker_is_listed_its_category_alone_and_opens_another_in_its_place(run, home, mapped):
    """A dispatched worker connects to its role's line and the catalog's, without the order to read the glossaries
    or the module lines; it is listed metaform_catalog and the tools of the ticket category, the one its first task
    uses; opening remember lists that category's tools in place of ticket's, announced; a tool of a category its role
    does not open is refused, by name and through the catalog."""
    run('enable', 'memory', cwd=mapped)
    heard = []

    async def check(client, init):
        first = await listed(client)
        categories = await called(client, 'metaform_catalog', {})
        opened = await called(client, 'metaform_catalog', {'category': 'remember'})
        second = await listed(client)
        refused = await called(client, 'metaform_set', {'tmux': True})
        through = await called(client, 'metaform_catalog', {'tool': 'metaform_set', 'arguments': {'tmux': True}})
        found = await called(client, 'metaform_catalog', {'search': 'note another agent'})
        return init.instructions, first, categories, opened, second, refused, through, found
    env = {'METAFORM_ROLE': 'worker', 'METAFORM_SESSION': 'tight-worker', 'METAFORM_WORK': 'w-1'}
    said, first, categories, opened, second, refused, through, found = session(home, mapped, check, heard,
                                                                               tight=True, env=env)
    assert said.startswith('You work one ticket at its node, so you are given the tool categories that work needs: ')
    assert 'metaform_catalog' in said and 'The ticket category is open now' in said
    assert 'metaform://metaform' not in said and 'You must use Metaform' not in said and 'compacted=true' not in said
    assert 'metaform_catalog' in first and 'map_work' in first and 'memory_read_graph' not in first
    assert not {'metaform_set', 'dispatch_start', 'map_activate'} & set(first)
    listing = blocks(categories)[-1]
    assert 'ticket (open): ' in listing and 'remember: ' in listing and 'steer' not in listing and 'setup' not in listing
    assert blocks(opened)[0].startswith('remember: ') and 'in place of ticket' in blocks(opened)[0]
    assert 'memory_read_graph(' in blocks(opened)[0] and 'metaform_catalog tool=' in blocks(opened)[0]
    assert 'memory_read_graph' in second and 'map_work' not in second
    assert 'notifications/tools/list_changed' in heard
    for answer in (refused, through):
        assert answer.is_error and 'metaform_set is not among the tools a worker agent is given' in blocks(answer)[0]
    assert blocks(found)[-1].splitlines()[0].endswith('[coordinate]')


@pytest.mark.req('MCP-039')
def test_a_lookup_result_is_trimmed_counted_filtered_or_whole_as_the_call_asks(run, home, mapped):
    """A lookup tool's result comes lean: a list as a table with no field that holds nothing, said once how to ask
    for more; view=count counts the records by a field, must_contain keeps the rows that hold the text, and view=full
    gives every field as JSON."""
    for title in ('Ring louder', 'Snooze for five minutes', 'Beep twice'):
        run('map', 'work', 'op=add', 'node=code.timer.kitchen', f'title={title}', 'kind=enhancement',
            f'task={title}.', cwd=mapped)

    async def check(client, init):
        return [await called(client, 'map_work', arguments) for arguments in (
            {}, {'view': 'count', 'fields': ['kind']}, {'must_contain': 'snooze'}, {'view': 'full'},
            {'view': 'sideways'})]
    table, counted, narrowed, full, wrong = session(home, mapped, check, tight=True)
    text_of = blocks(table)
    rows = next(one for one in text_of if one.startswith('results:')).splitlines()
    assert 'map.title' in rows[1].split('|') and len(rows) == 5 and 'null' not in '\n'.join(rows)
    assert any(one.startswith('Results are trimmed to the fields most next steps need') for one in text_of)
    assert json.loads(blocks(counted)[-1]) == {'total': 3, 'by': {'kind': {'enhancement': 3}}}
    kept = blocks(narrowed)[-1].splitlines()
    assert len(kept) == 3 and 'Snooze for five minutes' in kept[2]
    assert not any(one.startswith('Results are trimmed') for one in blocks(narrowed))
    assert 'node_kind' in json.loads(blocks(full)[-1])['results'][0]
    assert wrong.is_error and 'view is one of triage, full, count' in blocks(wrong)[-1]


@pytest.mark.req('MCP-039')
def test_each_guide_and_the_glossary_pointer_come_once_until_the_agent_says_its_context_was_compacted(run, home,
                                                                                                    mapped):
    """The person's own session: the connect message keeps the order and the module lines, adds the catalog's line,
    the compaction line and the project, and leaves the glossary order to the first map read, which says where the
    terms are; a guide comes once, a second glossary read is one line, and compacted=true, or reading
    metaform://runtime/compaction-state, has each come again at its next use."""
    async def check(client, init):
        answers = [blocks(await called(client, 'map_where', {'address': address}))
                   for address in ('code.timer.kitchen', 'code.alarm.audible')]
        glossary = [(await client.read_resource('metaform://metaform')).contents[0].text for _ in range(2)]
        forgot = blocks(await called(client, 'metaform_catalog', {'compacted': True}))
        again = blocks(await called(client, 'map_where', {'address': 'code.timer.kitchen'}))
        state = (await client.read_resource('metaform://runtime/compaction-state')).contents[0].text
        return init.instructions, answers, glossary, forgot, again, state
    said, answers, glossary, forgot, again, state = session(home, mapped, check, tight=True)
    assert said.startswith('You must use Metaform for this project') and 'metaform_catalog' in said
    assert 'compacted=true' in said and 'This folder is the project proj.' in said
    assert 'Before beginning work, read metaform://metaform' not in said and len(said) <= 2048
    first, second = ('\n'.join(one) for one in answers)
    assert 'How to use map_where' in first and 'The words this map is written in' in first
    assert 'How to use map_where' not in second and 'The words this map' not in second
    assert glossary[0].lstrip().startswith('@STATE_INIT') and glossary[1].startswith('metaform://metaform is unchanged')
    assert forgot[0].startswith('Metaform forgot what it gave you once in this session')
    assert 'How to use map_where' in '\n'.join(again)
    assert state.startswith('Metaform forgot what it gave you once in this session, ') and ' 0 pieces' not in state


def test_a_trimmed_result_drops_what_holds_nothing_and_lists_records_as_a_table():
    """`shaping.shaped`: nothing empty, no false inside rows, a nested record's fields as parent.field, a | in a
    value escaped; the structured content keeps the same lean data; view count tallies a field; a long list is cut."""
    from metaform.modules.mcp import shaping
    rows = {'results': [{'id': 'a', 'title': 'One', 'held': False, 'note': None, 'map': {'title': 'x'}},
                        {'id': 'b', 'title': 'Two|x', 'held': True, 'links': []}], 'next': None}
    text, data = shaping.shaped(rows, shaping.Shape(), '<n/> more')
    assert text == 'results:\nid|title|map.title|held\na|One|x|\nb|Two\\|x||true'
    assert data == {'results': [{'id': 'a', 'title': 'One', 'map': {'title': 'x'}},
                                {'id': 'b', 'title': 'Two|x', 'held': True}]}
    counted, _ = shaping.shaped(rows, shaping.Shape(view='count', fields=('held',)), '')
    assert json.loads(counted) == {'total': 2, 'by': {'held': {'(none)': 1, 'true': 1}}}
    many = {'results': [{'id': str(number)} for number in range(30)]}
    cut, _ = shaping.shaped(many, shaping.Shape(), '<n/> more not shown.')
    assert cut.splitlines()[-1] == '5 more not shown.' and len(cut.splitlines()) == 1 + 1 + 25 + 1


def test_a_tools_guide_for_an_op_holds_only_that_ops_arguments(run, home, mapped):
    """map_work's guide for op=step gives the arguments whose help is for step or for every op, never distribute's or
    move's; a read by id with no op gives only the arguments for every op."""
    from metaform.modules.mcp.server import listing
    guide = listing(mapped)['map_work'].guide
    step = guide('step').splitlines()
    assert any(line.startswith('said: ') for line in step)
    assert not any(line.startswith(('agents: ', 'column: ', 'glyph: ')) for line in step)
    read = guide('read').splitlines()
    assert any(line.startswith('id: ') for line in read) and not any(line.startswith('node: ') for line in read)


def test_find_names_the_addresses_that_hold_the_words(run, home, mapped):
    """map find: an element by its name and a join by its purpose, each by its Address, the most words first."""
    found = Store('proj').find('audible alarm')
    assert found[0] == {'address': 'code.alarm.audible', 'kind': 'element', 'what': 'audible alarm'}
    assert {'address': 'code.timer.kitchen', 'kind': 'join', 'what': 'Get attention. EF: Plays a tone.'} in \
        Store('proj').find('attention')
