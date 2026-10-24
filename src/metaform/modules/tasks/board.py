"""Temporary, reopenable worker records and worksheets. Callers publish their changes."""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import tempfile
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast


def _decoded(value: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(value))


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class Board:
    def __init__(self, project: str) -> None:
        if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._-]*', project) or project in ('.', '..'):
            raise ValueError('A project ID must be one safe path segment.')
        self.path = Path(os.environ.get('TMPDIR') or tempfile.gettempdir()) / '.metadata' / project / 'sessions.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workers (agent_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rounds (ticket TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ratings (
                    ticket TEXT NOT NULL, reviewer TEXT NOT NULL, target TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY (ticket, reviewer, target));
                CREATE TABLE IF NOT EXISTS outbox (
                    key TEXT PRIMARY KEY, agent TEXT NOT NULL, text TEXT NOT NULL);
            ''')

    @contextmanager
    def _db(self) -> Generator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _worker(db: sqlite3.Connection, agent_id: str) -> dict[str, Any] | None:
        row = db.execute('SELECT data FROM workers WHERE agent_id = ?', (agent_id,)).fetchone()
        return _decoded(row[0]) if row else None

    @staticmethod
    def _round(db: sqlite3.Connection, ticket: str) -> dict[str, Any] | None:
        row = db.execute('SELECT data FROM rounds WHERE ticket = ?', (ticket,)).fetchone()
        return _decoded(row[0]) if row else None

    @staticmethod
    def _put_worker(db: sqlite3.Connection, worker: dict[str, Any]) -> None:
        db.execute('INSERT INTO workers VALUES (?, ?) ON CONFLICT(agent_id) DO UPDATE SET data = excluded.data',
                   (worker['agent_id'], _dump(worker)))

    @staticmethod
    def _put_round(db: sqlite3.Connection, round_: dict[str, Any]) -> None:
        db.execute('INSERT INTO rounds VALUES (?, ?) ON CONFLICT(ticket) DO UPDATE SET data = excluded.data',
                   (round_['ticket'], _dump(round_)))

    def register(self, agent_id: str, name: str, work_id: str, session_id: str = '',
                 context: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._db() as db:
            old = self._worker(db, agent_id)
            worker: dict[str, Any] = old or {
                'agent_id': agent_id, 'name': name, 'work_id': work_id, 'session_id': session_id,
                'context': context, 'current': '', 'next': '', 'state': 'starting', 'waiting_for': None, 'nodes': []}
            worker.update(name=name, work_id=work_id)
            if session_id:
                worker['session_id'] = session_id
            if context is not None:
                worker['context'] = context
            self._put_worker(db, worker)
            return worker

    def worker(self, id: str) -> dict[str, Any] | None:
        with self._db() as db:
            return self._worker(db, id)

    def workers(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return [_decoded(row[0]) for row in db.execute('SELECT data FROM workers ORDER BY rowid')]

    def patch(self, id: str, fields: dict[str, Any]) -> None:
        if 'agent_id' in fields and fields['agent_id'] != id:
            raise ValueError('A worker ID cannot change.')
        if 'state' in fields and fields['state'] not in ('starting', 'working', 'idle', 'waiting', 'draining'):
            raise ValueError('Unknown worker state.')
        with self._db() as db:
            worker = self._worker(db, id)
            if worker is None:
                raise KeyError(id)
            worker.update(fields)
            if 'nodes' in fields:
                worker['_nodes_explicit'] = True
            self._put_worker(db, worker)

    def remove(self, id: str) -> None:
        with self._db() as db:
            db.execute('DELETE FROM workers WHERE agent_id = ?', (id,))
            db.execute('DELETE FROM outbox WHERE agent = ?', (id,))
            if db.execute('SELECT 1 FROM workers LIMIT 1').fetchone() is None:
                for table in ('rounds', 'ratings', 'outbox'):
                    db.execute(f'DELETE FROM {table}')

    def clear(self) -> None:
        with self._db() as db:
            for table in ('workers', 'rounds', 'ratings', 'outbox'):
                db.execute(f'DELETE FROM {table}')

    def set_round(self, ticket: str, phrase: str, holder: str, items: list[str | dict[str, Any]],
                  nodes: list[str], partner: str | None = None) -> dict[str, Any]:
        with self._db() as db:
            old = self._round(db, ticket)
            old_items = cast(list[dict[str, Any]], old['items']) if old else []
            by_id = {str(item['id']): item for item in old_items}
            remaining = list(old_items)
            worksheet: list[dict[str, Any]] = []
            seen: set[str] = set()
            for supplied in items:
                text = supplied if isinstance(supplied, str) else str(supplied.get('text') or '')
                explicit = str(supplied.get('id') or '') if isinstance(supplied, dict) else ''
                previous = by_id.get(explicit) if explicit else next(
                    (item for item in remaining if item['text'] == text and str(item['id']) not in seen), None)
                item_id = explicit or (str(previous['id']) if previous else uuid.uuid4().hex)
                if item_id in seen:
                    raise ValueError('Worksheet item IDs must be unique.')
                item = dict(previous) if previous else {'id': item_id, 'text': text, 'done': False}
                if isinstance(supplied, dict):
                    item.update(supplied)
                item.update(id=item_id, text=text)
                worksheet.append(item)
                seen.add(item_id)
            round_: dict[str, Any] = {**(old or {}),
                'ticket': ticket, 'phrase': phrase, 'holder': holder,
                'partner': partner if partner is not None else old.get('partner') if old else None,
                'items': worksheet, 'nodes': nodes, 'completed': bool(old and old.get('completed'))}
            self._put_round(db, round_)
            worker = self._worker(db, holder)
            if worker is not None:
                slot = 'next' if worker['current'] and worker['current'] != ticket else 'current'
                worker[slot] = ticket
                self._put_worker(db, worker)
            return round_

    def round(self, ticket: str) -> dict[str, Any] | None:
        with self._db() as db:
            return self._round(db, ticket)

    def rounds(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return [_decoded(row[0]) for row in db.execute('SELECT data FROM rounds ORDER BY rowid')]

    def pair(self, ticket: str, partner: str) -> dict[str, Any]:
        with self._db() as db:
            round_ = self._round(db, ticket)
            if round_ is None:
                raise KeyError(ticket)
            worker = self._worker(db, partner)
            if worker is None:
                raise KeyError(partner)
            round_['partner'] = partner
            occupied = bool(worker['current'] and worker['current'] != ticket)
            worker['next' if occupied else 'current'] = ticket
            self._put_worker(db, worker)
            holder = self._worker(db, str(round_['holder']))
            if holder is not None:
                holder['waiting_for'] = partner if occupied else None
                self._put_worker(db, holder)
            self._put_round(db, round_)
            return round_

    def check(self, ticket: str, item_id: str, done: bool = True) -> dict[str, Any]:
        with self._db() as db:
            round_ = self._round(db, ticket)
            if round_ is None:
                raise KeyError(ticket)
            items = cast(list[dict[str, Any]], round_['items'])
            item = next((item for item in items if item['id'] == item_id), None)
            if item is None:
                raise KeyError(item_id)
            item['done'] = done
            self._put_round(db, round_)
            return round_

    def rate(self, ticket: str, reviewer: str, target: str,
             scores: dict[str, Any]) -> dict[str, Any]:
        if any(isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score)
               or score < 0 for score in scores.values()):
            raise ValueError('Category scores must be finite nonnegative numbers.')
        total = sum(scores.values())
        if total > 100:
            raise ValueError('The total score must be between 0 and 100.')
        rating: dict[str, Any] = {'ticket': ticket, 'reviewer': reviewer, 'target': target,
                                  'scores': scores, 'total': total}
        with self._db() as db:
            if self._round(db, ticket) is None:
                raise KeyError(ticket)
            db.execute('INSERT OR REPLACE INTO ratings VALUES (?, ?, ?, ?)',
                       (ticket, reviewer, target, _dump(rating)))
        return rating

    def ratings(self, ticket: str) -> list[dict[str, Any]]:
        with self._db() as db:
            return [_decoded(row[0]) for row in db.execute(
                'SELECT data FROM ratings WHERE ticket = ? ORDER BY reviewer, target', (ticket,))]

    def complete_round(self, ticket: str) -> dict[str, Any]:
        with self._db() as db:
            round_ = self._round(db, ticket)
            if round_ is None:
                raise KeyError(ticket)
            if not round_['completed']:
                planned: dict[str, list[str]] = {}
                for participant in (round_['holder'], round_['partner']):
                    if participant is not None:
                        worker = self._worker(db, str(participant))
                        planned[str(participant)] = self._planned_nodes(
                            round_, str(participant), worker if worker and worker['current'] == ticket else None)
                round_['participant_nodes'] = planned
            round_['completed'] = True
            self._put_round(db, round_)
            affected: list[str] = []
            for row in db.execute('SELECT data FROM workers ORDER BY rowid').fetchall():
                worker = _decoded(row[0])
                if worker['current'] == ticket:
                    worker['current'], worker['next'] = worker['next'], ''
                    worker['nodes'], worker['_nodes_explicit'] = [], False
                elif worker['next'] == ticket:
                    worker['next'] = ''
                else:
                    continue
                worker['waiting_for'] = None
                affected.append(str(worker['agent_id']))
                self._put_worker(db, worker)
            return {'ticket': ticket, 'affected': affected}

    @staticmethod
    def _progress(round_: dict[str, Any], agent_id: str | None = None) -> dict[str, int]:
        items = cast(list[dict[str, Any]], round_['items'])
        selected = [item for item in items if agent_id is None or item.get('agent') in (None, agent_id)]
        return {'checked': sum(bool(item.get('done')) for item in selected), 'total': len(selected)}

    @staticmethod
    def _planned_nodes(round_: dict[str, Any], agent_id: str,
                       worker: dict[str, Any] | None = None) -> list[str]:
        historical = cast(dict[str, list[str]], round_.get('participant_nodes') or {})
        if round_['completed'] and agent_id in historical:
            return historical[agent_id]
        if worker is not None and (worker.get('_nodes_explicit') or worker.get('nodes')):
            return cast(list[str], worker.get('nodes') or [])
        allocated: list[str] = []
        provided = False
        for item in cast(list[dict[str, Any]], round_['items']):
            if item.get('agent') in (None, agent_id) and 'nodes' in item:
                allocated.extend(cast(list[str], item['nodes']))
                provided = True
        return allocated if provided else cast(list[str], round_['nodes'])

    def view(self, viewer: str | None = None) -> list[dict[str, Any]]:
        with self._db() as db:
            workers = [_decoded(row[0]) for row in db.execute('SELECT data FROM workers ORDER BY rowid')]
            rounds = {_decoded(row[0])['ticket']: _decoded(row[0])
                      for row in db.execute('SELECT data FROM rounds ORDER BY rowid')}
            ratings = [_decoded(row[0]) for row in db.execute('SELECT data FROM ratings')]
        result: list[dict[str, Any]] = []
        for worker in workers:
            agent_id = str(worker['agent_id'])
            if agent_id == viewer:
                continue
            past: list[dict[str, Any]] = []
            received: list[float] = []
            for round_ in rounds.values():
                if not round_['completed'] or agent_id not in (round_['holder'], round_['partner']):
                    continue
                points = [float(rating['total']) for rating in ratings
                          if rating['ticket'] == round_['ticket'] and rating['target'] == agent_id]
                average = sum(points) / len(points) if points else None
                if average is not None:
                    received.append(average)
                past.append({'ticket': round_['ticket'], 'phrase': round_['phrase'],
                             'nodes': self._planned_nodes(round_, agent_id), 'rating': average})
            current = rounds.get(worker['current'])
            next_ = rounds.get(worker['next'])
            progress = self._progress(current, agent_id) if current else {'checked': 0, 'total': 0}
            context = cast(dict[str, Any], worker.get('context') or {})
            used: Any = context.get('used')
            size: Any = context.get('size')
            occupancy = used / size * 100 if isinstance(used, (int, float)) and \
                isinstance(size, (int, float)) and size > 0 else None
            result.append({'agent_id': agent_id, 'name': worker['name'],
                           'rating': sum(received) / len(received) if received else None,
                           'context': occupancy,
                           'complete': progress['checked'] / progress['total'] * 100 if progress['total'] else None,
                           'next': self._summary(next_, agent_id) if next_ else None,
                           'current': self._summary(current, agent_id, worker) if current else None, 'past': past})
        return result

    @classmethod
    def _summary(cls, round_: dict[str, Any], agent_id: str,
                 worker: dict[str, Any] | None = None) -> dict[str, Any]:
        return {'ticket': round_['ticket'], 'phrase': round_['phrase'],
                'nodes': cls._planned_nodes(round_, agent_id, worker),
                **cls._progress(round_, agent_id)}

    def enqueue(self, agent: str, key: str, text: str) -> None:
        with self._db() as db:
            db.execute('INSERT OR IGNORE INTO outbox VALUES (?, ?, ?)', (key, agent, text))

    def pending(self, agent: str) -> list[dict[str, str]]:
        with self._db() as db:
            return [{'key': row[0], 'text': row[1]} for row in db.execute(
                'SELECT key, text FROM outbox WHERE agent = ? ORDER BY rowid', (agent,))]

    def delivered(self, key: str) -> None:
        with self._db() as db:
            db.execute('DELETE FROM outbox WHERE key = ?', (key,))

    def waiters(self, partner: str) -> list[dict[str, Any]]:
        return [worker for worker in self.workers() if worker.get('waiting_for') == partner]
