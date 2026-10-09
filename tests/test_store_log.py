"""STORE-046: the store as an op log, the graph in memory, the change order of 2026-10-07 items 1 and 2."""
from __future__ import annotations

import json
import sqlite3

import pytest
from storekit import knowledge, memory, small_map


def filled(store):
    from metaform.data import Node
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
    store.refine(outer.id, {'elements': ['code.timer.kitchen']}, reason="the tick is the timer's own")
    store.refine(outer.id, {'purpose': 'Serve each dish on time.'}, reason='sharper')
    return outer, inner

pytestmark = [pytest.mark.req('STORE-046'), pytest.mark.kind('fixture')]


def _opened(home, store):
    from metaform import home as homes
    base = homes.active_base(store.project_id)
    assert base is not None
    return sqlite3.connect(homes.store_path(store.project_id, base.id))


def _state(projection) -> dict:
    """Everything a read answers from, as plain data, so two projections can be compared whole."""
    return json.loads(json.dumps(projection.snapshot(), sort_keys=True))


def test_every_write_is_an_op_and_nothing_is_ever_edited(home, store):
    from metaform.data import Node
    outer, _ = filled(store)
    db = _opened(home, store)
    seqs = [row[0] for row in db.execute('SELECT seq FROM ops ORDER BY seq')]
    assert seqs == list(range(1, len(seqs) + 1))
    before = db.execute('SELECT seq, op, kind, id, data FROM ops ORDER BY seq').fetchall()
    store.refine(outer.id, {'purpose': 'Serve each dish on time, again.'}, reason='a later reading')
    store.add_item('notes', Node('element', 'code.timer.kitchen'), 'one more')
    after = db.execute('SELECT seq, op, kind, id, data FROM ops ORDER BY seq').fetchall()
    assert after[:len(before)] == before  # append only: the earlier rows are as they were
    assert len(after) > len(before)
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'ops', 'objects', 'snapshots', 'meta'} <= tables
    assert not {'elements', 'joins', 'items', 'current_elements', 'current_joins', 'item_text'} & tables
    assert {row[0] for row in db.execute('SELECT kind FROM objects')} == {'element', 'join', 'item', 'property'} \
        or {row[0] for row in db.execute('SELECT kind FROM objects')} <= {'element', 'join', 'item', 'property'}


def test_opening_from_the_log_alone_equals_a_snapshot_plus_replay(home, store):
    from metaform.data import log
    from metaform.data.projection import Projection
    filled(store)
    db = _opened(home, store)
    db.row_factory = sqlite3.Row
    whole = log.load(db)  # no snapshot yet: the whole log
    half = whole.seq // 2
    partial = Projection()
    log.catch_up(partial, db) if half == 0 else None
    rows = db.execute('SELECT seq, session_id, op, kind, id, layer_id, data FROM ops WHERE seq <= ? ORDER BY seq',
                      (half,)).fetchall()
    from metaform.data.projection import ops_from_rows
    halfway = Projection()
    for op in ops_from_rows(rows):
        halfway.apply(op)
    db.execute('INSERT INTO snapshots(seq, graph) VALUES (?, ?)',
               (halfway.seq, json.dumps(halfway.snapshot(), sort_keys=True)))
    db.commit()
    from_snapshot = log.load(db)
    assert from_snapshot.seq == whole.seq
    assert _state(from_snapshot) == _state(whole)
    assert sorted(from_snapshot.graph.nodes) == sorted(whole.graph.nodes)
    assert sorted(from_snapshot.graph.edges(keys=True)) == sorted(whole.graph.edges(keys=True))


def test_removing_one_op_and_replaying_removes_exactly_its_effect(home, store):
    from metaform.data import Node
    from metaform.data.projection import Projection, ops_from_rows
    filled(store)
    added = store.add_item('notes', Node('element', 'code.timer.kitchen'), 'the one to take out')
    db = _opened(home, store)
    db.row_factory = sqlite3.Row
    rows = db.execute('SELECT seq, session_id, op, kind, id, layer_id, data FROM ops ORDER BY seq').fetchall()
    whole, without = Projection(), Projection()
    for op in ops_from_rows(rows):
        whole.apply(op)
        if op.id != added.id:
            without.apply(op)
    assert added.id in whole.kinds and added.id not in without.kinds
    assert set(whole.graph.nodes) - set(without.graph.nodes) == {added.id}
    assert {edge[:2] for edge in whole.graph.edges} - {edge[:2] for edge in without.graph.edges} == {
        (store.element('code.timer.kitchen').id, added.id)}
    others = {ident: versions for ident, versions in whole.versions.items() if ident != added.id}
    assert {ident: [v.fields for v in versions] for ident, versions in others.items()} == {
        ident: [v.fields for v in versions] for ident, versions in without.versions.items()}


def test_a_read_touches_no_table_but_the_log_and_the_modules_own(home, store, traced):
    """Reads answer from the graph in memory, STORE-046: the only SQL a read issues reads the ops past the sequence
    it applied, and the modules' own tables."""
    from metaform.data import Node
    filled(store)
    traced.clear()
    store.where('code.timer.kitchen')
    store.roots()
    store.joins('code.timer.kitchen')
    store.search('loop')
    store.node(Node('element', 'code.timer.kitchen'))
    store.graph()
    chassis = [statement for statement in traced
               if ' ops' in statement.lower() or 'FROM elements' in statement or 'FROM joins' in statement
               or 'current_' in statement or 'item_text' in statement]
    assert all('FROM ops' in statement for statement in chassis), chassis


def test_a_cypher_query_answers_over_the_graph(store):
    filled(store)
    kitchen = store.element('code.timer.kitchen')
    found = store.cypher('MATCH (r)-[j]->(e) WHERE r.address = "stakeholder.cook.home" RETURN e.address, j.purpose')
    assert 'code.timer.kitchen' in found['e.address']
    assert kitchen is not None and any('dish' in str(purpose) for purpose in found['j.purpose'])


def test_two_processes_at_one_sequence_hold_the_same_graph(home, store):
    from metaform.data import Store, log
    filled(store)
    db = _opened(home, store)
    db.row_factory = sqlite3.Row
    other = log.load(db)
    mine = Store(store.project_id)
    with mine._read() as tx:
        assert _state(tx.base) == _state(other)


def test_a_cypher_query_sees_only_the_layers_in_view_and_can_name_its_own(store):
    """Rich, 2026-10-08: Cypher over the map is there so layers can be hidden or shown on the fly. A query sees what
    the layers in view show, as every read does, and names other layers for itself."""
    filled(store)
    items = 'MATCH (n) WHERE n.kind = "item" RETURN n.value'
    everything = store.cypher(items)['n.value']
    assert any('keep it small' in str(value) for value in everything)  # the notes layer is in view
    base_only = store.cypher(items, ['intake-1'])['n.value'] if store.cypher(items, ['intake-1']) else []
    assert not any('keep it small' in str(value) for value in base_only)  # named away for this query alone
    store.hide('notes')
    hidden = store.cypher(items)['n.value'] if store.cypher(items) else []
    assert not any('keep it small' in str(value) for value in hidden)  # a hidden layer is out of every query
    elements = store.cypher('MATCH (e) WHERE e.kind = "element" RETURN e.address', ['intake-1'])['e.address']
    assert 'code.timer.kitchen' in elements  # the base itself is always there
