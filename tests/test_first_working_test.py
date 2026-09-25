"""MCP-024, the first working test: installer, instructions and delegation end to end, then shared memory.

Automated with a temporary Metaform home and user home, fake `claude` and
`codex` executables that record their arguments, a real Cursor config file,
the real `uv` and `uvx`, and the probe client of MCP-017 as the scripted host.
It needs network access or a warm uv cache for uvx to prepare the server.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fakes import calls, recorder

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('MCP-024')]

ROOT = Path(__file__).parents[1]
SPEC = ROOT / 'specifications' / 'Canonical_Intake.xml'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))
NOTICE = ('This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions '
          'with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.')
BASE = ("Metaform keeps this project's functional map: what each part is for, who receives what it does, and how.")
TOOLS = {'intake_prompt', 'intake_submit', 'memory_add-observations', 'memory_open-nodes', 'map_select', 'map_mask',
         'map_clear', 'map_node', 'map_layers', 'map_tag', 'map_untag', 'map_knowledge', 'set'}
CURSOR = {'mcpServers': {'other': {'command': 'other-server', 'args': ['--port', '1']}}}
LIMIT = 180.0


def texts(result):
    return [block['text'] for block in result.get('content', []) if block.get('type') == 'text']


def last_json(result):
    return json.loads(texts(result)[-1])


def memory_values(view, layer='memory'):
    return [item['value'] for group in view['layers'] if group['layer'] == layer for item in group['items']]


def test_a_fresh_machine_reaches_shared_memory_under_layer_selection(tmp_path):
    from metaform.probe import open_session, probe

    uvx = shutil.which('uvx')
    uv = shutil.which('uv')
    if uvx is None or uv is None:
        pytest.fail('The first working test needs uv and uvx on PATH, MCP-013.')
    metaform_home = tmp_path / 'metaform-home'
    user = tmp_path / 'user'
    user.mkdir()
    fakes = tmp_path / 'fakes'
    recorder(fakes, 'claude')
    recorder(fakes, 'codex')
    (user / '.cursor').mkdir()
    cursor_file = user / '.cursor' / 'mcp.json'
    cursor_file.write_text(json.dumps(CURSOR, indent=2), encoding='utf-8')
    cursor_before = cursor_file.read_bytes()
    env = {**os.environ, 'METAFORM_HOME': str(metaform_home), 'HOME': str(user), 'USERPROFILE': str(user),
           'PATH': os.pathsep.join([str(fakes), str(Path(uvx).parent), str(Path(uv).parent),
                                    os.environ.get('PATH', '')])}
    env.pop('METAFORM_WHEEL', None)

    def metaform(*args, cwd=tmp_path, ok=True):
        result = subprocess.run([sys.executable, '-m', 'metaform', *args], cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=600)
        if ok:
            assert result.returncode == 0, f'metaform {" ".join(args)}:\n{result.stdout}{result.stderr}'
        return result

    # 1 and 2: build the wheel, then install for Claude Code, Codex and Cursor.
    built = metaform('build').stdout
    wheel = Path(re.search(r'^Wheel: (.+)$', built, re.M).group(1))
    installed = metaform('install', 'claude', 'codex', 'cursor').stdout
    command = ['uvx', '--from', str(wheel), 'metaform', 'mcp', 'serve']
    assert calls(fakes, 'claude')[-1] == ['mcp', 'add', '--transport', 'stdio', '--scope', 'user', 'metaform', '--',
                                          *command]
    assert calls(fakes, 'codex')[-1] == ['mcp', 'add', 'metaform', '--', *command]
    merged = json.loads(cursor_file.read_text())
    assert merged['mcpServers']['other'] == CURSOR['mcpServers']['other']
    assert merged['mcpServers']['metaform'] == {'command': 'uvx', 'args': command[1:]}
    backups = list((metaform_home / 'backups' / 'install').rglob('mcp.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == cursor_before
    skill = (ROOT / 'src' / 'metaform' / 'skill' / 'SKILL.md').read_bytes()
    for copy_of_skill in (metaform_home / 'skills' / 'metaform' / 'SKILL.md',
                          user / '.agents' / 'skills' / 'metaform' / 'SKILL.md',
                          user / '.claude' / 'skills' / 'metaform' / 'SKILL.md',
                          user / '.codex' / 'skills' / 'metaform' / 'SKILL.md',
                          user / '.cursor' / 'skills' / 'metaform' / 'SKILL.md'):
        assert copy_of_skill.read_bytes() == skill
    for tool in ('claude', 'codex', 'cursor'):
        assert re.search(rf'^  {tool}: server starts, \d+ tools$', installed, re.M), installed
    assert installed.splitlines()[-1].startswith('Next: ')

    # 3: register a project; it has no intake.
    project = tmp_path / 'kitchen timer'
    project.mkdir()
    metaform('add', 'project', 'timer', str(project))

    def connect():
        return open_session(command, cwd=project, env=env, limit=LIMIT)

    # 4: the agent's connection carries the base text, each module's section and the notice.
    host, initialized = connect()
    try:
        instructions = initialized['instructions']
        assert instructions.startswith(BASE)
        assert [line[3:] for line in instructions.splitlines() if line.startswith('## ')] == [
            'intake', 'map', 'mcp', 'memory']
        assert instructions.rstrip().endswith(NOTICE)
        listed = {tool['name'] for tool in host.request('tools/list', {}, deadline=_deadline())['tools']}
        assert TOOLS <= listed and not any(name.startswith(('helloworld_', 'template_')) for name in listed)

        # 5 and 6: the subagent reads its instructions by name, unaltered.
        served = texts(host.call('intake_prompt', {}, limit=LIMIT))[-1]
        submit_line = '\n\nSubmit the result with intake_submit, or metaform intake submit on the command line.\n'
        assert served.endswith(submit_line)
        stored = SPEC.read_text(encoding='utf-8')
        body = served[:-len(submit_line) + 1]
        assert re.sub(r'<target [^>]*>', '<target>', body, count=1) == \
            re.sub(r'<target [^>]*>', '<target>', stored, count=1)
        assert re.search(r'<target [^>]*type="path"[^>]*value="[^"]*kitchen timer"', body)

        # 7: a submission missing one purpose is refused whole; the corrected one is stored.
        broken = copy.deepcopy(FIXTURE)
        del broken['elements'][0]['joins'][0]['purpose']
        refused = host.call('intake_submit', broken, limit=LIMIT)
        assert refused.get('isError') is True
        assert 'elements[0].joins[0]: purpose is required' in texts(refused)[0]
    finally:
        host.close()
    status = metaform(cwd=project).stdout
    assert NOTICE in status
    host, initialized = connect()
    try:
        assert initialized['instructions'].rstrip().endswith(NOTICE)
        stored_result = host.call('intake_submit', {**FIXTURE, 'model': 'fixture', 'role': 'intake subagent'},
                                  limit=LIMIT)
        assert stored_result.get('isError') is not True, texts(stored_result)
        report = last_json(stored_result)
        assert (report['elements'], report['joins'], report['subtypes']) == (3, 2, 1)
    finally:
        host.close()

    # A new connection no longer shows the notice.
    first, initialized = connect()
    second = None
    try:
        assert NOTICE not in initialized['instructions']

        # 8: an agent writes a memory at the DE element and at one join.
        joins = last_json(first.call('map_joins', {'element': 'code.timer.kitchen'}, limit=LIMIT))['results']
        join_id = joins[0]['join_id']
        assert joins[0]['receiver_address'] == 'code.timer.kitchen'
        at_element = first.call('memory_add-observations', {'node': 'element:code.timer.kitchen',
                                                            'text': ['The countdown drifts under load.']}, limit=LIMIT)
        at_join = first.call('memory_add-observations', {'node': f'join:{join_id}',
                                                         'text': ['The tone is too quiet in a loud kitchen.']},
                             limit=LIMIT)
        assert at_element.get('isError') is not True and at_join.get('isError') is not True

        # 9: a second agent, on its own connection, reads both back.
        second, _ = connect()
        opened = last_json(second.call('memory_open-nodes', {'node': ['element:code.timer.kitchen',
                                                                        f'join:{join_id}']}, limit=LIMIT))
        assert [node['observations'] for node in opened['nodes']] == [
            ['The countdown drifts under load.'], ['The tone is too quiet in a loud kitchen.']]

        # 10: a mask of the memory layer at the element's address hides it there; clearing shows it again.
        element_view = last_json(second.call('map_node', {'node': 'element:code.timer.kitchen'}, limit=LIMIT))
        assert memory_values(element_view) == ['The countdown drifts under load.']
        second.call('map_mask', {'address': 'code.timer.kitchen', 'layer': 'memory'}, limit=LIMIT)
        masked = second.call('map_node', {'node': 'element:code.timer.kitchen'}, limit=LIMIT)
        assert memory_values(last_json(masked)) == []
        join_masked = last_json(second.call('map_node', {'node': f'join:{join_id}'}, limit=LIMIT))
        assert memory_values(join_masked) == []
        second.call('map_clear', {'address': 'code.timer.kitchen', 'layer': 'memory', 'kind': 'mask'}, limit=LIMIT)
        cleared = last_json(second.call('map_node', {'node': 'element:code.timer.kitchen'}, limit=LIMIT))
        assert memory_values(cleared) == ['The countdown drifts under load.']
        join_view = last_json(second.call('map_node', {'node': f'join:{join_id}'}, limit=LIMIT))
        assert memory_values(join_view) == ['The tone is too quiet in a loud kitchen.']

    finally:
        first.close()
        if second is not None:
            second.close()
    assert probe(command, cwd=user, env=env, limit=LIMIT).ok


def _deadline():
    import time
    return time.monotonic() + LIMIT
