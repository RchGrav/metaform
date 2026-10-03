"""The intake module: the Canonical Intake served by name, one atomic submission never blocked, intake state, BASE-039."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from metaform import home as metaform_home
from metaform.data import Store, export_document

pytestmark = pytest.mark.kind('fixture')

ROOT = Path(__file__).parents[5]
SPEC = ROOT / 'specifications' / 'Intake_2.1.md'  # the served intake, Rich 2026-10-03
RESOURCE = Path(__file__).parents[1] / 'resources' / 'Intake_2.1.md'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'timer & co'
    folder.mkdir()
    run('add', 'project', 'timer', str(folder))
    return folder


OBJECT_KEYS = {'namespace_address', 'role', 'name', 'name_length', 'refs', 'joins'}
JOIN_KEYS = {'type', 'provider', 'name', 'purpose', 'ef', 'verb', 'non_goal', 'refs', 'subtypes'}
# Each element of the fixture carries its name, which is stored on the element, Rich 2026-10-01, with no notice.
NAMED: set[str] = set()
SUBTYPE_KEYS = {'provider', 'ef', 'verb', 'element', 'purpose'}


def fields(given, names):
    """A record's fields as named arguments, a list or object as JSON. A field no tool names is sent as it is, so
    the chassis keeps it in the record's extra and names it, BASE-043."""
    unknown = set(given) - (OBJECT_KEYS | JOIN_KEYS | SUBTYPE_KEYS)
    return [f'{name}={json.dumps(value) if isinstance(value, (list, dict)) else value}'
            for name, value in given.items() if name in names | unknown]


def submit(run, cwd, document, tmp_path, extra=(), as_json=True):
    """Record a document's elements, joins and subtypes one object per call, as an intake agent does, then finish.
    The notices come back keyed by each object's place in the document and the field they name."""
    notes, calls = [], []

    def call(path, *args):
        result = run('intake', *args, '--json', cwd=cwd)
        calls.append(result)
        out = json.loads(result.stdout)
        notes.extend({'where': f'{path}.{notice["where"]}', 'message': notice['message']}
                     for notice in out.get('notices', []))
        return out

    start = [arg for arg in extra if arg.split('=', 1)[0] in ('model', 'role', 'blinded')]
    call('start', 'start', *start, *([f'id={document["id"]}'] if 'id' in document else []))
    elements = document['elements']
    for index, element in enumerate(elements):
        call(f'elements[{index}]', 'element', element.get('namespace_address', ''),
             *fields(element, {'role', 'name', 'name_length', 'refs'}))
    for index, element in enumerate(elements):
        for number, join in enumerate(element.get('joins', [])):
            path = f'elements[{index}].joins[{number}]'
            call(path, 'add_requirement', element['namespace_address'], join.get('provider', ''),
                 *fields(join, {'name', 'purpose', 'ef', 'verb', 'non_goal', 'refs'}))
            for place, subtype in enumerate(join.get('subtypes', [])):
                inner = subtype.get('element', {})
                call(f'{path}.subtypes[{place}]', 'subtype', element['namespace_address'], join.get('provider', ''),
                     inner.get('namespace_address', ''),
                     *fields(subtype, {'ef', 'verb', 'purpose'}),
                     *fields(inner, {'role', 'name', 'name_length', 'refs'}))
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
def test_the_served_intake_is_the_stored_file_byte_for_byte():
    """Rich, 2026-10-03: "We arent even using 2.0 its superceded". The module serves a byte copy of specifications/Intake_2.1.md; Intake 2.0 and the
    Canonical Intake stay in specifications as earlier versions and are not served."""
    assert RESOURCE.read_bytes() == SPEC.read_bytes()
    assert not RESOURCE.with_name('Canonical_Intake.xml').exists() and not RESOURCE.with_name('Intake_2.0.md').exists()


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
@pytest.mark.req('MAP-043')
def test_prompt_serves_the_intake_with_only_its_prompt_filled(run, project):
    '''Rich, 2026-10-01: the intake's prompt slot holds what the person asked for, a target or a task; with nothing
    asked it stays empty, and the intake reads that as this project. Intake 2.1 carries it as
    `{Prompt} := """{prompt}"""`, and its TARGET_RESOLUTION takes the target from it, so nothing else is filled.'''
    stored = SPEC.read_text(encoding='utf-8')
    assert '{Prompt}        := """{prompt}"""' in stored and '<target' not in stored
    out = run('intake', 'prompt', cwd=project).stdout
    assert out == stored.replace('{prompt}', '', 1)  # the intake is the instruction, and nothing is served beside it
    asked = run('intake', 'prompt', 'text=Map the timer and its alarm', cwd=project).stdout
    assert asked == stored.replace('{prompt}', 'Map the timer and its alarm', 1)


@pytest.mark.req('BASE-039')
def test_the_prompt_is_filled_as_written_in_intake_2_1_and_escaped_only_in_an_xml_intake_file(run, project, tmp_path):
    """Intake 2.1 is not XML, so what the person asks for reaches it exactly as written; an XML intake file, which the
    intake_file setting can still name, gets it escaped as an XML attribute value, as its <target> is filled."""
    asked = 'fix A & B in <main> "now"'
    stored = SPEC.read_text(encoding='utf-8')
    assert run('intake', 'prompt', f'text={asked}', cwd=project).stdout == stored.replace('{prompt}', asked, 1)
    xml = tmp_path / 'own-intake.xml'
    xml.write_text('<process><prompt text="{prompt}"/></process>\n', encoding='utf-8')
    run('set', f'--intake-file={xml}', cwd=project)
    assert run('intake', 'prompt', f'text={asked}', cwd=project).stdout == (
        '<process><prompt text="fix A &amp; B in &lt;main&gt; &quot;now&quot;"/></process>\n')


@pytest.mark.req('CLI-034')
@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_no_setting_adds_an_instruction_to_the_intake(run, project):
    """Rich, 2026-09-29: no instructions are side loaded into a workflow. What is added beside the intake competes
    with it, and the agent cannot tell which of the two is the procedure."""
    plain = run('intake', 'prompt', cwd=project).stdout
    run('set', '--debug', '--no-report', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    run('set', '--no-debug', '--report', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    assert plain == SPEC.read_text(encoding='utf-8').replace('{prompt}', '', 1)


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
    assert (report['project'], report['metaform'], report['elements'], report['requirements'], report['subtypes'],
            report['work']) == ('timer', 'main', 4, 2, 1, 0)
    assert set(notices(report)) == NAMED
    assert report['layer'] == 'intake'  # LAYER-025: no time or random part
    store = Store('timer')
    assert store.has_intake()
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.short_name, kitchen.name_length, kitchen.role, kitchen.open_work) == ('kitchen timer', 2, 'DE', ())
    assert (kitchen.name, kitchen.extra) == ('kitchen timer daemon', None)  # its own field, Rich 2026-10-01
    assert [(ref.key, ref.value) for ref in kitchen.refs] == [('path', 'src/main.c')]
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert (cook_join.provider_address, cook_join.purpose, cook_join.non_goal, cook_join.layer) == (
        'code.timer.kitchen', 'Know when each dish is done without watching the clock.', 'Plan the meal.',
        report['layer'])
    alarm_join = store.joins('code.timer.kitchen').results[0]
    assert [(ref.key, ref.value) for ref in alarm_join.refs] == [('path', 'src/alarm.c'), ('path', 'src/pins.h')]
    tick = store.subtypes(alarm_join.join_id).results[0]
    assert (tick.address, tick.ef, tick.role, tick.name) == (
        'code.loop.tick', 'tick_all subtracts one second from each running countdown.', 'SE', 'one-second tick loop')
    assert (cook_join.verb, alarm_join.verb, tick.verb) == ('tells', 'rings', 'advances')
    held = store.element('code.loop.tick')
    assert (held.element_id, held.role, held.name_length) == (tick.element_id, 'SE', 2)
    assert 'code.loop.tick' not in [root.address for root in store.roots().elements]
    layer = next(item for item in store.layers().results if item.name == report['layer'])
    assert (layer.kind, layer.mutable, layer.hideable, layer.result_id) == ('intake', False, False,
                                                                           'kitchen-timer-typology')
    provenance = store.provenance(report['layer'])
    assert (provenance.module, provenance.workflow, provenance.model, provenance.role) == (
        'intake', 'canonical-intake', 'claude', 'intake agent')
    assert provenance.prompt is None  # the Canonical Intake's purpose never changes, so no copy is kept, STORE-016
    document = export_document(['timer'], layers=[report['layer']])['projects'][0]['metaforms'][0]
    assert len(document['elements']) == 4 and len(document['joins']) == 3 and 'subtypes' not in document
    assert sorted(row['type'] for row in document['joins']) == ['require', 'require', 'subtype']  # Rich 2026-10-02
    assert all('perspective' not in row for row in document['joins'])
    assert sorted(row['verb'] for row in document['joins']) == ['advances', 'rings', 'tells']


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-044')
def test_a_name_is_recorded_wherever_a_namespace_address_and_a_name_length_are(run, project):
    """Rich, 2026-10-01: the name goes anywhere there is a namespace and name length; extra should be gone. The element
    holds its name in a field of its own, beside name_length; the join keeps the project's name for the functionality."""
    run('intake', 'start', cwd=project)
    element = json.loads(run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name_length=2',
                             'name=kitchen timer daemon', '--json', cwd=project).stdout)
    assert [notice for notice in element['notices'] if notice['where'] == 'name'] == []
    unnamed = json.loads(run('intake', 'element', 'code.alarm.audible', 'role=SE', 'name_length=2', '--json',
                             cwd=project).stdout)
    assert [notice['message'] for notice in unnamed['notices'] if notice['where'] == 'name'] == [
        'name is missing; stored empty.']
    join = json.loads(run('intake', 'add_requirement', 'code.timer.kitchen', 'code.alarm.audible', 'name=end-of-countdown alarm',
                          'purpose=Get attention.', 'ef=Rings.', 'ifd=receives',
                          'verb=rings', '--json', cwd=project).stdout)
    assert join['notices'] == []
    inner = json.loads(run('intake', 'subtype', 'code.timer.kitchen', 'code.alarm.audible', 'code.loop.tick', 'name=one-second tick',
                           'name_length=2', 'role=SE', 'ef=Ticks.', 'ifd=receives',
                           'verb=ticks', '--json', cwd=project).stdout)
    assert inner['notices'] == []
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert [row['name'] for row in shown['requirements']] == ['end-of-countdown alarm']
    kitchen = next(row for row in shown['elements'] if row['namespace_address'] == 'code.timer.kitchen')
    assert (kitchen['short_name'], kitchen['name_length'], kitchen['name'], kitchen['role']) == (
        'kitchen timer', 2, 'kitchen timer daemon', 'DE')
    assert not kitchen.get('extra')
    run('intake', 'finish', cwd=project)
    store = Store('timer')
    held = store.joins('code.timer.kitchen').results[0]
    assert (held.name, held.ifd, held.extra) == ('end-of-countdown alarm', 'receives', None)
    assert store.subtypes(held.join_id).results[0].name == 'one-second tick'
    assert (store.element('code.timer.kitchen').name, store.element('code.timer.kitchen').extra) == ('kitchen timer daemon', None)
    assert store.element('code.loop.tick').name == 'one-second tick'  # the element a subtype join holds is named too


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_no_intake_tool_takes_a_perspective():
    """Rich, 2026-10-02: "drop perspective drop the duality , EF infers fine, my reasoning is that its less reasoning,
    its locks in which direction we care about more clearly, and make it easier nd lowers mistakes". No intake tool
    takes a perspective, and no field description names one."""
    import xml.etree.ElementTree as ET
    for verb in ('add_requirement', 'subtype', 'edit'):
        assert 'perspective' not in nouns_of(verb), verb
    fields = ET.fromstring((RESOURCE.parent / 'prompts.xml').read_text(encoding='utf-8')).find('fields')
    assert fields is not None and fields.find('join/perspective') is None and fields.find('element/perspective') is None
    assert 'perspective' not in json.dumps(FIXTURE)


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-044')
def test_a_join_or_subtype_join_without_its_verb_is_stored_and_named_in_a_notice(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    del given['elements'][0]['joins'][0]['verb']
    del given['elements'][1]['joins'][0]['subtypes'][0]['verb']
    found = notices(submit(run, project, given, tmp_path))
    assert re.match(r'verb is missing\b', found['elements[0].joins[0].verb'])
    assert re.match(r'verb is missing\b', found['elements[1].joins[0].subtypes[0].verb'])
    store = Store('timer')
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert cook_join.verb is None and store.subtypes(store.joins('code.timer.kitchen').results[0].join_id).results[0].verb is None


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
@pytest.mark.req('MAP-030')
@pytest.mark.req('STORE-011')
def test_a_subtype_join_carries_its_own_purpose(run, project, tmp_path):
    """The parent is accounting and the parts are payable and receivable: each serves a share of the parent's
    purpose, and the share is its own. Kept in the extra it was set apart from the join it describes."""
    given = copy.deepcopy(FIXTURE)
    given['elements'][1]['joins'][0]['subtypes'][0]['purpose'] = 'Its own why.'
    report = submit(run, project, given, tmp_path)
    assert 'elements[1].joins[0].subtypes[0].purpose' not in notices(report)
    store = Store('timer')
    join = store.joins('code.timer.kitchen').results[0]
    tick = store.subtypes(join.join_id).results[0]
    assert tick.purpose == 'Its own why.' and not (tick.extra or {}).get('purpose')


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-026')
def test_what_does_not_fit_is_stored_as_given_and_named_in_a_notice(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    cook = given['elements'][0]
    cook['joins'][0]['provider'] = 'code.nowhere'
    cook['joins'].append({'provider': 'stakeholder.cook.home', 'purpose': 'Cook for itself.', 'ef': 'f'})
    given['elements'][2]['namespace_address'] = 'Code..Alarm'
    given['elements'][2]['colour'] = 'red'
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert {'elements[0].joins[0].provider', 'elements[0].joins[1].provider',
            'elements[2].namespace_address'} <= set(found)
    assert re.match(r"colour is not a noun of intake element; it was kept in the record's extra", found['elements[2].colour'])
    store = Store('timer')
    nowhere = store.element('code.nowhere')
    assert nowhere is not None and nowhere.role is None and nowhere.layer == report['layer']
    assert {join.provider_address for join in store.joins('stakeholder.cook.home').results} == {
        'code.nowhere', 'stakeholder.cook.home'}
    odd = store.where('Code..Alarm', raw=True)
    assert odd is not None and (odd.element.extra, odd.element.name) == ({'colour': 'red'}, 'audible alarm')


@pytest.mark.req('STORE-012')
@pytest.mark.req('STORE-004')
@pytest.mark.req('BASE-044')
def test_an_odd_ref_sent_to_an_intake_tool_is_placed_by_the_stores_one_rule(run, project):
    """The store owns what happens to a ref that is not a key and a value, STORE-012, for every writer; an intake tool
    hands its refs on as given. A ref that is a record is split into an item of its own, as the store does with any
    list of records in an extra, STORE-004, which a second copy of the rule in the intake module never did."""
    recorded(run, project, 'start')
    made = recorded(run, project, 'element', 'code.probe.echo', 'role=SE', 'name_length=1', 'name=echo probe',
                    'refs=[["path", "src/echo.c"], {"path": "src/pins.h"}]')
    messages = [(notice['where'], notice['message']) for notice in made['notices']]
    assert messages == [
        ('refs', 'A ref is a key and a value, both text; one was not, and kept in the extra under refs.'),
        ('extra', 'extra.refs on code.probe.echo held a list of records; each was stored as its own item.')]
    store = Store('timer')
    echo = store.element('code.probe.echo', raw=True)
    assert echo is not None and [(ref.key, ref.value) for ref in echo.refs] == [('path', 'src/echo.c')]
    assert echo.extra is None
    items = [item for item in store.layer_items(made['layer']).results if getattr(item, 'value', None) is not None]
    assert [item.value for item in items] == [{'refs': {'path': 'src/pins.h'}}]


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_refs_that_are_not_text_are_kept_in_the_extra_and_counted_in_words(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    given['elements'][1]['refs'] = [['path', 'src/timer.c'], ['line', 12], ['col', 3]]
    given['elements'][0]['joins'][0]['refs'] = [['line', 12]]
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert found['elements[1].refs'] == ('A ref is a key and a value, both text; two were not, and kept in the extra '
                                         'under refs.')
    assert found['elements[0].joins[0].refs'] == ('A ref is a key and a value, both text; one was not, and kept in '
                                                  'the extra under refs.')
    store = Store('timer')
    timer = store.element(given['elements'][1]['namespace_address'], raw=True)
    assert timer is not None and [(ref.key, ref.value) for ref in timer.refs] == [('path', 'src/timer.c')]
    assert timer.extra is not None and timer.extra['refs'] == [['line', 12], ['col', 3]]


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-045')
@pytest.mark.req('STORE-041')
def test_a_second_intake_is_stored_as_a_new_active_metaform_and_the_first_is_kept(run, project, tmp_path, home):
    first = submit(run, project, FIXTURE, tmp_path)
    main = metaform_home.active_metaform('timer')
    before = metaform_home.store_path('timer', main.metaform_id).read_bytes()
    changed = copy.deepcopy(FIXTURE)
    changed['elements'][2]['namespace_address'] = 'code.alarm.visual'
    changed['elements'][1]['joins'][0]['provider'] = 'code.alarm.visual'
    second = submit(run, project, changed, tmp_path)
    assert re.fullmatch(r'intake-\d{8}T\d{6}Z(-\d+)?', second['metaform'])
    active = metaform_home.active_metaform('timer')
    assert active.name == second['metaform'] and active.metaform_id != main.metaform_id
    assert any('metaform activate metaform main' in notice['message'] for notice in second['notices'])
    store = Store('timer')
    assert store.element('code.alarm.visual') is not None and store.element('code.alarm.audible') is None
    assert metaform_home.store_path('timer', main.metaform_id).read_bytes() == before
    run('activate', 'metaform', 'main', cwd=project)
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
    made = json.loads(run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=exclude',
                          'note=alarm.c conflicts with specifications/alarm.md:12', 'task=review the code against the linked specification', '--json',
                          cwd=project).stdout)
    assert made['condition'] == 'exclude'
    assert made['notices'] == []
    report = submit(run, project, copy.deepcopy(FIXTURE), tmp_path,
                    extra=('report=The alarm pin is unconnected.', 'feedback=The subtype fields were clear.'))
    assert report['work'] == 1
    layer_id = Store('timer').layers(kind='intake').results[0].layer_id
    folder = metaform_home.project_folder('timer') / 'reports'
    assert (folder / f'{layer_id}-report.md').read_text(encoding='utf-8') == 'The alarm pin is unconnected.'
    assert (folder / f'{layer_id}-feedback.md').read_text(encoding='utf-8') == 'The subtype fields were clear.'
    assert sorted(path.name for path in project.iterdir()) == []
    listed = json.loads(run('list', 'reports', '--json', cwd=project).stdout)['results']
    assert sorted((row['name'], row['kind']) for row in listed) == [
        (f'{layer_id}-feedback.md', 'feedback'), (f'{layer_id}-report.md', 'report')]
    provenance = Store('timer').provenance(report['layer'])
    assert sorted((ref.key, ref.value) for ref in provenance.refs) == [
        ('feedback', f'{layer_id}-feedback.md'), ('report', f'{layer_id}-report.md')]
    exclude = json.loads(run('map', 'work', 'condition=exclude', '--json', cwd=project).stdout)['results']
    assert [(row['address'], row['condition'], row['note'], row['task']) for row in exclude] == [
        ('code.alarm.audible', 'exclude', 'alarm.c conflicts with specifications/alarm.md:12', 'review the code against the linked specification')]
    assert Store('timer').element('code.alarm.audible').open_work == ('exclude',)


@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_the_intake_tools_carry_no_condition_field_and_a_flag_sent_anyway_is_kept_in_extra(run, project, tmp_path):
    for verb in ('element', 'add_requirement', 'subtype', 'edit'):
        assert not {'flag', 'flag_note'} & set(nouns_of(verb)), verb
    given = copy.deepcopy(FIXTURE)
    given['elements'][2]['flag'] = 'broken'
    report = submit(run, project, given, tmp_path)
    assert report['work'] == 0 and 'elements[2].flag' in notices(report)
    alarm = Store('timer').element('code.alarm.audible')
    assert alarm.open_work == () and (alarm.extra, alarm.name) == ({'flag': 'broken'}, 'audible alarm')
    assert not hasattr(alarm, 'flag')


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-016')
def test_two_elements_with_one_address_are_one_element_holding_both_joins(run, project, tmp_path):
    doubled = copy.deepcopy(FIXTURE)
    doubled['elements'].append({'namespace_address': 'stakeholder.cook.home', 'role': 'CQU', 'joins': [
        {'provider': 'code.alarm.audible', 'purpose': 'Hear it from the next room.', 'ef': 'Rings loudly.',
         'ifd': 'receives', 'verb': 'reaches'}]})
    report = submit(run, project, doubled, tmp_path)
    assert set(notices(report)) == NAMED
    joins = Store('timer').joins('stakeholder.cook.home').results
    assert sorted(join.provider_address for join in joins) == ['code.alarm.audible', 'code.timer.kitchen']


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
    """Rich, 2026-10-02: the no-intake notice is needed to onboard; and when an intake is started and aborted, the next
    agent is told that an intake was started but aborted and still remains to be completed. A finished intake clears
    both."""
    import xml.etree.ElementTree as ET
    prompts = ET.fromstring(RESOURCE.with_name('prompts.xml').read_text(encoding='utf-8'))
    notice, line = (prompts.findtext(name, '').strip() for name in ('no_intake', 'unfinished'))
    record = (ROOT / 'specifications' / 'spec' / '06-mcp-install.md').read_text(encoding='utf-8')
    assert line == 'An intake was started but aborted and still remains to be completed.' and line in record
    assert notice.startswith('This project has no intake yet. Have a subagent perform it.') and notice in record
    assert 'metaform intake prompt' in notice
    agents = lambda: run('help', 'agents', cwd=project).stdout  # noqa: E731
    shown = agents()
    assert notice in shown and line not in shown
    run('intake', 'start', cwd=project)
    shown = agents()
    assert line in shown and notice not in shown
    run('intake', 'finish', cwd=project)
    shown = agents()
    assert line not in shown and notice not in shown
    run('intake', 'start', cwd=project)  # a second intake, in a new metaform, while the first is finished
    assert line in agents()


@pytest.mark.req('MCP-027')
def test_the_no_intake_notice_suggests_a_blind_spot_challenge_and_a_best_practices_layer_and_asks(run, project):
    """MCP-027: offering an intake, the agent suggests also creating a blind spot challenge and a knowledge layer that
    records best practices, and asks the person whether that is all right. The suggestion comes after the sentence on
    delegating the intake, and leaves with the notice once an intake is finished."""
    import xml.etree.ElementTree as ET
    prompts = ET.fromstring(RESOURCE.with_name('prompts.xml').read_text(encoding='utf-8'))
    notice = prompts.findtext('no_intake', '').strip()
    delegate = notice.index('Have a subagent perform it.')
    for words in ('blind spot challenge', 'knowledge layer', 'best practices', 'ask the person'):
        assert notice.find(words) > delegate, words
    suggestion = notice[notice.index('blind spot challenge'):]
    assert suggestion in run('help', 'agents', cwd=project).stdout
    run('intake', 'start', cwd=project)
    run('intake', 'finish', cwd=project)
    assert 'blind spot challenge' not in run('help', 'agents', cwd=project).stdout


@pytest.mark.req('MAP-041')
@pytest.mark.req('MAP-042')
def test_an_artifact_that_is_not_software_is_mapped_the_same_way(run, tmp_path):
    photos = tmp_path / 'photos'
    photos.mkdir()
    (photos / 'kitchen.jpg').write_bytes(b'\xff\xd8\xff')
    run('add', 'project', 'photos', str(photos), 'artifact', 'kitchen_photos')
    document = {'elements': [
        {'namespace_address': 'media.photo.product', 'role': 'AUE', 'name': 'kitchen photos'},
        {'namespace_address': 'stakeholder.seller', 'role': 'CQU', 'joins': [
            {'provider': 'media.photo.subject', 'purpose': 'Show the object at its best.', 'ef': 'Frames it.',
             'ifd': 'receives'}]},
        {'namespace_address': 'media.photo.subject', 'role': 'DE'}]}
    submit(run, photos, document, tmp_path)
    store = Store('photos')
    assert store.element('media.photo.product').role == 'AUE' and store.element('media.photo.subject').role == 'DE'
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
    prompt, and a stored prompt of the same name does not reach it, Rich 2026-09-26."""
    from metaform.data import prompts
    first = run('intake', 'prompt', cwd=project).stdout
    assert without_target(first).startswith(without_target(RESOURCE.read_text(encoding='utf-8')))
    assert prompts.prompts() == ()
    prompts.add_prompt('canonical-intake', 'xml', '<!-- edited in the viewer -->\n<process/>\n')
    assert run('intake', 'prompt', cwd=project).stdout == first
    result = submit(run, project, FIXTURE, tmp_path)
    store = Store('timer')
    layer = store.layer_ref(result['layer'])
    assert prompts.use_of('timer', layer.metaform_id, layer.layer_id) is None
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
    assert prompts.use_of('timer', layer.metaform_id, layer.layer_id) is None
    assert Store('timer').provenance(result['layer']).prompt is None


@pytest.mark.req('BASE-039')
@pytest.mark.req('STORE-032')
def test_a_building_intake_is_seen_only_through_intake_show_until_it_finishes(run, project):
    """Rich, 2026-09-26: the intake is recorded object by object as it is reasoned; agents read it back while it is
    built, and only a finished intake reaches every other read."""
    run('intake', 'start', 'model=claude', 'role=intake agent', cwd=project)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', 'name=Home cook', cwd=project)
    made = json.loads(run('intake', 'add_requirement', 'stakeholder.cook.home', 'code.timer.kitchen',
                          'purpose=Know when each dish is done.', 'ef=Counts down and rings.', 'ifd=receives',
                          'verb=tells', '--json', cwd=project).stdout)
    assert [notice['where'] for notice in made['notices']] == ['provider']
    assert 'code.timer.kitchen was not an element' in made['notices'][0]['message']
    store = Store('timer')
    assert not store.has_intake() and store.element('stakeholder.cook.home') is None
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert (len(shown['elements']), len(shown['requirements']), len(shown['requirements'][0]['subtypes'])) == (2, 1, 0)
    assert shown['undescribed'] == ['code.timer.kitchen']
    assert 'Intake: being recorded' in run(cwd=project).stdout
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name=kitchen timer', cwd=project)
    assert json.loads(run('intake', 'show', '--json', cwd=project).stdout)['undescribed'] == []
    finished = json.loads(run('intake', 'finish', '--json', cwd=project).stdout)
    assert (finished['elements'], finished['requirements']) == (2, 1)
    store = Store('timer')
    assert store.has_intake() and store.element('code.timer.kitchen').role == 'DE'
    assert store.provenance(finished['layer']).model == 'claude'


@pytest.mark.req('BASE-039')
@pytest.mark.req('STORE-032')
@pytest.mark.req('BASE-044')
def test_edit_and_remove_change_a_building_intake_and_a_finished_one_changes_only_by_refining(run, project):
    run('intake', 'start', cwd=project)
    run('intake', 'element', 'code.a', 'role=DE', cwd=project)
    run('intake', 'element', 'code.b', 'role=SE', cwd=project)
    run('intake', 'add_requirement', 'code.a', 'code.b', 'purpose=p', 'ef=f', 'verb=v', cwd=project)
    run('intake', 'add_requirement', 'code.b', 'code.a', 'purpose=q', 'ef=g', 'verb=w', cwd=project)
    run('intake', 'edit', 'receiver=code.a', 'provider=code.b', 'purpose=The better purpose.', cwd=project)
    run('intake', 'remove', 'receiver=code.b', 'provider=code.a', cwd=project)
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert [(row['receiver'], row['provider'], row['purpose']) for row in shown['requirements']] == [
        ('code.a', 'code.b', 'The better purpose.')]
    run('intake', 'finish', cwd=project)
    late = json.loads(run('intake', 'edit', 'receiver=code.a', 'provider=code.b', 'purpose=Too late.', '--json',
                          cwd=project).stdout)
    assert 'map refine' in late['notices'][0]['message'] and 'correction' not in late['notices'][0]['message']
    gone = json.loads(run('intake', 'remove', 'receiver=code.a', 'provider=code.b', '--json', cwd=project).stdout)
    assert 'map refine' in gone['notices'][0]['message'] and 'correction' not in gone['notices'][0]['message']
    assert [join.purpose for join in Store('timer').joins('code.a').results] == ['The better purpose.']


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
    layer_id = Store('timer').layers(kind='intake').results[0].layer_id
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
    layer_id = Store('timer').layers(kind='intake').results[0].layer_id
    kept = (metaform_home.project_folder('timer') / 'reports' / f'{layer_id}-report.md').read_text(encoding='utf-8')
    assert kept == str(secret)


@pytest.mark.req('BASE-039')
@pytest.mark.req('LAYER-010')
@pytest.mark.req('BASE-044')
def test_a_resumed_intake_keeps_the_provenance_the_agent_gives_that_its_layer_lacks(run, project):
    """An orchestrator starts the intake with the model; the agent's own start resumes it and gives its role and its
    result's id. What the layer lacks is filled in; what it already holds is kept, and a different value is named."""
    from metaform.data import Store
    first = json.loads(run('intake', 'start', 'model=opus', '--json', cwd=project).stdout)
    again = json.loads(run('intake', 'start', 'model=opus', 'role=intake agent', 'id=result-1', 'blinded=false',
                           '--json', cwd=project).stdout)
    assert again['layer'] == first['layer']
    store = Store('timer')
    kept = store.provenance(first['layer'])
    assert (kept.model, kept.role, kept.blinded) == ('opus', 'intake agent', False)
    assert [layer.result_id for layer in store.layers(kind='intake', limit=0).results] == ['result-1']
    third = json.loads(run('intake', 'start', 'model=sonnet', '--json', cwd=project).stdout)
    assert any(notice['where'] == 'model' and 'opus' in notice['message'] and 'sonnet' in notice['message']
               for notice in third['notices'])
    assert store.provenance(first['layer']).model == 'opus'


def recorded(run, cwd, *args):
    return json.loads(run('intake', *args, '--json', cwd=cwd).stdout)


def failsafe_intake(run, project):
    """A building intake where an operator requires a gateway failsafe and an echo probe the failsafe can absorb, and
    an alarm requires the probe too."""
    recorded(run, project, 'start')
    for address, role in (('stakeholder.operator', 'CQU'), ('code.failsafe.gateway', 'DE'), ('code.probe.echo', 'SE'),
                          ('code.alarm', 'SE')):
        recorded(run, project, 'element', address, f'role={role}', 'name_length=1')
    recorded(run, project, 'add_requirement', 'stakeholder.operator', 'code.failsafe.gateway',
             'purpose=Catch a dead gateway.', 'ef=Probes the gateway and fails over.', 'verb=watches')
    recorded(run, project, 'add_requirement', 'stakeholder.operator', 'code.probe.echo', 'name=echo probe',
             'purpose=Know the gateway answers.', 'ef=Sends an echo each second.', 'verb=pings',
             'non_goal=Measure latency.', 'refs=[{"key": "path", "value": "src/echo.c"}]')
    recorded(run, project, 'add_requirement', 'code.alarm', 'code.probe.echo', 'purpose=Hear a lost echo.',
             'ef=Reports each lost echo.', 'verb=tells')


ID_KEYS = {'id', 'join_id', 'element_id', 'parent', 'layer_id'}
STORE_ID = re.compile(r'[0-9a-f]{32}')


def keys_in(found):
    """Every key of a result, at any depth."""
    if isinstance(found, dict):
        return [*found, *(key for value in found.values() for key in keys_in(value))]
    if isinstance(found, list):
        return [key for value in found for key in keys_in(value)]
    return []


def handed_ids(result):
    """What in a result hands the agent an id or a join: a key naming one at any depth, or a store id anywhere in it,
    a notice's message included."""
    keys = keys_in(result)
    return ([key for key in keys if key in ID_KEYS or 'join' in key] + STORE_ID.findall(json.dumps(result)))


@pytest.mark.req('BASE-039')
def test_the_agent_adds_a_requirement_and_is_never_handed_an_id_or_a_join(run, project):
    """Rich, 2026-10-02: "you need to have the AI submit stuff how it is being reasoned and then extract the joins,
    joins are a database concept"; "It's, it's just adding a fucking requirement. Why even use the word join?" The
    intake tool names a requirement by the element that requires and the element that serves it, a subpart by its
    address inside that requirement, and an element by its address; no verb, noun or result names a join or an id."""
    from metaform.modules.intake import MODULE
    names = [verb.name for verb in MODULE.verbs]
    assert 'add_requirement' in names and not [name for name in names if 'join' in name]
    for verb in MODULE.verbs:
        taken = {noun.name for noun in verb.nouns} - ({'id'} if verb.name == 'start' else set())
        assert not [name for name in taken if 'join' in name or name in ID_KEYS | {'into', 'type'}], verb.name
    failsafe_intake(run, project)
    results = [
        recorded(run, project, 'element', 'code.siren', 'role=SE', 'name_length=1'),
        recorded(run, project, 'add_requirement', 'code.alarm', 'code.failsafe.gateway', 'purpose=Know of a failover.',
                 'ef=Reports each failover.', 'verb=tells'),
        recorded(run, project, 'subtype', 'stakeholder.operator', 'code.failsafe.gateway', 'code.probe.ping',
                 'role=SE', 'name_length=1', 'ef=Sends a ping.', 'verb=pings'),
        recorded(run, project, 'show'),
        recorded(run, project, 'show', 'receiver=code.alarm'),
        recorded(run, project, 'edit', 'receiver=code.alarm', 'provider=code.failsafe.gateway', 'purpose=p'),
        recorded(run, project, 'remove', 'receiver=code.alarm', 'provider=code.failsafe.gateway'),
        recorded(run, project, 'absorb', 'stakeholder.operator', 'code.probe.echo', 'stakeholder.operator',
                 'code.failsafe.gateway'),
        recorded(run, project, 'finish'),
        recorded(run, project, 'edit', 'receiver=stakeholder.operator', 'provider=code.failsafe.gateway', 'purpose=q'),
        recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.failsafe.gateway'),
        recorded(run, project, 'absorb', 'code.alarm', 'code.probe.echo', 'stakeholder.operator',
                 'code.failsafe.gateway'),
    ]
    assert [found for result in results for found in handed_ids(result)] == []


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_a_requirement_named_twice_by_the_same_two_elements_is_changed_only_when_named_alone(run, project):
    """Two requirements of one element on the same provider cannot be told apart by their addresses: an edit or a
    removal naming them changes neither, and its notice lists both purposes."""
    recorded(run, project, 'start')
    recorded(run, project, 'add_requirement', 'code.a', 'code.b', 'purpose=First why.', 'ef=f', 'verb=v')
    recorded(run, project, 'add_requirement', 'code.a', 'code.b', 'purpose=Second why.', 'ef=g', 'verb=w')
    edited = recorded(run, project, 'edit', 'receiver=code.a', 'provider=code.b', 'purpose=Changed.')
    removed = recorded(run, project, 'remove', 'receiver=code.a', 'provider=code.b')
    for result in (edited, removed):
        message = ' '.join(notice['message'] for notice in result['notices'])
        assert 'First why.' in message and 'Second why.' in message
    part = recorded(run, project, 'subtype', 'code.a', 'code.b', 'code.c', 'ef=h', 'verb=x')
    recorded(run, project, 'add_requirement', 'code.d', 'code.e', 'purpose=Third why.', 'ef=i', 'verb=y')
    folded = recorded(run, project, 'absorb', 'code.d', 'code.e', 'code.a', 'code.b')
    for result in (part, folded):
        message = ' '.join(notice['message'] for notice in result['notices'])
        assert 'First why.' in message and 'Second why.' in message
    shown = recorded(run, project, 'show')
    assert sorted(row['purpose'] for row in shown['requirements']) == ['First why.', 'Second why.', 'Third why.']
    assert [sub for row in shown['requirements'] for sub in row['subtypes']] == []


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-031')
@pytest.mark.req('MAP-040')
def test_absorb_makes_a_recorded_requirement_a_subtype_inside_its_parents_requirement(run, project):
    """Rich, 2026-09-27: an element always appears as one element record; annealing places it in its parent's join as
    a subtype join, and the element itself does not move."""
    failsafe_intake(run, project)
    absorbed = recorded(run, project, 'absorb', 'stakeholder.operator', 'code.probe.echo', 'stakeholder.operator',
                        'code.failsafe.gateway')
    assert 'code.alarm' in ' '.join(notice['message'] for notice in absorbed['notices'])
    shown = recorded(run, project, 'show')
    assert sorted((row['receiver'], row['provider']) for row in shown['requirements']) == [
        ('code.alarm', 'code.probe.echo'), ('stakeholder.operator', 'code.failsafe.gateway')]
    [sub] = next(row for row in shown['requirements'] if row['receiver'] == 'stakeholder.operator')['subtypes']
    assert (sub['namespace_address'], sub['name'], sub['ef'], sub['verb'], sub['non_goal'], sub['purpose'],
            sub['extra']) == (
        'code.probe.echo', 'echo probe', 'Sends an echo each second.', 'pings', 'Measure latency.',
        'Know the gateway answers.', None)  # absorbed, it keeps its purpose as its own
    assert sub['refs'] == [{'key': 'path', 'value': 'src/echo.c'}]
    [element] = [row for row in shown['elements'] if row['namespace_address'] == 'code.probe.echo']
    assert element['role'] == 'SE'
    recorded(run, project, 'remove', 'receiver=code.alarm', 'provider=code.probe.echo')
    finished = recorded(run, project, 'finish')
    assert (finished['elements'], finished['requirements'], finished['subtypes']) == (4, 1, 1)
    store = Store('timer')
    assert 'code.probe.echo' not in [root.address for root in store.roots().elements]
    assert 'code.probe.echo' not in [placed.element.address for placed in store.graph().elements]
    [parent] = store.joins('stakeholder.operator').results
    assert [sub.address for sub in store.subtypes(parent.join_id).results] == ['code.probe.echo']
    assert store.element('code.probe.echo').element_id == store.subtypes(parent.join_id).results[0].element_id


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
def test_show_reads_one_receivers_requirements_and_what_they_hold(run, project):
    """Rich, 2026-09-27: the intake must not depend on the size of the agent's context."""
    failsafe_intake(run, project)
    recorded(run, project, 'absorb', 'stakeholder.operator', 'code.probe.echo', 'stakeholder.operator',
             'code.failsafe.gateway')
    operator = recorded(run, project, 'show', 'receiver=stakeholder.operator')
    assert [row['provider'] for row in operator['requirements']] == ['code.failsafe.gateway']
    assert [sub['namespace_address'] for sub in operator['requirements'][0]['subtypes']] == ['code.probe.echo']
    assert {row['namespace_address'] for row in operator['elements']} == {
        'stakeholder.operator', 'code.failsafe.gateway', 'code.probe.echo'}
    alarm = recorded(run, project, 'show', 'receiver=code.alarm')
    assert [row['provider'] for row in alarm['requirements']] == ['code.probe.echo']
    assert alarm['requirements'][0]['subtypes'] == []


@pytest.mark.req('BASE-039')
def test_edit_and_remove_name_an_element_a_requirement_and_a_subtype_by_their_addresses(run, project):
    """A Fable intake on 2026-09-27 crashed its own script expecting join_id where intake_show said id; there are no
    ids to expect: each thing is named by the addresses the agent reasoned."""
    failsafe_intake(run, project)
    recorded(run, project, 'subtype', 'stakeholder.operator', 'code.failsafe.gateway', 'code.probe.ping', 'role=SE',
             'name_length=1', 'ef=Sends a ping.', 'verb=pings')
    recorded(run, project, 'edit', 'namespace_address=code.alarm', 'name_length=2')
    recorded(run, project, 'edit', 'receiver=stakeholder.operator', 'provider=code.failsafe.gateway',
             'namespace_address=code.probe.ping', 'ef=Sends a ping each second.')
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.probe.echo')
    again = recorded(run, project, 'show')
    assert next(row for row in again['elements'] if row['namespace_address'] == 'code.alarm')['name_length'] == 2
    assert [(row['receiver'], row['provider'], sub['namespace_address'], sub['ef'])
            for row in again['requirements'] for sub in row['subtypes']] == [
        ('stakeholder.operator', 'code.failsafe.gateway', 'code.probe.ping', 'Sends a ping each second.')]
    assert ('stakeholder.operator', 'code.probe.echo') not in [(row['receiver'], row['provider'])
                                                               for row in again['requirements']]
    moved = recorded(run, project, 'edit', 'receiver=code.alarm', 'provider=code.probe.echo',
                     'to_receiver=stakeholder.operator')
    assert moved['notices'] == []
    assert ('stakeholder.operator', 'code.probe.echo') in [(row['receiver'], row['provider'])
                                                           for row in recorded(run, project, 'show')['requirements']]
    assert 'namespace_address' in nouns_of('element') and 'address' not in nouns_of('element')
    assert {'parent_receiver', 'parent_provider', 'namespace_address'} <= set(nouns_of('subtype'))
    assert not {'receiver', 'provider'} & set(nouns_of('subtype'))  # the intake's provider of a part is the part
    assert {'receiver', 'provider', 'parent_receiver', 'parent_provider'} <= set(nouns_of('absorb'))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-003')
def test_edit_never_moves_an_element_and_moves_a_requirement_to_another_receiver(run, project):
    failsafe_intake(run, project)
    kept = recorded(run, project, 'edit', 'namespace_address=code.alarm', 'to_address=code.alarm.siren', 'role=NE')
    [named] = [notice for notice in kept['notices'] if notice['where'] == 'to_address']
    assert 'cannot be moved' in named['message']
    shown = recorded(run, project, 'show')
    alarm = next(row for row in shown['elements'] if row['namespace_address'] == 'code.alarm')
    assert alarm['role'] == 'NE'
    assert 'code.alarm.siren' not in [row['namespace_address'] for row in shown['elements']]
    moved = recorded(run, project, 'edit', 'receiver=code.alarm', 'provider=code.probe.echo',
                     'to_receiver=code.failsafe.gateway')
    assert moved['notices'] == []
    again = recorded(run, project, 'show', 'receiver=code.failsafe.gateway')
    assert [(row['provider'], row['purpose']) for row in again['requirements']] == [('code.probe.echo',
                                                                                     'Hear a lost echo.')]
    assert recorded(run, project, 'show', 'receiver=code.alarm')['requirements'] == []
    recorded(run, project, 'finish')
    late = recorded(run, project, 'absorb', 'stakeholder.operator', 'code.probe.echo', 'stakeholder.operator',
                    'code.failsafe.gateway')
    assert 'map refine' in late['notices'][0]['message'] and 'correction' not in late['notices'][0]['message']
    assert sorted(join.provider_address for join in Store('timer').joins('stakeholder.operator').results) == [
        'code.failsafe.gateway', 'code.probe.echo']


@pytest.mark.req('MAP-017')
@pytest.mark.req('STORE-025')
def test_the_cestui_que_use_is_the_role_cqu_and_ve_is_no_longer_a_role(run, project):
    """Rich, 2026-10-01: VE is changed to CQU, Cestui Que Use, throughout. The Canonical Intake names the roles
    AUE, CQU, DE, SE and NE; an element given CQU is stored without a notice and is the map's entry beside the DE."""
    run('intake', 'start', 'model=claude', 'role=intake agent', cwd=project)
    kept = json.loads(run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', 'name_length=2', '--json',
                          cwd=project).stdout)
    assert not [notice for notice in kept.get('notices', []) if notice['where'] == 'role']
    old = json.loads(run('intake', 'element', 'stakeholder.diner', 'role=VE', 'name_length=1', '--json',
                         cwd=project).stdout)
    [said] = [notice['message'] for notice in old['notices'] if notice['where'] == 'role']
    assert said == "'VE' is not AUE, CQU, DE, SE or NE; it was stored as given."
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name_length=2', cwd=project)
    run('intake', 'finish', cwd=project)
    roots = json.loads(run('map', 'roots', '--json', cwd=project).stdout)
    assert {item['element']['address'] for item in roots['entry']} == {'stakeholder.cook.home', 'code.timer.kitchen'}


FIELDS = {'element': ('namespace_address', 'role', 'name_length', 'name', 'refs'),
          'join': ('receiver', 'provider', 'purpose', 'ef', 'verb', 'non_goal', 'refs')}
SUBTYPE_FIELDS = {'join': ('purpose', 'ef', 'verb', 'non_goal'),
                  'element': ('namespace_address', 'name_length', 'name', 'refs')}


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-031')
def test_each_recorded_field_is_described_once_from_the_intake_modules_prompts_file():
    """Rich, 2026-10-01: the field definitions are not parsed out of the Canonical Intake, which is being refined and
    no longer carries the response schema. Each one is written once, in the intake module's prompts.xml under
    <fields>, and every tool that takes the field shows those words."""
    import xml.etree.ElementTree as ET
    written = ET.parse(Path(__file__).parents[1] / 'resources' / 'prompts.xml').getroot().find('fields')
    assert written is not None
    assert [group.tag for group in written] == ['element', 'join']  # a subtype join is a join holding an element
    for verb, groups in (('element', {'element': FIELDS['element']}), ('add_requirement', {'join': FIELDS['join']}),
                         ('subtype', SUBTYPE_FIELDS)):
        nouns = nouns_of(verb)
        for group, names in groups.items():
            for field in names:
                said = written.findtext(f'{group}/{field}')
                assert said and said.strip() == nouns[field].help, (verb, field)
    for field in ('purpose', 'ef', 'verb', 'non_goal'):
        assert nouns_of('edit')[field].help == nouns_of('add_requirement')[field].help
    source = (Path(__file__).parents[1] / '__init__.py').read_text(encoding='utf-8')
    assert 'schema//elements' not in source and 'SET perspective' not in source  # the Canonical Intake is not parsed for them


@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
def test_no_intake_or_map_tool_takes_relation_or_observation():
    """Rich, 2026-10-02: "observation was not my design. I didn't ask for observation"; "Neither was relation". The
    intake tools and the map knowledge tool stop taking both, and verb is the verb ef opens with."""
    from metaform.modules.intake import MODULE
    from metaform.modules.map import MODULE as MAP
    taken = {(module.id, verb.name, noun.name) for module in (MODULE, MAP) for verb in module.verbs
             for noun in verb.nouns if noun.name in ('relation', 'observation')}
    assert taken == set()
    knowledge = {noun.name: noun for noun in next(verb for verb in MAP.verbs if verb.name == 'knowledge').nouns}
    assert 'relation' not in knowledge['verb'].help and 'the verb ef opens with' in knowledge['verb'].help


BANNED = ('encounter of a function', 'function of an encounter', 'functionality of the encounter',
          'function of the encounter')
# Which glossary lines each field carries, Rich 2026-10-02: "I think the long field descriptions get these".
GLOSSED = {'element/namespace_address': ('Element', 'Entity', 'AT'), 'element/role': ('AUE', 'CQU', 'DE', 'SE', 'NE'),
           'join/receiver': ('RE', 'Join'), 'join/provider': ('PE',), 'join/purpose': ('OP',), 'join/ef': ('EF',),
           'join/ifd': ('IFD',)}
UNGLOSSED = {'element/name_length': 'name length', 'element/name': 'name', 'element/refs': 'refs',
             'element/condition': 'condition: missing, broken, exclude', 'element/note': 'note',
             'join/verb': 'verb', 'join/non_goal': 'non-goal', 'join/refs': 'refs',
             'join/condition': 'condition: missing, broken, exclude', 'join/note': 'note',
             'element/extra': 'extra', 'join/extra': 'extra', 'element/to_address': 'new namespace address',
             'join/parent_receiver': 'parent receiver', 'join/parent_provider': 'parent provider',
             'join/to_receiver': 'new receiver', 'join/to_provider': 'new provider'}
RECORDING = ('element', 'add_requirement', 'subtype', 'absorb', 'show', 'edit', 'remove')


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-031')
def test_every_noun_of_the_intakes_recording_verbs_takes_its_words_from_the_prompts_file():
    """Rich, 2026-10-02: "The fields only need to carry the term of you want me to create dense descriptions I can."
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


GLOSSARY = ROOT / 'specifications' / 'Intake_2.1.md'  # the fields carry the served intake's glossary


def glossary():
    """Intake 2.1's GLOSSARY lines by term, each written as its term, a colon, and the text after ':= '. An entry that
    runs onto a second line keeps its line break, without the alignment spaces."""
    text = GLOSSARY.read_text(encoding='utf-8')
    block = text.split('# ---------- GLOSSARY', 1)[1].split('# ----------', 1)[0].splitlines()[1:]
    lines: dict[str, str] = {}
    term = ''
    for line in block:
        found = re.match(r'\s*\{(\w+)\}\s*:= (.*)$', line)
        if found:
            term = found.group(1)
            lines[term] = f'{term}: {found.group(2)}'
        elif line.strip():
            lines[term] += '\n' + line.strip()
    return lines


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
@pytest.mark.req('MCP-031')
def test_each_intake_field_carries_the_intake_2_glossary_lines_word_for_word():
    """Rich, 2026-10-02, on the intake tool fields: "I think the long field descriptions get these", pasting Intake
    2.0's glossary lines; the fields now carry Intake 2.1's lines in place of 2.0's, for AUE, Element, Entity, Join, OP, EF, RE, CQU, PE, IFD, AT, NE, DE and SE. namespace_address
    gets Element, Entity and AT; role gets AUE, CQU, DE, SE and NE; receiver gets RE and Join; provider gets PE; purpose
    gets OP; ef gets EF; ifd gets IFD. No other field changes, and the element a subtype join holds shares the element's words."""
    import xml.etree.ElementTree as ET

    from metaform.modules.map import MODULE as MAP
    lines = glossary()
    assert lines['OP'] == "OP: Operative Purpose — the WHY; the RE's reason for the encounter."
    assert lines['CQU'] == ('CQU: Cestui Que Use — the explicit RE which benefits from and drives the improvements on '
                            'the artifact.\nRecorded under {CQU_BASE}.')
    assert set(term for terms in GLOSSED.values() for term in terms) == {
        'AUE', 'Element', 'Entity', 'Join', 'OP', 'EF', 'RE', 'CQU', 'PE', 'IFD', 'AT', 'NE', 'DE', 'SE'}
    written = ET.parse(Path(__file__).parents[1] / 'resources' / 'prompts.xml').getroot().find('fields')
    said = {f'{group.tag}/{field.tag}': (field.text or '').strip() for group in written for field in group}
    assert set(said) == set(GLOSSED) | set(UNGLOSSED)
    for where, terms in GLOSSED.items():
        assert said[where] == '\n'.join(lines[term] for term in terms), where
    for where, words in UNGLOSSED.items():
        assert said[where] == words, where
    for verb, group, field in (('element', 'element', 'namespace_address'), ('element', 'element', 'role'),
                               ('subtype', 'element', 'namespace_address'), ('subtype', 'element', 'role'),
                               ('add_requirement', 'join', 'receiver'), ('add_requirement', 'join', 'provider'),
                               ('add_requirement', 'join', 'purpose'), ('add_requirement', 'join', 'ef'),
                               ('add_requirement', 'join', 'ifd'), ('subtype', 'join', 'purpose'),
                               ('subtype', 'join', 'ef'), ('subtype', 'join', 'ifd'), ('edit', 'join', 'purpose'),
                               ('edit', 'join', 'ef'), ('edit', 'join', 'ifd')):
        assert nouns_of(verb)[field].help == said[f'{group}/{field}'], (verb, field)
    from metaform.modules.intake import MODULE
    helps = {f'intake {verb.name} {noun.name}': noun.help for verb in MODULE.verbs for noun in verb.nouns}
    helps.update({f'map {verb.name} {noun.name}': noun.help for verb in MAP.verbs for noun in verb.nouns
                  if noun.name in ('ef', 'purpose')})
    for where, words in {**said, **helps}.items():
        assert not any(phrase in words.lower() for phrase in BANNED), where


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-046')
def test_a_condition_given_with_an_element_a_join_or_a_subtype_join_is_an_open_work_record_at_it(run, project):
    """Rich, 2026-10-01: the agent said it found missing and broken things, and nothing like that showed in the GUI.
    The Canonical Intake's step 2 has the agent mark them; the intake tools take the mark and the finding."""
    run('intake', 'start', cwd=project)
    element = recorded(run, project, 'element', 'code.auth', 'role=SE', 'name=auth', 'condition=broken',
                       'note=Non-debug modes are forced to debug.')
    run('intake', 'element', 'code.timer', 'role=DE', cwd=project)
    join = recorded(run, project, 'add_requirement', 'code.timer', 'code.auth', 'purpose=p', 'ef=f', 'ifd=receives',
                    'verb=v', 'condition=missing', 'note=The demo does not declare its autoap dependency.')
    subtype = recorded(run, project, 'subtype', 'code.timer', 'code.auth', 'code.auth.tofu', 'purpose=q', 'ef=g',
                       'ifd=sends', 'verb=w', 'role=SE',
                       'name=TOFU', 'condition=exclude', 'note=Stale build context.')
    plain = recorded(run, project, 'element', 'code.clock', 'role=SE', 'name=clock')
    for made in (element, join, subtype, plain):
        assert made['notices'] == []
    recorded(run, project, 'finish')
    store = Store('timer')
    [held] = store.joins('code.timer').results
    [part] = store.subtypes(held.join_id).results
    work = {(row.kind, row.id): (row.condition, row.note, row.done) for row in store.work(open=True, limit=0).results}
    assert work == {
        ('element', store.element('code.auth').element_id): ('broken', 'Non-debug modes are forced to debug.', None),
        ('join', held.join_id): ('missing', 'The demo does not declare its autoap dependency.', None),
        ('join', part.join_id): ('exclude', 'Stale build context.', None)}
    assert Store('timer').element('code.auth').open_work == ('broken',)  # what the page draws the node from
    assert 'condition' not in (Store('timer').element('code.auth').extra or {})  # apart from the map, MAP-046
    assert Store('timer').element('code.clock').open_work == ()


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_every_join_and_subtype_join_is_asked_its_information_flow_direction(run, project):
    """IFD, Information Flow Direction, Rich 2026-10-01: the primary flow of information. sends: OP to EF. receives:
    EF to OP. both: equal need. It is a field of the join and the subtype join, defined once in
    prompts.xml, a closed choice of three, kept with the join, and named in a notice when it is missing."""
    for noun in (nouns_of('add_requirement')['ifd'], nouns_of('subtype')['ifd'], nouns_of('edit')['ifd']):
        assert noun.schema['enum'] == ['sends', 'receives', 'both']
        assert noun.help.startswith('IFD: Information Flow Direction — the primary flow of information')
    run('intake', 'start', cwd=project)
    run('intake', 'element', 'code.store.state', 'role=SE', cwd=project)
    read = recorded(run, project, 'add_requirement', 'code.selector.route', 'code.store.state', 'purpose=p', 'ef=f',
                    'ifd=receives', 'verb=v')
    write = recorded(run, project, 'add_requirement', 'code.protocol.sync', 'code.store.state', 'purpose=q', 'ef=g',
                     'verb=w')
    assert 'ifd' in [notice['where'] for notice in write['notices']]
    assert 'ifd' not in [notice['where'] for notice in read['notices']]
    store = Store('timer')
    [held] = store.joins('code.selector.route', raw=True).results
    assert (held.ifd, held.extra) == ('receives', None)
