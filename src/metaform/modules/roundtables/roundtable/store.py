"""The roundtable's tables, in one SQLite file in the home, `roundtable.sqlite3`.

A discussion is numbered and its submissions within it, which gives each submission its resource address,
`roundtable://discussion<N>/submission<M>`. Every submission is kept, accepted or not, with its seat, its text, Jev's
four nouls and what its turn used, so the bar can later be checked against the person's own judgment. A seat keeps
its own running conversation: the number of the last submission it was shown, and the messages it was sent and
gave. A comment waits in `waiting` until the runner enters it at the next gap between turns.

A Roundtable 2 table also has its topics, in `topics`, in the order they open, each with its text as it was when the
table opened and why its discussion went to synthesis; the table's `topic` and `stage` say where it is, and every
submission names the topic it was made on. What each stage after the discussion gave is a row of `stages`: the
synthesis with its ideas, each seat's ranking, top-three and bottom-three explanation, and the host's summary. A table
with no topics, and every table made before topics were, discusses its opening alone.

Every judgment of a submission or a round is a row of `judgments`, paid or failed: its kind (`veto`, `dedup` for a
repeat caught by the code without a call, `sufficiency` after a round), the request exactly as sent, a hash of its
questions' text, the raw answer, the model that answered, the nouls read, the bars applied, the decision, the usage,
cost, latency, attempts and error. Each is written in the same transaction as the decision it causes, and its cost is
added to the table's `spent` there, so `spent` is the seats' costs and the judgments' together.

A table's operational events, in `events`, are what the chair is told is going wrong: credits run out, a hold, a seat
lost, degraded or back, the runner stopped. They are the chair's alone: never a submission, never judged by Jev,
never in a seat's view.

A seat's availability is in its row (`health`): `active`, `degraded` or `unavailable` with the reason, since when and
when it is probed next (`retry_at`), from its failures of one kind in a row. Its slots, the turns it was given, are
`taken`; its submissions, the turns it answered with a contribution, `submitted`; a pass or a turn with no submission
fills a slot and is no submission. `reseated` counts the chair's reseats, so a runner makes the seat afresh.

The runner and the server are separate processes that share this file, so every write is one short transaction
and the database runs in WAL mode with a busy timeout. A runner owns its table by the token it claims (`claim`), and
every write it makes to the table is fenced on that token: a write to `discussions` is `UPDATE … WHERE runner=?`, a
write to another table checks the token in the same transaction, and either raises Lost once another runner holds the
table, so two runners never drive one table.
"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

from metaform.data import DataConnection, DataRow, private_database

from . import config

STATES = ('running', 'held', 'ending', 'ended')  # a table runs, is held by its chair or by Jev failing, then ends
AVAILABILITY = ('active', 'degraded', 'unavailable')  # a seat's, from its failures in a row (`health`)
STAGES = ('discussion', 'synthesis', 'ranking', 'top_three', 'bottom_three', 'host_summary', 'report')
KINDS = ('seat', 'chair', 'none', 'pass', 'carry', 'handoff')
NOULS = ('new', 'valuable', 'relevant', 'keep')  # Jev's four nouls, in the order the review's array gives them
VETO = ('new_context', 'on_topic')  # Jev's two nouls for a submission at a table with topics
CHECKS = ('new_context', 'valuable', 'on_topic')
JUDGMENTS = ('veto', 'dedup', 'sufficiency')
JSON = frozenset({'messages', 'reply', 'unjudged', 'models', 'extra', 'imported', 'snapshot', 'host', 'synthesizer',
                  'ideas', 'ranking', 'request', 'response', 'nouls', 'floors', 'usage', 'seat_mcp',
                  'continuation', 'handoff', 'scores'})
# What an operational event says happened, in `events`: OpenRouter's credits ran out, the table held or resumed, a
# seat left the table, was degraded or came back, the table's runner stopped
EVENTS = ('credits', 'held', 'resumed', 'seat_lost', 'seat_degraded', 'seat_restored', 'runner_stopped', 'report',
          'permission', 'budget', 'topic_proposal_failed', 'topic_compression')
SYNTHESIZER, HOST, REPORTER = -1, -2, -3  # the position of a fresh request's seat, never one at the table

SCHEMA = """
CREATE TABLE IF NOT EXISTS discussions(
  number INTEGER PRIMARY KEY, subject TEXT NOT NULL, opening TEXT NOT NULL, folder TEXT NOT NULL,
  chair_key TEXT, chair_token TEXT NOT NULL, reporter TEXT NOT NULL,
  state TEXT NOT NULL, reason TEXT,
  round INTEGER NOT NULL DEFAULT 1, position INTEGER NOT NULL DEFAULT 0, round_kept INTEGER NOT NULL DEFAULT 0,
  runner TEXT, budget_runner TEXT, beat REAL NOT NULL DEFAULT 0, unjudged TEXT,
  rounds INTEGER NOT NULL, spend REAL NOT NULL, spent REAL NOT NULL DEFAULT 0,
  report TEXT, export TEXT, report_error TEXT, created TEXT NOT NULL, ended TEXT,
  context_id TEXT, task_id TEXT, imported TEXT, snapshot TEXT,
  topic INTEGER NOT NULL DEFAULT 0, stage TEXT, host TEXT, synthesizer TEXT, advance_asked INTEGER NOT NULL DEFAULT 0,
  unpaid INTEGER NOT NULL DEFAULT 0, mechanical TEXT, seat_mcp TEXT,
  continuation TEXT, handoff TEXT, pass_after INTEGER NOT NULL DEFAULT 0,
  phase_after INTEGER NOT NULL DEFAULT 0, collaboration_runner TEXT, quiet_rounds INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS seats(
  discussion INTEGER NOT NULL, position INTEGER NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
  agent TEXT, model TEXT, reported TEXT, session TEXT, gone TEXT,
  seen INTEGER NOT NULL DEFAULT 0, messages TEXT NOT NULL DEFAULT '[]',
  pending TEXT, asked REAL, reply TEXT, tries INTEGER NOT NULL DEFAULT 0, owner TEXT,
  taken INTEGER NOT NULL DEFAULT 0, kept INTEGER NOT NULL DEFAULT 0, extra TEXT,
  availability TEXT NOT NULL DEFAULT 'active', failures INTEGER NOT NULL DEFAULT 0, failing TEXT, reason TEXT,
  since TEXT, retry_at REAL, submitted INTEGER NOT NULL DEFAULT 0, reseated INTEGER NOT NULL DEFAULT 0,
  identity TEXT, profile_key TEXT,
  PRIMARY KEY (discussion, position));
CREATE TABLE IF NOT EXISTS submissions(
  discussion INTEGER NOT NULL, number INTEGER NOT NULL, round INTEGER NOT NULL, position INTEGER,
  seat TEXT NOT NULL, name TEXT, kind TEXT NOT NULL, text TEXT NOT NULL, reason TEXT,
  accepted INTEGER NOT NULL DEFAULT 0, over512 INTEGER NOT NULL DEFAULT 0,
  new REAL, valuable REAL, relevant REAL, keep REAL, original TEXT, truncated INTEGER NOT NULL DEFAULT 0,
  model TEXT, prompt_tokens INTEGER, cached_tokens INTEGER, cache_write_tokens INTEGER, cost REAL, jev_cost REAL,
  created TEXT NOT NULL, topic INTEGER, new_context REAL, on_topic REAL, label TEXT, repeat_of INTEGER, message_id TEXT,
  PRIMARY KEY (discussion, number));
CREATE TABLE IF NOT EXISTS waiting(
  discussion INTEGER NOT NULL, seq INTEGER NOT NULL, text TEXT NOT NULL, PRIMARY KEY (discussion, seq));
CREATE TABLE IF NOT EXISTS offered(
  agent TEXT PRIMARY KEY, models TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS topics(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, name TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
  opened TEXT, discussed TEXT, advanced_by TEXT, why TEXT, closed TEXT,
  PRIMARY KEY (discussion, topic));
CREATE TABLE IF NOT EXISTS stages(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, stage TEXT NOT NULL, position INTEGER NOT NULL,
  seat TEXT NOT NULL, name TEXT, text TEXT NOT NULL, original TEXT, truncated INTEGER NOT NULL DEFAULT 0,
  ideas TEXT, ranking TEXT, repair TEXT, error TEXT,
  model TEXT, prompt_tokens INTEGER, cached_tokens INTEGER, cache_write_tokens INTEGER, cost REAL,
  created TEXT NOT NULL,
  PRIMARY KEY (discussion, topic, stage, position));
CREATE TABLE IF NOT EXISTS judgments(
  id INTEGER PRIMARY KEY, discussion INTEGER NOT NULL, topic INTEGER, round INTEGER, position INTEGER,
  submission INTEGER, kind TEXT NOT NULL, request TEXT, prompts_sha TEXT, response TEXT, model TEXT,
  nouls TEXT, floors TEXT, decision TEXT, usage TEXT, cost REAL, state_tokens INTEGER, latency_ms INTEGER,
  attempts INTEGER, error TEXT, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS judgments_of ON judgments(discussion, topic, kind);
CREATE TABLE IF NOT EXISTS events(
  discussion INTEGER NOT NULL, number INTEGER NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, seat TEXT,
  created TEXT NOT NULL,
  PRIMARY KEY (discussion, number));
CREATE TABLE IF NOT EXISTS profiles(
  agent TEXT PRIMARY KEY, name TEXT NOT NULL, score REAL, ratings INTEGER NOT NULL DEFAULT 0,
  sessions INTEGER NOT NULL DEFAULT 0, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profile_aliases(
  source TEXT NOT NULL, occurrence INTEGER NOT NULL, identity TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL UNIQUE, profile_key TEXT NOT NULL UNIQUE, PRIMARY KEY(source, occurrence));
CREATE TABLE IF NOT EXISTS scorecards(
  discussion INTEGER NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL, created TEXT NOT NULL,
  PRIMARY KEY (discussion, position));
CREATE TABLE IF NOT EXISTS session_ratings(
  discussion INTEGER NOT NULL, agent TEXT NOT NULL, PRIMARY KEY (discussion, agent));
CREATE TABLE IF NOT EXISTS topic_proposals(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, position INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending', receipt TEXT, text TEXT, usage TEXT, created TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(discussion, topic, position));
CREATE TABLE IF NOT EXISTS topic_decisions(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
  request TEXT, response TEXT, scores TEXT, text TEXT, usage TEXT, error TEXT, created TEXT,
  PRIMARY KEY(discussion, topic));
CREATE TABLE IF NOT EXISTS phase_usage(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, phase TEXT NOT NULL, position INTEGER NOT NULL,
  tokens INTEGER NOT NULL DEFAULT 0, reported INTEGER NOT NULL DEFAULT 0, unreported INTEGER NOT NULL DEFAULT 0,
  notice INTEGER NOT NULL DEFAULT 0, closing INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (discussion, topic, phase, position));
CREATE TABLE IF NOT EXISTS phase_replies(
  discussion INTEGER NOT NULL, reply TEXT NOT NULL, topic INTEGER NOT NULL, phase TEXT NOT NULL,
  position INTEGER NOT NULL, tokens INTEGER NOT NULL, reported INTEGER NOT NULL, recorded INTEGER,
  PRIMARY KEY (discussion, reply));
CREATE TABLE IF NOT EXISTS phase_reply_usage(
  discussion INTEGER NOT NULL, reply TEXT NOT NULL, kind TEXT NOT NULL, usage TEXT NOT NULL,
  PRIMARY KEY (discussion, reply));
CREATE TABLE IF NOT EXISTS phase_notices(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, phase TEXT NOT NULL, percent INTEGER NOT NULL,
  position INTEGER NOT NULL, tokens INTEGER NOT NULL, token_limit INTEGER NOT NULL, text TEXT NOT NULL,
  PRIMARY KEY (discussion, topic, phase, percent));
CREATE TABLE IF NOT EXISTS phase_seed(
  discussion INTEGER NOT NULL, topic INTEGER NOT NULL, phase TEXT NOT NULL,
  PRIMARY KEY (discussion, topic, phase));
"""


# Columns added after a store was first made, given to an older store as it is opened: the A2A context and task each
# table is, what an imported table's record held that no column does, what a kind of seat keeps between turns (an A2A
# seat's context at its peer), a turn's full original when truncated, discussion-time judgment rules, and where a
# Roundtable 2 table is in its topics and stages, with its host and synthesizer and the topic of each submission, and
# a submission's two Roundtable 2 nouls, the T### label its seat wrote and the code took off, and the earlier
# submission it repeats; and whether a table is held for want of OpenRouter credits, so its runner probes and resumes
# it; where its mechanical report was written; and each seat's availability, submissions and reseats.
# Older discussions keep a NULL snapshot because current settings cannot recover historical evidence, and a NULL stage,
# so they go on discussing their opening alone; `topics` and `stages` are made empty for them by the schema.
ADDED = {'discussions': (('context_id', 'TEXT'), ('task_id', 'TEXT'), ('imported', 'TEXT'), ('snapshot', 'TEXT'),
                         ('topic', 'INTEGER NOT NULL DEFAULT 0'), ('stage', 'TEXT'), ('host', 'TEXT'),
                         ('synthesizer', 'TEXT'), ('advance_asked', 'INTEGER NOT NULL DEFAULT 0'),
                         ('unpaid', 'INTEGER NOT NULL DEFAULT 0'), ('mechanical', 'TEXT'), ('seat_mcp', 'TEXT'),
                         ('continuation', 'TEXT'), ('handoff', 'TEXT'), ('pass_after', 'INTEGER NOT NULL DEFAULT 0'),
                         ('phase_after', 'INTEGER NOT NULL DEFAULT 0'), ('budget_runner', 'TEXT'),
                         ('collaboration_runner', 'TEXT'), ('quiet_rounds', 'INTEGER NOT NULL DEFAULT 0')),
         'seats': (('extra', 'TEXT'), ('availability', "TEXT NOT NULL DEFAULT 'active'"),
                   ('failures', 'INTEGER NOT NULL DEFAULT 0'), ('failing', 'TEXT'), ('reason', 'TEXT'),
                   ('since', 'TEXT'), ('retry_at', 'REAL'), ('submitted', 'INTEGER NOT NULL DEFAULT 0'),
                   ('reseated', 'INTEGER NOT NULL DEFAULT 0'), ('identity', 'TEXT'), ('profile_key', 'TEXT')),
         'topic_proposals': (('attempts', 'INTEGER NOT NULL DEFAULT 0'),),
         'submissions': (('original', 'TEXT'), ('truncated', 'INTEGER NOT NULL DEFAULT 0'), ('topic', 'INTEGER'),
                         ('new_context', 'REAL'), ('on_topic', 'REAL'), ('label', 'TEXT'), ('repeat_of', 'INTEGER'),
                         ('unjudged', 'INTEGER NOT NULL DEFAULT 0'), ('message_id', 'TEXT'))}
# What a seat's turn or stage answer wrote, its completion and reasoning tokens, and why its model stopped, added to
# every store, old or new, as `submissions` and `stages` are opened.
WRITTEN = (('completion_tokens', 'INTEGER'), ('reasoning_tokens', 'INTEGER'), ('finish_reason', 'TEXT'))
_migrated: set[str] = set()


def migrate(db: DataConnection, path: str) -> None:
    if path in _migrated:
        return
    for table, columns in (*ADDED.items(), ('submissions', WRITTEN), ('stages', WRITTEN)):
        held = {str(row[1]) for row in db.execute(f'PRAGMA table_info({table})')}
        for name, kind in columns:
            if name not in held:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {kind}')
                if table == 'topic_proposals' and name == 'attempts':
                    db.execute('UPDATE topic_proposals SET attempts=1 WHERE receipt IS NOT NULL')
    for row in db.execute('SELECT number FROM discussions WHERE context_id IS NULL').fetchall():
        db.execute('UPDATE discussions SET context_id=?, task_id=? WHERE number=?',
                   (uuid.uuid4().hex, uuid.uuid4().hex, row[0]))
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS submission_message_id ON submissions(discussion,message_id) "
               "WHERE message_id IS NOT NULL")
    _migrated.add(path)


class Missing(Exception):
    """No such table or submission; the message says which."""


class Lost(Exception):
    """The table's runner token is no longer this runner's: another runner took the table, so this one stops."""


_fences: dict[int, str] = {}  # the tables this process runs, by number, with the token it claimed each under


def fence(db: DataConnection, number: int) -> None:
    """Lost when this process runs the table and another runner's token is on it now; nothing otherwise."""
    token = _fences.get(number)
    if token is not None and db.execute('SELECT 1 FROM discussions WHERE number=? AND runner=?',
                                        (number, token)).fetchone() is None:
        raise Lost(f'Table {number} is no longer run under token {token}.')


def stamp() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds')


@contextmanager
def connect() -> Generator[DataConnection]:
    """One transaction on the store, committed when the block ends."""
    path = config.home() / 'roundtable.sqlite3'
    db = private_database(path)
    try:
        db.row_factory = DataRow
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=30000')
        db.executescript(SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        migrate(db, str(path))
        try:
            yield db
        except BaseException:
            db.execute('ROLLBACK')
            raise
        db.execute('COMMIT')
    finally:
        db.close()


def plain(row: DataRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    found = dict(row)
    for key in JSON & found.keys():
        if isinstance(found[key], str):
            found[key] = json.loads(found[key])
    for key in ('accepted', 'over512', 'truncated', 'advance_asked', 'unpaid'):
        if key in found:
            found[key] = bool(found[key])
    return found


def stored(value: Any, key: str) -> Any:
    return json.dumps(value) if key in JSON and value is not None else value


def update(db: DataConnection, table: str, where: Mapping[str, Any], changes: Mapping[str, Any]) -> int:
    """The rows changed."""
    if not changes:
        return 0
    sets = ', '.join(f'{key}=?' for key in changes)
    keys = ' AND '.join(f'{key}=?' for key in where)
    return db.execute(f'UPDATE {table} SET {sets} WHERE {keys}',
                      [stored(value, key) for key, value in changes.items()] + list(where.values())).rowcount


def insert(db: DataConnection, table: str, row: Mapping[str, Any]) -> None:
    db.execute(f'INSERT INTO {table} ({", ".join(row)}) VALUES ({", ".join("?" * len(row))})',
               [stored(value, key) for key, value in row.items()])


# ----------------------------------------------------------------------------------------------- reads

def discussion(number: int) -> dict[str, Any]:
    with connect() as db:
        found = plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
    if found is None:
        raise Missing(f'No roundtable discussion {number}; list shows them.')
    return found


def discussions() -> list[dict[str, Any]]:
    with connect() as db:
        return [one for row in db.execute('SELECT * FROM discussions ORDER BY number DESC')
                if (one := plain(row)) is not None]


def seats(number: int) -> list[dict[str, Any]]:
    with connect() as db:
        return [one for row in db.execute('SELECT * FROM seats WHERE discussion=? ORDER BY position', (number,))
                if (one := plain(row)) is not None]


def submissions(number: int, since: int = 0) -> list[dict[str, Any]]:
    with connect() as db:
        return [one for row in db.execute('SELECT * FROM submissions WHERE discussion=? AND number>? ORDER BY number',
                                          (number, since)) if (one := plain(row)) is not None]


def topics(number: int) -> list[dict[str, Any]]:
    """A Roundtable 2 table's topics in the order they open; none for a table that discusses its opening alone."""
    with connect() as db:
        return [one for row in db.execute('SELECT * FROM topics WHERE discussion=? ORDER BY topic', (number,))
                if (one := plain(row)) is not None]


def staged(number: int, topic: int | None = None) -> list[dict[str, Any]]:
    """What the stages after a topic's discussion gave, in the order they came: every topic's, or one's."""
    with connect() as db:
        rows = db.execute('SELECT * FROM stages WHERE discussion=? AND (? IS NULL OR topic=?) ORDER BY rowid',
                          (number, topic, topic))
        return [one for row in rows if (one := plain(row)) is not None]


def judgments(number: int, topic: int | None = None) -> list[dict[str, Any]]:
    """Every judgment of a table in the order made: every topic's, or one's."""
    with connect() as db:
        rows = db.execute('SELECT * FROM judgments WHERE discussion=? AND (? IS NULL OR topic=?) ORDER BY id',
                          (number, topic, topic))
        return [one for row in rows if (one := plain(row)) is not None]


def events(number: int, since: int = 0) -> list[dict[str, Any]]:
    """The table's operational events after a cursor, oldest first."""
    with connect() as db:
        return [dict(row) for row in db.execute('SELECT * FROM events WHERE discussion=? AND number>? ORDER BY number',
                                                (number, since))]


def submission(number: int, at: int) -> dict[str, Any]:
    with connect() as db:
        found = plain(db.execute('SELECT * FROM submissions WHERE discussion=? AND number=?',
                                 (number, at)).fetchone())
    if found is None:
        raise Missing(f'No submission {at} in roundtable discussion {number}.')
    return found


# ----------------------------------------------------------------------------------------------- writes

def opened(row: Mapping[str, Any], chosen: list[dict[str, str]],
           topics: Sequence[Mapping[str, str]] = (), reply_limit: int = 512, judging: bool | None = None,
           session: Mapping[str, Any] | None = None,
           permissions: Mapping[str, Mapping[str, str]] | None = None, token_budget: int = 0,
           token_basis: str = 'uncached') -> int:
    """A new discussion with its seats in order, and its topics in order when it has them, the first open; its
    number, the next one."""
    from . import render

    with connect() as db:
        from . import identity

        assigned = identity.assign(db, str(row['folder']), chosen)
        snapshot = render.snapshot([person['name'] for person in assigned], staged=bool(topics),
                                   reply_limit=reply_limit, judging=judging)
        snapshot['token_budget'] = token_budget
        snapshot['token_basis'] = token_basis
        snapshot['message_ids'] = True
        snapshot['reply_credits'] = True
        if permissions:
            snapshot['permissions'] = {agent: dict(values) for agent, values in permissions.items()}
        if session:
            snapshot['session'] = dict(session)
        metadata = dict(row)
        if any(person['identity'] is not None for person in assigned):
            for role in ('host', 'synthesizer'):
                given = row.get(role)
                if isinstance(given, dict):
                    details = cast(dict[str, Any], given)
                    name = next((person['name'] for seat, person in zip(chosen, assigned, strict=True)
                                 if seat['id'] == details.get('id')), role.capitalize())
                    metadata[role] = {**details, 'name': name}
        number = 1 + int(db.execute('SELECT COALESCE(MAX(number), 0) FROM discussions').fetchone()[0])
        insert(db, 'discussions', {**metadata, 'snapshot': snapshot, 'number': number, 'state': 'running', 'created': stamp(),
                                   'context_id': uuid.uuid4().hex, 'task_id': uuid.uuid4().hex,
                                   **({'stage': 'discussion', 'topic': 0} if topics else {})})
        for position, (seat, person) in enumerate(zip(chosen, assigned, strict=True)):
            insert(db, 'seats', {'discussion': number, 'position': position, 'kind': seat['kind'], 'id': seat['id'],
                                 'name': person['name'], 'identity': person['identity'],
                                 'profile_key': person['profile_key'],
                                 'agent': seat.get('agent'), 'model': seat.get('model')})
        for at, topic in enumerate(topics):
            insert(db, 'topics', {'discussion': number, 'topic': at, 'name': topic['name'], 'title': topic['title'],
                                  'text': topic['text'], 'opened': stamp() if at == 0 else None})
        if any(person['identity'] is not None for person in assigned):
            folder = str(session['folder']) if session and session.get('folder') else str(
                config.notes(str(row['folder']), number))
            identity.write_roster(folder, [person['name'] for person in assigned])
    return number


def add_topic(number: int, text: str) -> int:
    """A topic added after the open ones, as a session's agents submit the next; its index."""
    from .stages import title
    with connect() as db:
        fence(db, number)
        at = int(db.execute('SELECT COUNT(*) FROM topics WHERE discussion=?', (number,)).fetchone()[0])
        insert(db, 'topics', {'discussion': number, 'topic': at, 'name': f'{at + 1:02d}', 'title': title(text),
                              'text': text, 'opened': None})
    return at


def profile(agent: str) -> dict[str, Any] | None:
    """An agent's profile across sessions: its rating, the total of the points it was given, and how many."""
    with connect() as db:
        return plain(db.execute('SELECT * FROM profiles WHERE agent=?', (agent,)).fetchone())


def rated(agent: str, name: str, points: Sequence[float], *, discussion: int) -> dict[str, Any]:
    """A session's points added once to an agent's profile; unscored until its first rating."""
    with connect() as db:
        fence(db, discussion)
        held = plain(db.execute('SELECT * FROM profiles WHERE agent=?', (agent,)).fetchone())
        if db.execute('SELECT 1 FROM session_ratings WHERE discussion=? AND agent=?',
                      (discussion, agent)).fetchone() is not None:
            assert held is not None
            return held
        score = (float(held['score']) if held and held['score'] is not None else 0.0) + sum(points)
        row = {'agent': agent, 'name': name,
               'score': score if points or (held and held['score'] is not None) else None,
               'ratings': (int(held['ratings']) if held else 0) + len(points),
               'sessions': (int(held['sessions']) if held else 0) + 1, 'updated': stamp()}
        db.execute('INSERT OR REPLACE INTO profiles VALUES (:agent, :name, :score, :ratings, :sessions, :updated)', row)
        db.execute('INSERT INTO session_ratings VALUES (?, ?)', (discussion, agent))
    return row


def scorecards(number: int) -> list[dict[str, Any]]:
    """Private scorecards, kept outside the shared transcript and exported discussion."""
    with connect() as db:
        return [dict(one) for one in db.execute('SELECT * FROM scorecards WHERE discussion=? ORDER BY position',
                                                (number,)).fetchall()]


def scorecard_record(number: int, position: int, text: str) -> None:
    with connect() as db:
        fence(db, number)
        db.execute('INSERT OR REPLACE INTO scorecards VALUES (?, ?, ?, ?)', (number, position, text, stamp()))


def phase(number: int, stage: str, text: str) -> None:
    """Start a session phase and record its opening message in one fenced transaction."""
    with connect() as db:
        fence(db, number)
        found = plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
        if found is None:
            raise Missing(f'No roundtable {number}.')
        latest = int(db.execute('SELECT COALESCE(MAX(number), 0) + 1 FROM submissions WHERE discussion=?',
                                (number,)).fetchone()[0])
        insert(db, 'submissions', {'discussion': number, 'number': latest, 'round': found['round'],
                                   'position': None, 'kind': 'chair', 'seat': 'chair', 'name': None, 'text': text,
                                   'topic': found['topic'], 'created': stamp()})
        update(db, 'discussions', {'number': number},
               {'stage': stage, 'position': 0, 'phase_after': latest, 'pass_after': latest})


def imported(row: Mapping[str, Any], seated: list[dict[str, Any]], rows: list[dict[str, Any]]) -> int:
    """A table recorded elsewhere, taken in whole as it ended: its row, its seats and its submissions with their own
    numbers; its number here, the next one."""
    with connect() as db:
        number = 1 + int(db.execute('SELECT COALESCE(MAX(number), 0) FROM discussions').fetchone()[0])
        insert(db, 'discussions', {**row, 'number': number, 'context_id': uuid.uuid4().hex,
                                   'task_id': uuid.uuid4().hex})
        for seat in seated:
            insert(db, 'seats', {**seat, 'discussion': number})
        for one in rows:
            insert(db, 'submissions', {'over512': False, 'truncated': False, 'accepted': False, **one,
                                       'discussion': number})
    return number


def change(number: int, **changes: Any) -> dict[str, Any]:
    """The table changed; from its runner, only while the runner's token is on it, else Lost."""
    token = _fences.get(number)
    with connect() as db:
        if token is None:
            update(db, 'discussions', {'number': number}, changes)
        elif changes and not update(db, 'discussions', {'number': number, 'runner': token}, changes):
            raise Lost(f'Table {number} is no longer run under token {token}.')
    return discussion(number)


def claim(number: int, token: str, stale: float) -> bool:
    """The table taken by the runner with `token`, when no runner has beaten in the last `stale` seconds; every write
    this process makes to it after is fenced on the token. False when another runner holds it."""
    now = time.time()
    with connect() as db:
        took = db.execute('UPDATE discussions SET runner=?, beat=? WHERE number=? AND (runner IS NULL OR beat<?)',
                          (token, now, number, now - stale)).rowcount
    if took:
        _fences[number] = token
    return bool(took)


def release(number: int, token: str) -> None:
    """The table let go by the runner with `token`, if it still holds it; its writes are no longer fenced."""
    _fences.pop(number, None)
    with connect() as db:
        db.execute('UPDATE discussions SET runner=NULL, budget_runner=NULL, collaboration_runner=NULL '
                   'WHERE number=? AND runner=?', (number, token))


def spend(number: int, cost: float) -> None:
    """One paid call's cost added to what the table has spent, in one transaction. Not fenced: a call paid for is
    spent by the table whichever runner made it."""
    if cost > 0:
        with connect() as db:
            db.execute('UPDATE discussions SET spent=spent+? WHERE number=?', (cost, number))


def topic_change(number: int, topic: int, **changes: Any) -> None:
    with connect() as db:
        fence(db, number)
        update(db, 'topics', {'discussion': number, 'topic': topic}, changes)


def stage_record(number: int, row: Mapping[str, Any]) -> dict[str, Any]:
    """What one stage gave for one topic, from one seat or from the synthesizer or host; a row already there for the
    same seat, stage and topic, an answer that could not be used, is replaced."""
    held = {'truncated': False, **row, 'discussion': number, 'created': stamp()}
    with connect() as db:
        fence(db, number)
        db.execute('DELETE FROM stages WHERE discussion=? AND topic=? AND stage=? AND position=?',
                   (number, held['topic'], held['stage'], held['position']))
        insert(db, 'stages', held)
    return held


def seat_change(number: int, position: int, **changes: Any) -> None:
    with connect() as db:
        fence(db, number)
        if 'extra' in changes:
            held = plain(db.execute('SELECT extra FROM seats WHERE discussion=? AND position=?',
                                    (number, position)).fetchone())
            current = cast(dict[str, Any], held.get('extra') or {}) if held else {}
            if 'reply_allowance' in current:
                changes['extra'] = {**cast(dict[str, Any], changes['extra'] or {}),
                                    'reply_allowance': current['reply_allowance']}
        update(db, 'seats', {'discussion': number, 'position': position}, changes)


def judge(db: DataConnection, number: int, judgment: Mapping[str, Any]) -> None:
    """One judgment written, and its cost added to what the table has spent, in the caller's transaction."""
    insert(db, 'judgments', {**judgment, 'discussion': number, 'created': stamp()})
    if float(judgment.get('cost') or 0) > 0:
        db.execute('UPDATE discussions SET spent=spent+? WHERE number=?', (float(judgment['cost']), number))


def decide(number: int, judgment: Mapping[str, Any] | None, changes: Mapping[str, Any],
           topic_changes: Mapping[str, Any] | None = None) -> None:
    """A decision on the table, and on its open topic when given, in one transaction with the judgment that caused
    it: a round's sufficiency and the next round or the synthesis, or a judgment that failed and the hold."""
    with connect() as db:
        fence(db, number)
        if judgment is not None:
            judge(db, number, judgment)
        if topic_changes:
            topic = int(db.execute('SELECT topic FROM discussions WHERE number=?', (number,)).fetchone()[0])
            update(db, 'topics', {'discussion': number, 'topic': topic}, topic_changes)
        update(db, 'discussions', {'number': number}, changes)


def close_round(number: int, reason: str, *, busy: set[int] | None = None) -> None:
    """Require actual completion from remaining participants, without inventing replies for those who left."""
    with connect() as db:
        fence(db, number)
        found = plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
        if found is None or found['state'] != 'running' or found.get('unjudged') or \
                found['stage'] and found['stage'] != 'discussion':
            return
        rows = db.execute('SELECT position,kind,accepted,unjudged FROM submissions '
                          'WHERE discussion=? AND number>? AND round=? '
                          'AND topic IS ? AND kind NOT IN (\'chair\', \'carry\', \'handoff\')',
                          (number, found['pass_after'], found['round'],
                           found['topic'] if found['stage'] else None)).fetchall()
        participants = db.execute('SELECT position FROM seats WHERE discussion=? AND (gone IS NULL OR gone=\'\') '
                                  'AND availability!=\'unavailable\'',
                                  (number,)).fetchall()
        participants = [seat for seat in participants if seat['position'] not in (busy or set())]
        waiting = db.execute('SELECT 1 FROM waiting WHERE discussion=? LIMIT 1', (number,)).fetchone()
        actual = [row for row in rows if row['kind'] == 'pass' or (row['kind'] == 'seat' and not row['unjudged'])]
        covered = {row['position'] for row in actual}
        snapshot = cast(dict[str, Any], found.get('snapshot') or {})
        judging = bool(snapshot.get('judging', True))
        terminal: set[int] = set()
        if judging:
            history = db.execute('SELECT number,position,kind,accepted,unjudged FROM submissions '
                                 'WHERE discussion=? AND topic IS ? ORDER BY number',
                                 (number, found['topic'] if found['stage'] else None)).fetchall()
            boundary = max((int(row['number']) for row in history if row['accepted'] or row['kind'] == 'chair'),
                           default=0)
            outcomes: dict[int, str] = {}
            for row in history:
                if row['number'] <= boundary or row['position'] is None or row['unjudged']:
                    continue
                if row['kind'] == 'pass' or row['kind'] == 'seat' and not row['accepted']:
                    position = int(row['position'])
                    outcomes[position] = (outcomes.get(position, '') + ('P' if row['kind'] == 'pass' else 'V'))[-2:]
            terminal = {position for position, pair in outcomes.items() if pair in ('PP', 'VV', 'VP')}
            if int(found['quiet_rounds']) >= 2:
                covered.update(terminal)
        if waiting or not participants or not all(seat['position'] in covered for seat in participants):
            return
        if not actual and (not judging or int(found['quiet_rounds']) < 2):
            return
        quiet = (0 if any(row['accepted'] for row in actual) else
                 int(found['quiet_rounds']) + int(bool(actual))) if judging else 0
        positions = {seat['position'] for seat in participants}
        remaining = [row for row in rows if row['position'] in positions]
        unanimous = not waiting and len(remaining) == len(participants) and all(
            sum(one['position'] == seat['position'] and one['kind'] == 'pass' for one in remaining) == 1
            for seat in participants)
        finished = quiet >= 2 and all(seat['position'] in terminal for seat in participants) if judging else unanimous
        if not finished:
            update(db, 'discussions', {'number': number},
                   {'round': int(found['round']) + 1, 'position': 0, 'round_kept': 0, 'quiet_rounds': quiet})
        elif found['stage']:
            update(db, 'discussions', {'number': number}, {'stage': 'synthesis', 'position': 0, 'quiet_rounds': quiet})
            update(db, 'topics', {'discussion': number, 'topic': found['topic']},
                   {'discussed': stamp(), 'advanced_by': 'exhausted' if judging else 'passes', 'why': reason})
        else:
            update(db, 'discussions', {'number': number},
                   {'state': 'ending', 'reason': reason, 'position': 0, 'quiet_rounds': quiet})


def record(number: int, entry: Mapping[str, Any], *, judged: bool = False,
           judgment: Mapping[str, Any] | None = None, receipt: str | None = None) -> dict[str, Any]:
    """One submission, numbered next in its discussion; a seat's counts its turn and, when accepted, its keep.
    `judged` when it is the table's unjudged submission, now judged: the table lets it go and its round counts the
    keep in the same transaction, so the submission is neither recorded twice nor lost. `judgment`, the judgment that
    decided it, is written in that transaction too, naming the submission."""
    with connect() as db:
        fence(db, number)
        if judged and receipt is None:
            pending = plain(db.execute('SELECT unjudged FROM discussions WHERE number=?', (number,)).fetchone())
            saved = cast(dict[str, Any], pending.get('unjudged') or {}) if pending else {}
            receipt = str(saved['usage_id']) if saved.get('usage_id') else None
        if receipt is not None:
            previous = db.execute('SELECT recorded FROM phase_replies WHERE discussion=? AND reply=?',
                                  (number, receipt)).fetchone()
            if previous is not None and previous['recorded'] is not None:
                saved = plain(db.execute('SELECT * FROM submissions WHERE discussion=? AND number=?',
                                         (number, previous['recorded'])).fetchone())
                if saved is not None:
                    if judged:
                        pending = plain(db.execute('SELECT unjudged FROM discussions WHERE number=?',
                                                   (number,)).fetchone())
                        waiting = cast(dict[str, Any], pending.get('unjudged') or {}) if pending else {}
                        if waiting.get('usage_id') == receipt:
                            update(db, 'discussions', {'number': number}, {'unjudged': None})
                    return saved
        latest = int(db.execute('SELECT COALESCE(MAX(number), 0) FROM submissions WHERE discussion=?',
                                (number,)).fetchone()[0])
        row = {'over512': False, 'truncated': False, 'accepted': False, **entry, 'discussion': number, 'number': latest + 1,
               'created': stamp()}
        held = plain(db.execute('SELECT snapshot FROM discussions WHERE number=?', (number,)).fetchone())
        snapshot = cast(dict[str, Any], held.get('snapshot') or {}) if held else {}
        row['message_id'] = None
        if snapshot.get('message_ids') and (row['kind'] == 'chair' or
                row['kind'] in ('seat', 'collab') and row['accepted']):
            topic = row.get('topic')
            count = int(db.execute('SELECT COUNT(*) FROM submissions WHERE discussion=? AND topic IS ? '
                                   'AND message_id IS NOT NULL', (number, topic)).fetchone()[0])
            row['message_id'] = f'R{int(topic or 0) + 1}-{count + 1}'
        insert(db, 'submissions', row)
        if receipt is not None:
            db.execute('UPDATE phase_replies SET recorded=? WHERE discussion=? AND reply=?',
                       (row['number'], number, receipt))
        if row['kind'] in ('chair', 'handoff'):
            update(db, 'discussions', {'number': number},
                   {'pass_after': row['number'], **({'quiet_rounds': 0} if row['kind'] == 'chair' else {})})
        if row.get('accepted'):
            update(db, 'discussions', {'number': number}, {'quiet_rounds': 0})
        if entry.get('position') is not None:  # a slot filled; a submission only when the seat contributed
            db.execute('UPDATE seats SET taken=taken+1, kept=kept+?, submitted=submitted+? '
                       'WHERE discussion=? AND position=?',
                       (int(bool(row['accepted'])), int(row['kind'] == 'seat'), number, entry['position']))
        if judged:
            db.execute('UPDATE discussions SET unjudged=NULL, round_kept=round_kept+? WHERE number=?',
                       (int(bool(row['accepted'])), number))
        if judgment is not None:
            judge(db, number, {**judgment, 'submission': row['number']})
        if snapshot.get('reply_credits'):
            from . import allowance

            allowance.recorded(db, number, row, receipt)
    return row


def event(number: int, kind: str, text: str, seat: str | None = None) -> dict[str, Any]:
    """One operational event for the chair, numbered next among the table's events; never a submission, so it
    reaches no seat and Jev never judges it. ValueError for a kind not in EVENTS."""
    if kind not in EVENTS:
        raise ValueError(f'No operational event {kind}; one of {", ".join(EVENTS)}.')
    with connect() as db:
        latest = int(db.execute('SELECT COALESCE(MAX(number), 0) FROM events WHERE discussion=?',
                                (number,)).fetchone()[0])
        row = {'discussion': number, 'number': latest + 1, 'kind': kind, 'text': text, 'seat': seat,
               'created': stamp()}
        insert(db, 'events', row)
    return row


def reseat(number: int, position: int, fresh: bool) -> None:
    """The chair's reseat: the seat active again with its failures forgotten, and, `fresh`, its session and its
    conversation started again, so its next turn is a first turn holding the whole discussion. Not fenced: the
    chair's, not a runner's; `reseated` tells the runner to make the seat afresh."""
    with connect() as db:
        update(db, 'seats', {'discussion': number, 'position': position},
               {'gone': None, 'availability': 'active', 'failures': 0, 'failing': None, 'reason': None,
                'since': None, 'retry_at': None,
                **({'session': None, 'messages': [], 'seen': 0} if fresh else {})})
        db.execute('UPDATE seats SET reseated=reseated+1 WHERE discussion=? AND position=?', (number, position))


def wait_comment(number: int, text: str) -> None:
    with connect() as db:
        insert(db, 'waiting', {'discussion': number, 'seq': time.time_ns(), 'text': text})
        # Invalidate votes at enqueue, even if the runner is deciding a completed round.
        db.execute('UPDATE discussions SET pass_after=(SELECT COALESCE(MAX(number), 0)+1 FROM submissions '
                   'WHERE discussion=?) WHERE number=?', (number, number))


def take_comments(number: int) -> list[dict[str, Any]]:
    """The comments waiting, oldest first, taken out of the queue."""
    with connect() as db:
        fence(db, number)
        found = [dict(row) for row in db.execute('SELECT * FROM waiting WHERE discussion=? ORDER BY seq', (number,))]
        db.execute('DELETE FROM waiting WHERE discussion=?', (number,))
    return found


def install_handoff(number: int, continuation: Mapping[str, Any], round_number: int,
                    topic: int | None, text: str) -> None:
    """Commit the visible marker and replacement seat contexts together."""
    with connect() as db:
        fence(db, number)
        latest = int(db.execute('SELECT COALESCE(MAX(number), 0)+1 FROM submissions WHERE discussion=?',
                                (number,)).fetchone()[0])
        insert(db, 'submissions', {'discussion': number, 'number': latest, 'round': round_number, 'position': None,
                                   'seat': 'handoff', 'name': 'Context handoff', 'kind': 'handoff',
                                   'text': text, 'topic': topic, 'created': stamp()})
        _reset_context(db, number, {**continuation, 'through': latest}, None)


def _reset_context(db: DataConnection, number: int, continuation: Mapping[str, Any], topic: int | None) -> None:
    fence(db, number)
    through = int(continuation['through'])
    update(db, 'discussions', {'number': number},
           {'continuation': dict(continuation), 'handoff': None, 'pass_after': through,
            'context_id': uuid.uuid4().hex, 'task_id': uuid.uuid4().hex,
            **({'topic': topic, 'stage': 'discussion', 'position': 0, 'round': 1,
                'state': 'running', 'reason': None, 'ended': None, 'advance_asked': False,
                'report': None, 'export': None, 'mechanical': None, 'report_error': None,
                'unjudged': None, 'unpaid': False} if topic is not None else {})})
    db.execute("UPDATE seats SET session=NULL, messages='[]', extra=NULL, seen=?, reseated=reseated+1, "
               "gone=NULL, availability='active', failures=0, failing=NULL, reason=NULL, retry_at=NULL, "
               "pending=NULL, reply=NULL, asked=NULL, owner=NULL WHERE discussion=?", (through, number))


def reopen(number: int, summary: str) -> None:
    """Explicitly continue a completed table as another topic, retaining previous topics and outputs."""
    unfinished = pending(number)
    with connect() as db:
        fence(db, number)
        found = plain(db.execute('SELECT * FROM discussions WHERE number=?', (number,)).fetchone())
        if found is None or found['state'] != 'ended':
            raise ValueError('Only a completed table can continue from its saved summary.')
        if unfinished:
            insert(db, 'submissions', unfinished)
        at = int(db.execute('SELECT COALESCE(MAX(topic), -1)+1 FROM topics WHERE discussion=?',
                            (number,)).fetchone()[0])
        original = db.execute('SELECT * FROM topics WHERE discussion=? ORDER BY topic LIMIT 1', (number,)).fetchone()
        insert(db, 'topics', {'discussion': number, 'topic': at, 'name': f'continuation-{at}',
                              'title': original['title'] if original else found['subject'],
                              'text': original['text'] if original else found['opening'], 'opened': stamp()})
        latest = int(db.execute('SELECT COALESCE(MAX(number), 0) FROM submissions WHERE discussion=?',
                                (number,)).fetchone()[0]) + 1
        insert(db, 'submissions', {'discussion': number, 'number': latest, 'round': 1, 'position': None,
                                   'seat': 'handoff', 'name': 'Context handoff', 'kind': 'handoff',
                                   'text': 'Discussion continued from saved summary.', 'topic': at, 'created': stamp()})
        from . import render
        from .prompts import said
        snapshot = render.captured(found)
        update(db, 'discussions', {'number': number}, {'snapshot': {
            **{key: value for key, value in snapshot.items() if key not in ('sufficiency', 'sufficiency_floors')},
            'rules': said('discussion_start' if render.judging(found) else 'discussion_unjudged')}})
        _reset_context(db, number, {'text': summary, 'notes': [], 'through': latest, 'topic': at}, at)


def offer(agent: str, models: list[dict[str, str]]) -> None:
    """The models an agent offered at its latest session, so the next `open` checks a seat's model against them."""
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO offered(agent, models, updated) VALUES (?, ?, ?)',
                   (agent, json.dumps(models), stamp()))


def offered(agent: str) -> list[dict[str, str]]:
    with connect() as db:
        row = db.execute('SELECT models FROM offered WHERE agent=?', (agent,)).fetchone()
    return json.loads(row[0]) if row else []


def pending(number: int) -> dict[str, Any] | None:
    """The submission Jev left unjudged when the table ended, as a row numbered after the last, so the report and
    the export keep it; None when there is none."""
    found = discussion(number)
    given: Any = found.get('unjudged')
    if not isinstance(given, dict):
        return None
    held = cast(dict[str, Any], given)
    seat = next((one for one in seats(number) if one['position'] == held.get('position')), None)
    if seat is None:
        return None
    rows = submissions(number)
    use: dict[str, Any] = held.get('use') or {}
    return {'discussion': number, 'number': (rows[-1]['number'] if rows else 0) + 1, 'round': found['round'],
            'topic': found['topic'] if found.get('stage') else None,
            'position': seat['position'], 'seat': seat['id'], 'name': seat['name'], 'kind': 'seat',
            'text': held['text'], 'reason': None, 'accepted': False, 'over512': False,
            'original': held.get('original'), 'truncated': bool(held.get('truncated', held.get('original'))),
            'label': held.get('label'), 'repeat_of': None,
            'unjudged': True, **{name: None for name in (*NOULS, *VETO)}, 'jev_cost': None, 'created': found['ended'],
            **{key: use.get(key) for key in ('model', 'prompt_tokens', 'cached_tokens', 'cache_write_tokens',
                                             'completion_tokens', 'reasoning_tokens', 'finish_reason', 'cost')}}


def noul_names(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Current independent checks, or the two/four checks retained in historical records."""
    if all(row.get(name) is not None for name in CHECKS):
        return CHECKS
    return VETO if all(row.get(name) is not None for name in VETO) else NOULS


def nouls(row: Mapping[str, Any]) -> list[float] | None:
    """A submission's independent probabilities in current or captured historical order; None when unjudged."""
    values = [row.get(name) for name in noul_names(row)]
    return None if any(value is None for value in values) else [round(float(v), 2) for v in values if v is not None]
