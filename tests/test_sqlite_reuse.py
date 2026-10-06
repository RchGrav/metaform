"""Every read keeps its own transaction, validates its version and uses the file lock.

Connection reuse was withdrawn after concurrent writers damaged the live store.
These checks protect that correction, alongside test_store_concurrency.py.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from metaform import sqlite
from metaform.errors import StoreError

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('STORE-006'), pytest.mark.req('STORE-029')]

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS records(value TEXT);
"""


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'read.sqlite3'
    with sqlite.opened(path, SCHEMA, write=True, version='1') as db:
        db.execute("INSERT INTO records VALUES ('first')")
    return path


def read(path):
    with sqlite.opened(path, SCHEMA, write=False, version='1') as db:
        return db, [row[0] for row in db.execute('SELECT value FROM records')]


def test_each_read_prepares_and_closes_its_own_connection(database, monkeypatch):
    prepare = sqlite.prepare
    preparations = []

    def record(*args, **kwargs):
        preparations.append(args[0])
        return prepare(*args, **kwargs)

    monkeypatch.setattr(sqlite, 'prepare', record)
    first, values = read(database)
    second, again = read(database)
    assert values == again == ['first']
    assert first is not second
    assert preparations == [first, second]
    for connection in (first, second):
        with pytest.raises(sqlite3.ProgrammingError, match='closed'):
            connection.execute('SELECT 1')


def test_external_commits_and_newer_versions_are_seen_by_next_read(database):
    read(database)
    with closing(sqlite3.connect(database, isolation_level=None)) as other:
        other.execute("INSERT INTO records VALUES ('external')")
    assert read(database)[1] == ['first', 'external']
    with closing(sqlite3.connect(database, isolation_level=None)) as other:
        other.execute("UPDATE meta SET value='999' WHERE key='schema_version'")
    with pytest.raises(StoreError, match='schema version 999'):
        read(database)


@pytest.mark.parametrize('warm', [False, True])
def test_every_reader_prepares_under_the_writer_lock(database, warm, monkeypatch):
    if warm:
        read(database)
    actual = sqlite.writer_lock(database)

    class CheckedLock:
        held = False

        def acquire(self):
            actual.acquire()
            self.held = True

        def release(self):
            self.held = False
            actual.release()

    lock = CheckedLock()
    prepare = sqlite.prepare

    def checked(*args, **kwargs):
        assert lock.held, 'reader prepared without taking the file writer lock'
        return prepare(*args, **kwargs)

    monkeypatch.setattr(sqlite, 'writer_lock', lambda path: lock)
    monkeypatch.setattr(sqlite, 'prepare', checked)
    with sqlite.opened(database, SCHEMA, write=False, version='1') as db:
        assert not lock.held, 'prepared read held the writer lock throughout its transaction'
        assert db.execute('SELECT value FROM records').fetchone() == ('first',)


def test_threads_and_nested_readers_have_independent_transactions(database):
    main, _ = read(database)

    def worker():
        return read(database)[0], read(database)[0]

    with ThreadPoolExecutor(max_workers=1) as executor:
        first, second = executor.submit(worker).result()
    assert first is not second
    assert first is not main
    with sqlite.opened(database, SCHEMA, write=False, version='1') as outer:
        outer.execute('BEGIN')
        assert outer.execute('SELECT count(*) FROM records').fetchone() == (1,)
        with sqlite.opened(database, SCHEMA, write=True, version='1') as writer:
            writer.execute("INSERT INTO records VALUES ('committed')")
        with sqlite.opened(database, SCHEMA, write=False, version='1') as inner:
            assert inner is not outer
            inner.execute('BEGIN')
            assert inner.execute('SELECT count(*) FROM records').fetchone() == (2,)
            inner.execute('COMMIT')
        assert outer.execute('SELECT count(*) FROM records').fetchone() == (1,)
        outer.execute('COMMIT')


def test_replaced_file_is_reopened_and_its_version_is_checked(database, tmp_path):
    first, _ = read(database)
    with closing(sqlite3.connect(database, isolation_level=None)) as other:
        other.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    replacement = tmp_path / 'replacement.sqlite3'
    with closing(sqlite3.connect(replacement, isolation_level=None)) as fresh:
        fresh.executescript(SCHEMA)
        fresh.execute("INSERT INTO meta VALUES ('schema_version', '1')")
        fresh.execute("INSERT INTO records VALUES ('replacement')")
    replacement.replace(database)
    second, values = read(database)
    assert second is not first
    assert values == ['replacement']


def test_removed_file_reads_empty_then_observes_recreation(database):
    first, _ = read(database)
    database.unlink()
    _, values = read(database)
    assert values == []
    assert not database.exists()
    with sqlite.opened(database, SCHEMA, write=True, version='1') as db:
        db.execute("INSERT INTO records VALUES ('recreated')")
    second, values = read(database)
    assert second is not first
    assert values == ['recreated']


def test_failed_reader_closes_its_transaction(database):
    with pytest.raises(RuntimeError, match='interrupted'), sqlite.opened(
            database, SCHEMA, write=False, version='1') as failed:
        failed.execute('BEGIN')
        failed.execute('SELECT * FROM records').fetchall()
        raise RuntimeError('interrupted')
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        failed.execute('SELECT 1')
    with sqlite.opened(database, SCHEMA, write=False, version='1') as db:
        db.execute('BEGIN')
        assert db.execute('SELECT count(*) FROM records').fetchone() == (1,)
        db.execute('COMMIT')
