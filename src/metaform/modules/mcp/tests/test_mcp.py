"""The mcp module: surfaced tools, calls and project selection."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform.data import Node, Store
from metaform.modules.mcp.server import mcp_next


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"
CHASSIS_TOOLS = {'metaform_set', 'metaform_feedback', 'metaform_list_reports', 'metaform_read_report',
                 'metaform_instructions', 'metaform_register'}


def session(home, folder, fn, heard=None):
    """A real MCP client on `metaform mcp serve` in the folder; the methods of the notifications it hears go in
    `heard`."""
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

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
    names = SKILLS

    async def check(client, init):
        assert 'workflow_skill' in await listed(client)
        declared = {one.name for one in (await client.list_prompts()).prompts}
        assert set(names) <= declared
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


def text(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None]


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
    assert 'metaform://metaform' in instructions and len(instructions) <= 2048
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
    assert names == {'solo_hi'} | CHASSIS_TOOLS
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
        names = set(await tool_names(client))
        started = await called(client, 'intake_start', {'model': 'claude', 'role': 'intake agent'})
        described = await called(client, 'intake_element', {'namespace_address': 'code.timer.kitchen', 'role': 'DE',
                                                              'name': 'kitchen timer', 'name_length': 2,
                                                              'refs': [{'key': 'path', 'value': 'src/main.c'}]})
        named = json.loads(text(described)[-1])['notices']
        await called(client, 'intake_element', {'namespace_address': 'code.loop.tick', 'role': 'SE'})
        made = await called(client, 'intake_join', {'receiver': 'code.timer.kitchen', 'elements': ['code.alarm.audible'],
                                                      'purpose': 'Get attention.', 'ef': 'rings', 'ifd': 'receives'})
        # Recorded again with an element it holds, the join takes the new elements: parts annealed into one join.
        annealed = await called(client, 'intake_join', {'receiver': 'code.timer.kitchen',
                                                          'elements': ['code.alarm.audible', 'code.loop.tick',
                                                                       'code.loop.beat']})
        shown = json.loads(text(await called(client, 'intake_show', {}))[-1])
        one = json.loads(text(await called(client, 'intake_show', {'receiver': 'code.timer.kitchen'}))[-1])
        finished = json.loads(text(await called(client, 'intake_finish', {'report': 'Fine.'}))[-1])
        return (names, started.is_error, shown, finished, named, described.is_error,
                (annealed.is_error, json.loads(text(made)[-1])), one)
    names, error, shown, finished, named, described_error, joined, one = session(home, folder, call)
    assert joined[0] is False and set(joined[1]) == {'receiver', 'elements', 'layer', 'notices'}
    assert [row['elements'] for row in one['joins']] == [['code.alarm.audible', 'code.loop.tick', 'code.loop.beat']]
    assert {'intake_start', 'intake_element', 'intake_join', 'intake_show', 'intake_remove', 'intake_finish'} <= names
    assert not names & {'intake_add_purpose', 'intake_subtype', 'intake_absorb', 'intake_edit'}
    assert error is False and described_error is False
    assert named == []  # the element's name is its own field
    assert [(row['purpose'], row['ef'], row['ifd']) for row in shown['joins']] == [('Get attention.', 'rings',
                                                                                     'receives')]
    assert [(row['namespace_address'], row['role']) for row in shown['elements']] == [
        ('code.alarm.audible', None), ('code.loop.beat', None), ('code.loop.tick', 'SE'), ('code.timer.kitchen', 'DE')]
    assert shown['undescribed'] == ['code.alarm.audible', 'code.loop.beat']
    assert (finished['elements'], finished['joins']) == (4, 1)
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


@pytest.mark.req('PROJ-025')
@pytest.mark.req('MCP-006')
def test_clear_project_is_a_caution_tool_while_the_chassis_is_on_the_surface(run, home, mapped):
    """metaform_clear_project is declared as every other tool: its description says what it removes, that a backup is
    made first and that restore brings it back; it takes confirm, as any caution tool, and is destructive."""
    run('feedback', 'A note.', cwd=mapped)

    async def check(client, init):
        tools = await listed(client)
        refused = await called(client, 'metaform_clear_project', {})
        still = await called(client, 'map_where', {'address': 'code.timer.kitchen'})
        cleared = await called(client, 'metaform_clear_project', {'confirm': True})
        return tools, refused, still, cleared
    tools, refused, still, cleared = session(home, mapped, check)
    declared = tools['metaform_clear_project']
    assert declared.input_schema['properties'].keys() == {'confirm', 'project'}
    assert declared.annotations.destructive_hint is True
    assert 'backup is made first' in declared.description and 'metaform restore project' in declared.description
    assert refused.is_error is True
    said = '\n'.join(text(refused))
    assert 'Clearing proj removes' in said and 'Next: If you are sure: call metaform_clear_project with confirm true' in said
    assert still.is_error is False  # the caution alone changed nothing
    assert cleared.is_error is False
    told = json.loads(text(cleared)[-1])
    assert told.pop('backup') and told.pop('restore') == 'metaform restore project proj'  # PROJ-030
    assert told == {'project': 'proj', 'bases': ['main'], 'reports': 1}
    assert run('list', 'bases', cwd=mapped).stdout == ''
    assert not (own('proj') / 'reports').exists()
    run('set', '--modules', 'map', cwd=mapped)

    async def narrowed(client, init):
        return set(await tool_names(client))
    assert 'clear_project' not in session(home, mapped, narrowed)


@pytest.mark.req('PROJ-025')
@pytest.mark.req('MCP-006')
def test_clear_project_returns_what_it_could_not_remove_with_what_to_do_and_no_error(run, home, mapped, unremovable):
    run('feedback', 'A note.', cwd=mapped)
    (stuck,) = (own('proj') / 'reports').iterdir()

    async def check(client, init):
        return await called(client, 'metaform_clear_project', {'confirm': True})
    with unremovable(stuck):
        cleared = session(home, mapped, check)
        assert stuck.is_file()
    assert cleared.is_error is False
    result = json.loads(text(cleared)[-1])
    assert (result['project'], result['bases'], result['reports']) == ('proj', ['main'], 1)
    assert [entry['path'] for entry in result['not_removed']] == [str(stuck)] and result['not_removed'][0]['reason']
    assert [notice['where'] for notice in result['notices']] == ['not_removed']
    assert 'call metaform_clear_project with confirm true again' in result['notices'][0]['message']
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
              if 'mcp' in verb.surfaces and on_this_system(verb)}
    assert set(tools) == wanted | CHASSIS_TOOLS | HISTORY_TOOLS | {
        'metaform_prompts', 'metaform_prompt', 'metaform_save_prompt', 'metaform_clear_project'}
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
    module's connect line, mcp's closing line, then what the folder's state calls for."""
    from metaform.instructions import startup
    return startup(folder)


@pytest.mark.req('CLI-037')
@pytest.mark.req('MCP-003')
def test_a_commands_tool_carries_its_schema_and_a_call_missing_an_argument_names_it(run, home, mapped):
    """A command's arguments, descriptions and schema are in its tool as listed, from the same declaration as its
    command line; a call that leaves out a required argument is refused with that tool as the next step."""
    async def check(client, init):
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
    assert full not in started and len(started) <= 2048
    assert entered['instructions'].strip() == full and [block.strip() for block in asked] == [full]
    assert wrong.is_error
    from metaform.modules.workflow import SKILLS
    described = [prompts[name] for name in SKILLS]
    assert len(set(described)) == len(SKILLS) and all(described)


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
        offered = (await listed(client))['metaform_set'].input_schema
        return refused.is_error, text(refused)[0], offered['properties']
    error, said, offered = session(home, mapped, call)
    assert error and 'dispatch_prompts is set only by the person' in said
    assert [line for line in said.splitlines() if line.startswith('Next: ')] == [
        'Next: call map_work op=edit id=<your work id> note="..."']
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
    assert 'metaform://metaform, then metaform://proj' in started and len(started) <= 2048
    assert listed[:3] == ['metaform://metaform', 'metaform://proj', 'metaform://tools']
    assert served == glossary.strip() + '\n' and len(served) > 2048  # whole and alone, past the connect text's cut


@pytest.mark.req('MCP-003')
def test_the_glossary_is_one_text_by_tool_resource_and_command_line(run, home, mapped):
    """metaform_instructions with module metaform is the glossary the resource serves and the command line prints."""
    async def check(client, init):
        tool = await called(client, 'metaform_instructions', {'module': 'metaform'})
        assert not tool.is_error, text(tool)
        described = (await listed(client))['metaform_instructions'].input_schema['properties']['module']['description']
        return ''.join(text(tool)), (await client.read_resource('metaform://metaform')).contents[0].text, described
    by_tool, by_resource, described = session(home, mapped, check)
    assert by_tool == by_resource == run('instructions', 'metaform', cwd=mapped).stdout
    assert 'metaform://metaform' in described  # found in the tool's schema by a model that cannot read resources


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
    # The server that ran the stranded call has stopped: a new one finds the task, and, its owner's mark gone stale,
    # reads it as failed rather than leaving the client to wait.
    with Store('proj', module='mcp').tables() as tx:
        tx.update('tool_tasks', {'task_id': stranded['taskId']}, {'beat': int(time.time()) - task_records.LOST_S - 1})
    wire = july_wire(home, mapped)
    try:
        assert declaring(wire, 'tasks/get', {'taskId': made['taskId']}, tasks)['status'] == 'completed'
        lost = declaring(wire, 'tasks/get', {'taskId': stranded['taskId']}, tasks)
        assert lost['status'] == 'failed' and lost['error']['message'] == task_records.STOPPED
    finally:
        wire.close()


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
            tx.insert('sessions', {'session_id': 's-died', 'work_id': died, 'agent': 'claude', 'state': 'ended',
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
    """A recorded agent thread for a ticket, written into dispatch's own tables as its runner writes them; no agent
    is started."""
    store = Store('proj', module='dispatch')
    with store.tables() as tx:
        if not tx.rows('sessions', {'session_id': 's-1'}, limit=1).results:
            tx.insert('sessions', {'session_id': 's-1', 'work_id': work_id, 'agent': 'claude', 'state': 'ended',
                                   'started': '2026-10-12T06:30:00Z', 'seq': 1})
        for seq, (kind, text) in enumerate(lines, start=first):
            tx.insert('lines', {'session_id': 's-1', 'name': f'line:{seq}', 'work_id': work_id, 'kind': kind,
                                'text': text, 'seq': seq})


@pytest.mark.req('MCP-037')
def test_each_view_is_linked_from_its_tools_and_reviewed_by_its_meta_and_the_agents_address_is_kept_for_the_views(
        run, home, mapped):
    """The tools that open a view carry its URI; the views are listed with their content policy, permissions and
    border, the same _meta.ui their read carries with a cache hint; a node's and an item's templates point at the node
    view. A model's call naming an Address is what the views' `focus` read gives, map_node's element: taken off; the
    glossary read gives each quoted term exactly as written; the trace read answers `unchanged` to a view holding it."""
    from metaform.modules.mcp import views
    run('enable', 'dispatch')
    ticket = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'title=Make the alarm louder', cwd=mapped)
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

        def trace(digest=''):
            return declaring(wire, 'tools/call', {'name': 'metaform_view', 'arguments': {
                'read': 'trace', 'params': {'id': work_id, 'digest': digest}}}, APPS)['structuredContent']
        trace()
        held = trace()
        assert [line['text'] for line in held['lines']] == ['I will raise the tone.']
        assert held['ticket']['map']['title'] == 'Make the alarm louder'
        assert trace(held['digest']) == {'digest': held['digest'], 'unchanged': True}
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
    ticket = run('map', 'work', 'op=add', 'node=code.alarm.audible', 'title=Make the alarm louder', cwd=mapped)
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

