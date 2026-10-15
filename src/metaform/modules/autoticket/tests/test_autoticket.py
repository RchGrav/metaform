"""autoticket's acceptance, artifacts/specs-draft/autoticket.md: local test logs and a stub for ssh, no real host."""
from __future__ import annotations

import json
import os
import random
import signal
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.kind('simulation')

TEMPLATES = (
    lambda rng: f'2026-10-15 10:{rng.randint(10, 59)}:{rng.randint(10, 59)} ERROR payment declined by gateway for '
                f'order {rng.randint(10000, 99999)} customer {rng.getrandbits(32):08x}',
    lambda rng: f'2026-10-15 10:{rng.randint(10, 59)}:{rng.randint(10, 59)} CRITICAL database connection pool '
                f'exhausted after {rng.randint(100, 9999)} ms waiting on replica db{rng.randint(1, 9)}',
    lambda rng: f'2026-10-15 10:{rng.randint(10, 59)}:{rng.randint(10, 59)} ERROR cache stampede detected on shard '
                f'{rng.randint(1, 64)} key {rng.getrandbits(40):010x} ttl {rng.randint(1, 600)}',
)


def traceback_lines():
    """A log line and its 29-line Python traceback: 13 frames, the raise and the exception."""
    frames = []
    for depth in range(13):
        frames += [f'  File "/srv/shop/app/step{depth}.py", line {10 + depth}, in handle{depth}',
                   f'    result = handle{depth + 1}(request)']
    return ['2026-10-15 10:00:00 ERROR request failed', 'Traceback (most recent call last):', *frames,
            '    raise ValueError("amount must be positive")', 'ValueError: amount must be positive']


@pytest.fixture
def project(run, tmp_path):
    run('enable', 'autoticket')
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    return folder


class Driver:
    """A Watch in this process, ticked by hand, with a clock that can be moved on."""

    def __init__(self, folder):
        from metaform.module import context
        from metaform.modules.autoticket.watch import Watch
        self.ctx = context('autoticket', folder)
        self.skew = 0.0
        self.watch = Watch(self.ctx, self.ctx.require_store(), clock=lambda: time.time() + self.skew,
                           monotonic=lambda: time.monotonic() + self.skew)

    def settle(self, seconds=1.5, until=None):
        """Tick until `until()` holds or `seconds` pass, then close the open entries and write them."""
        ends = time.monotonic() + seconds
        while time.monotonic() < ends and not (until and until()):
            self.watch.tick()
            time.sleep(0.05)
        self.watch.tick()
        self.skew += 3  # quiet for longer than an entry waits
        self.watch.tick()
        self.watch.written_at = 0
        self.watch.tick()

    def groups(self):
        with self.ctx.require_store().tables(write=False) as tx:
            return [dict(row) for row in tx.rows('groups', limit=0).results]

    def total(self):
        return sum(row['count'] for row in self.groups())

    def close(self):
        self.watch.release()


def write(log, lines):
    with open(log, 'a', encoding='utf-8') as handle:
        handle.writelines(line + '\n' for line in lines)


def test_a_thousand_lines_of_three_templates_make_three_groups_and_the_log_is_not_copied(run, project, home):
    log = project / 'app.log'
    log.write_text('2026-10-15 09:00:00 ERROR before watching began, never read\n', encoding='utf-8')
    run('autoticket', 'add', str(log), cwd=project)
    rng = random.Random(15)
    lines = [TEMPLATES[n % 3](rng) for n in range(1000)]
    rng.shuffle(lines)
    driver = Driver(project)
    try:
        write(log, lines)
        driver.settle(until=lambda: driver.watch.totals.lines >= 1000)
        groups = driver.groups()
    finally:
        driver.close()
    assert len(groups) == 3
    assert sum(row['count'] for row in groups) == 1000
    assert sorted(row['count'] for row in groups) == [333, 333, 334]
    # the log is not copied: nothing in the home holds a line of it but the three examples
    examples = {row['example'] for row in groups}
    held = b''.join(path.read_bytes() for path in home.rglob('*') if path.is_file())
    assert sum(1 for line in lines if line.encode() in held and line not in examples) == 0


def test_a_thirty_line_traceback_is_one_entry_counted_once(run, project):
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    trace = traceback_lines()
    assert len(trace) == 30
    driver = Driver(project)
    try:
        write(log, [*trace, '2026-10-15 10:00:01 INFO next request served', *trace])
        driver.settle(until=lambda: driver.watch.totals.lines >= 61)
        groups = driver.groups()
    finally:
        driver.close()
    assert len(groups) == 1 and groups[0]['count'] == 2
    assert groups[0]['example'].count('\n') == 29 and groups[0]['example'].endswith('ValueError: amount must be positive')


def test_rotation_and_truncation_lose_no_line_and_count_none_twice(run, project):
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    rng = random.Random(1)
    driver = Driver(project)
    try:
        write(log, [TEMPLATES[0](rng) for _ in range(5)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 5)
        assert driver.total() == 5
        rotated = project / 'app.log.1'
        log.rename(rotated)
        write(rotated, [TEMPLATES[0](rng) for _ in range(2)])  # written to the old file after it was renamed
        write(log, [TEMPLATES[0](rng) for _ in range(3)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 10)
        assert driver.total() == 10
        log.write_text('', encoding='utf-8')  # truncated in place
        driver.settle(seconds=1.0)
        write(log, [TEMPLATES[0](rng) for _ in range(4)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 14)
        assert driver.total() == 14
    finally:
        driver.close()


@pytest.fixture
def stub_ssh(tmp_path, monkeypatch):
    """An ssh that runs the remote command on this machine, the host ignored, as a test needs no real host. Like ssh it
    relays the remote output itself, so killing it ends the stream as a dropped link does."""
    folder = tmp_path / 'bin'
    folder.mkdir()
    stub = folder / 'ssh'
    stub.write_text(f'#!{sys.executable}\n'
                    'import subprocess, sys\n'
                    'args = sys.argv[1:]\n'
                    'while args and args[0] == "-o":\n'
                    '    args = args[2:]\n'
                    'child = subprocess.Popen(["sh", "-c", args[1]], stdout=subprocess.PIPE)\n'
                    'for chunk in iter(lambda: child.stdout.read1(65536), b""):\n'
                    '    sys.stdout.buffer.write(chunk)\n'
                    '    sys.stdout.buffer.flush()\n'
                    'sys.exit(child.wait())\n', encoding='utf-8')
    stub.chmod(0o755)
    monkeypatch.setenv('PATH', f'{folder}{os.pathsep}{os.environ["PATH"]}')
    return stub


def test_an_ssh_drop_loses_no_line_counts_none_twice_and_is_recorded(run, project, stub_ssh):
    log = project / 'remote.log'
    log.touch()
    source = f'ssh://web1{log}'
    run('autoticket', 'add', source, cwd=project)
    rng = random.Random(2)
    driver = Driver(project)
    try:
        driver.settle(until=lambda: bool(driver.watch.held) and driver.watch.held[source].identity != '')
        write(log, [TEMPLATES[1](rng) for _ in range(6)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 6)
        assert driver.total() == 6
        reader = driver.watch.held[source].reader
        reader.process.kill()  # the link drops mid-stream
        write(log, [TEMPLATES[1](rng) for _ in range(4)])  # written while it is down
        driver.settle(seconds=6, until=lambda: driver.watch.totals.lines >= 10)
        assert driver.total() == 10
        write(log, [TEMPLATES[1](rng) for _ in range(2)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 12)
        assert driver.total() == 12
    finally:
        driver.close()
    shown = json.loads(run('autoticket', 'logs', '--json', cwd=project).stdout)['logs'][0]
    assert shown['drops'] == 1 and shown['reconnects'] == 1 and 'stream ended' in shown['last_drop']


def test_two_processes_count_each_line_once_and_one_takes_over_when_the_other_dies(run, project, home):
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    environment = {**os.environ, 'METAFORM_HOME': str(home)}

    def watcher(seconds):
        return subprocess.Popen([sys.executable, '-m', 'metaform', 'autoticket', 'watch', f'seconds={seconds}',
                                 '--json'], cwd=project, env=environment, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def reader():
        return json.loads(run('autoticket', 'logs', '--json', cwd=project).stdout)['logs'][0]['reader']

    first = watcher(60)
    ends = time.monotonic() + 30
    while reader() is None and time.monotonic() < ends:
        time.sleep(0.2)
    holder = reader()
    assert holder is not None and holder.split(':')[1] == str(first.pid)
    second = watcher(20)
    rng = random.Random(3)
    written = 0
    for _ in range(3):
        write(log, [TEMPLATES[2](rng) for _ in range(50)])
        written += 50
        time.sleep(1.5)
    first.send_signal(signal.SIGKILL)  # dies holding the lease, some lines read and not yet written
    first.wait()
    for _ in range(3):
        write(log, [TEMPLATES[2](rng) for _ in range(50)])
        written += 50
        time.sleep(1.0)
    _, err = second.communicate(timeout=60)
    assert second.returncode == 0, err
    groups = json.loads(run('autoticket', 'list', '--json', cwd=project).stdout)['groups']
    assert sum(group['count'] for group in groups) == written == 300


def test_a_line_holding_an_api_key_is_kept_with_the_key_masked(run, project, home):
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    key, bearer, password = 'sk-ant-api03-q8Zr2Lm4Np6Tx0Vb', 'Zm9vYmFyYmF6cXV4MTIz', 'hunter2-Plover'
    driver = Driver(project)
    try:
        line = (f'2026-10-15 10:00:00 ERROR upstream refused key={key} with Authorization: Bearer {bearer} '
                f'db=postgres://shop:{password}@db1/shop')
        write(log, [line])
        driver.settle(until=lambda: driver.watch.totals.lines >= 1)
        example = driver.groups()[0]['example']
    finally:
        driver.close()
    assert key not in example and bearer not in example and password not in example
    assert 'key=****' in example and 'Bearer ****' in example and 'shop:****@db1' in example
    for path in home.rglob('*'):
        if path.is_file():
            data = path.read_bytes()
            assert key.encode() not in data and bearer.encode() not in data and password.encode() not in data, path


def test_after_the_first_list_a_new_error_is_reported_at_once_and_a_known_one_is_not(run, project, monkeypatch):
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    from metaform.modules.autoticket import watch as watching  # after run, which loads the module afresh
    told = []
    monkeypatch.setattr(watching, 'signal', lambda ctx, kind, details: told.append((kind, details)))
    rng = random.Random(4)
    driver = Driver(project)
    try:
        write(log, [TEMPLATES[0](rng) for _ in range(3)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 3)
        assert told == []  # no baseline yet: a group made now is not reported
        driver.skew += 15 * 60  # the interval passes: the first list, which sets the baseline
        driver.watch.written_at = 0
        driver.watch.tick()
        assert [kind for kind, _ in told] == ['autoticket-list']
        assert told[0][1]['baseline'] is True and told[0][1]['groups'][0]['count'] == 3
        write(log, [TEMPLATES[0](rng), TEMPLATES[1](rng)])  # a known kind and a new one
        driver.settle(until=lambda: driver.watch.totals.lines >= 5)
        news = [details for kind, details in told if kind == 'autoticket-new']
        assert len(news) == 1 and 'database connection pool' in news[0]['example']
        assert news[0]['count'] == 1 and set(news[0]['working']) == {'agents', 'tickets'}
        assert [kind for kind, _ in told] == ['autoticket-list', 'autoticket-new']  # the next list is not due yet
    finally:
        driver.close()
