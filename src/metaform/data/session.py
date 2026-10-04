"""Transactions on one metaform's store, STORE-006 and STORE-037.

Every operation opens its own connection, runs one transaction and closes it.
`atomic()` is the one exception: while its block runs, every operation on the
same project, in the same thread or task, joins its one connection and
transaction, and nested blocks join the outer one.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .. import changes, home, sqlite
from ..errors import StoreError
from .schema import STORE_SCHEMA
from .upgrade import upgrade

if TYPE_CHECKING:
    from .tables import Tables


@dataclass
class Tx:
    """One open transaction: its connection, its metaform, and the layers created inside it."""
    db: sqlite3.Connection
    metaform_id: str | None
    project_id: str
    writing: bool
    created: set[str] = field(default_factory=set[str])
    named: bool = False
    toggled: tuple[str, ...] = ()
    module: str | None = None

    def execute(self, statement: str, values: Any = ()) -> sqlite3.Cursor:
        """Issue SQL through the DAO inside this operation's transaction."""
        return self.db.execute(statement, values)

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
        """The operation owner's metaform tables on this same transaction."""
        from . import tables
        declared = tables.declared(self.module, retained=True)
        assert self.module is not None
        module = self.module
        path = home.store_path(self.project_id, self.metaform_id) if self.metaform_id else Path()
        def opener(place: tables.Place) -> tuple[sqlite3.Connection, Path, bool]:
            if place != 'metaform':
                raise StoreError('A map transaction reaches metaform-level tables.',
                                 'use Store.tables() for a project-level transaction')
            if self.writing:
                tables.ensure(self.db, path, module, declared, place)
                return self.db, path, True
            return self.db, path, tables.state(self.db, module, declared, place) == 'ready'
        return tables.TableTx(module, declared, write=self.writing, opener=opener)

    def layers(self) -> Any:
        from .selection import all_layers
        return all_layers(self.db)


_ATOMIC: ContextVar[Tx | None] = ContextVar('metaform_atomic', default=None)


@contextmanager
def open_store(path: Path, *, write: bool,
               required: tuple[str, Tables] | None = None) -> Generator[sqlite3.Connection, None, None]:
    """A prepared connection to one store file, opened inside its lock, STORE-006."""
    with sqlite.opened(path, STORE_SCHEMA, write=write, version=sqlite.SCHEMA_VERSION, upgrade=upgrade) as db:
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
    """Opens transactions on one metaform of one project: the active one, or the one named."""

    def __init__(self, project_id: str, metaform_id: str | None = None) -> None:
        self.project_id = project_id
        self.metaform_id = metaform_id

    def _metaform(self, *, create: bool) -> home.Metaform | None:
        if self.metaform_id is not None:
            return home.metaform_by_id(self.project_id, self.metaform_id)
        return home.ensure_metaform(self.project_id) if create else home.active_metaform(self.project_id)

    def _joined(self) -> Tx | None:
        active = _ATOMIC.get()
        if active is None or active.project_id != self.project_id:
            return None
        if self.metaform_id is not None:
            return active if active.metaform_id == self.metaform_id else None
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
            raise StoreError(f'Project {self.project_id} has no metaform {self.metaform_id}.', 'metaform list metaforms')
        path = home.store_file(self.project_id, metaform.name)
        with open_store(path, write=True) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield Tx(db, metaform.metaform_id, self.project_id, True, named=self.metaform_id is not None)
            except BaseException:
                db.execute('ROLLBACK')
                raise
            db.execute('COMMIT')
            if db.total_changes:  # the chassis announces it when the command ends, VIEW-018
                changes.note(self.project_id, metaform.metaform_id)

    @contextmanager
    def read(self, *, required: tuple[str, Tables] | None = None) -> Generator[Tx, None, None]:
        joined = self._joined()
        if joined is not None:
            if required is not None:
                from . import tables
                path = home.store_path(self.project_id, joined.metaform_id) if joined.metaform_id else Path()
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
        with open_store(home.store_file(self.project_id, metaform.name), write=False, required=required) as db:
            db.execute('BEGIN')
            try:
                yield Tx(db, metaform.metaform_id, self.project_id, False)
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
