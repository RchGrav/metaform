"""The join holds only the fields Rich's design names, MAP-020: the metaform points at the code and is never documentation."""
from __future__ import annotations

import sqlite3

import pytest

from metaform.data.schema import STORE_SCHEMA

# Rich, 2026-10-02: "observation was not my design"; "Neither was relation." A field added to a join is added to the design,
# so it changes this list only with his word. The bookkeeping columns are the store's own: row identity, layer, the
# version's op, reason and evidence, and extra.
DESIGN = {'type', 'parent', 'receiver', 'provider', 'name', 'purpose', 'ef', 'ifd', 'verb', 'non_goal'}
STORE_OWN = {'row', 'join_id', 'layer_id', 'extra', 'op', 'reason', 'evidence'}
TOOL_OWN = {'parent_receiver', 'parent_provider', 'namespace_address', 'role', 'name_length', 'refs', 'extra', 'condition',
            'note'}


@pytest.mark.kind('fixture')
@pytest.mark.req('MAP-020')
def test_a_join_has_only_the_fields_the_design_names():
    db = sqlite3.connect(':memory:')
    db.executescript(STORE_SCHEMA)
    columns = {row[1] for row in db.execute('PRAGMA table_info(joins)')}
    assert columns - STORE_OWN == DESIGN, f'join columns beyond the design: {sorted(columns - STORE_OWN - DESIGN)}'
    from metaform.modules.intake import MODULE
    for verb in MODULE.verbs:
        if verb.name in ('add_purpose', 'subtype'):
            fields = {noun.name for noun in verb.nouns} - TOOL_OWN
            assert fields <= DESIGN, f'intake {verb.name} takes fields beyond the design: {sorted(fields - DESIGN)}'
