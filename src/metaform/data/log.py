"""The op log of a base's store, and the projection each process keeps of it, STORE-046.

The store file holds `ops`, append only, `objects`, the registry of every id and its kind, and `snapshots`, the
projection as of a sequence, written now and then so a large log opens by a snapshot and a short replay. The
modules' own declared tables live in the same file as before. Every write appends its ops in one transaction under
`BEGIN IMMEDIATE`; nothing is ever edited. Each process holds one `Projection` per store file and catches it up by
reading the ops past the last sequence it applied, on every transaction.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .projection import OBJECT_KINDS, Op, Projection, ops_from_rows

LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS ops(
  seq        INTEGER PRIMARY KEY,
  session_id TEXT NOT NULL,
  at         TEXT NOT NULL,
  op         TEXT NOT NULL CHECK(op IN ('add','change','remove')),
  kind       TEXT NOT NULL,
  id         TEXT NOT NULL,
  layer_id   TEXT NOT NULL,
  data       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ops_by_id ON ops(id, seq);
CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY, kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(seq INTEGER PRIMARY KEY, graph TEXT NOT NULL);
"""
SNAPSHOT_EVERY = 1000  # ops past the last snapshot before a session writes a new one

_PROJECTIONS: dict[str, Projection] = {}
_GUARD = threading.Lock()


def projection(path: Path | str, db: sqlite3.Connection) -> Projection:
    """This process's projection of the store at `path`, caught up to the log the connection sees. A file that
    turned out to hold another log, a restored backup for one, is read whole again."""
    key = str(path)
    with _GUARD:
        held = _PROJECTIONS.get(key)
    if held is None:
        held = load(db)
        with _GUARD:
            _PROJECTIONS[key] = held
        return held
    with held.lock:
        if not _consistent(held, db):
            fresh = load(db)
            with _GUARD:
                _PROJECTIONS[key] = fresh
            return fresh
        catch_up(held, db)
    return held


def forget(path: Path | str) -> None:
    """Drop the projection of a store file that was removed or replaced."""
    with _GUARD:
        _PROJECTIONS.pop(str(path), None)


def _consistent(held: Projection, db: sqlite3.Connection) -> bool:
    """Whether the log still holds the last op the projection applied: a file replaced under the same name, by a
    restore or a collapse, holds another log and is read whole again."""
    if held.last is None:
        return db.execute('SELECT 1 FROM ops LIMIT 1').fetchone() is None or held.seq == 0
    seq, session_id, ident = held.last
    row = db.execute('SELECT session_id, id FROM ops WHERE seq=?', (seq,)).fetchone()
    return row is not None and (str(row[0]), str(row[1])) == (session_id, ident)


def load(db: sqlite3.Connection) -> Projection:
    """The projection from the newest snapshot and the ops after it, or from the whole log."""
    snap = db.execute('SELECT seq, graph FROM snapshots ORDER BY seq DESC LIMIT 1').fetchone()
    made = Projection.from_snapshot(json.loads(str(snap[1]))) if snap is not None else Projection()
    catch_up(made, db)
    return made


def catch_up(held: Projection, db: sqlite3.Connection) -> int:
    """Apply the ops past the last sequence applied: usually none or a few rows."""
    rows = db.execute('SELECT seq, session_id, op, kind, id, layer_id, data FROM ops WHERE seq > ? ORDER BY seq',
                      (held.seq,)).fetchall()
    for op in ops_from_rows(rows):
        held.apply(op)
    return len(rows)


def append(db: sqlite3.Connection, ops: list[Op], at: str) -> None:
    """Write the ops a transaction gathered, each at the sequence the projection applied it at."""
    for op in ops:
        if op.kind in OBJECT_KINDS:
            db.execute('INSERT OR IGNORE INTO objects(id, kind) VALUES (?, ?)', (op.id, op.kind))
        db.execute('INSERT INTO ops(seq, session_id, at, op, kind, id, layer_id, data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (op.seq, op.session_id, op.at or at, op.op, op.kind, op.id, op.layer_id,
                    json.dumps(op.data, ensure_ascii=False, sort_keys=True)))


def snapshot_if_due(db: sqlite3.Connection, held: Projection) -> None:
    """At the end of a write, a snapshot of the projection once enough ops have gone by since the last one. The
    log is never truncated: a snapshot only shortens the replay of a large log."""
    last = db.execute('SELECT MAX(seq) FROM snapshots').fetchone()[0]
    if held.seq - int(last or 0) >= SNAPSHOT_EVERY:
        db.execute('INSERT OR REPLACE INTO snapshots(seq, graph) VALUES (?, ?)',
                   (held.seq, json.dumps(held.snapshot(), ensure_ascii=False, sort_keys=True)))


def read_ops(db: sqlite3.Connection, after: int, limit: int | None = None) -> list[dict[str, Any]]:
    """The ops past a sequence, as plain data, for a page that applies them, VIEW-018."""
    sql = 'SELECT seq, session_id, at, op, kind, id, layer_id, data FROM ops WHERE seq > ? ORDER BY seq'
    rows = db.execute(sql + (f' LIMIT {int(limit)}' if limit else ''), (after,)).fetchall()
    return [{'seq': int(row[0]), 'session_id': str(row[1]), 'at': str(row[2]), 'op': str(row[3]),
             'kind': str(row[4]), 'id': str(row[5]), 'layer_id': str(row[6]), 'data': json.loads(str(row[7]))}
            for row in rows]
