"""Promotion preserves a join while giving it an ordinary element, MAP-054."""
import dataclasses
import json
import sqlite3

import pytest
from storekit import dump, knowledge, ops, small_map, store_file

from metaform.data import Node, Store, StoreError, export_document, import_document, promotion
from metaform.data.session import open_store
from metaform.sqlite import SCHEMA_VERSION

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('MAP-054')]


def test_promotion_keeps_the_join_ends_history_and_attachments(store):
    layer, original, _ = small_map(store)
    notes = knowledge(store, 'promotion-notes')
    item = store.add_item(notes.name, Node('join', original.id), 'Keep the receiver purpose.')
    store.finish(notes.name)
    work = store.add_work(Node('join', original.id), 'enhancement', task='Improve this purpose.')
    question = store.ask(Node('join', original.id), 'Which delivery serves it?')
    before = store.history(original.id).to_dict()

    promoted = store.promote_join(original.id, 'code.countdown.delivery', name='countdown delivery',
                                  name_length=2, role='SE')
    element = store.element(promoted.element)
    assert element.name == 'countdown delivery' and element.role == 'SE'
    assert promoted.element == 'code.countdown.delivery'
    assert dataclasses.replace(promoted, element=None, open_work=()) == original
    history = store.history(original.id).to_dict()
    assert history['results'][:-1] == before['results']
    assert history['results'][-1]['fields']['element'] == element.address
    assert history['results'][-1]['op'] == 'change'
    target = Node('join', original.id)
    assert store.work(target).results[0].id == work.id
    assert store.messages(target).results[0].id == question.id
    assert store.node(target).layers[0].items[0].id == item.id
    assert store.join_ends(original.id) == (original.receiver_address, original.elements[0].address)

    outgoing = store.add_join(layer.name, element.address, 'code.alarm.audible', purpose='Signal expiry.')
    incoming = store.add_join(layer.name, 'code.timer.kitchen', element.address, purpose='Deliver expiry.')
    assert [one.id for one in store.joins(element.address).results] == [outgoing.id]
    assert [one.id for one in store.identity(element.address).results] == [incoming.id]
    assert outgoing.element is None and incoming.element is None
    store.refine(original.id, {'purpose': 'Serve a revised purpose.'}, reason='Clarify the receiver need.')
    assert store.joins(original.receiver_address).results[0].element == element.address


def test_promotion_survives_export_import_and_collapse(home, store, monkeypatch, tmp_path):
    _, original, _ = small_map(store)
    promoted = store.promote_join(original.id, 'code.delivery')
    document = export_document(['proj'])
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'imported-home'))
    import_document(json.loads(json.dumps(document)))
    assert export_document(['proj']) == document
    imported = Store('proj')
    old = imported.active_base()
    before = imported.history(original.id).to_dict()
    assert imported.joins(original.receiver_address).results[0] == promoted
    imported.collapse('promoted-map')
    current = imported.joins(original.receiver_address).results[0]
    assert current.id == original.id and current.element == 'code.delivery'
    assert imported.element(current.element).id == store.element(current.element).id
    assert imported.join_ends(current.id) == (original.receiver_address, original.elements[0].address)
    imported.activate_base(old.name)
    assert imported.history(original.id).to_dict() == before


def test_promotion_reuses_an_element_and_repeat_is_idempotent(home, store):
    layer, original, _ = small_map(store)
    existing = store.add_element(layer.name, 'code.delivery', name='existing delivery')
    result = store.promote_join(original.id, existing.address, name='another name')
    assert result.element == existing.address
    assert store.element(existing.address).name == existing.name
    assert any(notice.where == 'name' for notice in result.notices)
    before = dump(store_file(home, store))
    repeated = store.promote_join(original.id, existing.address)
    assert repeated.element == existing.address
    assert dump(store_file(home, store)) == before
    conflict = store.promote_join(original.id, 'code.other')
    assert conflict.notices and store.element('code.other', raw=True) is None
    assert dump(store_file(home, store)) == before


@pytest.mark.req('STORE-032')
def test_discard_keeps_an_element_another_layers_promoted_join_uses(store):
    _, original, _ = small_map(store)
    notes = knowledge(store, 'delivery-notes')
    existing = store.add_element(notes.name, 'code.delivery', name='delivery')
    store.finish(notes.name)
    store.promote_join(original.id, existing.address)
    outcome = store.discard(notes.name)
    retained = store.element(existing.address)
    assert retained is not None
    assert retained.id == existing.id and retained.name == existing.name
    assert retained.layer == original.layer and outcome.notices
    assert store.joins(original.receiver_address).results[0].element == retained.address


def test_unreadable_promotion_target_rolls_back(home, store):
    _, original, _ = small_map(store)
    before = dump(store_file(home, store))
    with pytest.raises(StoreError):
        store.promote_join(original.id, 42)
    assert dump(store_file(home, store)) == before
    invalid = store.promote_join(store.element('code.timer.kitchen').id, 'code.delivery')
    assert invalid.notices and dump(store_file(home, store)) == before


def test_failed_association_rolls_back_the_new_element(home, store, monkeypatch):
    _, original, _ = small_map(store)
    before = dump(store_file(home, store))

    def fail(*args, **kwargs):
        raise StoreError('The join version could not be written.', 'metaform help map promote')

    monkeypatch.setattr(promotion.layering, 'refine', fail)
    with pytest.raises(StoreError, match='could not be written'):
        store.promote_join(original.id, 'code.delivery')
    assert dump(store_file(home, store)) == before


def test_a_knowledge_join_can_promote_without_changing_its_layer_rules(store):
    layer = knowledge(store, 'delivery')
    original = store.add_join(layer.name, 'code.receiver', 'code.provider', purpose='Receive delivery.')
    store.finish(layer.name)
    promoted = store.promote_join(original.id, 'code.delivery', name='delivery')
    assert promoted.element == 'code.delivery'
    assert store.element('code.delivery').layer == layer.name
    assert len(store.history(original.id).results) == 1


@pytest.mark.req('STORE-029')
@pytest.mark.req('STORE-046')
def test_a_layout_20_store_is_read_into_the_log_and_the_old_file_is_kept_whole(home, store):
    """A store at the layout before the log opens: its rows become ops in a new file, every version kept, and the old
    file goes whole under the backups, never changed in place, STORE-046."""
    from metaform.data.schema import LAYOUT_20
    _, original, _ = small_map(store)
    store.refine(original.id, {'ef': 'Delivers expiry.'}, reason='Clarify delivery.')
    history = store.history(original.id).to_dict()
    held = store.where('stakeholder.cook.home').to_dict()
    path = store_file(home, store)
    log_ops = ops(path)
    # A layout 20 file with the same content: its tables filled from the log, then the log taken away.
    old = sqlite3.connect(path)
    old.executescript(LAYOUT_20)
    for op in log_ops:
        data = op['data']
        if op['kind'] == 'layer' and op['op'] == 'add':
            old.execute('INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, result_id, '
                        'kind, created, ready) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (op['id'], data['base_id'], data['name'], data['module'], data['variable'], int(data['mutable']),
                         int(data['hideable']), data['result_id'], 'intake' if data['kind'] == 'base' else data['kind'],
                         data['created'], data['ready']))
        elif op['kind'] == 'element':
            old.execute('INSERT OR IGNORE INTO element_ids(element_id) VALUES (?)', (op['id'],))
            old.execute("INSERT OR IGNORE INTO identities(id, kind) VALUES (?, 'element')", (op['id'],))
            for prefix in [data['address'].rsplit('.', n)[0] for n in range(data['address'].count('.'), -1, -1)]:
                old.execute('INSERT OR IGNORE INTO types(address, parent) VALUES (?, ?)',
                            (prefix, prefix.rsplit('.', 1)[0] if '.' in prefix else None))
            old.execute('INSERT INTO elements(element_id, layer_id, address, name_length, name, role, op, reason, '
                        'evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (op['id'], op['layer_id'], data['address'], data['name_length'], data['name'], data['role'],
                         op['op'], data.get('reason'), data.get('evidence')))
        elif op['kind'] == 'join':
            old.execute('INSERT OR IGNORE INTO join_ids(join_id) VALUES (?)', (op['id'],))
            old.execute("INSERT OR IGNORE INTO identities(id, kind) VALUES (?, 'join')", (op['id'],))
            cursor = old.execute('INSERT INTO joins(join_id, layer_id, type, receiver, purpose, ef, ifd, element, op, '
                                 'reason, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                 (op['id'], op['layer_id'], data['type'], data['receiver'], data['purpose'], data['ef'],
                                  data['ifd'], data.get('element'), op['op'], data.get('reason'), data.get('evidence')))
            for position, element_id in enumerate(data['held']):
                old.execute('INSERT INTO join_elements(join_row, position, element_id) VALUES (?, ?, ?)',
                            (cursor.lastrowid, position, element_id))
    for name in ('ops', 'objects', 'snapshots'):
        old.execute(f'DROP TABLE {name}')
    old.execute("UPDATE meta SET value='20' WHERE key='schema_version'")
    old.commit()
    old.close()
    from metaform.data import log
    log.forget(path)
    before = dump(path)
    with open_store(path, write=False) as db:
        assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0] == SCHEMA_VERSION == '21'
        assert {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {'ops', 'objects'}
    kept = list((home / 'backups' / 'upgrade-21').glob('*/*/*.sqlite3'))
    assert len(kept) == 1 and dump(kept[0]) == before  # the old file, whole, never changed in place
    with open_store(path, write=False):
        pass
    assert len(list((home / 'backups' / 'upgrade-21').glob('*/*/*.sqlite3'))) == 1
    assert store.history(original.id).to_dict() == history  # every version, in order
    assert store.where('stakeholder.cook.home').to_dict() == held
    assert store.promote_join(original.id, 'code.delivery').element == 'code.delivery'
