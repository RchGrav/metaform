"""The intake module: the Canonical Intake served by name, one atomic submission never blocked, intake state, BASE-039."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from metaform import home as metaform_home
from metaform.data import Node, Store, export_document

pytestmark = pytest.mark.kind('fixture')

ROOT = Path(__file__).parents[5]
SPEC = Path(__file__).parents[1] / 'resources' / 'Intake_2.1.md'  # the served intake, Rich 2026-10-03
RESOURCE = Path(__file__).parents[1] / 'resources' / 'Intake_2.1.md'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'timer & co'
    folder.mkdir()
    run('add', 'project', 'timer', str(folder))
    return folder


OBJECT_KEYS = {'namespace_address', 'role', 'name', 'name_length', 'refs', 'joins'}
JOIN_KEYS = {'provider', 'purpose', 'ef', 'ifd', 'subtypes'}
# Each element of the fixture carries its name, which is stored on the element, Rich 2026-10-01, with no notice.
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
    document holds its provider and the element of each of its parts, Rich's shape, 2026-10-04. The notices come back
    keyed by each object's place in the document and the field they name."""
    notes, calls = [], []

    def call(path, *args):
        result = run('intake', *args, '--json', cwd=cwd)
        calls.append(result)
        out = json.loads(result.stdout)
        notes.extend({'where': f'{path}.{notice["where"]}', 'message': notice['message']}
                     for notice in out.get('notices', []))
        return out

    start = [arg for arg in extra if arg.split('=', 1)[0] in ('model', 'role')]
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
            call(f'elements[{index}].joins[{number}]', 'join', element['namespace_address'], json.dumps(held),
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
def test_only_intake_2_1_is_served():
    """Rich, 2026-10-03: "We arent even using 2.0 its superceded". The module serves resources/Intake_2.1.md, the one
    copy; Intake 2.0 and the Canonical Intake are not served."""
    assert not RESOURCE.with_name('Canonical_Intake.xml').exists() and not RESOURCE.with_name('Intake_2.0.md').exists()


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
@pytest.mark.req('MAP-043')
def test_prompt_serves_the_intake_with_only_its_prompt_filled(run, project):
    '''Rich, 2026-10-01: the intake's prompt slot holds what the person asked for, a target or a task; with nothing
    asked it stays empty, and the intake reads that as this project. Intake 2.1 carries it as
    `{Prompt} := """{prompt}"""`, and its TARGET_RESOLUTION takes the target from it, so nothing else is filled.'''
    stored = SPEC.read_text(encoding='utf-8')
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
    assert (report['project'], report['base'], report['elements'], report['joins'], report['work']) == (
        'timer', 'main', 4, 2, 0)
    assert set(notices(report)) == NAMED
    assert report['layer'] == 'base'  # LAYER-025: no time or random part
    store = Store('timer')
    assert store.has_intake()
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.short_name, kitchen.name_length, kitchen.role, kitchen.open_work) == ('kitchen timer', 2, 'DE', ())
    assert kitchen.name == 'kitchen timer daemon'  # its own field, Rich 2026-10-01
    # The element's refs are an item of the sources layer at it, Rich 2026-10-04, never a field of the element.
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
    assert sorted(op['data']['type'] for op in joins) == ['purpose', 'purpose']  # Rich 2026-10-04
    assert all(set(row) & {'perspective', 'verb', 'non_goal', 'name', 'provider'} == set() for row in (op['data'] for op in joins))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-044')
def test_a_name_is_recorded_wherever_a_namespace_address_and_a_name_length_are(run, project):
    """Rich, 2026-10-01: the name goes anywhere there is a namespace and name length; extra should be gone. The element
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
    join = json.loads(run('intake', 'join', 'code.timer.kitchen', '["code.alarm.audible", "code.loop.tick"]',
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
    """Rich, 2026-10-02: "drop perspective drop the duality , EF infers fine, my reasoning is that its less reasoning,
    its locks in which direction we care about more clearly, and make it easier nd lowers mistakes". No intake tool
    takes a perspective, and no field description names one."""
    import xml.etree.ElementTree as ET
    for verb in ('element', 'join'):
        assert 'perspective' not in nouns_of(verb), verb
    fields = ET.fromstring((RESOURCE.parent / 'prompts.xml').read_text(encoding='utf-8')).find('fields')
    assert fields is not None and fields.find('join/perspective') is None and fields.find('element/perspective') is None
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
    second = submit(run, project, changed, tmp_path)
    assert re.fullmatch(r'intake-\d{8}T\d{6}Z(-\d+)?', second['base'])
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
    made = json.loads(run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=exclude',
                          'note=alarm.c conflicts with specifications/alarm.md:12', 'task=review the code against the linked specification', '--json',
                          cwd=project).stdout)
    assert made['condition'] == 'exclude'
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
    exclude = json.loads(run('map', 'work', 'condition=exclude', '--json', cwd=project).stdout)['results']
    assert [(row['address'], row['condition'], row['note']) for row in exclude] == [
        ('code.alarm.audible', 'exclude', 'alarm.c conflicts with specifications/alarm.md:12')]
    assert json.loads(run('map', 'work', f'id={exclude[0]["id"]}', '--json', cwd=project).stdout)['task'] == (
        'review the code against the linked specification')  # a list row leaves its task out, MAP-049
    assert Store('timer').element('code.alarm.audible').open_work == ('exclude',)


@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
@pytest.mark.req('BASE-043')
def test_the_intake_tools_carry_no_flag_field_and_a_flag_sent_anyway_is_named_and_no_work_record(run, project,
                                                                                                   tmp_path):
    """The intake tools carry no flag field, and a flag sent anyway is never a work record. With no extra in Rich's
    shape the command line has nowhere to keep a word it does not know, so it refuses it, as the chassis grammar does
    for every verb with no extra, BASE-043, and writes nothing."""
    for verb in ('element', 'join'):
        assert not {'flag', 'flag_note'} & set(nouns_of(verb)), verb
    recorded(run, project, 'start')
    refused = run('intake', 'element', 'code.alarm.audible', 'role=SE', 'flag=broken', cwd=project, ok=False)
    assert refused.returncode == 2 and "does not take 'flag=broken'" in refused.stderr
    joined = run('intake', 'join', 'code.timer.kitchen', '["code.alarm.audible"]', 'purpose=p', 'colour=red',
                 cwd=project, ok=False)
    assert joined.returncode == 2 and "does not take 'colour=red'" in joined.stderr
    assert Store('timer').work(open=True, limit=0).results == ()
    shown = recorded(run, project, 'show')
    assert (shown['elements'], shown['joins']) == ([], [])


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
    """Rich, 2026-10-02: the no-intake notice is needed to onboard; and when an intake is started and aborted, the next
    agent is told that an intake was started but aborted and still remains to be completed. A finished intake clears
    both."""
    import xml.etree.ElementTree as ET
    prompts = ET.fromstring(RESOURCE.with_name('prompts.xml').read_text(encoding='utf-8'))
    notice, line = (prompts.findtext(name, '').strip() for name in ('no_intake', 'unfinished'))
    record = (ROOT / 'specifications' / '06-mcp-install.md').read_text(encoding='utf-8')
    assert line == 'An intake was started but aborted and still remains to be completed.' and line in record
    assert notice.startswith('This project has no intake.') and notice in record
    assert 'metaform://intake/procedure' in notice  # the procedure, named where an agent reads it, MCP-037
    agents = lambda: run('help', 'agents', cwd=project).stdout
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
def test_the_no_intake_notice_asks_once_starts_the_web_gui_and_runs_the_intake_while_the_person_watches(run, project):
    """MCP-009 and MCP-027, reworded with Rich 2026-10-07: on a first run the agent tells the person a basic analysis is
    about to run and asks once whether to start, starts the web GUI and gives its address, then has a subagent perform
    the intake from the procedure and forms resources while the person watches, then invites questions. What comes
    after intake is a separate notice. The notice leaves once an intake is finished."""
    import xml.etree.ElementTree as ET
    prompts = ET.fromstring(RESOURCE.with_name('prompts.xml').read_text(encoding='utf-8'))
    notice = prompts.findtext('no_intake', '').strip()
    ask, web = notice.index('Ready for me to start?'), notice.index('call web with command start')
    delegate, questions = notice.index('start a subagent'), notice.index('invite their questions')
    assert ask < web < delegate < questions
    assert 'metaform://intake/procedure' in notice and 'metaform://intake/schema' in notice
    assert 'blind spot' not in notice and 'best practices' not in notice
    assert notice in run('help', 'agents', cwd=project).stdout
    run('intake', 'start', cwd=project)
    run('intake', 'finish', cwd=project)
    assert 'Ready for me to start?' not in run('help', 'agents', cwd=project).stdout


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
    """Rich, 2026-09-26: the intake is recorded object by object as it is reasoned; agents read it back while it is
    built, and only a finished intake reaches every other read."""
    run('intake', 'start', 'model=claude', 'role=intake agent', cwd=project)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', 'name=Home cook', cwd=project)
    made = json.loads(run('intake', 'join', 'stakeholder.cook.home', '["code.timer.kitchen"]',
                          'purpose=Know when each dish is done.', 'ef=Counts down and rings.', 'ifd=receives',
                          '--json', cwd=project).stdout)
    assert [notice['where'] for notice in made['notices']] == ['elements']
    assert 'code.timer.kitchen was not an element' in made['notices'][0]['message']
    store = Store('timer')
    assert not store.has_intake() and store.element('stakeholder.cook.home') is None
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert (len(shown['elements']), len(shown['joins']), shown['joins'][0]['elements']) == (
        2, 1, ['code.timer.kitchen'])
    assert shown['undescribed'] == ['code.timer.kitchen']
    assert 'Intake: being recorded' in run(cwd=project).stdout
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name=kitchen timer', cwd=project)
    assert json.loads(run('intake', 'show', '--json', cwd=project).stdout)['undescribed'] == []
    finished = json.loads(run('intake', 'finish', '--json', cwd=project).stdout)
    assert (finished['elements'], finished['joins']) == (2, 1)
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
    run('intake', 'join', 'code.a', '["code.b"]', 'purpose=p', 'ef=f', 'ifd=receives', cwd=project)
    run('intake', 'join', 'code.b', '["code.a"]', 'purpose=q', 'ef=g', 'ifd=sends', cwd=project)
    run('intake', 'join', 'code.a', '["code.b"]', 'purpose=The better purpose.', cwd=project)
    run('intake', 'remove', 'receiver=code.b', 'provider=code.a', cwd=project)
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert [(row['receiver'], row['elements'], row['purpose'], row['ef']) for row in shown['joins']] == [
        ('code.a', ['code.b'], 'The better purpose.', 'f')]
    run('intake', 'finish', cwd=project)
    gone = json.loads(run('intake', 'remove', 'receiver=code.a', 'provider=code.b', '--json', cwd=project).stdout)
    assert 'map refine' in gone['notices'][0]['message'] and 'correction' not in gone['notices'][0]['message']
    assert [join.purpose for join in Store('timer').joins('code.a').results] == ['The better purpose.']
    # Recording after the finish starts a new intake in a new metaform; the finished one is left exactly as it was.
    later = json.loads(run('intake', 'join', 'code.a', '["code.b"]', 'purpose=Changed.', '--json', cwd=project).stdout)
    assert any(notice['where'] == 'base' for notice in later['notices'])
    run('intake', 'element', 'code.a', 'role=SE', 'name=renamed', cwd=project)
    finished = Store('timer')
    assert [(join.purpose, [held.address for held in join.elements]) for join in finished.joins('code.a').results] == [
        ('The better purpose.', ['code.b'])]
    kept = finished.element('code.a')
    assert kept is not None and (kept.role, kept.name) == ('DE', None)


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
    recorded(run, project, 'join', 'stakeholder.operator', '["code.failsafe.gateway"]',
             'purpose=Catch a dead gateway.', 'ef=Probes the gateway and fails over.', 'ifd=receives')
    recorded(run, project, 'join', 'stakeholder.operator', '["code.probe.echo"]',
             'purpose=Know the gateway answers.', 'ef=Sends an echo each second.', 'ifd=receives')
    recorded(run, project, 'join', 'code.alarm', '["code.probe.echo"]', 'purpose=Hear a lost echo.',
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
    """Rich, 2026-10-02: "you need to have the AI submit stuff how it is being reasoned and then extract the joins";
    Rich, 2026-10-04: "you can completely restore join to make a join". The intake tool names a join by its receiver
    and an element it holds, and an element by its address; no noun or result hands the agent an id."""
    from metaform.modules.intake import MODULE
    assert 'join' in [verb.name for verb in MODULE.verbs]
    for verb in MODULE.verbs:
        taken = {noun.name for noun in verb.nouns}
        assert not [name for name in taken if name in ID_KEYS | {'into', 'type'}], verb.name
    failsafe_intake(run, project)
    results = [
        recorded(run, project, 'element', 'code.siren', 'role=SE', 'name_length=1'),
        recorded(run, project, 'join', 'code.alarm', '["code.failsafe.gateway"]', 'purpose=Know of a failover.',
                 'ef=Reports each failover.', 'ifd=receives'),
        recorded(run, project, 'join', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.ping"]'),
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
    recorded(run, project, 'join', 'code.a', '["code.b"]', 'purpose=First why.', 'ef=f', 'ifd=receives')
    recorded(run, project, 'join', 'code.a', '["code.c"]', 'purpose=Second why.', 'ef=g', 'ifd=receives')
    both = recorded(run, project, 'join', 'code.a', '["code.b", "code.c"]', 'purpose=Changed.')
    message = ' '.join(notice['message'] for notice in both['notices'])
    assert 'First why.' in message and 'Second why.' in message
    shown = recorded(run, project, 'show')
    assert sorted((row['purpose'], tuple(row['elements'])) for row in shown['joins']) == [
        ('First why.', ('code.b',)), ('Second why.', ('code.c',))]


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-040')
def test_annealing_adds_an_element_to_its_parents_join_and_the_element_stays_one_record(run, project):
    """Rich, 2026-09-27: an element always appears as one element record; annealing places it in its parent's join,
    and the element itself does not move. In Rich's shape, 2026-10-04, the join holds it as one more element."""
    failsafe_intake(run, project)
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.probe.echo')
    annealed = recorded(run, project, 'join', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.echo"]')
    assert annealed['notices'] == []
    shown = recorded(run, project, 'show')
    assert sorted((row['receiver'], tuple(row['elements'])) for row in shown['joins']) == [
        ('code.alarm', ('code.probe.echo',)), ('stakeholder.operator', ('code.failsafe.gateway', 'code.probe.echo'))]
    [operator] = [row for row in shown['joins'] if row['receiver'] == 'stakeholder.operator']
    assert (operator['purpose'], operator['ef']) == ('Catch a dead gateway.', 'Probes the gateway and fails over.')
    [element] = [row for row in shown['elements'] if row['namespace_address'] == 'code.probe.echo']
    assert element['role'] == 'SE'
    finished = recorded(run, project, 'finish')
    assert (finished['elements'], finished['joins']) == (4, 2)
    store = Store('timer')
    [parent] = store.joins('stakeholder.operator').results
    assert [held.address for held in parent.elements] == ['code.failsafe.gateway', 'code.probe.echo']
    assert store.element('code.probe.echo').id == parent.elements[1].element_id


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
def test_show_reads_one_receivers_joins_and_what_they_hold(run, project):
    """Rich, 2026-09-27: the intake must not depend on the size of the agent's context."""
    failsafe_intake(run, project)
    recorded(run, project, 'remove', 'receiver=stakeholder.operator', 'provider=code.probe.echo')
    recorded(run, project, 'join', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.echo"]')
    operator = recorded(run, project, 'show', 'receiver=stakeholder.operator')
    assert [row['elements'] for row in operator['joins']] == [['code.failsafe.gateway', 'code.probe.echo']]
    assert {row['namespace_address'] for row in operator['elements']} == {
        'stakeholder.operator', 'code.failsafe.gateway', 'code.probe.echo'}
    alarm = recorded(run, project, 'show', 'receiver=code.alarm')
    assert [row['elements'] for row in alarm['joins']] == [['code.probe.echo']]


@pytest.mark.req('BASE-039')
def test_recording_and_remove_name_an_element_and_a_join_by_their_addresses(run, project):
    """A Fable intake on 2026-09-27 crashed its own script expecting join_id where intake_show said id; there are no
    ids to expect: each thing is named by the addresses the agent reasoned."""
    failsafe_intake(run, project)
    recorded(run, project, 'join', 'stakeholder.operator', '["code.failsafe.gateway", "code.probe.ping"]')
    held = next(row for row in recorded(run, project, 'show')['joins']
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
    assert sorted((row['receiver'], tuple(row['elements'])) for row in again['joins']) == [
        ('code.alarm', ('code.probe.echo',)), ('stakeholder.operator', ('code.failsafe.gateway',))]
    assert 'namespace_address' in nouns_of('element') and 'address' not in nouns_of('element')
    assert {'receiver', 'elements'} <= set(nouns_of('join'))
    assert {'receiver', 'provider', 'namespace_address'} <= set(nouns_of('remove'))


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
          'join': ('receiver', 'elements', 'purpose', 'ef', 'ifd')}


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-031')
def test_each_recorded_field_is_described_once_from_the_intake_modules_prompts_file():
    """Rich, 2026-10-01: the field definitions are not parsed out of the Canonical Intake, which is being refined and
    no longer carries the response schema. Each one is written once, in the intake module's prompts.xml under
    <fields>, and every tool that takes the field shows those words."""
    import xml.etree.ElementTree as ET
    written = ET.parse(Path(__file__).parents[1] / 'resources' / 'prompts.xml').getroot().find('fields')
    assert written is not None
    assert [group.tag for group in written] == ['element', 'join']
    for verb, group in (('element', 'element'), ('join', 'join')):
        nouns = nouns_of(verb)
        for field in FIELDS[group]:
            said = written.findtext(f'{group}/{field}')
            assert said and said.strip() == nouns[field].help, (verb, field)
    assert nouns_of('remove')['provider'].help == written.findtext('join/provider').strip()
    source = (Path(__file__).parents[1] / '__init__.py').read_text(encoding='utf-8')
    assert 'schema//elements' not in source and 'SET perspective' not in source  # the Canonical Intake is not parsed for them


@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
def test_no_intake_or_map_tool_takes_relation_or_observation():
    """Rich, 2026-10-02: "observation was not my design. I didn't ask for observation"; "Neither was relation". The
    intake tools and the map knowledge tool stop taking both."""
    from metaform.modules.intake import MODULE
    from metaform.modules.map import MODULE as MAP
    taken = {(module.id, verb.name, noun.name) for module in (MODULE, MAP) for verb in module.verbs
             for noun in verb.nouns if noun.name in ('relation', 'observation')}
    assert taken == set()


RECORDING = ('element', 'join', 'show', 'remove')


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


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-046')
def test_a_condition_given_with_an_element_or_a_join_is_an_open_work_record_at_it(run, project):
    """Rich, 2026-10-01: the agent said it found missing and broken things, and nothing like that showed in the GUI.
    The Canonical Intake's step 2 has the agent mark them; the intake tools take the mark and the finding."""
    run('intake', 'start', cwd=project)
    element = recorded(run, project, 'element', 'code.auth', 'role=SE', 'name=auth', 'condition=broken',
                       'note=Non-debug modes are forced to debug.')
    run('intake', 'element', 'code.timer', 'role=DE', 'name=timer', cwd=project)
    join = recorded(run, project, 'join', 'code.timer', '["code.auth"]', 'purpose=p', 'ef=f', 'ifd=receives',
                    'condition=missing', 'note=The demo does not declare its autoap dependency.')
    plain = recorded(run, project, 'element', 'code.clock', 'role=SE', 'name=clock')
    for made in (element, join, plain):
        assert made['notices'] == []
    recorded(run, project, 'finish')
    store = Store('timer')
    [held] = store.joins('code.timer').results
    work = {(row.node_kind, row.node_id): (row.condition, row.note, row.done) for row in store.work(open=True, limit=0).results}
    assert work == {
        ('element', store.element('code.auth').id): ('broken', 'Non-debug modes are forced to debug.', None),
        ('join', held.id): ('missing', 'The demo does not declare its autoap dependency.', None)}
    assert Store('timer').element('code.auth').open_work == ('broken',)  # what the page draws the node from
    assert 'condition' not in Store('timer').element('code.auth').to_dict()  # apart from the map, MAP-046
    assert Store('timer').element('code.clock').open_work == ()


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_every_join_is_asked_its_information_flow_direction(run, project):
    """IFD, Information Flow Direction, Rich 2026-10-01: the primary flow of information. sends: OP to EF. receives:
    EF to OP. both: equal need. It is a field of the join, defined once in prompts.xml, a closed choice of three, kept
    with the join, and named in a notice when it is missing."""
    noun = nouns_of('join')['ifd']
    assert noun.schema['enum'] == ['sends', 'receives', 'both']
    assert noun.help.startswith('IFD: Information Flow Direction — the primary flow of information')
    run('intake', 'start', cwd=project)
    run('intake', 'element', 'code.store.state', 'role=SE', cwd=project)
    read = recorded(run, project, 'join', 'code.selector.route', '["code.store.state"]', 'purpose=p', 'ef=f',
                    'ifd=receives')
    write = recorded(run, project, 'join', 'code.protocol.sync', '["code.store.state"]', 'purpose=q', 'ef=g')
    assert 'ifd' in [notice['where'] for notice in write['notices']]
    assert 'ifd' not in [notice['where'] for notice in read['notices']]
    store = Store('timer')
    [held] = store.joins('code.selector.route', raw=True).results
    assert held.ifd == 'receives'


@pytest.mark.req('STORE-012')
def test_refs_go_to_the_sources_layer_only_while_intake_sources_is_on(run, project):
    """Rich, 2026-10-04: "then if you want to have refs you add a sources layer, or you keep them in a sources layer..
    this makes the metaform itself the map I intended it to be." The refs given with an element are one item of the
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
