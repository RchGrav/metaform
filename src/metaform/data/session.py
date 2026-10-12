"""Transactions on one base's store, STORE-006, STORE-037 and STORE-046.

Every operation opens and closes its own connection and transaction, and works on this process's projection of
the base, caught up to the log first. A write gathers ops as it reasons, applies each to the projection at once,
so what it reads back inside the transaction is what it wrote, and appends them all to the log at commit; a
rollback reads the projection whole again from the log. `atomic()` is the one exception to one transaction per
operation: while its block runs, every operation on the same project, in the same thread or task, joins its one
connection and transaction, and nested blocks join the outer one.
"""
from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import changes, home, sqlite
from ..errors import StoreError
from . import log
from .projection import Op, Projection
from .schema import STORE_SCHEMA
from .upgrade import upgrade

if TYPE_CHECKING:
    from .tables import Tables


SESSION_ID = uuid.uuid4().hex  # who wrote each op: one id per process, a session boundary is where it changes


@dataclass
class Tx:
    """One open transaction: its connection, its base's projection, and the ops it has gathered."""
    db: sqlite3.Connection
    base_id: str | None
    project_id: str
    writing: bool
    base: Projection = field(default_factory=Projection)
    created: set[str] = field(default_factory=set[str])
    named: bool = False
    toggled: tuple[str, ...] = ()
    module: str | None = None
    path: Path = field(default_factory=Path)
    pending: list[Op] = field(default_factory=list[Op])
    kinds: set[str] = field(default_factory=set[str])  # the kinds of op this transaction wrote, VIEW-018

    def execute(self, statement: str, values: Any = ()) -> sqlite3.Cursor:
        """Issue SQL through the DAO inside this operation's transaction: a module's own tables."""
        return self.db.execute(statement, values)

    def emit(self, op: str, kind: str, ident: str, layer_id: str, data: dict[str, Any]) -> Op:
        """One op: applied to the projection now, appended to the log at commit."""
        if not self.writing:
            raise StoreError('A read transaction writes nothing.', 'metaform help map knowledge')
        made = Op(self.base.seq + 1, SESSION_ID, op, kind, ident, layer_id, data)
        self.base.apply(made)
        self.pending.append(made)
        self.kinds.add(kind)
        return made

    @property
    def rows(self) -> Any:
        from . import rows
        from .operations import Access
        return Access(self, rows)

    @property
    def views(self) -> Any:
        from . import views
        from .operations import Access
        return Access(self, views)

    @property
    def reads(self) -> Any:
        from . import reads
        from .operations import Access
        return Access(self, reads)

    def operation(self, name: str, *args: Any, **kwargs: Any) -> Any:
        from .operations import invoke
        return invoke(self, name, *args, **kwargs)

    def tables(self) -> Any:
        """The operation owner's base-level tables on this same transaction."""
        from . import tables
        declared = tables.declared(self.module, retained=True)
        assert self.module is not None
        module = self.module
        path = self.path
        def opener(place: tables.Place) -> tuple[sqlite3.Connection, Path, bool]:
            if place != 'metaform':
                raise StoreError('A map transaction reaches base-level tables.',
                                 'use Store.tables() for a project-level transaction')
            if self.writing:
                tables.ensure(self.db, path, module, declared, place)
                return self.db, path, True
            return self.db, path, tables.state(self.db, module, declared, place) == 'ready'
        return tables.TableTx(module, declared, write=self.writing, opener=opener)

    def layers(self) -> Any:
        from .selection import all_layers
        return all_layers(self.base)

    def number(self, address: str) -> int:
        """The next number at an address, from the project's counter, for an item this transaction writes there; taken
        in a transaction of its own, so a write that fails leaves a gap and never reuses a number, `numbers.py`."""
        from . import numbers
        return numbers.take(numbers.project_folder(self.project_id), address)


_ATOMIC: ContextVar[Tx | None] = ContextVar('metaform_atomic', default=None)


@contextmanager
def open_store(path: Path, *, write: bool,
               required: tuple[str, Tables] | None = None) -> Generator[sqlite3.Connection, None, None]:
    """A prepared connection to one store file, opened inside its lock, STORE-006."""
    with sqlite.opened(path, STORE_SCHEMA, write=write, version=sqlite.SCHEMA_VERSION,
                       compatible=sqlite.COMPATIBLE_FROM, upgrade=upgrade) as db:
        db.row_factory = sqlite3.Row
        from . import tables
        if not tables.extensions_ready(db) or required is not None and tables.state(
                db, required[0], required[1], 'metaform') != 'ready':
            db.execute('BEGIN IMMEDIATE')
            try:
                tables.ensure_extensions(db, path)
                if required is not None:
                    tables.ensure(db, path, required[0], required[1], 'metaform')
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        yield db


class Session:
    """Opens transactions on one base of one project: the active one, or the one named."""

    def __init__(self, project_id: str, base_id: str | None = None) -> None:
        self.project_id = project_id
        self.base_id = base_id

    def _metaform(self, *, create: bool) -> home.Base | None:
        if self.base_id is not None:
            return home.base_by_id(self.project_id, self.base_id)
        return home.ensure_base(self.project_id) if create else home.active_base(self.project_id)

    def _joined(self) -> Tx | None:
        active = _ATOMIC.get()
        if active is None or active.project_id != self.project_id:
            return None
        if self.base_id is not None:
            return active if active.base_id == self.base_id else None
        return None if active.named else active

    @property
    def in_atomic(self) -> bool:
        """Whether this session joins the current atomic transaction."""
        return self._joined() is not None

    @contextmanager
    def write(self) -> Generator[Tx, None, None]:
        joined = self._joined()
        if joined is not None:
            yield joined
            return
        metaform = self._metaform(create=True)
        if metaform is None:
            raise StoreError(f'Project {self.project_id} has no base {self.base_id}.', 'metaform list bases')
        path = home.store_file(self.project_id, metaform.name)
        with open_store(path, write=True) as db:
            written = changes.watch(db)
            db.execute('BEGIN IMMEDIATE')
            held = log.projection(path, db)
            with held.lock:
                tx = Tx(db, metaform.id, self.project_id, True, held, named=self.base_id is not None, path=path)
                try:
                    yield tx
                    log.append(db, tx.pending, home.now())
                    log.snapshot_if_due(db, held)
                except BaseException:
                    db.execute('ROLLBACK')
                    if tx.pending:
                        log.forget(path)  # the projection applied ops the log never took: read it whole again
                    raise
                db.execute('COMMIT')
            if db.total_changes:  # the chassis announces it when the command ends, VIEW-018
                changes.note(self.project_id, metaform.id, written | {f'op:{kind}' for kind in tx.kinds}, held.seq)

    @contextmanager
    def read(self, *, required: tuple[str, Tables] | None = None) -> Generator[Tx, None, None]:
        joined = self._joined()
        if joined is not None:
            if required is not None:
                from . import tables
                path = joined.path
                tables.ensure(joined.db, path, required[0], required[1], 'metaform')
            yield joined
            return
        metaform = self._metaform(create=False)
        if metaform is None:
            db = sqlite.memory(STORE_SCHEMA)
            db.row_factory = sqlite3.Row
            from . import tables
            tables.ensure_extensions(db, Path())
            if required is not None:
                tables.ensure(db, Path(), required[0], required[1], 'metaform')
            try:
                yield Tx(db, None, self.project_id, False)
            finally:
                db.close()
            return
        path = home.store_file(self.project_id, metaform.name)
        with open_store(path, write=False, required=required) as db:
            db.execute('BEGIN')
            try:
                held = log.projection(path, db)
                with held.lock:
                    yield Tx(db, metaform.id, self.project_id, False, held, path=path)
            finally:
                db.execute('COMMIT')

    @contextmanager
    def atomic(self) -> Generator[Tx, None, None]:
        joined = self._joined()
        if joined is not None:
            yield joined
            return
        with self.write() as tx:
            token = _ATOMIC.set(tx)
            try:
                yield tx
            finally:
                _ATOMIC.reset(token)
