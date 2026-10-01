"""Bringing a metaform store written at an earlier layout up to the current one, STORE-029.

Rich, 2026-10-01: the version changes only for a change that requires an update, and the store is updated, never
thrown away. Layout 7 to 8, LAYER-025: a thing is no longer unique per layer, `reexamine.correction_layer_id` is
`changed_in`, and there are no correction layers, so each correction layer's versions are folded into the intake
layer it refined, after that layer's own versions, and the intake layer is named `intake`. A copy of the file is
kept under the home's backups before anything is changed.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .. import home
from ..errors import StoreError
from .schema import STORE_SCHEMA
from .versions import KINDS, recompute

RENAMED = {'reexamine': {'changed_in': 'correction_layer_id'}}  # a new column read from its old name
VERSIONED = ('elements', 'joins', 'items', 'properties')
LAYERED = VERSIONED + ('item_ids', 'current_items', 'current_properties', 'reports', 'plans')  # kept, moved to the intake
SETTINGS = ('hidden_layers', 'layer_fields', 'layer_tags', 'provenance', 'selections')  # the correction layer's own
LEFT_OUT = {'layers': "kind <> 'correction'"}  # rows the new layout cannot hold; folded below


def upgrade(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Update a store at layout 7 to layout 8 in one transaction, after keeping a copy of it."""
    if found != '7':
        raise StoreError(f'{path} has schema version {found}; this Metaform updates only version 7.',
                         'install the Metaform release that wrote it')
    _backup(db, path)
    target = sqlite3.connect(':memory:')
    target.executescript(STORE_SCHEMA)
    wanted = target.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall()
    target.close()
    factory = db.row_factory
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=OFF')
    db.execute('BEGIN IMMEDIATE')
    try:
        stack = [row[0] for row in db.execute('SELECT layer_id FROM correction_stack ORDER BY position')]
        stack += [row[0] for row in db.execute("SELECT layer_id FROM layers WHERE kind='correction'")
                  if row[0] not in stack]
        _relayout(db, wanted)
        for layer_id in stack:
            _fold(db, layer_id)
        _name_intake(db)
        for kind in KINDS.values():
            ids = [row[0] for row in db.execute(f'SELECT DISTINCT {kind.id_column} FROM {kind.table}')]
            recompute(db, _kind_name(kind.table), ids)
        problems = db.execute('PRAGMA foreign_key_check').fetchall()
        if problems:
            raise StoreError(f'{path} could not be updated to version 8: {len(problems)} references would break, '
                             f'the first in {problems[0][0]}. Nothing was changed.', 'metaform feedback')
        db.execute("UPDATE meta SET value='8' WHERE key='schema_version'")
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise
    finally:
        db.execute('PRAGMA foreign_keys=ON')
        db.row_factory = factory


def _backup(db: sqlite3.Connection, path: Path) -> None:
    folder = home.home() / 'backups' / 'upgrade-8' / home.now().replace(':', '').replace('-', '') / path.parent.name
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
    tables = {name: sql for kind, name, sql in wanted if kind == 'table'}
    for name in have:
        if name not in tables and not name.startswith('sqlite_'):
            db.execute(f'DROP TABLE "{name}"')
    for name, sql in tables.items():
        if name not in have:
            db.execute(sql)
            continue
        if _plain(have[name]) == _plain(sql):
            continue
        old = [row[1] for row in db.execute(f'PRAGMA table_info("{name}")')]
        db.execute(re.sub(rf'^CREATE TABLE\s+"?{name}"?\s*\(', f'CREATE TABLE "{name}__8"(', sql, count=1))
        new = [row[1] for row in db.execute(f'PRAGMA table_info("{name}__8")')]
        sources = [RENAMED.get(name, {}).get(column, column) for column in new]
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


def _plain(sql: str) -> str:
    return ' '.join(sql.replace('IF NOT EXISTS ', '').split())


def _fold(db: sqlite3.Connection, correction: str) -> None:
    """Move one correction layer's versions into the intake layer it refined; its rows keep their row numbers,
    which come after the intake's own, so they stay the newest versions."""
    intake = _refined(db, correction)
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
