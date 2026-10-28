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
SPEC = Path(__file__).parents[1] / 'resources' / 'intake.xml'  # the served intake
RESOURCE = SPEC


def stored_procedure() -> str:
    """The authored task body with only its declared project binding applied."""
    return SPEC.read_text(encoding='utf-8').replace('{project}', 'timer')


def served_asked(asked: str) -> str:
    """The unchanged task body followed by separate request text when supplied."""
    return stored_procedure() + (f'\n\n## Intake request\n\n{asked}\n' if asked else '')


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


OBJECT_KEYS = {'namespace_address', 'role', 'name', 'name_length', 'block', 'within', 'refs', 'joins'}
JOIN_KEYS = {'provider', 'purpose', 'ef', 'ifd', 'subtypes'}
# Each element of the fixture carries its name, which is stored on the element, with no notice.
NAMED: set[str] = set()
SUBTYPE_KEYS = {'element'}


def fields(given, names):
    """A record's fields as named arguments, a list or object as JSON. A field no tool names is sent as it is, so
    the chassis names it, BASE-043."""
    unknown = set(given) - (OBJECT_KEYS | JOIN_KEYS | SUBTYPE_KEYS)
    return [f'{name}={json.dumps(value) if isinstance(value, (list, dict)) or name in ("block", "within") else value}'
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
             *fields(element, {'role', 'name', 'name_length', 'block', 'within', 'refs'}))
        for number, join in enumerate(element.get('joins', [])):
            for place, subtype in enumerate(join.get('subtypes', [])):
                inner = subtype.get('element', {})
                call(f'elements[{index}].joins[{number}].subtypes[{place}].element', 'element',
                     inner.get('namespace_address', ''),
                     *fields(inner, {'role', 'name', 'name_length', 'block', 'within', 'refs'}))
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


@pytest.mark.req('BASE-039')
def test_the_intake_task_has_one_source_and_a_separate_xml_data_schema(run, project):
    """Instruction text is opaque. The separate structured-data schema remains XML."""
    import xml.etree.ElementTree as ET

    from metaform.modules.intake import RESOURCE as served
    from metaform.modules.intake import SHAPE

    assert served == RESOURCE and SHAPE == RESOURCE.with_name('metaform.xml')
    ET.parse(SHAPE)
    assert run('intake', 'schema', cwd=project).stdout == SHAPE.read_text(encoding='utf-8')
    assert run('intake', 'prompt', cwd=project).stdout == stored_procedure()
    assert all(not RESOURCE.with_name(name).exists()
               for name in ('intake.axiom', 'metaform.axiom', 'Canonical_Intake.xml', 'Intake_2.0.md',
                            'Intake_2.1.md', 'digital-typology.axiom'))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
@pytest.mark.req('MAP-043')
def test_prompt_serves_the_unchanged_task_body_and_a_separate_request(run, project):
    """A request is appended without filling slots or changing the instruction body."""
    out = run('intake', 'prompt', cwd=project).stdout
    assert out == served_asked('')
    asked = run('intake', 'prompt', 'text=Map the timer and its alarm', cwd=project).stdout
    assert asked == served_asked('Map the timer and its alarm')


@pytest.mark.req('BASE-039')
def test_request_text_is_appended_literally_without_xml_escaping_or_slot_replacement(run, project):
    asked = 'fix A & B in <main> "now"\n{prompt}\n'
    assert run('intake', 'prompt', f'text={asked}', cwd=project).stdout == served_asked(asked)


@pytest.mark.req('BASE-039')
@pytest.mark.parametrize(('name', 'stored'), [
    ('own-intake.md', '# My intake\nInspect the supplied files.\n{prompt}\n'),
    ('own-intake.xml', '<anything target="{prompt}"\nA & B <not-closed>\n'),
    ('own-intake.txt', 'No headings or tags. Keep {project_id} and bind {project}.\n\n'),
])
def test_arbitrary_utf8_intake_files_are_opaque_and_requests_follow_them(run, project, tmp_path, name, stored):
    asked = 'fix A & B in <main> "now"\n{prompt}\n'
    own = tmp_path / name
    own.write_text(stored, encoding='utf-8')
    run('set', f'--intake-file={own}', cwd=project, env={'METAFORM_WORK': 'opaque-task'})
    effective = stored.replace('{project}', 'timer')
    expected = effective + f'\n\n## Intake request\n\n{asked}\n'
    assert run('intake', 'prompt', f'text={asked}', cwd=project).stdout == expected
    assert run('intake', 'prompt', cwd=project).stdout == effective
    assert own.read_text(encoding='utf-8') == stored


@pytest.mark.req('CLI-034')
@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_debug_does_not_modify_the_intake_task_instructions(run, project):
    plain = run('intake', 'prompt', cwd=project).stdout
    run('set', '--debug', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    run('set', '--no-debug', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == plain
    assert plain == stored_procedure()


@pytest.mark.req('CLI-034')
def test_debug_is_a_chassis_boolean_that_follows_every_settings_rule_and_report_is_gone(run, project):
    shown = {row['key']: row for row in json.loads(run('config', '--show', '--json', cwd=project).stdout)}
    assert (shown['debug']['value'], shown['debug']['owner']) == (False, 'chassis')
    assert 'report' not in shown  # nothing read it since 2026-09-29; removed in the settings cleanup, 2026-10-15
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
    assert provenance.prompt is None  # map provenance does not copy the task body
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
    hands its refs on as given, and each is linked at the element as a record of the sources layer. A ref given as an
    object of one entry is that key and value, linked as text and never refused, STORE-026."""
    recorded(run, project, 'start')
    made = recorded(run, project, 'element', 'code.probe.echo', 'role=SE', 'name_length=1', 'name=echo probe',
                    'refs=[["path", "src/echo.c"], {"path": "src/pins.h"}]')
    messages = [(notice['where'], notice['message']) for notice in made['notices']]
    assert messages == [('refs', 'A ref is a key and a value, both text; one was not, and linked as text.')]
    held = Store('timer').refs(Node('element', 'code.probe.echo'))
    assert [(ref.key, ref.value, ref.details) for ref in held] == [('path', 'src/echo.c', ()), ('path', 'src/pins.h', ())]


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_refs_that_are_not_text_are_linked_as_text_and_counted_in_words(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    given['elements'][1]['refs'] = [['path', 'src/timer.c'], ['line', 12], ['col', 3]]
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert found['elements[1].refs'] == 'A ref is a key and a value, both text; two were not, and linked as text.'
    [kept] = Store('timer').refs(Node('element', given['elements'][1]['namespace_address']))
    assert (kept.key, kept.value) == ('path', 'src/timer.c')  # the pairs after a path are its details
    assert [(ref.key, ref.value) for ref in kept.details] == [('line', '12'), ('col', '3')]


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


@pytest.mark.req('LAYER-025')
def test_an_agents_intake_update_refines_the_map_in_use(run, project, tmp_path):
    """Refinement first (2026-10-17): on a project with a map, intake start with no name is a verification pass on
    the map in use, which grows it under the same rules as map refine, each version carrying its reason and author."""
    submit(run, project, FIXTURE, tmp_path)
    agent = {'METAFORM_WORK': 'w9'}
    run('intake', 'start', cwd=project, env=agent)
    run('intake', 'element', 'code.alarm.snooze', 'role=SE', 'name=snooze', 'name_length=2', cwd=project, env=agent)
    snooze = Store('timer').element('code.alarm.snooze')
    [added] = Store('timer').history(snooze.id).results
    assert (snooze.layer, added.reason, added.by) == ('base', 'intake verification pass', 'work w9')
    assert [base.name for base in metaform_home.bases('timer')] == ['main']


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-045')
@pytest.mark.req('STORE-041')
def test_a_second_intake_is_stored_as_a_new_metaform_beside_the_active_one_and_the_first_is_kept(
        run, project, tmp_path, home):
    """UX review round 1, 2026-10-17 (fresh-start-intake F7): finishing a separate intake no longer makes its base the
    active map for everyone by itself. It is finished beside it, and the person makes it active."""
    first = submit(run, project, FIXTURE, tmp_path)
    main = metaform_home.active_base('timer')
    before = metaform_home.store_path('timer', main.id).read_bytes()
    changed = copy.deepcopy(FIXTURE)
    changed['elements'][2]['namespace_address'] = 'code.alarm.visual'
    changed['elements'][1]['joins'][0]['provider'] = 'code.alarm.visual'
    second = submit(run, project, changed, tmp_path, extra=('name=alarm-visual',))  # a separate intake is named
    assert second['base'] == 'alarm-visual'
    assert metaform_home.active_base('timer').id == main.id, 'the active map stays the person\'s'
    assert any('metaform map activate alarm-visual --confirm' in notice['message'] for notice in second['notices'])
    assert Store('timer').element('code.alarm.audible') is not None
    assert metaform_home.store_path('timer', main.id).read_bytes() == before
    run('activate', 'base', 'alarm-visual', cwd=project)
    store = Store('timer')
    assert store.element('code.alarm.visual') is not None and store.element('code.alarm.audible') is None
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
def test_a_project_mapped_in_another_base_is_never_told_first_run(run, project, tmp_path):
    """UX review round 1, 2026-10-17 (fresh-start-intake F6, orchestrator F2): with a new, empty base active and the
    finished intake in main, no agent is told FIRST RUN, and intake status names the base that holds it."""
    notice = onboarding()
    submit(run, project, FIXTURE, tmp_path)
    run('map', 'add-base', 'fresh', '--confirm', cwd=project)
    assert metaform_home.active_base('timer').name == 'fresh'
    assert notice not in run('help', 'agents', cwd=project).stdout
    said = run('intake', 'status', cwd=project).stdout
    assert 'none in the active map fresh' in said and 'finished intake in main' in said, said
    assert 'metaform map activate main --confirm' in said and 'No intake yet' not in said
    assert 'Intake: none in the active map fresh' in run(cwd=project).stdout


@pytest.mark.req('MCP-009')
@pytest.mark.req('STORE-041')
def test_an_empty_active_base_points_to_the_map_last_made_active_never_a_trial_beside_it(run, project, tmp_path):
    """UX review round 2, 2026-10-17 (project-scope F3 and F4): with main the person's map and a trial intake v2
    finished beside it and never made active, intake status sent the person to v2, and an agent's empty map reads in
    a new empty base said nothing of the map at all. Both name main, the map the person last made active, and the
    base list says which bases hold a map."""
    submit(run, project, FIXTURE, tmp_path)
    changed = copy.deepcopy(FIXTURE)
    changed['elements'][2]['namespace_address'] = 'code.alarm.visual'
    changed['elements'][1]['joins'][0]['provider'] = 'code.alarm.visual'
    submit(run, project, changed, tmp_path, extra=('name=v2',))  # finished beside main, never made active
    run('map', 'add-base', 'fresh', '--confirm', cwd=project)
    said = run('intake', 'status', cwd=project).stdout
    assert said.rstrip().endswith('metaform map activate main --confirm'), said
    roots = json.loads(run('map', 'roots', '--json', cwd=project).stdout)
    told = ("The active map, fresh, is empty; this project's map is kept in main (v2 holds a map too). Making it "
            "active again is the person's choice: metaform map activate main --confirm")
    assert [notice['message'] for notice in roots['notices']] == [told], roots
    missing = run('map', 'where', 'code.alarm.audible', cwd=project, ok=False)
    assert 'kept in main' in missing.stdout + missing.stderr
    listed = json.loads(run('map', 'bases', '--json', cwd=project).stdout)['results']
    assert {one['name']: one['mapped'] for one in listed} == {'main': True, 'v2': True, 'fresh': False}
    run('activate', 'base', 'main', cwd=project)
    assert json.loads(run('map', 'roots', '--json', cwd=project).stdout).get('notices') in (None, []), \
        'a mapped base pays nothing and says nothing'


@pytest.mark.req('MCP-009')
@pytest.mark.req('MCP-031')
def test_an_intake_started_and_not_finished_is_named_in_the_instructions(run, project):
    """The no-intake notice is needed to onboard; when an intake is started and aborted, the next agent is told that an
    intake was started but aborted and still remains to be completed. A finished intake clears both."""
    from metaform import prompt_files

    notice = onboarding()
    line = prompt_files.required(SPEC.parent.parent, 'unfinished')
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
    # no pass open: the record is still written onto the finished map, in a pass it opens, never a new intake
    # (refinement first, 2026-10-17)
    run('intake', 'element', 'code.display.dot', 'role=SE', 'name=dot', cwd=project)
    assert line not in agents() and [base.name for base in metaform_home.bases('timer')] == ['main']


@pytest.mark.req('MCP-009')
def test_a_dispatched_agent_is_never_given_the_first_run_onboarding(run, project, monkeypatch):
    """An agent a dispatch runner started has its work as its first turn: the onboarding, which asks an agent to
    handle the intake first, is not in what it reads, BASE-052."""
    monkeypatch.setenv('METAFORM_SESSION', 'r1')
    assert onboarding() not in run('help', 'agents', cwd=project).stdout


@pytest.mark.req('MCP-009')
@pytest.mark.req('MCP-027')
def test_the_authored_onboarding_notice_is_delivered_until_intake_is_completed(run, project):
    """The current authored notice is delivered before intake and leaves after completion."""
    notice = onboarding()
    assert notice in run('help', 'agents', cwd=project).stdout
    run('intake', 'start', cwd=project)
    run('intake', 'finish', cwd=project)
    assert notice not in run('help', 'agents', cwd=project).stdout


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
    original = '<process><target type="x" value="y"/>{project_id}</process>\n'
    other.write_text(original, encoding='utf-8')
    run('set', '--intake-file', str(other), cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == original
    replacement = 'Use this revised method. No tags, headings or prescribed phases.\n\n'
    other.write_text(replacement, encoding='utf-8')
    assert run('intake', 'prompt', cwd=project).stdout == replacement


@pytest.mark.req('STORE-044')
@pytest.mark.req('BASE-039')
def test_the_intake_uses_its_selected_edit_before_and_after_recording(run, home, project, tmp_path):
    from metaform import prompt_files
    from metaform.module import context
    from metaform.modules import tasks

    first = run('intake', 'prompt', cwd=project).stdout
    assert first == stored_procedure()
    ctx = context('tasks', project, nouns={'name': 'intake'})
    definition = tasks.definition(ctx)
    edited = 'Use the supplied method exactly. <unclosed> & {prompt}\n\n'
    selected, notices = prompt_files.save_edit(definition['component']['name'], edited)
    assert not notices and selected.text == edited
    assert run('intake', 'prompt', cwd=project).stdout == edited
    assert tasks.definition(ctx)['instructions'] == edited
    submit(run, project, FIXTURE, tmp_path)
    assert run('intake', 'prompt', cwd=project).stdout == edited
    assert tasks.definition(ctx)['component']['actual_version_id'] == selected.version_id


@pytest.mark.req('STORE-044')
def test_recording_an_intake_keeps_its_configured_instruction_text_unchanged(run, home, project, tmp_path):
    own = tmp_path / 'own-intake.xml'
    authored = '<process><target/> & literal {prompt}\n'
    own.write_text(authored, encoding='utf-8')
    run('set', f'--intake-file={own}', cwd=project)
    assert run('intake', 'prompt', cwd=project).stdout == authored
    submit(run, project, FIXTURE, tmp_path)
    assert run('intake', 'prompt', cwd=project).stdout == authored
    assert own.read_text(encoding='utf-8') == authored


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
    assert 'Intake: left unfinished' in run(cwd=project).stdout  # no agent's process records it, only commands
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
    async def record():
        for tool, arguments in (
                ('intake_start', {}),
                ('intake_element', {'namespace_address': 'code.alarm.audible', 'role': 'SE'}),
                ('intake_finish', {'report': str(secret)})):
            await server.read_resource_text(project, server.instruction_uri(tool), session='report-writer')
            error, blocks = await server.run_tool(project, tool, arguments, session='report-writer')
            assert not error, blocks
    anyio.run(record)
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


FIELDS = {'element': ('namespace_address', 'role', 'name_length', 'name', 'block', 'within', 'refs'),
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
    for field in ('block', 'within'):
        noun = nouns_of('element')[field]
        assert noun.kind == 'json' and noun.schema == {'type': ['string', 'null']}
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
@pytest.mark.parametrize('verb', ['element', 'purpose'])
@pytest.mark.parametrize('finished', [False, True])
def test_retired_annotation_arguments_create_no_critic_layer_or_tickets(run, project, verb, finished):
    """A stale importer must not turn supplied functional data into critique or repair work."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'downstream.cqu.cook', 'role=CQU')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE')
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE')
    recorded(run, project, 'purpose', 'downstream.cqu.cook', '["code.timer.kitchen"]',
             'purpose=Know when food is done', 'ef=Counts down', 'ifd=receives')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]',
             'purpose=Get attention', 'ef=Sounds an alarm', 'ifd=sends')
    if finished:
        recorded(run, project, 'finish')

    target = ('element', 'code.alarm.audible') if verb == 'element' else (
        'purpose', 'code.timer.kitchen', '["code.alarm.audible"]')
    supplied = json.dumps({'function': 'Sounds an alarm', 'relation': 'signals completion',
                           'verb': 'signals', 'observation': 'The alarm serves the countdown.'})
    rejected = run('intake', *target, f'note={supplied}', 'condition=BKN',
                   'same_as=code.timer.kitchen', '--json', cwd=project, ok=False)
    assert rejected.returncode != 0 and 'does not take' in rejected.stderr
    recorded(run, project, *target, 'refs=[{"key": "path", "value": "alarm.c"}]')
    shown = recorded(run, project, 'show')
    assert len(shown['elements']) == 3 and len(shown['purposes']) == 2
    assert shown['disconnected'] == []
    assert all(not {'note', 'condition', 'kept_in'} & row.keys()
               for row in [*shown['elements'], *shown['purposes']])
    store = Store('timer')
    assert {layer.name for layer in store.layers(limit=0).results} == {'base', 'sources'}
    assert store.work(open=True, limit=0).results == ()
    if verb == 'element':
        [found] = [row for row in shown['elements'] if row['namespace_address'] == 'code.alarm.audible']
    else:
        [found] = [row for row in shown['purposes'] if row['receiver'] == 'code.timer.kitchen']
    assert found['refs'] == [{'key': 'path', 'value': 'alarm.c'}]


@pytest.mark.req('BASE-039')
def test_intake_read_back_does_not_present_other_layer_content_as_notes(run, project):
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE')
    store = Store('timer')
    layer = store.layer('critic', 'map', 'An explicitly created external review.',
                        mutable=True, hideable=True, ready=True)
    element = store.element('code.timer.kitchen', raw=True)
    item = store.add_item(layer.name, Node('element', element.id), 'External review content')
    shown = recorded(run, project, 'show')
    assert 'note' not in shown['elements'][0]
    assert store.layer_items(layer.name, limit=0).results[0].id == item.id


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
def test_the_ignore_list_follows_the_intake_without_annotation_side_effects(run, project):
    """Exclude was meant as a metaform ignore, like gitignore, not a judgment the intake makes on what
    it sees; agents acted on exclude marks and deleted files. The person lists what is not the project in
    .metaform/ignore.txt, the intake is served with that list after it and reads nothing it names."""
    plain = stored_procedure()
    assert run('intake', 'prompt', cwd=project).stdout == plain  # no file: the intake alone
    (project / '.metaform').mkdir()
    (project / '.metaform' / 'ignore.txt').write_text('# not the project\nrich/\n\n*.zip\n', encoding='utf-8')
    assert metaform_home.ignore_patterns(project) == ['rich/', '*.zip']
    served = run('intake', 'prompt', cwd=project).stdout
    assert served.startswith(plain)
    assert served.endswith('(.metaform/ignore.txt):\nrich/\n*.zip\n')
    assert '# not the project' not in served[len(plain):]
    recorded(run, project, 'start')
    rejected = run('intake', 'element', 'code.alarm.audible', 'role=SE', 'condition=exclude', 'note=stray',
                   cwd=project, ok=False)
    assert rejected.returncode != 0 and 'does not take' in rejected.stderr
    assert Store('timer').element('code.alarm.audible', raw=True) is None
    assert Store('timer').work(open=True, limit=0).results == ()
    assert 'critic' not in {layer.name for layer in Store('timer').layers(limit=0).results}


@pytest.mark.req('MAP-040')
def test_the_field_text_lists_exactly_the_values_the_intake_tools_accept():
    """The description beside each argument is what an agent reads as it records, so a value listed there and refused
    by the tool, or accepted and never listed, misleads it: the old text offered condition missing after it was
    ruled out."""
    from metaform.modules.intake import ELEMENT_WORDS, MODULE, PURPOSE_WORDS

    def listed(words: str) -> set[str]:
        head = re.split(r'[.:]', words, maxsplit=1)[0]
        return {part.strip() for part in re.split(r',| or ', head) if part.strip() and ' ' not in part.strip()}

    nouns = {(verb.name, noun.name): noun for verb in MODULE.verbs for noun in verb.nouns}
    for verb, words in (('element', ELEMENT_WORDS), ('purpose', PURPOSE_WORDS)):
        for field in ('role', 'ifd'):
            noun = nouns.get((verb, field))
            if noun is not None:
                assert listed(words[field]) == set(noun.schema['enum']), (verb, field, words[field])
    assert not any(field in ('condition', 'note', 'same_as') for _, field in nouns)


@pytest.mark.req('BASE-039')
@pytest.mark.parametrize('finished', [False, True])
def test_element_metadata_is_native_preserved_when_omitted_and_cleared_by_null(run, project, finished):
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE', 'name=kitchen timer')
    recorded(run, project, 'element', 'code.control.timer', 'role=SE', 'name=timer control')
    store = Store('timer')
    original_layers = {layer.name for layer in store.layers(limit=0).results} | {'sources'}
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'name=alarm',
             'block="BLOCK_001"', 'within="code.timer.kitchen"',
             'refs=[{"key": "path", "value": "src/alarm.c"}]')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.control.timer", "code.alarm.audible"]',
             'purpose=Announce the elapsed time.', 'ef=Controls and sounds the alarm.', 'ifd=receives')
    if finished:
        recorded(run, project, 'finish')
        recorded(run, project, 'start')
    original_base = store.active_base().id
    assert {layer.name for layer in store.layers(limit=0).results} == original_layers
    element_id = store.element('code.alarm.audible', raw=True).id

    def metadata(block, within):
        native = store.element('code.alarm.audible', raw=True)
        assert (native.id, native.block, native.within) == (element_id, block, within)
        shown = recorded(run, project, 'show')
        alarm = next(row for row in shown['elements'] if row['namespace_address'] == 'code.alarm.audible')
        for field, expected in (('block', block), ('within', within)):
            if expected is None:
                assert field not in alarm
            else:
                assert alarm[field] == expected
        assert alarm['refs'] == [{'key': 'path', 'value': 'src/alarm.c'}]

    metadata('BLOCK_001', 'code.timer.kitchen')
    recorded(run, project, 'element', 'code.alarm.audible', 'name=alarm bell')
    metadata('BLOCK_001', 'code.timer.kitchen')
    recorded(run, project, 'element', 'code.alarm.audible', 'block="BLOCK_002"')
    metadata('BLOCK_002', 'code.timer.kitchen')
    recorded(run, project, 'element', 'code.alarm.audible', 'within="code.control.timer"')
    metadata('BLOCK_002', 'code.control.timer')
    recorded(run, project, 'element', 'code.alarm.audible', 'block=null')
    metadata(None, 'code.control.timer')
    recorded(run, project, 'element', 'code.alarm.audible', 'within=null')
    metadata(None, None)
    finished_result = recorded(run, project, 'finish')
    assert finished_result['work'] == 0
    metadata(None, None)
    assert store.active_base().id == original_base
    assert {layer.name for layer in store.layers(limit=0).results} == original_layers
    assert not {'critic', 'checked'} & original_layers
    assert store.work(open=True, limit=0).results == ()
    [source] = store.layer_items('sources', Node('element', element_id), limit=0).results
    assert [(ref.key, ref.value) for ref in source.refs] == [('path', 'src/alarm.c')]


@pytest.mark.req('BASE-039')
def test_a_verify_pass_updates_refs_without_adding_annotations_or_a_new_base(run, project):
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE', 'name=timer')
    recorded(run, project, 'element', 'code.alarm.audible', 'role=SE', 'name=alarm')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]',
             'purpose=p', 'ef=f', 'ifd=receives')
    recorded(run, project, 'finish', 'report=done')
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'refs=[{"key": "read", "value": "t.c#L1"}]')
    recorded(run, project, 'purpose', 'code.timer.kitchen', '["code.alarm.audible"]',
             'refs=[{"key": "path", "value": "alarm.c"}]')
    shown = recorded(run, project, 'show')
    by = {entry['namespace_address']: entry for entry in shown['elements']}
    assert by['code.timer.kitchen']['refs'] == [{'key': 'read', 'value': 't.c#L1'}]
    assert shown['purposes'][0]['refs'] == [{'key': 'path', 'value': 'alarm.c'}]
    assert all('condition' not in row and 'note' not in row for row in [*shown['elements'], *shown['purposes']])
    assert Store('timer').work(open=True, limit=0).results == ()
    assert not {'critic', 'checked'} & {layer.name for layer in Store('timer').layers(limit=0).results}
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
    assert 'follow_on' not in finished  # a pass that only refines adds no code, so intake.finished is not sent
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
    assert 'follow_on' not in finished  # no shipped module subscribes to intake.finished
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
def test_processes_recording_new_shape_on_a_finished_map_at_once_write_onto_it_in_one_pass(run, home, project):
    """Intake element calls at once, each with a new element for a finished map, write onto that map in one
    verification pass that keeps every element added; none opens a new base (refinement first, 2026-10-17). Four
    calls, as the verifier ran: with two the window is often missed."""
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
    assert bases == ['main'] and Store('timer').intake_building().results == ()
    passing = json.loads((metaform_home.project_folder('timer') / 'intake.verifying').read_text(encoding='utf-8'))
    held = Store('timer')
    for address in addresses:
        element = held.element(address, raw=True)
        assert element is not None and element.layer == 'base' and element.id in passing['added'], address


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


@pytest.mark.req('BASE-039')
def test_an_intake_is_recorded_only_while_its_agents_process_lives_and_is_left_unfinished_after(run, home, project):
    """Recording means an agent records the intake now: commands alone leave it unfinished, an agent's own process
    holds it while it lives, and once that process ends it is left unfinished, which the person may discard."""
    import subprocess
    import sys
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE')
    [left] = Store('timer').intake_building().results
    assert (left.recording, left.parts, Store('timer').intake_recording().results) == (False, 1, ())
    assert left.last is not None
    assert 'Intake: left unfinished' in run(cwd=project).stdout
    agent = subprocess.Popen([sys.executable, '-c', _AGENT], cwd=project, text=True, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, env={**os.environ, 'METAFORM_HOME': str(home)})
    try:
        assert agent.stdout is not None and agent.stdout.readline().strip() == 'recording'
        [now] = Store('timer').intake_recording().results
        assert (now.layer.id, now.parts) == (left.layer.id, 2)
        assert 'Intake: being recorded' in run(cwd=project).stdout
        refused = run('intake', 'discard', '--confirm', cwd=project, ok=False)
        assert refused.returncode != 0 and 'recording the intake' in refused.stderr
    finally:
        assert agent.stdin is not None
        agent.stdin.close()
        agent.wait(30)
    assert Store('timer').intake_recording().results == ()
    assert run('intake', 'discard', cwd=project, ok=False).returncode != 0  # its caution asks for --confirm
    gone = recorded(run, project, 'discard', '--confirm')
    assert (gone['layer'], gone['parts']) == (left.layer.name, 2)
    assert Store('timer').intake_building().results == () and not Store('timer').has_intake()
    assert Store('timer').graph(raw=True, limit=0).elements == ()


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


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
def test_an_intake_agent_at_work_holds_the_intake_against_every_other_caller_and_no_agent_is_told_first_run(
        run, home, project):
    """UX review round 1, 2026-10-17 (cross-surface F3, F4): while a dispatched intake agent's runner lives, before its
    first record too, the person's own agent is not told FIRST RUN or that an intake was aborted; another caller's
    start, record, finish or discard is refused; and the intake its records go into, through the command line too, is
    being recorded, never left unfinished."""
    held = _intake_runner(home, project)
    try:
        shown = run('help', 'agents', cwd=project).stdout
        assert onboarding() not in shown and 'FIRST RUN' not in shown
        assert 'an agent Metaform started is at work on it now (claude), work intake-x' in run(cwd=project).stdout
        assert 'metaform dispatch stop intake-x' in run('intake', 'status', cwd=project).stdout
        for words in (('start',), ('element', 'code.timer.kitchen', 'role=DE'), ('finish',)):
            refused = run('intake', *words, cwd=project, ok=False)
            assert refused.returncode != 0 and 'dispatch stop intake-x' in refused.stdout + refused.stderr, words
        mine = {'METAFORM_WORK': 'intake-x'}  # the intake agent itself, through its shell's command line
        run('intake', 'start', cwd=project, env=mine)
        run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=project, env=mine)
        [now] = Store('timer').intake_building().results
        assert now.recording, 'the intake agent records it whatever surface it records through'
        assert 'aborted' not in run('help', 'agents', cwd=project).stdout
        refused = run('intake', 'discard', '--confirm', cwd=project, ok=False)
        assert refused.returncode != 0 and 'dispatch stop intake-x' in refused.stdout + refused.stderr
        run('intake', 'finish', cwd=project, env=mine)
    finally:
        _let_go(held)
    assert Store('timer').intake_agent() is None and 'FIRST RUN' not in run('help', 'agents', cwd=project).stdout


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
@pytest.mark.parametrize(('choice', 'mode'), [('new', 'fresh'), ('extend', 'refine')])
def test_selected_intake_mode_reaches_first_turn_and_recording(run, home, project, choice, mode):
    """An existing map cannot redirect explicit Fresh into refinement. Refine reads that map instead."""
    from metaform import prompt_files
    from metaform.module import Context
    from metaform.modules.dispatch import intake_prompt

    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE')
    recorded(run, project, 'finish')
    ticket = Store('timer').add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='Preserve this work.')
    original = metaform_home.active_base('timer')
    original_graph = Store('timer').graph(raw=True, limit=0)
    held = _intake_runner(home, project, map=choice, name='fresh-map' if choice == 'new' else '', mode=mode)
    mine = {'METAFORM_WORK': 'intake-x'}
    try:
        ctx = Context('dispatch', project, project='timer', store=Store('timer'), identity=mine)
        assert ctx.require_store().intake_agent()['mode'] == mode
        first = intake_prompt(ctx, 'Examine current artifacts.')
        expected_request = prompt_files.required(SPEC.parent.parent, 'selected_mode', mode=mode,
                                                 request='Examine current artifacts.')
        assert first == served_asked(expected_request)
        reread = run('intake', 'prompt', 'text=Examine current artifacts.', cwd=project, env=mine).stdout
        assert reread == first
        assert 'This project has an intake' in run('intake', 'status', cwd=project, env=mine).stdout
        said = json.loads(run('intake', 'start', '--json', cwd=project, env=mine).stdout)
        assert said['base'] == ('fresh-map' if choice == 'new' else 'main')
        shown = json.loads(run('intake', 'show', '--json', cwd=project, env=mine).stdout)
        assert bool(shown['elements']) == (choice == 'extend')
        if choice == 'new':
            assert Store('timer', base='fresh-map').work(limit=0).results == ()
        run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=project, env=mine)
        run('intake', 'finish', cwd=project, env=mine)
        assert metaform_home.active_base('timer') == original
        assert Store('timer').ticket(ticket.id).work == ticket
        if choice == 'new':
            assert Store('timer').graph(raw=True, limit=0) == original_graph
    finally:
        _let_go(held)


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
def test_the_map_the_person_chose_for_an_intake_agent_decides_its_start(run, home, project):
    """UX review round 1, 2026-10-17 (fresh-start F5, web-gui F12): on a mapped project, an intake agent launched with
    map=new opens the new map beside the one in use, named as chosen, though its start gives no name; with map=extend
    its start writes onto the map in use, whatever name the agent gives."""
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.timer.kitchen', 'role=DE')
    recorded(run, project, 'finish')
    original = Store('timer')
    base_id = metaform_home.active_base('timer').id
    ticket = original.add_work(Node('element', 'code.timer.kitchen'), '', task='Retain attached work').id
    mine = {'METAFORM_WORK': 'intake-x'}
    held = _intake_runner(home, project, map='new', name='v2')
    try:
        said = json.loads(run('intake', 'start', '--json', cwd=project, env=mine).stdout)
        assert said['base'] == 'v2' and metaform_home.active_base('timer').id == base_id, said
        separate = Store('timer', base='v2')
        assert separate.element('code.timer.kitchen') is None
        assert separate.work(open=True, limit=0).results == ()
        assert original.ticket(ticket).work.task == 'Retain attached work'
    finally:
        _let_go(held)
    run('map', 'remove-base', 'v2', '--confirm', cwd=project)
    held = _intake_runner(home, project, map='extend')
    try:
        said = json.loads(run('intake', 'start', 'name=elsewhere', '--json', cwd=project, env=mine).stdout)
        assert said['base'] == 'main' and 'opens no new map' in json.dumps(said['notices']), said
        assert [base.name for base in metaform_home.bases('timer')] == ['main']
        assert metaform_home.active_base('timer').id == base_id
        shown = recorded(run, project, 'show')
        assert any(one['namespace_address'] == 'code.timer.kitchen' for one in shown['elements'])
        assert original.ticket(ticket).work.task == 'Retain attached work'
    finally:
        _let_go(held)


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_a_join_with_no_elements_records_nothing_and_starts_no_intake(run, project):
    said = recorded(run, project, 'purpose', 'code.timer.kitchen', '[]', 'purpose=p')
    assert said['layer'] is None and [notice['where'] for notice in said['notices']] == ['elements']
    assert 'No intake yet' in run('intake', 'status', cwd=project).stdout


@pytest.mark.req('BASE-039')
def test_removing_a_join_from_a_building_intake_closes_existing_work_at_it(run, project):
    recorded(run, project, 'purpose', 'code.alarm', '["code.probe.echo"]', 'purpose=p', 'ef=f', 'ifd=receives')
    store = Store('timer')
    [held] = store.joins('code.alarm', raw=True).results
    store.add_work(Node('join', held.id), 'trouble', note='never fires')
    recorded(run, project, 'remove', 'receiver=code.alarm', 'provider=code.probe.echo')
    assert store.work(open=True, limit=0).results == ()


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
    recording = Store('timer').intake_building().results[0]
    seen = []

    def follow_on(payload, ctx):
        assert ctx.project == 'timer'
        store = Store(payload['project'], base=payload['base'])
        assert store.bound_base().id == recording.base_id  # a separate intake's base, finished beside the active one
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

    completed = []

    def no_code_enrichment(_ctx, topic, payload):
        assert topic == 'intake.completed', 'A non-code intake must not start code enrichment.'
        completed.append(payload)
        return []

    monkeypatch.setattr(Context, 'publish', no_code_enrichment)
    assert 'follow_on' not in finish(Context('intake', project, store=Store('timer')))
    assert len(completed) == int(address is not None)


def test_finished_code_intake_without_subscribers_keeps_regular_result(run, project):
    recorded(run, project, 'start')
    recorded(run, project, 'element', 'code.example', 'role=DE')
    result = recorded(run, project, 'finish')
    assert 'follow_on' not in result and 'next' not in result
    assert result['elements'] == 1
    assert Store('timer').has_intake()
