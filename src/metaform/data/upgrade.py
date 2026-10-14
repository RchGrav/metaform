"""Bringing a base's store written at an earlier layout up to the current one, STORE-029 and STORE-046.

Layout 20 to 21, the change order of 2026-10-07: the store becomes an op log. The old file is never changed in place:
it is copied, brought to layout 20 on the copy when it is older, read into ops in a new file beside it, and kept whole
under the home's backups once the new file has taken its name. The modules' own tables are copied as they are.

the version changes only for a change that requires an update, and the store is updated, never
thrown away. Layout 7 to 8, LAYER-025: a thing is no longer unique per layer, `reexamine.correction_layer_id` is
`changed_in`, and there are no correction layers, so each correction layer's versions are folded into the intake
layer it refined, after that layer's own versions, and the intake layer is named `intake`. A copy of the file is
kept under the home's backups before anything is changed.

Layout 8 to 9, D92 and VIEW-035: a ticket keeps its kind while it is worked, so a record taken as in-progress is a
missing one taken, and one fixing a broken one taken; a ticket records who took it and its place on the board, and
links other nodes for reference.

Layout 10 to 11: a join carries no perspective, since its ef says the direction. The joins' perspective column
is taken out; every other field of every join is kept as it was.

Layout 11 to 12: observation and relation were never part of the design, and implementation detail does not belong
in the metaform. The metaform is a map that points to the code, never documentation. Every current join and subtype join takes its old
relation text as its ef, written as its newest version, so its earlier versions keep the old ef; then the relation and
observation columns are removed. The old ef text and the old observation text go into no field: they remain only in
the store's version history and in the backup made first.

Layout 12 to 13: the join type for requirements is renamed from purpose to require.
Every version of every join of type purpose is typed require; nothing else changes.

Layout 13 to 14, VIEW-040, a ticket holds the agent glyph it is assigned to. The work table gains its
glyph column, empty on every ticket; nothing else changes.

Layout 14 to 15, ticket 90430bba, STORE-045 and BASE-046: a ticket's glyph is a feature's field, kept in the map
module's own table keyed by the work id, so the chassis work table drops its glyph column; every other field of every
ticket is kept. The glyphs it held go into no field: they remain only in the backup made first.

Layout 15 to 16, LAYER-021, D91 and D92: a knowledge item carries read_first and always_show. The items
table gains both columns, false on every item; nothing else changes.

Layout 16 to 17, MAP-054, D112: "When a join becomes an element it creates an element record for the
join which can accept more joins itself. they are associated by the namespace name". The joins table gains its element
column, the address of the element a promoted join names, empty on every join; nothing else changes.

Layout 17 to 18: the join type goes back to purpose, because an artifact such as a photo cannot be said to meet a
requirement but can be reasoned to serve a purpose. Every version of every join of type require is typed purpose again; nothing else changes.

Layout 18 to 19, D115: the data shape goes back to the original design with no added field; what was added goes to
layers, and refs go in a sources layer. An element keeps its address, name_length, name and
role; a join keeps its type, receiver, purpose, ef and ifd, and holds the elements that serve it. Every version of a
join holds its provider; each current subtype join's element is held by its parent join's current version, and the
subtype join is gone. A join's or subtype join's name is the name of the element it holds.
Every current element's refs, and those of the joins that held it, become its
one item of a layer named sources. Items, tickets and messages at a subtype join move to its element. Nothing else of
the old shape is kept in the store; the backup made first
holds every field and every earlier version.

Layout 19 to 20, MAP-054: the join gains its nullable element address again.
Every existing row and version is kept, and a backup supports restoring layout 19.
No other removed join fields return.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import home
from ..errors import StoreError
from ..sqlite import BUSY_SECONDS, COMPATIBLE_FROM, SCHEMA_VERSION, connect, file_lock, private, stamp
from . import tables
from .schema import LAYOUT_20, STORE_SCHEMA

RENAMED: dict[str, dict[str, str]] = {'reexamine': {'changed_in': 'correction_layer_id'}}  # a new column read from its old name
VERSIONED = ('elements', 'joins', 'items', 'properties')
LAYERED = VERSIONED + ('item_ids', 'current_items', 'current_properties')  # kept, moved to the intake
SETTINGS = ('hidden_layers', 'layer_fields', 'layer_tags', 'provenance', 'selections')  # the correction layer's own
LEFT_OUT = {'layers': "kind <> 'correction'"}  # rows the new layout cannot hold; folded below



LEGACY = ('7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19')
UPGRADE_SESSION = 'upgrade-21'


def upgrade(db: sqlite3.Connection, path: Path, found: str) -> bool:
    """Bring a store at layout 7 to 20 to the log, STORE-046, writing a new file from the old one. Returns True: the
    file at `path` was replaced, and the caller's connection reads the old one, so it reconnects. Processes that open
    the file at once take turns under a lock beside it, STORE-006: one upgrades it, and each that waited finds it at
    the current layout and reconnects."""
    if found not in (*LEGACY, '20'):
        raise StoreError(f'{path} has schema version {found}; this Metaform updates only versions 7 to 20.',
                         'install the Metaform release that wrote it')
    with file_lock(path.with_name(path.name + '.upgrade.lock')):
        if _layout(path) == SCHEMA_VERSION:  # another process upgraded it while this one waited for the lock
            return True
        return _upgraded(db, path, found)


def _layout(path: Path) -> str | None:
    """The layout of the file now at `path`, read on a connection of its own: the caller's may read a file another
    process has since moved to backups."""
    fresh = connect(path)
    try:
        row = fresh.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    finally:
        fresh.close()
    return None if row is None else str(row[0])


def _upgraded(db: sqlite3.Connection, path: Path, found: str) -> bool:
    tables_held = {str(row[0]) for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'ops' in tables_held and 'elements' not in tables_held:  # the log already, under an earlier number
        kept = _kept_folder(path)
        home.mkdir_private(kept)
        private(kept / path.name)
        copy = sqlite3.connect(kept / path.name)
        try:
            db.backup(copy)  # a copy is kept before anything changes, as every upgrade keeps one, STORE-029
        finally:
            copy.close()
        db.execute('BEGIN IMMEDIATE')
        try:
            tables.create_missing(db)
            tables.legacy_upgrade(db, found)
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('prior_schema_version',?)", (found,))
            stamp(db, SCHEMA_VERSION, COMPATIBLE_FROM)
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise
        return False
    for left in (*path.parent.glob(glob.escape(path.name) + '.upgrading-*'),
                 *path.parent.glob(glob.escape(path.name) + '.new-*')):
        left.unlink(missing_ok=True)  # left by an upgrade that ended part way; under the lock no other one runs
    unique = f'{os.getpid()}-{uuid.uuid4().hex[:8]}'
    work = path.with_name(f'{path.name}.upgrading-{unique}')
    fresh = path.with_name(f'{path.name}.new-{unique}')
    # A connection of its own holds the old file's write lock from the copy to the swap, so no writer, such as a
    # process still on earlier code, commits to the file that goes to backups after it was copied. The caller's
    # connection cannot hold it: SQLite refuses to back up from a connection inside its own write transaction.
    guard = connect(path)
    guard.execute('BEGIN IMMEDIATE')
    try:
        private(work)
        copy = sqlite3.connect(work)
        try:
            db.backup(copy)
        finally:
            copy.close()
        old = sqlite3.connect(work, isolation_level=None)
        try:
            if found in LEGACY:
                _legacy(old, work, found)
            _to_log(old, fresh, found)
        finally:
            old.close()
        kept = _kept_folder(path)
        home.mkdir_private(kept)
        _backfilled(db, path)
    except BaseException:
        work.unlink(missing_ok=True)
        raise
    finally:
        guard.execute('ROLLBACK')
        guard.close()
    # The caller's connection reads the old file and is reconnected after this returns; it is closed before the file
    # moves, since Windows refuses to move or delete a file a connection holds open.
    db.close()
    shutil.move(str(path), str(kept / path.name))
    for suffix in ('-wal', '-shm'):
        path.with_name(path.name + suffix).unlink(missing_ok=True)
    work.unlink(missing_ok=True)
    fresh.replace(path)
    return True


def _backfilled(db: sqlite3.Connection, path: Path) -> None:
    """Every commit in the old file's write-ahead log copied into the file, so the file kept in backups is whole once
    its log is removed. Passive, since the full checkpoint waits for the write lock this upgrade holds; a reader in
    another process on an earlier snapshot is waited for, as a write waits, STORE-006."""
    deadline = time.monotonic() + BUSY_SECONDS
    while True:
        _, logged, copied = db.execute('PRAGMA wal_checkpoint(PASSIVE)').fetchone()
        if logged == copied:  # both -1 when the file is not in WAL mode
            return
        if time.monotonic() > deadline:
            raise StoreError(f'{path}: a read in another process kept its last commits from the backup for '
                             f'{BUSY_SECONDS} seconds, so it was not upgraded.', 'run metaform again')
        time.sleep(0.05)


def _kept_folder(path: Path) -> Path:
    when = home.now().replace(':', '').replace('-', '')
    return home.home() / 'backups' / f'upgrade-{SCHEMA_VERSION}' / f'{when}-{os.getpid()}' / path.parent.name


NATIVE_20 = set(re.findall(r'CREATE(?: VIRTUAL)? TABLE IF NOT EXISTS ([a-z_]+)', LAYOUT_20))


def _to_log(old: sqlite3.Connection, fresh: Path, found: str) -> None:
    """Read a layout 20 store into the ops of a new file, in the order its rows were written, with the modules'
    own tables copied as they are."""
    old.row_factory = sqlite3.Row
    private(fresh)
    new = sqlite3.connect(fresh, isolation_level=None)
    try:
        new.execute('PRAGMA journal_mode=WAL')
        new.executescript('BEGIN IMMEDIATE;\n' + STORE_SCHEMA +
                          '\nCOMMIT;')
        new.execute('BEGIN IMMEDIATE')
        for key, value in old.execute('SELECT key, value FROM meta'):
            if key not in ('schema_version', 'compatible_from', 'prior_schema_version'):
                new.execute('INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)', (key, value))
        new.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('prior_schema_version', ?)", (found,))
        stamp(new, SCHEMA_VERSION, COMPATIBLE_FROM)
        written = home.now()
        for seq, (op, kind, ident, layer_id, data) in enumerate(ops_of(old), 1):
            if kind in ('element', 'join', 'item', 'property'):
                new.execute('INSERT OR IGNORE INTO objects(id, kind) VALUES (?, ?)', (ident, kind))
            new.execute('INSERT INTO ops(seq, session_id, at, op, kind, id, layer_id, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (seq, UPGRADE_SESSION, written, op, kind, ident, layer_id,
                         json.dumps(data, ensure_ascii=False, sort_keys=True)))
        _copy_module_tables(old, new)
        new.execute('COMMIT')
    except BaseException:
        new.execute('ROLLBACK')
        new.close()
        fresh.unlink(missing_ok=True)
        raise
    new.close()


def _copy_module_tables(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """Every table that is not the chassis's, with its indexes, copied row for row, STORE-045."""
    rows = old.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL "
                       "AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, rowid").fetchall()
    copied: set[str] = set()
    for row in rows:
        kind, name, sql = str(row[0]), str(row[1]), str(row[3])
        if kind == 'table' and name not in NATIVE_20 and not name.startswith('item_text'):
            new.execute(re.sub(r'\s+REFERENCES\s+(' + '|'.join(sorted(NATIVE_20)) + r')\s*\([^)]*\)', '', sql))
            columns = [str(column[1]) for column in old.execute(f'PRAGMA table_info("{name}")')]
            quoted = ', '.join(f'"{column}"' for column in columns)
            for values in old.execute(f'SELECT {quoted} FROM "{name}"'):
                new.execute(f'INSERT INTO "{name}"({quoted}) VALUES ({", ".join("?" for _ in columns)})',
                            tuple(values))
            copied.add(name)
    for row in rows:
        if str(row[0]) == 'index' and str(row[2]) in copied:
            new.execute(str(row[3]))


def ops_of(old: sqlite3.Connection) -> list[tuple[str, str, str, str, dict[str, Any]]]:
    ops: list[tuple[str, str, str, str, dict[str, Any]]] = []
    hidden = {str(row[0]) for row in old.execute('SELECT layer_id FROM hidden_layers')}
    for layer in old.execute('SELECT * FROM layers ORDER BY rowid').fetchall():
        layer_id = str(layer['layer_id'])
        provenance = old.execute('SELECT * FROM provenance WHERE layer_id=?', (layer_id,)).fetchone()
        kind = 'base' if layer['kind'] == 'intake' else str(layer['kind'])
        name = 'base' if kind == 'base' and layer['name'] == 'intake' else str(layer['name'])
        ops.append(('add', 'layer', layer_id, layer_id, {
            'base_id': str(layer['metaform_id']), 'name': name, 'module': str(layer['module']),
            'variable': str(layer['variable']), 'mutable': bool(layer['mutable']), 'hideable': bool(layer['hideable']),
            'result_id': layer['result_id'], 'kind': kind, 'created': str(layer['created']), 'ready': layer['ready'],
            'fields': [str(row[0]) for row in old.execute('SELECT name FROM layer_fields WHERE layer_id=? '
                                                           'ORDER BY position', (layer_id,))],
            'tags': [str(row[0]) for row in old.execute('SELECT tag FROM layer_tags WHERE layer_id=? ORDER BY tag',
                                                         (layer_id,))],
            'sources': [str(row[0]) for row in old.execute('SELECT source_layer_id FROM layer_sources '
                                                            'WHERE layer_id=? ORDER BY rowid', (layer_id,))],
            'hidden': layer_id in hidden,
            'provenance': None if provenance is None else {
                'module': str(provenance['module']), 'workflow': provenance['workflow'], 'prompt': provenance['prompt'],
                'model': provenance['model'], 'role': provenance['role'],
                'blinded': None if provenance['blinded'] is None else int(provenance['blinded'])},
            'reexamine': [[str(row[0]), str(row[1])] for row in old.execute(
                'SELECT changed_in, thing_id FROM reexamine WHERE layer_id=? ORDER BY rowid', (layer_id,))]}))
    seen: set[str] = set()

    def refs_of(owner: str, row_number: int) -> list[list[str]]:
        return [[str(row[0]), str(row[1])] for row in old.execute(
            'SELECT key, value FROM refs WHERE owner=? AND owner_row=? ORDER BY position', (owner, row_number))]

    def version(kind: str, ident: str, row: Any, fields: dict[str, Any]) -> None:
        op = str(row['op'])
        mode = 'add' if op == 'add' else 'version'
        if op == 'add' and ident in seen:
            mode = 'add'
        seen.add(ident)
        ops.append((op, kind, ident, str(row['layer_id']),
                    {'mode': mode, 'reason': row['reason'], 'evidence': row['evidence'], **fields}))

    for row in old.execute('SELECT * FROM elements ORDER BY row').fetchall():
        version('element', str(row['element_id']), row, {'address': str(row['address']),
                                                          'name_length': row['name_length'], 'name': row['name'],
                                                          'role': row['role']})
    for row in old.execute('SELECT * FROM joins ORDER BY row').fetchall():
        held = [str(each[0]) for each in old.execute('SELECT element_id FROM join_elements WHERE join_row=? '
                                                     'ORDER BY position', (row['row'],))]
        version('join', str(row['join_id']), row, {'type': str(row['type']), 'receiver': str(row['receiver']),
                                                    'purpose': row['purpose'], 'ef': row['ef'], 'ifd': row['ifd'],
                                                    'element': row['element'], 'held': held})
    for row in old.execute('SELECT * FROM properties ORDER BY row').fetchall():
        version('property', str(row['property_id']), row, {'element_id': str(row['element_id']),
                                                            'value': str(row['value']), 'extra': row['extra'],
                                                            'refs': refs_of('property', int(row['row']))})
    for row in old.execute('SELECT * FROM items ORDER BY row').fetchall():
        version('item', str(row['item_id']), row, {'target_kind': str(row['target_kind']),
                                                    'target_id': str(row['target_id']), 'value': str(row['value']),
                                                    'link_kind': row['link_kind'], 'link_id': row['link_id'],
                                                    'extra': row['extra'], 'read_first': int(row['read_first']),
                                                    'always_show': int(row['always_show']),
                                                    'refs': refs_of('item', int(row['row']))})
    # Identities with no version: stubs and the ids of things a discarded layer wrote, kept in the registry.
    for ident, kind in old.execute('SELECT id, kind FROM identities ORDER BY rowid'):
        if str(ident) not in seen:
            ops.append(('remove', str(kind), str(ident), '', {'mode': 'place'}))
            seen.add(str(ident))
    for table, column, kind in (('element_ids', 'element_id', 'element'), ('join_ids', 'join_id', 'join'),
                                ('item_ids', 'item_id', 'item')):
        for (ident,) in old.execute(f'SELECT {column} FROM {table} ORDER BY rowid'):
            if str(ident) not in seen:
                ops.append(('remove', kind, str(ident), '', {'mode': 'place'}))
                seen.add(str(ident))
    held_addresses = {str(row[0]) for row in old.execute('SELECT DISTINCT address FROM elements')}
    for (address,) in old.execute('SELECT address FROM types ORDER BY address'):
        if str(address) not in held_addresses and not any(other.startswith(str(address) + '.') for other in held_addresses):
            ops.append(('add', 'type', str(address), '', {'address': str(address)}))
    for address, layer_id, kind in old.execute('SELECT address, layer_id, kind FROM selections ORDER BY rowid'):
        ops.append(('add', 'selection', f'{address}|{kind}|{layer_id}', str(layer_id),
                    {'address': str(address), 'layer_id': str(layer_id), 'kind': str(kind)}))
    return ops


# ---------------------------------------------------------------------------------- layouts 7 to 19, to layout 20

@dataclass(frozen=True)
class Kind:
    table: str
    id_column: str
    current: str


KINDS: dict[str, Kind] = {
    'element': Kind('elements', 'element_id', 'current_elements'),
    'join': Kind('joins', 'join_id', 'current_joins'),
    'property': Kind('properties', 'property_id', 'current_properties'),
    'item': Kind('items', 'item_id', 'current_items'),
}


def recompute(db: sqlite3.Connection, kind: str, ids: list[str]) -> None:
    """Rewrite the current rows of these things in a layout 20 store: each one's newest row, or none when that row
    is a removal."""
    spec = KINDS[kind]
    newest = [(thing_id, db.execute(f'SELECT * FROM {spec.table} WHERE {spec.id_column}=? ORDER BY row DESC LIMIT 1',
                                    (thing_id,)).fetchone()) for thing_id in ids]
    for thing_id, _ in newest:
        db.execute(f'DELETE FROM {spec.current} WHERE {spec.id_column}=?', (thing_id,))
    for thing_id, row in newest:
        if row is None or row['op'] == 'remove':
            continue
        if kind == 'element':
            db.execute('INSERT INTO current_elements(element_id, row, address, role) VALUES (?, ?, ?, ?)',
                       (thing_id, row['row'], row['address'], row['role']))
            db.execute('INSERT OR REPLACE INTO address_elements(address, element_id) VALUES (?, ?)',
                       (row['address'], thing_id))
        elif kind == 'join':
            db.execute('INSERT INTO current_joins(join_id, row, receiver) VALUES (?, ?, ?)',
                       (thing_id, row['row'], row['receiver']))
        elif kind == 'property':
            db.execute('INSERT INTO current_properties(property_id, row, layer_id, element_id) VALUES (?, ?, ?, ?)',
                       (thing_id, row['row'], row['layer_id'], row['element_id']))
        else:
            db.execute('INSERT INTO current_items(item_id, row, layer_id, target_kind, target_id, link_kind, link_id) '
                       'VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (thing_id, row['row'], row['layer_id'], row['target_kind'], row['target_id'], row['link_kind'],
                        row['link_id']))


def _legacy(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Update a copy of a store at layout 7 to 19 to layout 20 in one transaction."""
    target = sqlite3.connect(':memory:')
    target.executescript(LAYOUT_20 + '\n' + tables.extension_schema())
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
            db.execute("UPDATE joins SET type='purpose' WHERE type='require'")  # layout 18
        db.execute('DROP TABLE IF EXISTS temp.subtype_moves')
        problems = db.execute('PRAGMA foreign_key_check').fetchall()
        if problems:
            raise StoreError(f'{path} could not be updated to version 20: {len(problems)} references would break, '
                             f'the first in {problems[0][0]}. Nothing was changed.', 'metaform feedback')
        db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('prior_schema_version',?)", (found,))
        db.execute("UPDATE meta SET value='20' WHERE key='schema_version'")
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')
        db.row_factory = factory


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


EF_REASON = ('Layout 12, ef takes the old relation text; relation and observation are removed, '
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
    """Layout 10, an element's name and a join's IFD are fields of their own, no longer kept in its
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


SHAPE_REASON = "Layout 19, D115: the metaform goes back to its original shape."
SOURCES = 'sources'


def _to_shape(db: sqlite3.Connection, wanted: list[tuple[str, str, str]]) -> None:
    """Layout 19: a join holds the elements that serve it, and everything beyond the metaform's shape goes into layers.

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
        """A join's or a subtype join's name is the name of the element it holds; an element that has a name of its own keeps it."""
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
