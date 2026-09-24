"""Stage 2: metaform mcp serves module verbs as tools, from the same declarations as the CLI."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FIXTURE = Path(__file__).parent / 'fixtures' / 'kitchen_timer.xml'


def session(home, folder, fn):
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    async def go():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                init = await client.initialize()
                return await fn(client, init)
    return asyncio.run(go())


def text(result):
    return ''.join(item.text for item in result.content if getattr(item, 'text', None))


def setup(run, tmp_path):
    work = tmp_path / 'kitchen'
    work.mkdir()
    run('add', 'project', 'kitchen', str(work))
    run('map', 'import', str(FIXTURE), cwd=work)
    return work


def test_tools_match_module_verbs_and_instructions_carry_purposes(run, home, tmp_path):
    work = setup(run, tmp_path)

    async def check(client, init):
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
        return init.instructions, tools
    instructions, tools = session(home, work, check)
    assert {'map_where', 'map_element', 'map_list', 'map_import', 'template_greet'} <= set(tools)
    assert "Holds the project's functional map" in instructions
    assert 'Shows how a module declares verbs' in instructions
    schema = tools['template_greet'].input_schema
    assert schema['properties']['nouns']['type'] == 'array'
    assert schema['properties']['loud']['type'] == 'boolean'


def test_tool_returns_the_same_answer_as_the_cli(run, home, tmp_path):
    work = setup(run, tmp_path)
    cli = run('map', 'where', 'src/tick.c', '--json', cwd=work).stdout

    async def call(client, init):
        return text(await client.call_tool('map_where', {'nouns': ['src/tick.c'], 'json': True}))
    assert json.loads(session(home, work, call)) == json.loads(cli)


def test_tool_error_names_the_next_step(run, home, tmp_path):
    work = setup(run, tmp_path)

    async def call(client, init):
        result = await client.call_tool('map_element', {'nouns': ['code.nothing']})
        return result.is_error, text(result)
    error, message = session(home, work, call)
    assert error
    assert message.splitlines() == ['Error: No element or internal subtype at code.nothing.', 'Next: metaform map list']


def test_command_surface_narrows_the_tools(run, home, tmp_path):
    work = setup(run, tmp_path)
    run('set', '--commands', 'map', cwd=work)

    async def check(client, init):
        return {tool.name for tool in (await client.list_tools()).tools}
    names = session(home, work, check)
    assert 'map_where' in names and 'template_greet' not in names


def test_caution_verbs_take_confirm_over_mcp(run, home, tmp_path):
    work = setup(run, tmp_path)
    run('template', 'greet', 'ada', cwd=work)

    async def call(client, init):
        first = await client.call_tool('template_forget', {})
        second = await client.call_tool('template_forget', {'confirm': True})
        return first.is_error, text(first), second.is_error
    error, message, second_error = session(home, work, call)
    assert error and message.splitlines() == ['Error: This deletes the greeting history.',
                                             'Next: If you are sure: call template_forget with confirm true']
    assert not second_error
