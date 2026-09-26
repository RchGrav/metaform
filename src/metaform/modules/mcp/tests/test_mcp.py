"""The mcp module: every surfaced module verb as a tool, live instructions, MCP-001 to MCP-008 and MCP-025."""
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
BASE = ("Metaform keeps this project's functional map: what each part is for, who receives what it does, and how. "
        'Read the map before you change the project, so you work from the purpose of each part. Each tool comes '
        'from a module; the sections below say what each module is for. A tool named <module>_<verb> takes the '
        "verb's nouns and switches as named arguments. A tool error ends with the one next step to take. For any "
        "module's full help, run metaform help <module>.\n\n"
        'If you cannot continue, stop and submit a trouble report with the feedback tool, attaching what you have in '
        'its shape field; do not retry.')
DEBUG = ('Submit feedback on the Metaform process with the feedback tool: bad semantics, a tool that did not match '
         'its schema, where you got stuck.')
CHASSIS_TOOLS = {'set', 'feedback', 'list_reports', 'read_report'}


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
    enabled = sorted(line.split()[0] for line in run('list', 'modules', cwd=mapped).stdout.splitlines()
                     if line.split()[1] == 'on')
    sections = [line[3:] for line in instructions.splitlines() if line.startswith('## ')]
    assert instructions.startswith(BASE + '\n\n## ') and sections == enabled
    assert "## map\nReads and writes this project's functional map." in instructions
    assert ('## memory\nNotes that agents keep at the map\'s own nodes, in the reference memory server\'s operations.'
            in instructions)
    assert '## mcp\nServes Metaform\'s tools to AI tools over MCP. Every tool is also a metaform command on the CLI. ' \
           'Details: metaform help mcp.' in instructions
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
    assert schema == {'type': 'boolean', 'description': 'Use tmux.'}
    assert json.loads(off[-1]) == {'tmux': False} and json.loads(stored[-1]) == {'tmux': True}
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert (shown['tmux']['value'], shown['tmux']['state']) == (True, 'glued')


@pytest.mark.req('MCP-006')
@pytest.mark.req('BASE-013')
def test_tool_errors_end_with_the_one_next_step_the_cli_gives(run, home, mapped):
    run('enable', 'helloworld')
    run('helloworld', 'greet', 'ada', cwd=mapped)
    cli = run('map', 'element', 'code.nothing', cwd=mapped, ok=False).stderr.splitlines()

    async def call(client, init):
        missing = await client.call_tool('map_element', {'element': 'code.nothing'})
        caution = await client.call_tool('helloworld_forget', {})
        return missing.is_error, text(missing), caution.is_error, text(caution)
    error, missing, caution_error, caution = session(home, mapped, call)
    assert error and missing[0].splitlines() == cli
    assert caution_error and caution[0].splitlines() == [
        'Error: This deletes the greeting history.', 'Next: If you are sure: call helloworld_forget with confirm true']
    assert run('helloworld', 'history', cwd=mapped).stdout.split() == ['ada']


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


@pytest.mark.req('STORE-028')
@pytest.mark.req('LAYER-007')
def test_a_masked_layer_is_absent_from_the_tool_read_too(run, home, mapped):
    run('map', 'knowledge', 'op=create', 'layer=notes', 'variable=Notes.', 'mutable=true', 'hideable=true',
        'module=test', cwd=mapped)
    run('map', 'knowledge', 'op=add-item', 'layer=notes', 'node=element:code.timer.kitchen', 'value="n"', cwd=mapped)
    run('map', 'knowledge', 'op=finish', 'layer=notes', cwd=mapped)
    run('map', 'mask', 'code.timer', 'notes', cwd=mapped)

    async def call(client, init):
        return text(await client.call_tool('map_node', {'node': 'element:code.timer.kitchen'}))
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
        return tools, text(await client.call_tool('declared_later', {}))
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
        return (await client.call_tool('set', {'modules': ['map', 'mcp'], 'layers': ['intake-1']})).is_error
    assert session(home, mapped, call) is False

    def values(folder):
        rows = json.loads(run('config', '--show', '--json', cwd=folder).stdout)
        return {row['key']: (row['value'], row['state']) for row in rows if row['key'] in ('modules', 'layers')}
    assert values(mapped) == values(other)


@pytest.mark.req('MCP-007')
@pytest.mark.req('CLI-034')
@pytest.mark.req('BASE-044')
def test_the_instructions_always_carry_the_stop_rule_and_ask_for_feedback_only_under_debug(run, home, mapped):
    async def instructions(client, init):
        return init.instructions
    plain = session(home, mapped, instructions)
    assert plain.startswith(BASE + '\n\n## ') and DEBUG not in plain
    run('set', '--debug', cwd=mapped)
    debugging = session(home, mapped, instructions)
    assert debugging.startswith(BASE + '\n\n' + DEBUG + '\n\n## ')
    assert run('help', 'agents', cwd=mapped).stdout == debugging


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
        said = await client.call_tool('feedback', {'text': 'Narrowed to solo.'})
        listed = await client.call_tool('list_reports', {})
        name = json.loads(text(said)[-1])['files'][0]
        read = await client.call_tool('read_report', {'name': name})
        refused = await client.call_tool('map_where', {'address': 'code'})
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
    run('enable', 'helloworld')
    missing_cli = run('helloworld', 'greet', cwd=mapped, ok=False).stderr.splitlines()[-1]

    async def call(client, init):
        missing = await client.call_tool('helloworld_greet', {})
        as_text = await client.call_tool('helloworld_greet', {'name': 'x', 'loud': 'no'})
        not_number = await client.call_tool('helloworld_wait', {'seconds': 'abc'})
        not_text = await client.call_tool('helloworld_greet', {'name': {'a': 1}})
        bad_set = await client.call_tool('set', {'loud': 'no'})
        return [(result.is_error, text(result)) for result in (missing, as_text, not_number, not_text, bad_set)]
    results = session(home, mapped, call)
    assert all(error for error, _ in results)
    assert all(len([line for line in blocks[0].splitlines() if line.startswith('Next: ')]) == 1
               for _, blocks in results)
    assert results[0][1][0].splitlines()[-1] == missing_cli
    assert run('helloworld', 'history', cwd=mapped).stdout.startswith('No greetings')
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)}
    assert shown['loud']['state'] == 'default'


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('MCP-002')
def test_a_string_for_elements_over_mcp_is_one_notice_and_never_reads_a_file_or_stdin(run, home, mapped, tmp_path):
    secret = tmp_path / 'elements.json'
    secret.write_text(json.dumps([{'namespace_address': 'code.leak', 'role': 'DE'}]), encoding='utf-8')

    async def call(client, init):
        dashed = await client.call_tool('intake_submit', {'elements': '-'})
        pathed = await client.call_tool('intake_submit', {'elements': str(secret)})
        still = await client.call_tool('map_layers', {})
        return [(result.is_error, json.loads(text(result)[-1])) for result in (dashed, pathed)], still.is_error
    results, still_error = session(home, mapped, call)
    for error, report in results:
        assert error is False and len(report['notices']) == 1 and report['notices'][0]['where'] == 'elements'
    assert still_error is False
    assert Store('proj').element('code.leak', raw=True) is None


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
        origin = json.loads(text(await client.call_tool('add_origin', {}))[-1])
        variant = json.loads(text(await client.call_tool('add_variant', {'folder': str(work), 'workflow': 'mutate',
                                                                           'blinded': False}))[-1])
        listed = json.loads(text(await client.call_tool('list_variants', {}))[-1])
        written = json.loads(text(await client.call_tool('extract', {'variants': [variant['variant_id']],
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
