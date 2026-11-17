"""One project's map in LadybugDB, at `<home>/maps/<project>.lbug`.

The map is a graph, in the structure of the Rust form (`core/metaform/rust/crates/metaform-store/src/graph.rs`), which
the founder confirmed on 2026-11-17, with the founder's later decisions of 2026-11-15/16:

    (Map) -ROOT-> (Project) -CONTAINS-> (Element) -CONTAINS-> (Element) ...   the namespace tree, as edges
    (Element) -Wants {why, how, direction, ref}-> (Element)                 wants, as edges
    (Element) -HOLDS-> (ov_<key>)                                           overlay records, as edges

`Map` is the map, keyed by the project's stored name. `Project` is the project's root: it holds the project's own id, name
and source, where the Rust form keeps them on its root element `.`. Every element is reached from the root by exactly
one `CONTAINS` from its parent address, a top-level element from `Project` itself (R-4.16). The engine's names
are not case-sensitive, so the root node cannot be called `Root` beside the relationship `ROOT`. `Element` holds one row per
address, the address without the project's name as its key and one column per field of an element. `OverlayPart` holds
the parts of overlay definitions, everything beneath the `overlay` root. Each overlay has a node table `ov_<key>` of its
own, one column `f_<field>` per field of its definition, its position in the list and its `ref`: the records stored as
structs of arrays, the founder's decision of 2026-11-15, each reached from its element by `HOLDS`. The fixed tables are
named in capitals and every overlay table starts with `ov_`, so the two never meet.

Every value reaches the engine as a query parameter. The only names written into query text are the fixed tables and
the overlay tables and columns, and those are checked here against the form of a step before use.
"""
from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self, cast

import ladybug  # pyright: ignore[reportMissingTypeStubs]

from metaform.project import texts

Scalar = str | int | float | bool | None
ELEMENT_FIELDS = ('technical_name', 'name', 'role', 'ref', 'status')
ROOT_FIELDS = ('id', 'name', 'project')  # what the project's root holds: the project's own id, name and source
PART_FIELDS = ('description', 'instruction', 'type', 'rule', 'example', 'optional')
WANT_FIELDS = ('why', 'how', 'direction', 'ref')
COLUMN_TYPES = ('STRING', 'DOUBLE', 'BOOLEAN')
_NAME = re.compile(r'[a-z0-9]+(?:_[a-z0-9]+)*\Z')

_SCHEMA = (
    ('CREATE NODE TABLE Element(address STRING PRIMARY KEY, `technical_name` STRING, `name` STRING, `role` STRING, '
     '`ref` STRING, `status` STRING)'),
    # Every column is quoted: `optional` is a word of the engine's Cypher, and a bare column of that name is refused.
    ('CREATE NODE TABLE OverlayPart(address STRING PRIMARY KEY, `description` STRING, `instruction` STRING, '
     '`type` STRING, `rule` STRING, `example` STRING, `optional` BOOLEAN, ordinal INT64)'),
    'CREATE REL TABLE Wants(FROM Element TO Element, why STRING, how STRING, direction STRING, ref STRING)',
    # The project's own fields, held at its root: one row.
    'CREATE NODE TABLE Project(k STRING PRIMARY KEY, `id` STRING, `name` STRING, `project` STRING)',
    # The id of each write that was stored, written in the write's own transaction, so a write sent twice is done once.
    'CREATE NODE TABLE Request(id STRING PRIMARY KEY, seq SERIAL)',
    *(_MEMORY := (
        # The memory layer: the entities and relations of the MCP reference memory server, kept beside the map and
        # never in an overlay. An entity whose `entityType` is null is an object of the graph, named by its address,
        # that holds memory; its type is read from the object. `seq` keeps the order the reference returns things in.
        'CREATE NODE TABLE MemoryEntity(name STRING PRIMARY KEY, entityType STRING, observations STRING[], seq SERIAL)',
        'CREATE REL TABLE MemoryRelation(FROM MemoryEntity TO MemoryEntity, relationType STRING, seq INT64)',
    )),
    *(_TREE := (
        'CREATE NODE TABLE Map(id STRING PRIMARY KEY)',
        'CREATE REL TABLE ROOT(FROM Map TO Project)',
        'CREATE REL TABLE CONTAINS(FROM Project TO Element, FROM Element TO Element)',
    )),
)
HOLDS = 'HOLDS'  # the relationship from an element to each of its overlay records, one pair per overlay table
DEPTH = 30  # the bound of a walk down the tree: the engine walks at most 30 steps, deeper than any address
REQUESTS_KEPT = 10000  # the most recent write ids kept; a write is only ever sent again within moments of the first
_ELEMENT_COLUMNS = ', '.join(f'e.`{field}`' for field in ELEMENT_FIELDS)
_PART_COLUMNS = ', '.join(f'p.`{field}`' for field in PART_FIELDS)


class StoreError(Exception):
    """The engine failed. `unknown` is true when the failure came at commit, so the write may or may not be stored."""

    def __init__(self, message: str, unknown: bool = False) -> None:
        super().__init__(message)
        self.unknown = unknown


# Each open database: a 64 MiB buffer pool and 4 worker threads. The engine's own defaults size the pool from the
# machine's memory, and a process holding several databases open ran out at about seven.
_BUFFER_POOL = 64 * 1024 * 1024
_THREADS = 4


class _Engine:
    """The one place that calls `ladybug`, which has no type information. Everything it returns is plain rows. An
    engine is one connection; `sharing` makes another connection on the same open database, for a reader."""

    def __init__(self, path: Path, sharing: _Engine | None = None) -> None:
        try:
            self._owns = sharing is None
            self._database: Any = (ladybug.Database(str(path), buffer_pool_size=_BUFFER_POOL,
                                                    max_num_threads=_THREADS)
                                   if sharing is None else sharing._database)
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
        if self._owns:
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
    """One connection to an open project database. `owner.Database` holds the one that writes, on its writer thread,
    and makes a `reader` for each thread that reads. Only one process may hold a database open."""

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
                self._plant(create)
                for address, fields in texts.wants_definition(create).items():
                    self.put_part(address, dict(fields))
        else:
            self._upgrade()

    def _plant(self, project: str) -> None:
        """The map's node and the project's root, joined by `ROOT`."""
        self._rows("MERGE (m:Map {id: $id}) MERGE (r:Project {k: 'root'}) MERGE (m)-[:ROOT]->(r)", id=project)

    def _tables(self) -> set[str]:
        return {str(row[0]) for row in self._rows('CALL show_tables() RETURN name')}

    def _upgrade(self) -> None:
        """Bring a database made before the tree and `HOLDS` were stored to the graph's structure, once: the map and
        its `ROOT`, a `CONTAINS` to every element from its parent, and a `HOLDS` to every overlay record from the element
        its address names. A database already in that structure is left as it is."""
        tables = self._tables()
        if 'MemoryEntity' not in tables:  # a database made before the memory layer gains its tables, empty
            with self.transaction():
                for statement in _MEMORY:
                    self._rows(statement)
        overlays = sorted(name for name in tables if name.startswith('ov_'))
        if 'Map' in tables and 'Root' not in tables and (HOLDS in tables or not overlays):
            return
        with self.transaction():
            if 'Root' in tables:  # the project's root before the tree: the same node under the name `Project`
                self._rows('ALTER TABLE Root RENAME TO Project')
            if 'Map' not in tables:
                for statement in _TREE:
                    self._rows(statement)
                self._plant(self.path.stem)
                for row in self._rows('MATCH (e:Element) RETURN e.address ORDER BY e.address'):
                    self._contain(str(row[0]))
            if overlays and HOLDS not in tables:
                pairs = ', '.join(f'FROM Element TO {name}' for name in overlays)
                self._rows(f'CREATE REL TABLE {HOLDS}({pairs})')
                for name in overlays:
                    self._rows(f'MATCH (e:Element), (r:{name}) WHERE r.address = e.address CREATE (e)-[:{HOLDS}]->(r)')
    def reader(self) -> Store:
        """Another connection on the same open database. It sees the last committed state and never waits for a
        write in progress on this one."""
        other = object.__new__(Store)
        other.path = self.path
        other._engine = _Engine(self.path, sharing=self._engine)
        return other

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

    @contextmanager
    def reading(self) -> Generator[None]:
        """One read is one read-only transaction: it cannot write, and every query in it sees the same committed
        state, whatever is written meanwhile."""
        self._rows('BEGIN TRANSACTION READ ONLY')
        try:
            yield
        finally:
            try:
                self._rows('COMMIT')
            except StoreError:
                pass  # a query that failed has already ended the transaction

    def root(self) -> dict[str, Scalar]:
        columns = ', '.join(f'r.`{field}`' for field in ROOT_FIELDS)
        rows = self._rows(f"MATCH (r:Project {{k: 'root'}}) RETURN {columns}")
        return dict(zip(ROOT_FIELDS, rows[0])) if rows else dict.fromkeys(ROOT_FIELDS)

    def put_root(self, fields: dict[str, Scalar]) -> None:
        sets = ', '.join(f'r.`{field}` = $r_{field}' for field in ROOT_FIELDS)
        self._rows(f"MERGE (r:Project {{k: 'root'}}) SET {sets}",
                   **{f'r_{field}': fields.get(field) for field in ROOT_FIELDS})

    def request_done(self, request: str) -> bool:
        return bool(self._rows('MATCH (r:Request {id: $id}) RETURN count(*)', id=request)[0][0])

    def record_request(self, request: str) -> None:
        """Record a stored write's id, and drop the ids too old to be sent again."""
        row = self._rows('CREATE (r:Request {id: $id}) RETURN r.seq', id=request)
        seq = row[0][0]
        if isinstance(seq, int) and seq and seq % 1000 == 0:
            self._rows('MATCH (r:Request) WHERE r.seq < $oldest DELETE r', oldest=seq - REQUESTS_KEPT)

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
        self._contain(address)

    def _contain(self, address: str) -> None:
        """The one `CONTAINS` that reaches this element from its parent: the element above it, made empty where it is
        missing, or the project's root for a top-level element."""
        parent = address.rpartition('.')[0]
        if not parent:
            self._rows("MATCH (r:Project {k: 'root'}), (e:Element {address: $address}) MERGE (r)-[:CONTAINS]->(e)",
                       address=address)
            return
        if not self._rows('MATCH (p:Element {address: $parent}) RETURN count(*)', parent=parent)[0][0]:
            self._rows('CREATE (:Element {address: $parent})', parent=parent)
            self._contain(parent)
        self._rows('MATCH (p:Element {address: $parent}), (e:Element {address: $address}) '
                   'MERGE (p)-[:CONTAINS]->(e)', parent=parent, address=address)

    def delete_element(self, address: str, keys: list[str]) -> None:
        """Delete an element with its own wants, a want on itself, and its records in every overlay table."""
        for key in keys:
            self.delete_records(key, address)
        self._rows('MATCH (e:Element {address: $address}) DETACH DELETE e', address=address)

    def beneath(self, address: str) -> list[str]:
        """Every element beneath this one, walked down the tree by `CONTAINS` one level at a time, in address order. A
        walk of many steps in one query took the engine's whole buffer pool once the map was large (2026-11-17), so
        each level is one plain query of the elements the level above holds."""
        found: list[str] = []
        level = [address]
        for _ in range(DEPTH):
            rows = self._rows('MATCH (p:Element)-[:CONTAINS]->(e:Element) WHERE p.address IN $level RETURN e.address',
                              level=level)
            level = [str(row[0]) for row in rows]
            if not level:
                break
            found.extend(level)
        return sorted(found)

    def tree(self) -> list[tuple[str, str]]:
        """Every `CONTAINS` edge as (parent, child), the project's root written `.`, for a reader that draws the tree
        or checks its shape."""
        top = self._rows("MATCH (:Project {k: 'root'})-[:CONTAINS]->(e:Element) RETURN e.address ORDER BY e.address")
        rest = self._rows('MATCH (p:Element)-[:CONTAINS]->(e:Element) RETURN p.address, e.address '
                          'ORDER BY p.address, e.address')
        return [('.', str(row[0])) for row in top] + [(str(row[0]), str(row[1])) for row in rest]

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

    def all_wants(self) -> list[tuple[str, dict[str, Scalar]]]:
        """Every want of the project with its fields, each beside the address of the element that holds it."""
        rows = self._rows('MATCH (h:Element)-[w:Wants]->(e:Element) RETURN h.address, e.address, w.why, w.how, '
                          'w.direction, w.ref ORDER BY h.address, e.address')
        return [(str(row[0]), {'element': row[1], **dict(zip(WANT_FIELDS, row[2:]))}) for row in rows]

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

    def objects(self, addresses: list[str]) -> dict[str, str]:
        """Of these addresses, the ones the graph holds an object at, each with the type its memory reports: an
        element's technical name (`element` when it has none), `overlay` for an overlay's definition and `overlay
        field` for one of its fields. Only the addresses asked for are read."""
        if not addresses:
            return {}
        found = {str(row[0]): str(row[1] or 'element') for row in self._rows(
            'MATCH (e:Element) WHERE e.address IN $addresses RETURN e.address, e.`technical_name`',
            addresses=addresses)}
        for row in self._rows('MATCH (p:OverlayPart) WHERE p.address IN $addresses RETURN p.address, p.`instruction`',
                              addresses=addresses):
            found[str(row[0])] = 'overlay' if row[1] is not None else 'overlay field'
        return found

    def memory_entities(self) -> list[tuple[str, str | None, list[str]]]:
        """Every entity of the memory layer in the order it was made: its name, its type (null for an object of the
        graph) and its observations in the order they were added."""
        rows = self._rows('MATCH (m:MemoryEntity) RETURN m.name, m.entityType, m.observations ORDER BY m.seq')
        return [(str(row[0]), None if row[1] is None else str(row[1]),
                 [str(one) for one in cast(list[object], row[2] or [])]) for row in rows]

    def memory_relations(self) -> list[tuple[str, str, str]]:
        """Every relation of the memory layer in the order it was made: from, to and its type."""
        rows = self._rows('MATCH (a:MemoryEntity)-[r:MemoryRelation]->(b:MemoryEntity) '
                          'RETURN a.name, b.name, r.relationType ORDER BY r.seq')
        return [(str(row[0]), str(row[1]), str(row[2])) for row in rows]

    def put_memory_entity(self, name: str, entity_type: str | None, observations: list[str]) -> None:
        self._rows('CREATE (:MemoryEntity {name: $name, entityType: $type, observations: $observations})',
                   name=name, type=entity_type, observations=observations)

    def set_observations(self, name: str, observations: list[str]) -> None:
        self._rows('MATCH (m:MemoryEntity {name: $name}) SET m.observations = $observations', name=name,
                   observations=observations)

    def delete_memory_entities(self, names: list[str]) -> None:
        """Remove these entities with every relation to or from them."""
        self._rows('MATCH (m:MemoryEntity) WHERE m.name IN $names DETACH DELETE m', names=names)

    def add_memory_relation(self, start: str, end: str, relation_type: str) -> None:
        last = self._rows('MATCH ()-[r:MemoryRelation]->() RETURN max(r.seq)')
        seq = int(cast(int, last[0][0])) + 1 if last and last[0][0] is not None else 0
        self._rows('MATCH (a:MemoryEntity {name: $source}), (b:MemoryEntity {name: $target}) '
                   'CREATE (a)-[:MemoryRelation {relationType: $type, seq: $seq}]->(b)',
                   source=start, target=end, type=relation_type, seq=seq)

    def delete_memory_relation(self, start: str, end: str, relation_type: str) -> None:
        self._rows('MATCH (a:MemoryEntity {name: $source})-[r:MemoryRelation {relationType: $type}]->'
                   '(b:MemoryEntity {name: $target}) DELETE r', source=start, target=end, type=relation_type)

    def parts(self) -> dict[str, dict[str, Scalar]]:
        """Every part of every overlay definition, in the order the parts were first written: a definition's fields
        keep the order their writer gave them."""
        rows = self._rows(f'MATCH (p:OverlayPart) RETURN p.address, {_PART_COLUMNS} ORDER BY p.ordinal, p.address')
        return {str(row[0]): dict(zip(PART_FIELDS, row[1:])) for row in rows}

    def put_part(self, address: str, fields: dict[str, Scalar]) -> None:
        sets = ', '.join(f'p.`{field}` = $p_{field}' for field in PART_FIELDS)
        values = {f'p_{field}': fields.get(field) for field in PART_FIELDS}
        if self._rows('MATCH (p:OverlayPart {address: $address}) RETURN count(*)', address=address)[0][0]:
            self._rows(f'MATCH (p:OverlayPart {{address: $address}}) SET {sets}', address=address, **values)
            return
        last = self._rows('MATCH (p:OverlayPart) RETURN max(p.ordinal)')[0][0]
        self._rows(f'CREATE (p:OverlayPart {{address: $address, ordinal: $ordinal}}) SET {sets}', address=address,
                   ordinal=(int(last) + 1 if isinstance(last, (int, float)) else 0), **values)

    def delete_part(self, address: str) -> None:
        self._rows('MATCH (p:OverlayPart {address: $address}) DELETE p', address=address)

    # Overlay tables and their records

    def overlay_keys(self) -> list[str]:
        rows = self._rows('CALL show_tables() RETURN name')
        return sorted(str(row[0])[3:] for row in rows if str(row[0]).startswith('ov_'))

    def create_overlay(self, key: str, columns: dict[str, str]) -> None:
        """The overlay's own table, and its pair in `HOLDS`, so each record is reached from its element."""
        fields = ''.join(f', {_column(field)} {_kind(kind)}' for field, kind in columns.items())
        table = _table(key)
        self._rows(f'CREATE NODE TABLE {table}(id SERIAL PRIMARY KEY, position INT64, ref STRING{fields})')
        if HOLDS in self._tables():
            self._rows(f'ALTER TABLE {HOLDS} ADD FROM Element TO {table}')
        else:
            self._rows(f'CREATE REL TABLE {HOLDS}(FROM Element TO {table})')

    def add_column(self, key: str, field: str, kind: str) -> None:
        self._rows(f'ALTER TABLE {_table(key)} ADD {_column(field)} {_kind(kind)}')

    def drop_column(self, key: str, field: str) -> None:
        self._rows(f'ALTER TABLE {_table(key)} DROP {_column(field)}')

    def drop_overlay(self, key: str) -> None:
        """The overlay's table, after its pair in `HOLDS`; `HOLDS` itself goes with the last overlay."""
        table = _table(key)
        others = [name for name in self._tables() if name.startswith('ov_') and name != table]
        if others:
            self._rows(f'ALTER TABLE {HOLDS} DROP FROM Element TO {table}')
        elif HOLDS in self._tables():
            self._rows(f'DROP TABLE {HOLDS}')
        self._rows(f'DROP TABLE {table}')

    def _held_at(self, key: str) -> str:
        """The pattern of an element's records in one overlay, reached by `HOLDS`; `$address` names the element."""
        return f'MATCH (:Element {{address: $address}})-[:{HOLDS}]->(r:{_table(key)})'

    def records(self, key: str, address: str, fields: list[str]) -> list[dict[str, Scalar]]:
        columns = ''.join(f', r.{_column(field)}' for field in fields)
        rows = self._rows(f'{self._held_at(key)} RETURN r.ref{columns} ORDER BY r.position', address=address)
        return [dict(zip(['ref', *fields], row)) for row in rows]

    def all_records(self, key: str, fields: list[str]) -> list[tuple[str, int, dict[str, Scalar]]]:
        """Every record of an overlay in the project, each with the address of the element that holds it and its
        position there."""
        columns = ''.join(f', r.{_column(field)}' for field in fields)
        rows = self._rows(f'MATCH (e:Element)-[:{HOLDS}]->(r:{_table(key)}) RETURN e.address, r.position, '
                          f'r.ref{columns} ORDER BY e.address, r.position')
        return [(str(row[0]), cast(int, row[1]), dict(zip(['ref', *fields], row[2:]))) for row in rows]

    def record_count(self, key: str, address: str) -> int:
        rows = self._rows(f'{self._held_at(key)} RETURN count(*)', address=address)
        return int(rows[0][0] or 0)

    def held(self, key: str) -> tuple[int, int]:
        """How many records the overlay holds, and at how many addresses."""
        rows = self._rows(f'MATCH (e:Element)-[:{HOLDS}]->(r:{_table(key)}) RETURN count(*), count(DISTINCT e.address)')
        return int(rows[0][0] or 0), int(rows[0][1] or 0)

    def field_in_use(self, key: str, field: str) -> bool:
        rows = self._rows(f'MATCH (r:{_table(key)}) WHERE r.{_column(field)} IS NOT NULL RETURN count(*)')
        return bool(rows[0][0])

    def next_position(self, key: str, address: str) -> int:
        rows = self._rows(f'{self._held_at(key)} RETURN max(r.position)', address=address)
        last = rows[0][0] if rows else None
        return int(last) + 1 if isinstance(last, int) else 0

    def insert_record(self, key: str, address: str, position: int, record: dict[str, Scalar]) -> None:
        """One record, created with the `HOLDS` that reaches it from its element."""
        fields = [field for field in record if field != 'ref']
        columns = ''.join(f', {_column(field)}: $v{index}' for index, field in enumerate(fields))
        values = {f'v{index}': record[field] for index, field in enumerate(fields)}
        self._rows(f'MATCH (e:Element {{address: $address}}) '
                   f'CREATE (e)-[:{HOLDS}]->(:{_table(key)} {{position: $position, ref: $ref{columns}}})',
                   address=address, position=position, ref=record.get('ref'), **values)

    def replace_record(self, key: str, address: str, position: int, record: dict[str, Scalar]) -> None:
        """Rewrite the one record at `position`; the other records of the list are not touched."""
        self._rows(f'{self._held_at(key)} WHERE r.position = $position DETACH DELETE r', address=address,
                   position=position)
        self.insert_record(key, address, position, record)

    def delete_records_at(self, key: str, address: str, positions: list[int]) -> None:
        """Remove the records at `positions`, and close the gaps so a record's position stays its place in the list."""
        self._rows(f'{self._held_at(key)} WHERE r.position IN $positions DETACH DELETE r', address=address,
                   positions=positions)
        rows = self._rows(f'{self._held_at(key)} RETURN r.id, r.position ORDER BY r.position', address=address)
        for index, (ident, position) in enumerate(rows):
            if position != index:
                self._rows(f'MATCH (r:{_table(key)}) WHERE r.id = $id SET r.position = $position', id=ident,
                           position=index)

    def delete_records(self, key: str, address: str) -> None:
        self._rows(f'{self._held_at(key)} DETACH DELETE r', address=address)


def _kind(kind: str) -> str:
    if kind not in COLUMN_TYPES:
        raise StoreError(f'{kind!r} is not a column type')
    return kind
