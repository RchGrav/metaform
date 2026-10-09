"""The first run, MCP-009: a person opens their AI tool in a folder Metaform has never seen, and the agent is told,
at connect, everything it needs to take them from one question to a mapped project."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from importlib import resources

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from metaform import prompt_files

pytestmark = [pytest.mark.req('MCP-009'), pytest.mark.req('MCP-029'), pytest.mark.kind('real')]

INTAKE = resources.files('metaform.modules.intake')


def onboarding(registered: bool) -> str:
    """The onboarding as served: step 3a, registering the folder, only while the folder is not registered."""
    step = '' if registered else '   ' + prompt_files.required(INTAKE, 'register_step') + '\n'
    return prompt_files.required(INTAKE, 'no_intake', register=step)


def text(result):
    return [item.text for item in result.content if getattr(item, 'text', None) is not None]


async def call(client, tool, command, arguments=None):
    return await client.call_tool(tool, {'command': command, 'arguments': arguments or {}})


def test_a_first_run_in_an_unregistered_folder_goes_from_the_question_to_a_recorded_intake(run, home, tmp_path):
    for module in [line.split()[0] for line in run('list', 'modules').stdout.splitlines() if line.split()[1] != 'on']:
        run('enable', module)  # the size limit holds with every shipped module on
    folder = tmp_path / 'My Project'
    folder.mkdir()
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    async def first_run(client, init):
        said = init.instructions
        assert onboarding(registered=False) in said and len(said) <= 2048, len(said)
        assert said.index('FIRST RUN.') < 200  # near the top, inside what every host shows
        # every command and resource the onboarding names exists on the surface
        tools = {tool.name for tool in (await client.list_tools()).tools}
        assert {'metaform', 'web', 'intake'} <= tools
        commands = {name: [one['command'] for one in json.loads(text(await client.call_tool(name, {}))[-1])['commands']]
                    for name in ('metaform', 'web', 'intake')}
        assert 'register' in commands['metaform'] and 'start' in commands['web']
        uris = {str(one.uri) for one in (await client.list_resources()).resources}
        assert {'metaform://intake/procedure', 'metaform://intake/schema'} <= uris
        # step 3a: the folder is registered under its own name, and the answer brings the onboarding without it
        registered = await call(client, 'metaform', 'register')
        assert not registered.is_error, text(registered)
        answer = json.loads(text(registered)[-1])
        assert answer['project'] == 'my-project'
        assert onboarding(registered=True) in answer['instructions']
        assert 'a. Register this folder' not in answer['instructions']
        again = json.loads(text(await call(client, 'metaform', 'register'))[-1])
        assert again['project'] == 'my-project' and 'nothing was changed' in again['said']
        # step 3c: the subagent handed only the procedure finds the schema from it, and the intake tools work
        procedure = (await client.read_resource('metaform://intake/procedure')).contents[0].text
        assert procedure.rstrip().endswith(prompt_files.required(INTAKE, 'schema_pointer'))
        started = await call(client, 'intake', 'start')
        assert not started.is_error, text(started)

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            return await first_run(client, await client.initialize())
    asyncio.run(go())


def test_an_intake_command_in_an_unregistered_folder_names_the_register_command(home, tmp_path):
    folder = tmp_path / 'fresh'
    folder.mkdir()
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=str(folder),
                                   env={**os.environ, 'METAFORM_HOME': str(home)})

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as client:
            await client.initialize()
            return await call(client, 'intake', 'start')
    refused = asyncio.run(go())
    assert refused.is_error
    assert text(refused)[-1].splitlines()[-1] == 'Next: call metaform with command register'
