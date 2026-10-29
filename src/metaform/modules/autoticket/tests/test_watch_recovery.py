"""Exercise Watch's real event/recovery paths with SQLite transactions and controlled external dependencies."""
from __future__ import annotations

import asyncio
import sqlite3
import sys
import threading
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from metaform.modules.autoticket import sources, watch

pytestmark = [pytest.mark.kind('simulation'),
              pytest.mark.skipif(sys.platform == 'win32', reason='autoticket supports Linux and macOS')]


class Tables:
    """The small TableTx interface used by Watch, backed by actual SQLite commit/rollback."""
    def __init__(self, db):
        self.db = db

    def rows(self, table, where=None, limit=0):
        filters = where or {}
        sql = f'SELECT * FROM "{table}"'
        if filters:
            sql += ' WHERE ' + ' AND '.join(f'"{key}"=?' for key in filters)
        if limit:
            sql += f' LIMIT {int(limit)}'
        return SimpleNamespace(results=[dict(row) for row in self.db.execute(sql, list(filters.values()))])

    def get(self, table, where):
        rows = self.rows(table, where, limit=1).results
        return rows[0] if rows else None

    def insert(self, table, values):
        keys = ', '.join(f'"{key}"' for key in values)
        placeholders = ', '.join('?' for _ in values)
        result = self.db.execute(f'INSERT INTO "{table}" ({keys}) VALUES ({placeholders})', list(values.values()))
        return dict(self.db.execute(f'SELECT * FROM "{table}" WHERE rowid=?', [result.lastrowid]).fetchone())

    def update(self, table, where, values):
        assignments = ', '.join(f'"{key}"=?' for key in values)
        filters = ' AND '.join(f'"{key}"=?' for key in where)
        self.db.execute(f'UPDATE "{table}" SET {assignments} WHERE {filters}',
                        [*values.values(), *where.values()])


class Store:
    project_id = 'test-project'

    def __init__(self, path):
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.reads = self.writes = 0
        self.db.executescript('''
            CREATE TABLE logs(source TEXT PRIMARY KEY, holder TEXT, beat REAL, identity TEXT, offset INTEGER,
                              drops INTEGER DEFAULT 0, reconnects INTEGER DEFAULT 0, last_drop TEXT DEFAULT '');
            CREATE TABLE groups(group_id INTEGER PRIMARY KEY, fingerprint TEXT, example TEXT, count INTEGER,
                first_seen TEXT, last_seen TEXT, active TEXT, source TEXT, reproduce TEXT,
                address TEXT, number INTEGER, work_id TEXT);
            CREATE TABLE rules(pattern TEXT);
        ''')

    @contextmanager
    def tables(self, write=True):
        if write:
            self.writes += 1
        else:
            self.reads += 1
        with self.lock, self.db:
            yield Tables(self.db)

    def bound_base(self):
        return None

    def work(self, **kwargs):
        return SimpleNamespace(results=[])

    def roots(self, **kwargs):
        return SimpleNamespace(entry=[], elements=[])

    def row(self, name):
        with self.tables(write=False) as tx:
            return tx.get('logs', {'source': name})

    def count(self):
        with self.tables(write=False) as tx:
            return sum(row['count'] for row in tx.rows('groups').results)


class Clock:
    now = 100.0
    def __call__(self):
        return self.now


@pytest.fixture
def case(tmp_path, monkeypatch):
    store = Store(tmp_path / 'watch.sqlite')
    published = []

    def publish(topic, payload):
        published.append((topic, payload))
        return []

    ctx = SimpleNamespace(folder=tmp_path, store=store, project=store.project_id,
                          publish=publish, say=lambda text: None)
    clock = Clock()
    monkeypatch.setattr(watch, 'similarity', lambda folder: .45)
    monkeypatch.setattr(watch, 'secret_values', lambda folder: set())
    monkeypatch.setattr(watch, 'setting', lambda key, folder: 'errors')
    watcher = watch.Watch(ctx, store, clock=clock, monotonic=clock)
    watcher.claim_due = False
    try:
        yield watcher, store, clock, published
    finally:
        watcher.stop()
        watcher.release()
        store.db.close()


def hold(watcher, store, path, reader):
    name = str(path)
    identity = sources.local_identity(name)[0]
    with store.tables() as tx:
        tx.insert('logs', {'source': name, 'holder': watcher.me, 'identity': identity, 'offset': 0, 'beat': 0})
    watcher.held[name] = watch.Held(sources.Source(name), reader, identity=identity)
    watcher.leases[name] = SimpleNamespace(let_go=lambda: None)
    return watcher.held[name]


def tick_until(watcher, condition):
    while not condition():
        event = watcher.events.get(timeout=5)
        watcher.tick(event)


def test_failed_reader_replays_pending_entry_from_committed_checkpoint(case, tmp_path, monkeypatch):
    watcher, store, clock, published = case
    log = tmp_path / 'app.log'
    first, second = b'ERROR database unavailable\n', b'ERROR payment rejected\n  request detail\n'
    log.write_bytes(first + second)
    original = sources.waker
    calls = []
    def create(path):
        made = original(path)
        calls.append(made)
        if len(calls) == 1:
            def fail():
                raise OSError('injected notification failure')
            made.wait = fail
        return made
    monkeypatch.setattr(sources, 'waker', create)
    initial = sources.LocalReader(sources.Source(str(log)), '', 0, watcher.events)
    held = hold(watcher, store, log, initial)
    initial.start()
    initial.join(3)
    assert not initial.is_alive()
    watcher.tick()
    assert held.retry_at == 101.0
    assert store.count() == 1
    assert store.row(str(log))['offset'] == len(first)
    assert 'injected notification failure' in store.row(str(log))['last_drop']
    # Retry after the deadline. No failed-reader quiet timeout commits half of the pending entry.
    clock.now = 103.0
    watcher.tick()
    assert held.reader is not initial
    assert held.reader.offset == len(first)
    assert held.identity == store.row(str(log))['identity']
    tick_until(watcher, lambda: watcher.totals.lines >= 5)
    clock.now += 3
    watcher.tick()
    assert store.count() == 2, 'the first committed entry must not be replayed or the pending one lost'
    assert store.row(str(log))['offset'] == len(first + second)
    assert store.row(str(log))['reconnects'] == 1
    assert any(topic == 'autoticket.captured' for topic, _ in published)


def test_capture_is_committed_before_publication_and_has_no_ticket_dependency(case, tmp_path):
    watcher, store, clock, published = case
    log = tmp_path / 'app.log'
    log.touch()
    reader = SimpleNamespace(stop=lambda: None, join=lambda timeout: None)
    held = hold(watcher, store, log, reader)
    observed = []
    def published_after_commit(topic, payload):
        if topic == 'autoticket.captured':
            with sqlite3.connect(store.path) as independent:
                count = independent.execute('SELECT SUM(count) FROM groups').fetchone()[0]
            observed.append((payload, count))
        published.append((topic, payload))
        return []
    watcher.ctx.publish = published_after_commit
    watcher.events.put((held.source, ('line', 'ERROR failure', 0, 14)))
    watcher.tick()
    clock.now += 3
    watcher.tick()
    assert observed == [({'project': store.project_id, 'groups': [1]}, 1)]
    assert store.count() == 1
    map_events = [payload for topic, payload in published if topic == 'map.changed']
    assert map_events and all(payload['tables'] == ['autoticket.groups'] for payload in map_events)
    # Store provides no add_work/edit_work: capture would fail if it invoked ticket operations.


def test_removed_log_is_not_restarted_after_failure(case, tmp_path, monkeypatch):
    watcher, store, clock, _ = case
    log = tmp_path / 'app.log'
    log.touch()
    reader = SimpleNamespace(stop=lambda: None, join=lambda timeout: None)
    held = hold(watcher, store, log, reader)
    watcher.events.put((held.source, ('failed', 'gone')))
    watcher.tick()
    watcher.drop(str(log))
    def unexpected(*args):
        raise AssertionError('removed reader restarted')
    monkeypatch.setattr(sources, 'reader', unexpected)
    clock.now += 100
    watcher.tick()
    assert not watcher.held
    assert watcher.wait() is None


def test_reader_recovery_backoff_does_not_poll_healthy_watch(case, tmp_path, monkeypatch):
    watcher, store, clock, _ = case
    log = tmp_path / 'app.log'
    log.touch()
    dead = SimpleNamespace(stop=lambda: None, join=lambda timeout: None, start=lambda: None)
    held = hold(watcher, store, log, dead)
    monkeypatch.setattr(sources, 'reader', lambda *args: dead)
    for delay in (1.0, 2.0, 4.0):
        watcher.events.put((held.source, ('failed', 'watch unavailable')))
        watcher.tick()
        assert held.retry_at == clock.now + delay
        reads, writes = store.reads, store.writes
        watcher.wait()
        assert (store.reads, store.writes) == (reads, writes)
        clock.now += delay
        watcher.tick()
    watcher.events.put((held.source, ('file', held.identity, 0)))
    watcher.events.put((held.source, ('line', 'ERROR recovered', 0, 16)))
    watcher.tick()
    assert held.retry_delay == sources.BACKOFF_FIRST
    clock.now += 3
    watcher.tick()
    assert watcher.wait() is None


def test_checkpoint_failure_does_not_start_replacement(case, tmp_path, monkeypatch):
    watcher, store, clock, _ = case
    log = tmp_path / 'app.log'
    log.touch()
    dead = SimpleNamespace(stop=lambda: None, join=lambda timeout: None)
    held = hold(watcher, store, log, dead)
    watcher.events.put((held.source, ('failed', 'watch failed')))
    watcher.tick()
    original = watcher.write
    def fails(**kwargs):
        raise sqlite3.OperationalError('injected unavailable database')
    def unexpected(*args):
        raise AssertionError('replacement started before checkpoint committed')
    monkeypatch.setattr(watcher, 'write', fails)
    monkeypatch.setattr(sources, 'reader', unexpected)
    clock.now += 1
    try:
        with pytest.raises(sqlite3.OperationalError):
            watcher.tick()
    finally:
        monkeypatch.setattr(watcher, 'write', original)
    assert held.reader is dead


def test_failure_does_not_suspend_other_log(case, tmp_path):
    watcher, store, clock, _ = case
    for name in ('failed.log', 'healthy.log'):
        log = tmp_path / name
        log.touch()
        hold(watcher, store, log, SimpleNamespace(stop=lambda: None, join=lambda timeout: None))
    bad = watcher.held[str(tmp_path / 'failed.log')]
    good = watcher.held[str(tmp_path / 'healthy.log')]
    bad.retry_delay = 60
    watcher.events.put((bad.source, ('failed', 'cannot follow')))
    watcher.events.put((good.source, ('line', 'ERROR useful evidence', 0, 22)))
    watcher.tick()
    clock.now += 3
    watcher.tick()
    assert store.count() == 1
    assert bad.retry_at == 160
    assert good.retry_at is None


@pytest.mark.parametrize('error', [RuntimeError('injected repair policy failure'), asyncio.CancelledError()])
def test_failed_capture_policy_delivery_preserves_committed_group_for_retry(case, tmp_path, monkeypatch, error):
    from metaform import context, events, loader
    from metaform.modules import autoticket

    watcher, store, clock, _ = case
    log = tmp_path / 'app.log'
    log.touch()
    reader = SimpleNamespace(stop=lambda: None, join=lambda timeout: None)
    held = hold(watcher, store, log, reader)
    calls = []

    def policy(ctx, captured_store, groups, by_agent):
        assert captured_store is store
        calls.append(tuple(groups))
        if len(calls) == 1:
            raise error

    source = SimpleNamespace(module='autoticket', folder=tmp_path, project=store.project_id,
                             sink=None, surface='cli')
    monkeypatch.setattr(loader, 'enabled', lambda: [autoticket.MODULE])
    monkeypatch.setattr(context, 'build', lambda *args, **kwargs: watcher.ctx)
    monkeypatch.setattr(autoticket.faults, 'tell', policy)
    watcher.ctx.publish = lambda topic, payload: events.publish(topic, payload, source)
    watcher.events.put((held.source, ('line', 'ERROR failure', 0, 14)))
    watcher.tick()
    clock.now += 3
    with pytest.raises(RuntimeError, match='autoticket.captured delivery failed'):
        watcher.tick()
    assert store.count() == 1
    assert store.row(str(log))['offset'] == 14
    assert watcher.touched == {1}
    watcher.settle([])
    assert calls == [(1,), (1,)]
    assert watcher.touched == set()
    assert store.count() == 1
