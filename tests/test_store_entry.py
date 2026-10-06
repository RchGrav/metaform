"""The map's entry, roles indexed for it, and work records: STORE-009, STORE-025 `roots`, STORE-042."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from storekit import dump, knowledge, plans, record_intake, small_map, store_file

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'intake_timer.json').read_text(encoding='utf-8'))


@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-025')
def test_the_entry_is_the_ve_and_de_with_their_joins_and_every_root_element(home, store, traced):
    small_map(store)
    tables = dump(store_file(home, store))
    assert 'element_roles' not in tables
    # The tick loop a join holds is an element as any other, Rich's shape, 2026-10-04.
    assert sorted(row[3] for row in tables['current_elements']) == ['CQU', 'DE', 'SE', 'SE']
    traced.clear()
    roots = store.roots()
    lines = [line for _, plan in plans(home, store, traced) for line in plan]
    assert any('current_elements_by_role' in line for line in lines)
    entry = {item.element.address: [[each.address for each in join.elements] for join in item.joins]
             for item in roots.entry}
    assert entry == {'stakeholder.cook.home': [['code.timer.kitchen', 'code.loop.tick']],
                     'code.timer.kitchen': [['code.alarm.audible']]}
    assert sorted((element.address, element.role, element.short_name) for element in roots.elements) == [
        ('code.alarm.audible', 'SE', 'audible alarm'), ('code.loop.tick', 'SE', 'tick loop'),
        ('code.timer.kitchen', 'DE', 'kitchen timer'), ('stakeholder.cook.home', 'CQU', 'home cook')]


@pytest.mark.req('STORE-025')
@pytest.mark.req('BASE-038')
def test_map_roots_and_where_with_no_address_return_the_entry(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    small_map(Store('proj'))
    roots = json.loads(run('map', 'roots', '--json', cwd=folder).stdout)
    assert {item['element']['address'] for item in roots['entry']} == {'stakeholder.cook.home', 'code.timer.kitchen'}
    assert json.loads(run('map', 'where', '', '--json', cwd=folder).stdout) == roots


@pytest.mark.req('STORE-042')
@pytest.mark.req('MAP-046')
def test_a_work_record_is_its_own_row_apart_from_the_map_and_reads_back_on_its_object(run, home, tmp_path, traced):
    from metaform.data import Node, export_document
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    record_intake(run, folder, copy.deepcopy(FIXTURE)['elements'])
    store = Store('proj')
    alarm = store.element('code.alarm.audible')
    join = store.joins('code.timer.kitchen').results[0]
    before = dump(store_file(home, store))
    missing = store.add_work(Node('element', 'code.alarm.audible'), 'missing', note='the pin is never released',
                         task='release the pin after stop')
    broken = store.add_work(Node('join', join.join_id), 'broken', task='wire the tone', held=True)
    assert (missing.condition, missing.note, missing.task, missing.held, missing.reviewed, missing.done, missing.resolution) == (
        'missing', 'the pin is never released', 'release the pin after stop', False, False, None, None)
    assert (missing.kind, missing.id, missing.address) == ('element', alarm.element_id, 'code.alarm.audible')
    assert (broken.receiver_address, broken.provider_address, broken.held) == ('code.timer.kitchen', 'code.alarm.audible',
                                                                               True)
    after = dump(store_file(home, store))
    assert len(after['work']) == 2
    assert {name: rows for name, rows in after.items() if name != 'work'} == {name: rows for name, rows in before.items()
                                                                              if name != 'work'}, 'the map changed'
    listed = json.loads(run('map', 'work', 'condition=broken', '--json', cwd=folder).stdout)['results']
    assert [(row['kind'], row['receiver_address'], row['provider_address'], row['condition'])
            for row in listed] == [('join', 'code.timer.kitchen', 'code.alarm.audible', 'broken')]
    assert json.loads(run('map', 'work', f'id={listed[0]["work_id"]}', '--json', cwd=folder).stdout)['task'] == (
        'wire the tone')  # a list row leaves its task out, MAP-049
    element = json.loads(run('map', 'element', 'code.alarm.audible', '--json', cwd=folder).stdout)
    assert element['open_work'] == ['missing'] and 'flag' not in element
    assert store.joins('code.timer.kitchen').results[0].open_work == ('broken',)
    assert store.element('code.timer.kitchen').open_work == ()
    traced.clear()
    store.work(condition='missing')
    store.work(node=Node('element', alarm.element_id))
    store.work(open=True)
    lines = [line for _, plan in plans(home, store, traced) for line in plan]
    for index in ('work_by_condition', 'work_by_target', 'work_by_done'):
        assert any(index in line for line in lines), index
    changed = store.edit_work(missing.work_id, {'reviewed': True, 'task': 'release the pin, then test it'})
    assert (changed.reviewed, changed.task, changed.note) == (True, 'release the pin, then test it',
                                                              'the pin is never released')
    done = store.finish_work(missing.work_id, 'released in alarm.c')
    assert done.done is not None and done.resolution == 'released in alarm.c' and done.condition == 'missing'
    assert store.element('code.alarm.audible').open_work == ()
    assert [row.work_id for row in store.work(open=False).results] == [missing.work_id]
    assert [row.work_id for row in store.work(open=True).results] == [broken.work_id]
    assert len(dump(store_file(home, store))['work']) == 2
    again = store.finish_work(missing.work_id, 'a second resolution')
    assert again.resolution == 'released in alarm.c' and [notice.where for notice in again.notices] == ['work_id']
    document = export_document(['proj'])['projects'][0]['metaforms'][0]
    assert sorted(row['condition'] for row in document['work']) == ['broken', 'missing']


@pytest.mark.req('STORE-042')
@pytest.mark.req('BASE-044')
def test_a_work_record_that_does_not_fit_is_stored_as_given_with_a_notice(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    small_map(store)
    sideways = store.add_work(Node('element', 'code.alarm.audible'), 'sideways', note={'pin': 4})
    assert sideways.condition == 'sideways' and sideways.note == '{"pin": 4}'
    assert sorted(notice.where for notice in sideways.notices) == ['condition', 'note']
    nowhere = store.add_work(Node('element', 'code.nowhere'), 'missing', task='build it')
    assert (nowhere.kind, nowhere.id, nowhere.address) == ('element', 'code.nowhere', None)
    assert [notice.where for notice in nowhere.notices] == ['node']
    assert store.element('code.alarm.audible').open_work == ('sideways',)
    assert sorted(row.condition for row in store.work().results) == ['missing', 'sideways']
    edited = store.edit_work(nowhere.work_id, {'task': 'decide it', 'color': 'red'})
    assert edited.task == 'decide it' and [notice.where for notice in edited.notices] == ['color']
    assert json.loads(run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=exclude',
                          'note=old probe', '--json', cwd=folder).stdout)['condition'] == 'exclude'
    assert [row['condition'] for row in json.loads(run('map', 'work', 'node=element:code.alarm.audible', '--json',
                                                       cwd=folder).stdout)['results']] == ['sideways', 'exclude']


@pytest.mark.req('STORE-042')
@pytest.mark.req('BASE-044')
def test_a_work_record_without_a_condition_is_stored_as_empty_text_with_a_notice(store):
    from metaform.data import Node
    small_map(store)
    unsaid = store.add_work(Node('element', 'code.alarm.audible'), None, task='say what it is')
    assert (unsaid.condition, unsaid.task) == ('', 'say what it is')
    assert [(notice.where, notice.message) for notice in unsaid.notices] == [
        ('condition', 'condition is missing; stored empty.')]
    assert [row.condition for row in store.work().results] == ['']
    cleared = store.edit_work(unsaid.work_id, {'condition': None})
    assert cleared.condition == '' and [notice.where for notice in cleared.notices] == ['condition']


@pytest.mark.req('STORE-042')
@pytest.mark.req('STORE-009')
def test_a_work_record_follows_its_element_through_removal_and_recording_again(store):
    """A work record has no layer: it is on the object's identity, which its address gives back, STORE-009."""
    layer = knowledge(store, 'again')
    first = store.add_element(layer.name, 'code.engine')
    record = store.add_work(Node('element', 'code.engine'), 'missing', task='build it')
    assert store.element('code.engine', raw=True).open_work == ('missing',)
    store.remove(first.element_id)
    assert store.element('code.engine', raw=True) is None
    assert [(row.work_id, row.address) for row in store.work(open=True).results] == [(record.work_id, None)]
    again = store.add_element(layer.name, 'code.engine')
    assert again.element_id == first.element_id
    store.finish(layer.name)
    assert store.element('code.engine').open_work == ('missing',)
    assert [(row.work_id, row.address) for row in store.work(open=True).results] == [(record.work_id, 'code.engine')]


@pytest.mark.req('STORE-042')
@pytest.mark.req('STORE-032')
def test_discarding_a_layer_leaves_the_work_records_of_its_objects_in_place(home, store):
    small_map(store)
    layer = knowledge(store, 'draft')
    store.add_element(layer.name, 'code.draft.probe')
    join = store.add_join(layer.name, 'code.timer.kitchen', 'code.draft.probe', purpose='p', ef='f')
    on_element = store.add_work(Node('element', 'code.draft.probe'), 'exclude', note='old probe')
    on_join = store.add_work(Node('join', join.join_id), 'broken')
    on_intake = store.add_work(Node('element', 'code.alarm.audible'), 'missing')
    before = dump(store_file(home, store))
    store.discard(layer.name)
    assert dump(store_file(home, store))['work'] == before['work']
    assert [found.name for found in store.layers().results] == ['intake-1']
    listed = {row.work_id: (row.kind, row.id, row.address, row.condition) for row in store.work().results}
    assert listed == {on_element.work_id: ('element', on_element.id, None, 'exclude'),
                      on_join.work_id: ('join', join.join_id, None, 'broken'),
                      on_intake.work_id: ('element', on_intake.id, 'code.alarm.audible', 'missing')}
    assert store.element('code.alarm.audible').open_work == ('missing',)
