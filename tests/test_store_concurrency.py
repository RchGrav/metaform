"""Many writers at once: processes and threads each add their writes, and none is lost."""
from __future__ import annotations

import os
import subprocess
import sys
import threading

import pytest
from storekit import memory, small_map

from metaform.data import Node, Store

pytestmark = pytest.mark.kind('fixture')

WRITER = '''
import sys
from metaform.data import Node, Store
store = Store('proj')
for n in range(500):
    store.add_item('memory', Node('element', 'code.timer.kitchen'), f'{sys.argv[1]} {n}')
'''


@pytest.mark.req('STORE-006')
def test_two_processes_writing_to_one_node_lose_nothing(home, store, tmp_path):
    small_map(store)
    memory(store)
    script = tmp_path / 'writer.py'
    script.write_text(WRITER)
    env = {**os.environ, 'METAFORM_HOME': str(home)}
    writers = [subprocess.Popen([sys.executable, str(script), name], env=env) for name in ('a', 'b')]
    assert [writer.wait(timeout=300) for writer in writers] == [0, 0]
    assert len(store.layer_items('memory', limit=0).results) == 1000


@pytest.mark.req('STORE-037')
@pytest.mark.req('STORE-006')
def test_threads_of_one_process_writing_to_one_node_lose_nothing(store):
    small_map(store)
    memory(store)
    errors: list[BaseException] = []

    def write(name: str) -> None:
        try:
            for n in range(250):
                store.add_item('memory', Node('element', 'code.timer.kitchen'), f'{name} {n}')
        except BaseException as error:  # collected for the assertion below
            errors.append(error)
    threads = [threading.Thread(target=write, args=(name,)) for name in 'abcd']
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(Store('proj').layer_items('memory', limit=0).results) == 1000


@pytest.mark.req('BASE-030')
def test_a_reported_write_survives_its_process(home, store, tmp_path):
    small_map(store)
    memory(store)
    script = tmp_path / 'one.py'
    script.write_text("from metaform.data import Node, Store\n"
                      "Store('proj').add_item('memory', Node('element', 'code.timer.kitchen'), 'kept')\n"
                      "import os; os._exit(9)\n")
    subprocess.run([sys.executable, str(script)], env={**os.environ, 'METAFORM_HOME': str(home)}, check=False)
    assert [item.value for item in Store('proj').layer_items('memory').results] == ['kept']


@pytest.mark.req('STORE-029')
@pytest.mark.req('STORE-006')
def test_a_file_another_connection_creates_between_the_first_reads_is_not_refused(tmp_path):
    from metaform import sqlite
    from metaform.data.schema import STORE_SCHEMA
    path = tmp_path / 'race.sqlite3'
    done = threading.Event()

    def competitor():
        other = sqlite.connect(path)
        try:
            sqlite.prepare(other, path, STORE_SCHEMA, create=True, version=sqlite.SCHEMA_VERSION)
        finally:
            other.close()
            done.set()

    class Racing:
        """A connection that lets another one create the file right after its first read."""

        def __init__(self, db):
            self.db = db
            self.raced = False

        def execute(self, sql, *args):
            try:
                return self.db.execute(sql, *args)
            finally:
                if not self.raced and sql.lstrip().upper().startswith('SELECT'):
                    self.raced = True
                    threading.Thread(target=competitor).start()
                    done.wait(1.0)

        def __getattr__(self, name):
            return getattr(self.db, name)

    db = sqlite.connect(path)
    try:
        sqlite.prepare(Racing(db), path, STORE_SCHEMA, create=True, version=sqlite.SCHEMA_VERSION)
    finally:
        db.close()
    assert done.wait(10)
    check = sqlite.connect(path)
    try:
        assert check.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == (sqlite.SCHEMA_VERSION,)
    finally:
        check.close()


def _reads(read) -> None:
    """Fifty reads in a row, so a reader is at the file while the writers create it."""
    for _ in range(50):
        read()


def _race(work: list) -> list[BaseException]:
    """Run each callable in its own thread, all released at once; the errors any of them raised."""
    start = threading.Barrier(len(work))
    errors: list[BaseException] = []

    def run(call) -> None:
        start.wait()
        try:
            call()
        except BaseException as error:  # collected for the assertion
            errors.append(error)
    threads = [threading.Thread(target=run, args=(call,)) for call in work]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return errors


@pytest.mark.req('STORE-006')
def test_reads_during_the_first_write_of_a_store_never_fail(store):
    """Two threads create the store while two read it: no read is told the file is an earlier Metaform's, and
    no creating write meets a locked database."""
    from metaform import home as metaform_home
    metaform_home.ensure_metaform('proj')  # so a read goes to the store file, which does not exist yet

    def write(name):
        return lambda: store.layer(name, 'test', 'A layer.', mutable=True, hideable=True)
    errors = _race([write('one'), write('two'), lambda: _reads(Store('proj').layers),
                    lambda: _reads(Store('proj').layers)])
    assert errors == []
    assert sorted(layer.name for layer in Store('proj').layers().results) == ['one', 'two']


@pytest.mark.req('STORE-006')
def test_reads_during_the_first_write_of_the_prompt_database_never_fail(home):
    from metaform.data import prompts

    def write(name):
        return lambda: prompts.add_prompt(name, 'text', f'The {name} prompt.')
    errors = _race([write('one'), write('two'), lambda: _reads(prompts.prompts), lambda: _reads(prompts.prompts)])
    assert errors == []
    assert sorted(prompt.name for prompt in prompts.prompts()) == ['one', 'two']


@pytest.mark.req('STORE-006')
def test_reads_during_the_first_write_of_the_base_database_never_fail(home, tmp_path):
    from metaform import home as metaform_home

    def write(name):
        (tmp_path / name).mkdir()
        return lambda: metaform_home.add_project(name, tmp_path / name)
    errors = _race([write('one'), write('two'), lambda: _reads(metaform_home.projects),
                    lambda: _reads(metaform_home.projects)])
    assert errors == []
    assert sorted(project.project_id for project in metaform_home.projects()) == ['one', 'two']


@pytest.mark.req('STORE-006')
@pytest.mark.req('STORE-029')
def test_a_file_another_process_is_creating_reads_as_empty_and_is_not_refused(tmp_path):
    """Another process has the file open and its schema not yet committed: a read finds an empty store, never
    'an earlier Metaform'. The file is seen at both stages: no bytes yet, and the header written in WAL mode."""
    from metaform import sqlite
    from metaform.data.schema import STORE_SCHEMA
    path = tmp_path / 'creating.sqlite3'
    path.touch()
    with sqlite.opened(path, STORE_SCHEMA, write=False, version=sqlite.SCHEMA_VERSION) as db:
        assert db.execute('SELECT COUNT(*) FROM elements').fetchone() == (0,)
    creator = sqlite.connect(path)
    try:
        creator.execute('PRAGMA journal_mode=WAL')
        assert path.stat().st_size > 0
        with sqlite.opened(path, STORE_SCHEMA, write=False, version=sqlite.SCHEMA_VERSION) as db:
            assert db.execute('SELECT COUNT(*) FROM elements').fetchone() == (0,)
    finally:
        creator.close()


@pytest.mark.req('STORE-006')
def test_the_schema_of_a_new_file_is_written_in_wal_mode(tmp_path):
    """The switch to WAL comes first on a new file, so a reader in another process never holds a lock across it."""
    from metaform import sqlite
    from metaform.data.schema import STORE_SCHEMA
    path = tmp_path / 'new.sqlite3'
    statements: list[str] = []
    db = sqlite.connect(path)
    db.set_trace_callback(statements.append)
    try:
        sqlite.prepare(db, path, STORE_SCHEMA, create=True, version=sqlite.SCHEMA_VERSION)
    finally:
        db.close()
    switch = next(n for n, statement in enumerate(statements) if 'journal_mode' in statement)
    first_table = next(n for n, statement in enumerate(statements) if 'CREATE TABLE' in statement)
    assert switch < first_table


READER = '''
import sys, time
from metaform.data import Store
Store('proj').layers()
print('reading', flush=True)
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    if any(layer.name == 'memory' for layer in Store('proj').layers().results):
        break
'''


@pytest.mark.req('STORE-006')
def test_a_process_reading_a_store_another_process_creates_never_fails(home, store, tmp_path):
    """The reader starts first and reads until the layer this process creates appears; no read fails."""
    reader = tmp_path / 'reader.py'
    reader.write_text(READER)
    env = {**os.environ, 'METAFORM_HOME': str(home)}
    reading = subprocess.Popen([sys.executable, str(reader)], env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    assert reading.stdout and reading.stdout.readline() == 'reading\n'
    small_map(store)
    memory(store)
    _, err = reading.communicate(timeout=300)
    assert (reading.returncode, err) == (0, '')


def _free(lock: threading.RLock) -> bool:
    """Whether another thread could take the lock right now, so it is not held by the calling one."""
    result: list[bool] = []

    def probe() -> None:
        taken = lock.acquire(blocking=False)
        if taken:
            lock.release()
        result.append(taken)
    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return result[0]


@pytest.fixture
def lock_trace(monkeypatch):
    """Replace `sqlite.prepare` with one that records whether the file's lock is held while it runs, and whether it
    is held at each later statement of the connection, keyed by the file's name."""
    from metaform import sqlite
    real = sqlite.prepare
    seen: dict[str, list[tuple[str, bool]]] = {}

    def prepare(db, path, schema, *, create, version):
        lock = sqlite.writer_lock(path)
        events = seen.setdefault(path.name, [])
        events.append(('prepare', not _free(lock)))
        db.set_trace_callback(lambda statement: events.append((statement, not _free(lock))))
        return real(db, path, schema, create=create, version=version)
    monkeypatch.setattr(sqlite, 'prepare', prepare)
    return seen


def _openers(home, tmp_path):
    """Each database file's write opener and read opener, both context managers."""
    from metaform import home as metaform_home
    from metaform.data import history, prompts
    from metaform.data.session import Session
    folder = tmp_path / 'proj'
    folder.mkdir()
    metaform_home.add_project('proj', folder)
    return {
        'store.sqlite3': (lambda: Session('proj').write(), lambda: Session('proj').read()),
        'history.sqlite3': (lambda: history._db('proj', write=True), lambda: history._db('proj')),
        'prompts.sqlite3': (lambda: prompts._db(write=True), lambda: prompts._db()),
        'metaform.sqlite3': (lambda: metaform_home.base(write=True), lambda: metaform_home.base()),
    }


FILES = ['store.sqlite3', 'history.sqlite3', 'prompts.sqlite3', 'metaform.sqlite3']


@pytest.mark.req('STORE-006')
@pytest.mark.parametrize('name', FILES)
def test_a_write_prepares_its_connection_and_runs_its_transaction_inside_the_file_lock(home, tmp_path, lock_trace,
                                                                                       name):
    write, _ = _openers(home, tmp_path)[name]
    lock_trace.clear()
    with write() as tx:
        db = getattr(tx, 'db', tx)
        db.execute('SELECT 1')
    events = lock_trace[name]
    assert ('prepare', True) in events
    begins = [held for statement, held in events if statement.startswith('BEGIN IMMEDIATE')]
    assert begins and all(begins)  # the schema's own transaction on a new file, then the write's
    assert [held for statement, held in events if statement == 'SELECT 1'] == [True]
    assert [held for statement, held in events if statement == 'COMMIT'][-1] is True


@pytest.mark.req('STORE-006')
@pytest.mark.parametrize('name', FILES)
def test_a_read_prepares_its_connection_inside_the_file_lock_and_lets_go_before_its_transaction(home, tmp_path,
                                                                                                lock_trace, name):
    write, read = _openers(home, tmp_path)[name]
    with write():
        pass  # so the file exists and a read opens it rather than an empty database in memory
    lock_trace.clear()
    with read() as tx:
        db = getattr(tx, 'db', tx)
        db.execute('SELECT 1')
    events = lock_trace[name]
    assert ('prepare', True) in events
    assert [held for statement, held in events if statement == 'BEGIN'] == [False]
    assert [held for statement, held in events if statement in ('SELECT 1', 'COMMIT')] == [False, False]
