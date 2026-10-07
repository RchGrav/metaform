"""Export and import carry a project whole, by unique id, with nothing lost and no conflict case."""
from __future__ import annotations

import json

import pytest
from storekit import dump, knowledge, memory, small_map, store_file

from metaform import home as metaform_home
from metaform.data import Node, Store, StoreError, export_document, import_document

pytestmark = pytest.mark.kind('fixture')


def filled(store):
    _, outer, inner = small_map(store)
    notes = knowledge(store, 'notes', tags=('practices',))
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), {'imperative': 'keep it small'},
                   extra={'confidence': 'high'}, refs=[('path', 'src/timer.c')])
    store.add_property(notes.name, 'code.timer.kitchen', 'C')
    store.add_join(notes.name, 'code.alarm.audible', 'code.timer.kitchen', purpose='stop', ef='signals')
    store.finish(notes.name)
    store.mask('code.alarm', notes.name)
    notes_memory = memory(store)
    store.add_item(notes_memory.name, Node('join', inner.id), 'quiet tone')
    store.refine(inner.id, {'ef': 'Plays a loud tone.'}, reason='louder', evidence='bench')
    store.refine(outer.id, {'elements': ['code.timer.kitchen']}, reason='the tick is the timer\'s own')
    store.refine(outer.id, {'purpose': 'Serve each dish on time.'}, reason='sharper')
    return outer, inner


def move_home(monkeypatch, tmp_path, name):
    target = tmp_path / name
    monkeypatch.setenv('METAFORM_HOME', str(target))
    return target


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-007')
@pytest.mark.req('STORE-021')
def test_export_import_export_gives_the_same_document(home, store, monkeypatch, tmp_path):
    outer, _ = filled(store)
    versions = [(version.op, version.fields['purpose'], version.fields['elements'])
                for version in store.history(outer.id).results]
    kitchen = store.element('code.timer.kitchen').id
    first = export_document(['proj'])
    move_home(monkeypatch, tmp_path, 'other-home')
    report = import_document(json.loads(json.dumps(first)))
    assert report['layers_added'] == 3 and report['layers_skipped'] == 0
    second = export_document(['proj'])
    assert second == first
    moved = Store('proj')
    assert moved.element('code.timer.kitchen').id == kitchen
    item = moved.layer_items('notes', Node('element', 'code.timer.kitchen')).results[0]
    assert item.extra == {'confidence': 'high'}
    assert [(version.op, version.fields['purpose'], version.fields['elements'])
            for version in moved.history(outer.id).results] == versions  # every version, with the elements it holds
    assert versions[0][2] == ['code.timer.kitchen', 'code.loop.tick'] and versions[1][2] == ['code.timer.kitchen']
    assert len(versions) == 3
    assert moved.joins('stakeholder.cook.home').results[0].purpose == 'Serve each dish on time.'  # the newest is current


@pytest.mark.req('STORE-027')
@pytest.mark.req('MAP-020')
def test_an_exported_join_carries_no_relation_and_no_observation_and_a_document_with_them_is_refused(home, store):
    """Rich, 2026-10-02: relation and observation are removed from export and import with the store."""
    filled(store)
    document = export_document(['proj'])
    rows = document['projects'][0]['metaforms'][0]['joins']
    assert rows and all('relation' not in row and 'observation' not in row and 'ef' in row for row in rows)
    rows[0]['relation'] = 'r'
    with pytest.raises(StoreError, match='relation: not a field here'):
        import_document(json.loads(json.dumps(document)))


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-042')
def test_work_records_are_carried_by_export_and_read_back_on_their_objects_after_import(home, store, monkeypatch,
                                                                                         tmp_path):
    _, inner = filled(store)
    tick = store.element('code.loop.tick')
    missing = store.add_work(Node('element', 'code.alarm.audible'), 'missing', note='the pin is never released',
                         task='release the pin', held=True)
    broken = store.add_work(Node('join', inner.id), 'broken', task='wire the tone', reviewed=True)
    on_tick = store.add_work(Node('element', tick.id), 'exclude')
    done = store.finish_work(store.add_work(Node('element', 'code.timer.kitchen'), 'missing').id, 'built it')
    first = export_document(['proj'])
    assert len(first['projects'][0]['metaforms'][0]['work']) == 4
    move_home(monkeypatch, tmp_path, 'other-home')
    import_document(json.loads(json.dumps(first)))
    assert export_document(['proj']) == first
    moved = Store('proj')
    assert moved.element('code.alarm.audible').open_work == ('missing',)
    assert moved.element('code.timer.kitchen').open_work == ()
    assert [join.open_work for join in moved.joins('code.timer.kitchen').results] == [('broken',)]
    assert moved.element('code.loop.tick').open_work == ('exclude',)
    records = {row.id: row for row in moved.work().results}
    assert set(records) == {missing.id, broken.id, on_tick.id, done.id}
    assert (records[missing.id].address, records[missing.id].note, records[missing.id].task,
            records[missing.id].held, records[missing.id].created) == (
        'code.alarm.audible', 'the pin is never released', 'release the pin', True, missing.created)
    assert (records[broken.id].receiver_address, records[broken.id].provider_address,
            records[broken.id].reviewed) == ('code.timer.kitchen', 'code.alarm.audible', True)
    assert records[on_tick.id].address == 'code.loop.tick'
    assert (records[done.id].done, records[done.id].resolution) == (done.done, 'built it')
    assert [row.id for row in moved.work(open=False).results] == [done.id]


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-034')
def test_moved_joins_and_the_elements_joins_hold_come_through_export_and_import_where_they_were(home, store,
                                                                                                monkeypatch, tmp_path):
    _, outer, inner = small_map(store)
    store.refine(inner.id, {'receiver': 'stakeholder.cook.home'}, reason='the cook hears it')
    notes = knowledge(store, 'notes')
    for address in ('code.a', 'code.p', 'code.q'):
        store.add_element(notes.name, address)
    early = store.add_join(notes.name, 'code.a', 'code.q', purpose='q', ef='g')
    later = store.add_join(notes.name, 'code.a', 'code.p', purpose='p', ef='f')
    store.edit(later.id, {'elements': ['code.p', 'code.q']})
    store.finish(notes.name)
    first = export_document(['proj'])
    move_home(monkeypatch, tmp_path, 'other-home')
    import_document(json.loads(json.dumps(first)))
    assert export_document(['proj']) == first
    moved = Store('proj')
    assert inner.id in [join.id for join in moved.joins('stakeholder.cook.home').results]
    held = {join.id: [each.address for each in join.elements] for join in moved.joins('code.a').results}
    assert held == {early.id: ['code.q'], later.id: ['code.p', 'code.q']}
    cook = {join.id: join for join in moved.joins('stakeholder.cook.home').results}[outer.id]
    assert [each.address for each in cook.elements] == ['code.timer.kitchen', 'code.loop.tick']


@pytest.mark.req('STORE-027')
def test_importing_what_already_exists_changes_nothing(home, store):
    filled(store)
    document = export_document(['proj'])
    for row in document['projects'][0]['metaforms'][0]['items']:
        row['value'] = json.dumps('rewritten elsewhere')
    before = dump(store_file(home, store))
    report = import_document(document)
    assert report['layers_added'] == 0 and report['layers_skipped'] == 3 and report['metaforms_added'] == 0
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
    metaform['metaform']['base_id'] = target.active_base().id
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
    assert {'kind': 'element', 'id': store.element('code.timer.kitchen').id} in metaform['requires']
    kitchen = store.element('code.timer.kitchen').id
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


@pytest.mark.req('STORE-027')
@pytest.mark.req('STORE-042')
def test_a_tickets_links_and_steps_and_the_messages_at_nodes_are_carried_by_export_and_import(home, store, monkeypatch,
                                                                                               tmp_path):
    """An intake of Metaform found that export left out messages and work steps, Rich 2026-10-01: if you see issues
    you can fix them; we need a rock solid data store. A ticket's reference links and filed steps, and the questions
    and messages left at nodes, come through export and import, and importing again adds nothing twice."""
    filled(store)
    ticket = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone',
                            links=[Node('element', 'code.timer.kitchen')])
    store.take_work(ticket.id, steps=3, by='codex')
    store.step_work(ticket.id, 'Found the gain.')
    store.step_work(ticket.id, 'Lowered it.')
    asked = store.ask(Node('element', 'code.alarm.audible'), 'How quiet?', suggestions=['half', 'a quarter'])
    store.tell(Node('element', 'code.timer.kitchen'), 'The tick drifts under load.')
    first = export_document(['proj'])
    move_home(monkeypatch, tmp_path, 'other-home')
    import_document(json.loads(json.dumps(first)))
    assert export_document(['proj']) == first
    import_document(json.loads(json.dumps(first)))                    # again: nothing twice
    assert export_document(['proj']) == first
    moved = Store('proj')
    carried = next(record for record in moved.work(limit=0).results if record.id == ticket.id)
    assert [link.address for link in carried.links] == ['code.timer.kitchen']
    assert ([step.said for step in carried.said], carried.steps_done, carried.taken_by) == (
        ['Found the gain.', 'Lowered it.'], 2, 'codex')
    kept = {message.id: message for message in moved.messages(limit=0).results}
    assert asked.id in kept and len(kept) == 2
