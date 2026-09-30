"""The mcp module: surfaced tools, calls and project selection."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform.data import Store

pytestmark = pytest.mark.kind('fixture')

OS = "SUPPORTED_OS = ('linux', 'macos', 'windows')"
CHASSIS_TOOLS = {'set', 'feedback', 'list_reports', 'read_report'}


def session(home, folder, fn):
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            init = await client.initialize()
            return await fn(client, init)
    return asyncio.run(go())


def text(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None]


class Command:
    """One command of a tool, with what it takes."""

    def __init__(self, description, input_schema):
        self.description, self.input_schema = description, input_schema


async def listed(client):
    return {tool.name: tool for tool in (await client.list_tools()).tools}


async def tool_names(client):
    """Every command the server offers, by the name it runs under, `<module>_<command>` or the chassis's own name,
    read as an agent reads them: by entering each tool, CLI-037."""
    found = {}
    for tool in await listed(client):
        entered = json.loads(text(await client.call_tool(tool, {}))[-1])
        for one in entered['commands']:
            name = one['command'] if tool == 'metaform' else f"{tool}_{one['command']}"
            found[name] = Command(one['summary'], one['arguments'])
    return found


async def called(client, name, arguments):
    """Run a command as an agent does: the tool it belongs to, its command, and its arguments."""
    tool = next((one for one in await listed(client) if name.startswith(one + '_')), 'metaform')
    command = name if tool == 'metaform' else name[len(tool) + 1:]
    return await client.call_tool(tool, {'command': command, 'arguments': arguments})


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
        store.add_element(layer.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_join(layer.name, 'code.timer.kitchen', 'code.alarm.audible', name='audible alarm',
                       purpose='Get attention.',
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
    observations = tools['memory_add-observations'].input_schema['properties']['text']
    assert (observations['type'], observations['items']) == ('array', {'type': 'string'}) and observations['description']
    assert 'add-item' in tools['map_knowledge'].input_schema['properties']['op']['description']
    for name in ('feedback', 'list_reports', 'read_report', 'set'):
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
@pytest.mark.req('MAP-020')
@pytest.mark.req('STORE-011')
def test_a_knowledge_subtypes_own_purpose_survives_mcp_creation_and_readback(run, home, mapped):
    """The Canonical Intake's internal joins keep their own OP alongside their EF, also in knowledge layers."""
    async def check(client, init):
        async def knowledge(**arguments):
            result = await client.call_tool('map', {'command': 'knowledge',
                                                    'arguments': {'layer': 'notes', **arguments}})
            assert not result.is_error, text(result)
            return json.loads(text(result)[-1])

        await knowledge(op='create', variable='Alarm operation.', mutable=True, hideable=True)
        parent = await knowledge(op='add-join', receiver='code.timer.kitchen', provider='code.alarm.audible',
                                 purpose='Get attention.', function='Plays a tone.')
        await knowledge(op='add-subtype', join=parent['join_id'], address='code.alarm.audible.piezo',
                        purpose='Make the end audible.', function='Buzzes when driven.', ef='Function',
                        relation='buzzes when driven', verb='buzzes', observation='A piezo disc.')
        await knowledge(op='finish')
        result = await client.call_tool('map', {'command': 'where',
                                                'arguments': {'address': 'code.timer.kitchen'}})
        assert not result.is_error, text(result)
        return json.loads(text(result)[-1])

    view = session(home, mapped, check)
    parent = next(join for join in view['receives'] if join['layer'] == 'notes')
    (subtype,) = parent['subtypes']
    assert parent['purpose'] == 'Get attention.'
    assert (subtype['purpose'], subtype['function']) == ('Make the end audible.', 'Buzzes when driven.')
    assert 'purpose' not in subtype.get('extra', {})


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
        refused = await client.call_tool('map', {'command': 'knowledge', 'arguments': {'op': 'create', 'layer': 'x'}})
        return set(tools) | set(await listed(client)), refused.is_error, text(refused)
    names, error, message = session(home, mapped, narrowed)
    assert 'map' not in names and 'map_knowledge' not in names and 'memory_open-nodes' in names
    assert error and message[0].splitlines() == ['Error: No tool map on this surface.',
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
    assert error and missing[0].splitlines() == cli
    assert caution_error and caution[0].splitlines() == [
        'Error: This deletes the greeting history.', 'Next: If you are sure: call hello with command forget and confirm true in its arguments']
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
        chosen = await called(client, 'set', {'project': 'proj'})
        after = await called(client, 'map_layers', {})
        return init.instructions, before.is_error, text(before), chosen.is_error, after.is_error, text(after)
    instructions, before_error, before, chosen_error, after_error, after = session(home, outside, call)
    assert instructions.rstrip().endswith('To register one: metaform add project <id> <path>')
    assert before_error and before[0].splitlines()[-1] == 'Next: metaform set --project <id>'
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
    cli = json.loads(run('map', 'where', 'code.timer.kitchen', '--json', cwd=mapped).stdout)

    async def call(client, init):
        small = text(await called(client, 'map_where', {'address': 'code.timer.kitchen'}))
        full = text(await called(client, 'map_where', {'address': 'code.timer.kitchen', 'full': True}))
        return json.loads(small[-1]), json.loads(full[-1])
    small, full = session(home, mapped, call)
    assert small == cli and set(small) == {'kind', 'element', 'receives'}
    assert [(join['provider'], join['function']) for join in small['receives']] == [('code.alarm.audible',
                                                                                     'Plays a tone.')]
    assert 'join_id' not in small['receives'][0] and full['receives'][0]['join_id']


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
        return (await called(client, 'set', {'modules': ['map', 'mcp'], 'layers': ['intake-1']})).is_error
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
        said = await called(client, 'feedback', {'text': 'Narrowed to solo.'})
        listed = await called(client, 'list_reports', {})
        name = json.loads(text(said)[-1])['files'][0]
        read = await called(client, 'read_report', {'name': name})
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
        bad_set = await called(client, 'set', {'loud': 'no'})
        return [(result.is_error, text(result)) for result in (missing, as_text, not_number, bad_set)]
    results = session(home, mapped, call)
    assert all(error for error, _ in results)
    assert all(len([line for line in blocks[0].splitlines() if line.startswith('Next: ')]) == 1
               for _, blocks in results)
    assert results[0][1][0].splitlines()[-1] == missing_cli
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
        stored = await called(client, 'set', {'greeting': 5})
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
        said = await called(client, 'feedback', {'text': 12})
        listed = await called(client, 'list_reports', {'kind': ['feedback']})
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
        made = await called(client, 'intake_join', {'receiver': 'code.timer.kitchen', 'name': 'countdown alarm',
                                                      'provider': 'code.alarm.audible', 'purpose': 'Get attention.',
                                                      'function': 'Rings.', 'ef': 'Encounter', 'relation': 'r',
                                                      'verb': 'rings', 'observation': 'o'})
        join_id = json.loads(text(made)[-1])['join_id']
        await called(client, 'intake_subtype', {'into': join_id, 'namespace_address': 'code.loop.tick',
                                                  'function': 'Ticks.',
                                                  'ef': 'Function', 'relation': 'r', 'verb': 'advances',
                                                  'observation': 'o', 'role': 'SE'})
        beat = await called(client, 'intake_join', {'receiver': 'code.timer.kitchen', 'provider': 'code.loop.beat',
                                                      'purpose': 'Keep time.', 'function': 'Beats.', 'ef': 'Function',
                                                      'relation': 'r', 'verb': 'beats', 'observation': 'o'})
        beat_id = json.loads(text(beat)[-1])['join_id']
        absorbed = await called(client, 'intake_absorb', {'join': beat_id, 'into': join_id})
        moved = json.loads(text(absorbed)[-1])
        shown = json.loads(text(await called(client, 'intake_show', {}))[-1])
        one = json.loads(text(await called(client, 'intake_show', {'receiver': 'code.timer.kitchen'}))[-1])
        finished = json.loads(text(await called(client, 'intake_finish', {'report': 'Fine.'}))[-1])
        return (names, started.is_error, shown, finished, named, described.is_error,
                (absorbed.is_error, moved['join_id'], moved['parent'], beat_id, join_id), one)
    names, error, shown, finished, named, described_error, absorb, one = session(home, folder, call)
    assert absorb[0] is False and absorb[1:3] == absorb[3:5]
    assert [row['join_id'] for row in one['joins']] == [absorb[4]]
    assert {sub['join_id'] for sub in one['joins'][0]['subtypes']} >= {absorb[3]}
    assert {'intake_start', 'intake_element', 'intake_join', 'intake_subtype', 'intake_absorb', 'intake_show',
            'intake_edit', 'intake_remove', 'intake_finish'} <= names and 'intake_submit' not in names
    assert error is False and described_error is False
    assert [notice['where'] for notice in named] == ['name'] and 'join' in named[0]['message']
    assert [row['name'] for row in shown['joins']] == ['countdown alarm']
    assert [(row['namespace_address'], row['role']) for row in shown['elements']] == [
        ('code.alarm.audible', None), ('code.loop.beat', None), ('code.loop.tick', 'SE'), ('code.timer.kitchen', 'DE')]
    assert shown['undescribed'] == ['code.alarm.audible', 'code.loop.beat']
    assert len(shown['joins']) == 1 and len(shown['joins'][0]['subtypes']) == 2
    assert (finished['elements'], finished['joins'], finished['subtypes'], finished['refs']) == (4, 1, 2, 1)
    kitchen = Store('fresh').element('code.timer.kitchen')
    assert [(ref.key, ref.value) for ref in kitchen.refs] == [('path', 'src/main.c')]
    assert (kitchen.short_name, kitchen.extra) == ('kitchen timer', {'name': 'kitchen timer'})


@pytest.mark.req('VIEW-018')
@pytest.mark.req('MCP-002')
def test_a_tool_call_that_changes_the_map_is_announced_and_a_read_is_not(run, home, mapped, tmp_path, user_module):
    log = tmp_path / 'heard.jsonl'
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
        await called(client, 'memory_add-observations', {'node': 'element:code.timer.kitchen',
                                                           'text': ['The countdown drifts.']})
        written = lines()
        await called(client, 'map_layers', {})  # in the same server process: a read after a write
        return read, written, lines()
    read, written, after = session(home, mapped, call)
    active = Store('proj').active_metaform()
    assert read == []
    assert written == [{'project': 'proj', 'metaform_id': active.metaform_id}]  # once, for the one write
    assert after == written  # the notes were taken once: the read announces nothing, not the write again


HISTORY_TOOLS = {'add_origin', 'list_origins', 'add_variant', 'list_variants', 'extract'}


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
        origin = json.loads(text(await called(client, 'add_origin', {}))[-1])
        variant = json.loads(text(await called(client, 'add_variant', {'folder': str(work), 'workflow': 'mutate',
                                                                           'blinded': False}))[-1])
        listed = json.loads(text(await called(client, 'list_variants', {}))[-1])
        written = json.loads(text(await called(client, 'extract', {'variants': [variant['variant_id']],
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
        listed = json.loads(text(await called(client, 'prompts', {}))[-1])
        newest = json.loads(text(await called(client, 'prompt', {'name': 'practices'}))[-1])
        first = json.loads(text(await called(client, 'prompt', {'name': 'practices', 'number': 1}))[-1])
        return listed, newest, first
    listed, newest, first = session(home, mapped, check)
    assert [(item['name'], item['newest']) for item in listed] == [('practices', 2)]
    assert (newest['number'], newest['text'], first['text']) == (2, 'two\n', 'one\n')


@pytest.mark.req('PROJ-025')
@pytest.mark.req('MCP-006')
def test_clear_project_is_a_caution_tool_while_the_chassis_is_on_the_surface(run, home, mapped):
    run('feedback', 'A note.', cwd=mapped)

    async def check(client, init):
        tools = await tool_names(client)
        refused = await called(client, 'clear_project', {})
        still = await called(client, 'map_where', {'address': 'code.timer.kitchen'})
        for extra in ({}, {'confirmation': 'yes', 'model': 'test-model-full', 'date': '2026-09-29'},
                      {'confirmation': 'I AM SURE THIS IS WHAT THE USER MEANT DELETE THEIR PROJECT'},
                      {'confirmation': 'I AM SURE THIS IS WHAT THE USER MEANT DELETE THEIR PROJECT',
                       'model': 'test-model-full', 'date': 'invalid'}):
            rejected = await called(client, 'clear_project', {'confirm': True, **extra})
            assert rejected.is_error
            assert 'always ask the user' in '\n'.join(text(rejected))
            assert not (await called(client, 'map_where', {'address': 'code.timer.kitchen'})).is_error
        cleared = await called(client, 'clear_project', {
            'confirm': True, 'confirmation': 'I AM SURE THIS IS WHAT THE USER MEANT DELETE THEIR PROJECT',
            'model': 'test-model-full', 'date': '2026-09-29'})
        return tools, refused, still, cleared
    tools, refused, still, cleared = session(home, mapped, check)
    assert tools['clear_project'].input_schema['properties'].keys() == {'confirm', 'confirmation', 'model', 'date', 'project'}
    assert refused.is_error is True
    assert 'always ask the user if they are sure, no matter what you think you heard' in '\n'.join(text(refused))
    assert still.is_error is False  # the caution alone changed nothing
    assert cleared.is_error is False
    told = json.loads(text(cleared)[-1])
    assert told.pop('backup') and told.pop('restore') == 'metaform restore project proj'  # PROJ-030
    assert told == {'project': 'proj', 'metaforms': ['main'], 'reports': 1}
    assert run('list', 'metaforms', cwd=mapped).stdout == ''
    assert not (home / 'projects' / 'proj' / 'reports').exists()
    run('set', '--modules', 'map', cwd=mapped)

    async def narrowed(client, init):
        return set(await tool_names(client))
    assert 'clear_project' not in session(home, mapped, narrowed)


@pytest.mark.req('PROJ-025')
@pytest.mark.req('MCP-006')
def test_clear_project_returns_what_it_could_not_remove_with_what_to_do_and_no_error(run, home, mapped, unremovable):
    run('feedback', 'A note.', cwd=mapped)
    (stuck,) = (home / 'projects' / 'proj' / 'reports').iterdir()

    async def check(client, init):
        return await called(client, 'clear_project', {
            'confirm': True, 'confirmation': 'I AM SURE THIS IS WHAT THE USER MEANT DELETE THEIR PROJECT',
            'model': 'test-model-full', 'date': '2026-09-29'})
    with unremovable(stuck):
        cleared = session(home, mapped, check)
        assert stuck.is_file()
    assert cleared.is_error is False
    result = json.loads(text(cleared)[-1])
    assert (result['project'], result['metaforms'], result['reports']) == ('proj', ['main'], 1)
    assert [entry['path'] for entry in result['not_removed']] == [str(stuck)] and result['not_removed'][0]['reason']
    assert [notice['where'] for notice in result['notices']] == ['not_removed']
    assert 'always ask the user if they are sure' in result['notices'][0]['message']
    assert run('list', 'metaforms', cwd=mapped).stdout == ''


@pytest.mark.req('BASE-035')
@pytest.mark.req('BASE-044')
@pytest.mark.req('MCP-005')
def test_a_text_noun_sent_another_json_value_reaches_the_tool_as_its_json_text_with_a_notice(run, home, mapped):
    run('enable', 'hello')

    async def call(client, init):
        greeted = await called(client, 'hello_greet', {'name': {'a': 1}})
        joined = await called(client, 'map_knowledge', {
            'op': 'add-join', 'layer': 'notes', 'receiver': 'code.timer.kitchen', 'provider': 'code.alarm.audible',
            'purpose': 12, 'function': 'f', 'relation': ['r'], 'observation': 'o'})
        observed = await called(client, 'memory_add-observations', {'node': 'element:code.timer.kitchen',
                                                                     'text': ['fine', 7]})
        return [(result.is_error, text(result)) for result in (greeted, joined, observed)]
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=mapped)
    (greet_error, greeted), (join_error, joined), (observe_error, observed) = session(home, mapped, call)
    assert not greet_error and not join_error and not observe_error
    assert greeted == ['Notice: name: name is text; what was sent was kept as its JSON text.', 'hello, {"a": 1}\n']
    assert joined[0].splitlines() == ['Notice: purpose: purpose is text; what was sent was kept as its JSON text.',
                                      'Notice: relation: relation is text; what was sent was kept as its JSON text.']
    join = json.loads(joined[1])
    assert (join['purpose'], join['relation'], join['notices']) == ('12', '["r"]', [])
    assert observed[0].splitlines() == ['Notice: text: text is text; what was sent was kept as its JSON text.']
    store = Store('proj')
    assert {item.value for item in store.layer_items('memory').results} >= {'fine', '7'}


@pytest.mark.req('CLI-037')
def test_the_server_lists_one_tool_for_each_module_and_a_module_is_entered_for_its_commands(run, home, mapped):
    """The first thing an agent meets is small: a name for each thing that can be entered and none of the commands
    beneath it. 64 tools cost an agent about 13,800 tokens before it had done anything."""
    async def check(client, init):
        tools = await listed(client)
        entered = await client.call_tool('map', {})
        unknown = await client.call_tool('map', {'command': 'nothing'})
        stray = await client.call_tool('map', {'address': 'code.timer.kitchen'})
        ran = await client.call_tool('map', {'command': 'joins', 'arguments': {'element': 'code.timer.kitchen'}})
        return tools, entered, unknown, stray, ran
    tools, entered, unknown, stray, ran = session(home, mapped, check)
    enabled = {line.split()[0] for line in run('list', 'modules', cwd=mapped).stdout.splitlines()
               if line.split()[1] == 'on'}
    assert set(tools) == (enabled - {'mcp'}) | {'metaform'}           # mcp has only serve, which is no tool
    size = sum(len(json.dumps(tool.input_schema)) + len(tool.description) for tool in tools.values())
    assert size < 6000                                                   # what an agent is handed at the start
    for name, tool in tools.items():
        properties = tool.input_schema['properties']
        assert set(properties) == {'command', 'arguments'} and tool.input_schema['additionalProperties'] is False
        assert all(command in tool.description for command in properties['command']['enum']), name
    assert 'joins' in tools['map'].input_schema['properties']['command']['enum']
    commands = {one['command']: one for one in json.loads(text(entered)[-1])['commands']}
    assert not entered.is_error and set(commands) == set(tools['map'].input_schema['properties']['command']['enum'])
    assert commands['joins']['arguments']['required'] == ['element'] and commands['joins']['summary']
    assert unknown.is_error and text(unknown)[0].splitlines() == [
        'Error: map has no command nothing.', 'Next: call map with no command for its commands']
    assert stray.is_error and 'takes command and arguments' in text(stray)[0]
    assert json.loads(text(ran)[-1]) == json.loads(run('map', 'joins', 'code.timer.kitchen', '--json', cwd=mapped).stdout)


@pytest.mark.req('CLI-037')
def test_a_commands_arguments_sent_beside_the_command_are_taken_as_its_arguments(run, home, mapped):
    """Found in the intake run of 2026-09-29: an agent sent a join's fields beside `command`, not inside `arguments`,
    and the call was refused though every field it needed was there. What is sent is made to fit."""
    async def check(client, init):
        beside = await client.call_tool('map', {'command': 'joins', 'element': 'code.timer.kitchen'})
        both = await client.call_tool('map', {'command': 'joins', 'arguments': {'element': 'code.timer.kitchen'},
                                              'element': 'code.alarm.audible'})
        return beside, both
    beside, both = session(home, mapped, check)
    wanted = json.loads(run('map', 'joins', 'code.timer.kitchen', '--json', cwd=mapped).stdout)
    assert not beside.is_error and json.loads(text(beside)[-1]) == wanted
    assert not both.is_error and json.loads(text(both)[-1]) == wanted   # what is inside arguments is what was meant
