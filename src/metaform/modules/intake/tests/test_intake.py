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
SPEC = ROOT / 'specifications' / 'Canonical_Intake.xml'
RESOURCE = Path(__file__).parents[1] / 'resources' / 'Canonical_Intake.xml'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))
ALWAYS = ('Do not read past memories or any other details other than the material targeted for intake. Record each '
          'element as you work through the process. Use intake_start first, then intake_element, intake_join and '
          'intake_subtype, or metaform intake start, element, join and subtype on the command line. Read it back with '
          'intake_show, correct it with intake_edit and intake_remove, anneal it with intake_absorb, and end with '
          'intake_finish. If you cannot '
          'continue, stop and submit a trouble report with the feedback tool, attaching what you have in its shape '
          'field; do not retry.')
REPORT_LINE = ('Include your report on the project you examined in the report field of intake_finish: broken code, '
               'things that need fixing, anything not working or partially working.')
DEBUG_LINE = ('Include feedback on this process in the feedback field of intake_finish: bad semantics, a tool that '
              'did not match its schema, where you got stuck.')
NOTICE = ('This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions '
          'with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.')


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'timer & co'
    folder.mkdir()
    run('add', 'project', 'timer', str(folder))
    return folder


OBJECT_KEYS = {'namespace_address', 'role', 'name', 'name_length', 'refs', 'joins'}
JOIN_KEYS = {'type', 'provider', 'name', 'purpose', 'function', 'ef', 'relation', 'verb', 'observation', 'non_goal',
             'refs', 'subtypes'}
# The Canonical Intake's schema still puts a name on each element, and the fixture follows it: each is kept in the
# element's extra with a notice, since the project's name for a functionality goes on the join, BASE-039.
NAMED = {'elements[0].name', 'elements[1].name', 'elements[2].name'}
SUBTYPE_KEYS = {'provider', 'function', 'ef', 'relation', 'verb', 'observation', 'element', 'purpose'}


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
            made = call(path, 'join', element['namespace_address'], join.get('provider', ''),
                        *fields(join, {'type', 'name', 'purpose', 'function', 'ef', 'relation', 'verb', 'observation',
                                       'non_goal', 'refs'}))
            for place, subtype in enumerate(join.get('subtypes', [])):
                inner = subtype.get('element', {})
                call(f'{path}.subtypes[{place}]', 'subtype', made['join_id'], inner.get('namespace_address', ''),
                     *fields(subtype, {'function', 'ef', 'relation', 'verb', 'observation', 'purpose'}),
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
    return re.sub(r'<target [^>]*>', '<target>', text, count=1)


def footer(text):
    return text.split('</process>\n', 1)[1]


@pytest.mark.req('BASE-039')
def test_the_served_intake_is_the_stored_file_byte_for_byte():
    assert RESOURCE.read_bytes() == SPEC.read_bytes()


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
@pytest.mark.req('MAP-043')
def test_prompt_serves_the_intake_with_only_its_target_filled(run, project):
    out = run('intake', 'prompt', cwd=project).stdout
    served, _, tail = out.partition('</process>\n')
    stored = SPEC.read_text(encoding='utf-8')
    assert without_target(served + '</process>\n') == without_target(stored)
    assert tail.startswith('\n' + ALWAYS + '\n')
    target = re.search(r'<target [^>]*>', served).group(0)
    assert 'type="path"' in target and f'value="{str(project).replace("&", "&amp;")}"' in target


@pytest.mark.req('CLI-034')
@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_the_footer_asks_for_the_report_and_the_feedback_by_their_settings(run, project):
    default = footer(run('intake', 'prompt', cwd=project).stdout)
    assert ALWAYS in default and REPORT_LINE in default and DEBUG_LINE not in default
    run('set', '--debug', '--no-report', cwd=project)
    flipped = footer(run('intake', 'prompt', cwd=project).stdout)
    assert ALWAYS in flipped and DEBUG_LINE in flipped and REPORT_LINE not in flipped
    once = footer(run('intake', 'prompt', '--report', '--no-debug', cwd=project).stdout)
    assert REPORT_LINE in once and DEBUG_LINE not in once
    assert DEBUG_LINE in footer(run('intake', 'prompt', cwd=project).stdout)


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
    assert (report['project'], report['metaform'], report['elements'], report['joins'], report['subtypes'],
            report['work']) == ('timer', 'main', 4, 2, 1, 0)
    assert set(notices(report)) == NAMED
    assert re.fullmatch(r'intake-\d{8}T\d{6}Z-[0-9a-f]{6}', report['layer'])
    store = Store('timer')
    assert store.has_intake()
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.short_name, kitchen.name_length, kitchen.role, kitchen.open_work) == ('kitchen timer', 2, 'DE', ())
    assert kitchen.extra == {'name': 'kitchen timer daemon'}
    assert [(ref.key, ref.value) for ref in kitchen.refs] == [('path', 'src/main.c')]
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert (cook_join.provider_address, cook_join.purpose, cook_join.non_goal, cook_join.layer) == (
        'code.timer.kitchen', 'Know when each dish is done without watching the clock.', 'Plan the meal.',
        report['layer'])
    alarm_join = store.joins('code.timer.kitchen').results[0]
    assert [(ref.key, ref.value) for ref in alarm_join.refs] == [('path', 'src/alarm.c'), ('path', 'src/pins.h')]
    tick = store.subtypes(alarm_join.join_id).results[0]
    assert (tick.address, tick.function, tick.role, tick.name) == (
        'code.loop.tick', 'tick_all subtracts one second from each running countdown.', 'SE', 'one-second tick loop')
    assert (cook_join.ef, alarm_join.ef, tick.ef) == ('Function', 'Encounter', 'Function')
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
    assert sorted((row['type'], row['ef']) for row in document['joins']) == [
        ('purpose', 'Encounter'), ('purpose', 'Function'), ('subtype', 'Function')]
    assert sorted(row['verb'] for row in document['joins']) == ['advances', 'rings', 'tells']


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-020')
@pytest.mark.req('MAP-040')
@pytest.mark.req('STORE-009')
@pytest.mark.req('BASE-044')
def test_the_projects_name_for_a_functionality_is_recorded_on_its_join_and_an_element_keeps_a_name_in_its_extra(
        run, project):
    """Rich, 2026-09-27: the element is its address, name_length and role, and the project's own name for a
    functionality goes on the join, the purpose join and the subtype join alike. The Canonical Intake still shows a
    name on the element, so a name sent there is kept in the element's extra and the notice says where it goes."""
    run('intake', 'start', cwd=project)
    element = json.loads(run('intake', 'element', 'code.timer.kitchen', 'role=DE', 'name_length=2',
                             'name=kitchen timer daemon', '--json', cwd=project).stdout)
    [named] = [notice for notice in element['notices'] if notice['where'] == 'name']
    assert 'join' in named['message'] and 'extra' in named['message']
    run('intake', 'element', 'code.alarm.audible', 'role=SE', 'name_length=2', cwd=project)
    join = json.loads(run('intake', 'join', 'code.timer.kitchen', 'code.alarm.audible', 'name=end-of-countdown alarm',
                          'purpose=Get attention.', 'function=Rings.', 'ef=Encounter', 'relation=The alarm rings.',
                          'verb=rings', 'observation=A piezo.', '--json', cwd=project).stdout)
    assert join['notices'] == []
    inner = json.loads(run('intake', 'subtype', join['join_id'], 'code.loop.tick', 'name=one-second tick',
                           'name_length=2', 'role=SE', 'function=Ticks.', 'ef=Function', 'relation=The loop ticks.',
                           'verb=ticks', 'observation=One interrupt a second.', '--json', cwd=project).stdout)
    assert inner['notices'] == []
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert [row['name'] for row in shown['joins']] == ['end-of-countdown alarm']
    assert [(row['name'], row['short_name']) for row in shown['joins'][0]['subtypes']] == [
        ('one-second tick', 'tick loop')]
    kitchen = next(row for row in shown['elements'] if row['namespace_address'] == 'code.timer.kitchen')
    assert (kitchen['short_name'], kitchen['name_length'], kitchen['role'], kitchen['extra']) == (
        'kitchen timer', 2, 'DE', {'name': 'kitchen timer daemon'})
    assert 'name' not in kitchen
    run('intake', 'finish', cwd=project)
    store = Store('timer')
    held = store.joins('code.timer.kitchen').results[0]
    assert held.name == 'end-of-countdown alarm'
    assert store.subtypes(held.join_id).results[0].name == 'one-second tick'
    assert store.element('code.timer.kitchen').extra == {'name': 'kitchen timer daemon'}
    assert nouns_of('join')['name'].help == nouns_of('subtype')['name'].help
    assert 'join' in nouns_of('element')['name'].help and 'extra' in nouns_of('element')['name'].help


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_the_intake_and_its_tool_ask_every_join_and_subtype_join_for_function_or_encounter():
    """Each EF is named Function when it is the encounter of a functionality, Encounter when it is the functionality
    of the encounter, Rich 2026-09-26; a closed choice of two, on top-level and subtype joins alike."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(RESOURCE.read_text(encoding='utf-8'))
    join = root.find('.//schema//join')
    assert join is not None and join.get('ef') == '[Function|Encounter]'
    inner = join.find('join')
    assert inner is not None and inner.get('ef') == '[Function|Encounter]'
    step = root.find(".//step[@n='4']").get('text')
    assert 'Function if it is the encounter of a functionality' in step
    assert 'Encounter if it is the functionality of the encounter' in step
    for noun in (nouns_of('join')['ef'], nouns_of('subtype')['ef']):
        assert noun.schema['enum'] == ['Function', 'Encounter']


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-039')
def test_the_intake_and_its_tool_ask_every_join_and_subtype_join_for_the_verb_of_its_relation():
    """The agent infers the relation's verb into its own field, a third-person singular present-tense active verb
    ending in -s or -es, and the relation is a fragment that starts with it; the relation's subject follows the word,
    the Providing Element for Function, and for Encounter the Vested Entity on a top-level join and the Receiving
    Entity in a subtype join, since the Vested Entity is only ever at the top, Rich 2026-09-26 and 2026-09-27. The
    verb is the agent's word. The tools' help carries the intake's own wording."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(RESOURCE.read_text(encoding='utf-8'))
    join = root.find('.//schema//join')
    inner = join.find('join')
    fragment = ('active-voice descriptive fragment starting directly with a third-person singular present-tense verb '
                'ending in -s/-es')
    for found in (join, inner):
        assert found.get('verb') == '[third-person singular present-tense active verb ending in -s or -es]'
        assert found.get('relation').startswith('[' + fragment)
    assert 'the Providing Element when ef is Function, the Vested Entity when ef is Encounter' in join.get('relation')
    assert 'the Providing Element when ef is Function, the Receiving Entity when ef is Encounter' in inner.get('relation')
    same = lambda noun, placeholder: noun.help.rstrip('.').lower() == placeholder.strip('[]').lower()
    assert same(nouns_of('join')['verb'], join.get('verb')) and same(nouns_of('subtype')['verb'], inner.get('verb'))
    assert same(nouns_of('join')['relation'], join.get('relation'))
    assert same(nouns_of('subtype')['relation'], inner.get('relation'))
    step = root.find(".//step[@n='4']").get('text')
    assert ('the relation as an active-voice descriptive fragment starting directly with a third-person singular '
            'present-tense verb ending in -s or -es, whose subject is the Providing Element when ef is Function and the '
            'Vested Entity when ef is Encounter, that verb as verb') in step
    for name in ('join', 'subtype'):
        assert nouns_of(name)['verb'].kind == 'str'


@pytest.mark.req('MAP-020')
@pytest.mark.req('BASE-044')
def test_a_join_or_subtype_join_without_ef_is_stored_and_named_in_a_notice(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    del given['elements'][0]['joins'][0]['ef']
    del given['elements'][1]['joins'][0]['subtypes'][0]['ef']
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert re.match(r'ef is missing\b', found['elements[0].joins[0].ef'])
    assert re.match(r'ef is missing\b', found['elements[1].joins[0].subtypes[0].ef'])
    store = Store('timer')
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert cook_join.ef is None and store.subtypes(store.joins('code.timer.kitchen').results[0].join_id).results[0].ef is None


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
    assert cook_join.purpose in (None, '') and cook_join.function.startswith('The timer counts down')
    assert not any(NOTICE in line for line in run(cwd=project).stdout.splitlines())


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('MAP-030')
@pytest.mark.req('STORE-011')
def test_a_subtype_carrying_a_purpose_is_stored_with_the_purpose_in_its_extra(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    given['elements'][1]['joins'][0]['subtypes'][0]['purpose'] = 'Its own why.'
    report = submit(run, project, given, tmp_path)
    assert 'elements[1].joins[0].subtypes[0].purpose' in notices(report)
    store = Store('timer')
    join = store.joins('code.timer.kitchen').results[0]
    tick = store.subtypes(join.join_id).results[0]
    assert tick.extra == {'purpose': 'Its own why.'}


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-026')
def test_what_does_not_fit_is_stored_as_given_and_named_in_a_notice(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    cook = given['elements'][0]
    cook['joins'][0]['provider'] = 'code.nowhere'
    cook['joins'].append({'provider': 'stakeholder.cook.home', 'purpose': 'Cook for itself.', 'function': 'f',
                          'relation': 'r', 'observation': 'o'})
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
    assert odd is not None and odd.element.extra == {'colour': 'red', 'name': 'audible alarm'}


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
    made = json.loads(run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=cruft',
                          'note=disabled since the 2.0 rewrite', 'task=remove the module and its tests', '--json',
                          cwd=project).stdout)
    assert made['condition'] == 'cruft'
    report = submit(run, project, copy.deepcopy(FIXTURE), tmp_path,
                    extra=('report=The alarm pin is unconnected.', 'feedback=The subtype fields were clear.'))
    assert report['work'] == 1
    layer_id = Store('timer').layers(kind='intake').results[0].layer_id
    folder = home / 'projects' / 'timer' / 'reports'
    assert (folder / f'{layer_id}-report.md').read_text(encoding='utf-8') == 'The alarm pin is unconnected.'
    assert (folder / f'{layer_id}-feedback.md').read_text(encoding='utf-8') == 'The subtype fields were clear.'
    assert sorted(path.name for path in project.iterdir()) == []
    listed = json.loads(run('list', 'reports', '--json', cwd=project).stdout)['results']
    assert sorted((row['name'], row['kind']) for row in listed) == [
        (f'{layer_id}-feedback.md', 'feedback'), (f'{layer_id}-report.md', 'report')]
    provenance = Store('timer').provenance(report['layer'])
    assert sorted((ref.key, ref.value) for ref in provenance.refs) == [
        ('feedback', f'{layer_id}-feedback.md'), ('report', f'{layer_id}-report.md')]
    cruft = json.loads(run('map', 'work', 'condition=cruft', '--json', cwd=project).stdout)['results']
    assert [(row['address'], row['condition'], row['note'], row['task']) for row in cruft] == [
        ('code.alarm.audible', 'cruft', 'disabled since the 2.0 rewrite', 'remove the module and its tests')]
    assert Store('timer').element('code.alarm.audible').open_work == ('cruft',)


@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_the_intake_tools_carry_no_condition_field_and_a_flag_sent_anyway_is_kept_in_extra(run, project, tmp_path):
    for verb in ('element', 'join', 'subtype', 'edit'):
        assert not {'flag', 'flag_note'} & set(nouns_of(verb)), verb
    given = copy.deepcopy(FIXTURE)
    given['elements'][2]['flag'] = 'broken'
    report = submit(run, project, given, tmp_path)
    assert report['work'] == 0 and 'elements[2].flag' in notices(report)
    alarm = Store('timer').element('code.alarm.audible')
    assert alarm.open_work == () and alarm.extra == {'flag': 'broken', 'name': 'audible alarm'}
    assert not hasattr(alarm, 'flag')


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-016')
def test_two_elements_with_one_address_are_one_element_holding_both_joins(run, project, tmp_path):
    doubled = copy.deepcopy(FIXTURE)
    doubled['elements'].append({'namespace_address': 'stakeholder.cook.home', 'role': 'VE', 'joins': [
        {'provider': 'code.alarm.audible', 'purpose': 'Hear it from the next room.', 'function': 'Rings loudly.',
         'ef': 'Encounter', 'relation': 'The alarm reaches the cook.', 'verb': 'reaches', 'observation': 'Loud.'}]})
    report = submit(run, project, doubled, tmp_path)
    assert set(notices(report)) == NAMED
    joins = Store('timer').joins('stakeholder.cook.home').results
    assert sorted(join.provider_address for join in joins) == ['code.alarm.audible', 'code.timer.kitchen']


@pytest.mark.req('BASE-039')
@pytest.mark.req('CLI-028')
@pytest.mark.req('MCP-009')
def test_status_carries_the_notice_until_an_intake_is_stored_then_names_the_entry(run, project, tmp_path):
    out = run(cwd=project).stdout.splitlines()
    assert 'Intake: none yet' in out and '  ' + NOTICE in out
    assert run('intake', 'status', cwd=project).stdout.startswith('No intake')
    report = submit(run, project, FIXTURE, tmp_path)
    out = run(cwd=project).stdout.splitlines()
    assert 'Intake: complete' in out and 'Start with: metaform map roots' in out
    assert not any(NOTICE in line for line in out)
    assert report['layer'] in run('intake', 'status', cwd=project).stdout


@pytest.mark.req('MAP-041')
@pytest.mark.req('MAP-042')
def test_an_artifact_that_is_not_software_is_mapped_the_same_way(run, tmp_path):
    photos = tmp_path / 'photos'
    photos.mkdir()
    (photos / 'kitchen.jpg').write_bytes(b'\xff\xd8\xff')
    run('add', 'project', 'photos', str(photos), 'artifact', 'kitchen_photos')
    document = {'elements': [
        {'namespace_address': 'media.photo.product', 'role': 'AUE', 'name': 'kitchen photos'},
        {'namespace_address': 'stakeholder.seller', 'role': 'VE', 'joins': [
            {'provider': 'media.photo.subject', 'purpose': 'Show the object at its best.', 'function': 'Frames it.',
             'ef': 'Encounter', 'relation': 'The subject carries the sale.', 'observation': 'One mixer, centred.'}]},
        {'namespace_address': 'media.photo.subject', 'role': 'DE'}]}
    submit(run, photos, document, tmp_path)
    store = Store('photos')
    assert store.element('media.photo.product').role == 'AUE' and store.element('media.photo.subject').role == 'DE'
    assert store.project().target_type == 'artifact'
    served = run('intake', 'prompt', cwd=photos).stdout
    assert re.search(r'<target [^>]*type="artifact"[^>]*value="kitchen_photos"', served)


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
    run('intake', 'element', 'stakeholder.cook.home', 'role=VE', 'name=Home cook', cwd=project)
    made = json.loads(run('intake', 'join', 'stakeholder.cook.home', 'code.timer.kitchen',
                          'purpose=Know when each dish is done.', 'function=Counts down and rings.', 'ef=Function',
                          'relation=The kitchen timer tells the cook.', 'verb=tells',
                          'observation=One countdown per dish.', '--json', cwd=project).stdout)
    assert made['join_id'] and [notice['where'] for notice in made['notices']] == ['provider']
    assert 'code.timer.kitchen was not an element' in made['notices'][0]['message']
    store = Store('timer')
    assert not store.has_intake() and store.element('stakeholder.cook.home') is None
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert (len(shown['elements']), len(shown['joins']), len(shown['joins'][0]['subtypes'])) == (2, 1, 0)
    assert shown['undescribed'] == ['code.timer.kitchen']
    assert 'Intake: being recorded' in run(cwd=project).stdout
    assert NOTICE not in run(cwd=project).stdout
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
def test_edit_and_remove_change_a_building_intake_and_a_finished_one_changes_only_by_correction(run, project):
    run('intake', 'start', cwd=project)
    run('intake', 'element', 'code.a', 'role=DE', cwd=project)
    run('intake', 'element', 'code.b', 'role=SE', cwd=project)
    first = json.loads(run('intake', 'join', 'code.a', 'code.b', 'purpose=p', 'function=f', 'ef=Function',
                           'relation=r', 'verb=v', 'observation=o', '--json', cwd=project).stdout)
    second = json.loads(run('intake', 'join', 'code.b', 'code.a', 'purpose=q', 'function=g', 'ef=Encounter',
                            'relation=s', 'verb=w', 'observation=o', '--json', cwd=project).stdout)
    run('intake', 'edit', first['join_id'], 'purpose=The better purpose.', cwd=project)
    run('intake', 'remove', second['join_id'], cwd=project)
    shown = json.loads(run('intake', 'show', '--json', cwd=project).stdout)
    assert [(join['join_id'], join['purpose']) for join in shown['joins']] == [
        (first['join_id'], 'The better purpose.')]
    run('intake', 'finish', cwd=project)
    late = json.loads(run('intake', 'edit', first['join_id'], 'purpose=Too late.', '--json', cwd=project).stdout)
    assert 'correction layer' in late['notices'][0]['message']
    gone = json.loads(run('intake', 'remove', first['join_id'], '--json', cwd=project).stdout)
    assert 'correction layer' in gone['notices'][0]['message']
    assert [(join.join_id, join.purpose) for join in Store('timer').joins('code.a').results] == [
        (first['join_id'], 'The better purpose.')]


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
def test_the_intake_asks_for_each_object_to_be_recorded_as_it_is_reasoned_then_proofed():
    """Rich, 2026-09-26: construct the intake object by object as it is reasoned, each submitted as the work
    proceeds, then a proofing pass; the method and its semantics are unchanged."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(RESOURCE.read_text(encoding='utf-8'))
    steps = {step.get('n'): step.get('text') for step in root.iter('step')}
    assert steps['4'].endswith('Record each element and join as soon as it is reasoned, one object at a time, rather '
                               'than holding the map until the end.')
    assert steps['12'] == ('Proof the recorded map: read it back whole, check it against the artifact and this '
                           'document, correct it, anneal it and complete it, then finish the intake.')
    said = [instruction.text for instruction in root.iter('instruction')]
    assert not any('Respond with well-formed XML' in text for text in said)
    assert ('Record the result with the intake tools, one object per call, as it is reasoned. The schema below '
            'defines the fields of each object; it is not returned as a document.') in said
    assert root.find('.//output_instruction').get('text') == ('Record the final shape with the intake tools; nothing '
                                                              'is returned as a document.')


def recorded(run, cwd, *args):
    return json.loads(run('intake', *args, '--json', cwd=cwd).stdout)


def failsafe_intake(run, project):
    """A building intake where an operator receives from a gateway failsafe and from an echo probe the failsafe can
    absorb, and an alarm receives from the probe too."""
    recorded(run, project, 'start')
    for address, role in (('stakeholder.operator', 'VE'), ('code.failsafe.gateway', 'DE'), ('code.probe.echo', 'SE'),
                          ('code.alarm', 'SE')):
        recorded(run, project, 'element', address, f'role={role}', 'name_length=1')
    parent = recorded(run, project, 'join', 'stakeholder.operator', 'code.failsafe.gateway',
                      'purpose=Catch a dead gateway.', 'function=Probes the gateway and fails over.', 'ef=Function',
                      'relation=The failsafe watches the gateway.', 'verb=watches', 'observation=Two probes.')
    probe = recorded(run, project, 'join', 'stakeholder.operator', 'code.probe.echo', 'name=echo probe',
                     'purpose=Know the gateway answers.', 'function=Sends an echo each second.', 'ef=Function',
                     'relation=The echo probe pings the gateway.', 'verb=pings', 'observation=ICMP echo.',
                     'non_goal=Measure latency.', 'refs=[{"key": "path", "value": "src/echo.c"}]')
    other = recorded(run, project, 'join', 'code.alarm', 'code.probe.echo', 'purpose=Hear a lost echo.',
                     'function=Reports each lost echo.', 'ef=Function', 'relation=The probe tells the alarm.',
                     'verb=tells', 'observation=One report per loss.')
    return parent, probe, other


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-031')
@pytest.mark.req('MAP-040')
def test_absorb_makes_a_recorded_join_a_subtype_join_inside_its_parents_join(run, project):
    """Rich, 2026-09-27: an element always appears as one element record; annealing places it in its parent's join as
    a subtype join, and the element itself does not move."""
    parent, probe, other = failsafe_intake(run, project)
    absorbed = recorded(run, project, 'absorb', probe['join_id'], parent['join_id'])
    assert (absorbed['join_id'], absorbed['parent']) == (probe['join_id'], parent['join_id'])
    assert other['join_id'] in ' '.join(notice['message'] for notice in absorbed['notices'])
    shown = recorded(run, project, 'show')
    assert probe['join_id'] not in [row['join_id'] for row in shown['joins']]
    [held] = [row for row in shown['joins'] if row['join_id'] == parent['join_id']]
    [sub] = held['subtypes']
    assert (sub['join_id'], sub['parent'], sub['namespace_address'], sub['name'], sub['function'], sub['ef'],
            sub['relation'], sub['verb'], sub['observation'], sub['non_goal'], sub['extra']) == (
        probe['join_id'], parent['join_id'], 'code.probe.echo', 'echo probe', 'Sends an echo each second.', 'Function',
        'The echo probe pings the gateway.', 'pings', 'ICMP echo.', 'Measure latency.',
        {'purpose': 'Know the gateway answers.'})
    assert sub['refs'] == [{'key': 'path', 'value': 'src/echo.c'}]
    [element] = [row for row in shown['elements'] if row['namespace_address'] == 'code.probe.echo']
    assert sub['element_id'] == absorbed['element_id'] == element['element_id'] and element['role'] == 'SE'
    recorded(run, project, 'remove', other['join_id'])
    finished = recorded(run, project, 'finish')
    assert (finished['elements'], finished['joins'], finished['subtypes']) == (4, 1, 1)
    store = Store('timer')
    assert store.element('code.probe.echo').element_id == element['element_id']
    assert 'code.probe.echo' not in [root.address for root in store.roots().elements]
    assert 'code.probe.echo' not in [placed.element.address for placed in store.graph().elements]
    assert [sub.join_id for sub in store.subtypes(parent['join_id']).results] == [probe['join_id']]


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
def test_show_reads_one_receivers_joins_and_what_they_hold(run, project):
    """Rich, 2026-09-27: the intake must not depend on the size of the agent's context."""
    parent, probe, other = failsafe_intake(run, project)
    recorded(run, project, 'absorb', probe['join_id'], parent['join_id'])
    operator = recorded(run, project, 'show', 'receiver=stakeholder.operator')
    assert [row['join_id'] for row in operator['joins']] == [parent['join_id']]
    assert [sub['join_id'] for sub in operator['joins'][0]['subtypes']] == [probe['join_id']]
    assert {row['namespace_address'] for row in operator['elements']} == {
        'stakeholder.operator', 'code.failsafe.gateway', 'code.probe.echo'}
    alarm = recorded(run, project, 'show', 'receiver=code.alarm')
    assert [row['join_id'] for row in alarm['joins']] == [other['join_id']]
    assert alarm['joins'][0]['subtypes'] == []


@pytest.mark.req('BASE-039')
def test_show_names_every_object_by_the_key_its_recording_call_returned_and_edit_and_remove_take_it(run, project):
    """A Fable intake on 2026-09-27 crashed its own script expecting join_id where intake_show said id."""
    parent, probe, _ = failsafe_intake(run, project)
    made = recorded(run, project, 'subtype', parent['join_id'], 'code.probe.ping', 'role=SE', 'name_length=1',
                    'function=Sends a ping.', 'ef=Function', 'relation=The ping probe pings the gateway.',
                    'verb=pings', 'observation=ICMP.')
    assert set(made) >= {'join_id', 'parent', 'element_id', 'namespace_address'} and 'id' not in made
    shown = recorded(run, project, 'show')
    assert all('element_id' in row and 'namespace_address' in row and 'id' not in row and 'address' not in row
               for row in shown['elements'])
    assert all('join_id' in row and 'id' not in row for row in shown['joins'])
    [sub] = [sub for row in shown['joins'] for sub in row['subtypes']]
    assert (sub['join_id'], sub['parent'], sub['element_id']) == (made['join_id'], parent['join_id'],
                                                                  made['element_id'])
    element = next(row for row in shown['elements'] if row['namespace_address'] == 'code.alarm')
    recorded(run, project, 'edit', element['element_id'], 'name_length=2')
    recorded(run, project, 'edit', sub['join_id'], 'function=Sends a ping each second.')
    recorded(run, project, 'remove', probe['join_id'])
    again = recorded(run, project, 'show')
    assert next(row for row in again['elements'] if row['namespace_address'] == 'code.alarm')['name_length'] == 2
    assert [sub['function'] for row in again['joins'] for sub in row['subtypes']] == ['Sends a ping each second.']
    assert probe['join_id'] not in [row['join_id'] for row in again['joins']]
    assert 'namespace_address' in nouns_of('element') and 'address' not in nouns_of('element')
    assert {'into', 'namespace_address'} <= set(nouns_of('subtype')) and 'join' not in nouns_of('subtype')
    assert {'join', 'into'} <= set(nouns_of('absorb'))


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-003')
def test_edit_never_moves_an_element_and_moves_a_join_by_its_receiver(run, project):
    parent, probe, other = failsafe_intake(run, project)
    element = next(row for row in recorded(run, project, 'show')['elements']
                   if row['namespace_address'] == 'code.alarm')
    kept = recorded(run, project, 'edit', element['element_id'], 'namespace_address=code.alarm.siren', 'role=NE')
    [named] = [notice for notice in kept['notices'] if notice['where'] == 'namespace_address']
    assert 'cannot be moved' in named['message']
    shown = recorded(run, project, 'show')
    alarm = next(row for row in shown['elements'] if row['element_id'] == element['element_id'])
    assert (alarm['namespace_address'], alarm['role']) == ('code.alarm', 'NE')
    assert 'code.alarm.siren' not in [row['namespace_address'] for row in shown['elements']]
    moved = recorded(run, project, 'edit', other['join_id'], 'receiver=code.failsafe.gateway')
    assert moved['notices'] == []
    again = recorded(run, project, 'show', 'receiver=code.failsafe.gateway')
    assert [row['join_id'] for row in again['joins']] == [other['join_id']]
    assert recorded(run, project, 'show', 'receiver=code.alarm')['joins'] == []
    recorded(run, project, 'finish')
    late = recorded(run, project, 'absorb', probe['join_id'], parent['join_id'])
    assert 'correction layer' in late['notices'][0]['message']
    assert [join.join_id for join in Store('timer').joins('stakeholder.operator').results] == sorted(
        [parent['join_id'], probe['join_id']])
