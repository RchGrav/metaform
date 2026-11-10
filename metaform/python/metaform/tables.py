"""A project's maps in SQLite, laid out as a structure of arrays
(`docs/designs/sqlite-forms.md`, sections 3.2, 3.3 and 4). It has the role that `graph.rs` has in
the Rust form.

One narrow table for each field and each layer, keyed by element. No table holds an element as
one record. Stored addresses and catalog names are camelCase; the agent's snake_case form exists
only in memory and on the wire (R-4.11). Every value goes in as a bound parameter, and every
table name is a quoted identifier, so no field name can alter a statement.

SQLite ignores the case of ASCII letters in a table name, so `f_fooBar` (the field `foo_bar`)
and `f_foobar` (the field `foobar`) would be one table. `Catalog` gives the later of two such
names the table `f__<the name in snake_case>`, and finds each table by an exact match.
"""
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import names
from .model import Effect, Element, Map
from .values import ascii_lower, dumps, loads, same

SCHEMA = """
CREATE TABLE IF NOT EXISTS map     (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS element (key     INTEGER PRIMARY KEY,
                                    map     TEXT    NOT NULL REFERENCES map(id),
                                    address TEXT    NOT NULL,
                                    parent  INTEGER REFERENCES element(key),
                                    UNIQUE (map, address));
CREATE TABLE IF NOT EXISTS wants   (element   INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                                    provider  INTEGER NOT NULL REFERENCES element(key),
                                    why       TEXT NOT NULL,
                                    how       TEXT NOT NULL,
                                    direction TEXT NOT NULL,
                                    PRIMARY KEY (element, provider)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS field   (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS layer   (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS holds   (element INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,
                                    layer   TEXT    NOT NULL REFERENCES layer(name),
                                    PRIMARY KEY (element, layer)) WITHOUT ROWID;
"""

# How long a connection waits in line for the write lock, in milliseconds.
BUSY_TIMEOUT = 5000


def connect(path: Path) -> sqlite3.Connection:
    """Open a database with the pragmas every connection sets. With
    `isolation_level=None` the `sqlite3` module starts no transaction itself; this form writes
    every `BEGIN`, `COMMIT` and `ROLLBACK`."""
    connection = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT / 1000, isolation_level=None)
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT}")
    # SQLite does not wait in line to adjust the journal mode of a new database that another
    # process is adjusting at the same moment. Try again until the busy time ends.
    deadline = time.monotonic() + BUSY_TIMEOUT / 1000
    while True:
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            break
        except sqlite3.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def quoted(name: str) -> str:
    """A table name as a quoted identifier, with every `"` doubled."""
    return '"' + name.replace('"', '""') + '"'


def create_schema(connection: sqlite3.Connection) -> None:
    """Make the fixed tables of a project's database, if it does not have them yet."""
    found = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'holds'").fetchone()
    if found is not None:
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in SCHEMA.split(";"):
            if statement.strip():
                connection.execute(statement)
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        raise


class Corrupt(Exception):
    """Stored data that is not in the expected form."""


class Catalog:
    """The field tables and layer tables that a database has: the table of each stored name.

    A field's table is `f_<stored name>` and a layer's is `l_<stored name>`. When that name
    would equal the name of a table that exists, but for the case of ASCII letters, the table is
    `f__<the name in snake_case>` (or `l__...`). A stored name holds no underscore, so that name
    is always free. The character U+0000 cannot be written in SQL text, so a table name has a
    period in its place; no stored name holds a period.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.tables = {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.fields = {name: self.find("f", name) for (name,) in connection.execute("SELECT name FROM field")}
        self.layers = {name: self.find("l", name) for (name,) in connection.execute("SELECT name FROM layer")}

    @staticmethod
    def candidates(kind: str, stored: str) -> tuple[str, str]:
        plain, other = f"{kind}_{stored}", f"{kind}__{names.agent_name(stored)}"
        return plain.replace("\0", "."), other.replace("\0", ".")

    def find(self, kind: str, stored: str) -> str:
        """The table of a stored name, by an exact match that respects case."""
        for table in self.candidates(kind, stored):
            if table in self.tables:
                return table
        raise Corrupt(f"the catalog names {stored}, which has no table")

    def choose(self, kind: str, stored: str) -> str:
        """The table for a stored name that has none yet."""
        plain, other = self.candidates(kind, stored)
        taken = {ascii_lower(table) for table in self.tables}
        table = other if ascii_lower(plain) in taken else plain
        self.tables.add(table)
        return table


def load(connection: sqlite3.Connection, map_id: str, catalog: Catalog) -> Map:
    """Load one map. A map never written is the empty map: the root alone. The caller holds a
    transaction, so every table is read in one committed state."""
    by_key: dict[int, Element] = {}
    elements: dict[str, Element] = {}
    for key, address in connection.execute("SELECT key, address FROM element WHERE map = ?", (map_id,)):
        element = Element()
        by_key[key] = element
        elements[names.agent_name(address)] = element
    for stored, table in sorted(catalog.fields.items()):
        name = names.agent_name(stored)
        rows = connection.execute(
            f"SELECT f.element, f.value FROM {quoted(table)} f JOIN element e ON e.key = f.element WHERE e.map = ?",
            (map_id,),
        )
        for key, value in rows:
            by_key[key].fields[name] = loads(value)
    rows = connection.execute(
        "SELECT h.element, h.layer FROM holds h JOIN element e ON e.key = h.element WHERE e.map = ?", (map_id,)
    )
    for key, stored in rows:
        name = names.agent_name(stored)
        if name in by_key[key].fields:
            raise Corrupt(f"an element holds {name} both as a field and as a layer")
        by_key[key].fields[name] = []
    for stored, table in sorted(catalog.layers.items()):
        name = names.agent_name(stored)
        rows = connection.execute(
            f"SELECT l.element, l.data FROM {quoted(table)} l JOIN element e ON e.key = l.element"
            " WHERE e.map = ? ORDER BY l.element, l.ordinal",
            (map_id,),
        )
        for key, data in rows:
            records = by_key[key].fields.get(name)
            if not isinstance(records, list):
                raise Corrupt(f"an element has records of the layer {name} and no row in holds")
            records.append(loads(data))
    rows = connection.execute(
        "SELECT w.element, b.address, w.why, w.how, w.direction FROM wants w"
        " JOIN element a ON a.key = w.element JOIN element b ON b.key = w.provider WHERE a.map = ?",
        (map_id,),
    )
    for key, provider, why, how, direction in rows:
        by_key[key].wants[names.agent_name(provider)] = {"why": why, "how": how, "direction": direction}
    return Map.from_elements(elements)


def depth(address: str) -> int:
    """How far an address is beneath the root, for an order that puts children before parents."""
    return address.count(".")


class Writer:
    """Stores one effect inside the caller's transaction, as a difference: only the elements the
    command touched, and for each one only the fields, wants and layer rows that changed.
    `before` is the map the effect was computed from, and it equals what the database holds."""

    def __init__(self, connection: sqlite3.Connection, map_id: str, catalog: Catalog) -> None:
        self.connection = connection
        self.map_id = map_id
        self.catalog = catalog
        self.keys: dict[str, int] = {}

    def persist(self, before: Map, effect: Effect) -> None:
        """Elements first, parents before children. Then fields, layers and wants, so every want
        finds its provider. Then removals: the removed elements' wants, then the elements, children
        before parents."""
        run = self.connection.execute
        run("INSERT OR IGNORE INTO map (id) VALUES (?)", (self.map_id,))
        written = [address for address in sorted(effect.elements) if effect.elements[address] is not None]
        removed = [address for address in effect.elements if effect.elements[address] is None]
        for address in written:
            self.key(address, create=True)
        empty = Element()
        for address in written:
            after = effect.elements[address]
            assert after is not None
            old = before.element(address) or empty
            self.write_fields(self.key(address), old, after)
            self.write_wants(self.key(address), old, after)
        # One command can remove an element and the empty element it wanted (`commands.prune`).
        # The wants rows of every removed element go first, so no removed provider is still named.
        keys = [self.key(address) for address in sorted(removed, key=depth, reverse=True)]
        for key in keys:
            run("DELETE FROM wants WHERE element = ?", (key,))
        for key in keys:
            if key is not None:
                run("DELETE FROM element WHERE key = ?", (key,))

    def key(self, address: str, create: bool = False) -> Any:
        """The key of the element row at an address. With `create`, a missing row is made, and
        the rows above it first."""
        if address in self.keys:
            return self.keys[address]
        stored = names.stored_name(address)
        row = self.connection.execute(
            "SELECT key FROM element WHERE map = ? AND address = ?", (self.map_id, stored)
        ).fetchone()
        if row is None:
            if not create:
                return None
            above = names.parent(address)
            parent_key = None if above is None else self.key(above, create=True)
            cursor = self.connection.execute(
                "INSERT INTO element (map, address, parent) VALUES (?, ?, ?)", (self.map_id, stored, parent_key)
            )
            row = (cursor.lastrowid,)
        key = int(row[0])
        self.keys[address] = key
        return key

    def write_fields(self, key: int, old: Element, after: Element) -> None:
        run = self.connection.execute
        for name, value in old.fields.items():
            if name not in after.fields:
                self.remove_field(key, name, value)
        for name, value in after.fields.items():
            present = name in old.fields
            earlier = old.fields.get(name)
            if present and same(earlier, value):
                continue
            stored = names.stored_name(name)
            if isinstance(value, list):
                if present and not isinstance(earlier, list):
                    self.remove_field(key, name, earlier)
                table = self.layer(stored)
                run("INSERT OR IGNORE INTO holds (element, layer) VALUES (?, ?)", (key, stored))
                kept = earlier if isinstance(earlier, list) else []
                for ordinal, record in enumerate(value):
                    if ordinal >= len(kept):
                        run(f"INSERT INTO {table} (element, ordinal, data) VALUES (?, ?, ?)", (key, ordinal, dumps(record)))
                    elif not same(kept[ordinal], record):
                        run(f"UPDATE {table} SET data = ? WHERE element = ? AND ordinal = ?", (dumps(record), key, ordinal))
                if len(kept) > len(value):
                    run(f"DELETE FROM {table} WHERE element = ? AND ordinal >= ?", (key, len(value)))
            else:
                if isinstance(earlier, list):
                    self.remove_field(key, name, earlier)
                run(
                    f"INSERT INTO {self.field(stored)} (element, value) VALUES (?, ?)"
                    " ON CONFLICT (element) DO UPDATE SET value = excluded.value",
                    (key, dumps(value)),
                )

    def remove_field(self, key: int, name: str, value: Any) -> None:
        run = self.connection.execute
        stored = names.stored_name(name)
        if isinstance(value, list):
            run(f"DELETE FROM {quoted(self.catalog.layers[stored])} WHERE element = ?", (key,))
            run("DELETE FROM holds WHERE element = ? AND layer = ?", (key, stored))
        else:
            run(f"DELETE FROM {quoted(self.catalog.fields[stored])} WHERE element = ?", (key,))

    def write_wants(self, key: int, old: Element, after: Element) -> None:
        run = self.connection.execute
        for other in old.wants:
            if other not in after.wants:
                run("DELETE FROM wants WHERE element = ? AND provider = ?", (key, self.key(other)))
        for other, record in after.wants.items():
            if other in old.wants and same(old.wants[other], record):
                continue
            run(
                "INSERT INTO wants (element, provider, why, how, direction) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (element, provider) DO UPDATE SET why = excluded.why, how = excluded.how,"
                " direction = excluded.direction",
                (key, self.key(other, create=True), record["why"], record["how"], record["direction"]),
            )

    def field(self, stored: str) -> str:
        """The table of a scalar field, made in this transaction if the field is new."""
        if stored not in self.catalog.fields:
            table = self.catalog.choose("f", stored)
            self.connection.execute(
                f"CREATE TABLE {quoted(table)} (element INTEGER PRIMARY KEY REFERENCES element(key) ON DELETE CASCADE,"
                " value TEXT NOT NULL)"
            )
            self.connection.execute("INSERT INTO field (name) VALUES (?)", (stored,))
            self.catalog.fields[stored] = table
        return quoted(self.catalog.fields[stored])

    def layer(self, stored: str) -> str:
        """The table of a layer, made in this transaction if the layer is new."""
        if stored not in self.catalog.layers:
            table = self.catalog.choose("l", stored)
            self.connection.execute(
                f"CREATE TABLE {quoted(table)} (element INTEGER NOT NULL REFERENCES element(key) ON DELETE CASCADE,"
                " ordinal INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY (element, ordinal)) WITHOUT ROWID"
            )
            self.connection.execute("INSERT INTO layer (name) VALUES (?)", (stored,))
            self.catalog.layers[stored] = table
        return quoted(self.catalog.layers[stored])
