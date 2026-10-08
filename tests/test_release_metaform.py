"""The released self-map is a portable current functional map, BASE-048 and LAYER-026."""
from __future__ import annotations

import copy
import json
import zipfile
from importlib import resources

import pytest
from storekit import knowledge, small_map

from metaform import build
from metaform.data import Node, Store, export_document, import_document
from scripts.release_metaform import snapshot

pytestmark = pytest.mark.kind('fixture')


@pytest.mark.req('BASE-048')
@pytest.mark.req('LAYER-026')
def test_snapshot_keeps_current_encounters_and_identities_without_working_history(store, home, tmp_path,
                                                                                monkeypatch):
    layer, outer, inner = small_map(store)
    store.refine(outer.id, {'purpose': 'Serve dinner on time.', 'elements': ['code.timer.kitchen']},
                 reason='the timer owns the tick', evidence='design review')
    store.refine(inner.id, {'ef': 'Sounds until acknowledged.'}, reason='attention is needed')
    store.refine(store.element('code.loop.tick').id, {}, remove=True, reason='part of the timer')
    notes = knowledge(store, 'notes')
    store.add_element(notes.name, 'document.review')
    store.add_join(notes.name, 'code.timer.kitchen', 'document.review', purpose='Read the review.', ef='records it')
    store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'private review')
    store.finish(notes.name)
    store.add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='private task')
    store.ask(Node('element', 'code.timer.kitchen'), 'private question')
    original = export_document(['proj'])
    before = copy.deepcopy(original)
    document = snapshot(original)
    assert original == before
    held = document['projects'][0]['bases'][0]
    assert held['base']['id'] != original['projects'][0]['bases'][0]['base']['id']
    layers = [op for op in held['ops'] if op['kind'] == 'layer' and op['op'] == 'add']
    assert len(layers) == 1 and layers[0]['id'] != layer.id
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'other-home'))
    result = import_document(document)
    assert result['notices'] == []
    moved = Store('proj')
    assert moved.element('code.loop.tick') is None
    assert moved.element('document.review') is None
    current = moved.joins('stakeholder.cook.home').results[0]
    assert current.id == outer.id and current.purpose == 'Serve dinner on time.'
    assert [element.address for element in current.elements] == ['code.timer.kitchen']
    alarm = moved.joins('code.timer.kitchen').results[0]
    assert alarm.id == inner.id and alarm.ef == 'Sounds until acknowledged.'
    for thing in (outer.id, inner.id, moved.element('code.timer.kitchen').id):
        versions = moved.history(thing).results
        assert len(versions) == 1 and versions[0].op == 'add'
        assert versions[0].reason is None and versions[0].evidence is None
    assert not moved.work().results and not moved.messages().results
    assert [op for op in export_document(['proj'])['projects'][0]['bases'][0]['ops'] if op['kind'] == 'item'] == []


@pytest.mark.req('BASE-048')
@pytest.mark.req('STORE-001')
@pytest.mark.req('STORE-027')
def test_bundled_map_imports_explicitly_into_a_fork_and_reimport_is_idle(run, home, tmp_path):
    data = resources.files('metaform').joinpath('resources/metaform.json').read_bytes()
    file = tmp_path / 'release.json'
    file.write_bytes(data)
    folder = tmp_path / 'fork'
    folder.mkdir()
    run('add', 'project', 'fork', str(folder))
    assert not Store('fork').roots().elements
    original = Store('fork')
    small_map(original)
    active = original.active_base()
    before_import = export_document(['fork'])['projects'][0]['bases'][0]
    run('import', str(file), 'fork')
    assert Store('fork').active_base() == active
    assert export_document(['fork'], metaform=active.name)['projects'][0]['bases'][0] == before_import
    run('map', 'activate', 'metaform-release', cwd=folder)
    read = json.loads(run('map', 'where', 'code.tool.context_engineering', '--json', cwd=folder).stdout)
    assert read['element']['role'] == 'AUE'
    assert read['receives'] and read['provides']
    assert not Store('fork').work().results
    before = export_document(['fork'])
    run('import', str(file), 'fork')
    assert export_document(['fork']) == before
    assert list(folder.iterdir()) == []


@pytest.mark.req('BASE-048')
@pytest.mark.req('BASE-041')
def test_wheel_carries_the_same_snapshot_with_every_module_disabled(home, monkeypatch):
    from metaform import loader
    for found in loader.discover():
        loader.set_enabled(found.id, False)
    monkeypatch.setattr(build, '_carry', lambda *_: ({}, []))
    wheel, _ = build.build()
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read('metaform/resources/metaform.json') == resources.files('metaform').joinpath(
            'resources/metaform.json').read_bytes()
        assert not any(name.startswith('metaform/modules/map/') for name in archive.namelist())


@pytest.mark.req('LAYER-026')
@pytest.mark.req('STORE-041')
def test_collapse_writes_a_new_active_metaform_with_the_same_ids_and_keeps_the_old_whole(store, home):
    _layer, outer, inner = small_map(store)
    store.refine(outer.id, {'purpose': 'Serve dinner on time.',
                                'elements': ['code.timer.kitchen', 'code.alarm.audible']},
                 reason='the timer owns the tick')
    tick = store.element('code.loop.tick').id
    store.refine(tick, {}, remove=True, reason='part of the timer')
    old = store.active_base()
    before = export_document(['proj'], metaform=old.name)['projects'][0]['bases']
    made = store.collapse('fresh')
    assert made.active and made.name == 'fresh' and made.notices
    fresh = Store('proj')
    assert fresh.active_base().id == made.id != old.id
    assert fresh.element('code.loop.tick') is None
    current = fresh.joins('stakeholder.cook.home').results[0]
    assert current.id == outer.id and current.purpose == 'Serve dinner on time.'
    assert [held.address for held in current.elements] == ['code.timer.kitchen', 'code.alarm.audible']
    source = Store('proj', base=old.id)
    assert current.elements == source.joins('stakeholder.cook.home').results[0].elements
    assert all(fresh.element(held.address).id == held.element_id for held in current.elements)
    assert len(fresh.layers().results) == 1 and fresh.layers().results[0].ready is not None
    for thing in (outer.id, inner.id, fresh.element('code.timer.kitchen').id):
        assert [version.reason for version in fresh.history(thing).results] == [None]
    assert export_document(['proj'], metaform=old.name)['projects'][0]['bases'] == before
    assert fresh.collapse('fresh').name == 'fresh-2'


@pytest.mark.req('LAYER-026')
def test_collapse_refuses_an_intake_still_building(store, home):
    from storekit import intake

    from metaform.errors import StoreError
    intake(store, ready=False)
    names = [item.name for item in store.bases().results]
    with pytest.raises(StoreError, match='still building'):
        store.collapse('fresh')
    assert [item.name for item in store.bases().results] == names


@pytest.mark.req('LAYER-026')
@pytest.mark.req('STORE-006')
@pytest.mark.parametrize('failure', ['import', 'activation'])
def test_collapse_failure_keeps_the_source_active_and_leaves_no_partial_metaform(store, home, monkeypatch, failure):
    from metaform import home as metaform_home
    from metaform.data import exchange
    from metaform.errors import StoreError

    small_map(store)
    active = store.active_base()
    before = export_document(['proj'])
    files = set(home.rglob('*.sqlite3'))
    original_import = exchange.import_document

    def importing(*args, **kwargs):
        assert store.active_base() == active
        original_import(*args, **kwargs)
        assert store.active_base() == active
        if failure == 'import':
            raise StoreError('Collapse failed.', 'retry')

    def fail_activation(*args, **kwargs):
        assert store.active_base() == active
        raise StoreError('Collapse failed.', 'retry')

    monkeypatch.setattr(exchange, 'import_document', importing)
    if failure == 'activation':
        monkeypatch.setattr(metaform_home, 'activate_base', fail_activation)
    with pytest.raises(StoreError, match='Collapse failed'):
        store.collapse('fresh')
    assert export_document(['proj']) == before
    assert set(home.rglob('*.sqlite3')) == files
