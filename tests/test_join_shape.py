"""The metaform holds only the fields its design names: the metaform points at the code and is never documentation.

D115: the data shape is the original design, with no added field; anything more goes to a layer. An element is its namespace_address,
name_length, name and role; a join is its type, purpose, ef and ifd, held by its receiver, holding the elements that
serve it. A field added to either is added to the design, so it changes these lists only when the design does.
"""
from __future__ import annotations

import sqlite3

import pytest
from storekit import ops, small_map, store_file

# The op's own bookkeeping, beside the object's fields: how it was written, and why, LAYER-025.
VERSION = {'mode', 'reason', 'evidence'}
FIELDS = {
    'element': VERSION | {'address', 'name_length', 'name', 'role'},
    'join': VERSION | {'type', 'receiver', 'purpose', 'ef', 'ifd', 'element', 'held'},  # held: its elements, in order
}
ELEMENT = {'namespace_address', 'name_length', 'name', 'role'}
JOIN = {'receiver', 'elements', 'purpose', 'ef', 'ifd'}
TICKET = {'condition', 'note'}  # a ticket written beside what was recorded, apart from the map


@pytest.mark.kind('fixture')
@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-010')
@pytest.mark.req('STORE-046')
def test_the_metaform_holds_only_the_fields_of_its_shape(home, store):
    """Every op the base's layer writes for an element or a join carries the metaform's shape and nothing more; the base
    holds no refs, STORE-012: refs are on items and properties only."""
    small_map(store)
    written = ops(store_file(home, store))
    for kind, wanted in FIELDS.items():
        for op in (op for op in written if op['kind'] == kind):
            assert set(op['data']) <= wanted and set(op['data']) >= wanted - VERSION, \
                f'{kind}: {sorted(set(op["data"]) ^ wanted)}'
    db = sqlite3.connect(store_file(home, store))
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not {'current_subtypes', 'subtypes', 'refs', 'elements', 'joins'} & tables
    assert not any('refs' in op['data'] for op in written if op['kind'] in ('element', 'join'))


@pytest.mark.kind('fixture')
@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-020')
def test_the_tools_that_write_the_metaform_take_no_field_beyond_its_shape():
    from metaform.modules.intake import MODULE
    taken = {verb.name: {noun.name for noun in verb.nouns} for verb in MODULE.verbs}
    # Refs, an element's or a join's, go to the sources layer, never into the metaform, BASE-039 amendment 2026-10-08.
    assert taken['element'] - TICKET == ELEMENT | {'refs'}, sorted(taken['element'])
    assert taken['join'] - TICKET == JOIN | {'refs'}, sorted(taken['join'])
    from metaform.modules.map import READS, REFINE_FIELDS
    assert READS['add-element'] <= {'address', 'name_length', 'name', 'role', 'refs'}, sorted(READS['add-element'])
    assert READS['add-join'] <= {'receiver', 'elements', 'purpose', 'ef', 'ifd', 'type'}, sorted(READS['add-join'])
    assert set(REFINE_FIELDS) <= {'name', 'name_length', 'role', 'purpose', 'ef', 'ifd', 'elements'}, REFINE_FIELDS
