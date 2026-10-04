"""The metaform holds only the fields Rich's design names: the metaform points at the code and is never documentation.

Rich, 2026-10-04: "we are reverting the data shape back to my original original design, no added field nothing...
that can all go to a knowledge layer. metaform goes back to my original shape". An element is its namespace_address,
name_length, name and role; a join is its type, purpose, ef and ifd, held by its receiver, holding the elements that
serve it. A field added to either is added to the design, so it changes these lists only with his word.
"""
from __future__ import annotations

import sqlite3

import pytest

from metaform.data.schema import STORE_SCHEMA

# The store's bookkeeping of a versioned row: its row, identity, layer, and the version's op, reason and evidence.
VERSION = {'row', 'layer_id', 'op', 'reason', 'evidence'}
COLUMNS = {
    'elements': VERSION | {'element_id', 'address', 'name_length', 'name', 'role'},
    'joins': VERSION | {'join_id', 'type', 'receiver', 'purpose', 'ef', 'ifd'},
    'join_elements': {'join_row', 'position', 'element_id'},  # the elements a join holds, one row each, in order
    'current_elements': {'element_id', 'row', 'address', 'role'},
    'current_joins': {'join_id', 'row', 'receiver'},
    'refs': {'ref_id', 'owner', 'owner_row', 'position', 'key', 'value'},
}
ELEMENT = {'namespace_address', 'name_length', 'name', 'role'}
JOIN = {'receiver', 'elements', 'purpose', 'ef', 'ifd'}
TICKET = {'condition', 'note'}  # a ticket written beside what was recorded, apart from the map


@pytest.mark.kind('fixture')
@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-010')
def test_the_metaform_holds_only_the_fields_of_richs_shape():
    db = sqlite3.connect(':memory:')
    db.executescript(STORE_SCHEMA)
    for table, wanted in COLUMNS.items():
        found = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
        assert found == wanted, f'{table}: {sorted(found ^ wanted)}'
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert 'current_subtypes' not in tables
    # Refs belong only to layer items and properties: the metaform holds none, STORE-012.
    for owner in ('item', 'property'):
        db.execute("INSERT INTO refs(owner, owner_row, position, key, value) VALUES (?, 1, 0, 'k', 'v')", (owner,))
    for owner in ('element', 'join'):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO refs(owner, owner_row, position, key, value) VALUES (?, 1, 0, 'k', 'v')", (owner,))


@pytest.mark.kind('fixture')
@pytest.mark.req('BASE-039')
@pytest.mark.req('MAP-020')
def test_the_tools_that_write_the_metaform_take_no_field_beyond_richs_shape():
    from metaform.modules.intake import MODULE
    taken = {verb.name: {noun.name for noun in verb.nouns} for verb in MODULE.verbs}
    # An element's refs go to the sources layer; a join takes none, Rich 2026-10-04.
    assert taken['element'] - TICKET == ELEMENT | {'refs'}, sorted(taken['element'])
    assert taken['join'] - TICKET == JOIN, sorted(taken['join'])
    from metaform.modules.map import READS, REFINE_FIELDS
    assert READS['add-element'] <= {'address', 'name_length', 'name', 'role', 'refs'}, sorted(READS['add-element'])
    assert READS['add-join'] <= {'receiver', 'elements', 'purpose', 'ef', 'ifd', 'type'}, sorted(READS['add-join'])
    assert set(REFINE_FIELDS) <= {'name', 'name_length', 'role', 'purpose', 'ef', 'ifd', 'elements'}, REFINE_FIELDS
