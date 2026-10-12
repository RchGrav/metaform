"""A module's own tables, declared through the public base and reached through the data access object, STORE-045.

A module declares `Tables(version, tables, upgrade=None, compatible_from=None)`, each `Table` with its columns, its
key, its indexes and its place: `metaform`, beside the map in the metaform's store, or `project`, in a store of the
project that outlives a clear of its metaforms, `projects/<project>/modules/<module>.sqlite3`. A module table is
named `"<module>.<table>"`; an imported SQL declaration retains its existing physical name.

Each store that holds a module's tables records the module's version, the oldest version whose code still reads and
writes them, and the declaration of the tables it holds in its `meta` table under `module:<id>`, so a module's change
never changes the chassis store layout, STORE-029, and export, import and the chassis's own upgrade can carry the
tables without the module loaded.

`TableTx` reads and writes them in one transaction on the store of the first table it touches, STORE-006, every read
through the key's index or a declared index, STORE-005. A declared `Data` operation can also issue SQL through its
current DAO transaction.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from .. import home, sqlite
from ..errors import StoreError
from .paging import LIMIT
from .records import Page

Place = Literal['metaform', 'project']
ColumnKind = Literal['text', 'int', 'real', 'bool', 'json']
PLACES: tuple[Place, ...] = get_args(Place)
KINDS: tuple[ColumnKind, ...] = get_args(ColumnKind)
SQL_TYPE = {'text': 'TEXT', 'int': 'INTEGER', 'real': 'REAL', 'bool': 'INTEGER', 'json': 'TEXT'}
NAME = re.compile(r'^[a-z][a-z0-9_]{0,62}$')
MODULE_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
# A table no module owns any more keeps the physical name it was held under, `<module>.<table>` included.
PHYSICAL = re.compile(r'^(?:[A-Za-z0-9_-]{1,64}\.)?[a-z][a-z0-9_]{0,62}$')
META_PREFIX = 'module:'
# A project-level module store holds only its meta table and the module's tables; its own layout, STORE-029.
MODULE_STORE_SCHEMA = 'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);\n'
MODULE_STORE_VERSION = '1'
MODULE_STORE_COMPATIBLE_FROM = '1'  # its first layout, STORE-029
Row = dict[str, Any]


@dataclass(frozen=True)
class Column:
    """One column of a module's table. `required` means it never holds null; `default` fills it when not given."""
    name: str
    kind: ColumnKind = 'text'
    required: bool = False
    default: Any = None

    def __post_init__(self) -> None:
        if not NAME.fullmatch(self.name):
            raise ValueError(f'Column {self.name!r}: a name is lowercase letters, digits and _, starting with a letter.')
        if self.kind not in KINDS:
            raise ValueError(f'Column {self.name}: kind must be one of {", ".join(KINDS)}.')


@dataclass(frozen=True)
class Index:
    """An index on columns of a table: a read with equal values for its leading columns goes through it."""
    columns: tuple[str, ...]
    unique: bool = False

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError('An index names at least one column.')


@dataclass(frozen=True)
class Table:
    """One table a module declares, with its key and indexes, kept beside the map or in the project's store."""
    name: str
    columns: tuple[Column, ...]
    key: tuple[str, ...]
    indexes: tuple[Index, ...] = ()
    place: Place = 'metaform'
    schema: str | None = None
    exchange: bool = False
    on_remove: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self) -> None:
        if not (NAME if self.schema is None else PHYSICAL).fullmatch(self.name):
            raise ValueError(f'Table {self.name!r}: a name is lowercase letters, digits and _, starting with a letter.')
        if self.place not in PLACES:
            raise ValueError(f'Table {self.name}: place must be metaform or project.')
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError(f'Table {self.name}: two columns share one name.')
        if not self.key or any(name not in names for name in self.key) or len(set(self.key)) != len(self.key):
            raise ValueError(f'Table {self.name}: its key names one or more of its own columns, each once.')
        for kind, column, action in self.on_remove:
            if not NAME.fullmatch(kind) or column not in names or action not in ('delete', 'null'):
                raise ValueError(f'Table {self.name}: removal names a native kind, its column and delete or null.')
        for index in self.indexes:
            if any(name not in names for name in index.columns) or len(set(index.columns)) != len(index.columns):
                raise ValueError(f'Table {self.name}: an index names its own columns, each once.')

    def column(self, name: str) -> Column:
        return next(column for column in self.columns if column.name == name)

    def to_dict(self) -> dict[str, Any]:
        """The declaration as recorded in a store's meta and carried by an export."""
        value: dict[str, Any] = {'name': self.name, 'place': self.place, 'key': list(self.key),
                'columns': [[column.name, column.kind, column.required, column.default] for column in self.columns],
                'indexes': [[list(index.columns), index.unique] for index in self.indexes]}
        if self.schema is not None:
            value.update(schema=self.schema, exchange=self.exchange)
        if self.on_remove:
            value['on_remove'] = [list(rule) for rule in self.on_remove]
        return value

    @classmethod
    def from_sql(cls, name: str, schema: str, *, exchange: bool = True,
                 on_remove: tuple[tuple[str, str, str], ...] = (), unowned: bool = False) -> Table:
        """Declare a table with its existing SQL name and constraints, adopting rows already held there.

        Only CREATE TABLE and CREATE INDEX statements for this table belong to its declaration. `unowned` retains a
        table no module declares under its physical name, which may be another module's `<module>.<table>`.
        """
        if not (PHYSICAL if unowned else NAME).fullmatch(name):
            raise ValueError(f'Table {name!r}: a name is lowercase letters, digits and _, starting with a letter.')
        from .schema import LAYOUT_20, STORE_SCHEMA
        core = re.findall(r'CREATE(?: VIRTUAL)? TABLE IF NOT EXISTS ([a-z_]+)', STORE_SCHEMA + LAYOUT_20)
        if name in core:
            raise ValueError(f'Table {name}: the name belongs to the chassis.')
        statements = _schema_statements(name, schema)
        db = sqlite3.connect(':memory:')
        try:
            for statement in statements:
                db.execute(statement)
            info = db.execute(f'PRAGMA table_info({_quoted(name)})').fetchall()
            columns = tuple(Column(str(row[1]), 'int' if 'INT' in str(row[2]).upper() else
                                   'real' if str(row[2]).upper() in ('REAL', 'FLOAT', 'DOUBLE') else 'text',
                                   bool(row[3]), None) for row in info)
            key = tuple(str(row[1]) for row in sorted(info, key=lambda row: row[5]) if row[5])
            indexes = tuple(Index(tuple(str(row[2]) for row in db.execute(
                f'PRAGMA index_info({_quoted(index[1])})')), bool(index[2]))
                for index in db.execute(f'PRAGMA index_list({_quoted(name)})').fetchall() if index[3] != 'pk')
        except sqlite3.Error as error:
            raise ValueError(f'Table {name}: invalid schema: {error}.') from None
        finally:
            db.close()
        return cls(name, columns, key, indexes, schema=schema, exchange=exchange, on_remove=on_remove)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, unowned: bool = False) -> Table:
        if value.get('schema') is not None:
            return cls.from_sql(value['name'], value['schema'], exchange=bool(value.get('exchange', True)),
                                on_remove=tuple(tuple(rule) for rule in value.get('on_remove', ())), unowned=unowned)
        return cls(name=value['name'], place=value['place'], key=tuple(value['key']),
                   columns=tuple(Column(name, kind, bool(required), default)
                                 for name, kind, required, default in value['columns']),
                   indexes=tuple(Index(tuple(columns), bool(unique)) for columns, unique in value['indexes']),
                   on_remove=tuple(tuple(rule) for rule in value.get('on_remove', ())))


Upgrade = Callable[['TableTx', int], Any]


@dataclass(frozen=True)
class Tables:
    """Every table a module declares, at the module's own version, with what moves its data on an upgrade.

    `compatible_from` is the oldest version whose code still reads and writes these tables, the version itself when
    not given, STORE-029. A version that only adds a table, or a column that may be empty or has a default, keeps the
    one before it; any other change raises it to the new version, since older code would misread the tables."""
    version: int
    tables: tuple[Table, ...]
    upgrade: Upgrade | None = None
    legacy_upgrade: Callable[[sqlite3.Connection, str], Any] | None = None
    legacy_fold: Callable[[sqlite3.Connection, str, str], Any] | None = None
    compatible_from: int | None = None

    def __post_init__(self) -> None:
        version: Any = self.version
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError('Tables: version is a whole number from 1.')
        oldest: Any = self.compatible_from
        if oldest is not None and (isinstance(oldest, bool) or not isinstance(oldest, int)
                                   or not 1 <= oldest <= version):
            raise ValueError('Tables: compatible_from is a whole number from 1 to the version.')
        names = [table.name for table in self.tables]
        if len(names) != len(set(names)):
            raise ValueError('Tables: two tables share one name.')

    def table(self, name: str) -> Table:
        found = next((table for table in self.tables if table.name == name), None)
        if found is None:
            declared = ', '.join(table.name for table in self.tables) or 'none'
            raise StoreError(f'The module declares no table {name}; it declares {declared}.',
                             'declare it in the module\'s Tables and raise its version')
        return found

    @property
    def oldest(self) -> int:
        """The oldest version whose code reads these tables, STORE-029."""
        return self.version if self.compatible_from is None else self.compatible_from

    def recorded(self, place: Place) -> dict[str, Any]:
        """What a store of this place records for the module: its version, the oldest version whose code reads it
        and the tables it holds."""
        return {'version': self.version, 'compatible_from': self.oldest,
                'tables': [table.to_dict() for table in self.tables if table.place == place]}


# ------------------------------------------------------------------------------------------------ naming and SQL

def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def physical(module: str, table: str | Table) -> str:
    """The table's name in its store: the module's id, a dot and the table's name."""
    if isinstance(table, Table):
        return table.name if table.schema is not None else f'{module}.{table.name}'
    return f'{module}.{table}'


def _index_columns(table: Table, index: Index) -> tuple[str, ...]:
    """The columns an index is built on: a unique one on its own; any other with the key after them, so its order
    and a page's cursor are answered by the index, STORE-005."""
    if index.unique:
        return index.columns
    return index.columns + tuple(name for name in table.key if name not in index.columns)


def _index_name(module: str, table: Table, index: Index) -> str:
    return f'{physical(module, table)}:{"+".join(index.columns)}' + (':unique' if index.unique else '')


def _literal(column: Column) -> str:
    value = _encode(column, column.default)
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _create_sql(module: str, table: Table, name: str | None = None) -> str:
    if table.schema is not None:
        statement = _schema_statements(table.name, table.schema)[0]
        if name is not None:
            statement = re.sub(r'^(CREATE TABLE(?: IF NOT EXISTS)?)\s+[^ (]+',
                               lambda match: match[1] + ' ' + _quoted(name), statement, count=1, flags=re.IGNORECASE)
        return statement
    parts: list[str] = []
    for column in table.columns:
        part = f'{_quoted(column.name)} {SQL_TYPE[column.kind]}'
        if column.required or column.name in table.key:
            part += ' NOT NULL'
        if column.default is not None:
            part += f' DEFAULT {_literal(column)}'
        parts.append(part)
    parts.append(f'PRIMARY KEY({", ".join(_quoted(name) for name in table.key)})')
    return f'CREATE TABLE {_quoted(name or physical(module, table))}({", ".join(parts)})'


def _create_indexes(db: sqlite3.Connection, module: str, table: Table) -> None:
    if table.schema is not None:
        for statement in _schema_statements(table.name, table.schema)[1:]:
            name = re.match(r'^CREATE(?: UNIQUE)? INDEX(?: IF NOT EXISTS)?\s+([^ ]+)', statement, re.IGNORECASE)
            assert name is not None
            if db.execute('SELECT 1 FROM sqlite_master WHERE type=\'index\' AND name=?',
                          (name[1].strip('\"'),)).fetchone() is None:
                db.execute(statement)
        return
    for index in table.indexes:
        columns = ', '.join(_quoted(name) for name in _index_columns(table, index))
        db.execute(f'CREATE {"UNIQUE " if index.unique else ""}INDEX IF NOT EXISTS '
                   f'{_quoted(_index_name(module, table, index))} ON {_quoted(physical(module, table))}({columns})')


def _create(db: sqlite3.Connection, module: str, table: Table) -> None:
    if table.schema is None or not db.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?',
                                             (physical(module, table),)).fetchone():
        db.execute(_create_sql(module, table))
    _create_indexes(db, module, table)


def _encode(column: Column, value: Any) -> Any:
    if value is None:
        return None
    if column.kind == 'json':
        return json.dumps(value, ensure_ascii=False)
    if column.kind == 'bool':
        return int(bool(value))
    return value


def _decode(column: Column, value: Any) -> Any:
    if value is None:
        return None
    if column.kind == 'json':
        return json.loads(value)
    if column.kind == 'bool':
        return bool(value)
    return value


def _schema_statements(name: str, schema: str) -> list[str]:
    statements: list[str] = []
    pending = ''
    for char in schema:
        pending += char
        if char == ';' and sqlite3.complete_statement(pending):
            statements.append(pending.strip())
            pending = ''
    if pending.strip():
        statements.append(pending.strip())
    escaped = re.escape(name)
    identifier = rf'(?:"{escaped}"|{escaped})'
    table = rf'^CREATE TABLE(?: IF NOT EXISTS)?\s+{identifier}\s*\('
    index = rf'^CREATE(?: UNIQUE)? INDEX(?: IF NOT EXISTS)?\s+[^ ]+\s+ON\s+{identifier}\s*\('
    if not statements or not re.match(table, statements[0], re.IGNORECASE) or any(
            not re.match(index, statement, re.IGNORECASE) for statement in statements[1:]):
        raise ValueError(f'Table {name}: schema declares only its CREATE TABLE and CREATE INDEX statements.')
    return statements


def extensions(db: sqlite3.Connection | None = None) -> list[tuple[str, Tables]]:
    """Enabled existing-name declarations, plus recorded tables used by data callbacks and operations."""
    from .. import loader
    return [(module.id, module.tables) for module in loader.enabled() if module.tables is not None
            and (any(table.schema is not None for table in module.tables.tables)
                 or db is not None and module.data is not None and _recorded(db, module.id) is not None)]


def create_missing(db: sqlite3.Connection) -> None:
    """Every base-level table an enabled module declares that the store lacks, created, STORE-045: for a store whose
    layout number was set back by hand, the chassis upgrade puts the modules' tables back the way it did before the
    log, STORE-046."""
    present = {str(row[0]) for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for module, declared in extensions():
        for table in declared.tables:
            if table.place != 'metaform':
                continue
            name = physical(module, table)
            if name not in present:
                _create(db, module, table)
                continue
            held = {str(row[1]) for row in db.execute(f'PRAGMA table_info({_quoted(name)})')}
            wanted = sqlite3.connect(':memory:')
            try:
                wanted.execute(_create_sql(module, table))
                for row in wanted.execute(f'PRAGMA table_info({_quoted(name)})'):
                    if str(row[1]) not in held:  # a column the layout gained since: added, empty, as a relayout did
                        db.execute(f'ALTER TABLE {_quoted(name)} ADD COLUMN {_quoted(str(row[1]))} {row[2] or ""}')
            finally:
                wanted.close()


def extension_schema() -> str:
    """SQL supplied by enabled modules, for an existing layout's compatible upgrade."""
    return '\n'.join(table.schema for _, declared in extensions() for table in declared.tables
                     if table.schema is not None and table.place == 'metaform')


def extensions_ready(db: sqlite3.Connection) -> bool:
    """Whether every enabled declaration needed by native reads is ready."""
    return all(state(db, module, declared, 'metaform') == 'ready' for module, declared in extensions(db))


def exchange_tables(db: sqlite3.Connection | None = None,
                    entries: Sequence[dict[str, Any]] = ()) -> dict[str, Table]:
    """Existing-name tables carried under their established exchange keys, including unloaded owners."""
    found = {table.name: table for _, declared in extensions() for table in declared.tables
             if table.schema is not None and table.exchange}
    if db is not None:
        entries = [json.loads(value) for _, value in db.execute(
            "SELECT key, value FROM meta WHERE key >= ? AND key < ? ORDER BY key",
            (META_PREFIX, META_PREFIX[:-1] + ';')).fetchall()]
    for entry in entries:
        for value in entry['tables']:
            table = Table.from_dict(value)
            if table.schema is not None and table.exchange:
                found[table.name] = table
    return found


def recorded_tables(db: sqlite3.Connection) -> Generator[tuple[str, Table], None, None]:
    """Tables owned by the store's persisted declarations, whether their module is loaded or not."""
    for key, value in db.execute("SELECT key, value FROM meta WHERE key >= ? AND key < ? ORDER BY key",
                                 (META_PREFIX, META_PREFIX[:-1] + ';')).fetchall():
        module = str(key)[len(META_PREFIX):]
        for table in json.loads(value)['tables']:
            yield module, Table.from_dict(table)


def cleanup(db: sqlite3.Connection, kind: str, identity: str) -> None:
    """Apply each owner's declared removal of a native reference in the current DAO transaction."""
    for module, table in recorded_tables(db):
        for native, column, action in table.on_remove:
            if native != kind:
                continue
            name = _quoted(physical(module, table))
            column_name = _quoted(column)
            if action == 'delete':
                db.execute(f'DELETE FROM {name} WHERE {column_name}=?', (identity,))
            else:
                db.execute(f'UPDATE {name} SET {column_name}=NULL WHERE {column_name}=?', (identity,))


def ensure_extensions(db: sqlite3.Connection, path: Path) -> None:
    """Adopt existing-name tables and prepare recorded data declarations before the native transaction."""
    for module, declared in extensions(db):
        ensure(db, path, module, declared, 'metaform')


def legacy_fold(db: sqlite3.Connection, correction: str, intake: str) -> None:
    """Let each owner carry its layer references when a historical correction is folded."""
    for module, table in recorded_tables(db):
        for kind, column, _ in table.on_remove:
            if kind == 'layer':
                db.execute(f'UPDATE {_quoted(physical(module, table))} SET {_quoted(column)}=? '
                           f'WHERE {_quoted(column)}=?', (intake, correction))
    from .schema import LAYOUT_20
    native = set(re.findall(r'CREATE(?: VIRTUAL)? TABLE IF NOT EXISTS ([a-z_]+)', LAYOUT_20))
    for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        if name in native:
            continue
        for foreign in db.execute(f'PRAGMA foreign_key_list({_quoted(name)})').fetchall():
            if foreign[2] == 'layers' and foreign[4] == 'layer_id':
                column = _quoted(str(foreign[3]))
                db.execute(f'UPDATE {_quoted(name)} SET {column}=? WHERE {column}=?', (intake, correction))
    for _, declared in extensions():
        if declared.legacy_fold is not None:
            declared.legacy_fold(db, correction, intake)


def legacy_upgrade(db: sqlite3.Connection, found: str) -> None:
    """Let each enabled owner bring its data from a historical chassis layout."""
    for module, declared in extensions():
        if declared.legacy_upgrade is not None:
            declared.legacy_upgrade(db, found)
            db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)', ('legacy_upgrade:' + module, found))


# ------------------------------------------------------------------------------------------------ versions

def _recorded(db: sqlite3.Connection, module: str) -> dict[str, Any] | None:
    row = db.execute('SELECT value FROM meta WHERE key=?', (META_PREFIX + module,)).fetchone()
    return None if row is None else cast(dict[str, Any], json.loads(row[0]))


def _record(db: sqlite3.Connection, module: str, recorded: dict[str, Any]) -> None:
    db.execute('INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
               (META_PREFIX + module, json.dumps(recorded)))


def state(db: sqlite3.Connection, module: str, declared: Tables, place: Place) -> Literal['absent', 'ready', 'older']:
    """Whether a store holds the module's tables of this place at the declared version, an earlier one, or none.
    A later version whose `compatible_from` is at or below the declared one is read and written as it is, and
    nothing of it is rewritten or dropped; any other later version, or other tables at the same version, cannot be
    read and nothing is written, STORE-029."""
    recorded = _recorded(db, module)
    if recorded is None:
        return 'absent'
    found = int(recorded['version'])
    if found > declared.version:
        needed = int(recorded.get('compatible_from', found))
        if needed > declared.version:
            raise StoreError(f'The store holds the tables of {module} at version {found}, which {module} reads from '
                             f'version {needed}; this {module} declares version {declared.version}.',
                             f'install the {module} release that wrote version {found}')
        missing = _not_held(recorded, [table for table in declared.tables if table.place == place])
        if missing:
            raise StoreError(f'The tables of {module} at version {found} are named readable from version {needed}, '
                             f'but they do not hold {missing} as version {declared.version} declares it.',
                             f'install the {module} release that wrote version {found}')
        return 'ready'
    if found < declared.version:
        return 'older'
    if recorded['tables'] != declared.recorded(place)['tables']:
        raise StoreError(f'The tables {module} declares differ from those its store holds at version {found}.',
                         f'raise the version of {module}\'s Tables to {found + 1}')
    return 'ready'


def _not_held(recorded: Mapping[str, Any], tables: Sequence[Table]) -> str | None:
    """The first of these tables that a later version's record does not hold with the same key and every column, or
    None: a later version that only added tables and columns holds them all."""
    held = {str(value['name']): value for value in recorded['tables']}
    for table in tables:
        wanted = json.loads(json.dumps(table.to_dict()))  # as a record holds it, a default's tuple a list
        found = held.get(table.name)
        if found is None or found['key'] != wanted['key'] or any(
                column not in found['columns'] for column in wanted['columns']):
            return table.name
    return None


def ensure(db: sqlite3.Connection, path: Path, module: str, declared: Tables, place: Place) -> None:
    """Inside a write transaction: create the module's tables of this place, or upgrade them to the declared
    version after keeping a copy of the file, STORE-045."""
    found = state(db, module, declared, place)
    if found == 'ready':
        return
    if found == 'absent':
        _adopt(db, path, module, declared, place)
        _record(db, module, declared.recorded(place))
        return
    try:
        _upgrade(db, path, module, declared, place)
    except sqlite3.IntegrityError as error:
        raise StoreError(f'The tables of {module} could not be brought to version {declared.version}: {error}. '
                         'Nothing was changed.', 'give a new required column a default, or keep the key unique') from None


def _adopt(db: sqlite3.Connection, path: Path, module: str, declared: Tables, place: Place) -> None:
    """Bring pre-declaration tables, and tables held without their record, to their owner's layout while retaining
    every shared column."""
    changed: list[Table] = []
    target = sqlite3.connect(':memory:')
    try:
        for table in declared.tables:
            if table.place != place:
                continue
            name = _quoted(physical(module, table))
            actual = db.execute(f'PRAGMA table_info({name})').fetchall()
            if not actual:
                continue
            target.execute(_create_sql(module, table))
            wanted = target.execute(f'PRAGMA table_info({name})').fetchall()
            if [tuple(row)[1:] for row in actual] != [tuple(row)[1:] for row in wanted]:
                changed.append(table)
    finally:
        target.close()
    deferred = db.execute('PRAGMA defer_foreign_keys').fetchone()[0]
    if changed:
        if path.is_file():
            _backup(path, module, declared.version)
        db.execute('PRAGMA defer_foreign_keys=ON')
        for table in changed:
            name = physical(module, table)
            replacement = name + '__adopt'
            db.execute(_create_sql(module, table, replacement))
            old = {row[1] for row in db.execute(f'PRAGMA table_info({_quoted(name)})')}
            shared = ', '.join(_quoted(column.name) for column in table.columns if column.name in old)
            db.execute(f'INSERT INTO {_quoted(replacement)}({shared}) SELECT {shared} FROM {_quoted(name)}')
            db.execute(f'DROP TABLE {_quoted(name)}')
            db.execute(f'ALTER TABLE {_quoted(replacement)} RENAME TO {_quoted(name)}')
    for table in declared.tables:
        if table.place == place and (table.schema is not None or not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (physical(module, table),)).fetchone()):
            _create(db, module, table)
    former = db.execute("SELECT value FROM meta WHERE key='prior_schema_version'").fetchone()
    applied = db.execute('SELECT 1 FROM meta WHERE key=?', ('legacy_upgrade:' + module,)).fetchone()
    if former is not None and applied is None and declared.legacy_upgrade is not None:
        declared.legacy_upgrade(db, str(former[0]))
        db.execute('INSERT INTO meta(key,value) VALUES (?,?)', ('legacy_upgrade:' + module, str(former[0])))
    if changed:
        problems = db.execute('PRAGMA foreign_key_check').fetchall()
        if problems:
            raise StoreError(f'Adopting {module} would break {len(problems)} references. Nothing was changed.',
                             f'compare {module}\'s table declaration with the rows already held')
        # Replacing a referenced table leaves SQLite's deferred drop count pending even after its rows and name
        # have been restored. The actual references above are intact; clear that count before the commit.
        db.execute('PRAGMA defer_foreign_keys=OFF')
        if deferred:
            db.execute('PRAGMA defer_foreign_keys=ON')


def _backup(path: Path, module: str, version: int) -> None:
    """A copy of the store as last committed, read through a connection of its own, since the connection that
    upgrades it is already writing and SQLite refuses to copy from a connection that is writing; in WAL mode the
    reader does not wait on that writer."""
    folder = (home.home() / 'backups' / f'module-{module}-{version}' /
              home.now().replace(':', '').replace('-', '') / path.parent.name)
    folder.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)  # as_uri escapes #, ? and %
    copy = sqlite3.connect(folder / path.name)
    try:
        source.backup(copy)
    finally:
        copy.close()
        source.close()


def _upgrade(db: sqlite3.Connection, path: Path, module: str, declared: Tables, place: Place) -> None:
    """Bring the module's tables of this place to the declared version: new tables and indexes are made, a table
    whose columns changed is rebuilt keeping every row in the columns both have, the module's upgrade runs with the
    version found and reads the rows as that version held them through `found_rows`, and then the table as it was
    found and a table no longer declared are dropped."""
    recorded = _recorded(db, module)
    assert recorded is not None
    found = int(recorded['version'])
    _backup(path, module, declared.version)
    old = {value['name']: Table.from_dict(value) for value in recorded['tables']}
    held = {name: (table, physical(module, table)) for name, table in old.items()}  # each found table and where it is
    new = [table for table in declared.tables if table.place == place]
    # A table declared at the other place in this version still has its rows here: dropping it would lose them, and
    # no transplant between stores exists, so the upgrade is refused with the way out named. Found by review, 2026-10-06.
    elsewhere = {table.name: table.place for table in declared.tables if table.place != place}
    moved = sorted(name for name in old if name in elsewhere)
    if moved:
        raise StoreError(f'{module} version {declared.version} moves {", ".join(moved)} from the {place} store to the '
                         f'{elsewhere[moved[0]]} store, and the rows here would be lost; a table keeps its place, or '
                         f'the module\'s upgrade copies the rows itself before the table is declared elsewhere.',
                         f'metaform disable {module}')
    deferred = db.execute('PRAGMA defer_foreign_keys').fetchone()[0]
    db.execute('PRAGMA defer_foreign_keys=ON')
    for table in new:
        before = old.get(table.name)
        if before is None:
            _create(db, module, table)
            continue
        for index in db.execute(f'PRAGMA index_list({_quoted(physical(module, before))})').fetchall():
            if index[3] != 'pk' and index[3] != 'u':
                db.execute(f'DROP INDEX IF EXISTS {_quoted(index[1])}')
        if (before.columns, before.key, before.schema) != (table.columns, table.key, table.schema):
            # Rebuilt beside the old table and swapped into its name, as adoption does: a rename would repoint the
            # foreign keys of the tables that refer to it at a copy that is then dropped. The old rows stay readable
            # to the module's upgrade in a plain copy, `<name>.found`.
            name = physical(module, table)
            db.execute(f'CREATE TABLE {_quoted(name + ".found")} AS SELECT * FROM {_quoted(name)}')
            held[table.name] = (before, name + '.found')
            replacement = name + '__upgrade'
            db.execute(_create_sql(module, table, replacement))
            shared = [column.name for column in table.columns if column.name in [c.name for c in before.columns]]
            listed = ', '.join(_quoted(column) for column in shared)
            db.execute(f'INSERT INTO {_quoted(replacement)}({listed}) SELECT {listed} FROM {_quoted(name)}')
            db.execute(f'DROP TABLE {_quoted(name)}')
            db.execute(f'ALTER TABLE {_quoted(replacement)} RENAME TO {_quoted(name)}')
        _create_indexes(db, module, table)
    if declared.upgrade is not None:
        declared.upgrade(TableTx(module, declared, write=True, opener=lambda _: (db, path, True), bound=place,
                                 found=held), found)
    for name, (_, where) in held.items():
        if name not in [table.name for table in new] or where != physical(module, declared.table(name)):
            db.execute(f'DROP TABLE IF EXISTS {_quoted(where)}')
    problems = db.execute('PRAGMA foreign_key_check').fetchall()
    if problems:
        raise StoreError(f'Upgrading {module} would break {len(problems)} references. Nothing was changed.',
                         f'compare {module}\'s table declaration with the rows already held')
    # The swap leaves SQLite's deferred drop count pending though every reference is intact, as adoption notes.
    db.execute('PRAGMA defer_foreign_keys=OFF')
    if deferred:
        db.execute('PRAGMA defer_foreign_keys=ON')
    _record(db, module, declared.recorded(place))


# ------------------------------------------------------------------------------------------------ the transaction

Opener = Callable[[Place], tuple[sqlite3.Connection, Path, bool]]  # a place's connection, its file, whether it holds the tables


class TableTx:
    """One transaction on a module's own tables, given by `Store.tables()`, STORE-045.

    It is bound to the store of the first table it touches, and every read goes through the key's index or a
    declared index, STORE-005. Rows are dicts of column name to value.
    """

    def __init__(self, module: str, declared: Tables, *, write: bool, opener: Opener,
                 bound: Place | None = None, found: Mapping[str, tuple[Table, str]] | None = None) -> None:
        self.module = module
        self.declared = declared
        self.write = write
        self._opener = opener
        self._found = found  # an upgrade's: each table as the version found declared it, and the table holding it
        self._place: Place | None = None
        self._db: sqlite3.Connection | None = None
        self._path: Path | None = None
        self._present = False
        if bound is not None:
            self._bind(bound)

    @property
    def place(self) -> Place | None:
        """The store this transaction is on, `metaform` or `project`, once a table has been touched; an upgrade's
        transaction is on the store being upgraded from the start."""
        return self._place

    def _bind(self, place: Place) -> None:
        self._db, self._path, self._present = self._opener(place)
        self._place = place

    def number(self, address: str) -> int:
        """The next number at an address, from the project's counter, for an item this transaction writes there, as
        `DataTx.number` gives it; a module's upgrade numbers the items it already holds with it. The transaction must
        have touched a table, so it knows its store and the project it belongs to."""
        from . import numbers
        folder = numbers.folder_of(self._path) if self._path is not None else None
        if folder is None:
            raise StoreError('This transaction reaches no project store, so it has no counters.',
                             'touch one of the module\'s tables first, or number with store.number(address)')
        return numbers.take(folder, address)

    def _table(self, name: str) -> Table:
        table = self.declared.table(name)
        if self._place is None:
            self._bind(table.place)
        elif table.place != self._place:
            raise StoreError(f'{name} is in the {table.place}-level store and this transaction is in the '
                             f'{self._place}-level store; one transaction reaches one store, STORE-006.',
                             f'reach {name} in a transaction of its own: with store.tables() as tx')
        return table

    def _writing(self, name: str) -> Table:
        table = self._table(name)
        if not self.write:
            raise StoreError(f'This transaction reads {self.module}\'s tables and does not write them.',
                             'write in store.tables(), which writes')
        return table

    def _execute(self, sql: str, params: Sequence[Any]) -> sqlite3.Cursor:
        assert self._db is not None
        try:
            return self._db.execute(sql, tuple(params))
        except sqlite3.IntegrityError as error:
            raise StoreError(f'The write does not fit {self.module}\'s tables: {error}.',
                             f'compare the row with the declaration of {self.module}\'s Tables') from None

    def _known(self, table: Table, row: Mapping[str, Any], what: str) -> None:
        unknown = [name for name in row if name not in [column.name for column in table.columns]]
        if unknown:
            raise StoreError(f'{table.name} has no column {unknown[0]}; its columns are '
                             f'{", ".join(column.name for column in table.columns)}.',
                             f'name only the columns of {table.name} in the {what}')

    def _keyed(self, table: Table, key: Mapping[str, Any]) -> list[Any]:
        if set(key) != set(table.key):
            raise StoreError(f'A key of {table.name} names exactly {", ".join(table.key)}.',
                             f'give the key as {{{", ".join(repr(name) + ": ..." for name in table.key)}}}')
        return [_encode(table.column(name), key[name]) for name in table.key]

    def _row(self, table: Table, row: sqlite3.Row | Sequence[Any]) -> Row:
        return {column.name: _decode(column, row[place]) for place, column in enumerate(table.columns)}

    def _select(self, table: Table) -> str:
        return (f'SELECT {", ".join(_quoted(column.name) for column in table.columns)} '
                f'FROM {_quoted(physical(self.module, table))}')

    def _plan(self, table: Table, where: Mapping[str, Any],
              by: Sequence[str] = ()) -> tuple[tuple[str, ...], tuple[str, ...], list[Any]]:
        """The index a read or delete goes through: the key or a declared index whose leading columns are `by`,
        when given, and of which the where gives the first ones. Returns those columns in the index's order, the rest
        of the index and then the key, which is the order it reads in, and the where's values. A where or a `by`
        that no index starts with is refused, STORE-005."""
        self._known(table, where, 'where')
        self._known(table, dict.fromkeys(by), 'by')
        for order in [table.key] + [_index_columns(table, index) for index in table.indexes]:
            prefix = order[:len(where)]
            if set(prefix) == set(where) and order[:len(by)] == tuple(by):
                rest = order[len(where):] + tuple(name for name in table.key if name not in order)
                return prefix, rest, [_encode(table.column(name), where[name]) for name in prefix]
        wanted = ', '.join(by) if by else ', '.join(where)
        declared = '; '.join(', '.join(order) for order in [table.key] + [index.columns for index in table.indexes])
        raise StoreError(f'No index of {table.name} starts with {wanted}; its indexes start with {declared}.',
                         f'declare Index(({", ".join(repr(name) for name in (by or where))},)) on {table.name} '
                         'and raise the version')

    @staticmethod
    def _equal(names: Sequence[str]) -> str:
        return ' AND '.join(f'{_quoted(name)}=?' for name in names)

    # ------------------------------------------------------------------ writes

    def insert(self, table: str, row: Mapping[str, Any]) -> Row:
        """Add one row; a row whose key is held already cannot be added again."""
        declared = self._writing(table)
        self._known(declared, row, 'row')
        names = list(row)
        cursor = self._execute(f'INSERT INTO {_quoted(physical(self.module, declared))}'
                      f'({", ".join(_quoted(name) for name in names)}) VALUES ({", ".join("?" for _ in names)})',
                      [_encode(declared.column(name), row[name]) for name in names])
        key = {name: row[name] for name in declared.key if name in row}
        if not key and len(declared.key) == 1 and declared.column(declared.key[0]).kind == 'int':
            key[declared.key[0]] = cursor.lastrowid
        stored = self.get(table, key)
        assert stored is not None
        return stored

    def update(self, table: str, key: Mapping[str, Any], changes: Mapping[str, Any]) -> Row | None:
        """Change the row with this key; returns it as changed, or None when no row has the key."""
        declared = self._writing(table)
        values = self._keyed(declared, key)
        self._known(declared, changes, 'changes')
        if changes:
            cursor = self._execute(
                f'UPDATE {_quoted(physical(self.module, declared))} SET '
                f'{", ".join(f"{_quoted(name)}=?" for name in changes)} WHERE {self._equal(declared.key)}',
                [_encode(declared.column(name), value) for name, value in changes.items()] + values)
            if not cursor.rowcount:
                return None
        moved = {name: changes.get(name, key[name]) for name in declared.key}
        return self.get(table, moved)

    def delete(self, table: str, where: Mapping[str, Any]) -> int:
        """Delete the rows with these equal values for the leading columns of the key or an index; returns how
        many."""
        declared = self._writing(table)
        given = dict(where)
        if not given:
            raise StoreError(f'A delete from {declared.name} names the rows it deletes.',
                             f'give equal values for the leading columns of the key or an index of {declared.name}')
        prefix, _, values = self._plan(declared, given)
        return self._execute(f'DELETE FROM {_quoted(physical(self.module, declared))} WHERE '
                             f'{self._equal(prefix)}', values).rowcount

    # ------------------------------------------------------------------ reads

    def get(self, table: str, key: Mapping[str, Any]) -> Row | None:
        """The row with this key, or None."""
        declared = self._table(table)
        values = self._keyed(declared, key)
        if not self._present:
            return None
        found = self._execute(f'{self._select(declared)} WHERE '
                              f'{self._equal(declared.key)}', values).fetchone()
        return None if found is None else self._row(declared, found)

    def rows(self, table: str, where: Mapping[str, Any] | None = None, *, by: Sequence[str] = (),
             limit: int = LIMIT, after: str | None = None) -> Page[Row]:
        """The rows with these equal values for the leading columns of the key or an index, in that index's order,
        a page at a time; `by` names the leading columns of the index to read through, the key's when neither is
        given; `limit=0` reads them all, STORE-025."""
        declared = self._table(table)
        given = dict(where or {})
        prefix, rest, values = self._plan(declared, given, tuple(by))
        if not self._present:
            return Page((), None)
        clauses = [self._equal(prefix)] if given else []
        if after is not None and rest:
            cursor = json.loads(after)
            clauses.append(f'({", ".join(_quoted(name) for name in rest)}) > ({", ".join("?" for _ in rest)})')
            values = values + list(cursor)
        sql = self._select(declared) + (f' WHERE {" AND ".join(clauses)}' if clauses else '')
        if rest:  # a where that gives the whole key, or a unique index, answers one row and has no order
            sql += f' ORDER BY {", ".join(_quoted(name) for name in rest)}'
        if limit:
            sql += f' LIMIT {int(limit) + 1}'
        found = self._execute(sql, values).fetchall()
        more = bool(limit) and len(found) > limit
        kept = found[:limit] if limit else found
        results = tuple(self._row(declared, row) for row in kept)
        if not more or not rest:
            return Page(results, None)
        last = kept[-1]
        names = [column.name for column in declared.columns]
        return Page(results, json.dumps([last[names.index(name)] for name in rest]))

    def found_rows(self, table: str, *, limit: int = LIMIT, after: str | None = None) -> Page[Row]:
        """Inside the module's upgrade: the rows of a table as the version found held them, every column that version
        declared included, those the new version drops among them, in that version's key order, a page at a time;
        `limit=0` reads them all, STORE-025. They can be read until the upgrade returns."""
        if self._found is None:
            raise StoreError('Only a module\'s upgrade reads its rows as the version found held them.',
                             'read them in upgrade(tx, found), declared with the module\'s Tables')
        if table not in self._found:
            raise StoreError(f'The version found holds no table {table} in this store; it holds '
                             f'{", ".join(self._found) or "none"}.', 'name a table the version found held')
        before, name = self._found[table]
        assert self._db is not None
        clauses: list[str] = []
        values: list[Any] = []
        if after is not None:
            clauses.append(f'({", ".join(_quoted(key) for key in before.key)}) > '
                           f'({", ".join("?" for _ in before.key)})')
            values = list(json.loads(after))
        sql = (f'SELECT {", ".join(_quoted(column.name) for column in before.columns)} FROM {_quoted(name)}'
               + (f' WHERE {clauses[0]}' if clauses else '')
               + f' ORDER BY {", ".join(_quoted(key) for key in before.key)}')
        if limit:
            sql += f' LIMIT {int(limit) + 1}'
        found = self._db.execute(sql, values).fetchall()
        more = bool(limit) and len(found) > limit
        kept = found[:limit] if limit else found
        results = tuple(self._row(before, row) for row in kept)
        if not more:
            return Page(results, None)
        names = [column.name for column in before.columns]
        return Page(results, json.dumps([kept[-1][names.index(key)] for key in before.key]))


# ------------------------------------------------------------------------------------------------ the registry

def declared(module: str | None, *, retained: bool = False) -> Tables:
    """The tables a loaded module declares, read from its declaration, BASE-035."""
    if not module:
        raise StoreError('This store works for no module, so it reaches no module\'s tables.',
                         'use ctx.store in a verb, subscriber or tool of the module')
    from .. import loader
    found = loader.get(module)
    tables = None if found is None or found.module is None else found.module.tables
    if tables is None and retained:
        source = loader.data_source(module)
        candidate = getattr(source, 'TABLES', None)
        if isinstance(candidate, Tables):
            tables = candidate
    if tables is None:
        raise StoreError(f'{module} declares no tables.',
                         'declare them as Module(..., tables=Tables(...)), docs/guides/extending-metaform.md')
    return tables


# ------------------------------------------------------------------------------------------------ project stores

def project_store(project_id: str, module: str) -> Path:
    """Where a module's project-level tables live: `modules/<module>.sqlite3` in the project's folder."""
    folder = home.project_folder(project_id)
    if folder is None:
        raise StoreError(f'Project {project_id} is no longer registered.', 'metaform list projects')
    return folder / 'modules' / f'{module}.sqlite3'


@contextmanager
def open_project_store(path: Path, *, write: bool) -> Generator[sqlite3.Connection, None, None]:
    """A prepared connection to a project-level module store, opened inside its lock like every file, STORE-006."""
    with sqlite.opened(path, MODULE_STORE_SCHEMA, write=write, version=MODULE_STORE_VERSION,
                       compatible=MODULE_STORE_COMPATIBLE_FROM) as db:
        db.row_factory = sqlite3.Row
        yield db


@contextmanager
def project_transaction(path: Path, *, write: bool) -> Generator[sqlite3.Connection, None, None]:
    """One transaction on a project-level module store: BEGIN IMMEDIATE for a write, a deferred BEGIN for a read."""
    with open_project_store(path, write=write) as db:
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')


def project_stores(project_id: str) -> list[Path]:
    folder = home.project_folder(project_id)
    found = folder / 'modules' if folder is not None else None
    return sorted(found.glob('*.sqlite3')) if found is not None and found.is_dir() else []


# ------------------------------------------------------------------------------------------------ export and import

def export_unowned(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Preserve tables that predate a public ownership declaration without assigning them an owner."""
    from .schema import STORE_SCHEMA
    native = sqlite3.connect(':memory:')
    try:
        native.executescript(STORE_SCHEMA)
        known = {row[0] for row in native.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        native.close()
    known.update(physical(module, table) for module, table in recorded_tables(db))
    found: list[dict[str, Any]] = []
    for name, schema in db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        if name in known or name.startswith('sqlite_'):
            continue
        indexes = [row[0] for row in db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? "
                                                "AND sql IS NOT NULL ORDER BY name", (name,)).fetchall()]
        table = Table.from_sql(name, ';\n'.join([schema, *indexes]) + ';', exchange=False, unowned=True)
        names = [column.name for column in table.columns]
        rows = db.execute(f'SELECT {", ".join(_quoted(column) for column in names)} FROM {_quoted(name)} '
                          f'ORDER BY {", ".join(_quoted(column) for column in table.key)}').fetchall()
        found.append({'table': table.to_dict(), 'rows': [dict(zip(names, tuple(row), strict=True)) for row in rows]})
    return found


def check_unowned(entries: Any, path: str, problems: list[str]) -> None:
    """Validate undeclared legacy tables as schema declarations and scalar rows before importing."""
    if not isinstance(entries, list):
        problems.append(f'{path}: not a list')
        return
    for number, entry in enumerate(cast(list[Any], entries)):
        where = f'{path}[{number}]'
        if not isinstance(entry, dict):
            problems.append(f'{where}: holds exactly table and rows')
            continue
        fields = cast(dict[str, Any], entry)
        if set(fields) != {'table', 'rows'}:
            problems.append(f'{where}: holds exactly table and rows')
            continue
        try:
            table = Table.from_dict(fields['table'], unowned=True)
            if table.schema is None:
                raise ValueError('an unowned table retains its SQL declaration')
        except (KeyError, TypeError, ValueError) as error:
            problems.append(f'{where}.table: not a declaration: {error}')
            continue
        names = {column.name for column in table.columns}
        rows = fields['rows']
        if not isinstance(rows, list) or any(not isinstance(row, dict) or set(cast(dict[str, Any], row)) != names or not all(
                _scalar(value) for value in cast(dict[str, Any], row).values()) for row in cast(list[Any], rows)):
            problems.append(f'{where}.rows: not one text, number or null for each column')


def import_unowned(db: sqlite3.Connection, entries: Sequence[dict[str, Any]]) -> None:
    """Restore unknown tables as they were held; the actual owner can adopt them when it next loads."""
    declarations = [(Table.from_dict(entry['table'], unowned=True), entry['rows']) for entry in entries]
    for table, _ in declarations:
        _create(db, '', table)
    if declarations:
        db.execute('PRAGMA defer_foreign_keys=ON')
    for table, rows in declarations:
        names = [column.name for column in table.columns]
        for row in rows:
            db.execute(f'INSERT OR IGNORE INTO {_quoted(table.name)}'
                       f'({", ".join(_quoted(name) for name in names)}) VALUES ({", ".join("?" for _ in names)})',
                       tuple(row[name] for name in names))


def export_modules(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every module's tables a store holds, with their rows in key order, STORE-027."""
    exported: list[dict[str, Any]] = []
    for key, value in db.execute("SELECT key, value FROM meta WHERE key >= ? AND key < ? ORDER BY key",
                                 (META_PREFIX, META_PREFIX[:-1] + ';')).fetchall():
        module = str(key)[len(META_PREFIX):]
        recorded = json.loads(value)
        rows: dict[str, list[Row]] = {}
        for entry in recorded['tables']:
            table = Table.from_dict(entry)
            names = [column.name for column in table.columns]
            found = db.execute(f'SELECT {", ".join(_quoted(name) for name in names)} FROM '
                               f'{_quoted(physical(module, table))} '
                               f'ORDER BY {", ".join(_quoted(name) for name in table.key)}').fetchall()
            rows[table.name] = [dict(zip(names, tuple(row), strict=True)) for row in found]
        exported.append({'module': module, 'version': recorded['version'],
                         'compatible_from': recorded.get('compatible_from', recorded['version']),
                         'tables': recorded['tables'], 'rows': rows})
    return exported


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float)) and not isinstance(value, bool)


def check(entries: Any, path: str, problems: list[str]) -> None:
    """Check a document's modules list before anything is written; its names reach SQL only once checked, H8."""
    if not isinstance(entries, list):
        problems.append(f'{path}: not a list')
        return
    for number, entry in enumerate(cast(list[Any], entries)):
        where = f'{path}[{number}]'
        if not isinstance(entry, dict):
            problems.append(f'{where}: not an object')
            continue
        fields = cast(dict[str, Any], entry)
        # compatible_from is optional: a document written before it was recorded takes it as the version, STORE-029.
        if set(fields) - {'compatible_from'} != {'module', 'version', 'tables', 'rows'}:
            problems.append(f'{where}: holds exactly module, version, tables and rows, and may hold compatible_from')
            continue
        if not isinstance(fields['module'], str) or not MODULE_ID.fullmatch(fields['module']):
            problems.append(f'{where}.module: not a module id')
        if isinstance(fields['version'], bool) or not isinstance(fields['version'], int) or fields['version'] < 1:
            problems.append(f'{where}.version: not a whole number from 1')
        elif 'compatible_from' in fields and (isinstance(fields['compatible_from'], bool) or not isinstance(
                fields['compatible_from'], int) or not 1 <= fields['compatible_from'] <= fields['version']):
            problems.append(f'{where}.compatible_from: not a whole number from 1 to the version')
        tables: list[Table] = []
        try:
            tables = [Table.from_dict(value) for value in fields['tables']]
        except (KeyError, TypeError, ValueError) as error:
            problems.append(f'{where}.tables: not a declaration of tables: {error}')
            continue
        rows = fields['rows']
        if not isinstance(rows, dict) or set(cast(dict[str, Any], rows)) != {table.name for table in tables}:
            problems.append(f'{where}.rows: not one list of rows for each table')
            continue
        for table in tables:
            names = {column.name for column in table.columns}
            given = cast(dict[str, Any], rows)[table.name]
            if not isinstance(given, list):
                problems.append(f'{where}.rows.{table.name}: not a list')
                continue
            for place, row in enumerate(cast(list[Any], given)):
                if not isinstance(row, dict) or set(cast(dict[str, Any], row)) != names or not all(
                        _scalar(value) for value in cast(dict[str, Any], row).values()):
                    problems.append(f'{where}.rows.{table.name}[{place}]: not one text, number or null for each '
                                    'column')


def _takes(recorded: Mapping[str, Any], entry: Mapping[str, Any], tables: Sequence[Table]) -> bool:
    """Whether a store's tables of a module take the rows of a document's entry: the same version and tables, or a
    later version readable from the entry's that holds each of its tables with its key and columns."""
    found, version = int(recorded['version']), int(entry['version'])
    if found == version:
        return recorded['tables'] == entry['tables']
    if found < version or int(recorded.get('compatible_from', found)) > version:
        return False
    return _not_held(recorded, tables) is None


def import_modules(db: sqlite3.Connection, entries: Sequence[dict[str, Any]], report: dict[str, Any],
                   where: str) -> None:
    """Inside the import's transaction: create the tables a store lacks and add each row whose key it does not
    hold. A module held at a later version that names the document's version compatible takes the rows as code at
    that version writes them, STORE-029; a module held at any other version adds nothing, and a notice says so,
    BASE-044."""
    for entry in entries:
        module, version = str(entry['module']), int(entry['version'])
        tables = [Table.from_dict(value) for value in entry['tables']]
        recorded = _recorded(db, module)
        if recorded is None:
            for table in tables:
                _create(db, module, table)
            _record(db, module, {'version': version, 'compatible_from': int(entry.get('compatible_from', version)),
                                 'tables': entry['tables']})
        elif not _takes(recorded, entry, tables):
            report['notices'].append({'where': f'{where}.{module}', 'message': (
                f'This store holds the tables of {module} at version {recorded["version"]}; the document carries '
                f'version {version}, so none of its rows was imported. To add them, import into a home whose '
                f'{module} is at version {version}: metaform import <file>')})
            continue
        for table in tables:
            names = [column.name for column in table.columns]
            for row in entry['rows'][table.name]:
                cursor = db.execute(f'INSERT OR IGNORE INTO {_quoted(physical(module, table))}'
                                    f'({", ".join(_quoted(name) for name in names)}) '
                                    f'VALUES ({", ".join("?" for _ in names)})', tuple(row[name] for name in names))
                if not table.exchange:
                    report['things_added' if cursor.rowcount else 'things_skipped'] += 1
