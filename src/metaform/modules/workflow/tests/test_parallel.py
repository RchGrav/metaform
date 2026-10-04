"""Independent branch returns cannot overwrite one another's continuation."""
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from metaform.modules.workflow import executor
from metaform.modules.workflow.binding import Logic
from metaform.modules.workflow.element import ElementValue

pytestmark = [pytest.mark.req('BASE-051'), pytest.mark.kind('fixture')]


def test_simultaneous_branch_returns_keep_all_results(home):
    script = '@STATE_INIT:\n@CONSTRAINT:\n'
    lookup = lambda address, name: (Logic('logic', name, name, script), ElementValue({'address': address}))
    parent = executor.start('workflow.quality.code.run()', {}, None, lookup, {})
    words = executor.parallel(parent, [f'{{result{i}}} := workflow.quality.code.branch()' for i in range(4)],
                              {}, lookup)
    ready = home / 'return-now'
    code = '''import json, sys, time
from pathlib import Path
from metaform.modules.workflow import executor
from metaform import nonce
from metaform.data.records import plain
real = nonce.update
def slow(*args, **kwargs):
    time.sleep(0.1)
    return real(*args, **kwargs)
nonce.update = slow
while not Path(sys.argv[2]).exists():
    time.sleep(0.01)
print(json.dumps(plain(executor.complete(sys.argv[1], "RETURN TRUE", {}))))
'''
    processes = [subprocess.Popen([sys.executable, '-c', code, word, str(ready)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for word in words]
    try:
        time.sleep(0.2)
        ready.touch()
        with ThreadPoolExecutor(max_workers=len(processes)) as pool:
            outputs = list(pool.map(lambda process: process.communicate(timeout=10), processes))
        assert all(process.returncode == 0 for process in processes), outputs
        results = [json.loads(out) for out, _ in outputs]
        assert sum('resume' in result for result in results) == 1
        resumed = executor.view(parent)
        assert resumed['state'] == 'running'
        assert resumed['variables'] == {f'result{i}': True for i in range(4)}
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate()
