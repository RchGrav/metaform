"""Temporary, reopenable records of the agents online, their worktree rounds, ratings and scores. Callers publish their
changes."""
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

# The categories of a peer rating and their weights, as the project agent's instructions set them: five stars of five
# in each is 100 points, and a rating under five in a category takes its share of the weight from the rated agent's
# score. The bonus, for improving the final work beyond critiquing it, adds five.
CATEGORIES = {'Efficient': 10, 'Alert & Aware': 20, 'Thorough': 30, 'Coordination': 40}
STARS = 5
BONUS = 5
START, MOST = 100, 105  # every agent online starts at 100; the bonus can carry it to 105, never past
STATES = ('starting', 'working', 'idle', 'waiting')


def _decoded(value: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(value))


def _dump(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def points_of(stars: dict[str, Any], bonus: bool) -> float:
    """The points a rating gives: each category's weight by its stars of five, and the bonus."""
    return sum(CATEGORIES[name] * float(stars[name]) / STARS for name in CATEGORIES) + (BONUS if bonus else 0)


class Board:
    def __init__(self, project: str) -> None:
        if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9._-]*', project) or project in ('.', '..'):
            raise ValueError('A project ID must be one safe path segment.')
        self.path = Path(os.environ.get('TMPDIR') or tempfile.gettempdir()) / '.metadata' / project / 'board.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workers (agent_id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rounds (worktree TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS ratings (
                    worktree TEXT NOT NULL, reviewer TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY (worktree, reviewer));
                CREATE TABLE IF NOT EXISTS outbox (
                    key TEXT PRIMARY KEY, agent TEXT NOT NULL, text TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    key TEXT PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL, text TEXT NOT NULL,
                    time TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scores (session_id TEXT PRIMARY KEY, score REAL NOT NULL);
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
    def _round(db: sqlite3.Connection, worktree: str) -> dict[str, Any] | None:
        row = db.execute('SELECT data FROM rounds WHERE worktree = ?', (worktree,)).fetchone()
        return _decoded(row[0]) if row else None

    @staticmethod
    def _put_worker(db: sqlite3.Connection, worker: dict[str, Any]) -> None:
        db.execute('INSERT INTO workers VALUES (?, ?) ON CONFLICT(agent_id) DO UPDATE SET data = excluded.data',
                   (worker['agent_id'], _dump(worker)))

    @staticmethod
    def _put_round(db: sqlite3.Connection, round_: dict[str, Any]) -> None:
        db.execute('INSERT INTO rounds VALUES (?, ?) ON CONFLICT(worktree) DO UPDATE SET data = excluded.data',
                   (round_['worktree'], _dump(round_)))

    # ------------------------------------------------------------------------------------------ agents online

    # A score belongs to a context, the agent's session: it clears with the agent when it shuts down, since a fresh
    # agent starting a new context carries no penalty, and comes back when the same session is resumed. The `scores`
    # table keeps each session's score; a worker row gaining a session id reads it back, and a worker with no session
    # id yet is at 100 (the owner's rule, 2026-10-25).

    @classmethod
    def _joined(cls, db: sqlite3.Connection, worker: dict[str, Any], session_id: str) -> None:
        """The worker row gains a session id: the context's score comes back, or a context not seen before starts its
        record at 100."""
        worker['session_id'] = session_id
        row = db.execute('SELECT score FROM scores WHERE session_id = ?', (session_id,)).fetchone()
        if row is None:  # a context not seen before is fresh: it carries no penalty, whatever the row held
            worker['score'] = START
            cls._keep(db, worker)
        else:
            worker['score'] = float(row[0])

    @staticmethod
    def _keep(db: sqlite3.Connection, worker: dict[str, Any]) -> None:
        """The worker's score written to its context's record, when it has a session."""
        if worker.get('session_id'):
            db.execute('INSERT INTO scores VALUES (?, ?) ON CONFLICT(session_id) DO UPDATE SET score = excluded.score',
                       (worker['session_id'], float(worker.get('score', START))))

    def register(self, agent_id: str, name: str, work_id: str, session_id: str = '',
                 context: dict[str, Any] | None = None) -> dict[str, Any]:
        """An agent online, at the starting score until its session names a context with a score of its own; one
        registered again keeps its work."""
        with self._db() as db:
            old = self._worker(db, agent_id)
            worker: dict[str, Any] = old or {
                'agent_id': agent_id, 'name': name, 'work_id': work_id, 'session_id': '',
                'context': context, 'current': '', 'next': '', 'state': 'starting', 'waiting_for': None, 'nodes': [],
                'score': START}
            worker.update(name=name, work_id=work_id)
            if session_id and session_id != worker.get('session_id'):
                self._joined(db, worker, session_id)
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
        if 'state' in fields and fields['state'] not in STATES:
            raise ValueError('Unknown worker state.')
        with self._db() as db:
            worker = self._worker(db, id)
            if worker is None:
                raise KeyError(id)
            session_id = str(fields.get('session_id') or '')
            worker.update({key: value for key, value in fields.items() if key != 'session_id'})
            if 'nodes' in fields:
                worker['_nodes_explicit'] = True
            if session_id and session_id != worker.get('session_id'):
                self._joined(db, worker, session_id)
            self._put_worker(db, worker)

    def remove(self, id: str) -> None:
        """An agent gone offline; the run's rounds and ratings go with the last one. Its context's score stays for
        the session to be resumed with."""
        with self._db() as db:
            db.execute('DELETE FROM workers WHERE agent_id = ?', (id,))  # its queued messages wait for its context
            if db.execute('SELECT 1 FROM workers LIMIT 1').fetchone() is None:
                for table in ('rounds', 'ratings', 'outbox', 'messages'):
                    db.execute(f'DELETE FROM {table}')

    def clear(self) -> None:
        with self._db() as db:
            for table in ('workers', 'rounds', 'ratings', 'outbox', 'messages', 'scores'):
                db.execute(f'DELETE FROM {table}')

    def handoff(self, leaving: str, arriving: str) -> dict[str, Any]:
        """The leaving agent's place given to the arriving one: holder or partner in every open round, its current
        and next worktree, its nodes and the waits on it. The arriving agent's score is its own, a fresh context's."""
        with self._db() as db:
            left, come = self._worker(db, leaving), self._worker(db, arriving)
            if left is None:
                raise KeyError(leaving)
            if come is None:
                raise KeyError(arriving)
            moved: list[str] = []
            for row in db.execute('SELECT data FROM rounds ORDER BY rowid').fetchall():
                round_ = _decoded(row[0])
                if round_['completed'] or leaving not in (round_['holder'], round_.get('partner')):
                    continue
                for place in ('holder', 'partner'):
                    if round_.get(place) == leaving:
                        round_[place] = arriving
                self._put_round(db, round_)
                moved.append(str(round_['worktree']))
            for key in ('current', 'next', 'nodes', 'waiting_for', '_nodes_explicit'):
                if key in left:
                    come[key] = left[key]
            left.update(current='', next='', nodes=[], waiting_for=None, _nodes_explicit=False)
            db.execute('UPDATE outbox SET agent = ? WHERE agent = ?', (arriving, leaving))  # its unread messages too
            self._put_worker(db, left)
            self._put_worker(db, come)
            for row in db.execute('SELECT data FROM workers ORDER BY rowid').fetchall():
                waiter = _decoded(row[0])
                if waiter.get('waiting_for') == leaving:
                    waiter['waiting_for'] = arriving
                    self._put_worker(db, waiter)
            return {'leaving': leaving, 'arriving': arriving, 'worktrees': moved,
                    'current': come['current'], 'next': come['next']}

    def set_round(self, worktree: str, phrase: str, holder: str, items: list[str | dict[str, Any]],
                  nodes: list[str], partner: str | None = None, tickets: list[str] | None = None) -> dict[str, Any]:
        """The unified worksheet of a worktree, registered by the agent claiming it: its items keep their ids and
        checks across edits, and each may name the ticket, the agent and the nodes it is for."""
        with self._db() as db:
            old = self._round(db, worktree)
            if old is not None and old.get('completed'):
                self._retire(db, worktree)
                old = None
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
                'worktree': worktree, 'phrase': phrase, 'holder': holder,
                'partner': partner if partner is not None else old.get('partner') if old else None,
                'items': worksheet, 'nodes': nodes,
                'tickets': list(tickets) if tickets is not None else list(old.get('tickets') or []) if old else [],
                'completed': False}
            self._put_round(db, round_)
            worker = self._worker(db, holder)
            if worker is not None:
                slot = 'next' if worker['current'] and worker['current'] != worktree else 'current'
                worker[slot] = worktree
                self._put_worker(db, worker)
            return round_

    @staticmethod
    def _retire(db: sqlite3.Connection, worktree: str) -> None:
        """A closed round of this name set aside as <name>#<n>, with its ratings, so the name's new round starts clean
        and the history each agent is shown stays."""
        taken = db.execute('SELECT COUNT(*) FROM rounds WHERE worktree LIKE ?', (worktree + '#%',)).fetchone()[0]
        retired = f'{worktree}#{taken + 1}'
        for table in ('rounds', 'ratings'):
            for rowid, data in db.execute(f'SELECT rowid, data FROM {table} WHERE worktree = ?', (worktree,)).fetchall():
                record = _decoded(data)
                record['worktree'] = retired
                db.execute(f'UPDATE {table} SET worktree = ?, data = ? WHERE rowid = ?', (retired, _dump(record), rowid))

    def add_ticket(self, worktree: str, ticket: str) -> dict[str, Any] | None:
        """A ticket written into a claimed worktree joins its open round; none when the name has no open round."""
        with self._db() as db:
            round_ = self._round(db, worktree)
            if round_ is None or round_['completed']:
                return None
            if ticket not in round_['tickets']:
                round_['tickets'] = [*round_['tickets'], ticket]
                self._put_round(db, round_)
            return round_

    def round(self, worktree: str) -> dict[str, Any] | None:
        with self._db() as db:
            return self._round(db, worktree)

    def rounds(self) -> list[dict[str, Any]]:
        with self._db() as db:
            return [_decoded(row[0]) for row in db.execute('SELECT data FROM rounds ORDER BY rowid')]

    def pair(self, worktree: str, partner: str) -> dict[str, Any]:
        with self._db() as db:
            round_ = self._round(db, worktree)
            if round_ is None:
                raise KeyError(worktree)
            worker = self._worker(db, partner)
            if worker is None:
                raise KeyError(partner)
            round_['partner'] = partner
            occupied = bool(worker['current'] and worker['current'] != worktree)
            worker['next' if occupied else 'current'] = worktree
            self._put_worker(db, worker)
            holder = self._worker(db, str(round_['holder']))
            if holder is not None:
                holder['waiting_for'] = partner if occupied else None
                self._put_worker(db, holder)
            self._put_round(db, round_)
            return round_

    def check(self, worktree: str, item_id: str, done: bool = True) -> dict[str, Any]:
        with self._db() as db:
            round_ = self._round(db, worktree)
            if round_ is None:
                raise KeyError(worktree)
            items = cast(list[dict[str, Any]], round_['items'])
            item = next((item for item in items if item['id'] == item_id), None)
            if item is None:
                raise KeyError(item_id)
            item['done'] = done
            self._put_round(db, round_)
            return round_

    # ------------------------------------------------------------------------------------------ ratings and scores

    def rate(self, worktree: str, reviewer: str, target: str | None, stars: dict[str, Any], *,
             bonus: bool = False, alone: bool = False) -> dict[str, Any]:
        """One reviewer's pick at the close of a worktree: the agent it rates, with stars of five in each category and
        the bonus, or alone when there was no one to rate. The rated agent's score moves by the points under 100 and
        the bonus, within 0 and 105. A pick made again replaces the first, and the score moves by the difference."""
        if alone:
            rating: dict[str, Any] = {'worktree': worktree, 'reviewer': reviewer, 'target': None, 'alone': True,
                                      'stars': {}, 'bonus': False, 'points': None, 'change': 0.0}
        else:
            if not target:
                raise ValueError('Name the agent rated, or rate alone.')
            if target == reviewer:
                raise ValueError('An agent does not rate itself.')
            unknown = sorted(set(stars) - set(CATEGORIES))
            missing = [name for name in CATEGORIES if name not in stars]
            if unknown or missing:
                raise ValueError(f'A rating gives stars in each category, {", ".join(CATEGORIES)}'
                                 f'{"; not " + ", ".join(unknown) if unknown else ""}'
                                 f'{"; missing " + ", ".join(missing) if missing else ""}.')
            for value in stars.values():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                        or not 0 <= value <= STARS:
                    raise ValueError(f'Stars are numbers from 0 to {STARS} in each category.')
            given = {name: stars[name] for name in CATEGORIES}
            points = points_of(given, bonus)
            rating = {'worktree': worktree, 'reviewer': reviewer, 'target': target, 'alone': False, 'stars': given,
                      'bonus': bool(bonus), 'points': points, 'change': points - START}
        with self._db() as db:
            if self._round(db, worktree) is None:
                raise KeyError(worktree)
            row = db.execute('SELECT data FROM ratings WHERE worktree = ? AND reviewer = ?',
                             (worktree, reviewer)).fetchone()
            previous = _decoded(row[0]) if row else None
            if previous and previous.get('target'):
                self._move(db, str(previous['target']), -float(previous['applied']))
            rating['applied'] = self._move(db, str(rating['target']), float(rating['change'])) if rating['target'] else 0.0
            db.execute('INSERT OR REPLACE INTO ratings VALUES (?, ?, ?)', (worktree, reviewer, _dump(rating)))
        return rating

    @classmethod
    def _move(cls, db: sqlite3.Connection, agent_id: str, change: float) -> float:
        """The agent's score moved by `change` within 0 and 105; what was applied, so a replaced rating reverses
        exactly that."""
        worker = cls._worker(db, agent_id)
        if worker is None:
            return 0.0
        before = float(worker.get('score', START))
        worker['score'] = max(0.0, min(float(MOST), before + change))
        cls._put_worker(db, worker)
        cls._keep(db, worker)
        return float(worker['score']) - before

    def ratings(self, worktree: str) -> list[dict[str, Any]]:
        with self._db() as db:
            return [_decoded(row[0]) for row in db.execute(
                'SELECT data FROM ratings WHERE worktree = ? ORDER BY reviewer', (worktree,))]

    def complete_round(self, worktree: str) -> dict[str, Any]:
        with self._db() as db:
            round_ = self._round(db, worktree)
            if round_ is None:
                raise KeyError(worktree)
            if not round_['completed']:
                planned: dict[str, list[str]] = {}
                for participant in (round_['holder'], round_['partner']):
                    if participant is not None:
                        worker = self._worker(db, str(participant))
                        planned[str(participant)] = self._planned_nodes(
                            round_, str(participant), worker if worker and worker['current'] == worktree else None)
                round_['participant_nodes'] = planned
            round_['completed'] = True
            self._put_round(db, round_)
            affected: list[str] = []
            for row in db.execute('SELECT data FROM workers ORDER BY rowid').fetchall():
                worker = _decoded(row[0])
                if worker['current'] == worktree:
                    worker['current'], worker['next'] = worker['next'], ''
                    worker['nodes'], worker['_nodes_explicit'] = [], False
                elif worker['next'] == worktree:
                    worker['next'] = ''
                else:
                    continue
                worker['waiting_for'] = None
                affected.append(str(worker['agent_id']))
                self._put_worker(db, worker)
            return {'worktree': worktree, 'affected': affected}

    # ------------------------------------------------------------------------------------------ what is shown

    @staticmethod
    def progress(round_: dict[str, Any], agent_id: str | None = None, ticket: str | None = None) -> dict[str, int]:
        """Checked and total items, of one agent's when named, and of one ticket's, its own and the shared, when named."""
        items = cast(list[dict[str, Any]], round_['items'])
        selected = [item for item in items if (agent_id is None or item.get('agent') in (None, agent_id))
                    and (ticket is None or item.get('ticket') in (None, ticket))]
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
        """Every agent online but the viewer, with its score, context, progress, next and current worktree and the
        rounds it finished with the points each gave it."""
        with self._db() as db:
            workers = [_decoded(row[0]) for row in db.execute('SELECT data FROM workers ORDER BY rowid')]
            rounds = {_decoded(row[0])['worktree']: _decoded(row[0])
                      for row in db.execute('SELECT data FROM rounds ORDER BY rowid')}
            ratings = [_decoded(row[0]) for row in db.execute('SELECT data FROM ratings')]
        result: list[dict[str, Any]] = []
        for worker in workers:
            agent_id = str(worker['agent_id'])
            if agent_id == viewer:
                continue
            past: list[dict[str, Any]] = []
            for round_ in rounds.values():
                if not round_['completed'] or agent_id not in (round_['holder'], round_['partner']):
                    continue
                received = [float(rating['points']) for rating in ratings
                            if rating['worktree'] == round_['worktree'] and rating['target'] == agent_id]
                past.append({'worktree': round_['worktree'], 'phrase': round_['phrase'],
                             'tickets': round_.get('tickets') or [], 'nodes': self._planned_nodes(round_, agent_id),
                             'points': sum(received) / len(received) if received else None})
            current = rounds.get(worker['current'])
            next_ = rounds.get(worker['next'])
            progress = self.progress(current, agent_id) if current else {'checked': 0, 'total': 0}
            context = cast(dict[str, Any], worker.get('context') or {})
            used: Any = context.get('used')
            size: Any = context.get('size')
            occupancy = used / size * 100 if isinstance(used, (int, float)) and \
                isinstance(size, (int, float)) and size > 0 else None
            result.append({'agent_id': agent_id, 'name': worker['name'], 'state': worker.get('state'),
                           'score': float(worker.get('score', START)), 'context': occupancy,
                           'complete': progress['checked'] / progress['total'] * 100 if progress['total'] else None,
                           'next': self._summary(next_, agent_id) if next_ else None,
                           'current': self._summary(current, agent_id, worker) if current else None, 'past': past})
        return result

    @classmethod
    def _summary(cls, round_: dict[str, Any], agent_id: str,
                 worker: dict[str, Any] | None = None) -> dict[str, Any]:
        return {'worktree': round_['worktree'], 'phrase': round_['phrase'], 'tickets': round_.get('tickets') or [],
                'nodes': cls._planned_nodes(round_, agent_id, worker), **cls.progress(round_, agent_id)}

    # ------------------------------------------------------------------------------------------ the outbox

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

    # ------------------------------------------------------------------------------------------ the message log

    def log_message(self, key: str, sender: str, recipient: str, text: str) -> dict[str, Any]:
        """Every message sent through `tasks message`, kept for the run."""
        entry = {'key': key, 'sender': sender, 'recipient': recipient, 'text': text,
                 'time': datetime.now(UTC).isoformat()}
        with self._db() as db:
            db.execute('INSERT OR IGNORE INTO messages VALUES (?, ?, ?, ?, ?)',
                       (key, sender, recipient, text, entry['time']))
        return entry

    def messages(self, sender: str | None = None) -> list[dict[str, Any]]:
        where, values = (' WHERE sender = ?', (sender,)) if sender is not None else ('', ())
        with self._db() as db:
            rows = db.execute('SELECT key, sender, recipient, text, time FROM messages' + where + ' ORDER BY rowid',
                              values).fetchall()
        return [dict(zip(('key', 'sender', 'recipient', 'text', 'time'), row)) for row in rows]
