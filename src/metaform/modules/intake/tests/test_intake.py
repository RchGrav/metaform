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
ALWAYS = ('Submit the result with intake_submit, or metaform intake submit on the command line. If you cannot '
          'continue, stop and submit a trouble report with the feedback tool, attaching what you have in its shape '
          'field; do not retry.')
REPORT_LINE = ('Include your report on the project you examined in the report field: broken code, things that need '
               'fixing, anything not working or partially working.')
DEBUG_LINE = ('Include feedback on this process in the feedback field: bad semantics, a tool that did not match its '
              'schema, where you got stuck.')
NOTICE = ('This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions '
          'with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.')


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'timer & co'
    folder.mkdir()
    run('add', 'project', 'timer', str(folder))
    return folder


def submit(run, cwd, document, tmp_path, extra=(), as_json=True):
    path = tmp_path / 'elements.json'
    path.write_text(json.dumps(document['elements']), encoding='utf-8')
    args = ['intake', 'submit', f'elements={path}', *extra]
    if 'id' in document:
        args.append(f'id={document["id"]}')
    result = run(*args, *(['--json'] if as_json else []), cwd=cwd)
    return json.loads(result.stdout) if as_json else result


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
def test_a_submission_is_stored_whole_and_reads_back(run, project, tmp_path):
    report = submit(run, project, FIXTURE, tmp_path, extra=('model=claude', 'role=intake agent'))
    assert (report['project'], report['metaform'], report['elements'], report['joins'], report['subtypes'],
            report['findings']) == ('timer', 'main', 3, 2, 1, 0)
    assert report['notices'] == []
    assert re.fullmatch(r'intake-\d{8}T\d{6}Z-[0-9a-f]{6}', report['layer'])
    store = Store('timer')
    assert store.has_intake()
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.name, kitchen.name_length, kitchen.role, kitchen.flag) == ('kitchen timer daemon', 2, 'DE', None)
    assert [(ref.key, ref.value) for ref in kitchen.descriptors[0].refs] == [('path', 'src/main.c')]
    cook_join = store.joins('stakeholder.cook.home').results[0]
    assert (cook_join.provider_address, cook_join.purpose, cook_join.non_goal, cook_join.layer) == (
        'code.timer.kitchen', 'Know when each dish is done without watching the clock.', 'Plan the meal.',
        report['layer'])
    alarm_join = store.joins('code.timer.kitchen').results[0]
    assert [(ref.key, ref.value) for ref in alarm_join.refs] == [('path', 'src/alarm.c'), ('path', 'src/pins.h')]
    tick = store.subtypes(alarm_join.join_id).results[0]
    assert (tick.address, tick.function, tick.role, tick.name) == (
        'code.loop.tick', 'tick_all subtracts one second from each running countdown.', 'SE', 'one-second tick loop')
    assert store.element('code.loop.tick') is None
    layer = next(item for item in store.layers().results if item.name == report['layer'])
    assert (layer.kind, layer.mutable, layer.hideable, layer.result_id) == ('intake', False, False,
                                                                           'kitchen-timer-typology')
    provenance = store.provenance(report['layer'])
    assert (provenance.module, provenance.workflow, provenance.model, provenance.role) == (
        'intake', 'canonical-intake', 'claude', 'intake agent')
    assert provenance.prompt is None  # the Canonical Intake's purpose never changes, so no copy is kept, STORE-016
    document = export_document(['timer'], layers=[report['layer']])['projects'][0]['metaforms'][0]
    assert len(document['elements']) == 3 and len(document['joins']) == 2 and len(document['subtypes']) == 1


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
@pytest.mark.req('STORE-032')
@pytest.mark.req('MCP-009')
def test_a_join_missing_its_purpose_is_stored_whole_with_a_notice_naming_it(run, project, tmp_path):
    broken = copy.deepcopy(FIXTURE)
    del broken['elements'][0]['joins'][0]['purpose']
    result = submit(run, project, broken, tmp_path, as_json=False)
    assert result.returncode == 0
    assert re.search(r'^Notice: elements\[0\]\.joins\[0\]: .*purpose', result.stdout, re.M)
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
    assert 'elements[1].joins[0].subtypes[0]' in notices(report)
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
    tick = given['elements'][1]['joins'][0]['subtypes'][0]
    tick['provider'] = 'code.loop.other'
    given['elements'][2]['namespace_address'] = 'Code..Alarm'
    given['elements'][2]['colour'] = 'red'
    report = submit(run, project, given, tmp_path)
    found = notices(report)
    assert {'elements[0].joins[0]', 'elements[0].joins[1]', 'elements[1].joins[0].subtypes[0]',
            'elements[2].namespace_address', 'elements[2]'} <= set(found)
    store = Store('timer')
    nowhere = store.element('code.nowhere')
    assert nowhere is not None and nowhere.role is None and nowhere.layer == report['layer']
    assert {join.provider_address for join in store.joins('stakeholder.cook.home').results} == {
        'code.nowhere', 'stakeholder.cook.home'}
    kitchen_join = store.joins('code.timer.kitchen', raw=True).results[0]
    stored_tick = store.subtypes(kitchen_join.join_id, raw=True).results[0]
    assert stored_tick.address == 'code.loop.tick' and stored_tick.extra == {'provider': 'code.loop.other'}
    odd = store.where('Code..Alarm', raw=True)
    assert odd is not None and odd.element.extra == {'colour': 'red'}


@pytest.mark.req('BASE-039')
@pytest.mark.req('BASE-044')
def test_elements_that_cannot_be_read_store_nothing_and_return_one_notice(run, project, tmp_path):
    path = tmp_path / 'elements.json'
    path.write_text('{not json', encoding='utf-8')
    result = run('intake', 'submit', f'elements={path}', '--json', cwd=project)
    report = json.loads(result.stdout)
    assert len(report['notices']) == 1 and report['notices'][0]['where'] == 'elements'
    message = report['notices'][0]['message']
    assert 'feedback' in message and 'shape' in message and 'again' not in message
    assert Store('timer').layers().results == ()
    assert Store('timer').has_intake() is False


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
def test_a_report_feedback_and_flags_are_saved_listed_and_part_of_provenance(run, project, tmp_path, home):
    given = copy.deepcopy(FIXTURE)
    given['elements'][2]['flag'] = 'cruft'
    given['elements'][2]['flag_note'] = 'disabled since the 2.0 rewrite'
    path = tmp_path / 'elements.json'
    path.write_text(json.dumps(given['elements']), encoding='utf-8')
    report = json.loads(run('intake', 'submit', f'elements={path}', 'report=The alarm pin is unconnected.',
                            'feedback=The subtype fields were clear.', '--json', cwd=project).stdout)
    assert report['findings'] == 1
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
    cruft = json.loads(run('map', 'findings', 'flag=cruft', '--json', cwd=project).stdout)['results']
    assert [(row['address'], row['flag'], row['note']) for row in cruft] == [
        ('code.alarm.audible', 'cruft', 'disabled since the 2.0 rewrite')]


@pytest.mark.req('MAP-046')
@pytest.mark.req('STORE-042')
def test_each_flag_reads_back_on_its_object_and_working_has_none(run, project, tmp_path):
    given = copy.deepcopy(FIXTURE)
    given['elements'][0]['flag'] = 'missing'
    given['elements'][1]['flag'] = 'broken'
    given['elements'][1]['joins'][0]['flag'] = 'missing'
    given['elements'][1]['joins'][0]['subtypes'][0]['flag'] = 'cruft'
    given['elements'][2]['flag'] = 'sideways'
    report = submit(run, project, given, tmp_path)
    assert report['findings'] == 5
    assert 'elements[2].flag' in notices(report)
    store = Store('timer')
    assert store.element('stakeholder.cook.home').flag == 'missing'
    assert store.element('code.timer.kitchen').flag == 'broken'
    alarm = store.element('code.alarm.audible')
    assert (alarm.flag, alarm.flag_note) == ('broken', 'sideways')
    join = store.joins('code.timer.kitchen').results[0]
    assert join.flag == 'missing'
    assert store.subtypes(join.join_id).results[0].flag == 'cruft'
    working = submit(run, project, FIXTURE, tmp_path)
    assert working['findings'] == 0 and Store('timer').element('code.timer.kitchen').flag is None


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-016')
def test_two_elements_with_one_address_are_one_element_holding_both_joins(run, project, tmp_path):
    doubled = copy.deepcopy(FIXTURE)
    doubled['elements'].append({'namespace_address': 'stakeholder.cook.home', 'role': 'VE', 'joins': [
        {'provider': 'code.alarm.audible', 'purpose': 'Hear it from the next room.', 'function': 'Rings loudly.',
         'relation': 'The alarm reaches the cook.', 'observation': 'Loud.'}]})
    report = submit(run, project, doubled, tmp_path)
    assert report['notices'] == []
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
             'relation': 'The subject carries the sale.', 'observation': 'One mixer, centred.'}]},
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
