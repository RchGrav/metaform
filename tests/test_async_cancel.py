"""A forced CLI interrupt still drains tasks before closing its event loop."""
import os
import signal
import subprocess
import sys

import pytest

pytestmark = pytest.mark.kind('simulation')


@pytest.mark.req('BASE-031')
@pytest.mark.skipif(os.name == 'nt', reason='SIGINT is delivered differently on Windows')
def test_second_interrupt_drains_untracked_tasks(home, user_module, tmp_path):
    user_module('sleeper', '''
        import asyncio
        from metaform.module import Module, Verb
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        DEPENDENCIES = ()
        async def child():
            try:
                await asyncio.sleep(60)
            finally:
                print('child stopped', flush=True)
        async def sleep(ctx):
            asyncio.create_task(child())
            try:
                print('started', flush=True)
                await asyncio.sleep(60)
            finally:
                print('cleaning', flush=True)
                await asyncio.sleep(60)
        MODULE = Module(id='sleeper', summary='x', purpose='Sleeps. Details: metaform help sleeper.',
                        verbs=(Verb('sleep', sleep, 'Sleep.', needs_project=False),))
    ''')
    process = subprocess.Popen([sys.executable, '-m', 'metaform', 'sleeper', 'sleep'], cwd=tmp_path,
                               env={**os.environ, 'METAFORM_HOME': str(home)}, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'started'
        process.send_signal(signal.SIGINT)
        assert process.stdout.readline().strip() == 'cleaning'
        process.send_signal(signal.SIGINT)
        out, err = process.communicate(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
    assert 'Interrupted.' in err
    assert 'child stopped' in out
    assert 'Task was destroyed' not in err and 'Event loop is closed' not in err
