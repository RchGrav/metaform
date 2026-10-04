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

ELEMENT = {'address', 'name_length', 'name', 'role'}
JOIN = {'type', 'receiver', 'purpose', 'ef', 'ifd'}
HELD = {'join_row', 'position', 'element_id'}  # the elements a join holds, one row each, in order
# The bookkeeping columns are the store's own: row identity, layer, and the version's op, reason and evidence.
STORE_OWN = {'row', 'element_id', 'join_id', 'layer_id', 'op', 'reason', 'evidence'}
# What the intake tools take beside the design's own fields: the element's address under its intake name, the
# elements a join holds, refs for the sources layer, and the condition and note of a ticket.
TOOL_OWN = {'namespace_address', 'elements', 'refs', 'condition', 'note'}


@pytest.mark.kind('fixture')
@pytest.mark.req('STORE-009')
@pytest.mark.req('STORE-010')
def test_the_metaform_holds_only_the_fields_of_richs_shape():
    db = sqlite3.connect(':memory:')
    db.executescript(STORE_SCHEMA)
    columns = {table: {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
               for table in ('elements', 'joins', 'join_elements')}
    assert columns['elements'] - STORE_OWN == ELEMENT, f'element columns: {sorted(columns["elements"] - STORE_OWN)}'
    assert columns['joins'] - STORE_OWN == JOIN, f'join columns: {sorted(columns["joins"] - STORE_OWN)}'
    assert columns['join_elements'] == HELD
    assert 'current_subtypes' not in {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    from metaform.modules.intake import MODULE
    taken = {verb.name: {noun.name for noun in verb.nouns} for verb in MODULE.verbs}
    assert taken['element'] - TOOL_OWN <= ELEMENT, f'intake element takes {sorted(taken["element"] - TOOL_OWN - ELEMENT)}'
    assert taken['join'] - TOOL_OWN <= JOIN, f'intake join takes {sorted(taken["join"] - TOOL_OWN - JOIN)}'
