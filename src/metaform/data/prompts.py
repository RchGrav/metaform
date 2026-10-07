"""Prompts as versioned records in the home's prompt store, and the version each layer was made from, STORE-044.

One prompt store serves the whole home, `prompts.sqlite3`, Q50. A saved edit
is a new version with its parent, and no version is ever changed, so the
version a layer is linked to always shows the exact text it was made from. A
module's shipped prompt becomes version 1 when first served and keeps flowing
in as later versions until someone saves an edit of their own.
"""
from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .. import home, sqlite
from ..errors import StoreError
from .records import Notice, Record

PROMPT_SCHEMA_VERSION = '2'  # the prompt database's own layout, apart from the store's, STORE-029
PROMPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS prompts(
  prompt_id TEXT PRIMARY KEY,
  name      TEXT NOT NULL UNIQUE,
  format    TEXT NOT NULL CHECK(format IN ('xml','markdown','text')),
  created   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prompt_versions(
  version_id TEXT PRIMARY KEY,
  prompt_id  TEXT NOT NULL REFERENCES prompts(prompt_id),
  number     INTEGER NOT NULL,
  parent_id  TEXT REFERENCES prompt_versions(version_id),
  text       TEXT NOT NULL,
  origin     TEXT NOT NULL CHECK(origin IN ('shipped','edited')),
  created    TEXT NOT NULL,
  UNIQUE(prompt_id, number)
);
CREATE INDEX IF NOT EXISTS prompt_versions_by_prompt ON prompt_versions(prompt_id, number DESC);
CREATE TABLE IF NOT EXISTS prompt_uses(
  project_id  TEXT NOT NULL,
  base_id TEXT NOT NULL,
  layer_id    TEXT NOT NULL,
  version_id  TEXT NOT NULL REFERENCES prompt_versions(version_id),
  PRIMARY KEY(project_id, base_id, layer_id)
);
CREATE INDEX IF NOT EXISTS prompt_uses_by_version ON prompt_uses(version_id);
"""
FORMATS = ('xml', 'markdown', 'text')


def _upgrade(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Version 2 names a use's base `base_id`, the change order of 2026-10-07 item 1."""
    if found != '1':
        raise StoreError(f'{path} has schema version {found}; this Metaform updates only prompt version 1.',
                         'install the Metaform release that wrote it')
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ('1',):
            db.execute('ALTER TABLE prompt_uses RENAME COLUMN metaform_id TO base_id')
            db.execute("UPDATE meta SET value=? WHERE key='schema_version'", (PROMPT_SCHEMA_VERSION,))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


@dataclass(frozen=True)
class Prompt(Record):
    prompt_id: str
    name: str
    format: str
    created: str
    newest: int


@dataclass(frozen=True)
class PromptVersion(Record):
    version_id: str
    prompt_id: str
    name: str
    format: str
    number: int
    parent_id: str | None
    text: str
    origin: str
    created: str
    notices: tuple[Notice, ...] = ()


@dataclass(frozen=True)
class PromptUse(Record):
    project_id: str
    base_id: str
    layer_id: str
    version_id: str


@contextmanager
def _db(*, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    with sqlite.opened(home.home() / 'prompts.sqlite3', PROMPT_SCHEMA, write=write,
                       version=PROMPT_SCHEMA_VERSION, upgrade=_upgrade) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')


def _version(row: sqlite3.Row, notices: tuple[Notice, ...] = ()) -> PromptVersion:
    return PromptVersion(row['version_id'], row['prompt_id'], row['name'], row['format'], int(row['number']),
                         row['parent_id'], row['text'], row['origin'], row['created'], notices)


_VERSION = ('SELECT v.*, p.name, p.format FROM prompt_versions v JOIN prompts p ON p.prompt_id = v.prompt_id '
            'WHERE v.prompt_id=? ')


def _prompt_row(db: sqlite3.Connection, prompt: str) -> sqlite3.Row:
    found = db.execute('SELECT * FROM prompts WHERE name=?', (prompt,)).fetchone() or \
        db.execute('SELECT * FROM prompts WHERE prompt_id=?', (prompt,)).fetchone()
    if found is None:
        raise StoreError(f'No prompt {prompt}.', 'metaform prompts')
    return found


def _newest(db: sqlite3.Connection, prompt_id: str) -> sqlite3.Row | None:
    return db.execute(_VERSION + 'ORDER BY v.number DESC LIMIT 1', (prompt_id,)).fetchone()


def _insert(db: sqlite3.Connection, prompt_id: str, number: int, parent: str | None, text: str,
            origin: str) -> str:
    version_id = uuid.uuid4().hex
    db.execute('INSERT INTO prompt_versions(version_id, prompt_id, number, parent_id, text, origin, created) '
               'VALUES (?, ?, ?, ?, ?, ?, ?)', (version_id, prompt_id, number, parent, text, origin, home.now()))
    return version_id


def add_prompt(name: str, format: str, text: str, *, origin: str = 'edited') -> PromptVersion:
    """Create a prompt and its version 1."""
    if format not in FORMATS:
        raise StoreError(f'{format} is not a prompt format: {", ".join(FORMATS)}.', 'metaform prompts')
    with _db(write=True) as db:
        if db.execute('SELECT 1 FROM prompts WHERE name=?', (name,)).fetchone():
            raise StoreError(f'There is already a prompt {name}.', f'metaform prompt {name}')
        prompt_id = uuid.uuid4().hex
        db.execute('INSERT INTO prompts(prompt_id, name, format, created) VALUES (?, ?, ?, ?)',
                   (prompt_id, name, format, home.now()))
        version_id = _insert(db, prompt_id, 1, None, text, origin)
        return _version(db.execute(_VERSION + 'AND v.version_id=?', (prompt_id, version_id)).fetchone())


def add_prompt_version(prompt: str, text: str, parent: int | str, *, origin: str = 'edited') -> PromptVersion:
    """The next version of a prompt, edited from `parent`, a number or a version id; no row ever changes. Text the
    same as the parent's returns the parent with a notice, BASE-044."""
    with _db(write=True) as db:
        record = _prompt_row(db, prompt)
        return _edit(db, record, text, parent, origin)


def _edit(db: sqlite3.Connection, record: sqlite3.Row, text: str, parent: int | str,
          origin: str = 'edited') -> PromptVersion:
    column = 'number' if isinstance(parent, int) else 'version_id'
    base = db.execute(_VERSION + f'AND v.{column}=?', (record['prompt_id'], parent)).fetchone()
    if base is None:
        raise StoreError(f'Prompt {record["name"]} has no version {parent}.', f'metaform prompt {record["name"]}')
    if base['text'] == text:
        return _version(base, (Notice('text', f'The text is the same as version {base["number"]}; no version '
                                              'was added.'),))
    newest = _newest(db, record['prompt_id'])
    assert newest is not None
    version_id = _insert(db, record['prompt_id'], int(newest['number']) + 1, base['version_id'], text, origin)
    return _version(db.execute(_VERSION + 'AND v.version_id=?', (record['prompt_id'], version_id)).fetchone())


def save_prompt(name: str, text: str, *, format: str = 'text', parent: int | None = None) -> PromptVersion:
    """Create a named prompt or append an edit atomically, using the newest parent when omitted.

    Format describes a new prompt only; an existing prompt keeps its format. A specified parent must exist,
    including when the name is new, so a misspelled name cannot silently lose the intended version lineage.
    """
    if format not in FORMATS:
        raise StoreError(f'{format} is not a prompt format: {", ".join(FORMATS)}.', 'metaform prompts')
    with _db(write=True) as db:
        record = db.execute('SELECT * FROM prompts WHERE name=?', (name,)).fetchone()
        if record is not None:
            newest = _newest(db, record['prompt_id'])
            assert newest is not None
            return _edit(db, record, text, int(newest['number']) if parent is None else parent)
        if parent is not None:
            raise StoreError(f'Prompt {name} has no version {parent}.', f'metaform prompt {name}')
        prompt_id = uuid.uuid4().hex
        db.execute('INSERT INTO prompts(prompt_id, name, format, created) VALUES (?, ?, ?, ?)',
                   (prompt_id, name, format, home.now()))
        version_id = _insert(db, prompt_id, 1, None, text, 'edited')
        return _version(db.execute(_VERSION + 'AND v.version_id=?', (prompt_id, version_id)).fetchone())


def shipped(name: str, format: str, text: str) -> PromptVersion:
    """The version to serve of a module's shipped prompt: made version 1 when first served, and the shipped text
    again as the next version when it has changed and nobody has saved an edit since, STORE-044."""
    with _db() as db:
        found = db.execute('SELECT * FROM prompts WHERE name=?', (name,)).fetchone()
        newest = _newest(db, found['prompt_id']) if found is not None else None
    if found is None:
        return add_prompt(name, format, text, origin='shipped')
    assert newest is not None
    if newest['text'] == text or newest['origin'] == 'edited':
        return _version(newest)
    with _db(write=True) as db:
        again = _newest(db, found['prompt_id'])
        assert again is not None
        if again['version_id'] != newest['version_id']:  # another writer came first
            return _version(again)
        version_id = _insert(db, found['prompt_id'], int(again['number']) + 1, again['version_id'], text, 'shipped')
        return _version(db.execute(_VERSION + 'AND v.version_id=?', (found['prompt_id'], version_id)).fetchone())


def prompts() -> tuple[Prompt, ...]:
    """Every prompt with its newest version number; the list is the table, so it is read whole, STORE-005."""
    with _db() as db:
        rows = db.execute('SELECT p.*, (SELECT MAX(number) FROM prompt_versions v WHERE v.prompt_id = p.prompt_id) '
                          'AS newest FROM prompts p ORDER BY p.name').fetchall()
        return tuple(Prompt(row['prompt_id'], row['name'], row['format'], row['created'], int(row['newest']))
                     for row in rows)


def prompt_version(prompt: str, number: int | None = None) -> PromptVersion:
    """One version by number, or the newest."""
    with _db() as db:
        record = _prompt_row(db, prompt)
        found = _newest(db, record['prompt_id']) if number is None else \
            db.execute(_VERSION + 'AND v.number=?', (record['prompt_id'], number)).fetchone()
        if found is None:
            raise StoreError(f'Prompt {record["name"]} has no version {number}.', f'metaform prompt {record["name"]}')
        return _version(found)


def prompt_versions(prompt: str) -> tuple[PromptVersion, ...]:
    """Every version of a prompt, newest first."""
    with _db() as db:
        record = _prompt_row(db, prompt)
        return tuple(_version(row) for row in db.execute(_VERSION + 'ORDER BY v.number DESC',
                                                         (record['prompt_id'],)))


def record_use(version_id: str, project_id: str, base_id: str, layer_id: str) -> None:
    """Link a layer to the version it was made from; a layer is made once, so its link never changes."""
    with _db(write=True) as db:
        db.execute('INSERT OR IGNORE INTO prompt_uses(project_id, base_id, layer_id, version_id) '
                   'VALUES (?, ?, ?, ?)', (project_id, base_id, layer_id, version_id))


def layers_by_prompt_version(version_id: str) -> tuple[PromptUse, ...]:
    with _db() as db:
        return tuple(PromptUse(row['project_id'], row['base_id'], row['layer_id'], row['version_id'])
                     for row in db.execute('SELECT * FROM prompt_uses WHERE version_id=? ORDER BY project_id, '
                                           'base_id, layer_id', (version_id,)))


def use_of(project_id: str, base_id: str, layer_id: str) -> PromptVersion | None:
    """The version a layer was made from, if it came from a stored prompt."""
    with _db() as db:
        found = db.execute('SELECT version_id FROM prompt_uses WHERE project_id=? AND base_id=? AND layer_id=?',
                           (project_id, base_id, layer_id)).fetchone()
        if found is None:
            return None
        row = db.execute('SELECT v.*, p.name, p.format FROM prompt_versions v JOIN prompts p '
                         'ON p.prompt_id = v.prompt_id WHERE v.version_id=?', (found[0],)).fetchone()
        return _version(row)
