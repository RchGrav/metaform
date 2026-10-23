"""Measure 60-second Linux idle CPU of an isolated actual fake-ACP runner.

Copy into a checkout's tests directory and run pytest with
METAFORM_IDLE_MEASUREMENT naming the JSON result. No paid model is called.
"""
import json
import os
import threading
import time
from pathlib import Path

import pytest

from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

pytestmark = pytest.mark.kind('simulation')


def cpu(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')


def test_actual_runner_idle_cpu(run, home, project_folder, tmp_path):
    live = Dispatch(run, home, project_folder, tmp_path)
    run('set', '--no-dispatch-autostart', '--no-dispatch-stay-connected', cwd=project_folder)
    try:
        live.start('hold')
        eventually(lambda: live.received('session/prompt'))
        adapter_pid = next(entry['pid'] for entry in live.entries() if 'pid' in entry)
        runner_pid = live.process.pid
        before = {'runner': cpu(runner_pid), 'adapter': cpu(adapter_pid)}
        started = time.monotonic()
        threading.Event().wait(60)
        elapsed = time.monotonic() - started
        after = {'runner': cpu(runner_pid), 'adapter': cpu(adapter_pid)}
        result = {
            'scenario': 'Actual isolated runner and fake ACP adapter, unfinished hold-mode prompt, no incoming changes.',
            'elapsed_seconds': elapsed,
            'cpu_seconds': {name: after[name] - value for name, value in before.items()},
            'cpu_percent_one_core': {name: 100 * (after[name] - value) / elapsed for name, value in before.items()},
            'ticket_still_open': live.ticket().done is None,
            'limits': 'Linux /proc process CPU, 1/HZ resolution. No paid model or web server process. '
                      'An isolated idle workflow measures runner regression, not production throughput.',
        }
        target = os.environ.get('METAFORM_IDLE_MEASUREMENT')
        assert target, 'METAFORM_IDLE_MEASUREMENT must name the output artifact'
        Path(target).write_text(json.dumps(result, indent=2) + '\n')
        assert result['ticket_still_open']
    finally:
        live.stop()
        live.close()
