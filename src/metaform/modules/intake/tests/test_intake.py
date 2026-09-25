"""The intake module: the Canonical Intake served by name, one atomic submission, intake state, BASE-039."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from metaform.data import Store, export_document

pytestmark = pytest.mark.kind('fixture')

ROOT = Path(__file__).parents[5]
SPEC = ROOT / 'specifications' / 'Canonical_Intake.xml'
RESOURCE = Path(__file__).parents[1] / 'resources' / 'Canonical_Intake.xml'
FIXTURE = json.loads((ROOT / 'tests' / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))
SUBMIT_LINE = 'Submit the result with intake_submit, or metaform intake submit on the command line.'
NOTICE = ('This project has no intake yet. Have a subagent perform it. Tell the subagent to read its instructions '
          'with `metaform intake prompt`, or the `intake_prompt` tool, and to follow them.')


@pytest.fixture
def project(run, tmp_path):
    folder = tmp_path / 'timer & co'
    folder.mkdir()
    run('add', 'project', 'timer', str(folder))
    return folder


def submit(run, cwd, document, tmp_path, ok=True, extra=()):
    path = tmp_path / 'elements.json'
    path.write_text(json.dumps(document['elements']), encoding='utf-8')
    args = ['intake', 'submit', f'elements={path}', *extra]
    if 'id' in document:
        args.append(f'id={document["id"]}')
    return run(*args, '--json', cwd=cwd, ok=ok)


def without_target(text):
    return re.sub(r'<target [^>]*>', '<target>', text, count=1)


@pytest.mark.req('BASE-039')
def test_the_served_intake_is_the_stored_file_byte_for_byte():
    assert RESOURCE.read_bytes() == SPEC.read_bytes()


@pytest.mark.req('BASE-039')
@pytest.mark.req('MCP-009')
@pytest.mark.req('MAP-043')
def test_prompt_serves_the_intake_with_only_its_target_filled(run, project):
    out = run('intake', 'prompt', cwd=project).stdout
    assert out.endswith('\n\n' + SUBMIT_LINE + '\n')
    served = out[:-len('\n' + SUBMIT_LINE + '\n')]
    stored = SPEC.read_text(encoding='utf-8')
    assert without_target(served) == without_target(stored)
    target = re.search(r'<target [^>]*>', served).group(0)
    assert 'type="path"' in target and f'value="{str(project).replace("&", "&amp;")}"' in target


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-040')
@pytest.mark.req('MAP-021')
@pytest.mark.req('LAYER-001')
def test_a_submission_is_stored_whole_and_reads_back(run, project, tmp_path):
    report = json.loads(submit(run, project, FIXTURE, tmp_path, extra=('model=claude', 'role=intake agent')).stdout)
    assert (report['project'], report['elements'], report['joins'], report['subtypes']) == ('timer', 3, 2, 1)
    assert re.fullmatch(r'intake-\d{8}T\d{6}Z-[0-9a-f]{6}', report['layer'])
    store = Store('timer')
    assert store.has_intake()
    kitchen = store.element('code.timer.kitchen')
    assert (kitchen.name, kitchen.name_length, kitchen.role) == ('kitchen timer daemon', 2, 'DE')
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
    assert provenance.prompt == run('intake', 'prompt', cwd=project).stdout
    document = export_document(['timer'], layers=[report['layer']])['projects'][0]['metaforms'][0]
    assert len(document['elements']) == 3 and len(document['joins']) == 2 and len(document['subtypes']) == 1


@pytest.mark.req('BASE-039')
@pytest.mark.req('STORE-032')
@pytest.mark.req('MCP-009')
def test_a_submission_with_a_problem_writes_nothing_and_lists_every_problem(run, project, tmp_path):
    broken = copy.deepcopy(FIXTURE)
    del broken['elements'][0]['joins'][0]['purpose']
    broken['elements'][2]['namespace_address'] = 'Code..Alarm'
    refused = submit(run, project, broken, tmp_path, ok=False)
    assert refused.returncode == 2
    err = refused.stderr
    assert 'elements[0].joins[0]' in err and 'purpose' in err and 'elements[2].namespace_address' in err
    assert err.splitlines()[-1] == 'Next: fix the listed fields and call intake_submit again'
    assert Store('timer').has_intake() is False
    assert Store('timer').layers().results == ()
    assert NOTICE in run(cwd=project).stdout


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-030')
def test_a_subtype_with_a_purpose_is_refused_by_the_schema(run, project, tmp_path):
    broken = copy.deepcopy(FIXTURE)
    broken['elements'][1]['joins'][0]['subtypes'][0]['purpose'] = 'Its own why.'
    refused = submit(run, project, broken, tmp_path, ok=False)
    assert refused.returncode == 2 and 'subtypes[0]' in refused.stderr and 'purpose' in refused.stderr
    assert Store('timer').has_intake() is False


@pytest.mark.req('BASE-039')
def test_a_provider_that_names_no_element_and_a_mismatched_subtype_are_refused(run, project, tmp_path):
    broken = copy.deepcopy(FIXTURE)
    broken['elements'][0]['joins'][0]['provider'] = 'code.nowhere'
    broken['elements'][1]['joins'][0]['subtypes'][0]['provider'] = 'code.loop.other'
    refused = submit(run, project, broken, tmp_path, ok=False)
    assert 'code.nowhere' in refused.stderr and 'code.loop.other' in refused.stderr
    assert Store('timer').has_intake() is False


@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-015')
@pytest.mark.req('MAP-016')
def test_two_elements_with_one_address_are_one_element_holding_both_joins(run, project, tmp_path):
    doubled = copy.deepcopy(FIXTURE)
    doubled['elements'].append({'namespace_address': 'stakeholder.cook.home', 'role': 'VE', 'joins': [
        {'provider': 'code.alarm.audible', 'purpose': 'Hear it from the next room.', 'function': 'Rings loudly.',
         'relation': 'The alarm reaches the cook.', 'observation': 'Loud.'}]})
    submit(run, project, doubled, tmp_path)
    joins = Store('timer').joins('stakeholder.cook.home').results
    assert sorted(join.provider_address for join in joins) == ['code.alarm.audible', 'code.timer.kitchen']


@pytest.mark.req('BASE-039')
@pytest.mark.req('CLI-028')
@pytest.mark.req('MCP-009')
def test_status_carries_the_notice_until_an_intake_is_stored(run, project, tmp_path):
    out = run(cwd=project).stdout.splitlines()
    assert 'Intake: none yet' in out and '  ' + NOTICE in out
    assert run('intake', 'status', cwd=project).stdout.startswith('No intake')
    report = json.loads(submit(run, project, FIXTURE, tmp_path).stdout)
    out = run(cwd=project).stdout.splitlines()
    assert 'Intake: complete' in out and not any(NOTICE in line for line in out)
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
    run('set', f'--intake-file', str(other), cwd=project)
    out = run('intake', 'prompt', cwd=project).stdout
    assert out.startswith('<process><target type="path" value=') and 'timer</process>' in out
