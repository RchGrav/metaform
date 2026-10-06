"""Bringing a metaform store written at an earlier layout up to the current one, STORE-029.

Rich, 2026-10-01: the version changes only for a change that requires an update, and the store is updated, never
thrown away. Layout 7 to 8, LAYER-025: a thing is no longer unique per layer, `reexamine.correction_layer_id` is
`changed_in`, and there are no correction layers, so each correction layer's versions are folded into the intake
layer it refined, after that layer's own versions, and the intake layer is named `intake`. A copy of the file is
kept under the home's backups before anything is changed.

Layout 8 to 9, D92 and VIEW-035: a ticket keeps its kind while it is worked, so a record taken as in-progress is a
missing one taken, and one fixing a broken one taken; a ticket records who took it and its place on the board, and
links other nodes for reference.

Layout 10 to 11, Rich 2026-10-02: "drop perspective drop the duality , EF infers fine". The joins' perspective column
is taken out; every other field of every join is kept as it was.

Layout 11 to 12, Rich 2026-10-02: "observation was not my design. I didn't ask for observation"; "Neither was
relation"; "by placing permanent implementation details into the fucking metaform, you're fucking it all up". The
metaform is a map that points to the code, never documentation. Every current join and subtype join takes its old
relation text as its ef, written as its newest version, so its earlier versions keep the old ef; then the relation and
observation columns are removed. The old ef text and the old observation text go into no field: they remain only in
the store's version history and in the backup made first.

Layout 12 to 13, Rich 2026-10-02: "the join type for requirements is require, rename it across the board from purpose".
Every version of every join of type purpose is typed require; nothing else changes.

Layout 13 to 14, VIEW-040, Rich 2026-10-03: a ticket holds the agent glyph it is assigned to. The work table gains its
glyph column, empty on every ticket; nothing else changes.

Layout 14 to 15, ticket 90430bba, STORE-045 and BASE-046: a ticket's glyph is a feature's field, kept in the map
module's own table keyed by the work id, so the chassis work table drops its glyph column; every other field of every
ticket is kept. The glyphs it held go into no field: they remain only in the backup made first.

Layout 15 to 16, LAYER-021, Rich 2026-10-03, D91 and D92: a knowledge item carries read_first and always_show. The items
table gains both columns, false on every item; nothing else changes.

Layout 16 to 17, MAP-054, Rich 2026-10-02, D112: "When a join becomes an element it creates an element record for the
join which can accept more joins itself. they are associated by the namespace name". The joins table gains its element
column, the address of the element a promoted join names, empty on every join; nothing else changes.

Layout 17 to 18, Rich 2026-10-04: "well I think we need to go back to purpose for semantics"; "yeah, add it to
purpose..   thats because for certain artifact types like photos you cant call them a requirement but you can more
easily reason a purpose". Every version of every join of type require is typed purpose again; nothing else changes.

Layout 18 to 19, Rich 2026-10-04: "we are reverting the data shape back to my original original design, no added field
nothing...   that can all go to a knowledge layer.  metaform goes back to my original shape"; "if you want to have refs
you add a sources layer, or you keep them in a sources layer". An element keeps its address, name_length, name and
role; a join keeps its type, receiver, purpose, ef and ifd, and holds the elements that serve it. Every version of a
join holds its provider; each current subtype join's element is held by its parent join's current version, and the
subtype join is gone. A join's or subtype join's name is the name of the element it holds, Rich 2026-10-04: "the name on
the join was the name for the element". Every current element's refs, and those of the joins that held it, become its
one item of a layer named sources. Items, tickets and messages at a subtype join move to its element. Nothing else of
the old shape is kept in the store, Rich 2026-10-04: "I want all of that fucikiong  shit gone"; the backup made first
holds every field and every earlier version.

Layout 19 to 20, MAP-054: the join gains its nullable element address again.
Every existing row and version is kept, and a backup supports restoring layout 19.
No other removed join fields return.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .. import home
from ..errors import StoreError
from ..sqlite import SCHEMA_VERSION
from . import tables
from .schema import STORE_SCHEMA
from .versions import KINDS, recompute

RENAMED: dict[str, dict[str, str]] = {'reexamine': {'changed_in': 'correction_layer_id'}}  # a new column read from its old name
VERSIONED = ('elements', 'joins', 'items', 'properties')
LAYERED = VERSIONED + ('item_ids', 'current_items', 'current_properties')  # kept, moved to the intake
SETTINGS = ('hidden_layers', 'layer_fields', 'layer_tags', 'provenance', 'selections')  # the correction layer's own
LEFT_OUT = {'layers': "kind <> 'correction'"}  # rows the new layout cannot hold; folded below


def upgrade(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Update a store at layout 7 to 19 to the current layout in one transaction, after keeping a copy of it."""
    if found not in ('7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19'):
        raise StoreError(f'{path} has schema version {found}; this Metaform updates only versions 7 to 19.',
                         'install the Metaform release that wrote it')
    _backup(db, path)
    target = sqlite3.connect(':memory:')
    target.executescript(STORE_SCHEMA + '\n' + tables.extension_schema())
    wanted = target.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    target.close()
    factory = db.row_factory
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute('BEGIN IMMEDIATE')
    try:
        stack: list[str] = []
        if found == '7':
            stack = [row[0] for row in db.execute('SELECT layer_id FROM correction_stack ORDER BY position')]
            stack += [row[0] for row in db.execute("SELECT layer_id FROM layers WHERE kind='correction'")
                      if row[0] not in stack]
        _ef_from_relation(db)
        if int(found) < 10:  # a layout 10 store already holds these; run while `extra` is still there
            _fields(db)
        _to_shape(db, wanted)
        _relayout(db, wanted)
        if found == '7':
            for layer_id in stack:
                _fold(db, layer_id)
            _name_intake(db)
            for kind in KINDS.values():
                ids = [row[0] for row in db.execute(f'SELECT DISTINCT {kind.id_column} FROM {kind.table}')]
                recompute(db, _kind_name(kind.table), ids)
        tables.legacy_upgrade(db, found)
        if int(found) < 19:
            db.execute("UPDATE joins SET type='purpose' WHERE type='require'")  # layout 18, Rich 2026-10-04
        db.execute('DROP TABLE IF EXISTS temp.subtype_moves')
        problems = db.execute('PRAGMA foreign_key_check').fetchall()
        if problems:
            raise StoreError(f'{path} could not be updated to version {SCHEMA_VERSION}: {len(problems)} references would break, '
                             f'the first in {problems[0][0]}. Nothing was changed.', 'metaform feedback')
        db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('prior_schema_version',?)", (found,))
        db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (SCHEMA_VERSION,))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')
        db.row_factory = factory


def _backup(db: sqlite3.Connection, path: Path) -> None:
    folder = home.home() / 'backups' / f'upgrade-{SCHEMA_VERSION}' / home.now().replace(':', '').replace('-', '') / path.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    copy = sqlite3.connect(folder / path.name)
    try:
        db.backup(copy)
    finally:
        copy.close()


def _relayout(db: sqlite3.Connection, wanted: list[tuple[str, str, str]]) -> None:
    """Rebuild each table whose definition changed, keeping every row and row number; drop tables the layout no
    longer has; create the indexes it adds."""
    have = {name: sql for kind, name, sql in db.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL") if kind == 'table'}
    wanted_tables = {name: sql for kind, name, sql in wanted if kind == 'table'}
    for name in have:
        # A module's own table has a dot in its name and is the module's to keep, STORE-045.
        if name == 'correction_stack':
            db.execute(f'DROP TABLE "{name}"')
    for name, sql in wanted_tables.items():
        if name not in have:
            db.execute(sql)
            continue
        if _plain(have[name]) == _plain(sql):
            continue
        old: list[str] = [row[1] for row in db.execute(f'PRAGMA table_info("{name}")')]
        db.execute(re.sub(rf'^CREATE TABLE\s+"?{name}"?\s*\(', f'CREATE TABLE "{name}__8"(', sql, count=1))
        new: list[str] = [row[1] for row in db.execute(f'PRAGMA table_info("{name}__8")')]
        sources = [RENAMED.get(name, {}).get(column, column) if RENAMED.get(name, {}).get(column) in old else column
                   for column in new]
        kept = [(column, source) for column, source in zip(new, sources) if source in old]
        db.execute(f'INSERT INTO "{name}__8"({", ".join(c for c, _ in kept)}) '
                   f'SELECT {", ".join(s for _, s in kept)} FROM "{name}"'
                   + (f' WHERE {LEFT_OUT[name]}' if name in LEFT_OUT else ''))
        db.execute(f'DROP TABLE "{name}"')
        db.execute(f'ALTER TABLE "{name}__8" RENAME TO "{name}"')
    present = {row[0] for row in db.execute("SELECT name FROM sqlite_master")}
    for kind, name, sql in wanted:
        if kind in ('index', 'trigger') and name not in present:
            db.execute(sql)


EF_REASON = ('Layout 12, Rich 2026-10-02: ef takes the old relation text; relation and observation are removed, '
             'since the metaform is a map that points to the code, never documentation.')


def _ef_from_relation(db: sqlite3.Connection) -> None:
    """Layout 12: each current join and subtype join whose ef is not its relation gets a newest version, its ef the
    old relation text and every other field as it was, with its refs; the current row moves to it. Run before the
    relation column is removed; a removed join gets no version, and a store with no relation column has nothing to
    move."""
    if 'relation' not in [row[1] for row in db.execute('PRAGMA table_info(joins)')]:
        return
    for table in ('current_joins', 'current_subtypes'):
        for join_id, current in db.execute(f'SELECT join_id, row FROM {table} ORDER BY row').fetchall():
            base = db.execute('SELECT * FROM joins WHERE row=?', (current,)).fetchone()
            if base['ef'] == base['relation'] or not base['relation']:  # no relation, nothing to move
                continue
            # sqlite3.Row iterates values, so column names must come from keys().
            columns = {key: base[key] for key in base.keys() if key != 'row'}  # noqa: SIM118
            columns.update(ef=base['relation'], op='change', reason=EF_REASON, evidence=None)
            cursor = db.execute(f'INSERT INTO joins({", ".join(columns)}) VALUES ({", ".join("?" for _ in columns)})',
                                tuple(columns.values()))
            row = int(cursor.lastrowid or 0)
            db.execute("INSERT INTO refs(owner, owner_row, position, key, value) SELECT owner, ?, position, key, value "
                       "FROM refs WHERE owner='join' AND owner_row=? ORDER BY position", (row, current))
            db.execute(f'UPDATE {table} SET row=? WHERE join_id=?', (row, join_id))


def _fields(db: sqlite3.Connection) -> None:
    """Layout 10, Rich 2026-10-01: an element's name and a join's IFD are fields of their own, no longer kept in its
    extra; each is moved out of the extra, and an extra left empty is cleared. Run before the relayout, which takes
    `extra` off, so the two columns are added here when the store does not have them yet."""
    for table, key in (('elements', 'name'), ('joins', 'ifd')):
        columns = [row[1] for row in db.execute(f'PRAGMA table_info({table})')]
        if key not in columns:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {key} TEXT')
        if 'extra' not in columns:
            continue
        db.execute(f"UPDATE {table} SET {key}=json_extract(extra, '$.{key}') WHERE {key} IS NULL AND json_valid(extra) "
                   f"AND json_type(extra, '$.{key}') = 'text'")
        db.execute(f"UPDATE {table} SET extra=NULLIF(json_remove(extra, '$.{key}'), '{{}}') WHERE json_valid(extra) "
                   f"AND json_type(extra, '$.{key}') = 'text'")


def _plain(sql: str) -> str:
    return ' '.join(sql.replace('IF NOT EXISTS ', '').split())


def _fold(db: sqlite3.Connection, correction: str) -> None:
    """Move one correction layer's versions into the intake layer it refined; its rows keep their row numbers,
    which come after the intake's own, so they stay the newest versions."""
    intake = _refined(db, correction)
    tables.legacy_fold(db, correction, intake)
    for table in LAYERED:
        db.execute(f'UPDATE {table} SET layer_id=? WHERE layer_id=?', (intake, correction))
    db.execute('UPDATE OR IGNORE reexamine SET changed_in=? WHERE changed_in=?', (intake, correction))
    db.execute('DELETE FROM reexamine WHERE changed_in=? OR layer_id=?', (correction, correction))
    for table in SETTINGS:
        db.execute(f'DELETE FROM {table} WHERE layer_id=?', (correction,))
    db.execute('DELETE FROM layer_sources WHERE layer_id=? OR source_layer_id=?', (correction, correction))
    db.execute('DELETE FROM layers WHERE layer_id=?', (correction,))


def _refined(db: sqlite3.Connection, correction: str) -> str:
    sources = [row[0] for row in db.execute(
        "SELECT s.source_layer_id FROM layer_sources s JOIN layers l ON l.layer_id=s.source_layer_id "
        "WHERE s.layer_id=? AND l.kind='intake'", (correction,))]
    intakes = sources or [row[0] for row in db.execute("SELECT layer_id FROM layers WHERE kind='intake'")]
    if len(intakes) != 1:
        raise StoreError(f'The correction layer {correction} refines {len(intakes)} intake layers, not one, so it '
                         'cannot be folded into one. Nothing was changed.', 'metaform feedback')
    return intakes[0]


def _name_intake(db: sqlite3.Connection) -> None:
    intakes = [row[0] for row in db.execute("SELECT layer_id FROM layers WHERE kind='intake' ORDER BY created")]
    if len(intakes) == 1:
        db.execute("UPDATE layers SET name='intake' WHERE layer_id=?", (intakes[0],))


def _kind_name(table: str) -> str:
    return next(name for name, kind in KINDS.items() if kind.table == table)


SHAPE_REASON = "Layout 19, Rich 2026-10-04: the metaform goes back to Rich's original shape."
SOURCES = 'sources'


def _to_shape(db: sqlite3.Connection, wanted: list[tuple[str, str, str]]) -> None:
    """Layout 19: a join holds the elements that serve it, and everything beyond Rich's shape goes into layers.

    Run before the old columns are removed. `temp.subtype_moves` names, for each subtype join, the element it held,
    so each module's legacy upgrade can move what it keeps at a subtype join to that element.
    """
    columns = [row[1] for row in db.execute('PRAGMA table_info(joins)')]
    if 'provider' not in columns:
        return
    db.execute(next(sql for kind, name, sql in wanted if kind == 'table' and name == 'join_elements'))
    db.execute('CREATE TEMP TABLE subtype_moves(join_id TEXT PRIMARY KEY, element_id TEXT NOT NULL)')
    db.execute('INSERT INTO join_elements(join_row, position, element_id) '
               'SELECT row, 0, provider FROM joins WHERE parent IS NULL')
    db.execute('INSERT OR REPLACE INTO temp.subtype_moves(join_id, element_id) '
               'SELECT join_id, provider FROM joins WHERE parent IS NOT NULL ORDER BY row')
    made: dict[str, str] = {}

    def layer(name: str, variable: str) -> str | None:
        if name not in made:
            owner = db.execute("SELECT metaform_id FROM layers ORDER BY kind <> 'intake', created LIMIT 1").fetchone()
            if owner is None:
                return None
            chosen, number = name, 1
            while db.execute('SELECT 1 FROM layers WHERE name=?', (chosen,)).fetchone():
                number += 1
                chosen = f'{name}-{number}'
            made[name] = uuid.uuid4().hex
            now = home.now()
            db.execute('INSERT INTO layers(layer_id, metaform_id, name, module, variable, mutable, hideable, kind, '
                       "created, ready) VALUES (?, ?, ?, 'intake', ?, 1, 1, 'layer', ?, ?)",
                       (made[name], owner[0], chosen, variable, now, now))
        return made[name]

    def item(name: str, variable: str, kind: str, target: str, value: Any,
             refs: Sequence[tuple[str, str]] = ()) -> None:
        layer_id = layer(name, variable)
        if layer_id is None:
            return
        item_id = uuid.uuid4().hex
        db.execute('INSERT INTO item_ids(item_id, layer_id) VALUES (?, ?)', (item_id, layer_id))
        db.execute("INSERT INTO identities(id, kind) VALUES (?, 'item')", (item_id,))
        cursor = db.execute('INSERT INTO items(item_id, layer_id, target_kind, target_id, value) VALUES (?, ?, ?, ?, ?)',
                            (item_id, layer_id, kind, target, json.dumps(value, ensure_ascii=False, sort_keys=True)))
        row = int(cursor.lastrowid or 0)
        db.execute('INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id) VALUES (?, ?, ?, ?, ?)',
                   (item_id, row, layer_id, kind, target))
        db.executemany("INSERT INTO refs(owner, owner_row, position, key, value) VALUES ('item', ?, ?, ?, ?)",
                       [(row, index, key, value) for index, (key, value) in enumerate(refs)])

    def refs_of(owner: str, row: int) -> list[tuple[str, str]]:
        return [(str(ref[0]), str(ref[1])) for ref in db.execute(
            'SELECT key, value FROM refs WHERE owner=? AND owner_row=? ORDER BY position', (owner, row))]

    def address(element_id: Any) -> str:
        found = db.execute('SELECT address FROM elements WHERE element_id=? ORDER BY row DESC LIMIT 1',
                           (element_id,)).fetchone()
        return str(found[0]) if found else str(element_id)

    refs: dict[str, list[tuple[str, str]]] = {}  # each element's refs, its own and those of the joins that held it

    def name(element_id: Any, given: Any) -> None:
        """A join's or a subtype join's name is the name of the element it holds, Rich 2026-10-04: "the name on the
        join was the name for the element"; an element that has a name of its own keeps it."""
        if given:
            db.execute('UPDATE elements SET name=? WHERE name IS NULL AND row=(SELECT row FROM current_elements '
                       'WHERE element_id=?)', (given, element_id))

    for element_id, current in db.execute('SELECT element_id, row FROM current_elements ORDER BY row').fetchall():
        refs.setdefault(element_id, []).extend(refs_of('element', current))
    for current, provider in db.execute('SELECT c.row, j.provider FROM current_joins c JOIN joins j ON j.row = c.row '
                                        'ORDER BY c.row').fetchall():
        base = db.execute('SELECT * FROM joins WHERE row=?', (current,)).fetchone()
        name(provider, base['name'])
        refs.setdefault(provider, []).extend(refs_of('join', current))
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='current_subtypes'").fetchone():
        for parent, element_id, current in db.execute(
                'SELECT parent, provider, row FROM current_subtypes ORDER BY row').fetchall():
            base = db.execute('SELECT * FROM joins WHERE row=?', (current,)).fetchone()
            holder = db.execute('SELECT j.row FROM current_joins c JOIN joins j ON j.row = c.row WHERE c.join_id=?',
                                (parent,)).fetchone()
            if holder is not None and not db.execute('SELECT 1 FROM join_elements WHERE join_row=? AND element_id=?',
                                                     (holder[0], element_id)).fetchone():
                position = db.execute('SELECT COALESCE(MAX(position) + 1, 0) FROM join_elements WHERE join_row=?',
                                      (holder[0],)).fetchone()[0]
                db.execute('INSERT INTO join_elements(join_row, position, element_id) VALUES (?, ?, ?)',
                           (holder[0], position, element_id))
            name(element_id, base['name'])
            refs.setdefault(element_id, []).extend(refs_of('join', current))
        db.execute('DROP TABLE current_subtypes')
    for element_id, found in refs.items():
        if found:
            item(SOURCES, 'refs', 'element', element_id, address(element_id), found)
    for column in ('target', 'link'):
        for table in ('items', 'current_items'):
            db.execute(f"UPDATE {table} SET {column}_kind='element', {column}_id=(SELECT element_id FROM "
                       f"temp.subtype_moves m WHERE m.join_id={table}.{column}_id) WHERE {column}_kind='join' AND "
                       f'{column}_id IN (SELECT join_id FROM temp.subtype_moves)')
    db.execute("DELETE FROM refs WHERE owner IN ('element', 'join')")
    db.execute('DELETE FROM join_elements WHERE join_row IN (SELECT row FROM joins WHERE parent IS NOT NULL)')
    db.execute('DELETE FROM joins WHERE parent IS NOT NULL')
