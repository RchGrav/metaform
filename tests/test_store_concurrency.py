"""Many writers at once: processes and threads each add their writes, and none is lost."""
from __future__ import annotations

import os
import subprocess
import sys
import threading

import pytest

from metaform.data import Node, Store
from storekit import memory, small_map

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
