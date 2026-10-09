"""STORE-006: several processes writing one store at once never damage it.

Found 2026-10-05: a version of sqlite.py that kept read connections open across transactions and let reads skip the
writer lock corrupted the live store under the agents' concurrent writes (artifacts/incident-2026-10-05). This runs the
same kind of load, tickets stepped and read and transcript lines written from several processes, and checks the file.
"""
import multiprocessing
import os
import sqlite3
import time
from contextlib import closing

import pytest

pytestmark = [pytest.mark.req('STORE-006'), pytest.mark.kind('real')]
WORKERS, OPERATIONS = 6, 60  # 360 overlapping writes race as the incident did; 320 each took a minute


def _write(home: str, index: int, ids: list[str], failures) -> None:
    os.environ['METAFORM_HOME'] = home
    from metaform.data import Store
    store, own = Store('proj'), Store('proj', module='dispatch')
    for op in range(OPERATIONS):
        work_id = ids[(index + op) % len(ids)]
        try:
            if op % 3 == 0:
                store.step_work(work_id, f'step {index}-{op}')
            elif op % 3 == 1:
                store.work(open=True, limit=0)
            with own.tables() as tx:
                tx.insert('lines', {'session_id': f'writer-{index}', 'name': f'line-{op}', 'work_id': work_id,
                                    'kind': 'agent_message_chunk', 'text': 'x' * 400, 'seq': time.time_ns()})
        except Exception as error:  # noqa: BLE001  every failure is reported, a damaged file above all
            failures.put(f'writer {index}, op {op}: {error}')
            return


def test_concurrent_writers_leave_the_store_whole(run, home, tmp_path):
    from metaform import home as homes
    from metaform.data import Node, Store
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('enable', 'map')
    run('enable', 'dispatch')
    store = Store('proj')
    store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    for n in range(10):
        store.add_element('parts', f'code.part{n}')
    ids = [store.add_work(Node('element', f'code.part{n % 10}'), 'unbuilt', task=f'task {n}').id
           for n in range(WORKERS * 3)]
    with Store('proj', module='dispatch').tables() as tx:  # the dispatch tables exist before the writers race
        tx.rows('lines', limit=1)
    spawn = multiprocessing.get_context('spawn')
    failures = spawn.Queue()
    writers = [spawn.Process(target=_write, args=(str(home), index, ids, failures)) for index in range(WORKERS)]
    deadline = time.monotonic() + 240
    try:
        for writer in writers:
            writer.start()
        for writer in writers:
            writer.join(max(0, deadline - time.monotonic()))
        assert all(writer.exitcode == 0 for writer in writers), [writer.exitcode for writer in writers]
    finally:
        for writer in writers:
            if writer.is_alive():
                writer.terminate()
                writer.join(5)
    found = []
    while not failures.empty():
        found.append(failures.get())
    path = homes.project_folder('proj') / 'main.metaform.sqlite3'
    with closing(sqlite3.connect(f'file:{path}?mode=ro', uri=True)) as connection:
        checked = connection.execute('PRAGMA integrity_check').fetchall()
        lines = connection.execute('SELECT count(*) FROM "dispatch.lines"').fetchone()[0]
    failures.close()
    failures.join_thread()
    assert found == [], found  # every write succeeds: a failed one, damage above all, is the defect
    assert checked == [('ok',)], checked
    assert lines == WORKERS * OPERATIONS
