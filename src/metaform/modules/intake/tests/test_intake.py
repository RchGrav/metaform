"""The intake module: the Canonical Intake served by name, one atomic submission never blocked, intake state, BASE-039."""
from __future__ import annotations

import copy
import json
import multiprocessing
import os
import re
from pathlib import Path
from typing import Any

import pytest

from metaform import home as metaform_home
from metaform.data import Node, Store, export_document

pytestmark = pytest.mark.kind('fixture')

ROOT = Path(__file__).parents[5]
SPEC = Path(__file__).parents[1] / 'resources' / 'intake.axiom'  # the served intake
RESOURCE = SPEC


def stored_with_pointer() -> str:
    """The served intake: the stored file, then, when it does not name its schema, the line saying where it is,
    MCP-009."""
    from importlib import resources

    from metaform import prompt_files
    if 'metaform://intake/schema' in SPEC.read_text(encoding='utf-8'):
        return SPEC.read_text(encoding='utf-8')
    pointer = prompt_files.required(resources.files('metaform.modules.intake'), 'schema_pointer')
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
    run('set', '--debug', '--no-report', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    run('set', '--no-debug', '--report', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    assert plain == stored_with_pointer().replace('{prompt}', '', 1)


@pytest.mark.req('CLI-034')
def test_debug_and_report_are_chassis_booleans_that_follow_every_settings_rule(run, project):
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=project).stdout)}
    assert (shown['debug']['value'], shown['debug']['owner']) == (False, 'chassis')
    assert (shown['report']['value'], shown['report']['owner']) == (True, 'chassis')
    run('set', '--debug', '--glue', cwd=project)
    run('unset', 'all', cwd=project)
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=project).stdout)}
    assert (shown['debug']['value'], shown['debug']['state']) == (True, 'glued')


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
@pytest.mark.req('MAP-021')
@pytest.mark.req('LAYER-001')
def test_an_intake_recorded_object_by_object_is_stored_whole_and_reads_back(run, project, tmp_path):
    report = submit(run, project, FIXTURE, tmp_path, extra=('model=claude', 'role=intake agent'))
    assert (report['project'], report['base'], report['elements'], report['purposes'], report['work']) == (
        'timer', 'main', 4, 2, 0)
    assert set(notices(report)) == NAMED
    assert report['layer'] == 'base'  # LAYER-025: no time or random part
    store = Store('timer')
    assert store.has_intake()
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.short_name, kitchen.name_length, kitchen.role, kitchen.open_work) == ('kitchen timer', 2, 'DE', ())
    assert kitchen.name == 'kitchen timer daemon'  # its own field
    # The element's refs are an item of the sources layer at it, never a field of the element.
    [kept] = store.layer_items('sources', Node('element', 'code.timer.kitchen'), limit=0).results
    assert [(ref.key, ref.value) for ref in kept.refs] == [('path', 'src/main.c')]
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert ([held.address for held in cook_join.elements], cook_join.purpose, cook_join.ifd, cook_join.layer) == (
        ['code.timer.kitchen'], 'Know when each dish is done without watching the clock.', 'receives', report['layer'])
    alarm_join = store.joins('code.timer.kitchen').results[0]
    assert [held.address for held in alarm_join.elements] == ['code.alarm.audible', 'code.loop.tick']
    tick = store.element('code.loop.tick')
    assert (tick.role, tick.name_length, tick.name) == ('SE', 2, 'one-second tick loop')
    assert alarm_join.elements[1].element_id == tick.id  # the part is one element record
    layer = next(item for item in store.layers().results if item.name == report['layer'])
    assert (layer.kind, layer.mutable, layer.hideable) == ('base', False, False)
    provenance = store.provenance(report['layer'])
    assert (provenance.module, provenance.workflow, provenance.model, provenance.role) == (
        'intake', 'canonical-intake', 'claude', 'intake agent')
    assert provenance.prompt is None  # the Canonical Intake's purpose never changes, so no copy is kept, STORE-016
    document = export_document(['timer'], layers=[report['layer']])['projects'][0]['bases'][0]
    elements = [op for op in document['ops'] if op['kind'] == 'element']
    joins = [op for op in document['ops'] if op['kind'] == 'join']
    assert len(elements) == 4 and len(joins) == 2 and sum(len(op['data']['held']) for op in joins) == 3
    assert sorted(op['data']['type'] for op in joins) == ['purpose', 'purpose']
    assert all(set(row) & {'perspective', 'verb', 'non_goal', 'name', 'provider'} == set() for row in (op['data'] for op in joins))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-044')
def test_a_name_is_recorded_wherever_a_namespace_address_and_a_name_length_are(run, project):
    """The name goes anywhere there is a namespace and name length; extra should be gone. The element
    holds its name in a field of its own, beside name_length; the element a join holds is named the same way."""
    run('intake', 'start', cwd=project)
    element = json.loads(run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name_length=2',
                             'name=kitchen timer daemon', '--json', cwd=project).stdout)
    assert [notice for notice in element['notices'] if notice['where'] == 'name'] == []
    unnamed = json.loads(run('intake', 'element', 'code.alarm.audible', 'role=SE', 'name_length=2', '--json',
                             cwd=project).stdout)
    assert [notice['message'] for notice in unnamed['notices'] if notice['where'] == 'name'] == [
        'name is missing; stored empty.']
    inner = json.loads(run('intake', 'element', 'code.loop.tick', 'name=one-second tick', 'name_length=2', 'role=SE',
                           '--json', cwd=project).stdout)
    assert inner['notices'] == []
    join = json.loads(run('intake', 'purpose', 'code.timer.kitchen', '["code.alarm.audible", "code.loop.tick"]',
                          'purpose=Get attention.', 'ef=Rings.', 'ifd=receives', '--json', cwd=project).stdout)
    assert join['notices'] == []
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    kitchen = next(row for row in shown['elements'] if row['namespace_address'] == 'code.timer.kitchen')
    assert (kitchen['short_name'], kitchen['name_length'], kitchen['name'], kitchen['role']) == (
        'kitchen timer', 2, 'kitchen timer daemon', 'DE')
    assert not kitchen.get('extra')
    run('intake', 'finish', cwd=project)
    store = Store('timer')
    assert store.element('code.timer.kitchen').name == 'kitchen timer daemon'
    assert store.element('code.loop.tick').name == 'one-second tick'  # the element a join holds is named too


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_no_intake_tool_takes_a_perspective():
    """A join carries no perspective: one direction, read from its ef and ifd, is less to reason about and lowers
    mistakes. No intake tool
    takes a perspective, and no field description names one."""
    import xml.etree.ElementTree as ET
    for verb in ('element', 'purpose'):
        assert 'perspective' not in nouns_of(verb), verb
    fields = ET.fromstring((RESOURCE.parent / 'prompts.xml').read_text(encoding='utf-8')).find('fields')
    assert fields is not None and fields.find('purpose/perspective') is None and fields.find('element/perspective') is None
    assert 'perspective' not in json.dumps(FIXTURE)


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-032')
@pytest.mark.req('MCP-009')
def test_a_join_missing_its_purpose_is_stored_whole_with_a_notice_naming_it(run, project, tmp_path):
    broken = copy.deepcopy(FIXTURE)
    del broken['elements'][0]['joins'][0]['purpose']
    found = notices(submit(run, project, broken, tmp_path))
    assert re.match(r'purpose is missing\b', found['elements[0].joins[0].purpose'])
    store = Store('timer')
    assert store.has_intake()
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert cook_join.purpose in (None, '') and cook_join.ef.startswith('The timer counts down')


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-026')
def test_what_does_not_fit_is_stored_as_given_and_named_in_a_notice(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    cook = given['elements'][0]
    cook['joins'][0]['provider'] = 'code.nowhere'
    cook['joins'].append({'provider': 'stakeholder.cook.home', 'purpose': 'Cook for itself.', 'ef': 'f',
                          'ifd': 'both'})
    given['elements'][2]['namespace_address'] = 'Code..Alarm'
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert {'elements[0].joins[0].elements', 'elements[0].joins[1].elements',
            'elements[2].namespace_address'} <= set(found)
    store = Store('timer')
    nowhere = store.element('code.nowhere')
    assert nowhere is not None and nowhere.role is None and nowhere.layer == report['layer']
    assert sorted([held.address for held in join.elements] for join in store.joins('stakeholder.cook.home').results) == [
        ['code.nowhere'], ['stakeholder.cook.home']]
    odd = store.where('Code..Alarm', raw=True)
    assert odd is not None and odd.element.name == 'audible alarm'


@pytest.mark.req('STORE-012')
@pytest.mark.req('STORE-004')
@pytest.mark.req('BASE-044')
def test_an_odd_ref_sent_to_an_intake_tool_is_placed_by_the_stores_one_rule(run, project):
    """The store owns what happens to a ref that is not a key and a value, STORE-012, for every writer; an intake tool
    hands its refs on as given, to the element's item of the sources layer. A ref that is a record is split into an
    item of its own, as the store does with any list of records in an extra, STORE-004."""
    recorded(run, project, 'start')
    made = recorded(run, project, 'element', 'code.probe.echo', 'role=SE', 'name_length=1', 'name=echo probe',
                    'refs=[["path", "src/echo.c"], {"path": "src/pins.h"}]')
    messages = [(notice['where'], notice['message']) for notice in made['notices']]
    assert messages == [
        ('refs', 'A ref is a key and a value, both text; one was not, and kept in the extra under refs.'),
        ('extra', 'extra.refs on the item held a list of records; each was stored as its own item.')]
    store = Store('timer')
    found = store.layer_items('sources', Node('element', 'code.probe.echo'), limit=0).results
    kept = [item for item in found if item.refs]
    assert [[(ref.key, ref.value) for ref in item.refs] for item in kept] == [[('path', 'src/echo.c')]]
    assert kept[0].extra is None
    assert [item.value for item in found if not item.refs] == [{'refs': {'path': 'src/pins.h'}}]


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_refs_that_are_not_text_are_kept_in_the_extra_and_counted_in_words(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    given['elements'][1]['refs'] = [['path', 'src/timer.c'], ['line', 12], ['col', 3]]
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert found['elements[1].refs'] == ('A ref is a key and a value, both text; two were not, and kept in the extra '
                                         'under refs.')
    store = Store('timer')
    [kept] = store.layer_items('sources', Node('element', given['elements'][1]['namespace_address']), limit=0).results
    assert [(ref.key, ref.value) for ref in kept.refs] == [('path', 'src/timer.c')]
    assert kept.extra is not None and kept.extra['refs'] == [['line', 12], ['col', 3]]


@pytest.mark.req('STORE-041')
def test_a_new_intake_is_named_for_what_it_is_for(run, project, tmp_path, home):
    """The agent names a new intake from the person's request, such as a refactor of the web interface, and the name
    opens it at once in a metaform of that name; a name that is no name is refused with the form it takes."""
    submit(run, project, FIXTURE, tmp_path)
    refused = run('intake', 'start', 'name=web interface!', cwd=project, ok=False)
    assert 'is not a name for an intake' in refused.stderr
    started = json.loads(run('intake', 'start', 'name=web-interface-refactor', '--json', cwd=project).stdout)
    assert started['base'] == 'web-interface-refactor'
    assert any(base.name == 'web-interface-refactor' for base in metaform_home.bases('timer'))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-045')
@pytest.mark.req('STORE-041')
def test_a_second_intake_is_stored_as_a_new_active_metaform_and_the_first_is_kept(run, project, tmp_path, home):
    first = submit(run, project, FIXTURE, tmp_path)
    main = metaform_home.active_base('timer')
    before = metaform_home.store_path('timer', main.id).read_bytes()
    changed = copy.deepcopy(FIXTURE)
    changed['elements'][2]['namespace_address'] = 'code.alarm.visual'
    changed['elements'][1]['joins'][0]['provider'] = 'code.alarm.visual'
    second = submit(run, project, changed, tmp_path, extra=('name=alarm-visual',))  # a separate intake is named
    assert second['base'] == 'alarm-visual'
    active = metaform_home.active_base('timer')
    assert active.name == second['base'] and active.id != main.id
    assert any('metaform map activate main' in notice['message'] for notice in second['notices'])
    store = Store('timer')
    assert store.element('code.alarm.visual') is not None and store.element('code.alarm.audible') is None
    assert metaform_home.store_path('timer', main.id).read_bytes() == before
    run('activate', 'base', 'main', cwd=project)
    assert Store('timer').element('code.alarm.audible') is not None
    assert Store('timer').layers(kind='intake').results[0].name == first['layer']


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-045')
@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
@pytest.mark.req('STORE-043')
@pytest.mark.req('STORE-016')
def test_a_report_and_feedback_are_saved_and_a_work_record_on_the_intake_is_counted_at_the_finish(run, project,
                                                                                                    tmp_path, home):
    # The record is written while the intake is being recorded, through the map tool, never through an intake field.
    run('intake', 'start', '--json', cwd=project)
    run('intake', 'element', 'code.alarm.audible', 'role=SE', '--json', cwd=project)
    made = json.loads(run('map', 'work', 'op=add', 'title=A broken alarm', 'node=element:code.alarm.audible', 'condition=broken',
                          'note=alarm.c conflicts with specifications/alarm.md:12', 'task=review the code against the linked specification', '--json',
                          cwd=project).stdout)
    assert made['condition'] == 'broken'
    assert made['notices'] == []
    report = submit(run, project, copy.deepcopy(FIXTURE), tmp_path,
                    extra=('report=The alarm pin is unconnected.', 'feedback=The join fields were clear.'))
    assert report['work'] == 1
    layer_id = Store('timer').layers(kind='intake').results[0].id
    folder = metaform_home.project_folder('timer') / 'reports'
    assert (folder / f'{layer_id}-report.md').read_text(encoding='utf-8') == 'The alarm pin is unconnected.'
    assert (folder / f'{layer_id}-feedback.md').read_text(encoding='utf-8') == 'The join fields were clear.'
    assert sorted(path.name for path in project.iterdir()) == []
    listed = json.loads(run('list', 'reports', '--json', cwd=project).stdout)['results']
    assert sorted((row['name'], row['kind']) for row in listed) == [
        (f'{layer_id}-feedback.md', 'feedback'), (f'{layer_id}-report.md', 'report')]
    provenance = Store('timer').provenance(report['layer'])
    assert sorted((ref.key, ref.value) for ref in provenance.refs) == [
        ('feedback', f'{layer_id}-feedback.md'), ('report', f'{layer_id}-report.md')]
    exclude = json.loads(run('map', 'work', 'condition=broken', '--json', cwd=project).stdout)['results']
    assert [(row['address'], row['condition'], row['note']) for row in exclude] == [
        ('code.alarm.audible', 'broken', 'alarm.c conflicts with specifications/alarm.md:12')]
    assert json.loads(run('map', 'work', f'id={exclude[0]["id"]}', '--json', cwd=project).stdout)['task'] == (
        'review the code against the linked specification')  # a list row leaves its task out, MAP-049
    assert Store('timer').element('code.alarm.audible').open_work == ('broken',)


@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
@pytest.mark.req('BASE-043')
def test_the_intake_tools_carry_no_flag_field_and_a_flag_sent_anyway_is_named_and_no_work_record(run, project,
                                                                                                   tmp_path):
    """The intake tools carry no flag field, and a flag sent anyway is never a work record. With no extra in the
    metaform's shape the command line has nowhere to keep a word it does not know, so it refuses it, as the chassis grammar does
    for every verb with no extra, BASE-043, and writes nothing."""
    for verb in ('element', 'purpose'):
        assert not {'flag', 'flag_note'} & set(nouns_of(verb)), verb
    recorded(run, project, 'start')
    refused = run('intake', 'element', 'code.alarm.audible', 'role=SE', 'flag=broken', cwd=project, ok=False)
    assert refused.returncode == 2 and "does not take 'flag=broken'" in refused.stderr
    joined = run('intake', 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=p', 'colour=red',
                 cwd=project, ok=False)
    assert joined.returncode == 2 and "does not take 'colour=red'" in joined.stderr
    assert Store('timer').work(open=True, limit=0).results == ()
    shown = recorded(run, project, 'show')
    assert (shown['elements'], shown['purposes']) == ([], [])


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-016')
def test_two_elements_with_one_address_are_one_element_holding_both_joins(run, project, tmp_path):
    doubled = copy.deepcopy(FIXTURE)
    doubled['elements'].append({'namespace_address': 'stakeholder.cook.home', 'role': 'CQU', 'name': 'Home cook',
                                'joins': [{'provider': 'code.alarm.audible', 'purpose': 'Hear it from the next room.',
                                           'ef': 'Rings loudly.', 'ifd': 'receives'}]})
    report = submit(run, project, doubled, tmp_path)
    assert set(notices(report)) == NAMED
    joins = Store('timer').joins('stakeholder.cook.home').results
    assert sorted([held.address for held in join.elements] for join in joins) == [
        ['code.alarm.audible'], ['code.timer.kitchen']]


@pytest.mark.req('CLI-028')
@pytest.mark.req('MCP-031')
def test_status_says_whether_there_is_an_intake_and_gives_no_intake_or_map_directions(run, project, tmp_path):
    out = run(cwd=project).stdout.splitlines()
    at = out.index('Intake: none yet')
    assert not out[at + 1].startswith('  This project')
    assert run('intake', 'status', cwd=project).stdout.startswith('No intake')
    report = submit(run, project, FIXTURE, tmp_path)
    out = run(cwd=project).stdout.splitlines()
    at = out.index('Intake: complete')
    assert not any('subagent' in line or 'This project has a map' in line for line in out[at:])
    assert report['layer'] in run('intake', 'status', cwd=project).stdout


@pytest.mark.req('MCP-009')
@pytest.mark.req('MCP-031')
def test_an_intake_started_and_not_finished_is_named_in_the_instructions(run, project):
    """The no-intake notice is needed to onboard; when an intake is started and aborted, the next agent is told that an
    intake was started but aborted and still remains to be completed. A finished intake clears both."""
    import xml.etree.ElementTree as ET
    prompts = ET.fromstring(RESOURCE.with_name('prompts.xml').read_text(encoding='utf-8'))
    notice, line = onboarding(), prompts.findtext('unfinished', '').strip()
    assert line == 'An intake was started but aborted and still remains to be completed.'
    assert notice.startswith('FIRST RUN.')
    assert 'intake_prompt' in notice  # the procedure, named where an agent reads it, MCP-037
    agents = lambda: run('help', 'agents', cwd=project).stdout
    shown = agents()
    assert notice in shown and line not in shown
    run('intake', 'start', cwd=project)
    shown = agents()
    assert line in shown and notice not in shown
    run('intake', 'finish', cwd=project)
    shown = agents()
    assert line not in shown and notice not in shown
    run('intake', 'start', cwd=project)  # on a finished map start opens nothing: a verify pass writes onto it
    assert line not in agents()
    run('intake', 'element', 'code.display.digit', 'role=SE', 'name=digit', cwd=project)  # added to the map itself
    assert line not in agents()
    run('intake', 'finish', cwd=project)
    run('intake', 'element', 'code.display.dot', 'role=SE', 'name=dot', cwd=project)  # no pass open: a new intake
    assert line in agents()


@pytest.mark.req('MCP-009')
def test_a_dispatched_agent_is_never_given_the_first_run_onboarding(run, project, monkeypatch):
    """An agent a dispatch runner started has its work as its first turn: the onboarding, which asks an agent to
    handle the intake first, is not in what it reads, BASE-052."""
    monkeypatch.setenv('METAFORM_ROLE', 'worker')
    assert onboarding() not in run('help', 'agents', cwd=project).stdout


@pytest.mark.req('MCP-009')
@pytest.mark.req('MCP-027')
def test_the_no_intake_notice_asks_once_starts_the_web_gui_and_runs_the_intake_while_the_person_watches(run, project):
    """MCP-009: on a first run the agent asks the person once, and on a yes starts the browser view and gives its
    address, hands the intake to one fresh subagent with only the procedure's resource, then invites questions. A
    registered folder skips the register step. The notice leaves once an intake is finished."""
    notice = onboarding()
    ask, web = notice.index('Want me to start?'), notice.index('the web_start tool')
    delegate, questions = notice.index('Start ONE fresh subagent'), notice.index('invite their questions')
    assert ask < web < delegate < questions
    assert 'intake_prompt' in notice and 'Register this folder' not in notice
    assert 'blind spot' not in notice and 'best practices' not in notice
    assert notice in run('help', 'agents', cwd=project).stdout
    run('intake', 'start', cwd=project)
    run('intake', 'finish', cwd=project)
    assert 'Want me to start?' not in run('help', 'agents', cwd=project).stdout


@pytest.mark.req('MAP-041')
@pytest.mark.req('MAP-042')
def test_an_artifact_that_is_not_software_is_mapped_the_same_way(run, tmp_path):
    photos = tmp_path / 'photos'
    photos.mkdir()
    (photos / 'kitchen.jpg').write_bytes(b'\xff\xd8\xff')
    run('add', 'project', 'photos', str(photos), 'artifact', 'kitchen_photos')
    document = {'elements': [
        {'namespace_address': 'stakeholder.seller', 'role': 'CQU', 'joins': [
            {'provider': 'media.photo.subject', 'purpose': 'Show the object at its best.', 'ef': 'Frames it.',
             'ifd': 'receives'}]},
        {'namespace_address': 'media.photo.subject', 'role': 'DE'}]}
    submit(run, photos, document, tmp_path)
    store = Store('photos')
    assert store.element('media.photo.subject').role == 'DE'
    assert store.project().target_type == 'artifact'


@pytest.mark.req('BASE-039')
def test_a_test_intake_file_is_served_only_when_the_setting_names_it(run, project, tmp_path):
    other = tmp_path / 'other.xml'
    other.write_text('<process><target type="x" value="y"/>{project_id}</process>\n', encoding='utf-8')
    run('set', '--intake-file', str(other), cwd=project)
    out = run('intake', 'prompt', cwd=project).stdout
    assert out.startswith('<process><target type="path" value=') and 'timer</process>' in out


@pytest.mark.req('STORE-044')
@pytest.mark.req('BASE-039')
def test_the_intake_serves_the_shipped_file_and_keeps_nothing_in_the_prompt_store(run, home, project, tmp_path):
    """The Canonical Intake is the one prompt that is not edited: it is served as shipped, never kept as a stored
    prompt, and a stored prompt of the same name does not reach it."""
    from metaform.data import prompts
    first = run('intake', 'prompt', cwd=project).stdout
    assert without_target(first).startswith(without_target(RESOURCE.read_text(encoding='utf-8')))
    assert prompts.prompts() == ()
    prompts.add_prompt('canonical-intake', 'xml', '<!-- edited in the viewer -->\n<process/>\n')
    assert run('intake', 'prompt', cwd=project).stdout == first
    result = submit(run, project, FIXTURE, tmp_path)
    store = Store('timer')
    layer = store.layer_ref(result['layer'])
    assert prompts.use_of('timer', layer.base_id, layer.id) is None
    provenance = store.provenance(result['layer'])
    assert provenance.prompt_version is None and provenance.prompt is None
    assert [(prompt.name, prompt.newest) for prompt in prompts.prompts()] == [('canonical-intake', 1)]


@pytest.mark.req('STORE-044')
def test_an_intake_file_is_served_as_it_is_and_links_no_version(run, home, project, tmp_path):
    from metaform.data import prompts
    own = tmp_path / 'own-intake.xml'
    own.write_text('<process><target/></process>\n', encoding='utf-8')
    run('set', f'--intake-file={own}', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout.startswith('<process><target ')
    result = submit(run, project, FIXTURE, tmp_path)
    layer = Store('timer').layer_ref(result['layer'])
    assert prompts.use_of('timer', layer.base_id, layer.id) is None
    assert Store('timer').provenance(result['layer']).prompt is None


@pytest.mark.req('BASE-039')
@pytest.mark.req('STORE-032')
def test_a_building_intake_is_seen_only_through_intake_show_until_it_finishes(run, project):
    """The intake is recorded object by object as it is reasoned; agents read it back while it is
    built, and only a finished intake reaches every other read."""
    run('intake', 'start', 'model=claude', 'role=intake agent', cwd=project)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', 'name=Home cook', cwd=project)
    made = json.loads(run('intake', 'purpose', 'stakeholder.cook.home', '["code.timer.kitchen"]',
                          'purpose=Know when each dish is done.', 'ef=Counts down and rings.', 'ifd=receives',
                          '--json', cwd=project).stdout)
    assert [notice['where'] for notice in made['notices']] == ['elements']
    assert 'code.timer.kitchen was not an element' in made['notices'][0]['message']
    store = Store('timer')
    assert not store.has_intake() and store.element('stakeholder.cook.home') is None
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert (len(shown['elements']), len(shown['purposes']), shown['purposes'][0]['elements']) == (
        2, 1, ['code.timer.kitchen'])
    assert shown['undescribed'] == ['code.timer.kitchen']
    assert 'Intake: being recorded' in run(cwd=project).stdout
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name=kitchen timer', cwd=project)
    assert json.loads(run('intake', 'show', '--json', cwd=project).stdout)['undescribed'] == []
    finished = json.loads(run('intake', 'finish', '--json', cwd=project).stdout)
    assert (finished['elements'], finished['purposes']) == (2, 1)
    store = Store('timer')
    assert store.has_intake() and store.element('code.timer.kitchen').role == 'DE'
    assert store.provenance(finished['layer']).model == 'claude'


@pytest.mark.req('BASE-039')
@pytest.mark.req('STORE-032')
@pytest.mark.req('BASE-044')
def test_recording_again_and_remove_change_a_building_intake_and_a_finished_one_changes_only_by_refining(run,
                                                                                                         project):
    run('intake', 'start', cwd=project)
    run('intake', 'element', 'code.a', 'role=DE', cwd=project)
    run('intake', 'element', 'code.b', 'role=SE', cwd=project)
    run('intake', 'purpose', 'code.a', '["code.b"]', 'purpose=p', 'ef=f', 'ifd=receives', cwd=project)
    run('intake', 'purpose', 'code.b', '["code.a"]', 'purpose=q', 'ef=g', 'ifd=sends', cwd=project)
    run('intake', 'purpose', 'code.a', '["code.b"]', 'purpose=The better purpose.', cwd=project)
    run('intake', 'remove', 'receiver=code.b', 'provider=code.a', cwd=project)
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert [(row['receiver'], row['elements'], row['purpose'], row['ef']) for row in shown['purposes']] == [
        ('code.a', ['code.b'], 'The better purpose.', 'f')]
    run('intake', 'finish', cwd=project)
    gone = json.loads(run('intake', 'remove', 'receiver=code.a', 'provider=code.b', '--json', cwd=project).stdout)
    assert 'map refine' in gone['notices'][0]['message'] and 'correction' not in gone['notices'][0]['message']
    assert [join.purpose for join in Store('timer').joins('code.a').results] == ['The better purpose.']
    # A field changed after the finish is refined into the finished map as a new version; no new metaform opens.
    later = json.loads(run('intake', 'purpose', 'code.a', '["code.b"]', 'purpose=Changed.', '--json', cwd=project).stdout)
    assert later['base'] == 'main' and not any(notice['where'] == 'base' for notice in later['notices'])
    run('intake', 'element', 'code.a', 'role=SE', 'name=renamed', cwd=project)
    finished = Store('timer')
    assert [(join.purpose, [held.address for held in join.elements]) for join in finished.joins('code.a').results] == [
        ('Changed.', ['code.b'])]
    kept = finished.element('code.a')
    assert kept is not None and (kept.role, kept.name) == ('SE', 'renamed')


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_recording_without_a_start_starts_the_intake_and_a_second_start_resumes_it(run, project):
    made = json.loads(run('intake', 'element', 'code.a', 'role=DE', '--json', cwd=project).stdout)
    assert any('started' in notice['message'] for notice in made['notices'])
    layer = json.loads(run('intake', 'show', '--json', cwd=project).stdout)['layer']
    again = json.loads(run('intake', 'start', '--json', cwd=project).stdout)
    assert again['layer'] == layer and any('already being recorded' in notice['message']
                                           for notice in again['notices'])
    assert len(json.loads(run('intake', 'show', '--json', cwd=project).stdout)['elements']) == 1


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-045')
def test_the_finish_reads_a_long_report_from_a_file_or_from_standard_input_on_the_command_line(run, project,
                                                                                            tmp_path, home):
    """A report runs to pages, with quotes and new lines in it, which no command line carries well. On the command
    line a value that names a file is read from the file and `-` from standard input, as `metaform feedback` reads
    them; text that names no file is the report itself."""
    text = 'Broken:\n- the "alarm" pin is unconnected.\n\nCruft:\n- none.\n'
    (tmp_path / 'report.md').write_text(text, encoding='utf-8')
    run('intake', 'start', '--json', cwd=project)
    run('intake', 'element', 'code.alarm.audible', 'role=SE', '--json', cwd=project)
    run('intake', 'finish', f'report={tmp_path / "report.md"}', 'feedback=-', '--json', cwd=project,
        input='Said on standard input.\n')
    layer_id = Store('timer').layers(kind='intake').results[0].id
    folder = metaform_home.project_folder('timer') / 'reports'
    assert (folder / f'{layer_id}-report.md').read_text(encoding='utf-8') == text
    assert (folder / f'{layer_id}-feedback.md').read_text(encoding='utf-8') == 'Said on standard input.\n'


@pytest.mark.req('BASE-039')
def test_over_mcp_a_report_is_the_text_given_and_no_file_is_read(home, project, tmp_path, monkeypatch):
    """An agent hands its report over as text. A tool never opens a path it is given, so a report that happens to
    name a file is kept as those words."""
    import anyio

    from metaform.modules.mcp import server
    monkeypatch.setenv('METAFORM_HOME', str(home))
    secret = tmp_path / 'secret.txt'
    secret.write_text('not for a report', encoding='utf-8')
    anyio.run(server.run_tool, project, 'intake_start', {})
    anyio.run(server.run_tool, project, 'intake_element', {'namespace_address': 'code.alarm.audible', 'role': 'SE'})
    anyio.run(server.run_tool, project, 'intake_finish', {'report': str(secret)})
    layer_id = Store('timer').layers(kind='intake').results[0].id
    kept = (metaform_home.project_folder('timer') / 'reports' / f'{layer_id}-report.md').read_text(encoding='utf-8')
    assert kept == str(secret)


@pytest.mark.req('BASE-039')
@pytest.mark.req('LAYER-010')
@pytest.mark.req('BASE-044')
def test_a_resumed_intake_keeps_the_provenance_the_agent_gives_that_its_layer_lacks(run, project):
    """An orchestrator starts the intake with the model; the agent's own start resumes it and gives its role. What
    the layer lacks is filled in; what it already holds is kept, and a different value is named."""
    from metaform.data import Store
    first = json.loads(run('intake', 'start', 'model=opus', '--json', cwd=project).stdout)
    again = json.loads(run('intake', 'start', 'model=opus', 'role=intake agent', '--json', cwd=project).stdout)
    assert again['layer'] == first['layer']
    store = Store('timer')
    kept = store.provenance(first['layer'])
    assert (kept.model, kept.role) == ('opus', 'intake agent')
    third = json.loads(run('intake', 'start', 'model=sonnet', '--json', cwd=project).stdout)
    assert any(notice['where'] == 'model' and 'opus' in notice['message'] and 'sonnet' in notice['message']
               for notice in third['notices'])
    assert store.provenance(first['layer']).model == 'opus'


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


@pytest.mark.req('BASE-039')
def test_the_agent_records_joins_and_is_never_handed_an_id(run, project):
    """The agent records the map as it reasons it, never handling ids. The intake tool names a join by its receiver
    and an element it holds, and an element by its address; no noun or result hands the agent an id."""
    from metaform.modules.intake import MODULE
    assert 'purpose' in [verb.name for verb in MODULE.verbs]
    for verb in MODULE.verbs:
        taken = {noun.name for noun in verb.nouns}
        assert not [name for name in taken if name in ID_KEYS | {'into', 'type'}], verb.name
    failsafe_intake(run, project)
    results = [
        recorded(run, project, 'element', 'code.siren', 'role=SE', 'name_length=1'),
        recorded(run, project, 'purpose', 'code.alarm', '["code.failsafe.gateway"]', 'purpose=Know of a failover.',
                 'ef=Reports each failover.', 'ifd=receives'),
        recorded(run, project, 'purpose', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.ping"]'),
        recorded(run, project, 'show'),
        recorded(run, project, 'show', 'receiver=code.alarm'),
        recorded(run, project, 'remove', 'receiver=code.alarm', 'provider=code.failsafe.gateway'),
        recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.failsafe.gateway',
                 'namespace_address=code.probe.ping'),
        recorded(run, project, 'finish'),
        recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.failsafe.gateway'),
    ]
    assert [found for result in results for found in handed_ids(result)] == []


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_a_join_call_naming_elements_two_joins_hold_changes_neither(run, project):
    """Two joins of one receiver that a call names together cannot be told apart by their addresses: the call changes
    neither, adds no element to either, and its notice lists both purposes."""
    recorded(run, project, 'start')
    recorded(run, project, 'purpose', 'code.a', '["code.b"]', 'purpose=First why.', 'ef=f', 'ifd=receives')
    recorded(run, project, 'purpose', 'code.a', '["code.c"]', 'purpose=Second why.', 'ef=g', 'ifd=receives')
    both = recorded(run, project, 'purpose', 'code.a', '["code.b", "code.c"]', 'purpose=Changed.')
    message = ' '.join(notice['message'] for notice in both['notices'])
    assert 'First why.' in message and 'Second why.' in message
    shown = recorded(run, project, 'show')
    assert sorted((row['purpose'], tuple(row['elements'])) for row in shown['purposes']) == [
        ('First why.', ('code.b',)), ('Second why.', ('code.c',))]


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-040')
def test_annealing_adds_an_element_to_its_parents_join_and_the_element_stays_one_record(run, project):
    """An element always appears as one element record; annealing places it in its parent's join,
    and the element itself does not move. In, the join holds it as one more element."""
    failsafe_intake(run, project)
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.probe.echo')
    annealed = recorded(run, project, 'purpose', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.echo"]')
    assert annealed['notices'] == []
    shown = recorded(run, project, 'show')
    assert sorted((row['receiver'], tuple(row['elements'])) for row in shown['purposes']) == [
        ('code.alarm', ('code.probe.echo',)), ('stakeholder.operator', ('code.failsafe.gateway', 'code.probe.echo'))]
    [operator] = [row for row in shown['purposes'] if row['receiver'] == 'stakeholder.operator']
    assert (operator['purpose'], operator['ef']) == ('Catch a dead gateway.', 'Probes the gateway and fails over.')
    [element] = [row for row in shown['elements'] if row['namespace_address'] == 'code.probe.echo']
    assert element['role'] == 'SE'
    finished = recorded(run, project, 'finish')
    assert (finished['elements'], finished['purposes']) == (4, 2)
    store = Store('timer')
    [parent] = store.joins('stakeholder.operator').results
    assert [held.address for held in parent.elements] == ['code.failsafe.gateway', 'code.probe.echo']
    assert store.element('code.probe.echo').id == parent.elements[1].element_id


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
def test_show_reads_one_receivers_joins_and_what_they_hold(run, project):
    """The intake must not depend on the size of the agent's context."""
    failsafe_intake(run, project)
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.probe.echo')
    recorded(run, project, 'purpose', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.echo"]')
    operator = recorded(run, project, 'show', 'receiver=stakeholder.operator')
    assert [row['elements'] for row in operator['purposes']] == [['code.failsafe.gateway', 'code.probe.echo']]
    assert {row['namespace_address'] for row in operator['elements']} == {
        'stakeholder.operator', 'code.failsafe.gateway', 'code.probe.echo'}
    alarm = recorded(run, project, 'show', 'receiver=code.alarm')
    assert [row['elements'] for row in alarm['purposes']] == [['code.probe.echo']]


@pytest.mark.req('BASE-039')
def test_recording_and_remove_name_an_element_and_a_join_by_their_addresses(run, project):
    """A Fable intake on 2026-09-27 crashed its own script expecting join_id where intake_show said id; there are no
    ids to expect: each thing is named by the addresses the agent reasoned."""
    failsafe_intake(run, project)
    recorded(run, project, 'purpose', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.ping"]')
    held = next(row for row in recorded(run, project, 'show')['purposes']
                if row['receiver'] == 'stakeholder.operator' and 'code.probe.ping' in row['elements'])
    # recorded again with no fields, the join keeps its own and only gains the element
    assert (held['purpose'], held['ef'], held['ifd']) == ('Catch a dead gateway.', 'Probes the gateway and fails over.',
                                                          'receives')
    recorded(run, project, 'element', 'code.alarm', 'name=alarm bell')
    recorded(run, project, 'element', 'code.alarm', 'name_length=2')
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.failsafe.gateway',
             'namespace_address=code.probe.ping')
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.probe.echo')
    again = recorded(run, project, 'show')
    alarm = next(row for row in again['elements'] if row['namespace_address'] == 'code.alarm')
    assert (alarm['name_length'], alarm['role'], alarm['name']) == (2, 'SE', 'alarm bell')  # the rest is kept
    assert sorted((row['receiver'], tuple(row['elements'])) for row in again['purposes']) == [
        ('code.alarm', ('code.probe.echo',)), ('stakeholder.operator', ('code.failsafe.gateway',))]
    assert 'namespace_address' in nouns_of('element') and 'address' not in nouns_of('element')
    assert {'receiver', 'elements'} <= set(nouns_of('purpose'))
    assert {'receiver', 'provider', 'namespace_address'} <= set(nouns_of('remove'))


@pytest.mark.req('MAP-017')
@pytest.mark.req('STORE-025')
def test_the_cestui_que_use_is_the_role_cqu_and_ve_is_no_longer_a_role(run, project):
    """VE is changed to CQU, Cestui Que Use, throughout. The served intake names the roles
    CQU, DE, SE and NE; an element given CQU is stored without a notice and is the map's entry beside the DE."""
    run('intake', 'start', 'model=claude', 'role=intake agent', cwd=project)
    kept = json.loads(run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', 'name_length=2', '--json',
                          cwd=project).stdout)
    assert not [notice for notice in kept.get('notices', []) if notice['where'] == 'role']
    old = json.loads(run('intake', 'element', 'stakeholder.diner', 'role=VE', 'name_length=1', '--json',
                         cwd=project).stdout)
    [said] = [notice['message'] for notice in old['notices'] if notice['where'] == 'role']
    assert said == "'VE' is not CQU, DE, SE or NE; it was stored as given."
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name_length=2', cwd=project)
    run('intake', 'finish', cwd=project)
    roots = json.loads(run('map', 'roots', '--json', cwd=project).stdout)
    assert {item['element']['address'] for item in roots['entry']} == {'stakeholder.cook.home', 'code.timer.kitchen'}


FIELDS = {'element': ('namespace_address', 'role', 'name_length', 'name', 'refs'),
          'purpose': ('receiver', 'elements', 'purpose', 'ef', 'ifd')}


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-031')
def test_each_recorded_field_is_described_once_from_the_intake_modules_prompts_file():
    """The field definitions are not parsed out of the Canonical Intake, which is being refined and
    no longer carries the response schema. Each one is written once, in the intake module's prompts.xml under
    <fields>, and every tool that takes the field shows those words."""
    import xml.etree.ElementTree as ET
    written = ET.parse(Path(__file__).parents[1] / 'resources' / 'prompts.xml').getroot().find('fields')
    assert written is not None
    assert [group.tag for group in written] == ['element', 'purpose']
    for verb, group in (('element', 'element'), ('purpose', 'purpose')):
        nouns = nouns_of(verb)
        for field in FIELDS[group]:
            said = written.findtext(f'{group}/{field}')
            assert said and said.strip() == nouns[field].help, (verb, field)
    assert nouns_of('remove')['provider'].help == written.findtext('purpose/provider').strip()
    source = (Path(__file__).parents[1] / '__init__.py').read_text(encoding='utf-8')
    assert 'schema//elements' not in source and 'SET perspective' not in source  # the Canonical Intake is not parsed for them


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


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-031')
def test_every_noun_of_the_intakes_recording_verbs_takes_its_words_from_the_prompts_file():
    """A field's description carries its term.
    Every noun the recording verbs take is defined once, in prompts.xml under <fields>, by its glossary lines or by
    its plainest name, and no tool writes words of its own for one."""
    import xml.etree.ElementTree as ET
    written = ET.parse(Path(__file__).parents[1] / 'resources' / 'prompts.xml').getroot().find('fields')
    assert written is not None
    defined: dict[str, set[str]] = {}
    for group in written:
        for field in group:
            defined.setdefault(field.tag, set()).add((field.text or '').strip())
    for verb in RECORDING:
        for name, noun in nouns_of(verb).items():
            assert noun.help in defined.get(name, set()), (verb, name, noun.help)


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-046')
def test_a_condition_given_with_an_element_or_a_join_is_an_open_work_record_at_it(run, project):
    """The agent said it found missing and broken things, and nothing like that showed in the GUI.
    The Canonical Intake's step 2 has the agent mark them; the intake tools take the mark and the finding."""
    run('intake', 'start', cwd=project)
    element = recorded(run, project, 'element', 'code.auth', 'role=SE', 'name=auth', 'condition=trouble',
                       'note=Non-debug modes are forced to debug.')
    run('intake', 'element', 'code.timer', 'role=DE', 'name=timer', cwd=project)
    plain = recorded(run, project, 'element', 'code.clock', 'role=SE', 'name=clock')
    # a purpose record apart from code.auth, which would be one node with it, MAP-046's amendment of 2026-10-14
    join = recorded(run, project, 'purpose', 'code.timer', '["code.clock"]', 'purpose=p', 'ef=f', 'ifd=receives',
                    'condition=missing', 'note=The demo does not declare its autoap dependency.')
    for made in (element, join, plain):
        assert made['notices'] == []
    recorded(run, project, 'finish')
    store = Store('timer')
    [held] = store.joins('code.timer').results
    work = {(row.node_kind, row.node_id): (row.condition, row.note, row.done) for row in store.work(open=True, limit=0).results}
    assert work == {
        ('element', store.element('code.auth').id): ('trouble', 'Non-debug modes are forced to debug.', None),
        ('join', held.id): ('missing', 'The demo does not declare its autoap dependency.', None)}
    assert Store('timer').element('code.auth').open_work == ('trouble',)  # what the page draws the node from
    assert 'condition' not in Store('timer').element('code.auth').to_dict()  # apart from the map, MAP-046
    assert Store('timer').element('code.clock').open_work == ()


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_every_join_is_asked_its_information_flow_direction(run, project):
    """IFD, Information Flow Direction, the primary flow of information. sends: OP to EF. receives:
    EF to OP. both: equal need. It is a field of the join, defined once in prompts.xml, a closed choice of three, kept
    with the join, and named in a notice when it is missing."""
    noun = nouns_of('purpose')['ifd']
    assert noun.schema['enum'] == ['sends', 'receives', 'both']
    assert noun.help.startswith('sends, receives or both: the information flow direction')
    run('intake', 'start', cwd=project)
    run('intake', 'element', 'code.store.state', 'role=SE', cwd=project)
    read = recorded(run, project, 'purpose', 'code.selector.route', '["code.store.state"]', 'purpose=p', 'ef=f',
                    'ifd=receives')
    write = recorded(run, project, 'purpose', 'code.protocol.sync', '["code.store.state"]', 'purpose=q', 'ef=g')
    assert 'ifd' in [notice['where'] for notice in write['notices']]
    assert 'ifd' not in [notice['where'] for notice in read['notices']]
    store = Store('timer')
    [held] = store.joins('code.selector.route', raw=True).results
    assert held.ifd == 'receives'


@pytest.mark.req('STORE-012')
def test_refs_go_to_the_sources_layer_only_while_intake_sources_is_on(run, project):
    """Refs go in a sources layer, which keeps the metaform itself the map. The refs given with an element are one item of the
    sources layer at it, and the element holds none; with intake_sources off they are not recorded."""
    path = json.dumps([{'key': 'path', 'value': 'timer.c'}])
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE', 'name_length=2', f'refs={path}')
    store = Store('timer')
    found = store.layer_items('sources', Node('element', 'code.timer.kitchen'), limit=0).results
    assert [[(ref.key, ref.value) for ref in item.refs] for item in found] == [[('path', 'timer.c')]]
    # The ref is held by the sources item and by nothing of the metaform: the one thing citing it is that item.
    assert [(cited.kind, cited.layer, cited.address) for cited in store.citing('path', 'timer.c').results] == [
        ('item', 'sources', 'code.timer.kitchen')]
    # sources is a knowledge layer, mutable, hideable and finished, never part of the metaform.
    layer = next(each for each in store.layers(limit=0).results if each.name == 'sources')
    assert (layer.kind, layer.mutable, layer.hideable, layer.ready is not None) == ('layer', True, True, True)
    # The sources layer is read at once, with no step to finish it: the where read shows the refs at the element.
    shown = store.where('code.timer.kitchen', raw=True)
    assert [ref.key for group in shown.layers if group.layer == 'sources' for item in group.items for ref in item.refs] == ['path']
    again = json.dumps([{'key': 'path', 'value': 'clock.c'}])
    recorded(run, project, 'element', 'code.timer.kitchen', f'refs={again}')
    found = store.layer_items('sources', Node('element', 'code.timer.kitchen'), limit=0).results
    assert [[(ref.key, ref.value) for ref in item.refs] for item in found] == [[('path', 'clock.c')]]
    run('set', '--no-intake-sources', cwd=project)
    off = recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', f'refs={path}')
    assert {'where': 'refs', 'message': 'intake_sources is off, so the refs were not recorded.'} in off['notices']
    # The element is still recorded, and no layer holds the refs: nothing cites the path anywhere but timer.c's item.
    assert recorded(run, project, 'show', 'receiver=code.alarm.audible')['elements'][0]['role'] == 'SE'
    assert store.citing('path', 'timer.c').results == ()
    alarm = store.element('code.alarm.audible', raw=True)
    assert alarm is not None
    held = store.node(Node('element', alarm.id), raw=True)
    assert held is not None and [group.layer for group in held.layers if any(item.refs for item in group.items)] == []


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-046')
def test_the_ignore_list_follows_the_intake_and_exclude_is_not_a_condition(run, project):
    """Exclude was meant as a metaform ignore, like gitignore, not a judgment the intake makes on what
    it sees; agents acted on exclude marks and deleted files. The person lists what is not the project in
    .metaform/ignore.txt, the intake is served with that list after it and reads nothing it names, and a condition of
    exclude sent to an intake tool records nothing and is answered with where the list is."""
    plain = stored_with_pointer().replace('{prompt}', '', 1)
    assert run('intake', 'prompt', cwd=project).stdout == plain  # no file: the intake alone
    (project / '.metaform').mkdir()
    (project / '.metaform' / 'ignore.txt').write_text('# not the project\nrich/\n\n*.zip\n', encoding='utf-8')
    assert metaform_home.ignore_patterns(project) == ['rich/', '*.zip']
    served = run('intake', 'prompt', cwd=project).stdout
    assert served.startswith(plain.rstrip('\n'))
    assert served.endswith('(.metaform/ignore.txt):\nrich/\n*.zip\n')
    assert '# not the project' not in served
    recorded(run, project, 'start')
    answer = recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'condition=exclude', 'note=stray')
    assert any(n['message'] == 'exclude is the ignore list: .metaform/ignore.txt' for n in answer['notices'])
    assert Store('timer').work(open=True, limit=0).results == ()


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-046')
def test_notes_missing_and_join_refs_are_kept_as_the_intake_records_them(run, project):
    """The served intake keeps exclusions as notes with no condition, records what is absent as missing, and gives a
    join refs where it needs them. Each was refused or lost by the tools before."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.alarm.audible', 'role=DE', 'note=exclude: a stray copy beside it')
    recorded(run, project, 'element', 'downstream.cqu.cook', 'role=CQU')
    recorded(run, project, 'purpose', 'downstream.cqu.cook', 'code.alarm.audible', 'purpose=Know when food is done',
             'ef=Sounds an alarm', 'ifd=send', 'note=the join note', 'refs=[{"key": "path", "value": "src/alarm.c"}]')
    recorded(run, project, 'element', 'code.display.digit', 'role=SE', 'condition=missing', 'note=no display yet')
    recorded(run, project, 'finish', 'report=done')
    recorded(run, project, 'element', 'downstream.cqu.cook', 'note=reads it from across the room')  # finished map
    store = Store('timer')
    graph = store.graph()
    # the base holds RE, PE, OP and EF only: each note is the node's item of the critic layer, beside it
    assert [entry.element.note for entry in graph.elements] == [None] * len(graph.elements)
    [joined] = graph.joins
    assert (joined.note, joined.ifd) == (None, 'sends')
    ids = {entry.element.address: entry.element.id for entry in graph.elements}
    critic = {(item.target.kind, item.target.id): item.value for item in store.layer_items('critic', None, limit=0).results}
    assert critic == {('element', ids['code.alarm.audible']): 'exclude: a stray copy beside it',
                      ('join', joined.id): 'the join note',
                      ('element', ids['downstream.cqu.cook']): 'reads it from across the room'}
    refused = store.refine(ids['code.alarm.audible'], {'note': 'into the base'}, reason='a check')
    assert refused.notices[0].message.startswith('The base holds RE, PE, OP and EF only; a note goes to layer critic')
    assert store.element('code.alarm.audible', raw=True).note is None
    assert [(w.condition, w.note) for w in store.work(open=True, limit=0).results] == [('missing', 'no display yet')]
    refs = [[(ref.key, ref.value) for ref in item.refs] for item in store.layer_items('sources', None, limit=0).results]
    assert [('path', 'src/alarm.c')] in refs


@pytest.mark.req('BASE-039')
def test_the_read_back_shows_marks_notes_and_what_no_root_join_reaches(run, project):
    """Found in the runs of 2026-10-08: the read-back the proof step uses showed no marks and no notes; removing an
    element left its marks open and its joins orphaned. The map comes off the CQUs' root joins, so an element no join
    reaches from them is named disconnected for the proof to correct."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.alarm.audible', 'role=DE', 'condition=trouble', 'note=it never sounds')
    recorded(run, project, 'element', 'code.display.digit', 'role=SE', 'note=exclude: a stray copy')
    recorded(run, project, 'element', 'code.light.indicator', 'role=SE')
    recorded(run, project, 'element', 'downstream.cqu.cook', 'role=CQU')
    recorded(run, project, 'purpose', 'downstream.cqu.cook', '["code.alarm.audible", "code.display.digit"]',
             'purpose=Know when food is done', 'ef=Sounds an alarm', 'ifd=sends')
    shown = recorded(run, project, 'show')
    by = {entry['namespace_address']: entry for entry in shown['elements']}
    assert (by['code.alarm.audible']['condition'], by['code.alarm.audible']['note']) == ('trouble', 'it never sounds')
    assert by['code.display.digit']['note'] == 'exclude: a stray copy'
    assert shown['roots'] == ['downstream.cqu.cook'] and shown['undescribed'] == []
    assert shown['disconnected'] == ['code.light.indicator']
    recorded(run, project, 'remove', 'namespace_address=code.alarm.audible')
    after = recorded(run, project, 'show')
    [joined] = after['purposes']
    assert joined['elements'] == ['code.display.digit']  # the join lets the removed element go
    assert Store('timer').work(open=True, limit=0).results == ()  # and its mark is closed, not left open


@pytest.mark.req('MAP-040')
def test_the_field_text_lists_exactly_the_values_the_intake_tools_accept():
    """The description beside each argument is what an agent reads as it records, so a value listed there and refused
    by the tool, or accepted and never listed, misleads it: the old text offered condition missing after it was
    ruled out."""
    from metaform.modules.intake import ELEMENT_WORDS, INTAKE_MARKS, MODULE, PURPOSE_WORDS

    def listed(words: str) -> set[str]:
        head = re.split(r'[.:]', words, maxsplit=1)[0]
        return {part.strip() for part in re.split(r',| or ', head) if part.strip() and ' ' not in part.strip()}

    nouns = {(verb.name, noun.name): noun for verb in MODULE.verbs for noun in verb.nouns}
    for verb, words in (('element', ELEMENT_WORDS), ('purpose', PURPOSE_WORDS)):
        for field in ('role', 'condition', 'ifd'):
            noun = nouns.get((verb, field))
            if noun is not None:
                assert listed(words[field]) == set(noun.schema['enum']), (verb, field, words[field])
    assert set(nouns['element', 'condition'].schema['enum']) == set(INTAKE_MARKS) | {'MISS', 'BKN', 'OK', 'broken'}


@pytest.mark.req('MAP-046')
def test_the_procedures_marks_are_taken_as_written(run, project):
    """The served procedure marks a part MISS, BKN or OK; the tools take those words, so the agent never translates."""
    started = recorded(run, project, 'start', 'result=dt-20261010')  # the result id the procedure gives at start
    assert Store('timer').layer_ref(started['layer']).result_id == 'dt-20261010'
    refused = run('intake', 'element', 'code.alarm.audible', 'role=SE', 'condition=BKN', cwd=project, ok=False)
    assert refused.returncode != 0 and 'needs a note' in refused.stderr  # BKN says what is wrong and what corrects it
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'condition=BKN', 'note=never sounds; wire the pin')
    recorded(run, project, 'element', 'code.display.digit', 'role=SE', 'condition=OK')
    recorded(run, project, 'element', 'code.display.digit', 'role=SE', 'condition=broken', 'note=blank; reseat it')
    recorded(run, project, 'element', 'code.display.digit', 'role=SE', 'condition=MISS')  # found absent on a second look
    assert sorted((w.address, w.condition) for w in Store('timer').work(open=True, limit=0).results) == \
        [('code.alarm.audible', 'trouble'), ('code.display.digit', 'missing')]  # the last condition replaces


@pytest.mark.req('MAP-046')
@pytest.mark.parametrize('first', ['element', 'join'])
def test_a_finding_on_an_element_and_its_purpose_record_is_written_once(run, project, first):
    """Replaying either merged marker keeps one ticket, including after take, and completion clears the node."""
    recorded(run, project, 'start')
    markers = {'element': ('element', 'code.alarm.audible', 'role=SE'),
               'join': ('purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=p', 'ef=f', 'ifd=receives')}
    second = 'join' if first == 'element' else 'element'
    recorded(run, project, *markers[first], 'condition=BKN', 'note=never sounds')
    said = recorded(run, project, *markers[second], 'condition=BKN', 'note=never sounds')
    assert 'kept once' in said['notices'][-1]['message']
    merged = recorded(run, project, *markers[second], 'condition=BKN', 'note=other')
    assert 'is kept in' in merged['notices'][-1]['message']  # an element and its purpose record are one node
    store = Store('timer')
    assert [(w.node_kind, w.note) for w in store.work(open=True, limit=0).results] == \
        [(first, 'never sounds\n\nother')]
    recorded(run, project, *markers[second], 'condition=BKN', 'note=never')  # inside a paragraph, still a new finding
    [ticket] = store.work(open=True, limit=0).results
    assert ticket.note.endswith('\n\nnever')
    for kind, note in ((first, 'never sounds'), (second, 'other'), (second, 'never')):
        recorded(run, project, *markers[kind], 'condition=BKN', f'note={note}')
    assert [(w.id, w.note) for w in store.work(open=True, limit=0).results] == \
        [(ticket.id, 'never sounds\n\nother\n\nnever')]
    store.take_work(ticket.id, by='claude')
    repeated = [recorded(run, project, *markers[kind], 'condition=BKN', f'note={note}')
                for kind, note in ((first, 'never sounds'), (second, 'other'))]
    assert len(store.work(open=True, limit=0).results) == 1
    assert [(w.id, w.condition, w.note) for w in store.work(open=True, limit=0).results] == \
        [(ticket.id, 'trouble', 'never sounds\n\nother\n\nnever')]
    assert all('taken' in said['notices'][-1]['message'] for said in repeated)
    store.finish_work(ticket.id, 'Alarm repaired.')
    assert store.work(open=True, limit=0).results == ()
    shown = recorded(run, project, 'show')
    assert all(held.get('condition') != 'trouble' for held in shown['purposes'])
    assert all(element.get('condition') != 'trouble' for element in shown['elements'])
    # A genuinely new note at the other part still waits behind the ticket an agent has taken.
    recorded(run, project, *markers[first], 'condition=BKN', 'note=never sounds')
    recorded(run, project, *markers[second], 'condition=BKN', 'note=other')
    [active] = store.work(open=True, limit=0).results
    store.take_work(active.id, by='claude')
    recorded(run, project, *markers[second], 'condition=BKN', 'note=volume is wrong')
    open_work = store.work(open=True, limit=0).results
    assert len(open_work) == 2
    assert [(w.id, w.note) for w in open_work if w.taken] == [(active.id, 'never sounds\n\nother')]
    assert [(w.node_kind, w.note) for w in open_work if not w.taken] == [(second, 'volume is wrong')]


@pytest.mark.req('MAP-046')
def test_trouble_and_missing_are_tickets_an_agent_starts_and_recording_them_again_adds_none(run, project):
    """An open trouble or missing finding with no task was never started by the agent starter, so nobody fixed it."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'condition=BKN', 'note=never sounds')
    recorded(run, project, 'element', 'code.display.digit', 'role=SE', 'condition=MISS')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE', 'condition=OK')
    store = Store('timer')
    first = {w.address: w for w in store.work(open=True, limit=0).results}
    assert first['code.alarm.audible'].task.startswith('never sounds\n\n') and first['code.display.digit'].task
    assert first['code.timer.kitchen'].task is None
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'condition=BKN', 'note=never sounds; wire it')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=p', 'ef=f',
             'ifd=receives', 'condition=BKN', 'note=never sounds; wire it')
    [again] = [w for w in store.work(open=True, limit=0).results if w.condition == 'trouble']
    assert (again.id, again.note) == (first['code.alarm.audible'].id, 'never sounds; wire it')
    store.take_work(again.id, by='claude')
    said = recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'condition=BKN', 'note=other')
    assert 'taken' in said['notices'][-1]['message']
    assert [w.id for w in store.work(open=True, limit=0).results if w.condition == 'trouble'] == [again.id]


@pytest.mark.req('BASE-039')
def test_a_verify_pass_writes_conditions_and_refs_onto_the_finished_map_without_a_new_base(run, project):
    """An intake on a project that already has one re-examines the finished map and records what it found on it;
    conditions and refs are kept apart from the map's shape, so a finished map takes them without a new intake."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE', 'name=timer', 'condition=MISS')
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'name=alarm')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=p', 'ef=f', 'ifd=receives')
    recorded(run, project, 'finish', 'report=done')
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'condition=OK', 'refs=[{"key": "read", "value": "t.c#L1"}]')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'condition=BKN', 'note=never fires')
    shown = recorded(run, project, 'show')
    by = {entry['namespace_address']: entry for entry in shown['elements']}
    assert (by['code.timer.kitchen']['condition'], by['code.timer.kitchen']['refs']) == \
        ('ok', [{'key': 'read', 'value': 't.c#L1'}])
    assert [(held['condition'], held['note']) for held in shown['purposes']] == [('trouble', 'never fires')]
    assert [base['name'] for base in json.loads(run('map', 'bases', '--json', cwd=project).stdout)['results']] == ['main']


@pytest.mark.req('BASE-039')
@pytest.mark.req('LAYER-025')
def test_a_changed_field_on_a_finished_map_is_refined_in_place_and_the_map_stays_active(run, project):
    """A verification pass that corrects a field of an element or purpose record on the finished map refines it, a
    new version in the map's own layer; no new base holding only the corrections becomes the active map."""
    recorded(run, project, 'start')
    for address, role in (('stakeholder.cook.home', 'CQU'), ('code.timer.kitchen', 'DE'), ('code.alarm.audible', 'SE')):
        recorded(run, project, 'element', address, f'role={role}', 'name=n')
    recorded(run, project, 'purpose', 'stakeholder.cook.home', '["code.timer.kitchen"]', 'purpose=p', 'ef=f',
             'ifd=receives')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=q', 'ef=g',
             'ifd=receives')
    recorded(run, project, 'finish')
    recorded(run, project, 'start')
    renamed = recorded(run, project, 'element', 'code.timer.kitchen', 'name=kitchen timer')
    assert renamed['base'] == 'main' and not any(notice['where'] == 'base' for notice in renamed['notices'])
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=Ring when done.')
    finished = recorded(run, project, 'finish')
    assert not any(notice['where'] == 'undescribed' for notice in finished['notices'])
    assert [base['name'] for base in json.loads(run('map', 'bases', '--json', cwd=project).stdout)['results']] == ['main']
    run('map', 'where', 'code.alarm.audible', cwd=project)
    store = Store('timer')
    kitchen = store.element('code.timer.kitchen')
    assert kitchen is not None and kitchen.name == 'kitchen timer'
    assert len(store.history(kitchen.id).results) == 2
    assert [join.purpose for join in store.joins('code.timer.kitchen').results] == ['Ring when done.']
    # a pass that adds an element first adds it to the map too, and the corrections after it still refine the map
    recorded(run, project, 'start')
    added = recorded(run, project, 'element', 'code.light.oven', 'role=SE', 'name_length=1')
    assert added['base'] == 'main' and not any(notice['where'] == 'base' for notice in added['notices'])
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.light.oven"]', 'purpose=Glow when done.',
             'ef=e', 'ifd=receives')
    recorded(run, project, 'element', 'code.alarm.audible', 'name=bell')
    finished = recorded(run, project, 'finish')
    assert (finished['base'], finished['elements']) == ('main', 4)
    assert [base['name'] for base in json.loads(run('map', 'bases', '--json', cwd=project).stdout)['results']] == ['main']
    for address in ('stakeholder.cook.home', 'code.light.oven'):
        run('map', 'where', address, cwd=project)
    alarm = Store('timer').element('code.alarm.audible')
    assert alarm is not None and alarm.name == 'bell' and len(Store('timer').history(alarm.id).results) == 2
    assert sorted(join.purpose for join in Store('timer').joins('code.timer.kitchen').results) == \
        ['Glow when done.', 'Ring when done.']


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


@pytest.mark.req('BASE-039')
@pytest.mark.req('QUAL-001')
def test_processes_recording_new_shape_on_a_finished_map_at_once_open_one_base(run, home, project):
    """Intake element calls at once, each with a new element for a finished map, open one new base that holds them
    all; none is stranded in a base of its own. Four calls, as the verifier ran: with two the window is often missed."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'stakeholder.cook.home', 'role=CQU', 'name_length=1')
    recorded(run, project, 'finish')
    spawn = multiprocessing.get_context('spawn')
    addresses = ('code.timer.kitchen', 'code.alarm.audible', 'code.light.oven', 'code.clock.wall')
    ready, failures = spawn.Barrier(len(addresses)), spawn.Queue()
    workers = [spawn.Process(target=_element_at_once, args=(str(home), str(project), address, ready, failures))
               for address in addresses]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(120)
    assert [worker.exitcode for worker in workers] == [0] * len(addresses)
    assert failures.empty(), failures.get()
    bases = [base['name'] for base in json.loads(run('map', 'bases', '--json', cwd=project).stdout)['results']]
    building = Store('timer').intake_recording().results
    assert len(bases) == 2 and len(building) == 1, (bases, [held.base for held in building])
    held = Store('timer', base=building[0].base_id)
    for address in addresses:
        element = held.element(address, raw=True)
        assert element is not None and element.layer_id == building[0].layer.id, address


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_a_join_with_no_elements_records_nothing_and_starts_no_intake(run, project):
    said = recorded(run, project, 'purpose', 'code.timer.kitchen', '[]', 'purpose=p')
    assert said['layer'] is None and [notice['where'] for notice in said['notices']] == ['elements']
    assert 'No intake yet' in run('intake', 'status', cwd=project).stdout


@pytest.mark.req('MAP-046')
@pytest.mark.req('BASE-039')
def test_removing_a_join_from_a_building_intake_closes_its_marks(run, project):
    failsafe_intake(run, project)
    recorded(run, project, 'purpose', 'code.alarm', '["code.probe.echo"]', 'condition=BKN', 'note=never fires')
    recorded(run, project, 'remove', 'receiver=code.alarm', 'provider=code.probe.echo')
    assert Store('timer').work(open=True, limit=0).results == ()


@pytest.mark.parametrize('new_base', [False, True])
def test_code_intake_follow_on_sees_committed_active_base(run, project, monkeypatch, new_base):
    from metaform import loader
    from metaform.module import Context, Module, Subscription
    from metaform.modules.intake import finish

    if new_base:
        recorded(run, project, 'start')
        recorded(run, project, 'element', 'media.previous', 'role=DE')
        recorded(run, project, 'finish')
    recorded(run, project, 'start', *(['name=code-follow-on'] if new_base else []))
    recorded(run, project, 'element', 'code.example', 'role=DE')
    recording = Store('timer').intake_recording().results[0]
    seen = []

    def follow_on(payload, ctx):
        assert ctx.project == 'timer'
        store = Store(payload['project'], base=payload['base'])
        assert store.active_base().id == recording.base_id
        assert store.layers(kind='intake', limit=0).results[0].ready is not None
        assert store.element('code.example') is not None
        seen.append(payload)
        return {'state': 'started'}

    subscriber = Module(id='follow_on', summary='Follow on.', purpose='Follow on.',
                        subscriptions=(Subscription('intake.finished', follow_on),))
    enabled = loader.enabled()
    monkeypatch.setattr(loader, 'enabled', lambda: [*enabled, subscriber])
    result = finish(Context('intake', project, store=Store('timer')))
    assert seen == [{'project': 'timer', 'base': recording.base_id, 'layer': recording.layer.id, 'code': True}]
    delivery = next(one for one in result['follow_on'] if one['module'] == 'follow_on')
    assert delivery == {'module': 'follow_on', 'status': 'completed', 'result': {'state': 'started'}}


def test_failed_follow_on_does_not_undo_finished_intake(run, project, monkeypatch):
    from metaform import loader
    from metaform.module import Context, Module, Subscription
    from metaform.modules.intake import finish

    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.example', 'role=DE')

    def unavailable(payload, ctx):
        raise RuntimeError('Service unavailable')

    subscriber = Module(id='unavailable', summary='Unavailable.', purpose='Unavailable.',
                        subscriptions=(Subscription('intake.finished', unavailable),))
    enabled = loader.enabled()
    monkeypatch.setattr(loader, 'enabled', lambda: [*enabled, subscriber])
    result = finish(Context('intake', project, store=Store('timer')))
    delivery = next(one for one in result['follow_on'] if one['module'] == 'unavailable')
    assert delivery['status'] == 'failed'
    assert 'Service unavailable' in delivery['error']
    assert Store('timer').has_intake()
    assert Store('timer').element('code.example') is not None


@pytest.mark.parametrize('address', [None, 'media.photo'])
def test_follow_on_is_not_published_without_a_finished_code_intake(run, project, monkeypatch, address):
    from metaform.module import Context
    from metaform.modules.intake import finish

    if address:
        recorded(run, project, 'start')
        recorded(run, project, 'element', address, 'role=DE')

    def unexpected(*args):
        pytest.fail('No code intake was finished.')

    monkeypatch.setattr(Context, 'publish', unexpected)
    assert 'follow_on' not in finish(Context('intake', project, store=Store('timer')))


def test_finished_code_intake_without_subscribers_keeps_regular_result(run, project):
    run('disable', 'source_placement', cwd=project)
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.example', 'role=DE')
    result = recorded(run, project, 'finish')
    assert 'follow_on' not in result
    assert result['next'] == ['metaform map code-import']
    assert result['elements'] == 1
    assert Store('timer').has_intake()
