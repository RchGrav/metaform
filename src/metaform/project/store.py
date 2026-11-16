"""One project's map in LadybugDB, at `<home>/maps/<project>.lbug`.

The map is stored by field. `Element` holds one row per address, the address without the project's name as its key
and one column per field of an element. `OverlayPart` holds the parts of overlay definitions, everything beneath the
`overlay` root. `Wants` is a relationship between elements with the want's fields as its columns. Every other overlay
has a node table `ov_<key>` of its own: one row per record, with the address it sits at, its position in the list, its
`ref`, and one column `f_<field>` per field of its definition. The fixed tables are named in capitals and every
overlay table starts with `ov_`, so the two never meet.

Every value reaches the engine as a query parameter. The only names written into query text are the fixed tables and
the overlay tables and columns, and those are checked here against the form of a step before use.
"""
from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self

import ladybug  # pyright: ignore[reportMissingTypeStubs]

from metaform.project import texts

Scalar = str | int | float | bool | None
ELEMENT_FIELDS = ('technical_name', 'name', 'role', 'ref', 'status')
PART_FIELDS = ('description', 'instruction', 'type', 'rule', 'example', 'optional')
WANT_FIELDS = ('why', 'how', 'direction', 'ref')
COLUMN_TYPES = ('STRING', 'DOUBLE', 'BOOLEAN')
_NAME = re.compile(r'[a-z0-9]+(?:_[a-z0-9]+)*\Z')

_SCHEMA = (
    ('CREATE NODE TABLE Element(address STRING PRIMARY KEY, `technical_name` STRING, `name` STRING, `role` STRING, '
     '`ref` STRING, `status` STRING)'),
    # Every column is quoted: `optional` is a word of the engine's Cypher, and a bare column of that name is refused.
    ('CREATE NODE TABLE OverlayPart(address STRING PRIMARY KEY, `description` STRING, `instruction` STRING, '
     '`type` STRING, `rule` STRING, `example` STRING, `optional` BOOLEAN)'),
    'CREATE REL TABLE Wants(FROM Element TO Element, why STRING, how STRING, direction STRING, ref STRING)',
)
_ELEMENT_COLUMNS = ', '.join(f'e.`{field}`' for field in ELEMENT_FIELDS)
_PART_COLUMNS = ', '.join(f'p.`{field}`' for field in PART_FIELDS)


class StoreError(Exception):
    """The engine failed. `unknown` is true when the failure came at commit, so the write may or may not be stored."""

    def __init__(self, message: str, unknown: bool = False) -> None:
        super().__init__(message)
        self.unknown = unknown


class _Engine:
    """The one place that calls `ladybug`, which has no type information. Everything it returns is plain rows."""

    def __init__(self, path: Path) -> None:
        try:
            self._database: Any = ladybug.Database(str(path))
            self._connection: Any = ladybug.Connection(self._database)
        except Exception as error:
            raise StoreError(f'cannot open {path.name}: {error}') from error

    def rows(self, query: str, values: dict[str, object]) -> list[list[Scalar]]:
        try:
            result: Any = self._connection.execute(query, values)
            rows: list[list[Scalar]] = []
            while result.has_next():
                rows.append(list(result.get_next()))
            return rows
        except Exception as error:
            raise StoreError(str(error)) from error

    def close(self) -> None:
        self._connection.close()
        self._database.close()


def location(home: Path, project: str) -> Path:
    return home / 'maps' / f'{project}.lbug'


def projects(home: Path) -> list[str]:
    folder = home / 'maps'
    return sorted(path.stem for path in folder.glob('*.lbug')) if folder.is_dir() else []


def remove(path: Path) -> None:
    """Remove a database and the files the engine keeps beside it, used when a project's first write is refused."""
    for found in [path, *path.parent.glob(path.name + '.*')]:
        found.unlink(missing_ok=True)


def _table(key: str) -> str:
    if not _NAME.match(key):
        raise StoreError(f'{key!r} is not an overlay key')
    return f'ov_{key}'


def _column(field: str) -> str:
    if not _NAME.match(field):
        raise StoreError(f'{field!r} is not a field name')
    return f'f_{field}'


class Store:
    """An open project database. A long-running server can hold one; `commands.run` opens and closes one per call.
    Only one process may hold a database open for writing."""

    def __init__(self, path: Path, create: str | None = None) -> None:
        """Open the database at `path`. With `create`, the project's name, make it: the tables, and the definition
        of the wants overlay, so that wants are checked by the same path as every other overlay."""
        if create is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._engine = _Engine(path)
        if create is not None:
            with self.transaction():
                for statement in _SCHEMA:
                    self._rows(statement)
                for address, fields in texts.wants_definition(create).items():
                    self.put_part(address, dict(fields))

    def close(self) -> None:
        self._engine.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _rows(self, query: str, **values: object) -> list[list[Scalar]]:
        return self._engine.rows(query, values)

    @contextmanager
    def transaction(self) -> Generator[None]:
        """One command is one transaction. A statement that fails ends the engine's transaction by itself, so the
        rollback after it may find none to end."""
        self._rows('BEGIN TRANSACTION')
        try:
            yield
        except BaseException:
            try:
                self._rows('ROLLBACK')
            except StoreError:
                pass
            raise
        try:
            self._rows('COMMIT')
        except StoreError as error:
            raise StoreError(str(error), unknown=True) from error

    # Elements

    def elements(self, addresses: list[str]) -> dict[str, dict[str, Scalar]]:
        rows = self._rows(f'MATCH (e:Element) WHERE e.address IN $addresses RETURN e.address, {_ELEMENT_COLUMNS}',
                          addresses=addresses)
        return {str(row[0]): dict(zip(ELEMENT_FIELDS, row[1:])) for row in rows}

    def all_elements(self) -> list[tuple[str, dict[str, Scalar]]]:
        rows = self._rows(f'MATCH (e:Element) RETURN e.address, {_ELEMENT_COLUMNS} ORDER BY e.address')
        return [(str(row[0]), dict(zip(ELEMENT_FIELDS, row[1:]))) for row in rows]

    def orphans(self) -> list[tuple[str, dict[str, Scalar]]]:
        held = ' OR '.join(f'e.`{field}` IS NOT NULL' for field in ELEMENT_FIELDS)
        rows = self._rows(f'MATCH (e:Element) WHERE ({held}) AND NOT EXISTS {{ MATCH (:Element)-[:Wants]->(e) }} '
                          f'RETURN e.address, {_ELEMENT_COLUMNS} ORDER BY e.address')
        return [(str(row[0]), dict(zip(ELEMENT_FIELDS, row[1:]))) for row in rows]

    def put_element(self, address: str, fields: dict[str, Scalar]) -> None:
        sets = ', '.join(f'e.`{field}` = ${field}' for field in ELEMENT_FIELDS)
        self._rows(f'MERGE (e:Element {{address: $address}}) SET {sets}', address=address,
                   **{field: fields.get(field) for field in ELEMENT_FIELDS})

    def delete_element(self, address: str, keys: list[str]) -> None:
        """Delete an element with its own wants, a want on itself, and its records in every overlay table."""
        for key in keys:
            self.delete_records(key, address)
        self._rows('MATCH (e:Element {address: $address}) DETACH DELETE e', address=address)

    def beneath(self, address: str) -> list[str]:
        rows = self._rows('MATCH (e:Element) WHERE e.address STARTS WITH $prefix RETURN e.address ORDER BY e.address',
                          prefix=address + '.')
        return [str(row[0]) for row in rows]

    # Wants

    def holders(self, address: str) -> list[str]:
        """The elements whose wants name this address, each once, in address order."""
        rows = self._rows('MATCH (h:Element)-[:Wants]->(e:Element {address: $address}) RETURN DISTINCT h.address '
                          'ORDER BY h.address', address=address)
        return [str(row[0]) for row in rows]

    def wants_of(self, holder: str) -> list[dict[str, Scalar]]:
        rows = self._rows('MATCH (h:Element {address: $address})-[w:Wants]->(e:Element) '
                          'RETURN e.address, w.why, w.how, w.direction, w.ref', address=holder)
        wants = [{'element': row[0], **dict(zip(WANT_FIELDS, row[1:]))} for row in rows]
        return sorted(wants, key=lambda want: (str(want['element']), str(want['ref'] or '')))

    def pairs(self) -> list[tuple[str, str]]:
        rows = self._rows('MATCH (h:Element)-[:Wants]->(e:Element) RETURN DISTINCT h.address, e.address '
                          'ORDER BY h.address, e.address')
        return [(str(row[0]), str(row[1])) for row in rows]

    def remove_wants(self, holder: str, element: str, ref: str | None, every: bool = False) -> None:
        """Remove the holder's want on the element with this ref, or with no ref; with `every`, all its wants on it."""
        match = 'MATCH (h:Element {address: $holder})-[w:Wants]->(e:Element {address: $element})'
        if every:
            self._rows(f'{match} DELETE w', holder=holder, element=element)
        elif ref is None:
            self._rows(f'{match} WHERE w.ref IS NULL DELETE w', holder=holder, element=element)
        else:
            self._rows(f'{match} WHERE w.ref = $ref DELETE w', holder=holder, element=element, ref=ref)

    def add_want(self, holder: str, element: str, want: dict[str, Scalar]) -> None:
        self._rows('MATCH (h:Element {address: $holder}), (e:Element {address: $element}) '
                   'CREATE (h)-[:Wants {why: $why, how: $how, direction: $direction, ref: $ref}]->(e)',
                   holder=holder, element=element, **{field: want.get(field) for field in WANT_FIELDS})

    # Overlay definitions

    def parts(self) -> dict[str, dict[str, Scalar]]:
        rows = self._rows(f'MATCH (p:OverlayPart) RETURN p.address, {_PART_COLUMNS} ORDER BY p.address')
        return {str(row[0]): dict(zip(PART_FIELDS, row[1:])) for row in rows}

    def put_part(self, address: str, fields: dict[str, Scalar]) -> None:
        sets = ', '.join(f'p.`{field}` = $p_{field}' for field in PART_FIELDS)
        self._rows(f'MERGE (p:OverlayPart {{address: $address}}) SET {sets}', address=address,
                   **{f'p_{field}': fields.get(field) for field in PART_FIELDS})

    def delete_part(self, address: str) -> None:
        self._rows('MATCH (p:OverlayPart {address: $address}) DELETE p', address=address)

    # Overlay tables and their records

    def overlay_keys(self) -> list[str]:
        rows = self._rows('CALL show_tables() RETURN name')
        return sorted(str(row[0])[3:] for row in rows if str(row[0]).startswith('ov_'))

    def create_overlay(self, key: str, columns: dict[str, str]) -> None:
        fields = ''.join(f', {_column(field)} {_kind(kind)}' for field, kind in columns.items())
        self._rows(f'CREATE NODE TABLE {_table(key)}(id SERIAL PRIMARY KEY, address STRING, position INT64, '
                   f'ref STRING{fields})')

    def add_column(self, key: str, field: str, kind: str) -> None:
        self._rows(f'ALTER TABLE {_table(key)} ADD {_column(field)} {_kind(kind)}')

    def drop_column(self, key: str, field: str) -> None:
        self._rows(f'ALTER TABLE {_table(key)} DROP {_column(field)}')

    def drop_overlay(self, key: str) -> None:
        self._rows(f'DROP TABLE {_table(key)}')

    def records(self, key: str, address: str, fields: list[str]) -> list[dict[str, Scalar]]:
        columns = ''.join(f', r.{_column(field)}' for field in fields)
        rows = self._rows(f'MATCH (r:{_table(key)}) WHERE r.address = $address RETURN r.ref{columns} '
                          'ORDER BY r.position', address=address)
        return [dict(zip(['ref', *fields], row)) for row in rows]

    def record_count(self, key: str, address: str) -> int:
        rows = self._rows(f'MATCH (r:{_table(key)}) WHERE r.address = $address RETURN count(*)', address=address)
        return int(rows[0][0] or 0)

    def first_holder(self, key: str) -> str | None:
        rows = self._rows(f'MATCH (r:{_table(key)}) RETURN r.address ORDER BY r.address LIMIT 1')
        return str(rows[0][0]) if rows else None

    def field_in_use(self, key: str, field: str) -> bool:
        rows = self._rows(f'MATCH (r:{_table(key)}) WHERE r.{_column(field)} IS NOT NULL RETURN count(*)')
        return bool(rows[0][0])

    def next_position(self, key: str, address: str) -> int:
        rows = self._rows(f'MATCH (r:{_table(key)}) WHERE r.address = $address RETURN max(r.position)',
                          address=address)
        last = rows[0][0] if rows else None
        return int(last) + 1 if isinstance(last, int) else 0

    def insert_record(self, key: str, address: str, position: int, record: dict[str, Scalar]) -> None:
        fields = [field for field in record if field != 'ref']
        columns = ''.join(f', {_column(field)}: $v{index}' for index, field in enumerate(fields))
        values = {f'v{index}': record[field] for index, field in enumerate(fields)}
        self._rows(f'CREATE (:{_table(key)} {{address: $address, position: $position, ref: $ref{columns}}})',
                   address=address, position=position, ref=record.get('ref'), **values)

    def delete_records(self, key: str, address: str) -> None:
        self._rows(f'MATCH (r:{_table(key)}) WHERE r.address = $address DELETE r', address=address)


def _kind(kind: str) -> str:
    if kind not in COLUMN_TYPES:
        raise StoreError(f'{kind!r} is not a column type')
    return kind
