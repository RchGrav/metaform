"""The first run, MCP-009: a person opens their AI tool in a folder Metaform has never seen, and the agent is told,
at connect, everything it needs to take them from one question to a mapped project."""
from __future__ import annotations

from importlib import resources

import pytest

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
    """Run a command as an agent does: its own tool, `<module>_<command>` or `metaform_<command>`."""
    return await client.call_tool(f'{tool}_{command}', arguments or {})


def test_the_first_run_notice_stands_on_its_own_line_in_the_guide(run, home, tmp_path):
    folder = tmp_path / 'unseen'
    lines = run('help', 'agents', cwd=folder).stdout.splitlines()
    assert prompt_files.required(INTAKE, 'connect') in lines
    assert any(line.startswith('FIRST RUN.') for line in lines)


def test_the_metaform_instructions_are_the_glossary(run, home, tmp_path):
    written = (prompt_files.module('mcp', 'glossary') or '').strip()
    assert run('instructions', 'metaform').stdout == written + '\n'
