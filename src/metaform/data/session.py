"""Transactions on one metaform's store, STORE-006 and STORE-037.

Every operation opens its own connection, runs one transaction and closes it.
`atomic()` is the one exception: while its block runs, every operation on the
same project, in the same thread or task, joins its one connection and
transaction, and nested blocks join the outer one.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from .. import home, sqlite
from ..errors import StoreError
from .schema import STORE_SCHEMA


@dataclass
class Tx:
    """One open transaction: its connection, its metaform, and the layers created inside it."""
    db: sqlite3.Connection
    metaform_id: str | None
    project_id: str
    writing: bool
    created: set[str] = field(default_factory=set)
    named: bool = False


_ATOMIC: ContextVar[Tx | None] = ContextVar('metaform_atomic', default=None)


def _open(path: Path, *, create: bool) -> sqlite3.Connection:
    db = sqlite.connect(path)
    try:
        sqlite.prepare(db, path, STORE_SCHEMA, create=create)
    except BaseException:
        db.close()
        raise
    db.row_factory = sqlite3.Row
    return db


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

    @contextmanager
    def write(self) -> Iterator[Tx]:
        joined = self._joined()
        if joined is not None:
            yield joined
            return
        metaform = self._metaform(create=True)
        if metaform is None:
            raise StoreError(f'Project {self.project_id} has no metaform {self.metaform_id}.', 'metaform list metaforms')
        path = home.store_path(self.project_id, metaform.metaform_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = _open(path, create=True)
        try:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield Tx(db, metaform.metaform_id, self.project_id, True, named=self.metaform_id is not None)
            except BaseException:
                db.execute('ROLLBACK')
                raise
            db.execute('COMMIT')
        finally:
            db.close()

    @contextmanager
    def read(self) -> Iterator[Tx]:
        joined = self._joined()
        if joined is not None:
            yield joined
            return
        metaform = self._metaform(create=False)
        path = None if metaform is None else home.store_path(self.project_id, metaform.metaform_id)
        if path is None or not path.exists():
            db = sqlite.memory(STORE_SCHEMA)
            db.row_factory = sqlite3.Row
            try:
                yield Tx(db, None if metaform is None else metaform.metaform_id, self.project_id, False)
            finally:
                db.close()
            return
        db = _open(path, create=False)
        try:
            db.execute('BEGIN')
            try:
                yield Tx(db, metaform.metaform_id if metaform else None, self.project_id, False)
            finally:
                db.execute('COMMIT')
        finally:
            db.close()

    @contextmanager
    def atomic(self) -> Iterator[Tx]:
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
