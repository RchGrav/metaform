"""The intake module: the Canonical Intake served by name, one atomic submission never blocked, intake state, BASE-039."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.kind('fixture')

ROOT = Path(__file__).parents[5]
SPEC = Path(__file__).parents[1] / 'resources' / 'digital_typology.xml'  # the served intake
RESOURCE = SPEC


def stored_with_pointer() -> str:
    """The served intake: the stored file, then, when it does not name its schema, the line saying where it is,
    MCP-009."""
    from importlib import resources

    from metaform import prompt_files
    if 'metaform://intake/schema' in SPEC.read_text(encoding='utf-8'):
        return SPEC.read_text(encoding='utf-8')
    pointer = prompt_files.required(resources.files('metaform.modules.intake'), 'schema_pointer', project='timer')
    return SPEC.read_text(encoding='utf-8').rstrip('\n') + '\n\n' + pointer + '\n'


def served_asked(asked: str) -> str:
    """The served intake with what the person asked: in an XML intake's prompt slot, escaped as an attribute value;
    after an Axiom intake, which has no slot, as data."""
    stored = stored_with_pointer()
    if SPEC.suffix == '.xml':
        escaped = asked.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        return stored.replace('{prompt}', escaped, 1)
    return stored.rstrip('\n') + f'\n\n<<DATA: Prompt>>\n{asked}\n<<END DATA>>\n' if asked else stored


def onboarding() -> str:
    """The onboarding as a registered folder is served it, MCP-009."""
    from importlib import resources

    from metaform import prompt_files
    return prompt_files.required(resources.files('metaform.modules.intake'), 'no_intake')
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'timer & co'
    folder.mkdir()
    run('add', 'project', 'timer', str(folder))
    return folder


OBJECT_KEYS = {'namespace_address', 'role', 'name', 'name_length', 'refs', 'joins'}
JOIN_KEYS = {'provider', 'purpose', 'ef', 'ifd', 'subtypes'}
# Each element of the fixture carries its name, which is stored on the element, with no notice.
NAMED: set[str] = set()
SUBTYPE_KEYS = {'element'}


def fields(given, names):
    """A record's fields as named arguments, a list or object as JSON. A field no tool names is sent as it is, so
    the chassis names it, BASE-043."""
    unknown = set(given) - (OBJECT_KEYS | JOIN_KEYS | SUBTYPE_KEYS)
    return [f'{name}={json.dumps(value) if isinstance(value, (list, dict)) else value}'
            for name, value in given.items() if name in names | unknown]


def submit(run, cwd, document, tmp_path, extra=(), as_json=True):
    """Record a document's elements and joins one object per call, as an intake agent does, then finish. A join of the
    document holds its provider and the element of each of its parts. The notices come back
    keyed by each object's place in the document and the field they name."""
    notes, calls = [], []

    def call(path, *args):
        result = run('intake', *args, '--json', cwd=cwd)
        calls.append(result)
        out = json.loads(result.stdout)
        notes.extend({'where': f'{path}.{notice["where"]}', 'message': notice['message']}
                     for notice in out.get('notices', []))
        return out

    start = [arg for arg in extra if arg.split('=', 1)[0] in ('model', 'role', 'name')]
    call('start', 'start', *start)
    elements = document['elements']
    for index, element in enumerate(elements):
        call(f'elements[{index}]', 'element', element.get('namespace_address', ''),
             *fields(element, {'role', 'name', 'name_length', 'refs'}))
        for number, join in enumerate(element.get('joins', [])):
            for place, subtype in enumerate(join.get('subtypes', [])):
                inner = subtype.get('element', {})
                call(f'elements[{index}].joins[{number}].subtypes[{place}].element', 'element',
                     inner.get('namespace_address', ''), *fields(inner, {'role', 'name', 'name_length', 'refs'}))
    for index, element in enumerate(elements):
        for number, join in enumerate(element.get('joins', [])):
            held = [join.get('provider', ''), *(subtype.get('element', {}).get('namespace_address', '')
                                                for subtype in join.get('subtypes', []))]
            call(f'elements[{index}].joins[{number}]', 'purpose', element['namespace_address'], json.dumps(held),
                 *fields(join, {'purpose', 'ef', 'ifd'}))
    finish = [arg for arg in extra if arg.split('=', 1)[0] in ('report', 'feedback')]
    finished = run('intake', 'finish', *finish, *(['--json'] if as_json else []), cwd=cwd)
    if not as_json:
        return finished
    report = json.loads(finished.stdout)
    report['notices'] = notes + [{'where': f'finish.{notice["where"]}', 'message': notice['message']}
                                 for notice in report.get('notices', [])]
    return report


def nouns_of(verb):
    from metaform.modules.intake import MODULE
    return {noun.name: noun for noun in next(item for item in MODULE.verbs if item.name == verb).nouns}


def notices(result):
    return {notice['where']: notice['message'] for notice in result['notices']}


def without_target(text):
    """The intake with what the server fills set aside: the prompt slot, and a target where an intake has one."""
    return re.sub(r'<target [^>]*>', '<target>', text.replace('{prompt}', '', 1), count=1)


def footer(text):
    return text.split('</process>\n', 1)[1]


@pytest.mark.req('BASE-039')
def test_only_the_axiom_intake_is_served():
    """The digital typology intake, compiled to Axiom, is the served intake, the one copy; the
    intakes it supersedes are not kept beside it."""
    assert all(not RESOURCE.with_name(name).exists()
               for name in ('Canonical_Intake.xml', 'Intake_2.0.md', 'Intake_2.1.md', 'digital-typology.axiom'))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
@pytest.mark.req('MAP-043')
def test_prompt_serves_the_intake_with_only_its_prompt_filled(run, project):
    '''the intake's prompt slot holds what the person asked for, a target or a task; with nothing
    asked it stays empty, and the intake reads that as this project. Intake 2.1 carries it as
    `{Prompt} := """{prompt}"""`, and its TARGET_RESOLUTION takes the target from it, so nothing else is filled.'''
    out = run('intake', 'prompt', cwd=project).stdout
    assert out == served_asked('')  # the intake is the instruction, with only its prompt filled
    asked = run('intake', 'prompt', 'text=Map the timer and its alarm', cwd=project).stdout
    assert asked == served_asked('Map the timer and its alarm')


@pytest.mark.req('BASE-039')
def test_the_prompt_is_filled_as_written_in_intake_2_1_and_escaped_only_in_an_xml_intake_file(run, project, tmp_path):
    """Intake 2.1 is not XML, so what the person asks for reaches it exactly as written; an XML intake file, which the
    intake_file setting can still name, gets it escaped as an XML attribute value, as its <target> is filled."""
    asked = 'fix A & B in <main> "now"'
    assert run('intake', 'prompt', f'text={asked}', cwd=project).stdout == served_asked(asked)
    xml = tmp_path / 'own-intake.xml'
    xml.write_text('<process><prompt text="{prompt}"/></process>\n', encoding='utf-8')
    run('set', f'--intake-file={xml}', cwd=project)
    assert run('intake', 'prompt', f'text={asked}', cwd=project).stdout.startswith(
        '<process><prompt text="fix A &amp; B in &lt;main&gt; &quot;now&quot;"/></process>\n')  # then where its schema is


@pytest.mark.req('CLI-034')
@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_no_setting_adds_an_instruction_to_the_intake(run, project):
    """No instructions are side loaded into a workflow. What is added beside the intake competes
    with it, and the agent cannot tell which of the two is the procedure."""
    plain = run('intake', 'prompt', cwd=project).stdout
    run('set', '--debug', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    run('set', '--no-debug', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    assert plain == stored_with_pointer().replace('{prompt}', '', 1)


@pytest.mark.req('CLI-034')
def test_debug_is_a_chassis_boolean_that_follows_every_settings_rule_and_report_is_gone(run, project):
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=project).stdout)}
    assert (shown['debug']['value'], shown['debug']['owner']) == (False, 'chassis')
    assert 'report' not in shown  # nothing read it since 2026-09-29; removed in the settings cleanup, 2026-10-15
    run('set', '--debug', '--glue', cwd=project)
    run('unset', 'all', cwd=project)
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=project).stdout)}
    assert (shown['debug']['value'], shown['debug']['state']) == (True, 'glued')


@pytest.mark.req('MCP-009')
@pytest.mark.parametrize('identity', ['METAFORM_SESSION', 'METAFORM_ROLE'])
def test_a_dispatched_agent_is_never_given_the_first_run_onboarding(run, project, monkeypatch, identity):
    """An agent a dispatch runner started has its work as its first turn: the onboarding, which asks an agent to
    handle the intake first, is not in what it reads, BASE-052."""
    monkeypatch.setenv(identity, 'worker')
    assert onboarding() not in run('help', 'agents', cwd=project).stdout


@pytest.mark.req('BASE-039')
def test_a_test_intake_file_is_served_only_when_the_setting_names_it(run, project, tmp_path):
    other = tmp_path / 'other.xml'
    other.write_text('<process><target type="x" value="y"/>{project_id}</process>\n', encoding='utf-8')
    run('set', '--intake-file', str(other), cwd=project)
    out = run('intake', 'prompt', cwd=project).stdout
    assert out.startswith('<process><target type="path" value=') and 'timer</process>' in out


def recorded(run, cwd, *args):
    return json.loads(run('intake', *args, '--json', cwd=cwd).stdout)


def failsafe_intake(run, project):
    """A building intake where an operator requires a gateway failsafe and an echo probe the failsafe can hold, and
    an alarm requires the probe too."""
    recorded(run, project, 'start')
    for address, role in (('stakeholder.operator', 'CQU'), ('code.failsafe.gateway', 'DE'), ('code.probe.echo', 'SE'),
                          ('code.alarm', 'SE')):
        recorded(run, project, 'element', address, f'role={role}', 'name_length=1')
    recorded(run, project, 'purpose', 'stakeholder.operator', '["code.failsafe.gateway"]',
             'purpose=Catch a dead gateway.', 'ef=Probes the gateway and fails over.', 'ifd=receives')
    recorded(run, project, 'purpose', 'stakeholder.operator', '["code.probe.echo"]',
             'purpose=Know the gateway answers.', 'ef=Sends an echo each second.', 'ifd=receives')
    recorded(run, project, 'purpose', 'code.alarm', '["code.probe.echo"]', 'purpose=Hear a lost echo.',
             'ef=Reports each lost echo.', 'ifd=receives')


ID_KEYS = {'id', 'join_id', 'element_id', 'parent', 'layer_id', 'item_id'}
STORE_ID = re.compile(r'[0-9a-f]{32}')


def keys_in(found):
    """Every key of a result, at any depth."""
    if isinstance(found, dict):
        return [*found, *(key for value in found.values() for key in keys_in(value))]
    if isinstance(found, list):
        return [key for value in found for key in keys_in(value)]
    return []


def handed_ids(result):
    """What in a result hands the agent an id: a key naming one at any depth, or a store id anywhere in it, a notice's
    message included."""
    keys = keys_in(result)
    return [key for key in keys if key in ID_KEYS] + STORE_ID.findall(json.dumps(result))


FIELDS = {'element': ('namespace_address', 'role', 'name_length', 'name', 'refs'),
          'purpose': ('receiver', 'elements', 'purpose', 'ef', 'ifd')}


@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
def test_no_intake_or_map_tool_takes_relation_or_observation():
    """Observation and relation were never part of the design, so the
    intake tools and the map knowledge tool stop taking both."""
    from metaform.modules.intake import MODULE
    from metaform.modules.map import MODULE as MAP
    taken = {(module.id, verb.name, noun.name) for module in (MODULE, MAP) for verb in module.verbs
             for noun in verb.nouns if noun.name in ('relation', 'observation')}
    assert taken == set()


RECORDING = ('element', 'purpose', 'show', 'remove')


def _element_at_once(home: str, folder: str, address: str, ready: Any, failures: Any) -> None:
    """One process's intake element call, released with the others' at the same moment."""
    os.environ['METAFORM_HOME'] = home
    os.chdir(folder)
    from metaform import cli
    ready.wait()
    try:
        code = cli.main(['intake', 'element', address, 'role=SE', 'name_length=1', '--json'])
    except SystemExit as stopped:
        code = stopped.code
    if code not in (0, None):
        failures.put(f'{address}: exit {code}')


# An agent's own process, as a host's MCP server over stdio is: it records one element, says so, and lives until its
# input closes, as that server does when its host goes.
_AGENT = """
import contextlib, io, sys
from metaform import cli, shown
shown.serving()
with contextlib.redirect_stdout(io.StringIO()):
    try:
        cli.main(['intake', 'element', 'code.alarm.audible', 'role=DE'])
    except SystemExit:
        pass
print('recording', flush=True)
sys.stdin.read()
"""


# An intake agent's runner, as dispatch starts one: its launch noted, then `intake.agent` held while it lives.
_INTAKE_AGENT = """
import json, sys
from metaform.data import Store
store = Store('timer')
store.note_intake_launch(json.loads(sys.argv[1]))
assert store.hold_intake_agent(json.loads(sys.argv[1])['work']) is None
print('holding', flush=True)
sys.stdin.read()
"""


def _intake_runner(home, project, **launch):
    import subprocess
    import sys
    record = {'work': 'intake-x', 'agent': 'claude', 'since': '2026-10-17T05:00:00Z', **launch}
    held = subprocess.Popen([sys.executable, '-c', _INTAKE_AGENT, json.dumps(record)], cwd=project, text=True,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**os.environ, 'METAFORM_HOME': str(home)})
    assert held.stdout is not None and held.stdout.readline().strip() == 'holding'
    return held


def _let_go(held):
    held.stdin.close()
    held.wait(30)
