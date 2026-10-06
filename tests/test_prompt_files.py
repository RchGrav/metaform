"""Prompt files: every prompt an agent reads is authored in an XML file, addressed by name, and never in Python."""
from __future__ import annotations

import ast
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('fixture')

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'metaform'


def prompt_files() -> list[Path]:
    return sorted(SOURCE.glob('**/resources/prompts.xml'))


def prompt(path: Path, name: str) -> ET.Element:
    found = ET.parse(path).getroot().find(name)
    assert found is not None, f'{path} has no prompt {name}'
    return found


@pytest.mark.req('MCP-031')
def test_the_chassis_and_the_modules_that_prompt_agents_keep_their_prompts_in_xml():
    held = {path.relative_to(SOURCE).as_posix() for path in prompt_files()}
    assert {'resources/prompts.xml', 'modules/intake/resources/prompts.xml', 'modules/map/resources/prompts.xml',
            'modules/web/resources/prompts.xml', 'modules/mcp/resources/prompts.xml'} <= held


def literals(path: Path) -> set[str]:
    """Every string a Python file writes, with implicitly joined pieces as one string, as Python reads them."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(' '.join(node.value.split()))
    return found


@pytest.mark.req('MCP-031')
def test_no_prompt_text_is_written_in_python():
    python = {path: literals(path) for path in SOURCE.glob('**/*.py') if 'tests' not in path.parts}
    for path in prompt_files():
        for element in ET.parse(path).getroot():
            for piece in [element.text or ''] + [child.tail or '' for child in element]:
                for line in piece.splitlines():
                    line = ' '.join(line.split())
                    if len(line) < 25:
                        continue
                    holders = [str(source.relative_to(SOURCE)) for source, strings in python.items()
                               if any(line in string for string in strings)]
                    assert not holders, f'{path.relative_to(SOURCE)} {element.tag}: "{line}" is in {holders}'


@pytest.mark.req('MCP-031')
def test_the_full_instructions_are_the_instructions_prompt_with_the_surfaced_modules_listed(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('set', '--connect-instructions=full', cwd=folder)
    run('set', '--no-web-autostart', cwd=folder)  # the web message, VIEW-015, is tested with the web module
    run('set', '--no-tasks', cwd=folder)  # the task lines are tested below
    element = prompt(SOURCE / 'resources' / 'prompts.xml', 'instructions')
    on = [line.split()[0] for line in run('list', 'modules', cwd=folder).stdout.splitlines() if line.split()[1] == 'on']
    def line(module):  # a module's instructions prompt; a project with no intake also gets the notice, MCP-009
        own = prompt(SOURCE / 'modules' / module / 'resources' / 'prompts.xml', 'instructions').text.strip()
        notice = ET.parse(SOURCE / 'modules' / module / 'resources' / 'prompts.xml').getroot().findtext('no_intake')
        return own if notice is None else f'{own} {notice}'
    listed = '\n'.join(line(module) for module in sorted(on))
    assert [child.tag for child in element] == ['modules']
    expected = (element.text or '') + listed + (element[0].tail or '')
    assert run('help', 'agents', cwd=folder).stdout.strip() == expected.strip()


INTAKE = (('element', 'code.timer.kitchen', 'role=DE', 'name_length=2', 'name=kitchen timer'),
          ('element', 'code.alarm.audible', 'role=SE', 'name_length=2', 'name=alarm'),
          ('join', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=Get attention.', 'ef=Rings.',
           'ifd=receives'))


@pytest.mark.req('MCP-029')
@pytest.mark.req('MCP-031')
def test_the_compact_instructions_fit_what_claude_code_keeps_in_every_intake_state(run, home, tmp_path):
    """Claude Code keeps the first 2,048 characters of a server's instructions and drops the rest, so the whole
    default text must fit before an intake, while one is recorded and after it, with every shipped module on."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    for module in [line.split()[0] for line in run('list', 'modules', cwd=folder).stdout.splitlines()
                   if line.split()[1] != 'on']:
        run('enable', module, cwd=folder)
    more = prompt(SOURCE / 'resources' / 'prompts.xml', 'more').text.strip()
    def served():
        text = run('help', 'agents', cwd=folder).stdout
        assert more in text and len(text) <= 2048, len(text)
        return text
    assert prompt(SOURCE / 'modules' / 'intake' / 'resources' / 'prompts.xml', 'no_intake').text.strip() in served()
    run('intake', 'start', cwd=folder)
    served()
    for step in INTAKE:
        run('intake', *step, cwd=folder)
    run('intake', 'finish', cwd=folder)
    served()


@pytest.mark.req('MCP-029')
def test_a_module_s_full_instructions_are_read_on_their_own(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('set', '--no-tasks', cwd=folder)
    own = prompt(SOURCE / 'modules' / 'map' / 'resources' / 'prompts.xml', 'instructions').text.strip()
    assert run('help', 'agents', 'map', cwd=folder).stdout.strip() == own
    assert run('instructions', 'map', cwd=folder).stdout.strip() == own
    assert own not in run('help', 'agents', cwd=folder).stdout


@pytest.mark.req('MCP-031')
@pytest.mark.req('MAP-048')
def test_the_kanban_lines_are_served_only_while_tasks_is_on(run, home, tmp_path):
    """Rich, 2026-10-01: agents assign and track work via Metaform like a kanban; a project that keeps its own board
    turns it off, and then the instructions say nothing of it. On by default."""
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    lines = prompt(SOURCE / 'modules' / 'map' / 'resources' / 'prompts.xml', 'tasks').text.strip()
    assert lines not in run('help', 'agents', cwd=folder).stdout  # no nodes to link work to before an intake
    run('intake', 'start', cwd=folder)
    for step in INTAKE:
        run('intake', *step, cwd=folder)
    run('intake', 'finish', cwd=folder)
    assert lines in run('help', 'agents', cwd=folder).stdout
    run('set', '--no-tasks', cwd=folder)
    assert lines not in run('help', 'agents', cwd=folder).stdout


@pytest.mark.req('MCP-031')
def test_the_trouble_report_and_debug_prompts_are_served_only_while_debug_is_on(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    chassis = SOURCE / 'resources' / 'prompts.xml'
    lines = [prompt(chassis, name).text.strip() for name in ('stop', 'debug')]
    served = run('help', 'agents', cwd=folder).stdout
    assert not any(line in served for line in lines)
    run('set', '--debug', cwd=folder)
    assert run('help', 'agents', cwd=folder).stdout.rstrip().endswith('\n\n'.join(lines))
