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


def test_a_new_kind_of_error_in_a_log_is_filed_at_once_and_a_known_kind_is_counted_on_its_ticket(run, project):
    store = mapped(project)
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    rng = random.Random(4)
    driver = Driver(project)
    try:
        write(log, [TEMPLATES[0](rng) for _ in range(3)])
        driver.settle(until=lambda: driver.watch.totals.lines >= 3)
        [first] = tickets(store)
        assert first.kind == 'broken' and 'payment declined' in first.task and first.address == 'code.metaform'
        write(log, [TEMPLATES[0](rng), TEMPLATES[1](rng)])  # a known kind and a new one
        driver.settle(until=lambda: driver.watch.totals.lines >= 5)
        filed = tickets(store)
        assert len(filed) == 2 and any('database connection pool' in record.task for record in filed)
        assert 'seen 4 times' in note_of(store, first.id)
    finally:
        driver.close()


@pytest.mark.req('QUAL-015')
def test_a_local_reader_at_its_files_end_sleeps_until_the_file_changes(tmp_path, monkeypatch):
    """At the end of its file the reader looks again only when the system says the file changed: not on a timer, and
    not for writes to other files in its folder; a line written to its own file is read at once."""
    import queue
    import threading

    from metaform.modules.autoticket import sources
    log = tmp_path / 'app.log'
    log.touch()
    looks = []
    real = sources.local_identity
    monkeypatch.setattr(sources, 'local_identity', lambda path: (looks.append(path), real(path))[1])
    events = queue.Queue()
    reader = sources.reader(sources.Source(str(log)), '', 0, events)
    reader.start()
    try:
        assert events.get(timeout=5)[1][0] == 'file'
        threading.Event().wait(0.5)
        before = len(looks)
        for at in range(50):  # a burst in the same folder that does not concern it
            write(tmp_path / 'other.log', [f'2026-10-15 10:00:00 ERROR elsewhere {at}'])
        threading.Event().wait(1.0)
        quiet = len(looks) - before
        write(log, ['2026-10-15 10:00:01 ERROR here'])
        line = events.get(timeout=2)[1]
    finally:
        reader.stop()
        reader.join(5)
    assert quiet == 0
    assert line[:2] == ('line', '2026-10-15 10:00:01 ERROR here')


@pytest.mark.req('QUAL-015')
def test_the_watch_reads_nothing_while_nothing_happens_nor_for_changes_that_do_not_concern_it(run, project,
                                                                                            monkeypatch):
    """A watch with its log read to the end touches the store only for an event or a deadline: a quiet second and a
    burst of map.changed naming other tables or projects cost no read."""
    import asyncio
    import threading
    log = project / 'app.log'
    log.touch()
    run('autoticket', 'add', str(log), cwd=project)
    from metaform.data import Store
    from metaform.module import Context, context
    from metaform.modules.autoticket import watch_logs
    touched = []
    settled = threading.Event()  # the logs claimed, the lease taken and its first position written
    real = Store.tables

    def tables(self, *args, **kwargs):
        touched.append(time.monotonic())
        if len(touched) >= 3:
            settled.set()
        return real(self, *args, **kwargs)
    monkeypatch.setattr(Store, 'tables', tables)
    handlers = []

    class Heard:
        def close(self):
            pass

    def listen(self, handler):
        handlers.append(handler)
        return Heard()
    monkeypatch.setattr(Context, 'listen', listen)
    window = []

    def burst():
        settled.wait(10)
        threading.Event().wait(0.2)  # the last of those writes ended
        window.append(time.monotonic())
        for _ in range(50):
            for payload in ({'project': 'proj', 'tables': ['ops', 'work']}, {'project': 'other', 'base_id': None},
                            {'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']}):
                for handler in handlers:
                    handler(payload)
        threading.Event().wait(1.5)
        window.append(time.monotonic())
    threading.Thread(target=burst, daemon=True).start()
    asyncio.run(watch_logs(context('autoticket', project, nouns={'seconds': 5})))
    assert len(window) == 2
    assert [at for at in touched if window[0] <= at <= window[1]] == []


def test_a_group_sits_at_the_address_whose_file_ref_names_its_traces_file_else_at_the_top_node(project):
    """A group is placed by the file ref in the sources layer, as dispatch link writes it, ticket
    code.analyzer.refactoring#1a; a file no ref names leaves it at the project's DE."""
    from metaform.data import Node, Store
    from metaform.module import context
    from metaform.modules.autoticket.watch import place
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.shop.online', name_length=2, role='DE')
        store.add_element(layer.name, 'code.gateway.payment', name_length=2, role='SE')
        store.add_join(layer.name, 'code.shop.online', 'code.gateway.payment', purpose='Take payment.')
        sources = store.layer('sources', 'intake', 'refs', mutable=True, hideable=True, ready=True)
        store.add_item(sources.name, Node('element', 'code.gateway.payment'), 'gateway',
                       refs=[('path', 'app/pay.py')])
    ctx = context('autoticket', project)
    trace = 'Traceback (most recent call last):\n  File "{}", line 9, in charge\nValueError: declined'
    assert place(ctx, store, trace.format(project / 'app' / 'pay.py')) == 'code.gateway.payment'
    assert place(ctx, store, trace.format(project / 'app' / 'cart.py')) == 'code.gateway.payment'  # nearest: its folder
    assert place(ctx, store, trace.format(project / 'lib' / 'cart.py')) == 'code.shop.online'
    assert place(ctx, store, trace.format('/elsewhere/app/pay.py')) == 'code.shop.online'


# ------------------------------------------------------------------------------------------------ faults filed


OWNED = (('code.server.web', 'src/metaform/modules/web/server.py'),
         ('code.interface.graphical', 'src/metaform/modules/web/page/app/core/errors.js'),
         ('code.dispatcher.agent', 'src/metaform/modules/dispatch/runner.py'))


def mapped(project):
    """A map whose sources layer names the web server, the page's error part and the dispatch runner, each at its own
    element, under a DE."""
    from metaform.data import Node, Store
    store = Store('proj')
    with store.atomic():
        layer = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.metaform', name_length=1, role='DE')
        for address, _ in OWNED:
            store.add_element(layer.name, address, name_length=2, role='SE')
            store.add_join(layer.name, 'code.metaform', address, purpose=f'Serve {address}.')
        sources = store.layer('sources', 'intake', 'refs', mutable=True, hideable=True, ready=True)
        for address, path in OWNED:
            store.add_item(sources.name, Node('element', address), address, refs=[('path', path)])
    return store


def raise_fault(project, **payload):
    """A fault as its source publishes it, `fault.raised`."""
    from metaform.module import context
    return context('autoticket', project).publish('fault.raised', payload)


def web_fault(project, number=0, **said):
    return raise_fault(project, source='web', message=f"KeyError: 'node {number}'", **said,
                       detail=('Traceback (most recent call last):\n'
                               f'  File "{project}/src/metaform/modules/web/server.py", line 812, in graph\n'
                               f"KeyError: 'node {number}'"),
                       reproduce='GET /api/graph on the web server, as the page reads the map.')


def delivered():
    """The faults module the bus delivers to, as the loader loaded it, so a patch on it is the one that runs."""
    from metaform import loader
    module = next(module for module in loader.enabled() if module.id == 'autoticket')
    return sys.modules[module.subscriptions[0].handler.__module__]


def tickets(store, open=True):
    return [record for record in store.work(open=open, limit=0).results]


def note_of(store, work_id):
    return next(record for record in store.work(limit=0).results if record.id == work_id).note or ''


def test_a_web_fault_a_page_error_and_a_crashed_run_each_file_one_ticket_at_the_owning_element(run, project):
    store = mapped(project)
    web_fault(project)
    raise_fault(project, source='page', message='TypeError: graph.nodes is undefined',
                detail='TypeError: graph.nodes is undefined\n    at draw (/page/app/core/errors.js:77:12)',
                file='page/app/core/errors.js', reproduce='Open the web page on the project and select a node.')
    raise_fault(project, source='run', message='The run of ticket 1234 ended: it failed: the agent crashed',
                detail=('Traceback (most recent call last):\n'
                        f'  File "{project}/src/metaform/modules/dispatch/runner.py", line 3480, in run\n'
                        'RuntimeError: the agent crashed'),
                reproduce='metaform dispatch start 1234 claude', work_id='1234')
    found = {record.address: record for record in tickets(store)}
    assert set(found) == {'code.server.web', 'code.interface.graphical', 'code.dispatcher.agent'}
    web = found['code.server.web']
    assert web.kind == 'broken' and not web.held
    assert "KeyError: 'node 0'" in web.task and 'seen 1 time' in web.task and 'GET /api/graph' in web.task
    assert 'first 20' in web.task and 'last 20' in web.task  # first and last seen, as times
    assert 'server.py", line 812' in web.task  # the sample
    assert 'check' in web.task and 'no longer happens' in web.task
    assert 'graph.nodes is undefined' in found['code.interface.graphical'].task
    assert 'metaform dispatch start 1234 claude' in found['code.dispatcher.agent'].task


def test_the_same_error_ten_times_makes_one_ticket_whose_note_counts_ten(run, project):
    store = mapped(project)
    for number in range(10):
        web_fault(project, number)
    filed = tickets(store)
    assert len(filed) == 1
    assert 'seen 10 times' in filed[0].note


def test_a_burst_of_one_error_is_one_pass_and_counts_each(run, project, monkeypatch):
    """Faults that arrive while a pass runs merge into the next pass: twenty in a burst, two passes, one ticket."""
    store = mapped(project)
    faults = delivered()
    passes = []
    real = faults.settle

    def counted(ctx, store, batch):
        passes.append(sum(fault.count for fault in batch))
        if len(passes) == 1:  # the burst arrives while the first pass runs
            for number in range(1, 20):
                web_fault(project, number)
        return real(ctx, store, batch)
    monkeypatch.setattr(faults, 'settle', counted)
    web_fault(project)
    assert passes == [1, 19]
    assert len(tickets(store)) == 1 and 'seen 20 times' in tickets(store)[0].note


def test_twenty_page_faults_in_one_request_are_one_pass(run, project, monkeypatch):
    """The page sends the errors of a second in one request; the web server hands them on as one event, one pass."""
    from metaform.modules.web import server
    mapped(project)
    faults = delivered()
    passes = []
    real = faults.settle

    def counted(ctx, store, batch):
        passes.append(len(batch))
        return real(ctx, store, batch)
    monkeypatch.setattr(faults, 'settle', counted)

    class Asked:
        def send(self, status, data):
            self.answer = (status, data)
    handler = Asked()
    handler.fault_raised = lambda named, payload: server.Handler.fault_raised(handler, named, payload)
    server.Handler.page_faults(handler, {'project': 'proj', 'faults': [
        {'message': f'TypeError: part {number} of the drawing is undefined', 'where': '/page/app/core/errors.js:77:12'}
        for number in range(20)]})
    assert handler.answer == (200, {'taken': 20})
    assert passes == [20]


SIX = ('payment declined by gateway for order', 'database connection pool exhausted waiting on replica',
       'cache stampede detected on shard key', 'websocket handshake rejected by proxy upstream',
       'template render missing variable heading in layout', 'thumbnail resize ran out of memory on image')


def test_a_sixth_group_waits_while_five_are_open_and_is_filed_when_one_closes(run, project):
    store = mapped(project)
    for words in SIX:
        raise_fault(project, source='web', message=f'ValueError: {words}',
                    reproduce='GET /api/x')
    filed = tickets(store)
    assert len(filed) == 5
    assert not any('thumbnail' in record.task for record in filed)
    run('map', 'work', 'op=done', f'id={filed[0].id}', 'resolution=Fixed.', 'why=Tested.', cwd=project)
    now = tickets(store)  # pending delivery takes no agent slot
    assert len(now) == 6 and any('thumbnail' in record.task for record in now)


@pytest.mark.parametrize('source', ['feedback', 'web', 'page', 'mcp', 'run', 'log'])
def test_fault_creation_never_adds_implicit_hold(run, project, source):
    """Feedback origin and a saved obsolete policy cannot turn repair work into a hold."""
    from metaform import home
    home.save(home.path_key(project), 'autoticket', 'autoticket_hold_feedback', [True], folder=project)
    store = mapped(project)
    raise_fault(project, source=source, message='Remove failing cache adapter', reproduce='Read the help.')
    filed = tickets(store)
    assert len(filed) == 1
    assert not filed[0].held and filed[0].column == 'todo'
    assert 'Held for the person:' not in filed[0].note
    shown = json.loads(run('map', 'work', f'id={filed[0].id}', '--json', cwd=project).stdout)
    assert not shown.get('map', {}).get('hold')


def test_five_dispatch_held_tickets_take_no_slot_and_a_web_fault_is_filed(run, project):
    """The person's hold on a ticket, map_work hold=true, keeps agents off it as the Backlog's held mark does: holding
    the five filed tickets files the waiting sixth group, and a later fault is filed too."""
    store = mapped(project)
    for words in SIX:
        raise_fault(project, source='web', message=f'ValueError: {words}', reproduce='GET /api/x')
    filed = tickets(store)
    assert len(filed) == 5 and not any('thumbnail' in record.task for record in filed)
    for record in filed:
        run('map', 'work', 'op=edit', f'id={record.id}', 'hold=true', 'hold_reason=Wait for triage', cwd=project)
    assert any('thumbnail' in record.task for record in tickets(store))
    web_fault(project)
    assert any("KeyError: 'node 0'" in record.task for record in tickets(store))


def test_an_error_from_an_agent_on_an_autoticket_ticket_lands_on_that_ticket(run, project):
    store = mapped(project)
    web_fault(project)
    [ticket] = tickets(store)
    for _ in range(3):
        raise_fault(project, source='mcp', message='StoreError: the store is locked',
                    reproduce='call map_work op=step', work_id=ticket.id)
    assert [record.id for record in tickets(store)] == [ticket.id]
    note = note_of(store, ticket.id)
    assert 'the store is locked' in note and 'seen 3 times' in note


def test_feedback_and_error_words_do_not_impose_unrequested_approval_gates(run, project):
    store = mapped(project)
    raise_fault(project, source='feedback', message='The map_work help never says what held means.',
                reproduce='Read map_work help.')
    raise_fault(project, source='web', message='OSError: could not delete the base folder',
                reproduce='POST /api/remove-base: remove a base from the page.')
    held = tickets(store)
    assert len(held) == 2 and not any(record.held for record in held)
    assert all('Find its cause and fix it' in record.task for record in held)


@pytest.mark.req('QUAL-015')
def test_a_burst_of_changes_that_do_not_close_an_autoticket_ticket_reads_nothing(run, project, monkeypatch):
    """The subscriber that files a waiting group when a slot frees decides from the event alone: a burst of
    map.changed naming notes, steps, sessions or no tickets costs no read."""
    from metaform.data import Store
    from metaform.module import context
    faults = delivered()
    touched = []
    real = Store.tables
    monkeypatch.setattr(Store, 'tables', lambda self, *a, **k: (touched.append(1), real(self, *a, **k))[1])
    ctx = context('autoticket', project)
    for _ in range(50):
        for payload in ({'project': 'proj', 'tables': ['ops'], 'work_ids': ['a'], 'kinds': ['note']},
                        {'project': 'proj', 'tables': ['work'], 'work_ids': ['b'], 'kinds': ['step']},
                        {'project': 'proj', 'tables': 'dispatch', 'work_ids': [], 'kinds': ['session']},
                        {'project': 'proj', 'tables': ['objects', 'ops']},
                        {'project': 'other', 'tables': ['work'], 'work_ids': ['c'], 'kinds': ['ticket']}):
            faults.freed(payload, ctx)
    assert touched == []


def test_recurrence_reopens_same_issue_and_assignment_but_cancel_stays_cancelled(run, project, monkeypatch):
    from metaform.module import context
    from metaform.modules.autoticket.tests.test_fault_closure import delivered
    from metaform.modules.orchestration.state import SERVICE

    store = mapped(project)
    web_fault(project, 1)
    [original] = tickets(store)
    ctx = context('orchestration', project, project='proj')
    first = SERVICE.ensure(ctx, original.id)
    SERVICE.bind(ctx, first['assignment_id'], 'repair-one', persons=True)
    run('enable', 'dispatch', cwd=project)
    SERVICE.returned(ctx, original.id, 'Repaired.', evidence=['Reproduction passes.'])
    assert not store.ticket(original.id).work.done
    delivered(store, project, original.id)
    assert store.complete_delivery(original.id).done
    web_fault(project, 2)
    reopened = store.ticket(original.id).work
    assert reopened.id == original.id
    assert 'Previous resolution' in reopened.note
    second = SERVICE.ensure(ctx, reopened.id)
    assert second['assignment_id'] == first['assignment_id'] and second['attempt'] == 2
    assert second['evidence'] == [] and second['last_check_in']['previous_evidence']
    store.finish_work(original.id, 'No longer wanted.', 'User choice.', outcome='cancelled')
    web_fault(project, 3)
    assert store.ticket(original.id).work.outcome == 'cancelled'
    assert original.id not in [record.id for record in tickets(store)]


def lights(store, address='code.server.web'):
    """The fault lights: open work records of condition broken or trouble."""
    return [record for record in tickets(store) if record.address == address and record.condition in ('broken', 'trouble')]
