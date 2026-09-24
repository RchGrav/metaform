"""The join store: every record is a join owned by the element that receives it.

Each project has one store in the Metaform home. A join has an id; saving a
changed body adds a new revision, and every earlier revision stays readable.
Saving an identical body again changes nothing.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from . import home

_SCHEMA = (
    'CREATE TABLE IF NOT EXISTS objects(address TEXT PRIMARY KEY, name_length INTEGER NOT NULL)',
    'CREATE TABLE IF NOT EXISTS joins(address TEXT NOT NULL, join_id TEXT NOT NULL, revision INTEGER NOT NULL, '
    'body TEXT NOT NULL, PRIMARY KEY(address, join_id, revision))',
)


def _encode(body: dict) -> str:
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


class Store:
    def __init__(self, project: str):
        self.project = project
        self.path = home.home() / 'projects' / project / 'store.sqlite3'

    @contextmanager
    def _db(self, write=False):
        if not write and not self.path.exists():
            db = sqlite3.connect(':memory:')
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path)
        for statement in _SCHEMA:
            db.execute(statement)
        try:
            yield db
            if write:
                db.commit()
        finally:
            db.close()

    def put(self, address: str, body: dict, *, name_length: int = 1) -> dict:
        """Save a join on its receiving element. Returns its reference and whether it changed."""
        identifier = str(body['id'])
        encoded = _encode(body)
        with self._db(write=True) as db:
            db.execute('INSERT OR IGNORE INTO objects(address, name_length) VALUES (?, ?)', (address, name_length))
            row = db.execute('SELECT revision, body FROM joins WHERE address=? AND join_id=? '
                             'ORDER BY revision DESC LIMIT 1', (address, identifier)).fetchone()
            if row and row[1] == encoded:
                return {'address': address, 'join_id': identifier, 'revision': row[0], 'changed': False}
            revision = (row[0] + 1) if row else 1
            db.execute('INSERT INTO joins(address, join_id, revision, body) VALUES (?, ?, ?, ?)',
                       (address, identifier, revision, encoded))
            return {'address': address, 'join_id': identifier, 'revision': revision, 'changed': True}

    def latest(self) -> list[tuple[dict, dict]]:
        """Every join at its current revision, as (reference, body)."""
        with self._db() as db:
            rows = db.execute('SELECT j.address, j.join_id, j.revision, j.body FROM joins j '
                              'JOIN (SELECT address, join_id, MAX(revision) r FROM joins GROUP BY address, join_id) m '
                              'ON j.address=m.address AND j.join_id=m.join_id AND j.revision=m.r '
                              'ORDER BY j.address, j.join_id').fetchall()
        return [({'address': a, 'join_id': i, 'revision': r}, json.loads(b)) for a, i, r, b in rows]

    def read(self, ref: dict) -> dict | None:
        with self._db() as db:
            row = db.execute('SELECT body FROM joins WHERE address=? AND join_id=? AND revision=?',
                             (ref['address'], ref['join_id'], ref['revision'])).fetchone()
        return json.loads(row[0]) if row else None

    def objects(self) -> dict[str, int]:
        with self._db() as db:
            return dict(db.execute('SELECT address, name_length FROM objects ORDER BY address').fetchall())
