"""Export and import carry a project whole, by unique id, with nothing lost and no conflict case."""
from __future__ import annotations

import json

import pytest

from metaform import home as metaform_home
from metaform.data import Node, Store, StoreError, export_document, import_document
from storekit import correction, dump, knowledge, memory, small_map, store_file

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
    move_home(monkeypatch, tmp_path, 'empty-home')
    with pytest.raises(StoreError) as refused:
        import_document(document)
    assert refused.value.next_step


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
