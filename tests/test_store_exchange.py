"""Export and import carry a project whole, by unique id, with nothing lost and no conflict case."""
from __future__ import annotations

import json

import pytest
from storekit import correction, dump, knowledge, memory, record_intake, small_map, store_file

from metaform import home as metaform_home
from metaform.data import Node, Store, StoreError, export_document, import_document

pytestmark = pytest.mark.kind('fixture')


def filled(store):
    _, outer, inner = small_map(store)
    notes = knowledge(store, 'notes', tags=('practices',))
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), {'imperative': 'keep it small'},
                   extra={'confidence': 'high'}, refs=[('path', 'src/timer.c')])
    store.add_property(notes.name, 'code.timer.kitchen', 'C')
    store.add_join(notes.name, 'code.alarm.audible', 'code.timer.kitchen', purpose='stop', function='signals',
                   relation='r', observation='o', extra={'latency_budget': '5 ms'})
    store.finish(notes.name)
    store.mask('code.alarm', notes.name)
    notes_memory = memory(store)
    store.add_item(notes_memory.name, Node('join', inner.join_id), 'quiet tone')
    fix = correction(store, 'fix-1')
    store.correct(fix.name, inner.join_id, {'function': 'Plays a loud tone.'}, reason='louder', evidence='bench')
    store.finish(fix.name)
    return outer, inner


def move_home(monkeypatch, tmp_path, name):
    target = tmp_path / name
    monkeypatch.setenv('METAFORM_HOME', str(target))
    return target


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-007')
@pytest.mark.req('STORE-021')
def test_export_import_export_gives_the_same_document(home, store, monkeypatch, tmp_path):
    filled(store)
    kitchen = store.element('code.timer.kitchen').element_id
    first = export_document(['proj'])
    move_home(monkeypatch, tmp_path, 'other-home')
    report = import_document(json.loads(json.dumps(first)))
    assert report['layers_added'] >= 4 and report['layers_skipped'] == 0
    second = export_document(['proj'])
    assert second == first
    moved = Store('proj')
    assert moved.element('code.timer.kitchen').element_id == kitchen
    join = next(join for join in moved.joins('code.alarm.audible', raw=True).results if join.layer == 'notes')
    assert join.extra == {'latency_budget': '5 ms'}
    assert [layer.name for layer in moved.stack().results] == ['fix-1']


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-042')
def test_work_records_are_carried_by_export_and_read_back_on_their_objects_after_import(home, store, monkeypatch,
                                                                                         tmp_path):
    outer, inner = filled(store)
    tick = store.subtypes(outer.join_id).results[0]
    missing = store.add_work(Node('element', 'code.alarm.audible'), 'missing', note='the pin is never released',
                         task='release the pin', held=True)
    broken = store.add_work(Node('join', inner.join_id), 'broken', task='wire the tone', reviewed=True)
    on_tick = store.add_work(Node('join', tick.join_id), 'exclude')
    done = store.finish_work(store.add_work(Node('element', 'code.timer.kitchen'), 'missing').work_id, 'built it')
    first = export_document(['proj'])
    assert len(first['projects'][0]['metaforms'][0]['work']) == 4
    move_home(monkeypatch, tmp_path, 'other-home')
    import_document(json.loads(json.dumps(first)))
    assert export_document(['proj']) == first
    moved = Store('proj')
    assert moved.element('code.alarm.audible').open_work == ('missing',)
    assert moved.element('code.timer.kitchen').open_work == ()
    assert [join.open_work for join in moved.joins('code.timer.kitchen').results] == [('broken',)]
    assert moved.subtypes(outer.join_id).results[0].open_work == ('exclude',)
    records = {row.work_id: row for row in moved.work().results}
    assert set(records) == {missing.work_id, broken.work_id, on_tick.work_id, done.work_id}
    assert (records[missing.work_id].address, records[missing.work_id].note, records[missing.work_id].task,
            records[missing.work_id].held, records[missing.work_id].created) == (
        'code.alarm.audible', 'the pin is never released', 'release the pin', True, missing.created)
    assert (records[broken.work_id].receiver_address, records[broken.work_id].provider_address,
            records[broken.work_id].reviewed) == ('code.timer.kitchen', 'code.alarm.audible', True)
    assert (records[on_tick.work_id].receiver_address, records[on_tick.work_id].provider_address) == (
        'stakeholder.cook.home', 'code.loop.tick')
    assert (records[done.work_id].done, records[done.work_id].resolution) == (done.done, 'built it')
    assert [row.work_id for row in moved.work(open=False).results] == [done.work_id]


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-011')
@pytest.mark.req('STORE-034')
def test_moved_joins_and_subtype_joins_come_through_export_and_import_where_they_were(home, store, monkeypatch,
                                                                                       tmp_path):
    _, outer, inner = small_map(store)
    fix = correction(store, 'fix-1')
    store.correct(fix.name, inner.join_id, {'receiver': 'stakeholder.cook.home'}, reason='the cook hears it')
    store.finish(fix.name)
    notes = knowledge(store, 'notes')
    for address in ('code.a', 'code.p', 'code.q'):
        store.add_element(notes.name, address)
    early = store.add_join(notes.name, 'code.a', 'code.q', purpose='q', function='g', relation='r', observation='o')
    later = store.add_join(notes.name, 'code.a', 'code.p', purpose='p', function='f', relation='r', observation='o')
    store.edit(early.join_id, {'parent': later.join_id})
    store.finish(notes.name)
    first = export_document(['proj'])
    move_home(monkeypatch, tmp_path, 'other-home')
    import_document(json.loads(json.dumps(first)))
    assert export_document(['proj']) == first
    moved = Store('proj')
    assert inner.join_id in [join.join_id for join in moved.joins('stakeholder.cook.home').results]
    assert [sub.join_id for sub in moved.subtypes(outer.join_id).results] == [
        store.subtypes(outer.join_id).results[0].join_id]
    assert [sub.join_id for sub in moved.subtypes(later.join_id).results] == [early.join_id]
    assert [join.join_id for join in moved.joins('code.a').results] == [later.join_id]


@pytest.mark.req('STORE-027')
def test_importing_what_already_exists_changes_nothing(home, store):
    filled(store)
    document = export_document(['proj'])
    for row in document['projects'][0]['metaforms'][0]['items']:
        row['value'] = json.dumps('rewritten elsewhere')
    before = dump(store_file(home, store))
    report = import_document(document)
    assert report['layers_added'] == 0 and report['layers_skipped'] >= 4 and report['metaforms_added'] == 0
    assert dump(store_file(home, store)) == before


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-006')
def test_an_import_that_fails_partway_leaves_the_store_unchanged(home, store, monkeypatch, tmp_path):
    filled(store)
    document = export_document(['proj'])
    move_home(monkeypatch, tmp_path, 'other-home')
    folder = tmp_path / 'proj'
    metaform_home.add_project('proj', folder)
    target = Store('proj')
    layer = knowledge(target, 'already-here')
    target.add_element(layer.name, 'code.here')
    snapshot = dump(store_file(tmp_path / 'other-home', target))
    broken = json.loads(json.dumps(document))
    metaform = broken['projects'][0]['metaforms'][0]
    metaform['metaform']['metaform_id'] = target.active_metaform().metaform_id
    notes_id = next(layer['layer_id'] for layer in metaform['layers'] if layer['name'] == 'notes')
    metaform['refs'].append({'owner': 'join', 'owner_id': '0' * 32, 'owner_layer_id': notes_id,
                             'position': 0, 'key': 'path', 'value': 'nowhere'})
    with pytest.raises(StoreError):
        import_document(broken, 'proj')
    assert dump(store_file(tmp_path / 'other-home', target)) == snapshot


@pytest.mark.req('STORE-027')
def test_a_layer_limited_export_names_what_it_requires(home, store, monkeypatch, tmp_path):
    filled(store)
    document = export_document(['proj'], layers=['notes'])
    metaform = document['projects'][0]['metaforms'][0]
    assert {layer['name'] for layer in metaform['layers']} == {'notes'}
    assert {'kind': 'element', 'id': store.element('code.timer.kitchen').element_id} in metaform['requires']
    kitchen = store.element('code.timer.kitchen').element_id
    move_home(monkeypatch, tmp_path, 'empty-home')
    report = import_document(document)
    assert report['layers_added'] == 1
    named = ' '.join(notice['message'] for notice in report['notices'])
    assert kitchen in named and 'metaform import' in named


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-023')
@pytest.mark.req('STORE-026')
def test_an_import_document_is_checked_whole_before_any_write_and_its_keys_never_reach_sql(
        home, store, monkeypatch, tmp_path, traced):
    filled(store)
    document = json.loads(json.dumps(export_document(['proj'])))
    other = move_home(monkeypatch, tmp_path, 'other-home')
    entry = document['projects'][0]
    entry['project']['owner'] = 'someone'
    metaform = entry['metaforms'][0]
    metaform['items'][0]['value) SELECT * FROM items; --'] = 'x'
    del metaform['joins'][0]['purpose']
    metaform['elements'][0]['address'] = {'not': 'text'}
    traced.clear()
    with pytest.raises(StoreError) as refused:
        import_document(document)
    message = str(refused.value)
    for path in ('projects[0].project.owner', 'projects[0].metaforms[0].items[0]',
                 'projects[0].metaforms[0].joins[0].purpose', 'projects[0].metaforms[0].elements[0].address'):
        assert path in message
    assert refused.value.next_step and '\n' not in refused.value.next_step
    assert not any('SELECT * FROM items' in statement for statement in traced)
    assert not (other / 'metaform.sqlite3').exists() and not (other / 'projects').exists()


def wheel_home(home, label):
    return home / 'wheels' / label


def roots_of(run, folder):
    return run('map', 'roots', '--json', cwd=folder).stdout


ELEMENTS_MAIN = [{'namespace_address': 'code.timer.kitchen', 'name': 'kitchen timer', 'name_length': 2, 'role': 'DE'}]
ELEMENTS_WHEEL = [{'namespace_address': 'code.alarm.audible', 'name': 'audible alarm', 'name_length': 2, 'role': 'DE'}]


@pytest.mark.req('BASE-025')
@pytest.mark.req('STORE-030')
def test_a_wheels_data_is_pulled_in_as_its_own_metaforms_never_active_and_only_once(run, home, tmp_path):
    folder, other = tmp_path / 'proj', tmp_path / 'other'
    folder.mkdir()
    other.mkdir()
    run('add', 'project', 'proj', str(folder))
    record_intake(run, folder, ELEMENTS_MAIN, env={})
    before = roots_of(run, folder)
    wheel = {'METAFORM_HOME': str(wheel_home(home, 'metaform-9.9.9'))}
    run('add', 'project', 'proj', str(folder), env=wheel)
    record_intake(run, folder, ELEMENTS_WHEEL, env=wheel)
    run('add', 'project', 'other', str(other), env=wheel)
    record_intake(run, other, ELEMENTS_WHEEL, env=wheel)
    pulled = run('import', 'wheel=metaform-9.9.9').stdout
    assert 'metaforms added: two' in pulled
    rows = [line.split() for line in run('list', 'metaforms', 'proj').stdout.splitlines()]
    names = {row[0]: row for row in rows}
    assert set(names) == {'main', 'main-from-metaform-9.9.9'}
    assert 'active' in ' '.join(names['main']) and 'active' not in ' '.join(names['main-from-metaform-9.9.9'])
    assert roots_of(run, folder) == before
    assert [row.split()[0] for row in run('list', 'metaforms', 'other').stdout.splitlines()] == [
        'main-from-metaform-9.9.9']
    assert 'active' not in run('list', 'metaforms', 'other').stdout
    run('activate', 'metaform', 'main-from-metaform-9.9.9', 'proj')
    assert 'code.alarm.audible' in roots_of(run, folder) and 'code.timer.kitchen' not in roots_of(run, folder)
    run('activate', 'metaform', 'main', 'proj')
    stores = sorted((home / 'projects').rglob('store.sqlite3'))
    kept = [path.read_bytes() for path in stores]
    again = run('import', 'wheel=metaform-9.9.9').stdout
    assert 'metaforms added: no' in again and 'things added: no' in again
    assert sorted((home / 'projects').rglob('store.sqlite3')) == stores
    assert run('list', 'metaforms', 'proj').stdout.count('from-metaform') == 1
    assert wheel_home(home, 'metaform-9.9.9').is_dir() and [path.read_bytes() for path in stores] == kept


@pytest.mark.req('BASE-025')
def test_a_wheel_folder_that_is_not_there_names_the_folders_that_are(run, home):
    (wheel_home(home, 'metaform-1.0.0')).mkdir(parents=True)
    missing = run('import', 'wheel=metaform-8.8.8', ok=False)
    assert missing.returncode != 0 and 'metaform-8.8.8' in missing.stderr
    assert 'Next: metaform import wheel=metaform-1.0.0' in missing.stderr
