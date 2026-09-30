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
def test_the_instructions_are_the_instructions_prompt_with_the_surfaced_modules_listed(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    element = prompt(SOURCE / 'resources' / 'prompts.xml', 'instructions')
    on = [line.split()[0] for line in run('list', 'modules', cwd=folder).stdout.splitlines() if line.split()[1] == 'on']
    listed = '\n'.join(prompt(SOURCE / 'modules' / module / 'resources' / 'prompts.xml', 'instructions').text
                       for module in sorted(on))
    assert [child.tag for child in element] == ['modules']
    expected = (element.text or '') + listed + (element[0].tail or '')
    assert run('help', 'agents', cwd=folder).stdout.strip() == expected.strip()


@pytest.mark.req('MCP-031')
def test_module_notices_are_not_added_to_the_instructions(run, home, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    served = run('help', 'agents', cwd=folder).stdout
    for module in ('intake', 'web'):
        assert prompt(SOURCE / 'modules' / module / 'resources' / 'prompts.xml', 'notice').text.strip() not in served
