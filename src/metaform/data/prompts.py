"""Prompts as versioned records in the home's prompt store, and the version each layer was made from, STORE-044.

One prompt store serves the whole home, `prompts.sqlite3`, Q50. A saved edit
is a new version with its parent, and no version is ever changed, so the
version a layer is linked to always shows the exact text it was made from. A
module's shipped prompt becomes version 1 when first served and keeps flowing
in as later versions until someone saves an edit of their own. From then on the
edit is served, and a shipped text that changes behind it is kept beside the
edit, so the person sees their edit is behind and can merge or drop it.
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import home, sqlite
from ..errors import StoreError
from .records import Notice, Record

PROMPT_SCHEMA_VERSION = '7'  # the prompt database's own layout, apart from the store's, STORE-029
# Version 7 merges duplicate canonical identities and retains name and ID aliases.
PROMPT_COMPATIBLE_FROM = '4'
# prompt_shipped: the text a module ships now, kept beside the edit it is behind while that edit is the newest version,
# one row for each edit; never served from here, only shown, ticket 3a1306bd (2026-10-15)
SHIPPED_TABLE = """CREATE TABLE IF NOT EXISTS prompt_shipped(
  version_id TEXT PRIMARY KEY REFERENCES prompt_versions(version_id),
  text       TEXT NOT NULL,
  seen       TEXT NOT NULL
);"""
MERGE_TABLE = """CREATE TABLE IF NOT EXISTS prompt_merges(
  prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
  migration_id TEXT NOT NULL,
  state TEXT NOT NULL,
  before_version_id TEXT NOT NULL REFERENCES prompt_versions(version_id),
  after_version_id TEXT NOT NULL REFERENCES prompt_versions(version_id),
  details TEXT NOT NULL,
  created TEXT NOT NULL,
  PRIMARY KEY(prompt_id, migration_id)
);"""
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
CREATE TABLE IF NOT EXISTS prompt_aliases(
  alias TEXT PRIMARY KEY,
  prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id)
);
""" + SHIPPED_TABLE + '\n' + MERGE_TABLE + '\n'
FORMATS = ('xml', 'markdown', 'text')


def _address(name: str) -> str:
    """The canonical identity of a legacy module or skill prompt, CTX-082."""
    if name == 'prompt-lexicalization':
        return 'prompt.workflow:prompt-lexicalization'
    if name in ('skills:workflow-logic', 'prompt.skills:workflow-logic'):
        return 'prompt.skills:workflow-prompt'
    if name in ('axiom-language', 'metaform-system', 'namespace-rules', 'workflow-logic',
                'workflow-prompt', 'metaform-tools', 'delexicalization-rules',
                'lib_axiom', 'lib_metaform', 'lib_workflow', 'lib_quality'):
        return 'prompt.skills:' + ('workflow-prompt' if name == 'workflow-logic' else name)
    if name.startswith('skill:'):
        return 'prompt.skill.' + name[6:]
    if name.startswith('logic.skill.'):
        return 'prompt.skill.' + name[len('logic.skill.'):]
    if re.fullmatch(r'[A-Za-z_][\w.-]*:.+', name) and not name.startswith('prompt.'):
        return 'prompt.' + name
    return name


def _merge(db: sqlite3.Connection, source: str, target: str) -> None:
    """Keep version identities and lineage while ordering both histories by write time."""
    versions = db.execute('SELECT version_id FROM prompt_versions WHERE prompt_id IN (?,?) '
                          'ORDER BY created,rowid', (source, target)).fetchall()
    if versions:
        selected = db.execute('SELECT prompt_id FROM prompt_versions WHERE version_id=?', versions[-1]).fetchone()[0]
        db.execute('UPDATE prompts SET format=(SELECT format FROM prompts WHERE prompt_id=?) WHERE prompt_id=?',
                   (selected, target))
    # Negative temporary numbers avoid UNIQUE(prompt_id, number) collisions during the move.
    for number, (version_id,) in enumerate(versions, 1):
        db.execute('UPDATE prompt_versions SET number=? WHERE version_id=?', (-number, version_id))
    db.execute('UPDATE prompt_versions SET prompt_id=? WHERE prompt_id=?', (target, source))
    for number, (version_id,) in enumerate(versions, 1):
        db.execute('UPDATE prompt_versions SET number=? WHERE version_id=?', (number, version_id))
    for (migration,) in db.execute('SELECT migration_id FROM prompt_merges WHERE prompt_id=?', (source,)).fetchall():
        identity = migration
        while db.execute('SELECT 1 FROM prompt_merges WHERE prompt_id=? AND migration_id=?',
                         (target, identity)).fetchone():
            identity += ':' + source
        db.execute('UPDATE prompt_merges SET prompt_id=?,migration_id=? WHERE prompt_id=? AND migration_id=?',
                   (target, identity, source, migration))
    db.execute('UPDATE prompt_aliases SET prompt_id=? WHERE prompt_id=?', (target, source))
    db.execute('INSERT OR REPLACE INTO prompt_aliases VALUES (?,?)', (source, target))
    db.execute('DELETE FROM prompts WHERE prompt_id=?', (source,))


def _compatibility(db: sqlite3.Connection) -> None:
    """Keep the old SQL surface writable for processes whose prompt code is already loaded."""
    if db.execute("SELECT type FROM sqlite_master WHERE name='prompts'").fetchone()[0] == 'view':
        return
    db.execute('ALTER TABLE prompts RENAME TO prompt_records')
    # Aliases project the canonical ID, so old readers and writers share the same version history.
    db.execute("""CREATE VIEW prompts AS
        SELECT * FROM prompt_records
        UNION SELECT r.prompt_id,a.alias,r.format,r.created FROM prompt_records r
              JOIN prompt_aliases a ON a.prompt_id=r.prompt_id
        UNION SELECT prompt_id,substr(name,8),format,created FROM prompt_records
              WHERE name LIKE 'prompt.%:%'
        UNION SELECT prompt_id,'skill:'||substr(name,14),format,created FROM prompt_records
              WHERE name LIKE 'prompt.skill.%'
        UNION SELECT prompt_id,'logic.skill.'||substr(name,14),format,created FROM prompt_records
              WHERE name LIKE 'prompt.skill.%'
        UNION SELECT prompt_id,substr(name,15),format,created FROM prompt_records
              WHERE name LIKE 'prompt.skills:%'
        UNION SELECT prompt_id,'workflow-logic',format,created FROM prompt_records
              WHERE name='prompt.skills:workflow-prompt'
        UNION SELECT prompt_id,'skills:workflow-logic',format,created FROM prompt_records
              WHERE name='prompt.skills:workflow-prompt'
        UNION SELECT prompt_id,'prompt-lexicalization',format,created FROM prompt_records
              WHERE name='prompt.workflow:prompt-lexicalization'""")
    db.execute("""CREATE TRIGGER prompts_insert INSTEAD OF INSERT ON prompts BEGIN
        INSERT INTO prompt_records(prompt_id,name,format,created) VALUES(NEW.prompt_id,
          CASE WHEN NEW.name LIKE 'prompt.%' THEN NEW.name
               WHEN NEW.name='prompt-lexicalization' THEN 'prompt.workflow:prompt-lexicalization'
               WHEN NEW.name IN ('workflow-logic','skills:workflow-logic') THEN 'prompt.skills:workflow-prompt'
               WHEN NEW.name IN ('axiom-language','metaform-system','namespace-rules','workflow-prompt',
                    'metaform-tools','delexicalization-rules','lib_axiom','lib_metaform','lib_workflow','lib_quality')
                    THEN 'prompt.skills:'||NEW.name
               WHEN NEW.name LIKE 'skill:%' THEN 'prompt.skill.'||substr(NEW.name,7)
               WHEN NEW.name LIKE 'logic.skill.%' THEN 'prompt.skill.'||substr(NEW.name,13)
               WHEN instr(NEW.name,':')>0 THEN 'prompt.'||NEW.name ELSE NEW.name END,
          NEW.format,NEW.created);
        END""")
    db.execute("""CREATE TRIGGER prompts_update INSTEAD OF UPDATE ON prompts BEGIN
        UPDATE prompt_records SET name=NEW.name,format=NEW.format,created=NEW.created
          WHERE prompt_id=OLD.prompt_id;
        END""")
    db.execute("""CREATE TRIGGER prompts_delete INSTEAD OF DELETE ON prompts BEGIN
        DELETE FROM prompt_records WHERE prompt_id=OLD.prompt_id;
        END""")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('prompt_compatibility','7')")


def _upgrade(db: sqlite3.Connection, path: Path, found: str) -> None:
    """Merge legacy names atomically; newer selections win without losing any version."""
    if found not in ('1', '2', '3', '4', '5', '6'):
        raise StoreError(f'{path} has schema version {found}; this Metaform updates prompt versions 1 through 6.',
                         'install the Metaform release that wrote it')
    db.execute('BEGIN IMMEDIATE')
    try:
        at = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if at != (PROMPT_SCHEMA_VERSION,):
            if at == ('1',):
                db.execute('ALTER TABLE prompt_uses RENAME COLUMN metaform_id TO base_id')
            db.execute(SHIPPED_TABLE)
            db.execute(MERGE_TABLE)
            db.execute('CREATE TABLE IF NOT EXISTS prompt_aliases(alias TEXT PRIMARY KEY, '
                       'prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id))')
            for source, name in db.execute('SELECT prompt_id,name FROM prompts ORDER BY name').fetchall():
                target_name = _address(name)
                if target_name == name:
                    continue
                target = db.execute('SELECT prompt_id FROM prompts WHERE name=?', (target_name,)).fetchone()
                identity = source if target is None else target[0]
                if target is None:
                    db.execute('UPDATE prompts SET name=? WHERE prompt_id=?', (target_name, source))
                else:
                    _merge(db, source, identity)
                db.execute('INSERT OR REPLACE INTO prompt_aliases VALUES (?,?)', (name, identity))
            _compatibility(db)
            sqlite.stamp(db, PROMPT_SCHEMA_VERSION, PROMPT_COMPATIBLE_FROM)
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
class Behind(Record):
    """An edit that is served while its module now ships another text: the edit's number, and the shipped text."""
    name: str
    number: int
    text: str
    seen: str


@dataclass(frozen=True)
class PromptUse(Record):
    project_id: str
    base_id: str
    layer_id: str
    version_id: str


@contextmanager
def _db(*, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
    with sqlite.opened(home.home() / 'prompts.sqlite3', PROMPT_SCHEMA, write=write,
                       version=PROMPT_SCHEMA_VERSION, compatible=PROMPT_COMPATIBLE_FROM, upgrade=_upgrade) as db:
        if db.execute("SELECT value FROM meta WHERE key='prompt_compatibility'").fetchone() is None:
            db.execute('BEGIN IMMEDIATE')
            try:
                _compatibility(db)
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
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


_VERSION = ('SELECT v.*, p.name, p.format FROM prompt_versions v JOIN prompt_records p ON p.prompt_id = v.prompt_id '
            'WHERE v.prompt_id=? ')


def _prompt_row(db: sqlite3.Connection, prompt: str) -> sqlite3.Row:
    found = db.execute('SELECT * FROM prompt_records WHERE name=?', (_address(prompt),)).fetchone() or \
        db.execute('SELECT * FROM prompt_records WHERE prompt_id=?', (prompt,)).fetchone() or \
        db.execute('SELECT p.* FROM prompt_records p JOIN prompt_aliases a ON a.prompt_id=p.prompt_id WHERE a.alias=?',
                   (prompt,)).fetchone()
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


def _create(db: sqlite3.Connection, name: str, format: str, text: str, origin: str) -> PromptVersion:
    prompt_id = uuid.uuid4().hex
    db.execute('INSERT INTO prompts(prompt_id, name, format, created) VALUES (?, ?, ?, ?)',
               (prompt_id, name, format, home.now()))
    version_id = _insert(db, prompt_id, 1, None, text, origin)
    return _version(db.execute(_VERSION + 'AND v.version_id=?', (prompt_id, version_id)).fetchone())


def add_prompt(name: str, format: str, text: str, *, origin: str = 'edited') -> PromptVersion:
    """Create a prompt and its version 1."""
    if format not in FORMATS:
        raise StoreError(f'{format} is not a prompt format: {", ".join(FORMATS)}.', 'metaform prompts')
    name = _address(name)
    with _db(write=True) as db:
        if db.execute('SELECT 1 FROM prompt_records WHERE name=?', (name,)).fetchone():
            raise StoreError(f'There is already a prompt {name}.', f'metaform prompt {name}')
        return _create(db, name, format, text, origin)


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
    name = _address(name)
    with _db(write=True) as db:
        record = db.execute('SELECT * FROM prompt_records WHERE name=?', (name,)).fetchone()
        if record is not None:
            newest = _newest(db, record['prompt_id'])
            assert newest is not None
            return _edit(db, record, text, int(newest['number']) if parent is None else parent)
        if parent is not None:
            raise StoreError(f'Prompt {name} has no version {parent}.', f'metaform prompt {name}')
        return _create(db, name, format, text, 'edited')


def merge_selected(prompt: str, migration_id: str,
                   transform: Callable[[PromptVersion], tuple[str, list[str]]], *,
                   source: Mapping[str, Any] | None = None, retry: bool = False) -> dict[str, Any]:
    """Apply an exact selected-source merge once, preserving prompt identity and every immutable version.

    `transform` runs on the current selected version under the same transaction as its append. It returns the new
    stored text and any conflicts; conflicts keep the selection unchanged. A recorded migration never changes a
    later user edit. Explicit `retry` retries a previously conflicted merge against the current selection.
    """
    with _db(write=True) as db:
        record = _prompt_row(db, prompt)
        prior = db.execute('SELECT * FROM prompt_merges WHERE prompt_id=? AND migration_id=?',
                           (record['prompt_id'], migration_id)).fetchone()
        if prior is not None and not (retry and prior['state'] == 'conflict'):
            return {'name': record['name'], 'migration_id': migration_id, 'state': prior['state'],
                    'before_version_id': prior['before_version_id'], 'after_version_id': prior['after_version_id'],
                    **json.loads(prior['details'])}
        newest = _newest(db, record['prompt_id'])
        assert newest is not None
        before = _version(newest)
        after, conflicts = before, []
        state = 'shipped'
        if before.origin == 'edited':
            text, conflicts = transform(before)
            state = 'conflict' if conflicts else 'already_applied' if text == before.text else 'applied'
            if state == 'applied':
                after = _edit(db, record, text, before.version_id)
        details = {'conflicts': conflicts, 'source': dict(source or {}),
                   'before_number': before.number, 'after_number': after.number}
        db.execute('INSERT INTO prompt_merges(prompt_id,migration_id,state,before_version_id,after_version_id,'
                   'details,created) VALUES (?,?,?,?,?,?,?) ON CONFLICT(prompt_id,migration_id) DO UPDATE SET '
                   'state=excluded.state,before_version_id=excluded.before_version_id,'
                   'after_version_id=excluded.after_version_id,details=excluded.details,created=excluded.created',
                   (record['prompt_id'], migration_id, state, before.version_id, after.version_id,
                    json.dumps(details, sort_keys=True), home.now()))
        return {'name': record['name'], 'migration_id': migration_id, 'state': state,
                'before_version_id': before.version_id, 'after_version_id': after.version_id, **details}


def prompt_merges(prompt: str | None = None) -> list[dict[str, Any]]:
    """Selected-source migration evidence, including exact input/output versions and conflicts left untouched."""
    with _db() as db:
        sql = ('SELECT m.*, p.name FROM prompt_merges m JOIN prompt_records p ON p.prompt_id=m.prompt_id'
               + (' WHERE p.name=?' if prompt else '') + ' ORDER BY m.created,m.migration_id')
        rows = db.execute(sql, (_address(prompt),) if prompt else ()).fetchall()
    return [{'name': row['name'], 'migration_id': row['migration_id'], 'state': row['state'],
             'before_version_id': row['before_version_id'], 'after_version_id': row['after_version_id'],
             'created': row['created'], **json.loads(row['details'])} for row in rows]


def shipped(name: str, format: str, text: str) -> PromptVersion:
    """The version to serve of a module's shipped prompt: made version 1 when first served, and the shipped text
    again as the next version when it has changed and nobody has saved an edit since, STORE-044."""
    name = _address(name)
    with _db() as db:
        found = db.execute('SELECT * FROM prompt_records WHERE name=?', (name,)).fetchone()
        newest = _newest(db, found['prompt_id']) if found is not None else None
    if found is None:
        if format not in FORMATS:
            raise StoreError(f'{format} is not a prompt format: {", ".join(FORMATS)}.', 'metaform prompts')
        with _db(write=True) as db:
            if db.execute('SELECT 1 FROM prompt_records WHERE name=?', (name,)).fetchone() is None:
                return _create(db, name, format, text, 'shipped')
        return shipped(name, format, text)  # another writer made it first, as two agents starting at once do
    assert newest is not None
    if newest['origin'] == 'edited':
        _note_behind(newest, text)
        return _version(newest)
    if newest['text'] == text:
        return _version(newest)
    with _db(write=True) as db:
        again = _newest(db, found['prompt_id'])
        assert again is not None
        if again['version_id'] != newest['version_id']:  # another writer came first
            return _version(again)
        version_id = _insert(db, found['prompt_id'], int(again['number']) + 1, again['version_id'], text, 'shipped')
        return _version(db.execute(_VERSION + 'AND v.version_id=?', (found['prompt_id'], version_id)).fetchone())


def _note_behind(edit: sqlite3.Row, text: str) -> None:
    """Keep the shipped text beside the edit served in its place when the module ships a text the edit was not made
    over: neither the edit's own text nor the last shipped version's. Nothing is written when that is already kept,
    and the row goes when the shipped text comes back to one of those, ticket 3a1306bd."""
    with _db() as db:
        kept = db.execute('SELECT text FROM prompt_shipped WHERE version_id=?', (edit['version_id'],)).fetchone()
        last = db.execute("SELECT text FROM prompt_versions WHERE prompt_id=? AND origin='shipped' "
                          'ORDER BY number DESC LIMIT 1', (edit['prompt_id'],)).fetchone()
    behind = text != edit['text'] and (last is None or text != last['text'])
    if (kept is not None and kept['text'] == text) or (kept is None and not behind):
        return
    with _db(write=True) as db:
        if behind:
            db.execute('INSERT INTO prompt_shipped(version_id, text, seen) VALUES (?, ?, ?) ON CONFLICT(version_id) '
                       'DO UPDATE SET text=excluded.text, seen=excluded.seen', (edit['version_id'], text, home.now()))
        else:
            db.execute('DELETE FROM prompt_shipped WHERE version_id=?', (edit['version_id'],))


def edits() -> dict[str, str]:
    """Every prompt whose newest version is an edit, by name, with that version's text: what is sent in place of the
    shipped text, read in one pass, STORE-044."""
    with _db() as db:
        rows = db.execute("SELECT p.name, v.text FROM prompt_records p JOIN prompt_versions v ON v.prompt_id = p.prompt_id "
                          "WHERE v.origin='edited' AND v.number = (SELECT MAX(number) FROM prompt_versions n "
                          'WHERE n.prompt_id = p.prompt_id)').fetchall()
    return {str(row['name']): str(row['text']) for row in rows}


def store_path() -> Path:
    """The home's prompt store file."""
    return home.home() / 'prompts.sqlite3'


def behind(prompt: str) -> Behind | None:
    """The shipped text the served edit of a prompt is behind, when its newest version is an edit and its module now
    ships a text the edit was not made over; None otherwise, and for a prompt the store does not hold."""
    prompt = _address(prompt)
    with _db() as db:
        record = db.execute('SELECT * FROM prompt_records WHERE name=?', (prompt,)).fetchone()
        newest = _newest(db, record['prompt_id']) if record is not None else None
        if newest is None or newest['origin'] != 'edited':
            return None
        found = db.execute('SELECT text, seen FROM prompt_shipped WHERE version_id=?',
                           (newest['version_id'],)).fetchone()
    return None if found is None else Behind(prompt, int(newest['number']), found['text'], found['seen'])


def prompts() -> tuple[Prompt, ...]:
    """Every prompt with its newest version number; the list is the table, so it is read whole, STORE-005."""
    with _db() as db:
        rows = db.execute('SELECT p.*, (SELECT MAX(number) FROM prompt_versions v WHERE v.prompt_id = p.prompt_id) '
                          'AS newest FROM prompt_records p ORDER BY p.name').fetchall()
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
        row = db.execute('SELECT v.*, p.name, p.format FROM prompt_versions v JOIN prompt_records p '
                         'ON p.prompt_id = v.prompt_id WHERE v.version_id=?', (found[0],)).fetchone()
        return _version(row)
