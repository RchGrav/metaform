"""Metaform's store: the data behind the one Metaform tool. It has the role that
`metaform-store/src/lib.rs` has in the Rust form, on SQLite
(`docs/designs/sqlite-forms.md`, sections 3 and 4).

- **The home.** `Store` opens a home, checks its format marker and holds the project registry.
- **No server.** Each process opens the databases itself. SQLite's write lock puts the writers of
  one database in a line.
- **Writes.** One transaction for each command, started with `BEGIN IMMEDIATE`, stored as a
  difference and acknowledged after `COMMIT` (R-4.7). A refused command stores nothing (R-5.8).
- **Reads.** One read transaction, so a read sees one committed state.
- **The loaded map** is kept between commands and loaded again only when `PRAGMA data_version`
  shows that another connection committed.
"""
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from . import commands, refusal, registry, specification, tables
from .model import Map
from .refusal import Refusal
from .values import same

# Marks a home this store created. A home with files and no marker is refused, and so is a home
# with another marker, so two engines never write one home.
FORMAT_FILE = "store.format"
FORMAT = "sqlite-soa 1"

# The name a marker has while a process writes it: `store.format.<process id>.tmp`.
DRAFT = re.compile(re.escape(FORMAT_FILE) + r"\.\d+\.tmp")

# The id of a project's main map within the project's database.
MAIN_MAP = "main"


class StoreError(Exception):
    """A store failure that is not a refusal of the command. `stored` says what is known about a
    write: `False` when it was not stored, `None` when the store cannot tell."""

    def __init__(self, message: str, stored: bool | None = None) -> None:
        super().__init__(message)
        self.stored = stored


def default_home() -> Path:
    """The home: `METAFORM_HOME` if set, otherwise `~/.metaform-sqlite`."""
    named = os.environ.get("METAFORM_HOME")
    return Path(named) if named else Path(os.environ.get("HOME", "")) / ".metaform-sqlite"


def check_format(home: Path) -> None:
    """Make the home if it is missing, and refuse a home that this store did not make."""
    home.mkdir(parents=True, exist_ok=True)
    marker = home / FORMAT_FILE
    while True:
        try:
            found = marker.read_text(encoding="utf-8", errors="replace").strip()
            break
        except FileNotFoundError:
            pass
        # Another process's marker that is not yet in place does not count as a file in the home.
        others = [name for name in os.listdir(home) if not DRAFT.fullmatch(name)]
        if others and not marker.exists():
            raise StoreError(
                f"{home} holds files this store did not write (no {FORMAT_FILE}). Nothing was changed. "
                "Use another home (METAFORM_HOME or --home)."
            )
        if not others:
            # Write the marker beside its place and link it into place, so another process sees
            # the marker complete or not at all.
            draft = home / f"{FORMAT_FILE}.{os.getpid()}.tmp"
            draft.write_text(FORMAT + "\n", encoding="utf-8")
            try:
                os.link(draft, marker)
            except FileExistsError:
                pass
            finally:
                draft.unlink()
    if found != FORMAT:
        raise StoreError(
            f"{home} holds a store of another format ({FORMAT_FILE} says \"{found}\"; this form reads \"{FORMAT}\"). "
            "Nothing was changed. Use another home (METAFORM_HOME or --home)."
        )


class Store:
    """The store for one home: the format marker and the project registry."""

    def __init__(self, home: Path) -> None:
        try:
            check_format(home)
            self.home = home
            self.core = tables.connect(home / "metaform.db")
            registry.create_schema(self.core)
        except OSError as error:
            raise StoreError(f"i/o error: {error}") from error
        except sqlite3.Error as error:
            raise StoreError(f"sqlite error: {error}") from error

    def register_project(self, source: Path) -> str:
        """Register a project folder under its last segment as the name, or return the id it
        already has. The id names its folder under `projects/`. Nothing is written into the
        project's own folder."""
        try:
            folder = source.resolve(strict=True)
            return registry.register(self.core, self.home, str(folder), folder.name)
        except OSError as error:
            raise StoreError(f"{source}: {error.strerror or error}") from error
        except sqlite3.Error as error:
            raise StoreError(f"sqlite error: {error}") from error

    def projects(self) -> list[registry.Registered]:
        """Every project registered in this home, by name. Registers nothing."""
        try:
            return registry.list_projects(self.core)
        except sqlite3.Error as error:
            raise StoreError(f"sqlite error: {error}") from error

    def main_map(self, project: str) -> "MapStore":
        """A registered project's main map."""
        try:
            return MapStore(self.home / "projects" / project / "project.db", MAIN_MAP)
        except sqlite3.Error as error:
            raise StoreError(f"sqlite error: {error}") from error


class MapStore:
    """One map in a project's database, as one process uses it."""

    def __init__(self, path: Path, map_id: str) -> None:
        self.connection = tables.connect(path)
        tables.create_schema(self.connection)
        self.map_id = map_id
        # The loaded map, the catalog of tables and the `data_version` they were loaded at.
        self.map: Map | None = None
        self.catalog: tables.Catalog | None = None
        self.version: int | None = None
        # Whether this process has made the map's server-defined layer current (`ensure_defined`).
        self.defined = False

    def execute(self, command: Any) -> Any:
        """Perform one command of the Metaform tool on the map. Returns the result an agent
        receives. Raises `Refusal` when the command broke a rule, and `StoreError` when the store
        failed."""
        try:
            self.ensure_defined()
            verb = next(iter(command), None) if isinstance(command, dict) else None
            if verb not in ("add", "update", "delete"):
                return commands.execute(self.snapshot(), command).result
            return self.write(command)
        except sqlite3.Error as error:
            raise self.failure(error) from error
        except tables.Corrupt as error:
            self.map = None
            raise StoreError(f"stored data is not in the expected form: {error}", stored=False) from error

    def failure(self, error: sqlite3.Error) -> StoreError:
        """A SQLite failure as a store failure. Every transaction that failed was rolled back,
        except one that failed at `COMMIT`, which this cannot tell apart; a busy database fails
        before anything is written."""
        self.map = None
        if isinstance(error, sqlite3.OperationalError) and "locked" in str(error):
            seconds = tables.BUSY_TIMEOUT // 1000
            return StoreError(
                f"the database was busy for more than {seconds} seconds, and the command was not performed", stored=False
            )
        return StoreError(f"sqlite error: {error}")

    def current(self) -> Map:
        """The map as the open transaction sees it. It is loaded on first use, and again when
        `data_version` shows that another connection committed."""
        version = self.connection.execute("PRAGMA data_version").fetchone()[0]
        if self.map is None or self.catalog is None or version != self.version:
            self.catalog = tables.Catalog(self.connection)
            self.map = tables.load(self.connection, self.map_id, self.catalog)
            self.version = version
        return self.map

    def snapshot(self) -> Map:
        """The map's last committed state, read in one read transaction."""
        self.connection.execute("BEGIN")
        try:
            return self.current()
        finally:
            if self.connection.in_transaction:
                self.connection.execute("COMMIT")

    def write(self, command: Any) -> Any:
        """One write: take the write lock, load the map if it changed, perform the command on a
        copy, store the effect as a difference, commit, and only then answer."""
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            before = self.current()
            outcome = commands.execute(before, command)
            if outcome.effect is not None and not outcome.effect.is_empty():
                assert self.catalog is not None
                tables.Writer(self.connection, self.map_id, self.catalog).persist(before, outcome.effect)
            self.connection.execute("COMMIT")
        except Refusal:
            self.connection.execute("ROLLBACK")
            raise
        except BaseException:
            # A rolled-back transaction can leave the catalog naming a table that was not made,
            # so the next command loads the map and the catalog again.
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            self.catalog = None
            raise
        if outcome.map is not None:
            self.map = outcome.map
        return outcome.result

    def ensure_defined(self) -> None:
        """Make the map hold the server-defined layer definitions exactly as the code defines
        them (R-6.24): today the specification layer at `specification.DEFINITION_ADDRESS`. It is
        done once for each process, before the first command, so `goto` always finds the layer
        and the stored definition follows the code. The write goes through `commands.execute`
        like any command. When the definition is already current, nothing is written and the
        write lock is not taken."""
        if self.defined:
            return
        command = definition_command(self.snapshot())
        if command is not None:
            try:
                self.write(command)
            except Refusal as error:
                raise StoreError(
                    f"the server could not write its layer definition: {specification.DEFINITION_ADDRESS}: {error}",
                    stored=False,
                ) from error
        self.defined = True


def definition_command(map: Map) -> dict[str, Any] | None:
    """The `update` that makes the map's specification layer definition equal to
    `specification.definition()`, or `None` when it already is. `update` merges fields, so a
    stored field the definition no longer has is removed with `null` (R-5.5)."""
    wanted = specification.definition()
    current = map.element(specification.DEFINITION_ADDRESS)
    if current is not None and same(current.fields, wanted):
        return None
    fields: dict[str, Any] = dict(wanted)
    for key in current.fields if current is not None else ():
        if key not in wanted:
            fields[key] = None
    return {"update": {specification.DEFINITION_ADDRESS: fields}}


def refusal_json(command: Any, refused: Refusal) -> dict[str, Any]:
    """The JSON an agent receives for a refusal."""
    out: dict[str, Any] = dict(command) if isinstance(command, dict) else {}
    out["status"] = "error"
    out.update(refused.to_json())
    return out


def store_failure_json(command: Any, error: StoreError) -> dict[str, Any]:
    """A store failure as an agent receives it: the same structure as a refusal, with the code
    `INTERNAL_ERROR`. The message is the store's own, followed by what to do before a retry. When
    the store cannot tell whether a write was stored, the message says so: a repeated `add` can
    duplicate entries."""
    if error.stored is False:
        message = f"{error}. Nothing was stored; send the command again."
    else:
        message = f"{error}. A write may or may not be stored; read the element before you retry it."
    return refusal_json(command, Refusal(refusal.INTERNAL_ERROR, message))
