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
TOOLS = {'intake_prompt', 'intake_start', 'intake_element', 'intake_join', 'intake_subtype',
         'intake_show', 'intake_finish', 'memory_create_entities', 'memory_open_nodes', 'map_select', 'map_mask',
         'map_clear', 'map_node', 'map_layers', 'map_tag', 'map_untag', 'map_knowledge', 'map_work', 'feedback',
         'list_reports', 'read_report', 'set'}
ENTERED = ('intake', 'map', 'memory', 'web')


def asked(host, name, arguments, *, limit):
    """Run a command as an agent does, CLI-037: the tool it belongs to, its command, and its arguments."""
    tool = next((one for one in ENTERED if name.startswith(one + '_')), 'metaform')
    return host.call(tool, {'command': name if tool == 'metaform' else name[len(tool) + 1:], 'arguments': arguments},
                     limit=limit)


def commands(host):
    """Every command the server offers, by the name it runs under, read by entering each tool."""
    found = set()
    for tool in host.request('tools/list', {}, deadline=_deadline())['tools']:
        for one in last_json(host.call(tool['name'], {}, limit=LIMIT))['commands']:
            found.add(one['command'] if tool['name'] == 'metaform' else f"{tool['name']}_{one['command']}")
    return found


REPORT = 'The alarm pin is never released after stop.'
FEEDBACK = 'The subtype provider field repeats the element address.'
CURSOR = {'mcpServers': {'other': {'command': 'other-server', 'args': ['--port', '1']}}}
LIMIT = 180.0


def texts(result):
    return [block['text'] for block in result.get('content', []) if block.get('type') == 'text']


def last_json(result):
    return json.loads(texts(result)[-1])


def memory_values(view):
    """The observations of the memories a node read shows, LAYER-013."""
    return [text for entity in view.get('memory', {}).get('entities', []) for text in entity['observations']]


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
                                text=True, encoding='utf-8', timeout=600)
        if ok:
            assert result.returncode == 0, f'metaform {" ".join(args)}:\n{result.stdout}{result.stderr}'
        return result

    # 1 and 2: build the wheel, then install for Claude Code, Codex and Cursor.
    built = metaform('build').stdout
    wheel = Path(re.search(r'^Wheel: (.+)$', built, re.MULTILINE).group(1))
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
        assert re.search(rf'^  {tool}: server starts, \d+ tools$', installed, re.MULTILINE), installed
    assert installed.splitlines()[-1].startswith('Next: ')

    # 3: register a project; it has no intake.
    project = tmp_path / 'kitchen timer'
    project.mkdir()
    metaform('add', 'project', 'timer', str(project))

    def connect():
        return open_session(command, cwd=project, env=env, limit=LIMIT)

    # 4: the agent's connection exposes the module tools.
    host, _ = connect()
    try:
        tools = {tool['name'] for tool in host.request('tools/list', {}, deadline=_deadline())['tools']}
        assert tools == {'intake', 'map', 'memory', 'web', 'metaform'}
        listed = commands(host)
        assert TOOLS <= listed and not any(name.startswith(('hello_', 'template_')) for name in listed)

        # 5 and 6: the subagent reads its instructions by name, unaltered.
        served = texts(asked(host, 'intake_prompt', {}, limit=LIMIT))[-1]
        body, _, footer = served.partition('</process>\n')
        body += '</process>\n'
        assert footer == ''  # nothing is served beside the intake
        assert body == SPEC.read_text(encoding='utf-8').replace('{prompt}', '', 1)

        # 7: the intake is recorded one object per call; a join missing its purpose is stored with a notice naming
        # that field, and nothing is refused.
        submission = copy.deepcopy(FIXTURE)
        del submission['elements'][0]['joins'][0]['purpose']
        noticed = []

        def record(tool, arguments):
            result = asked(host, tool, arguments, limit=LIMIT)
            assert result.get('isError') is not True, texts(result)
            out = last_json(result)
            noticed.extend(notice['where'] for notice in out.get('notices', []))
            return out

        record('intake_start', {'model': 'fixture', 'role': 'intake subagent'})
        for element in submission['elements']:
            record('intake_element', {'namespace_address': element['namespace_address'],
                                      **{key: value for key, value in element.items()
                                         if key in ('role', 'name', 'name_length', 'refs')}})
        for element in submission['elements']:
            for join in element.get('joins', []):
                made = record('intake_join', {'receiver': element['namespace_address'], **{
                    key: value for key, value in join.items() if key != 'subtypes'}})
                for subtype in join.get('subtypes', []):
                    inner = subtype['element']
                    record('intake_subtype', {'into': made['join_id'], 'namespace_address': inner['namespace_address'],
                                              **{key: value for key, value in subtype.items() if key != 'element'},
                                              **{key: value for key, value in inner.items()
                                                 if key in ('role', 'name', 'name_length', 'refs')}})
        # The condition of an object is a work record, apart from the map, written by the same agent through
        # map_work while the intake is being recorded, MAP-046.
        record('map_work', {'op': 'add', 'node': 'element:code.alarm.audible', 'condition': 'broken',
                            'note': 'the pin is never released', 'task': 'release it after stop'})
        report = record('intake_finish', {'report': REPORT, 'feedback': FEEDBACK})
        assert (report['elements'], report['joins'], report['subtypes'], report['work']) == (4, 2, 1, 1)
        # Each element of the fixture carries its name, kept on the element with no notice, Rich 2026-10-01.
        assert noticed == ['purpose']
    finally:
        host.close()

    # On a new connection the report, the feedback and the work record are there to read.
    first, _ = connect()
    second = None
    try:
        listed = last_json(asked(first, 'list_reports', {}, limit=LIMIT))['results']
        by_kind = {row['kind']: row['name'] for row in listed}
        assert sorted(by_kind) == ['feedback', 'report']
        assert texts(asked(first, 'read_report', {'name': by_kind['report']}, limit=LIMIT)) == [REPORT]
        assert texts(asked(first, 'read_report', {'name': by_kind['feedback']}, limit=LIMIT)) == [FEEDBACK]
        broken = last_json(asked(first, 'map_work', {'condition': 'broken'}, limit=LIMIT))['results']
        assert [(row['address'], row['task']) for row in broken] == [('code.alarm.audible', 'release it after stop')]
        said = last_json(asked(first, 'feedback', {'text': 'The first working test ran.'}, limit=LIMIT))
        relisted = {row['name'] for row in last_json(asked(first, 'list_reports', {}, limit=LIMIT))['results']}
        assert set(said['files']) <= relisted and len(relisted) == 3

        # 8: an agent writes a memory at the DE element and at one join.
        joins = last_json(asked(first, 'map_joins', {'element': 'code.timer.kitchen'}, limit=LIMIT))['results']
        join_id = joins[0]['join_id']
        assert joins[0]['receiver_address'] == 'code.timer.kitchen'
        at_element = asked(first, 'memory_create_entities', {
            'node': 'element:code.timer.kitchen',
            'entities': [{'name': 'countdown drift', 'entityType': 'behavior',
                          'observations': ['The countdown drifts under load.']}]}, limit=LIMIT)
        at_join = asked(first, 'memory_create_entities', {
            'node': f'join:{join_id}',
            'entities': [{'name': 'quiet tone', 'entityType': 'behavior',
                          'observations': ['The tone is too quiet in a loud kitchen.']}]}, limit=LIMIT)
        assert at_element.get('isError') is not True and at_join.get('isError') is not True

        # 9: a second agent, on its own connection, reads both back at their nodes.
        second, _ = connect()
        opened = [last_json(asked(second, 'memory_open_nodes', {'node': node, 'names': [name]}, limit=LIMIT))
                  for node, name in (('element:code.timer.kitchen', 'countdown drift'),
                                     (f'join:{join_id}', 'quiet tone'))]
        assert [found['entities'][0]['observations'] for found in opened] == [
            ['The countdown drifts under load.'], ['The tone is too quiet in a loud kitchen.']]
        elsewhere = last_json(asked(second, 'memory_open_nodes', {'node': 'element:code.timer.kitchen',
                                                                   'names': ['quiet tone']}, limit=LIMIT))
        assert elsewhere['entities'] == []  # the join's memory is not the element's

        # 10: a mask of the memory layer at the element's address hides it there; clearing shows it again.
        element_view = last_json(asked(second, 'map_node', {'node': 'element:code.timer.kitchen'}, limit=LIMIT))
        assert memory_values(element_view) == ['The countdown drifts under load.']
        asked(second, 'map_mask', {'address': 'code.timer.kitchen', 'layer': 'memory'}, limit=LIMIT)
        masked = asked(second, 'map_node', {'node': 'element:code.timer.kitchen'}, limit=LIMIT)
        assert memory_values(last_json(masked)) == []
        join_masked = last_json(asked(second, 'map_node', {'node': f'join:{join_id}'}, limit=LIMIT))
        assert memory_values(join_masked) == []
        asked(second, 'map_clear', {'address': 'code.timer.kitchen', 'layer': 'memory', 'kind': 'mask'}, limit=LIMIT)
        cleared = last_json(asked(second, 'map_node', {'node': 'element:code.timer.kitchen'}, limit=LIMIT))
        assert memory_values(cleared) == ['The countdown drifts under load.']
        join_view = last_json(asked(second, 'map_node', {'node': f'join:{join_id}'}, limit=LIMIT))
        assert memory_values(join_view) == ['The tone is too quiet in a loud kitchen.']

    finally:
        first.close()
        if second is not None:
            second.close()
    assert probe(command, cwd=user, env=env, limit=LIMIT).ok


def _deadline():
    import time
    return time.monotonic() + LIMIT
