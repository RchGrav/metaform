"""The web module: one web GUI server per Metaform home, started and stopped from any folder, VIEW-001, VIEW-002, VIEW-015."""
from __future__ import annotations

import http.client
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import FAKE_AGENT  # dispatch's ACP agent, no model, which every test home starts


def own(project_id):
    """A project's folder in the home, PROJ-026."""
    from metaform import home as metaform_home
    return metaform_home.project_folder(project_id)

pytestmark = pytest.mark.kind('fixture')

PROMPTS = Path(__file__).resolve().parents[1] / 'resources' / 'prompts.xml'


def prompt(name: str) -> str:
    import xml.etree.ElementTree as ET
    found = ET.parse(PROMPTS).getroot().find(name)
    assert found is not None and found.text
    return found.text.strip()


def free_port() -> int:
    """A port below every system's ephemeral range, Linux's from 32768 and Windows' and macOS's from 49152: a port the
    system hands out can be taken by any test's outgoing connection between this probe and the server's bind."""
    import random
    while True:
        port = random.randrange(20000, 32768)
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port


PAGE_KEYS: dict[tuple[str, int], str] = {}  # the page cookie each server gave this test process, by its address


def page_cookie(port, address='127.0.0.1', host=None, *, again=False, token=None):
    """The cookie with the key the server gives a page it serves, as a browser keeps it from loading the page: a write
    that is the person's alone is taken only with it, CLI-011 (UX review, person-consent F1). `token`: the one a
    server on another bind asks of the page's load."""
    if again or (address, port) not in PAGE_KEYS:
        connection = http.client.HTTPConnection(address, port, timeout=10)
        try:
            connection.putrequest('GET', '/', skip_host=True, skip_accept_encoding=True)
            connection.putheader('Host', host or f'{address}:{port}')
            if token:
                connection.putheader('X-Metaform-Token', token)
            connection.endheaders()
            response = connection.getresponse()
            response.read()
            given = [one.split(';', 1)[0] for one in response.msg.get_all('Set-Cookie') or []
                     if one.startswith('metaform_page_')]
        finally:
            connection.close()
        PAGE_KEYS[(address, port)] = '; '.join(given)
    return PAGE_KEYS[(address, port)]


def request(port, path='/', *, address='127.0.0.1', host=None, method='GET', body=None, headers=None):
    """One request; a POST carrying an Origin, as the page's writes do, carries the page's cookie too, unless it names
    a Cookie of its own, as a browser that loaded the page sends it."""
    if method == 'POST' and 'Origin' in (headers or {}) and 'Cookie' not in (headers or {}):
        token = (headers or {}).get('X-Metaform-Token')
        sent = _request(port, path, address=address, host=host, method=method, body=body,
                        headers={**(headers or {}), 'Cookie': page_cookie(port, address, host, token=token)})
        if sent[0] == 403 and 'carries no key this server gave' in sent[1]:  # a key the server has since let go
            sent = _request(port, path, address=address, host=host, method=method, body=body, headers={
                **(headers or {}), 'Cookie': page_cookie(port, address, host, again=True, token=token)})
        return sent
    return _request(port, path, address=address, host=host, method=method, body=body, headers=headers)


def _request(port, path='/', *, address='127.0.0.1', host=None, method='GET', body=None, headers=None):
    connection = http.client.HTTPConnection(address, port, timeout=10)
    try:
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        connection.putheader('Host', host or f'{address}:{port}')
        for key, value in (headers or {}).items():
            connection.putheader(key, value)
        data = b'' if body is None else body.encode('utf-8')
        if body is not None:
            connection.putheader('Content-Length', str(len(data)))
        connection.endheaders(data or None)
        response = connection.getresponse()
        held: dict[str, str] = {}
        for key, value in response.getheaders():  # a header sent twice, as two cookies are, keeps both, a line each
            held[key] = f'{held[key]}\n{value}' if key in held else value
        return response.status, response.read().decode('utf-8', errors='replace'), held
    finally:
        connection.close()


def lan_address() -> str | None:
    """This machine's address on its outbound interface. No packet is sent: a UDP connect only picks the route."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))
            found = probe.getsockname()[0]
    except OSError:
        return None
    return None if found.startswith('127.') else found


def refused(address, port) -> bool:
    try:
        socket.create_connection((address, port), timeout=3).close()
    except OSError:
        return True
    return False


@pytest.fixture
def web(run, home):
    """The test home's web port, set to a free one; the server is stopped and its process gone afterwards."""
    port = free_port()
    run('set', f'--web-port={port}')
    yield port
    run('web', 'stop', ok=False)
    deadline = time.monotonic() + 10
    while not refused('127.0.0.1', port) and time.monotonic() < deadline:
        time.sleep(0.1)


def started(run, cwd=None):
    return json.loads(run('web', '--json', cwd=cwd).stdout)


def intake_agent(run, folder, log, dispatch_runners, *nouns):
    """An intake agent Metaform starts, the fake agent held, and the environment its MCP server records with: its role,
    its work, its runner's session and the base it is pinned to. A page follows only an intake its agent records,
    BASE-039, so a test records through this, never through a bare command line (UX review round 2, 2026-10-17,
    project-scope F6: the follow tests drove the command line, which is never recording, and went red unseen)."""
    from metaform import home as metaform_home
    from metaform.data import Store
    from metaform.modules.dispatch.tests.test_dispatch import eventually
    run('enable', 'dispatch')
    fake = {'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}
    launched = json.loads(run('dispatch', 'intake', 'agent=claude', *nouns, '--json', cwd=folder, env=fake).stdout)
    dispatch_runners.append((launched, folder, log))
    project = metaform_home.folder_project(folder)

    def running():
        with Store(project, module='dispatch').tables(write=False) as tx:
            return next((dict(row) for row in tx.rows('agent_sessions', limit=0).results
                         if row['work_id'] == launched['work_id'] and row['state'] == 'running'), None)
    row = eventually(running)
    return {'METAFORM_ROLE': 'intake', 'METAFORM_WORK': str(row['work_id']), 'METAFORM_SESSION': str(row['runner']),
            'METAFORM_BASE': str(row['base'] or ''), **fake}


@pytest.mark.req('VIEW-001')
def test_web_ships_on_and_with_it_off_the_rest_of_metaform_works(run, module_row, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    assert module_row('web')[1:3] == ['on', 'system']
    assert run('help', 'web').stdout.startswith('web: ')
    run('disable', 'web')
    stopped = run('web', ok=False)
    assert stopped.returncode != 0 and 'Next: metaform enable web' in stopped.stderr
    assert 'Intake: none yet' in run(cwd=folder).stdout
    from metaform.modules.intake import RESOURCE as served  # the served intake, BASE-039, named by the module
    assert run('intake', 'prompt', cwd=folder).stdout.startswith(served.read_text(encoding='utf-8').splitlines()[0])
    assert run('map', 'roots', cwd=folder).returncode == 0
    assert not any(line.startswith('web') for line in run('help', 'commands').stdout.splitlines())


@pytest.mark.req('VIEW-002')
@pytest.mark.req('VIEW-015')
def test_one_server_per_home_serves_every_project_and_stops(run, home, web, tmp_path):
    first, second = tmp_path / 'alpha', tmp_path / 'beta'
    for folder in (first, second):
        folder.mkdir()
        run('add', 'project', folder.name, str(folder))
    address = f'http://127.0.0.1:{web}/'
    assert started(run, first) == {'state': 'started', 'address': address}
    record = json.loads((home / 'run' / 'web.json').read_text(encoding='utf-8'))
    assert started(run, second) == {'state': 'running', 'address': address}
    assert json.loads((home / 'run' / 'web.json').read_text(encoding='utf-8'))['pid'] == record['pid']
    status, body, _ = request(web, '/api/projects')
    assert status == 200 and {'alpha', 'beta'} <= {project['id'] for project in json.loads(body)['projects']}
    assert run('web', 'stop').stdout == 'state: stopped\n'
    assert not (home / 'run' / 'web.json').exists()
    assert refused('127.0.0.1', web)
    assert run('web', 'stop').stdout == 'state: not running\n'


@pytest.mark.req('VIEW-002')
def test_a_held_port_or_an_address_it_cannot_bind_stops_with_the_setting_to_change(run, web):
    with socket.socket() as holder:
        holder.bind(('127.0.0.1', web))
        holder.listen()
        held = run('web', ok=False)
    assert held.returncode != 0 and str(web) in held.stderr
    assert 'Next: metaform set --web-port <port>' in held.stderr
    run('set', '--web-bind=203.0.113.7')
    unbound = run('web', ok=False)
    assert unbound.returncode != 0 and '203.0.113.7' in unbound.stderr
    assert 'Next: metaform set --web-bind <address>' in unbound.stderr


@pytest.mark.req('VIEW-002')
def test_a_request_for_another_host_is_refused_and_loopback_asks_no_token(run, web):
    started(run)
    assert request(web, '/')[0] == 200
    assert request(web, '/', host=f'localhost:{web}')[0] == 200
    assert request(web, '/api/projects', host=f'rebound.example:{web}')[0] == 403
    assert request(web, '/', host=f'127.0.0.1:{web + 1}')[0] == 403


@pytest.mark.req('VIEW-002')
def test_the_default_bind_takes_no_other_address_and_another_bind_needs_the_token(run, web):
    lan = lan_address()
    if lan is None:
        pytest.skip('this machine has no address besides loopback')
    started(run)
    assert refused(lan, web)
    run('web', 'stop')
    run('set', '--web-bind=0.0.0.0')
    answer = started(run)
    token = answer['token']
    assert answer['state'] == 'started' and answer['address'].endswith(f':{web}/?t={token}')
    assert request(web, '/', address=lan)[0] == 403
    assert request(web, '/api/projects', address=lan)[0] == 403
    status, _, headers = request(web, f'/?t={token}', address=lan)
    assert status == 200
    cookie = headers['Set-Cookie'].split(';', 1)[0]
    assert request(web, '/api/projects', address=lan, headers={'Cookie': cookie})[0] == 200
    wrong = cookie[:-1] + ('y' if cookie.endswith('x') else 'x')  # one character off, never the token itself
    assert request(web, '/api/projects', address=lan, headers={'Cookie': wrong})[0] == 403
    assert started(run)['token'] == token


@pytest.mark.req('VIEW-002')
def test_a_server_older_than_the_store_hands_over_to_the_code_on_disk_only_when_that_code_changed(
        run, web, mapped, monkeypatch):
    """A server started before the code on disk moved the store to a newer schema starts a replacement from that code
    on its port and sends the request there; with its code unchanged the store is from a newer release, and the error
    stands, so nothing loops."""
    import os
    import threading

    from metaform import sqlite
    from metaform.modules.web import server as web_server
    monkeypatch.setattr(sqlite, 'SCHEMA_VERSION', str(int(sqlite.SCHEMA_VERSION) - 1))  # the store is one newer
    old = web_server.Server('127.0.0.1', web, 'old')
    serving = threading.Thread(target=old.run, daemon=True)
    serving.start()
    status, body = api(web, '/api/roots?project=proj')
    assert status == 404 and f'supports version {sqlite.SCHEMA_VERSION}.' in body['error']
    old.code = 'the code it started from'  # the code on disk changed since
    status, _, headers = request(web, '/api/roots?project=proj')
    assert status == 307 and headers['Location'] == '/api/roots?project=proj'
    serving.join(10)
    assert not serving.is_alive()
    assert api(web, '/api/roots?project=proj')[0] == 200
    assert api(web, '/api/server')[1]['pid'] != os.getpid()


@pytest.mark.req('VIEW-002')
def test_a_read_that_hangs_is_answered_in_time_while_health_names_it_until_it_is_stuck(run, web, mapped, monkeypatch):
    """A page read whose work hangs is answered 503 with what it waits on within the read limit, so it never holds the
    page's connection; /api/health answers meanwhile, names it as slow, and answers 503 once it is stuck."""
    import threading

    from metaform.modules.web import server as web_server
    monkeypatch.setattr(web_server, 'READ_LIMIT', 0.5)
    monkeypatch.setattr(web_server, 'SLOW', 0.2)
    monkeypatch.setattr(web_server, 'STUCK', 1.5)
    let_go, real = threading.Event(), web_server.query_read

    def hung(store, name, given):
        if name == 'roots':
            let_go.wait(20)
        return real(store, name, given)

    monkeypatch.setattr(web_server, 'query_read', hung)
    served = web_server.Server('127.0.0.1', web, 'n')
    serving = threading.Thread(target=served.run, daemon=True)
    serving.start()
    try:
        begun = time.monotonic()
        status, body = api(web, '/api/roots?project=proj')
        assert status == 503 and time.monotonic() - begun < 3
        assert body['error'].endswith('it is waiting on the roots read of proj.') and body['next']
        status, health = api(web, '/api/health')
        assert status == 200 and health['ok'] and not health['supervised']
        assert health['slow']['route'] == 'GET /api/roots' and health['slow']['said'].startswith('waiting ')
        assert health['slowest'] == health['slow']
        time.sleep(1.5)
        status, health = api(web, '/api/health')
        assert status == 503 and health['stuck'] and not health['ok']
        let_go.set()
        deadline = time.monotonic() + 10
        while api(web, '/api/health')[1]['running'] and time.monotonic() < deadline:
            time.sleep(0.05)
        status, health = api(web, '/api/health')
        assert status == 200 and health['ok'] and health['slowest'] is None
        assert api(web, '/api/roots?project=proj')[0] == 200
    finally:
        let_go.set()
        served.shutdown()
        serving.join(10)


@pytest.mark.req('VIEW-002')
def test_a_read_stuck_past_its_deadline_ends_a_server_under_the_watchdog_saying_why_on_its_pipe(
        run, web, mapped, monkeypatch):
    """No one asks the server on a clock: its stuck read's own deadline ends it, and the watchdog hears why."""
    import select
    import threading

    from metaform.modules.web import server as web_server
    monkeypatch.setattr(web_server, 'READ_LIMIT', 0.3)
    monkeypatch.setattr(web_server, 'STUCK', 1.0)
    let_go, real, exited = threading.Event(), web_server.query_read, []

    def hung(store, name, given):
        if name == 'roots':
            let_go.wait(20)
        return real(store, name, given)

    monkeypatch.setattr(web_server, 'query_read', hung)
    monkeypatch.setattr(web_server.os, '_exit', exited.append)
    served = web_server.Server('127.0.0.1', web, 'n')
    reading, served.told = os.pipe()
    serving = threading.Thread(target=served.run, daemon=True)
    serving.start()
    try:
        assert api(web, '/api/roots?project=proj')[0] == 503
        assert select.select([reading], [], [], 10)[0], 'the server said nothing on its pipe at the deadline'
        with os.fdopen(reading, 'rb') as pipe:
            said = json.loads(pipe.readline())
        assert exited == [web_server.STUCK_EXIT]
        assert said['stuck'].startswith('GET /api/roots was stuck, waiting 1 s on the roots read of proj')
    finally:
        let_go.set()
        os.close(served.told)
        served.shutdown()
        serving.join(10)


@pytest.mark.req('VIEW-002')
def test_the_watchdog_wakes_on_its_servers_pipe_and_on_a_handed_over_servers_exit_never_on_a_clock(home):
    import importlib
    import threading

    module = importlib.import_module('metaform.modules.web.watchdog')  # the package's watchdog() hides the module
    keeper = module.Watchdog('127.0.0.1', free_port())
    cause = 'GET /api/roots was stuck, waiting 20 s on the roots read of proj'
    keeper.process = subprocess.Popen([sys.executable, '-c', f'import json; print(json.dumps({{"stuck": {cause!r}}}))'],
                                      stdout=subprocess.PIPE)
    keeper.pid = keeper.process.pid
    assert keeper.watch() == cause
    handed = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    keeper.process, keeper.pid = None, handed.pid
    threading.Timer(0.5, handed.kill).start()
    begun = time.monotonic()
    assert keeper.watch() == f'its process {handed.pid} ended'
    assert time.monotonic() - begun < 3
    handed.wait()


COUNT_HEALTH = """() => { window.healthAsked = 0; const real = window.fetch;
  window.fetch = (url, ...rest) => { if (String(url).startsWith('/api/health')) window.healthAsked++;
    return real(url, ...rest); }; }"""


@pytest.mark.req('VIEW-002')
def test_the_page_asks_the_servers_health_only_when_its_stream_says_the_server_went_and_came_back(
        run, web, mapped, browser):
    started(run)
    page = opened(browser, web)[0]
    time.sleep(1)  # the load's own asks have answered
    page.evaluate(COUNT_HEALTH)
    time.sleep(5)
    assert page.evaluate('window.healthAsked') == 0, 'the page asked the server its health on a clock'
    run('web', 'stop')
    page.wait_for_function("() => document.querySelector('#banners').textContent.includes('has not answered since')",
                           timeout=15000)
    assert page.evaluate('window.healthAsked') >= 1
    started(run)
    page.wait_for_function("() => document.querySelector('#banners').textContent.includes('server is back')",
                           timeout=20000)


@pytest.mark.req('VIEW-002')
def test_a_voice_model_download_pushes_what_has_arrived_to_the_open_pages_as_it_arrives(run, home, monkeypatch):
    """The page's download bar is drawn from what the server pushes as the bytes land, never by asking for status."""
    import io
    import urllib.request
    from types import SimpleNamespace

    import metaform.modules.web as package

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    pushed = []
    monkeypatch.setattr(package, 'SERVING', [SimpleNamespace(push=pushed.append)], raising=False)
    monkeypatch.setattr(urllib.request, 'urlopen', lambda request, timeout=None: Answer(b'x' * 10))
    run('voice', 'download', 'engine=browser', '--confirm', ok=False)  # 10 bytes is never a whole file: it stops there
    assert pushed, 'nothing was pushed to the open pages as the download ran'
    assert {event['topic'] for event in pushed} == {'voice.download'}
    assert pushed[0]['payload']['key'].startswith('browser:') and pushed[0]['payload']['done'] == 10


# Nothing in the web server, its watchdog, the page or the MCP views polls, VIEW-002 and VIEW-018: no interval, no check
# that sets its own timer again, no loop that sleeps, no sleep in the server's code. What waits on a clock is one of
# these, each with why it stays.
TIMED = re.compile(r'setInterval\(|setTimeout\((?:check|tick|poll)\b|for \(.*await new Promise\(\w+ => setTimeout')
TIMED_KEPT = {
    # the MCP views' reads on a host with no push, bridge.js poll(), only while on screen; a view's worker is refused
    # under MCP Apps' default content policy, so it cannot move off the view's main thread (its comment says why)
    ('mcp/resources/views/bridge.js', 'setTimeout(tick'),
    ('web/watchdog.py', 'time.sleep('),  # the pause before a server that keeps ending is started again, a backoff
}


@pytest.mark.req('VIEW-002')
def test_nothing_in_the_web_server_its_watchdog_the_page_or_the_views_waits_on_a_clock_to_see_a_change():
    modules = Path(__file__).resolve().parents[2]
    found = set()
    for folder in (modules / 'web' / 'page', modules / 'mcp' / 'resources' / 'views'):
        for path in sorted(folder.rglob('*')):
            if path.suffix not in ('.js', '.html') or 'vendor' in path.parts or path.name in ('ext-apps.js', 'map.html'):
                continue
            for hit in TIMED.finditer(path.read_text(encoding='utf-8')):
                said = 'a loop that sleeps' if hit.group(0).startswith('for') else hit.group(0)
                found.add((path.relative_to(modules).as_posix(), said))
    for path in sorted((modules / 'web').glob('*.py')):
        if 'time.sleep(' in path.read_text(encoding='utf-8'):
            found.add((path.relative_to(modules).as_posix(), 'time.sleep('))
    assert found == TIMED_KEPT


COUNT_READS = """() => { window.readsOf = {}; const real = window.fetch;
  window.fetch = (url, ...rest) => { const path = String(url).split('?')[0];
    window.readsOf[path] = (window.readsOf[path] || 0) + 1; return real(url, ...rest); }; }"""


@pytest.mark.req('VIEW-039')
@pytest.mark.req('STORE-005')
def test_session_reads_select_live_rows_before_hydrating_and_page_ended_history(run, web, mapped, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from urllib.parse import urlencode

    from metaform import module as chassis
    from metaform.data import Store, tables
    from metaform.modules.dispatch import carry_conversations, read_sessions, release, signals

    run('enable', 'dispatch')
    store = Store('proj', module='dispatch')
    current = datetime.now(UTC)
    stamp = lambda hours: (current - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%SZ')
    with store.tables() as tx:
        for number in range(105):
            sid = f'old-{number:03}'
            tx.insert('agent_sessions', {'session_id': sid, 'work_id': 'old-work', 'agent': 'claude',
                                         'state': 'ended', 'started': stamp(30), 'ended': stamp(2), 'seq': number})
            tx.insert('session_lines', {'session_id': sid, 'name': 'state', 'work_id': 'old-work',
                                        'kind': 'state', 'text': json.dumps({'commands': ['x' * 10000],
                                                                           'title': sid}), 'seq': 1})
        for sid, state, ended in [('waiting', 'waiting', ''), ('recent-end', 'ended', stamp(0.5)),
                                  ('long-run', 'running', '')]:
            tx.insert('agent_sessions', {'session_id': sid, 'work_id': 'current-work', 'agent': 'claude',
                                         'state': state, 'started': stamp(30), 'ended': ended, 'seq': 1000})
        tx.insert('session_lines', {'session_id': 'old-000', 'work_id': 'old-work', 'name': 'line:2',
                                    'kind': 'agent_message_chunk', 'text': 'Complete transcript.', 'seq': 2})
    # A long-running session belongs to the live hour after release, regardless of its old start time.
    release(store, 'current-work', 'claude long-run', False, 'long-run', 'finished')
    signals.record(store, 'stopped-open', work_id='empty-work')
    carry_conversations(store)
    executed = []
    original = tables.TableTx._execute

    def counted(tx, sql, params):
        if sql.startswith('SELECT'):
            executed.append((sql, params))
        return original(tx, sql, params)

    monkeypatch.setattr(tables.TableTx, '_execute', counted)
    ctx = chassis.context('dispatch', mapped, project='proj', nouns={'thread': False})
    live = read_sessions(ctx)
    assert {one['session_id'] for one in live['sessions']} == {'waiting', 'recent-end', 'long-run'}
    assert live['next'] and live['lines'] == []
    state_reads = [(sql, params) for sql, params in executed if 'FROM "dispatch.session_lines"' in sql]
    assert len(state_reads) == 1 and set(state_reads[0][1]) == {'state', 'waiting', 'recent-end', 'long-run'}
    assert all(' WHERE ' in sql for sql, _ in executed if 'FROM "dispatch.agent_sessions"' in sql)
    started(run, mapped)
    direct = api(web, '/api/dispatch-sessions?project=proj&thread=false')[1]
    assert {one['session_id'] for one in direct['sessions']} == {'waiting', 'recent-end', 'long-run'}
    cursor, seen = direct['next'], []
    while cursor:
        status, page = api(web, '/api/dispatch-sessions?' + urlencode({'project': 'proj', 'thread': 'false',
                                                                      'after': cursor, 'limit': 20}))
        assert status == 200 and len(page['sessions']) <= 20
        seen.extend(one['session_id'] for one in page['sessions'])
        cursor = page['next']
    assert seen == [f'old-{number:03}' for number in range(105)]
    detail = api(web, '/api/dispatch-sessions?project=proj&id=old-000')[1]
    assert [one['session_id'] for one in detail['sessions']] == ['old-000']
    assert detail['states']['old-000']['commands'] == ['x' * 10000]
    assert [one['text'] for one in detail['lines']] == ['Complete transcript.']
    scoped = api(web, '/api/dispatch-sessions?' + urlencode({'project': 'proj', 'thread': 'false',
                                                            'ids': json.dumps(['current-work'])}))[1]
    assert {one['session_id'] for one in scoped['sessions']} == {'waiting', 'recent-end', 'long-run'}
    scoped = api(web, '/api/dispatch-sessions?' + urlencode({'project': 'proj', 'thread': 'false',
                                                            'session_ids': json.dumps(['old-001'])}))[1]
    assert [one['session_id'] for one in scoped['sessions']] == ['old-001']
    assert api(web, '/api/dispatch-sessions?project=proj&ids=%7B%7D')[0] == 400
    assert api(web, '/api/dispatch-sessions?project=proj&after=invalid')[0] == 400
    assert api(web, '/api/dispatch-sessions?project=proj&history=true&limit=0')[0] == 400
    no_argument = api(web, '/api/dispatch-sessions?project=proj')[1]
    assert {one['session_id'] for one in no_argument['sessions']} == {'waiting', 'recent-end', 'long-run'}
    scoped = api(web, '/api/dispatch-sessions?' + urlencode({'project': 'proj', 'thread': 'false',
                                                            'ids': json.dumps(['empty-work'])}))[1]
    assert scoped['sessions'] == [] and [one['signal'] for one in scoped['signals']] == ['stopped-open']


@pytest.mark.req('VIEW-018')
def test_an_agents_thread_lines_read_no_session_again_and_a_change_to_its_session_reads_them(run, web, mapped, browser):
    """A handler acts on the events that concern it: a line of a thread no open chat shows reads nothing, a session's
    change reads the agents again."""
    from metaform import relay
    started(run)
    page = opened(browser, web)[0]
    time.sleep(2)  # the load's own reads have answered
    page.evaluate(COUNT_READS)
    line = {'project': 'proj', 'base_id': None, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines'],
            'work_ids': ['w1'], 'session_ids': ['s1'], 'kinds': ['line']}
    for _ in range(6):
        relay.deliver('map.changed', line)
        time.sleep(0.25)
    time.sleep(2)
    assert page.evaluate("window.readsOf['/api/dispatch-sessions'] || 0") == 0, 'a thread line read every session'
    relay.deliver('map.changed', {**line, 'dispatch_tables': ['dispatch.lines', 'dispatch.sessions'],
                                  'kinds': ['line', 'session']})
    page.wait_for_function("() => (window.readsOf['/api/dispatch-sessions'] || 0) >= 1")


@pytest.mark.req('BASE-053')
def test_a_page_opening_and_closing_its_stream_is_said_to_the_homes_other_processes_as_it_happens(
        run, web, mapped, monkeypatch):
    """A process waiting for a page, as the demo's agent does, hears it open and close, never asks."""
    import queue
    import threading

    from metaform.modules.web import server as web_server
    said = queue.Queue()
    monkeypatch.setattr(web_server.events, 'publish', lambda topic, payload, source: said.put((topic, payload)))
    served = web_server.Server('127.0.0.1', web, 'n')
    monkeypatch.setattr(served, 'schedule_dispatch', lambda *args, **kwargs: None)
    serving = threading.Thread(target=served.run, daemon=True)
    serving.start()
    try:
        connection = http.client.HTTPConnection('127.0.0.1', web, timeout=5)
        connection.request('GET', '/api/events?project=proj', headers={'Host': f'127.0.0.1:{web}'})
        assert connection.getresponse().status == 200
        topic, payload = said.get(timeout=5)
        assert topic == 'map.changed' and payload['kinds'] == ['pages'] and payload['pages'] == 1
        assert payload['tables'] == ['web.pages'] and payload['project'] == 'proj'
        connection.close()
        assert said.get(timeout=5)[1]['pages'] == 0, 'the closed page was not said as it closed'
    finally:
        served.shutdown()
        serving.join(10)


def health_after(port, pid, limit=20.0):
    """The first health answer of a server other than process `pid`, waiting out its restart."""
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        try:
            found = api(port, '/api/health')[1]
        except OSError:
            found = {}
        if found.get('pid') not in (None, pid):
            return found
        time.sleep(0.2)
    raise AssertionError(f'no other server answered within {limit} s')


@pytest.mark.req('VIEW-002')
def test_the_watchdog_starts_a_killed_server_again_and_stop_ends_both(run, home, web):
    import os
    import signal

    from metaform.modules import web as module
    started(run)
    record = json.loads((home / 'run' / 'web.json').read_text(encoding='utf-8'))
    kept = json.loads((home / 'run' / 'web-watchdog.json').read_text(encoding='utf-8'))
    assert kept['server'] == record['pid'] and kept['pid'] != record['pid']
    status, health = api(web, '/api/health')
    assert status == 200 and health['supervised'] and health['restarted'] is None
    os.kill(record['pid'], getattr(signal, 'SIGKILL', signal.SIGTERM))
    health = health_after(web, record['pid'])
    assert health['restarted']['count'] == 1 and f'its process {record["pid"]} ended' in health['restarted']['cause']
    assert f'starting the server again (1): its process {record["pid"]} ended' in \
        (home / 'run' / 'web.log').read_text(encoding='utf-8')
    assert run('web', 'stop').stdout == 'state: stopped\n'
    assert refused('127.0.0.1', web) and not (home / 'run' / 'web-watchdog.json').exists()

    def ended(pid):
        if os.name != 'nt':
            try:  # the watchdog is this process's child when the command ran in this process: reaped here
                return os.waitpid(pid, os.WNOHANG)[0] == pid
            except ChildProcessError:
                pass
        return not module.alive(pid)

    deadline = time.monotonic() + 10
    while not ended(kept['pid']) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert time.monotonic() < deadline, 'the watchdog still runs after web stop'


@pytest.mark.req('VIEW-002')
def test_a_restart_brings_the_page_back_when_the_process_that_asked_is_killed_right_after_the_stop(
        run, home, web, tmp_path):
    """`web restart` hands the stop and the start to a process of its own, so killing the asker and its process group
    the moment the old server has ended still leaves a new server answering."""
    import signal

    from metaform.modules import web as module
    started(run)
    record = json.loads((home / 'run' / 'web.json').read_text(encoding='utf-8'))
    stream = module.held_open(record)
    assert stream is not None
    asker = subprocess.Popen([sys.executable, '-m', 'metaform', 'web', 'restart'], cwd=tmp_path,
                             env={**os.environ, 'METAFORM_HOME': str(home)}, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    stream.read()  # returns as the old server's process ends: the stop has happened
    if os.name == 'nt':
        asker.kill()
    else:
        os.killpg(asker.pid, signal.SIGKILL)
    assert asker.wait(10) != 0, 'the restart finished before its asker was killed'
    health = health_after(web, record['pid'], limit=60)
    assert health['supervised']
    assert started(run)['state'] == 'running'


@pytest.mark.req('VIEW-002')
def test_a_restart_starts_a_server_when_none_runs_and_keeps_the_port_it_was_started_on(run, home, web):
    """With none running a restart is a start; with one running the new server listens where the old one was started,
    whatever the port setting says now, and the answer says an open page reconnects by itself."""
    first = json.loads(run('web', 'restart', '--json').stdout)
    assert first['state'] == 'started' and first['address'] == f'http://127.0.0.1:{web}/'
    old = json.loads((home / 'run' / 'web.json').read_text(encoding='utf-8'))['pid']
    run('set', f'--web-port={free_port()}')
    again = json.loads(run('web', 'restart', '--json').stdout)
    assert again['state'] == 'restarted' and again['address'] == f'http://127.0.0.1:{web}/'
    assert 'reconnects on its own' in again['pages']
    assert api(web, '/api/health')[1]['pid'] not in (None, old)
    run('set', f'--web-port={web}')  # the web fixture stops the server it set up


@pytest.mark.req('VIEW-002')
def test_a_page_open_through_a_restart_reconnects_to_the_new_server_and_is_told_its_code_changed(
        run, web, mapped, browser):
    """The page's stream reconnects to the restarted server on the same port by itself, and the new process runs the
    code on disk now: a Python file changed since the last start shows the page's 'Metaform was updated'."""
    import importlib

    restarter = importlib.import_module('metaform.modules.web.restart')  # the package's restart() hides the module
    run('set', '--web-notices')  # the notice is a banner only while web_notices is on
    started(run)
    page = opened(browser, web)[0]
    page.wait_for_function('() => window.metaform.loaded()')
    source = Path(restarter.__file__)
    kept = source.stat()
    os.utime(source, ns=(kept.st_atime_ns, kept.st_mtime_ns + 1_000_000_000))  # a code change, by its stamp
    try:
        assert json.loads(run('web', 'restart', '--json').stdout)['state'] == 'restarted'
    finally:
        os.utime(source, ns=(kept.st_atime_ns, kept.st_mtime_ns))
    page.wait_for_function("() => document.querySelector('#banners').textContent.includes('Metaform was updated')",
                           timeout=20000)


@pytest.mark.req('VIEW-002')
@pytest.mark.req('CLI-011')
def test_a_page_open_through_a_restart_starts_a_ticket_without_a_reload(run, web, mapped, browser):
    """An agent restarted the web GUI, 2026-10-21: the new process held none of the keys the old one gave its pages,
    so every write of the person's from an open page was refused until a reload. The stream the page reopens on the
    new process gives it a key of its own, and Start on a card is taken."""
    from metaform.data import Node, Store
    work = Store('proj').add_work(Node('element', 'exterior.cook'), None, task='Name the cook').id
    run('enable', 'dispatch')
    started(run)
    page = opened(browser, web)[0]  # its stream's refused reconnects while no server runs are in its console
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate("document.addEventListener('metaform:reconnected', () => { document.body.dataset.reconnected = 1 })")
    old = api(web, '/api/health')[1]['pid']
    assert json.loads(run('web', 'restart', '--json').stdout)['state'] == 'restarted'
    assert api(web, '/api/health')[1]['pid'] not in (None, old)
    page.wait_for_function('() => document.body.dataset.reconnected', timeout=20000)
    page.click('#boardBtn')
    page.click(f'#board .card[data-id="{work}"] button.start')
    page.wait_for_selector('#dispatch:not([hidden])')
    with page.expect_response(lambda response: '/api/dispatch-start' in response.url) as sent:
        page.click(f'#dispatch .ticket[data-id="{work}"] button.start')
    assert sent.value.status == 200, sent.value.text()
    assert sent.value.json()['work_id'] == work  # the start taken, the specialist then chosen for it


@pytest.mark.req('VIEW-002')
@pytest.mark.skipif(sys.platform == 'win32', reason='the hold tool runs on POSIX systems only')
def test_with_the_hold_tool_the_watchdog_is_placed_as_a_hold_call_and_says_it_listens_through_a_pipe(
        run, home, web, tmp_path, monkeypatch):
    """A stand-in for hold that records what it was asked and runs the call detached, as hold -d does."""
    asked = tmp_path / 'asked'
    tool = tmp_path / 'hold'
    tool.write_text(f'#!/bin/sh\necho "$@" >> {asked}\n[ "$1" = purge ] && exit 0\nshift 3\nshift\n'
                    'setsid "$@" </dev/null >/dev/null 2>&1 &\necho 0123abcd\n', encoding='utf-8')
    tool.chmod(0o755)
    monkeypatch.setenv('METAFORM_HOLD', str(tool))
    assert started(run)['state'] == 'started'
    said = asked.read_text(encoding='utf-8').splitlines()
    assert said[0] == f'purge metaform-web-{web}'
    # hold runs every path by its real path, so the watchdog's python, a link in a virtual environment, goes to the
    # shell in the environment
    assert said[1].startswith(f'--quiet --name metaform-web-{web} -d /bin/sh -c exec "$METAFORM_WATCHDOG_PYTHON" '
                              '"$@" sh -m metaform.modules.web.watchdog')
    assert '--ready' in said[1] and not list((home / 'run').glob('web-ready-*'))
    assert api(web, '/api/health')[1]['supervised']
    assert run('web', 'stop').stdout == 'state: stopped\n'
    assert asked.read_text(encoding='utf-8').splitlines()[-1] == f'purge metaform-web-{web}'  # no past call is left


# A question the person writes from the command line, MAP-050.
ASK_FORM = ('suggestions=["Yes", "No"]', 'by=builder', 'title=A check', 'why=The work waits on it')
PROVENANCE = {'module': 'test', 'workflow': 'fixture', 'prompt': 'Write the fixture.', 'model': 'none',
              'role': 'fixture writer', 'blinded': False}
KNOWLEDGE = ['notes', 'extra', 'secret']
TOGGLED = ['intake-1', *KNOWLEDGE]


def build(store):
    """An intake with a DE carrying a broken work record, the cook's join holding the DE and a tick loop;
    a knowledge layer on, one masked at code.alarm, one hidden; and a knowledge item orphaned when a refinement removes
    its element, VIEW-004 and LAYER-025."""
    from metaform.data import Node
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance=PROVENANCE, ready=True)
        store.add_element(intake.name, 'exterior.cook', name_length=1, role='CQU')
        store.add_element(intake.name, 'code.timer.kitchen', name_length=2, role='DE', name='dish timer')
        store.add_element(intake.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_element(intake.name, 'code.gone', name_length=1, role='SE')
        store.add_element(intake.name, 'code.loop.tick', name_length=2, role='SE', name='one-second tick')
        store.add_join(intake.name, 'exterior.cook', ['code.timer.kitchen', 'code.loop.tick'],
                       purpose='Know when food is done.', ef='Counts down and rings.')
        store.add_join(intake.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
    store.add_work(Node('element', 'code.timer.kitchen'), 'broken', note='drifts', task='hold the tick to one second')
    for name in KNOWLEDGE:
        store.layer(name, 'test', f'What {name} says.', mutable=True, hideable=True, provenance=PROVENANCE)
    store.add_element('notes', 'code.timer.kitchen.display', name_length=1)
    store.add_join('notes', 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='Show the time left.',
                   ef='Reports the time left.')
    store.add_item('notes', Node('element', 'code.timer.kitchen'), 'keep the loop small')
    store.add_item('notes', Node('element', 'code.gone'), 'the loop drifts here')
    store.add_element('extra', 'code.alarm.audible.loud', name_length=1)
    store.add_item('extra', Node('element', 'code.alarm.audible'), 'louder is better')
    store.add_element('secret', 'code.secret', name_length=1)
    for name in KNOWLEDGE:
        store.finish(name)
    store.mask('code.alarm', 'extra')
    store.hide('secret')
    store.refine(store.element('code.gone').id, remove=True, reason='It is not there.')


@pytest.fixture
def mapped(run, home, tmp_path):
    from metaform.data import Store
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    build(Store('proj'))
    run('set', '--layers', ','.join(TOGGLED), cwd=folder)
    return folder


def api(port, path, **given):
    status, body, _ = request(port, path, **given)
    return status, json.loads(body)


def plain(result):
    from metaform import results
    return json.loads(results.as_json(result))


@pytest.mark.req('VIEW-004')
def test_each_read_endpoint_returns_what_its_store_read_returns_in_context_and_raw(run, web, mapped):
    from metaform.data import Node, Store
    started(run)
    store = Store('proj', toggled=TOGGLED)
    kitchen = Node('element', 'code.timer.kitchen')
    reads = {
        '/api/roots': lambda raw: store.roots(raw=raw),
        '/api/children?address=code': lambda raw: store.children('code'),
        '/api/children?address=': lambda raw: store.children(''),
        '/api/node?target=element:code.timer.kitchen': lambda raw: store.node(kitchen, raw=raw),
        '/api/node?target=element:code.alarm.audible': lambda raw: store.node(Node('element', 'code.alarm.audible'),
                                                                            raw=raw),
        '/api/joins?element=code.timer.kitchen': lambda raw: store.joins('code.timer.kitchen', raw=raw),
        '/api/joins?element=code.timer.kitchen&as=provider':
            lambda raw: store.joins('code.timer.kitchen', as_='provider', raw=raw),
        '/api/layers': lambda raw: store.layers(),
        '/api/work': lambda raw: store.work(),
        '/api/work?node=element:code.timer.kitchen': lambda raw: store.work(node=kitchen),
        '/api/search?text=loop': lambda raw: store.search('loop'),
        '/api/provenance?layer=notes': lambda raw: store.provenance('notes'),
        '/api/bases': lambda raw: store.bases(),
        '/api/layer-items?layer=notes': lambda raw: store.layer_items('notes'),
    }
    for path, read in reads.items():
        for raw in (False, True):
            url = path + ('&' if '?' in path else '?') + 'project=proj' + ('&raw=true' if raw else '')
            status, body = api(web, url)
            assert status == 200 and body == plain(read(raw)), url
    gone = '/api/node?project=proj&target=element:code.gone'
    assert api(web, gone)[0] == 404 and api(web, gone + '&raw=true')[0] == 404
    items = api(web, '/api/layer-items?project=proj&layer=notes')[1]['results']
    assert [item['orphaned'] for item in items if item['value'] == 'the loop drifts here'] == [True]
    masked = api(web, '/api/node?project=proj&target=element:code.alarm.audible')[1]
    assert 'extra' not in [group['layer'] for group in masked['layers']]
    assert 'extra' in [group['layer'] for group in api(web, '/api/node?project=proj&raw=true&'
                                                            'target=element:code.alarm.audible')[1]['layers']]
    status, body = api(web, '/api/node?project=proj&target=element:code.timer.kitchen&layers=notes')
    assert body == plain(Store('proj', toggled=['notes']).node(kitchen))
    assert body != api(web, '/api/node?project=proj&target=element:code.timer.kitchen&layers=intake-1')[1]
    assert api(web, '/api/roots?project=nobody')[0] == 404


@pytest.mark.req('VIEW-004')
def test_the_page_data_for_a_node_is_what_map_node_returns(run, web, mapped):
    from metaform.data import Store
    started(run)
    store = Store('proj')
    held = store.joins('exterior.cook').results[0].id
    for node in ('element:code.timer.kitchen', 'element:exterior.cook', f'join:{held}', 'element:code.loop.tick'):
        cli = json.loads(run('map', 'node', node, '--json', cwd=mapped).stdout)
        assert api(web, f'/api/node?project=proj&target={node}') == (200, cli)


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-010')
def test_the_graph_pages_every_visible_element_and_join_once_with_its_nearest_parent_element(run, web, mapped):
    started(run)
    elements, joins, cursor, pages = [], [], None, 0
    while True:
        status, page = api(web, '/api/graph?project=proj&limit=2' + (f'&after={cursor}' if cursor else ''))
        assert status == 200
        elements += page['elements']
        joins += page['joins']
        pages += 1
        cursor = page['next']
        if cursor is None:
            break
    assert pages > 1
    parents = {element['element']['address']: element['parent'] for element in elements}
    assert len(parents) == len(elements)
    assert parents == {'exterior.cook': None, 'code.timer.kitchen': None, 'code.alarm.audible': None,
                       'code.loop.tick': None, 'code.timer.kitchen.display': 'code.timer.kitchen'}
    # Each join once, with the elements it holds.
    held = sorted((join['receiver_address'], [each['address'] for each in join['elements']]) for join in joins)
    assert held == [('code.timer.kitchen', ['code.alarm.audible']),
                    ('code.timer.kitchen.display', ['code.timer.kitchen']),
                    ('exterior.cook', ['code.timer.kitchen', 'code.loop.tick'])]
    raw = api(web, '/api/graph?project=proj&raw=true&limit=0')[1]
    shown = {entry['element']['address'] for entry in raw['elements']}
    assert {'code.alarm.audible.loud', 'code.secret'} <= shown and 'code.gone' not in shown


@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('VIEW-002')
def test_reading_changes_nothing_and_applying_layers_is_a_write_only_from_the_gui_itself(run, home, web, mapped):
    remember(run, mapped, 'create_entities', [entity('drift', 'Drifts under load.')], 'element:code.timer.kitchen')
    from tests.storekit import page_note
    page_note('proj', 'element:code.timer.kitchen', 'Keep the loop small.')  # the person's note, VIEW-034
    started(run)
    stores = sorted((home / 'projects').rglob('*.sqlite3')) + [home / 'metaform.sqlite3']
    assert any(path.name == 'memory.sqlite3' for path in stores)  # the memory module's store, with rows, is read too
    before = [path.read_bytes() for path in stores]
    shown = run('config', '--show', '--json', cwd=mapped).stdout
    for path in ('/api/projects', '/api/bases?project=proj', '/api/roots?project=proj',
                 '/api/graph?project=proj&limit=0', '/api/graph?project=proj&raw=true&layers=notes',
                 '/api/children?project=proj&address=code', '/api/node?project=proj&target=element:code.timer.kitchen',
                 '/api/joins?project=proj&element=code.timer.kitchen', '/api/layers?project=proj',
                 '/api/work?project=proj', '/api/search?project=proj&text=loop',
                 '/api/provenance?project=proj&layer=notes', '/api/memory-graph?project=proj',
                 '/api/memory-orphaned?project=proj', '/api/memory-note?project=proj&node=element:code.timer.kitchen'):
        assert request(web, path)[0] == 200, path
    assert sorted((home / 'projects').rglob('*.sqlite3')) + [home / 'metaform.sqlite3'] == stores
    assert [path.read_bytes() for path in stores] == before
    assert run('config', '--show', '--json', cwd=mapped).stdout == shown
    own = f'http://127.0.0.1:{web}'
    body = json.dumps({'project': 'proj', 'layers': ['notes']})
    as_json = {'Content-Type': 'application/json'}
    assert request(web, '/api/apply-layers', method='POST', body=body, headers=as_json)[0] == 403
    assert request(web, '/api/apply-layers', method='POST', body=body,
                   headers={**as_json, 'Origin': 'http://rebound.example'})[0] == 403
    assert request(web, '/api/apply-layers', method='POST', body=body,
                   headers={'Origin': own, 'Content-Type': 'text/plain'})[0] == 415
    assert run('config', '--show', '--json', cwd=mapped).stdout == shown
    status, answer = api(web, '/api/apply-layers', method='POST', body=body, headers={**as_json, 'Origin': own})
    assert status == 200 and answer['layers'] == ['notes']
    layers = next(row for row in json.loads(run('config', '--show', '--json', cwd=mapped).stdout)
                  if row['key'] == 'layers')
    assert layers['value'] == ['notes']
    for method in ('PUT', 'PATCH', 'DELETE'):
        assert request(web, '/api/apply-layers', method=method, body=body, headers={**as_json, 'Origin': own})[0] == 501
    assert request(web, '/api/other', method='POST', body=body, headers={**as_json, 'Origin': own})[0] == 404


@pytest.mark.req('VIEW-002')
def test_whether_a_person_came_new_and_closed_the_welcome_is_kept_in_the_home_for_that_person(run, home, web):
    """The page keeps whether a person came new, and that they closed the welcome, in the home, so a welcome closed in
    one browser stays gone in every one. Only the page itself may write it, and nothing brings it back."""
    started(run)
    own = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'}
    assert api(web, '/api/hints')[1] == {'dismissed': []}
    for name in ('newcomer', 'welcome', 'welcome'):
        assert request(web, '/api/hints', method='POST', body=json.dumps({'hint': name}), headers=own)[0] == 200
    assert request(web, '/api/hints', method='POST', body=json.dumps({'hint': '../x'}), headers=own)[0] == 400
    assert request(web, '/api/hints', method='POST', body=json.dumps({'hint': 'welcome'}),
                   headers={'Content-Type': 'application/json'})[0] == 403  # only from the page itself
    assert request(web, '/api/hints', method='POST', body=json.dumps({'again': True}), headers=own)[0] == 400
    assert api(web, '/api/hints')[1] == {'dismissed': ['newcomer', 'welcome']}
    assert json.loads((home / 'web' / 'hints.json').read_text()) == {'': ['newcomer', 'welcome']}


NAMESPACES = ('http://www.w3.org/2000/svg',)  # a namespace name the script uses to make SVG nodes, never fetched


@pytest.mark.req('VIEW-003')
def test_the_page_loads_only_the_servers_own_files(run, web):
    import re
    started(run)
    import base64
    import hashlib
    status, page, headers = request(web, '/')
    policy = headers['Content-Security-Policy']
    assert status == 200 and policy.startswith("default-src 'self'")
    # The one inline script is the import map, allowed by its hash; no other inline script runs.
    inline = re.findall(r'<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>', page, re.DOTALL)
    assert [attributes.strip() for attributes, _ in inline] == ['type="importmap"']
    digest = base64.b64encode(hashlib.sha256(inline[0][1].encode('utf-8')).digest()).decode()
    script = next(part.strip() for part in policy.split(';') if part.strip().startswith('script-src'))
    assert script.split() == ['script-src', "'self'", "'wasm-unsafe-eval'", f"'sha256-{digest}'"]
    imports = json.loads(inline[0][1])['imports']
    from metaform.modules.web import server
    version = server.vendor_version()  # the libraries are named at /vendor/v-<version>/
    assert imports['three'] == f'/vendor/{version}/three.module.min.js'
    assert imports['three/addons/'] == imports['three/examples/jsm/'] == f'/vendor/{version}/three-addons/'
    assert all(path.startswith('/') and not path.startswith('//') for path in imports.values())
    loaded_modules = [path for path in imports.values() if not path.endswith('/')]
    for path in loaded_modules:
        status, _, headers = request(web, path)
        assert status == 200 and headers['Content-Type'].startswith('text/javascript'), path
    loaded = re.findall(r'(?:src|href)="([^"]+)"', page)
    assert loaded and all(path.startswith('/') and not path.startswith('//') for path in loaded)
    texts = [page]
    loaded.append('/page/agents3d.js')                                # imported by the page's own script, VIEW-035
    for path in loaded:
        status, body, headers = request(web, path)
        assert status == 200, path
        if path.startswith('/page/'):
            texts.append(body)
        if path.endswith('.js'):
            assert headers['Content-Type'].startswith('text/javascript'), path
    remote = [found for text in texts for found in re.findall(r'(?:https?:)?//[\w.-]+\.[a-z]{2,}[^\s"\')]*', text)
              if not found.startswith(NAMESPACES)]
    assert remote == []
    fonts = re.findall(r'url\((/vendor/[^)]+)\)', next(text for text in texts if '@font-face' in text))
    assert fonts and all(request(web, font)[0] == 200 for font in fonts)


@pytest.mark.req('VIEW-003')
def test_the_wheel_carries_the_page_and_every_vendor_file_with_its_license(run, home):
    import zipfile
    from pathlib import Path
    folder = Path(__file__).parents[1]
    built = run('build').stdout
    wheel = Path(next(line.split(':', 1)[1].strip() for line in built.splitlines() if line.startswith('Wheel:')))
    names = set(zipfile.ZipFile(wheel).namelist())
    shipped = [path.relative_to(folder).as_posix() for part in ('page', 'vendor')
               for path in (folder / part).rglob('*') if path.is_file()]
    assert shipped and {f'metaform/modules/web/{name}' for name in shipped} <= names
    licenses = ['mermaid.LICENSE', 'mermaid.THIRD-PARTY.LICENSE', '3d-force-graph.LICENSE', 'three.LICENSE', 'fonts/IBM-Plex.LICENSE',
                'codemirror/LICENSE', 'drei-vanilla/LICENSE']
    assert all(f'metaform/modules/web/vendor/{license}' in names for license in licenses)


def test_voice_status_always_answers_and_the_voice_endpoints_take_only_the_pages_own_audio(run, web, home):
    started(run)
    own = {'Origin': f'http://127.0.0.1:{web}'}
    status, body, _ = request(web, '/api/voice/status')
    assert status == 200 and json.loads(body)['available'] is True and json.loads(body)['engine'] != ''
    assert request(web, '/api/voice/transcribe', method='POST', body='hi', headers={**own, 'Content-Type': 'text/plain'})[0] == 415
    assert request(web, '/api/voice/transcribe', method='POST', body='RIFF', headers={'Content-Type': 'audio/wav'})[0] == 403
    assert request(web, '/api/voice/files/..%2f..%2frun/web.json')[0] == 404
    said = json.dumps({'text': 'Whisper could not hear that audio:\nlibcublas.so.12 is not found'})
    assert request(web, '/api/voice/note', method='POST', body=said, headers={'Content-Type': 'application/json'})[0] == 403
    assert request(web, '/api/voice/note', method='POST', body=said, headers={**own, 'Content-Type': 'application/json'})[0] == 200
    log = (home / 'run' / 'web.log').read_text(encoding='utf-8')
    assert 'voice note: Whisper could not hear that audio: libcublas.so.12 is not found' in log
    run('disable', 'voice')
    status, body, _ = request(web, '/api/voice/status')  # off is a state the page shows, never a failed request
    assert status == 200 and json.loads(body)['available'] is False and 'metaform enable voice' in body


RETURNING = ("try { if (localStorage.getItem('metaform.hints') === null) localStorage.setItem('metaform.hints', "
             "'[\"returning\"]') } catch (error) {}")


@pytest.fixture
def browser():
    """Headless Chromium through Playwright, a dev dependency; WebGL runs in software, VIEW-012."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        launched = driver.chromium.launch(executable_path=os.environ.get('METAFORM_CHROMIUM') or None, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                                                '--ignore-gpu-blocklist'])
        new_page = launched.new_page

        def quick(*args, **kwargs):  # a wait that is not met fails in 10 seconds, not Playwright's 30
            page = new_page(*args, **kwargs)
            page.set_default_timeout(10_000)
            # a person who has used the page before, so no first-time welcome comes; the welcome's check opens a page
            # of its own without this, `newcomer`
            page.add_init_script(RETURNING)
            return page
        launched.new_page = quick
        yield launched
        launched.close()


def opened(browser, port, clock=False, plain=False):
    """The page open on the project; with `clock`, on Playwright's clock, which runs as time does until a test holds
    it and steps it; with `plain`, in a plain theme, Black, where the 3D map is drawn clean, glass in the page's own
    light, rather than in Space, the theme it opens in, where outer space draws it."""
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    if clock:
        page.clock.install()
    # the checks are written with the 3D map in the large area, as the page opened before the 2D map took it, VIEW-028;
    # a choice a check makes is kept through its reloads
    page.add_init_script("try { if (localStorage.getItem('metaform.swapped') === null) localStorage.setItem('metaform.swapped', '') } catch (error) {}")
    if plain:
        page.add_init_script("try { if (localStorage.getItem('metaform.theme') === null) localStorage.setItem('metaform.theme', 'black') } catch (error) {}")
    own = f'http://127.0.0.1:{port}/'
    problems, remote = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda sent: None if sent.url.startswith((own, 'data:', 'blob:')) else remote.append(sent.url))
    page.goto(own + '#p=proj')
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    try:
        page.wait_for_function('() => window.metaform && document.querySelectorAll("#map2d svg g.node").length > 0',
                               timeout=90000)  # the first draw, which parallel browsers rendering in software slow
    except PlaywrightTimeoutError:  # what the page said as it failed to draw is the cause, not the wait
        pytest.fail(f'The first draw never came: {problems}, ready: {page.evaluate("document.readyState")}, '
                    f'metaform: {page.evaluate("Boolean(window.metaform)")}')
    return page, problems, remote


def choose_agent(page, where, agent):
    """Choose an agent in the agent picker inside `where`, as a person does: open its list and click the agent,
    VIEW-039."""
    page.click(f'{where} .agentpicker .choice > .btn')
    page.click(f'.listbox:not([hidden]) [role="option"][data-value="{agent}"]')
    page.wait_for_function('([where, agent]) => document.querySelector(`${where} .agentpicker .choice > .btn .lbl`)'
                           '.textContent === window.metaform.harnesses().agents.find(one => one.agent === agent).label',
                           arg=[where, agent])


def set_layer(page, name, on):
    """Tick or untick a layer in the header's Layers list, opening the list first when it is closed."""
    if not page.is_visible('#layerlist'):
        page.click('#layersBtn')
    page.set_checked(f'#layerlist input[data-layer="{name}"]', on)


def pick_theme(page, name):
    """Choose a theme in the header's view settings, opening them first when they are closed."""
    if not page.is_visible('#settingsbox'):
        page.click('#settingsBtn')
    page.select_option('#theme', name)


def config_layers(run, folder):
    return next(row for row in json.loads(run('config', '--show', '--json', cwd=folder).stdout)
                if row['key'] == 'layers')['value']


def drawn_as_paths(graph, expected):
    """The page's graph against the store's: one vertex per element and none for a join, each join an edge from its
    receiver to each element it holds, with nothing back to the receiver, MAP-002 and the Join rule (Rich,
    2026-10-17), and each element's namespace edge from its nearest parent element, VIEW-005, where no join's edge
    already joins the two."""
    elements = {entry['element']['id'] for entry in expected['elements']}
    by_address = {entry['element']['address']: entry['element']['id'] for entry in expected['elements']}
    links = graph['links']
    assert sorted(node['id'] for node in graph['nodes'] if node['t'] == 'el') == sorted(elements)
    by_join = {}
    for link in links:
        if link.get('join'):
            by_join.setdefault(link['join'], []).append((link['source'], link['target'], link['k']))
    joined = set()
    for join in expected['joins']:
        assert sorted(by_join.pop(join['id'])) == sorted(
            (join['receiver'], each['element_id'], 'encounter') for each in join['elements'])
        joined |= {frozenset((join['receiver'], each['element_id'])) for each in join['elements']}
    assert by_join == {}
    assert sorted((link['source'], link['target']) for link in links if link['k'] == 'tree') == sorted(
        (by_address[entry['parent']], entry['element']['id']) for entry in expected['elements']
        if entry['parent'] and frozenset((by_address[entry['parent']], entry['element']['id'])) not in joined)
    assert not [node for node in graph['nodes'] if node['t'] == 'purpose']


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-003')
@pytest.mark.req('VIEW-012')
def test_the_page_draws_each_join_as_its_path_and_both_views_select_together(run, web, mapped, browser):
    started(run)
    page, problems, remote = opened(browser, web)
    graph = page.evaluate('window.metaform.graph()')
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    elements = {entry['element']['id'] for entry in expected['elements']}
    drawn_as_paths(graph, expected)
    page.wait_for_function('([count]) => window.metaform.labels3d().filter(label => !label.hidden).length === count',
                           arg=[len(elements)])
    # an element's label is its name, or else its short name
    names = {entry['element'].get('name') or entry['element'].get('short_name') or entry['element']['address']
             for entry in expected['elements']}
    assert {label['text'] for label in page.evaluate('window.metaform.labels3d()')} == names
    assert page.locator('#map2d svg g.node').count() == len(elements)
    # one edge from a join's receiver to each element it holds
    assert page.locator('#map2d svg .edgePaths path').count() == sum(len(join['elements']) for join in expected['joins'])
    assert page.evaluate('[...document.querySelectorAll("#map2d svg .edgeLabel")].map(e => e.textContent.trim())'
                         '.filter(Boolean)') == []
    alarm = next(entry['element'] for entry in expected['elements'] if entry['element']['address'] == 'code.alarm.audible')
    page.evaluate(f'window.metaform.select("{alarm["id"]}")')
    assert page.evaluate('[...document.querySelectorAll("#map2d svg g.node.sel")].map(g => g.dataset.title)') == [
        'code.alarm.audible']
    page.evaluate('[...document.querySelectorAll("#map2d svg g.node")].find(g => g.dataset.title '
                  '=== "exterior.cook").dispatchEvent(new MouseEvent("click", {bubbles: true}))')
    cook = next(entry['element'] for entry in expected['elements'] if entry['element']['address'] == 'exterior.cook')
    assert page.evaluate('window.metaform.selected()') == cook['id']
    assert page.text_content('#p-object h2') == 'cook'
    page.evaluate('window.metaform.fit()')
    page.wait_for_timeout(300)
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-008')
def test_the_layers_list_opens_from_the_header_and_the_2d_map_fills_its_area_with_no_bar(run, web, mapped, browser):
    """The layers are chosen with checkboxes from a Layers button at the top right of the header; the 2D map has no
    bar: its drawing fills its area to the top, and back and forward are Alt with Left and Right."""
    started(run)
    page, problems, _ = opened(browser, web)
    width = page.viewport_size['width']
    button = page.locator('#layersBtn').bounding_box()
    header = page.locator('header').bounding_box()
    assert button['x'] + button['width'] > width - 260 and button['y'] < header['y'] + header['height']
    assert not page.is_visible('#layerlist')
    page.click('#layersBtn')
    listed = page.locator('#layerlist').bounding_box()
    assert listed['y'] >= button['y'] + button['height'] - 1 and listed['x'] < button['x'] + button['width']
    rows = page.evaluate("""[...document.querySelectorAll('#layerlist .layerrow')].map(row => ({
        text: row.textContent, checked: row.querySelector('input').checked, disabled: row.querySelector('input').disabled}))""")
    by_name = {row['text'].split()[0]: row for row in rows}
    assert by_name['notes']['checked'] and not by_name['notes']['disabled'] and 'layer' in by_name['notes']['text']
    assert by_name['secret']['disabled'] and 'hidden' in by_name['secret']['text']
    assert sorted(by_name) == ['downstream', 'extra', 'intake-1', 'notes', 'secret', 'upstream']  # the roots are toggles beside the layers  # nothing about refinements, LAYER-025
    assert page.is_visible('#layerlist #apply')
    page.keyboard.press('Escape')
    assert not page.is_visible('#layerlist')
    page.evaluate('() => { const svg = document.querySelector("#map2d svg"); svg.setAttribute("viewBox", "-400 -400 1600 1600"); }')
    assert page.evaluate("document.querySelectorAll('.bar2d, .bar3d, #backBtn, #swapBtn, .peekpart').length") == 0
    area, viewport = page.locator('#map2d').bounding_box(), page.locator('#viewport').bounding_box()
    assert viewport['y'] == pytest.approx(area['y'], abs=1) and viewport['height'] == pytest.approx(area['height'], abs=1)
    assert problems == []


@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-012')
def test_toggling_layers_in_the_page_changes_only_the_view_until_apply(run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    before = config_layers(run, mapped)
    assert page.inner_text('#layersBtn') == 'Layers · 3 of 4'  # secret is hidden, so it cannot be on
    set_layer(page, 'notes', False)
    page.wait_for_function('() => !document.querySelector("#apply").disabled')
    assert not page.is_checked('#layerlist input[data-layer="notes"]')
    assert page.inner_text('#layersBtn') == 'Layers · 2 of 4'
    page.wait_for_timeout(1000)
    assert config_layers(run, mapped) == before
    assert 'display' not in page.evaluate('window.metaform.graph().nodes.map(n => n.name)')
    page.click('#apply')
    page.wait_for_function('() => document.querySelector("#apply").disabled')
    assert set(config_layers(run, mapped)) == {'intake-1', 'extra'}
    assert problems == []


def remove(port, layer, headers=None):
    body = json.dumps({'project': 'proj', 'layer': layer})
    return api(port, '/api/remove-correction', method='POST', body=body,
               headers=headers or {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}'})


@pytest.mark.req('LAYER-025')
@pytest.mark.req('VIEW-006')
@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-012')
def test_a_refined_join_is_drawn_as_the_metaform_is_and_the_page_offers_no_correction_layers(run, web, mapped, browser):
    """Refinements should not be changing things' colors, and need not be in layer select."""
    from metaform.data import Store
    held = Store('proj').joins('code.timer.kitchen').results[0]
    join = held.id
    named = (f'receiver={held.receiver_address}', f'provider={held.elements[0].address}')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    colors = lambda shown: sorted((link['k'], link['color'].lower()) for link in
                                  shown.evaluate('window.metaform.linkColors()') if link['join'] == join)
    before = colors(page)
    assert before
    run('map', 'refine', *named, 'purpose=Ring when the countdown ends.', 'reason=wording',
        cwd=mapped)
    run('map', 'refine', *named, 'ef=Plays a loud tone.', 'reason=louder', cwd=mapped)
    again, again_problems, _ = opened(browser, web)
    again.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    assert colors(again) == before
    # the join's edges keep its layer, a join having no node of its own
    assert again.evaluate(f'window.metaform.graph().links.find(link => link.join === "{join}").layer') == 'intake-1'
    again.click('#layersBtn')
    rows = again.evaluate("[...document.querySelectorAll('#layerlist .layerrow .name')].map(name => name.textContent)")
    assert sorted(rows) == ['downstream', 'extra', 'intake-1', 'notes', 'secret', 'upstream']  # roots as toggles
    assert again.locator('#t-corr').count() == 0 and again.locator('#p-corr').count() == 0
    assert remove(web, 'intake-1')[0] == 404  # the page's write that removed a correction layer is gone
    assert problems == [] and again_problems == []


@pytest.mark.req('VIEW-009')
@pytest.mark.req('VIEW-012')
def test_the_panel_shows_everything_about_the_selected_element_with_its_layers(run, web, mapped, browser):
    from metaform.data import Node, Store
    store = Store('proj')
    store.add_property('notes', 'code.timer.kitchen', 'written in C')
    remembered = store.layer('memory', 'memory', 'What agents noted.', kind='memory', mutable=True, hideable=True,
                             ready=True)
    store.add_item(remembered.name, Node('element', 'code.timer.kitchen'), 'drifts under load')
    challenged = store.add_item('notes', Node('element', 'code.timer.kitchen'), 'Nothing recovers a hung loop.')
    store.answer(challenged.id, 'A')
    run('set', '--layers', ','.join([*TOGGLED, 'memory']), cwd=mapped)
    started(run)
    page, problems, _ = opened(browser, web)
    kitchen = store.element('code.timer.kitchen').id
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("written in C")')
    # the joins and the knowledge fold closed under a line with their count; opened, they show every record
    assert page.evaluate('[...document.querySelectorAll("#p-object details.fold")].every(fold => !fold.open)')
    page.evaluate('document.querySelectorAll("#p-object details").forEach(fold => { fold.open = true; })')
    panel = page.inner_text('#p-object')
    for shown in ('kitchen timer', 'code.timer.kitchen', 'DE', 'intake-1',
                  'provider · audible alarm', 'receiver · cook', 'receiver · display',
                  'MEMORIES', 'drifts under load', 'Nothing recovers a hung loop. · A', 'written in C', 'notes'):
        assert shown in panel, shown
    assert panel.index('MEMORIES') < panel.index('OPEN WORK') < panel.index('JOINS') < panel.index('KNOWLEDGE')
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-009')
@pytest.mark.req('VIEW-027')
@pytest.mark.req('MAP-046')
def test_a_node_with_open_unbuilt_work_is_a_ghost_a_broken_one_flashes_red_until_resolved_and_the_panel_lists_the_records(
        run, web, mapped, browser):
    """A part not built is a ghost, its own node three quarters clear, which is the one mark of it, VIEW-027; the agent
    that completes its task makes it solid; a node with an open issue flashes red; a part with a plain task carries no
    mark. The fixture's kitchen timer carries an open broken record."""
    from metaform.data import Node, Store
    store = Store('proj')
    missing = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', note='in the spec', task='build the piezo driver')
    store.add_work(Node('element', 'exterior.cook'), None, task='name the cook')  # a plain task marks nothing
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.loaded()')
    ids = {address: store.element(address).id for address in ('code.alarm.audible', 'code.timer.kitchen', 'exterior.cook')}
    look = lambda address: page.evaluate(f'window.metaform.look("{ids[address]}")')
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").ghost === true', timeout=5000)
    alarm = look('code.alarm.audible')
    # A part not built yet keeps its own color. In 3D it is a ghost of its glass node, a quarter seen, with nothing
    # around it; in 2D a glow around it marks it.
    assert alarm['around3d'] == 0 and alarm['material'] == 'MeshTransmissionMaterial'
    assert (alarm['work'], alarm['classes'], alarm['opacity2d'], alarm['animated2d']) == (['unbuilt'], ['work-unbuilt'], 1, False)
    assert alarm['opacity3d'] == pytest.approx(0.25)
    assert alarm['color3d'] == page.evaluate('window.metaform.own(' + json.dumps(ids['code.alarm.audible']) + ')')
    assert alarm['bloom2d'] is True and alarm['label3d'] == ['work-unbuilt']
    assert look('exterior.cook')['around3d'] == 0 and look('exterior.cook')['bloom2d'] is False
    assert look('code.timer.kitchen')['label3d'] == ['work-broken']
    cook = look('exterior.cook')
    assert (cook['work'], cook['classes'], cook['red3d']) == ([], [], False)
    kitchen = look('code.timer.kitchen')
    assert (kitchen['work'], kitchen['classes'], kitchen['opacity2d'], kitchen['animated2d']) == (['broken'], ['work-broken'], 1, True)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.timer.kitchen"]}").red3d === true', timeout=3000)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.timer.kitchen"]}").red3d === false', timeout=3000)
    legend = page.inner_text('#legend')
    assert 'part: unbuilt' in legend and 'part: broken' in legend and 'waiting' not in legend
    # The panel lists the selected node's work records.
    page.evaluate(f'window.metaform.select("{ids["code.timer.kitchen"]}")')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("hold the tick to one second")')
    panel = page.inner_text('#p-object')
    # one line per ticket, its condition, kind, number and title; the note is read by opening it
    for shown in ('OPEN WORK', 'broken', 'code.timer.kitchen#', 'hold the tick to one second'):
        assert shown in panel, shown
    assert 'drifts' not in panel
    # Its task done, pushed to the page, the alarm turns solid without a reload.
    run('map', 'work', 'op=done', f'id={missing.id}', 'resolution=driver written', 'why=the test closes it', cwd=mapped)
    # solid glass, as every built element, once its ghost has come up to it
    page.wait_for_function(f'() => !window.metaform.look("{ids["code.alarm.audible"]}").ghost'
                           f' && window.metaform.look("{ids["code.alarm.audible"]}").opacity3d >= 0.99', timeout=30000)
    assert look('code.alarm.audible')['material'] == 'MeshTransmissionMaterial'
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").bloom2d === false', timeout=5000)
    solid = look('code.alarm.audible')
    assert (solid['work'], solid['classes'], solid['opacity2d']) == ([], [], 1)
    page.evaluate(f'window.metaform.select("{ids["code.alarm.audible"]}")')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("Past work · 1")')
    assert 'build the piezo driver' not in page.inner_text('#p-object')  # done work stays folded until opened
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-027')
@pytest.mark.req('MAP-046')
def test_a_join_that_is_not_built_yet_is_marked_in_both_views(run, web, mapped, browser):
    """An open missing record on a join shows on its receiving element in 3D, the join having no node of its own:
    the receiver is a ghost, VIEW-027 and the Join rule (Rich, 2026-10-17); and its edge has a glow in 2D, with its
    color and opacity as they are."""
    from metaform.data import Node, Store
    store = Store('proj')
    joins = list(store.joins('code.timer.kitchen').results)
    store.add_work(Node('join', joins[0].id), 'unbuilt', task='build it')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    links = page.evaluate('window.metaform.linkColors()')
    assert not any(link['color'].startswith('rgba(') for link in links)  # its links keep their color and opacity
    receiver = store.element('code.timer.kitchen').id
    page.wait_for_function(f'() => window.metaform.look("{receiver}").ghost === true', timeout=5000)
    assert page.evaluate(f'window.metaform.look("p:{joins[0].id}").ghost') is True  # a join's key, its receiver
    assert 'unbuilt' in page.evaluate(f'window.metaform.look("{receiver}").work')  # beside its own broken record
    other = store.element('code.alarm.audible').id
    assert page.evaluate(f'window.metaform.look("{other}").ghost') is False
    assert page.evaluate(f'window.metaform.edge2d("{joins[0].id}")') == ['work-unbuilt']
    glow = page.evaluate("""(() => { const path = document.querySelector('#map2d svg path.work-unbuilt');
        const style = getComputedStyle(path); return [Number(style.opacity), style.filter]; })()""")
    assert glow[0] == 1 and 'drop-shadow' in glow[1]
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-027')
@pytest.mark.req('MAP-046')
def test_a_part_being_worked_on_stays_a_ghost_until_done_and_then_comes_up_solid(run, web, mapped, browser):
    """A part not built is a ghost while it waits and while it is under construction, so the map says it is still to
    come, and when the work is done it comes up to its solid node, VIEW-027. Its work shows in 2D and the legend."""
    from metaform.data import Node, Store
    store = Store('proj')
    waiting = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='build it')
    working = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='build that')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    ids = {address: store.element(address).id for address in ('code.alarm.audible', 'exterior.cook')}
    run('map', 'work', 'op=edit', f'id={working.id}', 'condition=under-construction', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{ids["exterior.cook"]}").work[0] === "under-construction"', timeout=15000)  # pushed, read and drawn again
    assert all(page.evaluate(f'window.metaform.look("{ids[address]}").ghost') for address in ids)
    cook = page.evaluate(f'window.metaform.look("{ids["exterior.cook"]}")')
    assert cook['classes'] == ['work-under-construction'] and cook['animated2d'] is True
    assert 'part: under construction' in page.inner_text('#legend')
    run('map', 'work', 'op=done', f'id={working.id}', 'resolution=built', 'why=the test closes it', cwd=mapped)
    page.wait_for_function(f'() => !window.metaform.look("{ids["exterior.cook"]}").ghost'
                           f' && window.metaform.look("{ids["exterior.cook"]}").opacity3d >= 0.99', timeout=30000)
    page.wait_for_function(f'() => window.metaform.look("{ids["exterior.cook"]}").classes.length === 0', timeout=5000)
    assert page.evaluate(f'window.metaform.look("{ids["code.alarm.audible"]}").ghost')  # still waiting
    assert waiting.id and problems == []


@pytest.mark.req('VIEW-022')
@pytest.mark.req('VIEW-026')
def test_a_propertys_reach_travels_as_a_wave_from_the_element_it_is_linked_to(run, web, mapped, browser):
    """Clicking a property sends a wave out from the element it is linked to, toward the leaves where it applies and
    toward the trunk where it is visible. A node is lit only while it holds a dot, so the near elements light before
    the far ones and an element the property does not reach never lights. Selecting anything else puts the map back."""
    from metaform.data import Store
    store = Store('proj')
    for address in ('code.timer', 'code.timer.kitchen.dial', 'code.timer.kitchen.dial.pointer'):
        store.add_element('notes', address, name_length=1)
    written = store.add_property('notes', 'code.timer.kitchen', 'written in C11')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    names = {at[address]: address for address in at}
    assert {key: page.evaluate('window.metaform.bloom()')[key] for key in ('pass', 'levels')} == {'pass': True, 'levels': 3}
    assert page.evaluate('window.metaform.reach()') == {'property': None, 'elements': [], 'edges': 0}
    page.evaluate('window.metaform.waveTimes({every: 2.4, cross: 0.5, hold: 0.3, gaussian: false})')
    key = 'r:' + written.id
    page.wait_for_function(f'() => window.metaform.graph().nodes.some(node => node.id === "{key}")', timeout=5000)
    page.evaluate(f'window.metaform.select("{key}")')
    reach = page.evaluate('window.metaform.reach()')
    assert reach['property'] == key
    # the fixture's display sits toward the leaves from the kitchen timer too
    reached = ['code.timer', 'code.timer.kitchen', 'code.timer.kitchen.dial', 'code.timer.kitchen.dial.pointer',
               'code.timer.kitchen.display']
    assert sorted(reach['elements']) == reached
    assert reach['edges'] == 4  # the namespace edges that join them
    assert page.evaluate(f'window.metaform.look("{at["code.timer.kitchen.dial"]}")')['reach2d'] is True
    # Sampled until the wave has been everywhere it goes, for up to a minute; a slow machine draws fewer frames, the
    # wave's clock moves at most 0.1 s a frame, and the wave keeps its order whatever the speed.
    seen = page.evaluate("""async count => { const seen = [], lit = new Set();
        for (let at = 0; at < 1200 && lit.size < count; at++) {
          await new Promise(done => setTimeout(done, 50));
          const now = window.metaform.wave(); seen.push(now); now.lit.forEach(node => lit.add(node));
          now.light = now.lit.map(node => window.metaform.look(node).light3d);
          now.around = now.lit.map(node => window.metaform.look(node).around3d); }
        return seen; }""", len(reached))
    first = {}
    for index, moment in enumerate(seen):
        for node in moment['lit']:
            first.setdefault(names[node], index)
    assert sorted(first) == reached  # every element of the reach lit, and no other
    home = first['code.timer.kitchen']
    assert home < first['code.timer'] and home < first['code.timer.kitchen.dial'] and home < first['code.timer.kitchen.display']
    assert first['code.timer.kitchen.dial'] < first['code.timer.kitchen.dial.pointer']  # a hop further, later
    assert max(len(moment['lit']) for moment in seen) < len(reached)  # lit while holding a dot, never all at once
    assert any(moment['dots'] for moment in seen)
    # a node lit by the wave gives off its body's light, above full brightness at the pulse's height, which the bloom
    # spreads; nothing is drawn around it, VIEW-029
    assert max(light for moment in seen for light in moment['light']) > 1
    assert all(count == 0 for moment in seen for count in moment['around'])
    assert any(at['code.timer.kitchen'] not in moment['lit'] and moment['lit'] for moment in seen)  # the wave moved on
    # an edge keeps its own look: the dots carry the property's color
    colors = {link['color'].lower() for link in page.evaluate('window.metaform.linkColors()') if link['k'] == 'tree'}
    assert len(colors) == 1
    # a minute of waves would fill the graphics card's memory if each dot kept a shape of its own
    early = page.evaluate('window.metaform.wave().shapes')
    page.wait_for_timeout(6000)
    assert page.evaluate('window.metaform.wave().shapes') == early
    page.evaluate(f'window.metaform.select("{at["code.alarm.audible"]}")')
    assert page.evaluate('window.metaform.reach()') == {'property': None, 'elements': [], 'edges': 0}
    page.wait_for_function('() => { const wave = window.metaform.wave(); return !wave.dots && !wave.lit.length; }',
                           timeout=3000)
    assert page.evaluate(f'window.metaform.look("{at["code.timer.kitchen.dial"]}")')['reach2d'] is False
    assert problems == []


@pytest.mark.req('VIEW-006')
@pytest.mark.req('MAP-020')
@pytest.mark.req('VIEW-012')
def test_each_encounter_keeps_its_layers_color_and_nothing_names_a_perspective(run, web, mapped, browser):
    """A join carries no perspective. Each encounter link, one to each element
    a join holds, takes its layer's color in both views; the legend and the panel name no Function or Encounter word."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    color = {name: page.evaluate(f'getComputedStyle(document.documentElement).getPropertyValue("--{name}").trim()')
             for name in ('intake', 'k1')}
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    drawn = page.evaluate('window.metaform.linkColors()')
    for join in expected['joins']:
        assert 'perspective' not in join
        encounters = [link for link in drawn if link['join'] == join['id'] and link['k'] == 'encounter']
        assert len(encounters) == len(join['elements'])
        for encounter in encounters:
            assert encounter['color'] == color['k1' if join['layer'] == 'notes' else 'intake'], join
    assert page.locator('#map2d svg .edgePaths path[class*="perspective-"]').count() == 0
    legend = page.inner_text('#legend')
    assert 'Function ·' not in legend and 'Encounter ·' not in legend
    kitchen = next(entry['element']['id'] for entry in expected['elements']
                   if entry['element']['address'] == 'code.timer.kitchen')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    assert page.locator('#p-object .join .perspective').count() == 0
    assert problems == []


def keys_of(web):
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    by_address = {entry['element']['address']: entry['element']['id'] for entry in expected['elements']}
    return expected, by_address


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_sibling_arrows_follow_three_distinct_rendered_targets(run, web, mapped, browser):
    """Three siblings distinguish screen direction from reversed traversal with two-node wrapping."""
    from metaform.data import Store

    store = Store('proj')
    for number in range(3):
        address = f'code.alarm.audible.tone{number}'
        store.add_element('notes', address, name_length=1)
        store.add_join('notes', 'code.alarm.audible', address, purpose=f'Play tone {number}.',
                       ef=f'Plays tone {number}.')
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    tones = [at[f'code.alarm.audible.tone{number}'] for number in range(3)]
    for direction in ('down', 'across', 'down'):
        page.evaluate("direction => import('/page/app/map2d/fit.js').then(part => part.fitDirection2d(direction))",
                      direction)
        vertical = direction == 'down'
        page.wait_for_function('vertical => window.metaform.vertical() === vertical', arg=vertical)
        still2d(page)
        axis = 'x' if vertical else 'y'
        positions = {key: page.evaluate('key => window.metaform.at2d(key)', key)[axis] for key in tones}
        assert len(set(positions.values())) == 3
        row = sorted(tones, key=positions.get)
        previous, following = ('ArrowLeft', 'ArrowRight') if vertical else ('ArrowUp', 'ArrowDown')
        for key, expected in ((previous, row[0]), (following, row[2])):
            page.evaluate('key => window.metaform.select(key)', row[1])
            page.keyboard.press(key)
            assert page.evaluate('window.metaform.selected()') == expected, (direction, key, positions)
    assert problems == []


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_arrow_keys_go_deeper_back_to_the_parent_and_across_the_parents_nodes(run, web, mapped, browser):
    """Physical arrows follow the rendered axes, including after orientation changes on the same page."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    cook, kitchen, alarm, display, tick = (at[address] for address in (
        'exterior.cook', 'code.timer.kitchen', 'code.alarm.audible', 'code.timer.kitchen.display', 'code.loop.tick'))
    # cook's join holds the kitchen timer and the tick loop, a row of two in the order they are drawn across the map;
    # the kitchen timer receives from the alarm; the display, which nothing receives from, sits beside the cook.
    press = lambda key: (page.keyboard.press(key), page.evaluate('window.metaform.selected()'))[1]
    for direction in ('down', 'across', 'down'):
        page.evaluate("direction => import('/page/app/map2d/fit.js').then(part => part.fitDirection2d(direction))",
                      direction)
        vertical = direction == 'down'
        page.wait_for_function('vertical => window.metaform.vertical() === vertical', arg=vertical)
        still2d(page)
        deeper, parent, previous, following = (('ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight') if vertical
                                               else ('ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown'))
        axis = 'x' if vertical else 'y'
        across = {key: page.evaluate('key => window.metaform.at2d(key)', key)[axis] for key in (kitchen, tick)}
        row = sorted(across, key=across.get)
        page.evaluate('key => window.metaform.select(key)', cook)
        assert press(parent) == cook, (direction, page.evaluate('window.metaform.vertical()'))
        first = press(deeper)
        assert first in row
        other = row[1 - row.index(first)]
        toward, back = (following, previous) if row.index(first) == 0 else (previous, following)
        assert press(toward) == other
        assert press(back) == first
        if first != kitchen:
            assert press(toward) == kitchen
        assert [press(key) for key in (deeper, parent, parent, following, previous)] == [
            alarm, kitchen, cook, display, cook]
        page.evaluate('key => window.metaform.select(key)', alarm)
        assert press(deeper) == alarm  # a leaf keeps its selection
        page.evaluate('key => window.metaform.select(key)', kitchen)
        assert press('Alt+ArrowLeft') == alarm
        assert press('Alt+ArrowRight') == kitchen
        # Text entry owns arrows in either layout.
        page.keyboard.press('/')
        assert page.locator('#search input').evaluate('(input) => input === document.activeElement')
        assert press(deeper) == kitchen
        page.keyboard.press('Escape')
    assert problems == []


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
@pytest.mark.parametrize('direction', ['down', 'across'])
def test_every_element_can_be_reached_with_the_arrow_keys(run, web, mapped, browser, direction):
    from metaform.modules.web import view
    view.keep(view.OWNER, 'web_map_direction', direction)
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    everything = set(at.values())
    start = page.evaluate('window.metaform.selected()')
    reached, queue = {start}, [start]
    while queue:
        here = queue.pop()
        for key in ('ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight'):
            page.evaluate(f'window.metaform.select("{here}")')
            page.keyboard.press(key)
            there = page.evaluate('window.metaform.selected()')
            if there not in reached:
                reached.add(there)
                queue.append(there)
    assert everything <= reached, everything - reached
    assert problems == []


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-009')
@pytest.mark.req('VIEW-012')
def test_clicking_a_join_in_3d_shows_that_join(run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at = keys_of(web)
    outer = next(join for join in expected['joins'] if join['receiver'] == at['exterior.cook'])
    page.evaluate(f'window.metaform.click3d("p:{outer["id"]}")')
    assert page.evaluate('window.metaform.selected()') == 'p:' + outer['id']
    assert page.text_content('#p-object .eyebrow') == 'Join'
    assert outer['purpose'] in page.inner_text('#p-object')
    page.evaluate(f'window.metaform.select("{at["code.timer.kitchen"]}")')
    assert 'visible from above' not in page.inner_text('#p-object')
    assert problems == []


@pytest.mark.req('VIEW-009')
@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-016')
@pytest.mark.req('MAP-012')
@pytest.mark.req('MAP-020')
def test_an_element_is_labeled_by_its_name_or_else_its_short_name_and_a_join_shows_its_purpose(run, web, mapped, browser):
    """An element is labeled with its name, or else its short name, its address read through name_length. A join has no
    name, since a name belongs to the element it holds; inside a node its box shows its purpose instead of a blank, with
    the elements that serve it drawn beneath it."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    drawn = {node['id']: node.get('name') for node in page.evaluate('window.metaform.graph().nodes')}
    assert drawn[at['code.timer.kitchen']] == 'dish timer'  # its name
    assert drawn[at['code.alarm.audible']] == 'audible alarm'  # no name: its short name
    page.wait_for_function('() => document.querySelector("#map2d").textContent.includes("dish timer")')
    outer = page.evaluate('[...document.querySelectorAll("#map2d svg g.node")].map(node => [...node.childNodes].filter(part => part.nodeName !== "title").map(part => part.textContent).join("").trim())')
    assert outer.count('dish timer') == 1 and outer.count('audible alarm') == 1, outer
    graph = page.evaluate('window.metaform.graph().nodes')
    assert [node for node in graph if node['t'] == 'purpose' and node.get('name')] == []  # a join has no name of its own
    page.evaluate(f'window.metaform.select("{at["code.timer.kitchen"]}")')
    assert page.text_content('#p-object h2') == 'kitchen timer' and 'dish timer' in page.inner_text('#p-object')
    cook = at['exterior.cook']
    page.evaluate(f'window.metaform.select("{cook}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    labels = page.evaluate('[...document.querySelectorAll("#map2d svg g.node")].map(node => [...node.childNodes].filter(part => part.nodeName !== "title").map(part => part.textContent).join("").trim())')
    assert any(label.startswith('Know when food is') for label in labels) and 'dish timer' in labels, labels  # its purpose, the timer beneath
    assert problems == []


STILL = '''measure => { const now = measure(), was = window.stillness;
    window.stillness = {now, frames: was && was.now === now ? was.frames + 1 : 0};
    return window.stillness.frames >= 2; }'''


def still(page, measure):
    """Wait until what `measure` reads in the page is the same over three animation frames; the wait reads it once a
    frame. A predicate's promise cannot do this, since Playwright ends the wait when one settles, even to false."""
    page.evaluate('window.stillness = null')
    page.wait_for_function(f'() => ({STILL})({measure})')


def still2d(page):
    """Wait until the 2D camera is still. An easing camera moves its view box on every frame, and a sleep as long as
    the ease ends too soon on a machine whose frames come slowly."""
    still(page, '() => document.querySelector("#map2d svg")?.getAttribute("viewBox")')


def still3d(page, fits):
    """Wait until the page's own fits of the 3D map have ended, the count `window.metaform.fits3d()` gives, and its
    camera is still: a camera moved by the test while one runs is taken back by it."""
    page.wait_for_function(f'() => window.metaform.fits3d() >= {fits}', timeout=15000)
    still(page, '() => window.metaform.away3d()')


def box_of(page, address):
    return page.evaluate(f"""() => {{
        const node = [...document.querySelectorAll('#map2d svg g.node')].find(g => g.dataset.title === '{address}');
        const box = node?.getBoundingClientRect();
        return box && {{x: box.left, y: box.top, w: box.width, h: box.height}};
    }}""")


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_a_click_selects_and_goes_inside_escape_lets_go_then_backs_out_and_an_edge_selects_its_join(
        run, web, mapped, browser):
    """One click selects a node, a click on the selected node goes inside it, and so does Enter. Escape lets go of the
    selection first and backs out once nothing is selected, as a click on empty space lets go of it; Shift+Enter and a
    Shift-click back out whatever is selected. An edge takes a click and selects its join, VIEW-008."""
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at = keys_of(web)
    kitchen, cook = at['code.timer.kitchen'], at['exterior.cook']
    # inside the kitchen timer is the join it receives, drawn as its purpose
    tick = 'p:' + next(join['id'] for join in expected['joins'] if join['receiver'] == kitchen)
    selected = lambda: page.evaluate('window.metaform.selected()')
    now_inside = lambda: page.evaluate('window.metaform.inside()')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}")')
    assert selected() == kitchen
    page.keyboard.press('Escape')                          # lets go of the selection, and stays inside
    assert selected() is None and now_inside()
    page.keyboard.press('Escape')                          # with nothing selected, out one level, to the node left
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert selected() == kitchen and 'focused' in page.get_attribute('#map2d', 'class')
    page.keyboard.press('Escape')
    assert selected() is None and 'focused' not in page.get_attribute('#map2d', 'class')
    assert page.inner_text('#p-object').startswith('Nothing is selected')
    page.evaluate(f'window.metaform.select("{cook}")')
    box = box_of(page, 'code.timer.kitchen')
    page.mouse.click(box['x'] + 6, box['y'] + 6)  # the element's own box, clear of the nodes inside it
    assert selected() == kitchen
    still2d(page)  # the camera settles on it
    box = box_of(page, 'code.timer.kitchen')
    page.mouse.click(box['x'] + 6, box['y'] + 6)  # a click on the selected node goes inside
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}")')
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert selected() == kitchen
    page.evaluate(f'window.metaform.select("{cook}")')
    page.keyboard.press('Enter')  # the cook has an inside too, VIEW-016
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    assert selected() == cook and now_inside()
    still2d(page)
    view = page.locator('#viewport').bounding_box()
    page.keyboard.down('Shift')                            # a Shift-click anywhere backs out, a node selected or not
    page.mouse.click(view['x'] + view['width'] / 2, view['y'] + view['height'] / 2)
    page.keyboard.up('Shift')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert selected() == cook
    still2d(page)
    # an edge: the point on an edge's line farthest from every node's area, its box and its reach around its centre,
    # half the spacing to its nearest neighbour, inside the map; the click takes the nearest edge, and a node whose area
    # covers the pointer wins, so the 2D map is put in the large area where its edges are long
    map_key(page, 's')
    page.wait_for_function('() => document.querySelector("main #map2d") !== null')
    page.wait_for_timeout(1200)  # the map is drawn again for its new area
    view = page.locator('#viewport').bounding_box()
    point = page.evaluate("""(() => { const view = document.querySelector('#viewport').getBoundingClientRect();
        const nodes = window.metaform.reaches('2d');
        const clear = (x, y) => Math.min(...nodes.map(one => Math.min(Math.hypot(Math.max(one.left - x, 0, x - one.right),
            Math.max(one.top - y, 0, y - one.bottom)), Math.hypot(one.x - x, one.y - y) - one.reach)));
        let best = null;
        for (const hit of document.querySelectorAll('#map2d .hits2d path')) {
            const length = hit.getTotalLength(), screen = hit.getScreenCTM();
            for (let share = 0.1; share < 0.95; share += 0.05) {
                const on = hit.getPointAtLength(length * share), at = new DOMPoint(on.x, on.y).matrixTransform(screen);
                if (at.x < view.left + 2 || at.x > view.right - 2 || at.y < view.top + 2 || at.y > view.bottom - 2) continue;
                const room = clear(at.x, at.y);
                if (!best || room > best[2]) best = [at.x, at.y, room];
            } }
        return best && best[2] > 4 ? best.slice(0, 2) : null; })()""")
    assert point
    page.mouse.click(*point)
    assert selected().startswith('p:') and page.text_content('#p-object .eyebrow') == 'Join'
    page.mouse.click(view['x'] + 3, view['y'] + view['height'] - 3)  # empty space lets go of it
    assert selected() is None
    assert problems == []


def remember(run, folder, command, value, node=None):
    """An agent's memory, written with the memory module's commands, LAYER-013: `value` is the command's one JSON
    argument, and `node` the map node it is written at. A new entity carries the short why every memory written at an
    address carries, MCP-037; its title is its first observation."""
    if command == 'create_entities':
        value = [{'why': f'Kept for the test of {one["name"]}.', **one} for one in value]
    # deleting memories is the agents' own upkeep, no confirm (the owner, 2026-10-20: agents keep memories current)
    return run('memory', command, json.dumps(value), *([f'node={node}'] if node else []), cwd=folder)


def entity(name, *observations, kind='behavior'):
    return {'name': name, 'entityType': kind, 'observations': list(observations)}


def click_node(page, title):
    """A real click on the 2D node whose full text is this title."""
    still2d(page)  # a box read while the camera eases is not where the node stops
    box = box_of(page, title)
    assert box, title
    view = page.evaluate("""(() => { const box = document.querySelector('#viewport').getBoundingClientRect();
        return {x: box.left, y: box.top, w: box.width, h: box.height}; })()""")
    x, y = box['x'] + box['w'] / 2, box['y'] + box['h'] / 2
    if not (view['x'] <= x <= view['x'] + view['w'] and view['y'] <= y <= view['y'] + view['h']):
        page.evaluate('window.metaform.fit()')  # All: a mode that zooms in may leave a node outside the view
        still2d(page)
        box = box_of(page, title)
    page.mouse.click(box['x'] + box['w'] / 2, box['y'] + box['h'] / 2)


def inside(page):
    """The current level's node keys and the breadcrumb's words."""
    return page.evaluate('window.metaform.inside()'), page.inner_text('#crumbs') if page.is_visible('#crumbs') else ''


# The fades of the views, VIEW-016, as the browser and the page run them: each opacity transition's transitionrun with
# its duration and its transitionend, the moment the page sets a view's opacity, and the moment it takes a view off the
# page, which it does as the view's fade ends, so no transitionend comes for that view. A fade is seen to run whether or
# not a frame is drawn inside it. At a frame, `part` says how far into its fade's time a view is.
FADES = '''window.fades = [];
    if (!window.fading) { window.fading = true;
      const view = target => target.id === "stage" ? "3d" : target.dataset.base === "yes" ? "base" : "own";
      const ours = target => target.id === "stage" || target instanceof SVGSVGElement && target.parentNode?.id === "viewport";
      const level = target => target.style.opacity === "" ? 1 : Number(target.style.opacity);
      const note = (type, target, more = {}) =>
        window.fades.push({type, view: view(target), to: level(target), t: performance.now(), ...more});
      const runs = new WeakMap();  // a transition's end value and duration, read as it runs, for its end
      for (const type of ["transitionrun", "transitionend", "transitioncancel"])
        document.addEventListener(type, event => { const target = event.target;
          if (event.propertyName !== "opacity" || !ours(target)) return;
          if (type === "transitionrun") {
            const fade = target.getAnimations().find(one => one.transitionProperty === "opacity");
            const frames = fade?.effect.getKeyframes(), timing = fade?.effect.getTiming();
            runs.set(target, fade ? {from: Number(frames[0].opacity), to: Number(frames.at(-1).opacity), duration: timing.duration,
              delay: timing.delay, easing: timing.easing} : {to: level(target), duration: null}); }
          note(type, target, {elapsed: event.elapsedTime, ...runs.get(target)}); }, true);
      const set = new WeakMap(), styled = {attributes: true, attributeFilter: ["style"]};
      const watch = new MutationObserver(records => { for (const record of records) {
        if (record.type === "attributes" && ours(record.target) && set.get(record.target) !== level(record.target)) {
          set.set(record.target, level(record.target)); note("set", record.target); }
        for (const node of record.addedNodes || []) if (node instanceof SVGSVGElement) watch.observe(node, styled);
        for (const node of record.removedNodes || []) if (node instanceof SVGSVGElement) note("removed", node); } });
      const viewport = document.querySelector("#viewport");  // the views only, not every node drawn in them
      watch.observe(viewport, {childList: true});
      for (const node of viewport.children) if (node instanceof SVGSVGElement) watch.observe(node, styled);
      watch.observe(document.querySelector("#stage"), styled); }
    const part = element => { const fade = element?.getAnimations().find(one => one.transitionProperty === "opacity"
        && one.playState === "running" && one.currentTime !== null);
      return fade ? fade.currentTime / fade.effect.getTiming().duration : null; };'''

SAMPLE_2D = '''() => { window.samples = []; window.sampling = true;
    ''' + FADES + '''
    const tick = () => { const svg = document.querySelector("#map2d svg");
        if (svg) { const box = svg.viewBox.baseVal;
            window.samples.push({base: svg.dataset.base === "yes", o: Number(getComputedStyle(svg).opacity),
                                 w: box ? box.width : 0, f: part(svg)}); }
        if (window.sampling) requestAnimationFrame(tick); };
    requestAnimationFrame(tick); }'''


def faded(page, view, to, samples, key='o', part='f'):
    """VIEW-016: the browser ran the view's opacity from the other end to `to` in a 480 ms `ease` transition with no
    delay, and the fade had its time: the transition ended 0.48 s in, or, for a view the page takes off as its fade
    ends, the view stayed 480 ms from the moment its opacity was set. And each frame drawn inside the fade where its time puts the opacity past half way, the
    second half of a fade out and the first quarter of a fade in under the page's `ease`, shows it under 0.5; a frame
    need not land there, since a loaded machine can draw none inside 480 ms."""
    over = ('transitionend', 'transitioncancel', 'removed')
    from playwright.sync_api import TimeoutError as Waited
    try:
        page.wait_for_function('([view, to, over]) => window.fades.some(one => one.view === view && one.to === to'
                               ' && over.includes(one.type))', arg=[view, to, over], timeout=5000)
    except Waited:
        raise AssertionError(('the fade did not end', view, to, page.evaluate('window.fades'))) from None
    fades = page.evaluate('window.fades')
    ran = [one for one in fades if one['view'] == view and one['to'] == to]
    assert any(one['type'] == 'transitionrun' and one['from'] == 1 - to and one['duration'] == 480 and one['delay'] == 0
               and one['easing'] == 'ease' for one in ran), (view, to, fades)  # from the other end, at once, eased
    end = next(one for one in ran if one['type'] in over)
    if end['type'] == 'removed':
        began = [one for one in ran if one['type'] == 'set' and one['t'] <= end['t']]
        assert began and end['t'] - began[-1]['t'] >= 479, (view, to, fades)  # a timer rounds to the millisecond
    else:
        assert end['type'] == 'transitionend' and end['elapsed'] == pytest.approx(0.48), (view, to, fades)
    inside = [one for one in samples if one[part] is not None and (one[part] >= 0.5 if to == 0 else one[part] <= 0.25)]
    assert all(one[key] < 0.5 for one in inside), (view, to, inside)


@pytest.mark.req('VIEW-016')
def test_going_inside_a_node_zooms_into_it_as_the_map_fades_and_its_own_graph_fades_in(run, web, mapped, browser):
    """The zoom in and fade effect when going inside was nice and was lost when going inside became a
    swap to the node's own graph. The base map zooms into the node as it fades out, the node's graph fades in, and
    going back out runs the other way; with reduced motion the views change at once."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    cook = at['exterior.cook']
    page.evaluate('() => { document.querySelector("#map2d svg").dataset.base = "yes"; }')
    page.evaluate(f'window.metaform.select("{cook}")')
    still2d(page)  # the selection's own camera move settles first
    page.evaluate(SAMPLE_2D)
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    page.wait_for_function('() => { const last = window.samples.at(-1); return last && !last.base && last.o === 1; }')
    going_in = page.evaluate('() => { window.sampling = false; return window.samples; }')
    base = [sample for sample in going_in if sample['base']]
    own = [sample for sample in going_in if not sample['base']]
    assert base and own
    faded(page, 'base', 0, base)  # the map fades as the camera goes in
    assert base[-1]['w'] < base[0]['w'] * 0.8  # and the camera zooms into the node
    faded(page, 'own', 1, own)  # the node's own graph fades in
    assert own[-1]['o'] == 1

    page.evaluate(SAMPLE_2D)
    page.keyboard.press('Shift+Enter')  # out one level; Escape would let go of the selection first, VIEW-008
    page.wait_for_function('() => window.metaform.inside().length === 0')
    page.wait_for_function('() => { const last = window.samples.at(-1); return last && last.base && last.o === 1; }')
    still2d(page)
    going_out = page.evaluate('() => { window.sampling = false; return window.samples; }')
    own = [sample for sample in going_out if not sample['base']]
    back = [sample for sample in going_out if sample['base']]
    assert own and back
    faded(page, 'own', 0, own)  # the node's graph fades out
    faded(page, 'base', 1, back)  # the map fades back in
    assert back[-1]['o'] == 1
    assert back[-1]['w'] > back[0]['w'] * 1.25  # and the camera eases out from the node
    assert problems == []

    page.emulate_media(reduced_motion='reduce')
    page.evaluate(SAMPLE_2D)
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    page.wait_for_timeout(400)
    still = page.evaluate('() => { window.sampling = false; return window.samples; }')
    assert still and all(sample['o'] == 1 for sample in still)  # nothing fades for a person who turned motion off


@pytest.mark.req('VIEW-016')
@pytest.mark.req('VIEW-008')
def test_going_inside_any_node_replaces_the_2d_map_with_its_own_graph_of_what_the_visible_layers_attach(
        run, web, mapped, browser):
    """Any node can be entered, whether or not it holds subtypes; going inside a node replaces the map
    with another graph, and the other layers show only what is attached to the node being viewed, as busy as the
    layers turned on; the base map stays the project's current shape."""
    remember(run, mapped, 'create_entities', [entity('countdown drift', 'The countdown drifts under load.')],
             'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'Too quiet in a loud kitchen.')],
             'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'quiet tone', 'relationType': 'drives'}])
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at = keys_of(web)
    kitchen, cook, alarm = at['code.timer.kitchen'], at['exterior.cook'], at['code.alarm.audible']
    received = 'p:' + next(join['id'] for join in expected['joins'] if join['receiver'] == kitchen)
    assert 'The countdown drifts' not in page.inner_text('#p-object')  # the folder's layers leave memory off
    set_layer(page, 'memory', True)  # turned on in this view only
    page.keyboard.press('Escape')  # the first Escape closes the Layers list, and only that
    assert not page.is_visible('#layerlist')
    page.wait_for_function('() => window.metaform.loaded() && '
                           'document.querySelector("#p-object").textContent.includes("The countdown drifts")')
    base = page.evaluate('() => { const svg = document.querySelector("#map2d svg"); svg.dataset.base = "yes"; '
                         'return document.querySelectorAll("#map2d svg g.node").length; }')

    page.evaluate(f'window.metaform.select("{cook}")')
    page.keyboard.press('Enter')  # the cook can be entered
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    keys, crumbs = inside(page)
    assert crumbs.split('›')[-1].strip() == 'cook' and not page.query_selector('#map2d svg[data-base]')
    assert any(key.startswith('p:') for key in keys)  # the join it holds, as its purpose
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert page.query_selector('#map2d svg[data-base="yes"]') is not None  # the same map, never laid out again
    assert page.evaluate('document.querySelectorAll("#map2d svg g.node").length') == base
    assert page.evaluate('window.metaform.selected()') == cook and not page.is_visible('#crumbs')

    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{kitchen}") && '
                           'window.metaform.inside().some(key => key.startsWith("e:"))')
    keys, crumbs = inside(page)
    assert [part.strip() for part in crumbs.split('›')] == ['map', 'dish timer']
    # the join it receives, its memory, the memory that memory relates to, and the node that one is kept at
    assert {received, 'e:countdown drift', 'e:quiet tone', alarm} <= set(keys)
    words = page.evaluate('document.querySelector("#map2d svg").textContent')
    assert 'keep the loop small' in words and 'countdown drift' in words and 'louder is better' not in words
    assert 'drives' in words  # the relation, on its line
    click_node(page, 'countdown drift')  # selecting a memory shows it whole in the panel
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("under load.")')
    assert page.text_content('#p-object .eyebrow') == 'Memory'

    set_layer(page, 'notes', False)  # turning a layer off takes its group away inside
    page.keyboard.press('Escape')
    page.wait_for_function('() => !document.querySelector("#map2d svg").textContent.includes("keep the loop small")')
    assert 'countdown drift' in page.evaluate('document.querySelector("#map2d svg").textContent')

    click_node(page, 'quiet tone')  # the memory it relates to; its panel links across to the alarm it is kept at
    page.click('#p-object a.link:has-text("audible alarm")')
    page.wait_for_function('() => window.metaform.inside().length && '
                           'document.querySelector("#crumbs").textContent.includes("audible alarm")')
    assert [part.strip() for part in inside(page)[1].split('›')] == ['map', 'dish timer', 'audible alarm']
    page.keyboard.press('Escape')  # the first lets go of the selection, VIEW-008, the second backs out
    assert page.evaluate('window.metaform.selected()') is None and len(inside(page)[0])
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length && '
                           '!document.querySelector("#crumbs").textContent.includes("audible alarm")')
    assert page.evaluate('window.metaform.selected()') == alarm  # the node left, selected where it shows
    click_node(page, 'audible alarm')  # the alarm is selected: a click on it goes inside
    page.wait_for_function('() => window.metaform.inside().length && '
                           'document.querySelector("#crumbs").textContent.includes("audible alarm")')
    page.keyboard.press('Shift+Enter')  # out one level whatever is selected
    page.wait_for_function('() => window.metaform.inside().length && '
                           '!document.querySelector("#crumbs").textContent.includes("audible alarm")')
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert page.evaluate('window.metaform.selected()') == kitchen and not page.is_visible('#crumbs')
    assert problems == []


@pytest.mark.req('VIEW-016')
@pytest.mark.req('VIEW-008')
def test_inside_a_node_the_graph_keeps_the_maps_orientation_and_a_mode_still_zooms(run, web, mapped, browser):
    """After going inside a node, the map seemed to turn on its side, and the zoom did not work there.
    The inside graph runs the way the whole map does, and the modes zoom inside, VIEW-041."""
    from metaform.data import Store
    store = Store('proj')
    for name in ('dial', 'buzzer', 'battery'):  # the map runs whichever way fits its pane, P043; inside follows it
        store.add_element('notes', f'code.timer.kitchen.{name}', name_length=1)
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at = keys_of(web)
    kitchen = at['code.timer.kitchen']
    tick = 'p:' + next(join['id'] for join in expected['joins'] if join['receiver'] == kitchen)
    across = page.evaluate('window.metaform.vertical()')
    assert isinstance(across, bool)
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}")')
    assert page.evaluate('window.metaform.vertical()') == across
    # the timer and the join it receives, found by their keys, since a join has no label
    center, held = (page.evaluate(f'window.metaform.at2d("{key}")') for key in (kitchen, tick))
    if across:  # top to bottom: what the node holds sits below it
        assert held['y'] > center['y']
    else:
        assert held['x'] > center['x']
    width = lambda: float(page.get_attribute('#map2d svg', 'viewBox').split()[2])
    whole = width()
    zoomed_to(page, 2 * page.evaluate(HEADING))  # the selection at twice the heading's size
    still2d(page)  # the camera eases for 700 ms
    assert width() < whole * 0.8  # zoomed in
    assert problems == []


@pytest.mark.req('VIEW-003')
@pytest.mark.req('VIEW-005')
def test_the_3d_map_shares_one_three_module_with_its_glass_and_figures(run, web, mapped, browser):
    """A second Three.js runtime warns at load and can disagree on object identity in the shared scene."""
    started(run)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    messages, problems, fetched = [], [], []
    page.on('console', lambda message: messages.append(message.text))
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda request: fetched.append(request.url))
    page.goto(f'http://127.0.0.1:{web}/#p=proj')
    assert problems == [], messages
    try:
        page.wait_for_function('() => window.metaform?.loaded() && window.metaform.drawn()?.nodes > 0')
    finally:
        assert problems == [], messages
        assert not [message for message in messages if 'Failed to load' in message], messages
    assert not [message for message in messages if 'Multiple instances of Three.js' in message]
    assert page.evaluate('''async () => {
        const THREE = await import('three');
        const {default: Graph} = await import('three-forcegraph');
        return new Graph() instanceof THREE.Group;
    }''')  # the library's scene objects have the same identity as the page's Three.js objects
    assert problems == []
    assert sum(re.search(r'/vendor/v-[0-9a-f]{16}/three\.module\.min\.js$', url) is not None for url in fetched) == 1
    assert all(url.startswith((f'http://127.0.0.1:{web}/', 'data:', 'blob:')) for url in fetched), fetched


@pytest.mark.req('VIEW-003')
def test_the_page_files_are_checked_with_the_server_on_every_load(run, web):
    """A page file the browser keeps would show a person the page as it was before an update, with nothing to say
    so. Each page file tells the browser to ask again before using its copy."""
    started(run)
    for path in ('/', '/page/app.js', '/page/app.css', '/vendor/three.module.min.js'):
        status, _, headers = request(web, path)
        assert status == 200 and headers['Cache-Control'] == 'no-cache', path
        # a copy that is current is confirmed with no body, so a load re-sends none of the libraries
        status, body, again = request(web, path, headers={'If-None-Match': headers['ETag']})
        assert status == 304 and body == '' and again['ETag'] == headers['ETag'], path
        assert again['Content-Security-Policy'] == headers['Content-Security-Policy'], path
        assert request(web, path, headers={'If-None-Match': '"stale"'})[0] == 200, path


@pytest.mark.req('VIEW-003')
def test_the_libraries_are_kept_by_version_sent_gzipped_and_named_to_the_browser_at_once(run, web):
    """A library at the page's vendor version is kept without asking again; a file is gzipped for a browser that takes
    gzip; and the page names every module it imports, so the browser asks for them side by side."""
    import gzip

    from metaform.modules.web import server
    started(run)
    _, page, _ = request(web, '/')
    version = server.vendor_version()
    preloaded = re.findall(r'<link rel="modulepreload" href="([^"]+)">', page)
    for module in ('/page/app.js', '/page/app/workspace/workspace.js', f'/vendor/{version}/three.module.min.js',
                   f'/vendor/{version}/drei-vanilla/MeshTransmissionMaterial.js'):
        assert module in preloaded, module
    assert page.index('type="importmap"') < page.index('rel="modulepreload"')  # only then resolved through the map
    status, _, headers = request(web, f'/vendor/{version}/three.module.min.js')
    assert status == 200 and headers['Cache-Control'] == 'public, max-age=31536000, immutable'
    assert request(web, '/vendor/v-0000000000000000/three.module.min.js')[2]['Cache-Control'] == 'no-cache'
    connection = http.client.HTTPConnection('127.0.0.1', web, timeout=10)
    try:
        connection.request('GET', '/page/app/map3d/light.js', headers={'Accept-Encoding': 'gzip'})
        response = connection.getresponse()
        packed = response.read()
    finally:
        connection.close()
    assert response.getheader('Content-Encoding') == 'gzip' and response.getheader('Vary') == 'Accept-Encoding'
    sent = gzip.decompress(packed)
    assert f"from '/vendor/{version}/drei-vanilla/".encode() in sent and b"from '/vendor/drei" not in sent
    status, _, again = request(web, '/page/app/map3d/light.js',
                               headers={'Accept-Encoding': 'gzip', 'If-None-Match': response.getheader('ETag')})
    assert status == 304 and again['ETag'] == response.getheader('ETag')
    assert request(web, '/page/app/map3d/light.js', headers={'Accept-Encoding': 'gzip;q=0'})[2].get(
        'Content-Encoding') is None


@pytest.mark.req('VIEW-025')
@pytest.mark.req('VIEW-003')
def test_in_every_theme_the_elements_are_glass_and_the_page_loads_nothing_from_outside(run, web, mapped, browser):
    """A node is made of a material that lets light through, in each plain theme alike, with no mode to choose. The glass
    comes from the copy of three.js the page carries, so it works with no network."""
    started(run)
    page, problems, _ = opened(browser, web)
    fetched = []
    page.on('request', lambda request: fetched.append(request.url))
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    themes = page.evaluate('[...document.querySelectorAll("#theme option")].map(option => option.value)')
    themes = [theme for theme in themes if theme != 'space']  # Space draws the map in outer space, ultra.js
    assert len(themes) > 1
    checked = (at['code.timer.kitchen'], at['code.alarm.audible'], at['code.loop.tick'])
    pick_theme(page, themes[0])
    # a node's object can be missing, or still drawn in outer space's own material, a moment after the theme changes
    made = f'() => {json.dumps(checked)}.every(node => window.metaform.look(node).material === "MeshTransmissionMaterial")'
    page.wait_for_function(made, timeout=10000)
    for theme in themes:
        pick_theme(page, theme)
        page.wait_for_timeout(250)
        page.wait_for_function(made, timeout=10000)
        for node in checked:
            seen = page.evaluate(f'window.metaform.look("{node}")')
            # drei's glass, it lets light through, parts its colors at the edge and draws its far wall; it is clear,
            # so nothing bends what is read through it (2026-10-21)
            assert seen['material'] == 'MeshTransmissionMaterial' and seen['transmission'] > 0, (theme, node, seen)
            assert seen['chromatic'] > 0 and seen['distortion'] == 0 and seen['backside'] is True, (theme, node, seen)
    # one shape for every node of a size, however many nodes there are
    sizes = page.evaluate('new Set(window.metaform.graph().nodes.filter(node => node.t === "el")'
                          '.map(node => window.metaform.look(node.id).shape)).size')
    assert sizes <= 4
    assert any(re.search(r'/vendor/v-[0-9a-f]{16}/three\.module\.min\.js$', url) for url in fetched)
    assert any(re.search(r'/vendor/v-[0-9a-f]{16}/drei-vanilla/MeshTransmissionMaterial\.js$', url) for url in fetched)
    assert all(url.startswith((f'http://127.0.0.1:{web}/', 'data:', 'blob:')) for url in fetched), fetched
    assert problems == []


@pytest.mark.req('VIEW-025')
def test_what_is_behind_a_node_reaches_its_glass_through_the_pictures_the_page_draws(run, web, mapped, browser):
    """What is behind the glass reaches it through the pictures the page draws each frame, as drei's component does.
    The glass is clear, so it is read as it is: the kitchen timer, which the cook's join reaches, is set behind the cook,
    and the join's line running back to it shows through the cook; moved away, the line leaves the cook another way
    and the cook changes. A node's body behind another is faint through it: the pictures hold a node's far wall only,
    and a far wall is mostly the ground it tints (2026-10-21)."""
    from metaform.data import Store
    store = Store('proj')
    for record in store.work(None, None, True, limit=0).results:  # nothing lit, nothing drawn in characters
        store.finish_work(record.id, 'done')
    cook = store.element('exterior.cook').id
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.emulate_media(reduced_motion='reduce')           # the distortion is still
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate('window.metaform.glass(true, {roughness: 0, transmission: 1})')  # the glass is clear as it is
    behind = store.element('code.timer.kitchen').id
    staged(page, {cook: (2000, 0, 0), behind: (2000, 0, -40)},
           ({'x': 2000, 'y': 0, 'z': 80}, {'x': 2000, 'y': 0, 'z': 0}))
    node = page.evaluate(f'window.metaform.screen3d("{cook}")')
    points = [(node['x'] + dx * node['r'], node['y'] + dy * node['r'])
              for dx, dy in ((0, 0), (0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2))]
    seen = pixels(page, points)
    page.evaluate(f'window.metaform.pin3d("{behind}", 2000, 400, -40)')  # out of view
    page.wait_for_timeout(800)
    gone = pixels(page, points)
    assert sum(abs(one - two) for before, after in zip(seen, gone) for one, two in zip(before, after)) > 60, (seen, gone)
    assert problems == []


@pytest.mark.req('MAP-052')
@pytest.mark.req('VIEW-024')
def test_the_page_exports_the_map_as_the_same_markdown_document_the_command_writes(run, web, mapped, browser):
    """A person exports the understanding of a system from the page they read it on. The page and the command give
    one document, written by one piece of the chassis. What the server answers is checked without a browser, in
    test_the_exports_the_server_answers_are_the_documents_the_commands_write."""
    started(run)
    written = run('map', 'markdown', cwd=mapped).stdout
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#exportBtn')
    with page.expect_download() as saved:
        page.click('#exportMarkdown')
    assert saved.value.suggested_filename == 'proj-map.md'
    assert Path(saved.value.path()).read_text(encoding='utf-8') == written
    assert problems == []


@pytest.mark.req('MAP-059')
@pytest.mark.req('VIEW-024')
def test_the_export_menu_saves_the_same_xml_document_the_command_writes_in_the_pages_layers(run, web, mapped,
                                                                                            browser):
    """Export is a menu with an entry for each format. The menu offers each
    format the command writes; the XML holds what the layers in view hold, so a hidden layer and a layer masked at an
    address leave nothing in it, and a layer that is on does. What the server answers is checked without a browser,
    in test_the_exports_the_server_answers_are_the_documents_the_commands_write."""
    started(run)
    written = run('map', 'xml', cwd=mapped).stdout
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.is_hidden('#exportXml')
    page.click('#exportBtn')
    with page.expect_download() as saved:
        page.click('#exportXml')
    assert saved.value.suggested_filename == 'proj-map.xml'
    assert Path(saved.value.path()).read_text(encoding='utf-8') == written
    assert page.is_hidden('#exportXml')
    assert problems == []


# The smallest text of the 2D map as drawn on the screen, in pixels: each label's font size times the screen pixels
# per unit of its own coordinates, which the camera's viewBox sets, VIEW-041.
TEXT_PX = '''() => { const sizes = [...document.querySelectorAll("#map2d svg text, #map2d svg tspan")]
    .filter(text => [...text.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()))
    .map(text => parseFloat(getComputedStyle(text).fontSize) * text.getScreenCTM().a);
    return sizes.length ? Math.min(...sizes) : 0; }'''
# Every node of the 2D map inside its area on the screen.
ALL_IN = '''() => { const view = document.querySelector("#viewport").getBoundingClientRect();
    const nodes = [...document.querySelectorAll("#map2d svg g.node")];
    return nodes.length > 0 && nodes.every(node => { const box = node.getBoundingClientRect();
        return box.left >= view.left - 1 && box.right <= view.right + 1 && box.top >= view.top - 1
            && box.bottom <= view.bottom + 1; }); }'''
# The 2D map's area a fit uses: the pane above the room kept at its foot for the hover card, `foot2d`.
USABLE = '''(() => { const pane = document.querySelector("#viewport").getBoundingClientRect();
    return {left: pane.left, right: pane.right, top: pane.top, bottom: pane.bottom - window.metaform.foot2d(),
            width: pane.width, height: pane.height - window.metaform.foot2d()}; })()'''
# How much of the 2D map's area the drawn diagram spans, across or down, whichever is more.
SPAN = f'''() => {{ const view = {USABLE};
    const scene = document.querySelector("#map2d svg > g").getBoundingClientRect();
    return Math.max(scene.width / view.width, scene.height / view.height); }}'''
FILLS = 0.75  # the whole diagram fitted to the area spans at least this much of it, its margin included
FRAME = 16       # ms of the page's clock in one step, one frame
EASE = 700       # ms, the 2D camera's eased move
STEEPEST = 3     # the steepest slope of its ease in and out, in share of the move per share of its time
ENDS = 0.6       # its first and last frames move at most this share of its fastest: it eases in and eases out
SETTLED = 30     # frames the camera stays still before a move is taken as over
VIEW_BOX = '(() => document.querySelector("#map2d svg").getAttribute("viewBox").trim().split(/[\\s,]+/).map(Number))()'


def stepped(page, act, until='true'):
    """Do `act` with the page's clock held, then step the clock one frame at a time, reading the 2D camera's viewBox
    after each, until it has stayed still SETTLED frames since `until` came to hold in the page. Every frame is read,
    however loaded the machine, since the page's frames come only as the clock is stepped. Returns the viewBoxes, the
    first from before `act`."""
    page.clock.pause_at(page.evaluate('Date.now()') / 1000 + 1)  # in seconds, a second on
    cams, still = [page.evaluate(VIEW_BOX)], 0
    try:
        act()
        for _ in range(3000):
            page.clock.run_for(FRAME)
            cams.append(page.evaluate(VIEW_BOX))
            still = still + 1 if cams[-1] == cams[-2] and page.evaluate(until) else 0  # still once `until` holds
            if still >= SETTLED:
                return cams
        raise AssertionError(('the camera did not settle', cams[-5:]))
    finally:
        page.clock.resume()


def eased(cams, must=True):
    """VIEW-041: the 2D camera, read at every frame, moved and eased in and out. For each of x, y, width and height
    that moved, no frame moved it more of its whole move than the 700 ms ease covers at its steepest in one frame, so
    the move was spread over half the ease's frames or more, and its first and last frames moved it slower than its
    fastest by ENDS, as an ease in and out does and a linear move, a move by jumps or one that closes a part of the
    distance each frame does not. With `must` false, a camera that did not move passes. Returns the viewBox it ended
    at."""
    moved = [index for index in range(1, len(cams)) if cams[index] != cams[index - 1]]
    if not must and not moved:
        return cams[-1]
    assert moved, 'the camera did not move'
    for k in range(4):
        path = sum(abs(cams[index][k] - cams[index - 1][k]) for index in moved)
        if path < 1:
            continue
        shares = [abs(cams[index][k] - cams[index - 1][k]) / path for index in moved]
        assert len(shares) >= EASE / FRAME / 2, str(('xywh'[k], 'too few frames', shares))
        assert max(shares) <= STEEPEST * FRAME / EASE * 1.1, str(('xywh'[k], 'a jump', shares))
        assert shares[0] <= ENDS * max(shares) and shares[-1] <= ENDS * max(shares), str(('xywh'[k], 'not eased', shares))
    return cams[-1]


def view_box(page):
    return [float(value) for value in page.get_attribute('#map2d svg', 'viewBox').split()]


def centered(page, key):
    """How far, in screen pixels, the node's center is from the center of the 2D map's area."""
    return page.evaluate(f"""(() => {{ const view = document.querySelector('#viewport').getBoundingClientRect();
        const box = window.metaform.box2d("{key}");
        return Math.max(Math.abs((box.left + box.right - view.left - view.right) / 2),
                        Math.abs((box.top + box.bottom - view.top - view.bottom) / 2)); }})()""")


def fitted(page):
    """The whole diagram is in view, and fills the area across or down, VIEW-041's mode one."""
    return page.evaluate(ALL_IN) and page.evaluate(SPAN) >= FILLS


def margins(page):
    """How far in from each side of the 2D map's area above its foot room, `USABLE`, the map's drawing stands, by its own bounds as the page reads
    them, in screen pixels; negative on a side it runs past, VIEW-041."""
    return page.evaluate("""(() => { const view = """ + USABLE + """;
        const scene = document.querySelector('#map2d svg > g'), box = scene.getBBox(), screen = scene.getScreenCTM();
        const from = new DOMPoint(box.x, box.y).matrixTransform(screen);
        const to = new DOMPoint(box.x + box.width, box.y + box.height).matrixTransform(screen);
        return {left: from.x - view.left, right: view.right - to.x, top: from.y - view.top,
                bottom: view.bottom - to.y}; })()""")


def mode(page):
    """The 2D map's framing, VIEW-041: full, the whole map fitted, or free, the view held where it was left."""
    return 'full' if page.evaluate('window.metaform.view2d().full') else 'free'


def zoomed_to(page, px):
    """The 2D map zoomed by hand until its text is drawn `px` high, on the selection, and held there, VIEW-041."""
    page.evaluate(f'window.metaform.zoom2d({px})')


# The panel heading's size on the screen, which Medium draws the 2D map's text at, VIEW-041.
HEADING = 'parseFloat(getComputedStyle(document.querySelector("#p-object h2")).fontSize)'
ALL_CLICK = 'Meta' if sys.platform == 'darwin' else 'Control'  # a Ctrl-click, a Command-click on macOS, VIEW-008


def modified_click(page, key, x, y):
    """A click with a key held, which waits for nothing."""
    page.keyboard.down(key)
    page.mouse.click(x, y)
    page.keyboard.up(key)


def turn(page, delta, at=(0.5, 0.5)):
    """The wheel turned over the 2D map's area, `at` its share across and down, the middle by default; it zooms the map
    at once, VIEW-041."""
    page.mouse.move(*pointer_at(page, at))
    page.mouse.wheel(0, delta)
    page.wait_for_timeout(60)


def pointer_at(page, at):
    """The point on the screen `at` its share across and down the 2D map's area."""
    return page.evaluate(f'(() => {{ const box = document.querySelector("#viewport").getBoundingClientRect();'
                         f' return [box.left + box.width * {at[0]}, box.top + box.height * {at[1]}]; }})()')


def under(page, point):
    """The point of the 2D map, in its own units, under a point on the screen."""
    return page.evaluate('([x, y]) => { const svg = document.querySelector("#map2d svg");'
                         ' const at = new DOMPoint(x, y).matrixTransform(svg.getScreenCTM().inverse());'
                         ' return [at.x, at.y]; }', point)


def to_large_area(page):
    """The 2D map put in the large area, VIEW-028, drawn there and still."""
    map_key(page, 's')
    page.wait_for_function("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        return box('#map2d').width * box('#map2d').height > 2 * box('#stage').width * box('#stage').height; }""")
    page.wait_for_function('() => window.metaform.loaded() && document.querySelector("#map2d svg g.node")')
    still2d(page)


def changed_by(page, write):
    """Run `write`, a change to the map from the command line, and wait until the page has read it and drawn it."""
    before = page.evaluate('window.metaform.changes()')
    write()
    page.wait_for_function(f'() => window.metaform.changes() > {before} && window.metaform.loaded()', timeout=15000)


def thirty(store):
    """Thirty parts joined under the kitchen timer, one row whose whole diagram draws its text far below 8 px."""
    for index in range(30):
        store.add_element('notes', f'code.part.number{index}', name_length=2)
        store.add_join('notes', 'code.timer.kitchen', f'code.part.number{index}', purpose='Keep the timer working.',
                       ef='serves the timer')


def arrives(run, folder, address='code.part.added'):
    """A part joined under the kitchen timer, in the row of thirty, so the whole diagram grows wider: the element
    written without a word to the page and the join through the command line, which tells the page once of both."""
    from metaform.data import Store
    Store('proj').add_element('notes', address, name_length=2)
    run('map', 'knowledge', 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen', f'elements=["{address}"]',
        'purpose=Keep the timer working.', 'ef=serves the timer', cwd=folder)


def opened_on(browser, web, run, large=True):
    """The page open on the project on Playwright's clock, the 3D map not drawing, which the 2D camera's frames do not
    need, and the 2D map in the large area when `large`."""
    started(run)
    page, problems, _ = opened(browser, web, clock=True)
    page.wait_for_function('() => window.metaform.loaded() && document.querySelector("#map2d svg")')
    page.evaluate('window.metaform.pause3d(true)')
    if large:
        to_large_area(page)
    else:
        still2d(page)
    return page, problems


def click_center(page, key):
    """A click on the middle of a node of the 2D map, which waits for nothing."""
    box = page.evaluate(f'window.metaform.box2d("{key}")')
    page.mouse.click((box['left'] + box['right']) / 2, (box['top'] + box['bottom']) / 2)


def shown(page, at, besides):
    """A node of the 2D map other than `besides` whose middle is in the map's area, by its key."""
    title = page.evaluate("""(() => { const view = document.querySelector('#viewport').getBoundingClientRect();
        return [...document.querySelectorAll('#map2d svg g.node')].map(node => [node.dataset.title,
            node.getBoundingClientRect()]).filter(([title, box]) => (box.left + box.right) / 2 > view.left + 10
            && (box.left + box.right) / 2 < view.right - 10 && (box.top + box.bottom) / 2 > view.top + 10
            && (box.top + box.bottom) / 2 < view.bottom - 10).map(([title]) => title); })()""")
    keys = [at[name] for name in title if name in at and at[name] != besides]
    assert keys, title
    return keys[0]


def acted(page, act, must=True, until='true'):
    """Do `act` on the held clock, and return the viewBox the 2D camera eased to."""
    return eased(stepped(page, act, until), must)


def arrival(page):
    """What holds in the page once it has read and drawn the next change to the map."""
    return f'window.metaform.changes() > {page.evaluate("window.metaform.changes()")} && window.metaform.loaded()'


def map_key(page, key):
    """A map's key pressed with the focus on the page itself, as over the map: the maps have no bar, and their keys,
    which ? lists, do what its buttons did."""
    page.evaluate('document.activeElement?.blur()')
    page.keyboard.press(key)


def mode3d(page):
    """The large 3D map's mode, VIEW-005: whole, zoom or free."""
    return page.evaluate("import('/page/app/camera/flight.js').then(part => part.V3.mode)")


def press(page, selector):
    """A click on a button at its place on the screen, which waits for nothing, so it can be done on the held clock."""
    box = page.evaluate(f'(() => {{ const box = document.querySelector("{selector}").getBoundingClientRect();'
                        f' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; }})()')
    page.mouse.click(*box)


@pytest.mark.req('VIEW-041')
def test_full_fit_keeps_the_whole_map_fitted_and_eases_to_each_new_fit(run, web, mapped, browser):
    """Full fit, which the page opens in with its entry selected, keeps the whole map fitted and eases to each new fit
    as nodes arrive or go and as the area changes size, so an intake can be watched filling in without the camera
    jumping; 0, Home and a Ctrl-click anywhere on the map go back to it from a view zoomed by hand."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run)
    assert fitted(page) and mode(page) == 'full'
    acted(page, lambda: arrives(run, mapped), until=arrival(page))  # a node arrives: it eases out to hold it too
    assert page.evaluate('[...document.querySelectorAll("#map2d svg g.node")].some(g => g.dataset.title === "code.part.added")')
    assert fitted(page)
    expected, at = keys_of(web)
    joined = next(join['id'] for join in expected['joins']
                  if [held['element_id'] for held in join['elements']] == [at['code.part.added']])
    gone = '![...document.querySelectorAll("#map2d svg g.node")].some(g => g.dataset.title === "code.part.added")'
    acted(page, lambda: [run('map', 'knowledge', 'op=remove', 'layer=notes', f'id={thing}', cwd=mapped)
                         for thing in (joined, at['code.part.added'])],
          until=f'{arrival(page)} && {gone}')             # it goes: the row is narrower again
    assert fitted(page)
    acted(page, lambda: page.set_viewport_size({'width': 1100, 'height': 760}))  # the area changes size
    assert fitted(page)
    kitchen = at['code.timer.kitchen']                    # selected as the map opened, as its DE
    # the map's corner where it is at the click: the large map's bar, out after a key, moves the map down below it
    corner = lambda: page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                                   ' return [box.left + 4, box.top + 4]; })()')
    for back in (lambda: page.keyboard.press('0'), lambda: page.keyboard.press('Home'),
                 lambda: modified_click(page, ALL_CLICK, *corner())):
        turn(page, -300)                                  # zoomed in by hand
        assert mode(page) == 'free' and not fitted(page)
        acted(page, back)                                 # eased back to the whole map
        assert mode(page) == 'full' and fitted(page)
    assert page.evaluate('window.metaform.selected()') == kitchen  # a Ctrl-click changes nothing else
    assert problems == []


@pytest.mark.req('VIEW-041')
def test_the_2d_map_moves_between_layouts_each_node_keeping_its_key_and_a_new_one_growing_into_place(
        run, web, mapped, browser):
    """Drawn again, the map jumped to its new layout before the camera eased. Each node now keeps the key of what it
    stands for from one drawing to the next, starts where it stood and eases to its new place, and a new node grows
    in; once settled every node is where the new layout puts it."""
    page, problems = opened_on(browser, web, run, large=False)
    _, at = keys_of(web)
    kitchen = at['code.timer.kitchen']
    assert page.evaluate(f'!!document.querySelector(\'#map2d svg g.node[data-key="{kitchen}"]\')')
    page.clock.pause_at(page.evaluate('Date.now()') / 1000 + 1)
    arrives(run, mapped)
    added = '[...document.querySelectorAll("#map2d svg g.node")].find(g => g.dataset.title === "code.part.added")'
    for _ in range(600):
        page.clock.run_for(FRAME)
        if page.evaluate(f'!!{added}'):
            break
    assert page.evaluate(f'{added}.style.scale') not in ('', '1')   # it grows in
    page.clock.run_for(1200)
    assert page.evaluate('[...document.querySelectorAll("#map2d svg g.node")].every(g => !g.style.translate && !g.style.scale)')
    assert page.evaluate(f'!!document.querySelector(\'#map2d svg g.node[data-key="{kitchen}"]\')')   # the same key, drawn again
    assert problems == []


@pytest.mark.req('VIEW-016')
def test_inside_a_node_each_purpose_box_shows_its_purpose_with_the_elements_that_serve_it_beneath(
        run, web, mapped, browser):
    """A join has no name of its own, so in a node's own graph its box showed only a dot. It shows the join's purpose,
    and the elements the join holds are drawn beneath it."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && document.querySelector("#map2d svg")')
    expected, at = keys_of(web)
    cook, kitchen, tick = at['exterior.cook'], at['code.timer.kitchen'], at['code.loop.tick']
    join = next(held['id'] for held in expected['joins'] if held['receiver'] == cook)
    page.evaluate(f'window.metaform.select("{cook}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    keys = page.evaluate('window.metaform.inside()')
    assert f'p:{join}' in keys and kitchen in keys and tick in keys
    # the purpose wraps into rows, one tspan each, as Mermaid draws a label; read them as the words they show
    text = page.evaluate(f'[...document.querySelectorAll(\'#map2d svg g.node[data-key="p:{join}"] tspan.row\')]'
                         '.map(row => row.textContent.trim()).join(" ")')
    assert 'Know when food is done' in text
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.req('VIEW-008')
def test_the_2d_map_stays_fitted_through_selections_and_frames_the_node_of_the_agent_followed(run, web, mapped, browser):
    """The 2D map is fit-all, VIEW-041: a click in the 3D map, a click, the arrow keys and a selection by id each leave
    it where it is. A follows an agent: none, then each agent on the map in turn, then none again, each press said at
    the map's corner; while one is followed the 2D map frames its node with every part one join away, and with none it
    goes back to full fit. V sees the large 3D map through the followed agent's own eyes, its camera the agent's and
    never orbiting, and back; with the 3D map in the small area it says so and changes nothing. No node carries a
    hover title: the readout names what the pointer is on."""
    from metaform.data import Node, Store
    store = Store('proj')
    thirty(store)
    run('enable', 'dispatch')
    # held left to right, so the framing below is read on one layout: in Auto the row may be drawn top to bottom with
    # its layers held narrow, where the followed node and the timer it serves span the whole map
    from metaform.modules.web import view
    view.keep(view.OWNER, 'web_map_direction', 'across')  # the person's view, view.py, read by the page's server
    worked = store.add_work(Node('element', 'code.part.number27'), None, task='a steadier tick')
    store.take_work(worked.id, by='claude')
    live_session(worked.id)
    page, problems = opened_on(browser, web, run)
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{worked.id}")', timeout=15000)
    expected, at = keys_of(web)
    part = lambda number: at[f'code.part.number{number}']
    assert mode(page) == 'full' and fitted(page)
    tips = '[...document.querySelectorAll("#map2d svg g.node")].filter(g => g.querySelector(":scope > title")).length'
    # the readout at the top of the map names what the pointer is on at every size, so no node carries a hover title
    assert page.evaluate(tips) == 0
    whole = view_box(page)
    selected = lambda: page.evaluate('window.metaform.selected()')
    for act in (lambda: page.evaluate(f'window.metaform.click3d("{part(5)}")'),
                lambda: click_center(page, shown(page, at, selected())),
                lambda: page.keyboard.press('ArrowRight'), lambda: page.keyboard.press('ArrowUp'),
                lambda: page.evaluate(f'window.metaform.select("{part(27)}")')):
        before = selected()
        acted(page, act, must=False)
        assert selected() != before
        assert view_box(page) == pytest.approx(whole, rel=1e-6), selected()
    acted(page, lambda: page.keyboard.press('Escape'), must=False)
    followed = lambda: page.evaluate("import('/page/app/map2d/camera.js').then(part => part.FOLLOW.work)")
    said = lambda: page.evaluate('document.querySelector("#note2d")?.textContent || ""')
    # A: the one agent on the map is followed, and the view frames its node and every part one join away
    acted(page, lambda: page.keyboard.press('a'))
    assert followed() == worked.id
    assert said().startswith('Following: the ') and said().endswith(' on code.part.number27'), said()
    # and it is named, its agent and its glyph, for as long as it is followed, and marked in the agents key
    named = lambda: page.evaluate('document.querySelector("#followed")?.textContent || ""')
    glyph = page.evaluate(f'window.metaform.figures().find(one => one.work_id === "{worked.id}").glyph')
    assert named() == f'Following Claude Code · {glyph}', named()
    marked = '[...document.querySelectorAll("#agents .agent-row[aria-current=true] .agent")].map(one => one.dataset.id)'
    assert page.evaluate(marked) == [worked.id]
    near ={part(27)} | {join['receiver'] for join in expected['joins']
                         if part(27) in [held['element_id'] for held in join['elements']]} | {
        held['element_id'] for join in expected['joins'] if join['receiver'] == part(27) for held in join['elements']}
    assert view_box(page)[2] < whole[2] and mode(page) == 'free'
    inside = lambda key: page.evaluate(f"""(() => {{ const view = document.querySelector('#viewport').getBoundingClientRect(),
        box = window.metaform.box2d("{key}"); return box.left >= view.left - 1 && box.right <= view.right + 1
        && box.top >= view.top - 1 && box.bottom <= view.bottom + 1; }})()""")
    assert all(inside(key) for key in near), near
    framed = view_box(page)
    acted(page, lambda: page.evaluate(f'window.metaform.select("{part(5)}")'), must=False)  # a selection: it stays
    assert view_box(page) == pytest.approx(framed, rel=1e-6)
    # V: with the 3D map in the small area, the agent's view is not taken
    eyes = lambda: page.evaluate("import('/page/app/figures/eyes.js').then(part => [part.EYE.view, part.EYE.agent])")
    page.keyboard.press('v')
    assert eyes() == [False, False] and said() == "The agent's view is the large 3D map's: S swaps the maps"
    # A again: past the last agent, none, and the 2D map back to full fit
    acted(page, lambda: page.keyboard.press('a'))
    assert followed() is None and said() == 'Following: none'
    assert named() == '' and page.evaluate(marked) == []
    assert mode(page) == 'full' and fitted(page)
    page.keyboard.press('v')
    assert eyes() == [False, False] and said() == 'No agent is followed: A follows one'
    # in the large area, V sees through the followed agent's eyes, where the hand no longer turns the camera, and V
    # again gives the person's view back
    page.clock.resume()
    map_key(page, 's')
    page.wait_for_function("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        return box('#stage').width * box('#stage').height > box('#map2d').width * box('#map2d').height; }""")
    page.keyboard.press('a')
    assert followed() == worked.id
    page.keyboard.press('v')
    assert eyes() == [True, True] and said().startswith('View: the ')
    hand = "import('/page/app/map3d/graph3d.js').then(part => part.G.controls().enabled)"
    assert page.evaluate(hand) is False
    assert page.evaluate("import('/page/app/camera/flight.js').then(part => part.V3.eyes)") is True
    # A through none and back to the agent: the agent view stays on, the person's view for none, its eyes again after
    page.keyboard.press('a')
    assert followed() is None and eyes() == [False, False]
    page.keyboard.press('a')
    assert followed() == worked.id and eyes() == [True, True]
    page.keyboard.press('v')
    assert eyes() == [False, False] and said() == 'View: yours'
    # a drag on a map is the hand taking the camera: the following ends where the hand leaves the view
    assert followed() == worked.id
    middle = page.evaluate("""(() => { const box = document.querySelector('#map2d').getBoundingClientRect();
        return [box.x + box.width / 2, box.y + box.height / 2]; })()""")
    page.mouse.move(*middle)
    page.mouse.down()
    page.mouse.move(middle[0] + 40, middle[1] + 10, steps=4)
    page.mouse.up()
    assert followed() is None and named() == '' and said() == 'Following: none'
    assert problems == []


@pytest.mark.req('VIEW-041')
def test_the_wheel_zooms_the_2d_map_about_the_pointer_and_the_view_stays_where_it_is_left(run, web, mapped, browser):
    """Free zoom, VIEW-041: the wheel zooms the map at any time, with nothing selected and with a selection, about the
    pointer, the point of the map under it staying there, and no further out than half the full fit; the view then
    stays where it is left, through a selection, letting go of it and a pane of another size; a digit typed in a text
    field chooses nothing."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run)
    acted(page, lambda: page.keyboard.press('Escape'), must=False)  # nothing selected: the view stays
    assert page.evaluate('window.metaform.selected()') is None and mode(page) == 'full'
    whole = view_box(page)
    point = pointer_at(page, (0.5, 0.3))
    before = under(page, point)
    turn(page, -300, (0.5, 0.3))
    assert view_box(page)[2] < whole[2] and mode(page) == 'free'
    # in about the pointer, not the middle: the row of thirty stands as a column, centered across, so the pointer is
    # above the middle on the map
    assert under(page, point) == pytest.approx(before, abs=2)
    for _ in range(30):
        turn(page, 800)
    assert view_box(page)[2] == pytest.approx(2 * whole[2], rel=1e-3)  # out no further than half the full fit
    for _ in range(6):                                    # in again, closer than the fit
        turn(page, -200, (0.5, 0.3))
    zoomed = view_box(page)
    assert zoomed[2] < whole[2]
    page.wait_for_timeout(800)
    assert view_box(page) == zoomed                       # held: nothing eases after the wheel
    _, at = keys_of(web)                                  # a selection leaves the view
    acted(page, lambda: page.evaluate(f'window.metaform.select("{at["code.part.number27"]}")'), must=False)
    assert view_box(page) == pytest.approx(zoomed, rel=1e-6)
    point = pointer_at(page, (0.5, 0.7))                  # with a selection the wheel zooms about the pointer too
    before = under(page, point)
    turn(page, -200, (0.5, 0.7))
    assert view_box(page)[2] < zoomed[2] and under(page, point) == pytest.approx(before, abs=2)
    zoomed = view_box(page)
    acted(page, lambda: page.keyboard.press('Escape'), must=False)  # letting go of it leaves the view
    assert view_box(page) == pytest.approx(zoomed, rel=1e-6)
    acted(page, lambda: page.set_viewport_size({'width': 1160, 'height': 800}), must=False)  # the zoom is held
    assert mode(page) == 'free' and view_box(page)[2] == pytest.approx(zoomed[2], rel=1e-6)
    page.keyboard.press('/')                              # a digit typed in the search box is a letter of it
    page.wait_for_selector('#search:not([hidden])')
    page.keyboard.type('0')
    page.wait_for_timeout(300)
    assert mode(page) == 'free' and page.input_value('#search .query') == '0'
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.req('VIEW-008')
def test_in_the_small_area_the_view_holds_through_selections_a_drag_and_a_redraw_and_every_move_eases(
        run, web, mapped, browser):
    """The view holds in the small area as in the large one, VIEW-041: zoomed by hand, a run of selections leaves it
    where it is; a drag stops 40 pixels past the map's edge; and the map drawn again as a node arrives keeps the
    zoom."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run, large=False)
    _, at = keys_of(web)
    assert mode(page) == 'full'
    acted(page, lambda: zoomed_to(page, page.evaluate(HEADING)), must=False)
    assert page.evaluate(TEXT_PX) == pytest.approx(page.evaluate(HEADING), abs=1)
    zoom = view_box(page)
    for address in ('code.part.number3', 'code.part.number27', 'code.timer.kitchen', 'code.part.number14'):
        acted(page, lambda address=address: page.evaluate(f'window.metaform.select("{at[address]}")'), must=False)
        assert view_box(page) == pytest.approx(zoom, rel=1e-6), address
    zoom = zoom[2:]
    middle = page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                           ' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; })()')
    page.mouse.move(*middle)                              # the map dragged far to the right
    page.mouse.down()
    page.mouse.move(middle[0] + 4000, middle[1], steps=200)  # short steps, as a hand moves, so it starts in the pane
    page.mouse.up()
    still2d(page)
    assert margins(page)['left'] == pytest.approx(40, abs=1) and view_box(page)[2:] == pytest.approx(zoom, rel=1e-6)
    assert acted(page, lambda: arrives(run, mapped), must=False, until=arrival(page))[2:] == pytest.approx(zoom, rel=1e-6)
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.req('VIEW-008')
def test_a_drag_interrupts_an_eased_2d_camera_move(run, web, mapped, browser):
    """Dragging during an eased move takes the camera away from that move; its remaining frames never pull the view
    back from the place the person dragged it to, VIEW-008's interruptible camera. A selection leaves the 2D view where
    it is, VIEW-041 (`focus2D` in map2d/flow2d.js), so the move is the held zoom eased onto the selection."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run, large=False)
    _, at = keys_of(web)
    heading = page.evaluate(HEADING)
    zoomed_to(page, heading)  # where the map runs past the pane and so can be dragged, VIEW-041
    still2d(page)
    page.evaluate(f'window.metaform.select("{at["code.part.number27"]}")')
    still2d(page)
    page.clock.pause_at(page.evaluate('Date.now()') / 1000 + 1)
    try:
        before = view_box(page)
        zoomed_to(page, heading)  # the same zoom, eased to the selection
        page.clock.run_for(160)
        assert view_box(page) != before  # interrupt a move that has actually begun
        middle = page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                               ' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; })()')
        page.mouse.move(*middle)
        page.mouse.down()
        page.clock.run_for(80)  # the camera can advance while the pointer is held before the drag starts
        visible = view_box(page)
        page.mouse.move(middle[0] + 100, middle[1] + 50, steps=8)
        page.mouse.up()
        dragged = view_box(page)
        scale = visible[2] / page.locator('#viewport').bounding_box()['width']
        assert dragged == pytest.approx([visible[0] - 100 * scale, visible[1] - 50 * scale,
                                        visible[2], visible[3]], abs=1)
        page.clock.run_for(EASE + 200)
        assert view_box(page) == dragged
    finally:
        page.clock.resume()
    assert problems == []


@pytest.mark.req('VIEW-016')
@pytest.mark.req('VIEW-041')
def test_inside_a_node_the_graph_opens_in_full_fit_and_the_map_comes_back_as_it_was_left(run, web, mapped, browser):
    """A node's own graph opened at a size of its own, and the map came back at another. It opens in full fit, the
    whole graph in view, whatever zoom the map was at, VIEW-041; and the map zoomed by hand comes back on the way out
    at the zoom it was left at."""
    from metaform.data import Store
    store = Store('proj')
    for index in range(14):
        store.add_element('notes', f'code.part.number{index}', name_length=2)
        store.add_join('notes', 'code.timer.kitchen', f'code.part.number{index}',
                       purpose='Keep the timer working.', ef='serves the timer')
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    kitchen = at['code.timer.kitchen']
    page.evaluate(f'window.metaform.select("{kitchen}")')
    heading = page.evaluate(HEADING)
    page.keyboard.press('Enter')
    page.wait_for_function('() => window.metaform.inside().length > 14')
    still2d(page)
    assert mode(page) == 'full' and page.evaluate(ALL_IN)
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    zoomed_to(page, heading)
    still2d(page)
    page.keyboard.press('Enter')
    page.wait_for_function('() => window.metaform.inside().length > 14')
    still2d(page)
    assert mode(page) == 'full' and page.evaluate(ALL_IN)
    seen = page.evaluate("""(() => { const view = document.querySelector('#viewport').getBoundingClientRect();
        const node = [...document.querySelectorAll('#map2d svg g.node')].find(g => g.dataset.title === 'dish timer');
        const box = node.getBoundingClientRect();
        return box.left >= view.left && box.right <= view.right && box.top >= view.top && box.bottom <= view.bottom; })()""")
    assert seen  # the node entered is in view
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    still2d(page)
    assert page.evaluate(TEXT_PX) == pytest.approx(heading, abs=1)
    assert problems == []


@pytest.mark.req('VIEW-017')
@pytest.mark.req('VIEW-005')
def test_in_3d_every_item_of_the_layers_turned_on_is_its_own_node_joined_to_its_node_and_what_it_links(
        run, web, mapped, browser):
    """The 3D map shows everything with no drilling, every memory and item its own node, relations
    as links, seen connected together like a brain, as busy as the layers turned on."""
    from metaform.data import Store
    started(run)
    expected, at = keys_of(web)
    kitchen, alarm, tick = at['code.timer.kitchen'], at['code.alarm.audible'], at['code.loop.tick']
    to_alarm = next(join['id'] for join in expected['joins'] if join['receiver'] == kitchen)
    remember(run, mapped, 'create_entities', [entity('countdown drift', 'The countdown drifts under load.')],
             'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('alarm pitch', 'Two kilohertz.')], 'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'alarm pitch', 'relationType': 'drives'}])
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'The tone is too quiet.')], f'join:{to_alarm}')
    remember(run, mapped, 'create_entities', [entity('lost tick', 'One tick can be lost.')], 'element:code.loop.tick')
    Store('proj').add_property('notes', 'code.timer.kitchen', 'ticks at 1 Hz')
    page, problems, _ = opened(browser, web)
    items = lambda: page.evaluate('window.metaform.graph().nodes.filter(node => node.t === "item")')
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.graph().nodes.some(node => node.t === "item")')
    first = page.evaluate('window.metaform.graph()')
    assert sorted(node['text'] for node in items()) == ['keep the loop small', 'ticks at 1 Hz']  # nothing masked,
    # orphaned or hidden; the property hangs from its element like an item
    prop = next(node['id'] for node in items() if node['text'] == 'ticks at 1 Hz')
    assert prop.startswith('r:') and (kitchen, prop, 'item') in {(link['source'], link['target'], link['k'])
                                                                   for link in first['links']}
    set_layer(page, 'memory', True)
    page.wait_for_function('() => window.metaform.loaded() && '
                           'window.metaform.graph().nodes.filter(node => node.layer === "memory").length === 4')
    graph = page.evaluate('window.metaform.graph()')
    memory = {node['text']: node['id'] for node in graph['nodes'] if node['t'] == 'item' and node['layer'] == 'memory'}
    assert sorted(memory) == ['alarm pitch', 'countdown drift', 'lost tick', 'quiet tone']  # each memory its own node
    edges = {(link['source'], link['target'], link['k']) for link in graph['links']}
    assert {(kitchen, memory['countdown drift'], 'item'), (alarm, memory['alarm pitch'], 'item'),
            (kitchen, memory['quiet tone'], 'item'),
            (tick, memory['lost tick'], 'item')} <= edges  # from each element, and from the join's receiver
    assert (memory['countdown drift'], memory['alarm pitch'], 'relation') in edges  # a relation is a link
    page.wait_for_function('() => window.metaform.drawn().nodes === window.metaform.graph().nodes.length')
    page.evaluate(f'window.metaform.click3d("{memory["countdown drift"]}")')
    assert page.text_content('#p-object .eyebrow') == 'Memory'
    assert 'The countdown drifts under load.' in page.inner_text('#p-object')
    set_layer(page, 'memory', False)
    page.wait_for_function('() => window.metaform.loaded() && '
                           '!window.metaform.graph().nodes.some(node => node.layer === "memory")')
    assert problems == []


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_back_and_forward_step_through_the_selected_nodes(run, web, mapped, browser):
    """Alt with Left and Right step back and forward through the nodes selected, as a browser's history does; past
    either end they do nothing, and the browser's own history step on them is held back."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    cook, kitchen, alarm, display = (at[address] for address in (
        'exterior.cook', 'code.timer.kitchen', 'code.alarm.audible', 'code.timer.kitchen.display'))
    selected = lambda: page.evaluate('window.metaform.selected()')
    for key in (cook, kitchen, alarm):
        page.evaluate(f'window.metaform.select("{key}")')
    address = page.url
    map_key(page, 'Alt+ArrowLeft')
    assert selected() == kitchen
    map_key(page, 'Alt+ArrowLeft')
    assert selected() == cook
    map_key(page, 'Alt+ArrowRight')
    assert selected() == kitchen
    page.evaluate(f'window.metaform.select("{display}")')
    map_key(page, 'Alt+ArrowRight')                       # nothing forward of the newest
    assert selected() == display
    map_key(page, 'Alt+ArrowLeft')
    assert selected() == kitchen
    map_key(page, 'Alt+ArrowDown')                        # no other Alt key is the map's
    assert selected() == kitchen and page.url == address
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-012')
def test_pointing_at_a_node_shows_its_name_above_the_node_clear_of_the_pointer(run, web, mapped, browser):
    """Pointing at a node whose name can be read shows its card at the lower left of the map, clear of the pointer, and
    no name at the top left; the card names the node by its kind and address, not again by its name, which its sign
    already shows; the card goes when the pointer leaves."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.wait_for_timeout(2500)
    map_key(page, 'p')  # hold the layout still so the node stays where the pointer goes
    # the kitchen timer's outward sign may stand at a slant too steep to read; facing, it reads from here
    page.evaluate('(() => { const pick = document.querySelector("#signsat"); pick.value = "facing";'
                  ' pick.dispatchEvent(new Event("change")); })()')
    page.wait_for_timeout(300)
    stage = page.locator('#stage').bounding_box()
    kitchen = page.evaluate('(() => { const tag = window.metaform.labels3d().find(label => label.text === "dish timer");'
                            ' return window.metaform.screen3d(tag.id); })()')
    x, y = kitchen['x'], kitchen['y']
    page.mouse.move(x - 40, y - 40)
    page.mouse.move(x, y, steps=4)
    card = page.locator('#card3d.on')
    card.wait_for(state='visible')
    said = card.inner_text()
    assert 'code.timer.kitchen' in said and 'dish timer' not in said, said
    page.wait_for_timeout(400)  # past the moment a name waits to show, `READOUT.settle`
    assert page.evaluate('window.metaform.readout("3d")') is None  # its label can be read, so no name at the top left
    box = card.bounding_box()
    assert box['x'] < stage['x'] + stage['width'] / 2 and box['y'] > stage['y'] + stage['height'] / 2, box  # lower left
    assert not (box['x'] <= x <= box['x'] + box['width'] and box['y'] <= y <= box['y'] + box['height'])  # not under the hand
    page.mouse.move(stage['x'] + stage['width'] - 5, stage['y'] + 5)
    page.wait_for_function('() => !document.querySelector("#card3d").classList.contains("on")')
    assert problems == []


def test_the_3d_layout_is_switched_paused_and_run_again_by_its_keys(run, web, mapped, browser):
    """The 3D map has no bar: 3 switches its layout, said at the 2D map's corner, P pauses and resumes it and R runs
    it again from new places, each said in a toast where a button said it before."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    layout = lambda: page.evaluate("import('/page/app/views/bar.js').then(part => part.PHYS.name)")
    paused = lambda: page.evaluate("import('/page/app/map3d/graph3d.js').then(part => part.LAYOUT.paused)")
    toast = lambda: page.inner_text('#toast')
    assert layout() == 'organic' and page.query_selector('#physicsmenu') is None
    map_key(page, '3')
    assert layout() == 'flat' and page.inner_text('#note2d') == 'Layout: Flat'
    map_key(page, 'p')
    assert paused() is True and 'paused' in toast()
    map_key(page, 'p')
    assert paused() is False and 'runs again' in toast()
    map_key(page, 'p')
    map_key(page, 'r')
    assert paused() is False and 'new places' in toast()
    map_key(page, '3')
    assert layout() == 'organic' and page.inner_text('#note2d') == 'Layout: Organic'
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_an_idle_3d_map_draws_no_frames_until_something_on_it_moves(run, web, mapped, browser):
    """The 3D map drew every frame for as long as the page was open, so a page left alone kept the machine busy. Once
    its layout has settled and nothing on it moves, here with motion reduced so nothing flows or flashes, it draws
    nothing; the pointer on it draws again."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate('window.stillness = null')
    page.wait_for_function(f'() => ({STILL})(() => window.metaform.frames3d())', timeout=60000)  # the layout rests
    drawn = page.evaluate('window.metaform.frames3d()')
    page.wait_for_timeout(1500)
    assert page.evaluate('window.metaform.frames3d()') == drawn  # nothing moves, nothing is drawn
    stage = page.locator('#stage').bounding_box()
    page.mouse.move(stage['x'] + stage['width'] / 2, stage['y'] + stage['height'] / 2)
    page.wait_for_function(f'() => window.metaform.frames3d() > {drawn}', timeout=10000)
    assert problems == []


def test_u_draws_the_3d_map_in_outer_space_keeps_the_choice_and_an_idle_map_still_rests(run, web, mapped, browser):
    """The theme is the one choice of look: Space, the theme the page opens in, draws the 3D map in outer space,
    page/ultra.js, where ultra's own bloom takes the place of the page's. U switches to the last plain theme, drawn
    clean with the page's bloom, and back, and keeps the choice in web_theme, the one look setting since the settings
    cleanup of 2026-10-15. With motion reduced the sky stands still and the map, once it rests, draws nothing, as in
    clean."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')
    posts = []
    page.on('request', lambda sent: posts.append(sent.url) if sent.method == 'POST' else None)
    page.reload()  # it opens in outer space, so with motion reduced from the first frame
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=90000)
    page.evaluate("async () => { window.ultra = await import('/page/ultra.js'); }")
    theme = lambda: next((row['value'], row['state']) for row in api(web, '/api/settings?project=proj')[1]['settings']
                         if row['key'] == 'web_theme')
    look = 'window.ultra.stats().drawn'
    assert page.evaluate('document.documentElement.dataset.theme') == 'space'
    page.wait_for_function(f"() => {look} === 'ultra'")
    page.wait_for_timeout(300)
    # opening the page writes nothing: the setting stays at its default until the person changes the look, VIEW-011
    assert posts == [] and theme() == ('space', 'default')
    stage = page.locator('#stage').bounding_box()
    page.mouse.move(stage['x'] + stage['width'] / 2, stage['y'] + stage['height'] / 2)
    page.keyboard.press('u')
    page.wait_for_function(f"() => {look} === 'clean'")
    assert page.evaluate('document.documentElement.dataset.theme') != 'space'
    assert not page.evaluate('window.ultra.stats().bloom') and page.evaluate('window.metaform.bloom().on')
    page.wait_for_timeout(300)
    assert theme() == (page.evaluate('document.documentElement.dataset.theme'), 'set')  # the person's choice is kept
    page.keyboard.press('u')
    page.wait_for_function(f"() => {look} === 'ultra'")
    shown = page.evaluate('window.ultra.stats()')
    assert shown['bloom'] and shown['stars'] > 0 and not page.evaluate('window.metaform.bloom().on')
    assert page.evaluate('document.documentElement.dataset.theme') == 'space'
    page.wait_for_function("() => document.querySelector('.ultra-veil') && "
                           "getComputedStyle(document.querySelector('.ultra-veil')).opacity === '0'")
    page.wait_for_timeout(300)
    assert theme() == ('space', 'set')
    page.evaluate('window.stillness = null')
    page.wait_for_function(f'() => ({STILL})(() => window.metaform.frames3d())', timeout=60000)
    drawn = page.evaluate('window.metaform.frames3d()')
    page.wait_for_timeout(1500)
    assert page.evaluate('window.metaform.frames3d()') == drawn  # an idle map in outer space rests too
    assert page.evaluate('window.ultra.stats().clock') == 0  # the sky never moved
    page.keyboard.press('?')  # U is in the page's key table, so the reference lists it, with the looks
    page.click('#help .helptabs button:has-text("Visuals")')
    assert 'Space theme' in page.locator('#help .keys').inner_text()
    assert problems == []


def test_web_open_opens_the_board_on_the_persons_page(run, web, mapped, browser):
    """An agent's `web open board` opens the board on the page the person has open, as the act says it did."""
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    assert page.is_hidden('#board')
    said = json.loads(run('web', 'open', 'board', '--json', cwd=mapped).stdout)
    assert said['act'] == 'open' and said['what'] == 'board'
    page.wait_for_selector('#board:not([hidden])', timeout=10000)
    assert problems == []


def test_web_open_of_a_ticket_not_on_the_map_fails_with_the_pages_words(run, web, mapped, browser):
    """`web open` waits for the page: a ticket the map does not hold is refused in the page's words with a non-zero
    exit, where it answered success and opened nothing; the board still opens. With the workspace on in its default,
    classic layout, a real pane opens and an unknown one is refused."""
    run('set', '--web-panes')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.workspace.layout() !== null', timeout=10000)
    refused = run('web', 'open', 'ticket', 'id=nope-0000', '--json', cwd=mapped, ok=False)
    assert refused.returncode != 0 and 'No ticket nope-0000' in refused.stdout + refused.stderr
    said = run('web', 'open', 'board', '--json', cwd=mapped)
    assert json.loads(said.stdout)['what'] == 'board'
    page.wait_for_selector('#board:not([hidden])', timeout=10000)
    pane = run('web', 'open', 'pane', 'id=map.messages', '--json', cwd=mapped)
    assert json.loads(pane.stdout)['done'] is True
    assert page.evaluate("window.metaform.workspace.shown('map.messages')")
    unknown = run('web', 'open', 'pane', 'id=nope', cwd=mapped, ok=False)
    assert unknown.returncode != 0 and 'No pane nope' in unknown.stdout + unknown.stderr
    assert problems == []


def test_web_open_with_two_pages_succeeds_when_one_refuses_and_fails_when_both_do(run, web, mapped, browser):
    """With two pages open, one opened before the workspace was turned on, `web open` of a pane succeeds when the
    other page opens it, whichever answers first; a pane neither page has is refused in a page's words."""
    started(run)
    opened(browser, web, plain=True)
    run('web', 'stop')
    run('set', '--web-panes')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.workspace.layout() !== null', timeout=10000)
    pane = run('web', 'open', 'pane', 'id=map.messages', '--json', cwd=mapped)
    assert json.loads(pane.stdout)['done'] is True
    assert page.evaluate("window.metaform.workspace.shown('map.messages')")
    unknown = run('web', 'open', 'pane', 'id=nope', cwd=mapped, ok=False)
    assert unknown.returncode != 0 and 'No pane nope' in unknown.stdout + unknown.stderr
    assert problems == []


def test_a_refused_permission_answer_or_resume_gives_the_person_its_buttons_back(run, web, mapped, browser):
    """When the server refuses the person's answer to a permission prompt, or a Resume, the buttons are enabled again
    and none stays marked chosen, so the person can try again."""
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    refused = lambda route: route.fulfill(status=400, content_type='application/json', body='{"error": "Refused."}')
    page.route('**/api/dispatch-permit', refused)
    page.route('**/api/dispatch-resume', refused)
    page.evaluate('''async () => {
        const {permissionCard} = await import('/page/app/session/tools.js');
        const {drawSession} = await import('/page/app/session/text.js');
        const card = permissionCard({data: {request: 'r1', title: 'write a file', options: [
            {option_id: 'allow', name: 'Allow once', kind: 'allow_once'},
            {option_id: 'reject', name: 'Reject', kind: 'reject_once'}]}}, 'w1', 'div', 'claude');
        card.id = 'permitcheck';
        const bar = document.createElement('div');
        bar.id = 'resumecheck';
        document.body.append(card, bar);
        drawSession(bar, {work: 'w1', session: {session_id: 's1', state: 'ended', agent: 'claude'},
            state: {capabilities: {load: true}}});
    }''')
    page.click('#permitcheck button[data-option="allow"]')
    page.wait_for_function('''() => [...document.querySelectorAll('#permitcheck .answers button')]
        .every(button => !button.disabled && !button.classList.contains('chosen'))''', timeout=10000)
    assert page.is_visible('#permitcheck.waiting')
    page.click('#resumecheck button.resume')
    page.wait_for_function('() => !document.querySelector("#resumecheck button.resume").disabled', timeout=10000)
    refusal = 'Failed to load resource: the server responded with a status of 400 (Bad Request)'
    assert problems == [refusal, refusal], problems


@pytest.mark.req('VIEW-008')
def test_selecting_a_node_turns_the_3d_map_to_it_and_comes_in_close(run, web, mapped, browser):
    """Selection turns to the node with its sign at the default half-panel width. Whole returns to the map while
    keeping the selected node marked."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    cook = at['exterior.cook']
    still3d(page, 1)
    map_key(page, 'p')  # the layout held, so what is read is where the camera put it
    observe_met_sign(page)
    page.evaluate(f'window.metaform.click3d("{cook}")')
    page.wait_for_function(f'() => window.metaform.selected() === "{cook}"')
    assert_met_sign_share(page, 0.5)
    stage = page.locator('#stage').bounding_box()
    seen = page.evaluate(f'window.metaform.screen3d("{cook}")')
    off = math.hypot(seen['x'] - stage['x'] - stage['width'] / 2, seen['y'] - stage['y'] - stage['height'] / 2)
    assert off < 0.1 * min(stage['width'], stage['height']), (seen, stage)
    page.evaluate('window.metaform.mode3d("whole")')
    still(page, '() => window.metaform.away3d()')
    assert mode3d(page) == 'whole'
    assert page.is_hidden('#stage .metsign')
    assert page.evaluate('window.metaform.selected()') == cook
    assert problems == []


# The modules are loaded once, `PIVOT_PARTS`, so a wait reads them in a plain function: a wait on a promise ends as soon as
# it settles, even to false, `still`.
PIVOT_PARTS = '''async () => { window.pivotParts = {G: (await import('/page/app/map3d/graph3d.js')).G,
    FLIGHT: (await import('/page/app/camera/flight.js')).FLIGHT}; }'''
PIVOT_STATE = '''id => { const {G, FLIGHT} = window.pivotParts;
    const t = G.controls().target, c = G.camera().position, n = G.graphData().nodes.find(node => node.id === id);
    return {off: Math.hypot(t.x - n.x, t.y - n.y, t.z - n.z) / c.distanceTo(t), target: [t.x, t.y, t.z],
        away: c.distanceTo(t), turn: Math.atan2(c.x - t.x, c.z - t.z), cursor: G.controls().zoomToCursor,
        flying: FLIGHT.on}; }'''


@pytest.mark.req('VIEW-005')
def test_the_3d_map_turns_and_zooms_about_the_selected_node(run, web, mapped, browser):
    """After a selection's flight the point the camera turns about is the node's centre, not its sign: the wheel with
    the pointer off the node zooms along the line to it, a drag turns the map round it with the node held still on the
    screen, and the layout moving the node takes the point with it. With nothing selected the wheel zooms toward the
    pointer again."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    cook = at['exterior.cook']
    still3d(page, 1)
    map_key(page, 'p')  # the layout held, so the name is read where the camera put it; `pin3d` moves the node below
    observe_met_sign(page)
    page.evaluate(PIVOT_PARTS)
    page.evaluate(f'window.metaform.click3d("{cook}")')
    page.wait_for_function(f'() => window.metaform.selected() === "{cook}"')
    assert_met_sign_share(page, 0.5)  # the name framed as before, VIEW-005
    page.wait_for_function(f'() => (({PIVOT_STATE})("{cook}")).off < 1e-3 && !window.pivotParts.FLIGHT.on')
    assert page.evaluate(PIVOT_STATE, cook)['cursor'] is False
    stage = page.locator('#stage').bounding_box()
    aside = stage['x'] + stage['width'] * 0.2, stage['y'] + stage['height'] * 0.25  # off the node
    page.mouse.move(*aside)
    for delta in (-300, 300, 300):
        page.mouse.wheel(0, delta)
        still(page, '() => window.metaform.away3d()')
        assert page.evaluate(PIVOT_STATE, cook)['off'] < 1e-3
    seen, turn = page.evaluate(f'window.metaform.screen3d("{cook}")'), page.evaluate(PIVOT_STATE, cook)['turn']
    corner = stage['x'] + stage['width'] * 0.92, stage['y'] + stage['height'] * 0.12  # empty, so no node is dragged
    page.mouse.move(*corner)
    page.mouse.down()
    page.mouse.move(corner[0] - 150, corner[1] + 20, steps=10)
    page.mouse.up()
    still(page, '() => window.metaform.away3d() + window.metaform.cameraAt().turn')
    turned = page.evaluate(PIVOT_STATE, cook)
    assert abs(turned['turn'] - turn) > 0.1 and turned['off'] < 1e-3, turned  # the map turned, round the node
    now = page.evaluate(f'window.metaform.screen3d("{cook}")')
    assert math.hypot(now['x'] - seen['x'], now['y'] - seen['y']) < 2, (seen, now)
    page.evaluate(f'window.metaform.pin3d("{cook}", 40, -30, 20)')  # the layout moves the node
    page.wait_for_function('() => Math.abs(window.pivotParts.G.controls().target.x - 40) < 1e-3')
    assert page.evaluate(PIVOT_STATE, cook)['off'] < 1e-3
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.selected() === null')
    page.wait_for_function('() => window.pivotParts.G.controls().zoomToCursor')
    left = page.evaluate(PIVOT_STATE, cook)
    page.mouse.move(*aside)
    page.mouse.wheel(0, -300)
    still(page, '() => window.metaform.away3d()')
    after = page.evaluate(PIVOT_STATE, cook)
    assert math.dist(after['target'], left['target']) > 0.01 * left['away'], (left, after)  # toward the pointer
    # a hand that takes the camera during the selection's flight: the flight never arrives, and the map turns about
    # the node from where the hand took it
    page.evaluate(f'window.metaform.click3d("{cook}")')
    page.wait_for_function('() => window.pivotParts.FLIGHT.on')
    page.mouse.move(*corner)
    page.mouse.down()
    page.mouse.move(corner[0] - 60, corner[1] + 10, steps=4)
    page.mouse.up()
    page.wait_for_function(f'() => (({PIVOT_STATE})("{cook}")).off < 1e-3')
    assert page.evaluate(PIVOT_STATE, cook)['cursor'] is False
    assert problems == []


def observe_met_sign(page):
    """Read the actual sign drawn on the overlay, whose canvas itself covers the whole panel."""
    page.evaluate('''() => {
        const draw = CanvasRenderingContext2D.prototype.drawImage;
        CanvasRenderingContext2D.prototype.drawImage = function (...args) {
            if (this.canvas.matches('#stage .metsign') && args.length === 5)
                window.metSignDrawn = {left: args[1], top: args[2], width: args[3], height: args[4],
                    selected: window.metaform.selected()};
            return draw.apply(this, args);
        };
    }''')


def assert_met_sign_fits(page):
    """In the small area the selected name is flown to four fifths of the pane's width, or fitted to its height with a
    margin where it would be taller than the pane, every line in view, VIEW-005."""
    page.wait_for_function("""() => { const sign = document.querySelector('#stage .metsign'), drawn = window.metSignDrawn;
        return sign && !sign.hidden && drawn && drawn.selected === window.metaform.selected(); }""")
    still(page, '() => JSON.stringify(window.metSignDrawn)')
    sign = page.evaluate('window.metSignDrawn')
    stage = page.locator('#stage').bounding_box()
    assert 0 < sign['left'] and sign['left'] + sign['width'] < stage['width'], (sign, stage)
    assert 0 < sign['top'] and sign['top'] + sign['height'] < stage['height'], (sign, stage)
    # four fifths of the pane's width, or, where that would be taller than the pane, its height less a margin
    assert sign['width'] / stage['width'] == pytest.approx(0.8, abs=0.015) and sign['height'] <= 0.86 * stage['height'] \
        or sign['height'] / stage['height'] == pytest.approx(0.85, abs=0.015), (sign, stage)


def assert_met_sign_share(page, share):
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    try:
        # Swapping defers its camera fit until after layout, so a still old drawing is not arrival.
        page.wait_for_function('''share => {
            const sign = document.querySelector('#stage .metsign'), drawn = window.metSignDrawn;
            return sign && !sign.hidden && drawn && drawn.selected === window.metaform.selected()
                && Math.abs(drawn.width / document.querySelector('#stage').getBoundingClientRect().width - share) < 0.015;
        }''', arg=share)
    except PlaywrightTimeoutError:
        pytest.fail(f"Selected sign never reached {share}: " + str(page.evaluate('''() => ({
            selected: window.metaform.selected(), drawn: window.metSignDrawn,
            hidden: document.querySelector('#stage .metsign')?.hidden,
            panel: document.querySelector('#stage').getBoundingClientRect().toJSON()
        })''')))
    still(page, '() => JSON.stringify(window.metSignDrawn)')
    sign = page.evaluate('window.metSignDrawn')
    stage = page.locator('#stage').bounding_box()
    assert sign['width'] / stage['width'] == pytest.approx(share, abs=0.015), (sign, stage)
    assert sign['left'] == pytest.approx((stage['width'] - sign['width']) / 2, abs=2), (sign, stage)
    assert 0 < sign['left'] < sign['left'] + sign['width'] < stage['width'], (sign, stage)


@pytest.mark.req('VIEW-005')
def test_3d_selection_frames_different_names_and_join_titles_at_the_chosen_width(run, web, mapped, browser):
    """Name length and node position must not decide how much of the panel a selected sign consumes."""
    started(run)
    page, problems, _ = opened(browser, web)
    graph, at = keys_of(web)
    still3d(page, 1)
    map_key(page, 'p')
    observe_met_sign(page)
    names = [at[address] for address in ('exterior.cook', 'code.loop.tick')]
    join = 'p:' + next(join['id'] for join in graph['joins'] if join['receiver'] == names[0])
    for key in [*names, join]:
        page.evaluate('key => window.metaform.select(key)', key)
        assert_met_sign_share(page, 0.5)
    # Work, the mode it opens in, meets a node nobody works on at the half; 1 steps to the zoom's quarter, half and three
    # quarters, then back to Work, `zoomKey` in keys/walk.js
    for share in (0.25, 0.5, 0.75):
        page.keyboard.press('1')
        assert_met_sign_share(page, share)
        page.evaluate('key => window.metaform.select(key)', names[0])
        assert_met_sign_share(page, share)
        page.evaluate('key => window.metaform.select(key)', names[1])
        assert_met_sign_share(page, share)
        if share == 0.25:  # F frames the whole map once and leaves the mode, Zoom, as it is
            assert mode3d(page) == 'zoom'
            map_key(page, 'f')
            still(page, '() => window.metaform.away3d()')
            assert mode3d(page) == 'zoom'
            assert page.is_hidden('#stage .metsign')
            page.evaluate('window.metaform.mode3d("zoom")')
            assert_met_sign_share(page, share)
            assert mode3d(page) == 'zoom'
    page.keyboard.press('1')
    assert mode3d(page) == 'work' and page.inner_text('#note2d') == '3D camera: the work in view'
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-008')
def test_3d_zoom_keys_belong_to_the_large_map_and_yield_to_fields_and_windows(run, web, mapped, browser):
    """1 steps the large 3D map's zoom, the selected name a quarter, a half or three quarters of its width, each
    press said at the 2D map's corner; a window or a text field takes the key; the small area takes no zoom and
    always meets a selection at four fifths, node zoom on or off, VIEW-005."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    still3d(page, 1)
    map_key(page, 'p')
    observe_met_sign(page)
    page.evaluate('key => window.metaform.select(key)', at['exterior.cook'])
    page.keyboard.press('1')  # from Work, the mode it opens in, to the zoom's quarter
    assert_met_sign_share(page, 0.25)
    assert page.inner_text('#note2d') == '3D zoom: 1/4'
    page.keyboard.press('?')
    page.wait_for_selector('#help:not([hidden])')
    page.keyboard.press('1')
    page.keyboard.press('Escape')
    assert_met_sign_share(page, 0.25)
    page.click('#searchBtn')
    page.locator('#search .query').fill('')
    page.keyboard.press('1')
    assert page.locator('#search .query').input_value() == '1'
    page.keyboard.press('Escape')
    assert_met_sign_share(page, 0.25)
    map_key(page, 's')
    assert_met_sign_fits(page)
    for _ in range(3):  # the small area takes no zoom key
        page.keyboard.press('1')
        assert_met_sign_fits(page)
    # with node zoom off the small area still meets each selection at four fifths
    page.evaluate("import('/page/app/views/lens.js').then(part => part.toggleNodeZoom(false))")
    page.evaluate('key => window.metaform.select(key)', at['code.loop.tick'])
    assert_met_sign_fits(page)
    page.evaluate("import('/page/app/views/lens.js').then(part => part.toggleNodeZoom(true))")
    page.evaluate('key => window.metaform.select(key)', at['exterior.cook'])
    assert_met_sign_fits(page)
    map_key(page, 's')
    assert_met_sign_share(page, 0.25)
    page.evaluate('key => window.metaform.select(key)', at['code.loop.tick'])
    assert_met_sign_share(page, 0.25)  # ignored keys must not change the large view's next selection
    page.keyboard.press('1')  # on to half the width
    assert_met_sign_share(page, 0.5)
    assert page.inner_text('#note2d') == '3D zoom: 1/2'
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-001')
def test_divider_resizes_the_3d_canvas_and_keeps_the_selected_name_at_its_width_share(run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    _, at = keys_of(web)
    still3d(page, 1)
    map_key(page, 'p')
    observe_met_sign(page)
    page.evaluate('key => window.metaform.select(key)', at['code.loop.tick'])
    assert_met_sign_share(page, 0.5)

    def drag(selector, dx=0, dy=0):
        handle = page.locator(selector).bounding_box()
        x, y = handle['x'] + handle['width'] / 2, handle['y'] + handle['height'] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + dx, y + dy, steps=5)
        page.mouse.up()

    def width():
        return page.locator('#stage').bounding_box()['width']

    def renderer_fits():
        page.wait_for_function('''() => {
            const panel = document.querySelector('#stage').getBoundingClientRect();
            const drawn = document.querySelector('#stage canvas:not(.metsign)').getBoundingClientRect();
            return Math.abs(panel.width - drawn.width) < 2 && Math.abs(panel.height - drawn.height) < 2;
        }''')

    # the side column opens on the right by default: its edge dragged toward it widens the stage, away narrows it
    side = -1 if page.evaluate("document.querySelector('.app').classList.contains('side-right')") else 1
    original = width()
    drag('#sideSplit', dx=180 * side)
    assert width() < original - 100
    renderer_fits()
    assert_met_sign_share(page, 0.5)
    drag('#sideSplit', dx=-180 * side)
    assert width() == pytest.approx(original, abs=2)
    renderer_fits()
    assert_met_sign_share(page, 0.5)

    map_key(page, 's')
    assert_met_sign_fits(page)
    small = width()
    drag('#sideSplit', dx=120 * side)
    assert width() > small + 80
    renderer_fits()
    assert_met_sign_fits(page)
    drag('#sideSplit', dx=-120 * side)
    assert width() == pytest.approx(small, abs=2)
    renderer_fits()
    assert_met_sign_fits(page)
    drag('#smallSplit', dy=-60)                          # a shorter small area: the name is framed again in it
    renderer_fits()
    assert_met_sign_fits(page)
    assert problems == []


@pytest.mark.req('VIEW-008')
def test_a_long_name_is_cut_in_the_2d_map_at_a_break_between_words_with_an_ellipsis(run, web, mapped, browser):
    """2D labels were cut at 30 characters, mid-word and with nothing to say the name went on."""
    from metaform.data import Store
    name = 'the chime that rings when the timer runs out'
    Store('proj').add_element('notes', 'code.timer.kitchen.chime', name_length=1, name=name)
    started(run)
    page, problems, _ = opened(browser, web)
    label = page.evaluate("""[...document.querySelectorAll('#map2d svg g.node')].map(node => [node.dataset.title,
        [...node.querySelectorAll('tspan.row')].map(row => row.textContent.trim()).join(' ')])
        .find(([title]) => title === 'code.timer.kitchen.chime')[1]""")  # a row for each line Mermaid wraps it to
    assert label.endswith('…') and len(label) <= 30, label
    assert name.startswith(label[:-1]) and name[len(label) - 1] == ' ', label  # whole words only
    assert problems == []


@pytest.mark.req('VIEW-010')
@pytest.mark.req('VIEW-012')
def test_every_element_and_join_of_every_page_is_drawn(run, home, web, mapped, browser, tmp_path):
    from metaform.data import Store
    started(run)
    folder = tmp_path / 'big'
    folder.mkdir()
    run('add', 'project', 'big', str(folder))
    big = Store('big')
    with big.atomic():
        layer = big.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                          provenance=PROVENANCE, ready=True)
        # More elements than one page of /api/graph holds, 500, so the drawing has to take in a second page.
        for group in range(20):
            big.add_element(layer.name, f'code.g{group}', role='SE')
        for n in range(600):
            big.add_element(layer.name, f'code.g{n % 20}.e{n}', role='SE')
        for n in range(10):
            big.add_element(layer.name, f'code.loop.s{n}', role='SE')
        for n in range(600):  # the first ten joins hold a second element each
            held = [f'code.g{(n + 1) % 20}.e{(n + 1) % 600}', *([f'code.loop.s{n}'] if n < 10 else [])]
            big.add_join(layer.name, f'code.g{n % 20}.e{n}', held, purpose='p', ef='f')
        # e0 receives from e1 above; e1 also receives from e0: two joins, two paths, no loop, MAP-002.
        big.add_join(layer.name, 'code.g1.e1', 'code.g0.e0', purpose='q', ef='g')
    from metaform.modules.web import view
    view.keep(view.OWNER, 'web_map_depth', 'all')  # every level: a map past 200 parts opens collapsed at auto
    page, problems, _ = opened(browser, web)
    page.goto(f'http://127.0.0.1:{web}/#p=big')
    page.reload()
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn() '
                           '&& window.metaform.drawn().nodes >= 630', timeout=60000)
    # every element a node and every join its edges, one to each element it holds, and no node of its own; each
    # namespace edge from code.gN to its elements
    assert page.evaluate('window.metaform.drawn()') == {'nodes': 630, 'links': 600 + 601 + 10}
    assert page.inner_text('#count').startswith('630 elements · 601 joins')
    drawn_as_paths(page.evaluate('window.metaform.graph()'), api(web, '/api/graph?project=big&limit=0')[1])
    assert problems == []


# An agent's own process, as a host's MCP server over stdio is: it records one element of the intake and then holds
# it as being recorded until its input closes, as that server ends when its host goes, BASE-039.
RECORDING_AGENT = """
import contextlib, io, sys
from metaform import cli, shown
shown.serving()
with contextlib.redirect_stdout(io.StringIO()):
    try:
        cli.main(['intake', 'element', *sys.argv[1:]])
    except SystemExit:
        pass
print('recording', flush=True)
sys.stdin.read()
"""


def recording_agent(home, folder, *element):
    """A stand-in for an intake agent's own process, recording `element` and holding the intake until it is ended."""
    import os
    agent = subprocess.Popen([sys.executable, '-c', RECORDING_AGENT, *element], cwd=folder, text=True,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**os.environ, 'METAFORM_HOME': str(home)})
    assert agent.stdout is not None and agent.stdout.readline().strip() == 'recording'
    return agent


def ended(agent):
    """The stand-in agent's process ended, as its host going ends it."""
    agent.stdin.close()
    agent.wait(30)


@pytest.mark.req('VIEW-005')
@pytest.mark.req('BASE-039')
def test_an_intake_being_recorded_is_drawn_live_as_each_object_arrives(run, home, web, browser, tmp_path):
    """The page reacts to the intake's records as they happen, then shows the finished map."""
    started(run)
    folder = tmp_path / 'live'
    folder.mkdir()
    run('add', 'project', 'live', str(folder))
    run('intake', 'start', cwd=folder)
    agent = recording_agent(home, folder, 'stakeholder.cook.home', 'role=CQU')  # an agent records it now
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems, asked = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda sent: asked.append(sent.url) if '/api/' in sent.url else None)
    page.goto(f'http://127.0.0.1:{web}/#p=live')
    page.wait_for_function('() => window.metaform && window.metaform.drawn() && window.metaform.drawn().nodes === 1',
                           timeout=30000)
    assert page.evaluate('window.metaform.live()') is not None
    assert 'intake being recorded' in page.inner_text('#count')
    page.evaluate('''() => { window.toasts = [];  // every message the page shows, however briefly
        new MutationObserver(() => window.toasts.push(document.querySelector('#toast').textContent))
            .observe(document.querySelector('#toast'), {childList: true, characterData: true, subtree: true}); }''')
    page.wait_for_function('() => window.metaform.loaded()')
    for _ in range(30):  # the first reads settle, however long a loaded machine takes over them
        asked.clear()
        page.wait_for_timeout(700)
        if not asked:
            break
    page.wait_for_timeout(3000)  # nothing happens: a page that is told asks nothing, QUAL-015
    assert asked == []
    run('intake', 'purpose', 'stakeholder.cook.home', '["code.timer.kitchen"]', 'purpose=p', 'ef=f', cwd=folder)
    # pushed, not waited for: the join is an edge, the timer it holds a node
    page.wait_for_function('() => window.metaform.drawn().nodes === 2 && window.metaform.drawn().links === 1',
                           timeout=1500)
    page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length === 2', timeout=15000)
    page.wait_for_timeout(300)  # the panel's reads for the selected node settle
    assert not [text for text in page.evaluate('window.toasts') if 'Nothing for' in text]  # an unfinished layer is no error
    run('intake', 'element', 'code.loop.tick', 'role=SE', cwd=folder)
    page.wait_for_function('() => window.metaform.drawn().nodes === 3', timeout=15000)
    run('intake', 'purpose', 'stakeholder.cook.home', '["code.timer.kitchen", "code.loop.tick"]',
        cwd=folder)  # annealed into the cook's join, the join that holds the kitchen timer
    page.wait_for_function('() => window.metaform.drawn().links === 2', timeout=15000)  # an edge to each
    run('intake', 'finish', cwd=folder)
    page.wait_for_function('() => window.metaform.live() === null', timeout=15000)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes === 3', timeout=15000)
    assert 'intake being recorded' not in page.inner_text('#count')
    ended(agent)
    drawn_as_paths(page.evaluate('window.metaform.graph()'), api(web, '/api/graph?project=live&limit=0')[1])
    assert problems == []  # the console stayed clean through the whole intake: no read that could only find nothing


@pytest.mark.req('BASE-039')
@pytest.mark.req('VIEW-045')
def test_an_intake_left_unfinished_is_never_shown_as_recorded_and_offers_resume_finish_and_discard(
        run, home, web, browser, tmp_path, dispatch_runners):
    """An intake no agent records any more was left unfinished: no bar says it is being recorded, and one notice offers
    Resume, Finish and Discard, its × putting it away for good. The bar of an intake an agent records goes the moment
    that agent's process ends, and has a × of its own."""
    folder, log = tmp_path / 'left', tmp_path / 'fake.jsonl'
    folder.mkdir()
    run('add', 'project', 'left', str(folder))
    run('enable', 'dispatch')
    run('intake', 'start', cwd=folder)
    for address in ('code.timer.kitchen', 'code.alarm.audible'):
        run('intake', 'element', address, 'role=DE', cwd=folder)  # commands only: no agent records it now
    run('web', '--json', env={'FAKE_ACP_LOG': str(log)})
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.goto(f'http://127.0.0.1:{web}/#p=left')
    page.wait_for_selector('#intakeLeft', timeout=60000)
    assert 'left unfinished' in page.inner_text('#intakeLeft') and '2 parts' in page.inner_text('#intakeLeft')
    assert page.is_hidden('#intakeBar') and page.evaluate('window.metaform.live()') is None  # never followed
    page.click('#intakeLeft .x')                                        # put away for good
    page.wait_for_selector('#intakeLeft', state='detached')
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=60000)
    page.wait_for_timeout(500)
    assert page.locator('#intakeLeft').count() == 0
    page.evaluate('() => Object.keys(localStorage).filter(key => key.startsWith("metaform.intake-left."))'
                  '.forEach(key => localStorage.removeItem(key))')
    page.reload()
    page.wait_for_selector('#intakeLeft', timeout=60000)
    page.click('#intakeLeft button:has-text("Resume")')                # Resume: an agent that goes on with it
    page.wait_for_selector('#intake:not([hidden])')
    assert page.inner_text('#intake .start') == 'Take over the intake'
    choose_agent(page, '#intake', 'claude')
    with page.expect_response(lambda response: '/api/dispatch-intake' in response.url) as answered:
        page.click('#intake .start')
    resumed = answered.value.json()
    dispatch_runners.append((resumed, folder, log))
    assert resumed['work_id'].startswith('intake-'), resumed
    page.wait_for_selector('#intakeBar:not([hidden]):has-text("Claude Code")', timeout=30000)
    assert page.locator('#intakeLeft').count() == 0                     # its agent runs, so it is no longer left
    deadline = time.monotonic() + 30  # its runner makes its session a moment after the start answers
    while run('dispatch', 'stop', resumed['work_id'], cwd=folder, ok=False).returncode and time.monotonic() < deadline:
        time.sleep(0.2)
    page.wait_for_selector('#intakeLeft', timeout=30000)                # stopped before recording: left again
    page.wait_for_selector('#intakeBar', state='hidden')
    agent = recording_agent(home, folder, 'code.light.oven', 'role=DE')  # an agent outside the page goes on with it
    page.wait_for_selector('#intakeBar:not([hidden]):has-text("outside the page")', timeout=30000)
    assert page.locator('#intakeLeft').count() == 0
    ended(agent)                                                        # its agent goes
    began = time.monotonic()
    page.wait_for_selector('#intakeBar', state='hidden', timeout=5000)
    assert time.monotonic() - began < 2, time.monotonic() - began       # the page is told; nothing polls
    page.wait_for_selector('#intakeLeft', timeout=5000)
    assert '3 parts' in page.inner_text('#intakeLeft') and page.evaluate('window.metaform.live()') is None
    agent = recording_agent(home, folder, 'code.clock.wall', 'role=DE')
    page.wait_for_selector('#intakeBar:not([hidden])', timeout=30000)
    page.click('#intakeBar .x')                                         # the bar's own ×
    page.wait_for_selector('#intakeBar', state='hidden')
    ended(agent)
    page.wait_for_selector('#intakeLeft', timeout=5000)
    page.click('#intakeLeft button:has-text("Discard")')               # Discard, after one confirmation
    page.click('#confirm .keep')
    assert page.locator('#intakeLeft').count() == 1
    page.click('#intakeLeft button:has-text("Discard")')
    with page.expect_response(lambda response: '/api/intake-discard' in response.url) as answered:
        page.click('#confirm button.confirm')
    assert answered.value.ok, answered.value.json()
    page.wait_for_selector('#intakeLeft', state='detached', timeout=30000)
    assert api(web, '/api/intake-building?project=left')[1]['results'] == []
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=folder)  # a new one, left at once
    page.wait_for_selector('#intakeLeft', timeout=30000)
    with page.expect_response(lambda response: '/api/intake-finish' in response.url) as answered:
        page.click('#intakeLeft button:has-text("Finish")')            # Finish, with what it recorded
    assert answered.value.ok, answered.value.json()
    page.wait_for_selector('#intakeLeft', state='detached', timeout=30000)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes === 1', timeout=30000)
    assert api(web, '/api/has-intake?project=left')[1] is True
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('BASE-039')
def test_following_a_new_intake_with_nothing_recorded_clears_the_panel_of_the_earlier_metaform(run, home, web,
                                                                                               browser, tmp_path,
                                                                                               dispatch_runners):
    """Following a new intake, the map was redrawn and the panel kept the earlier metaform's element. A finished
    intake's project opens a new intake base when new shape is recorded, so the first part recorded opens it."""
    started(run)
    folder = tmp_path / 'again'
    folder.mkdir()
    run('add', 'project', 'again', str(folder))
    run('intake', 'start', cwd=folder)
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=folder)
    run('intake', 'finish', cwd=folder)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.goto(f'http://127.0.0.1:{web}/#p=again')
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.drawn() '
                           '&& window.metaform.drawn().nodes === 1', timeout=30000)
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("code.timer.kitchen")',
                           timeout=15000)
    agent = intake_agent(run, folder, tmp_path / 'fake.jsonl', dispatch_runners, 'map=new', 'name=alarm')
    run('intake', 'start', 'name=alarm', cwd=folder, env=agent)  # a named intake: the new intake base opens
    run('intake', 'element', 'code.alarm.audible', 'role=SE', cwd=folder, env=agent)
    page.wait_for_function('() => window.metaform.live() !== null', timeout=15000)
    # UX review round 1, 2026-10-17 (agent-identity-handoff F8): an intake in a base of its own no longer swaps the
    # whole page to it; the base list offers it, and the page follows it once the person shows it
    page.wait_for_function('() => document.querySelectorAll("#mf option").length === 2', timeout=15000)
    assert page.evaluate('window.metaform.drawn().nodes') == 1
    assert 'code.timer.kitchen' in page.inner_text('#p-object'), 'the map shown stays as it was'
    page.select_option('#mf', page.evaluate('[...document.querySelectorAll("#mf option")].find(o => !o.selected).value'))
    page.wait_for_function('() => window.metaform.drawn().nodes === 1', timeout=15000)
    page.wait_for_function('() => !document.querySelector("#p-object").innerText.includes("code.timer.kitchen")',
                           timeout=10000)  # once the panel's reads settle
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('QUAL-016')
@pytest.mark.req('BASE-019')
def test_a_module_that_writes_to_the_map_is_seen_live_as_hello_greetings_appear_in_3d(run, web, mapped, browser):
    """A capability added for a feature gets a demonstration in hello; here a greeting,
    written by a module that is not built into the map, reaches the open page through map.changed."""
    run('enable', 'hello')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    texts = lambda: page.evaluate('window.metaform.graph().nodes.filter(node => node.t === "item").map(node => node.text)')
    assert 'world' not in texts()
    run('hello', 'greet', 'world', cwd=mapped)
    page.click('#layersBtn')
    page.wait_for_selector('#layerlist input[data-layer="hello.greetings"]', timeout=3000)  # pushed to the page;
    set_layer(page, 'hello.greetings', True)  # the folder's layers leave the new layer off
    page.wait_for_function('() => window.metaform.graph().nodes.some(node => node.t === "item" && node.text === "world")',
                           timeout=3000)
    run('hello', 'greet', 'moon', cwd=mapped)
    page.wait_for_function('() => window.metaform.graph().nodes.some(node => node.t === "item" && node.text === "moon")',
                           timeout=3000)
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('BASE-053')
def test_a_change_to_a_project_no_longer_registered_is_not_pushed_to_the_open_pages(run, home, tmp_path):
    import queue

    from metaform.modules.web.server import Server
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    server = Server('127.0.0.1', 0, 'nonce')
    try:
        page: queue.SimpleQueue = queue.SimpleQueue()
        server.listeners.add(page)
        assert server.changed({'project': 'gone', 'base_id': None}) == 0
        assert page.empty()
        assert server.changed({'project': 'proj', 'base_id': None}) == 1
        assert page.get_nowait() == {'topic': 'map.changed', 'payload': {'project': 'proj', 'base_id': None}}
    finally:
        server.server_close()


@pytest.mark.req('VIEW-018')
@pytest.mark.req('BASE-053')
def test_the_server_hears_a_commands_change_through_the_bases_listener_and_has_no_relay_of_its_own(run, web, mapped,
                                                                                                   home):
    import http.client
    import socket
    import threading

    from metaform.modules import web as module
    started(run)
    assert module.MODULE.subscriptions == (), 'the base relays map.changed to the server; web subscribes to nothing'
    kept = [json.loads(path.read_text(encoding='utf-8')) for path in (home / 'run' / 'listeners').glob('*.json')]
    [listening] = [record for record in kept if record['module'] == 'web']
    heard, ready = [], threading.Event()

    def listen():
        stream = http.client.HTTPConnection('127.0.0.1', web, timeout=10)
        stream.request('GET', '/api/events', headers={'Host': f'127.0.0.1:{web}'})
        answer = stream.getresponse()
        assert answer.getheader('Content-Type', '').startswith('text/event-stream')
        ready.set()
        for line in answer:
            if line.startswith(b'data:'):
                heard.append(json.loads(line[5:]))
                return
    listener = threading.Thread(target=listen, daemon=True)
    listener.start()
    assert ready.wait(10)
    body = json.dumps({'topic': 'map.changed', 'payload': {'project': 'proj', 'layer': 'x'}})
    gone = request(web, '/api/notify', method='POST', body=body, headers={
        'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'})
    assert gone[0] == 404, 'the server takes no event over HTTP'
    with socket.create_connection(('127.0.0.1', listening['port']), timeout=5) as connection:
        connection.sendall(json.dumps({'token': 'guessed', 'topic': 'map.changed',
                                       'payload': {'project': 'proj', 'layer': 'x'}}).encode('utf-8') + b'\n')
        connection.makefile('rb').readline()
    listener.join(1)
    assert heard == [], 'a delivery without the listener\'s token reaches no page'
    run('add', 'base', 'fresh', cwd=mapped)
    listener.join(5)
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'base_id': None}}]


@pytest.mark.req('QUAL-015')
@pytest.mark.req('VIEW-018')
def test_the_page_keeps_no_repeating_timer():
    """No polling, QUAL-015: the page is told what changed, so it holds no timer that repeats; an idle window only
    shows that nothing polled within it."""
    assert 'setInterval' not in page_script()


@pytest.mark.req('QUAL-015')
@pytest.mark.req('VIEW-002')
def test_start_is_told_the_server_is_ready_and_stop_is_told_it_has_gone_without_asking_again(run, home, web,
                                                                                            monkeypatch):
    """No polling, QUAL-015: `start` reads the server's one ready line and `stop` reads the server's stream to its
    end; neither sleeps and asks again. A server that ends before it listens is reported at once, not at a limit."""
    from metaform import module, settings
    from metaform.modules import web as gui

    def never(seconds):
        raise AssertionError(f'the web module slept {seconds} s and asked again')
    monkeypatch.setattr(time, 'sleep', never)
    ctx = module.Context(module='web', folder=Path(str(home)))
    assert settings.value('web_port', ctx.folder) == web
    assert gui.start(ctx) == {'state': 'started', 'address': f'http://127.0.0.1:{web}/'}
    assert gui.start(ctx) == {'state': 'running', 'address': f'http://127.0.0.1:{web}/'}
    assert gui.stop(ctx) == {'state': 'stopped'}
    assert refused('127.0.0.1', web)
    assert gui.stop(ctx) == {'state': 'not running'}
    held = socket.socket()
    held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    held.bind(('127.0.0.1', web))
    held.listen()
    try:
        monkeypatch.setattr(gui, 'check_free', lambda bind, port: None)
        began = time.monotonic()
        with pytest.raises(gui.Stop) as failed:
            gui.start(ctx)
    finally:
        held.close()
    assert 'did not start' in str(failed.value) and time.monotonic() - began < gui.WAIT / 2


@pytest.mark.req('QUAL-015')
@pytest.mark.req('VIEW-002')
def test_the_server_loop_wakes_only_for_a_connection_and_the_module_never_sleeps(home, monkeypatch):
    """The real server, run by the module's own `main`: the standard library's loop runs `service_actions` on every
    wake, whether a connection or a timeout woke it, so a run with no connection that counts no wake shows the loop
    waits with no timeout, however that is written. The stop signal ends the process, so nothing checks for shutdown.
    A sleep elsewhere in the module has many spellings and its other paths, the launcher's wait for the ready line
    and stop, do not run inside one server run, so the source is read for `time.sleep` beside this."""
    import threading

    from metaform.modules import web as gui
    from metaform.modules.web import server as served
    wakes: list[float] = []
    woke, started = threading.Event(), threading.Event()
    instances: list[served.Server] = []

    class Counted(served.Server):
        def __init__(self, *args):
            super().__init__(*args)
            instances.append(self)

        def service_actions(self):
            wakes.append(time.monotonic())
            woke.set()

    monkeypatch.setattr(served, 'Server', Counted)
    monkeypatch.setattr(served, 'ready', lambda server: started.set())
    serving = threading.Thread(target=served.main, args=(['--bind', '127.0.0.1', '--port', '0', '--nonce', 'n'],),
                               daemon=True)
    serving.start()
    assert started.wait(10)
    [server] = instances
    assert not woke.wait(1.5) and wakes == []
    socket.create_connection(('127.0.0.1', server.port), timeout=5).close()
    assert woke.wait(5) and len(wakes) == 1
    stopping = threading.Thread(target=server.shutdown, daemon=True)
    stopping.start()
    try:  # a connection wakes the loop to see the shutdown; one the closing server refuses is as good
        socket.create_connection(('127.0.0.1', server.port), timeout=5).close()
    except OSError:
        pass
    serving.join(10)
    assert not serving.is_alive()
    assert 'time.sleep' not in Path(gui.__file__).read_text(encoding='utf-8')
    assert 'time.sleep' not in Path(served.__file__).read_text(encoding='utf-8')


@pytest.mark.req('VIEW-002')
def test_the_log_dates_each_start_stop_and_error_and_leaves_out_pages_that_went_away(home, monkeypatch, capsys):
    """The log alone says when the server started and stopped and what failed. A page that closed while it was
    answered is no fault of the server, so it writes nothing; before, each one left a traceback that buried the one
    error that ended the server."""
    import os
    import re
    import threading

    from metaform.modules.web import server as served
    instances: list[served.Server] = []
    started = threading.Event()
    failures: list[Exception] = [ConnectionResetError(), BrokenPipeError(), ConnectionAbortedError(),
                                 ZeroDivisionError('not a page going away')]

    class Kept(served.Server):
        def __init__(self, *args):
            super().__init__(*args)
            instances.append(self)

    def failing(self, method):
        raise failures.pop(0)

    monkeypatch.setattr(served, 'Server', Kept)
    monkeypatch.setattr(served, 'ready', lambda server: started.set())
    monkeypatch.setattr(served.Handler, 'route', failing)
    serving = threading.Thread(target=served.main, args=(['--bind', '127.0.0.1', '--port', '0', '--nonce', 'n'],),
                               daemon=True)
    serving.start()
    assert started.wait(10)
    [server] = instances
    for index in range(4):
        with socket.create_connection(('127.0.0.1', server.port), timeout=5) as asking:
            asking.sendall(f'GET /api/projects HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n\r\n'.encode())
            answer = asking.recv(4096)
            if index < 3:
                assert answer == b''  # a disconnected request is closed without a fabricated 500
            else:
                assert b'500 Internal Server Error' in answer
    threading.Thread(target=server.shutdown, daemon=True).start()
    serving.join(10)
    log = capsys.readouterr().err
    stamp = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00'
    assert re.search(rf'{stamp} Process {os.getpid()} started on port {server.port}, code \w{{12}}, schema version '
                     rf'{served.SCHEMA_VERSION}\n', log)
    assert re.search(rf'{stamp} Fault answering GET /api/projects:.*ZeroDivisionError: not a page going away\n',
                     log, re.DOTALL)
    assert re.search(rf'{stamp} Process {os.getpid()} stopped\n', log)
    assert not re.search('ConnectionResetError|BrokenPipeError|ConnectionAbortedError', log)


@pytest.mark.req('VIEW-018')
@pytest.mark.req('QUAL-015')
def test_a_new_metaform_an_activation_and_a_memory_reach_the_open_page_without_a_reload(run, web, mapped, browser):
    """Clearing the project left the page on data that no longer existed until the page was refreshed. Any
    command that changes the map is announced by the chassis, so the page follows it."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes > 0')
    whole = page.evaluate('window.metaform.drawn().nodes')
    options = 'document.querySelectorAll("#mf option")'
    run('add', 'base', 'fresh', cwd=mapped)
    page.wait_for_function(f'() => [...{options}].some(o => o.selected && o.textContent === "fresh · active")',
                           timeout=3000)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes === 0', timeout=5000)
    run('activate', 'base', 'main', cwd=mapped)
    page.wait_for_function(f'() => [...{options}].some(o => o.selected && o.textContent === "main · active")',
                           timeout=3000)
    page.wait_for_function(f'() => window.metaform.loaded() && window.metaform.drawn().nodes === {whole}',
                           timeout=5000)  # the whole map again, redrawn from the reads
    remember(run, mapped, 'create_entities', [entity('drift', 'Drifts under load.')], 'element:code.timer.kitchen')
    page.click('#layersBtn')
    page.wait_for_selector('#layerlist input[data-layer="memory"]', timeout=3000)
    assert problems == []


@pytest.mark.req('VIEW-013')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('STORE-044')
def test_prompts_are_read_and_an_edit_is_saved_as_a_new_version_only_from_the_gui(run, web, mapped):
    from metaform.data import Store, prompts
    prompts.add_prompt('practices', 'markdown', 'one\n')
    prompts.add_prompt_version('practices', 'two\n', 1)
    third = prompts.add_prompt_version('practices', 'three\n', 2)
    notes = Store('proj').layer_ref('notes')
    prompts.record_use(third.version_id, 'proj', notes.base_id, notes.id)
    started(run)
    assert [item['name'] for item in api(web, '/api/prompts')[1]['prompts']] == ['practices']
    assert api(web, '/api/prompt?name=practices&number=3')[1]['text'] == 'three\n'
    versions = api(web, '/api/prompt-versions?name=practices')[1]['versions']
    assert [item['number'] for item in versions] == [3, 2, 1]
    assert [use['layer_id'] for use in versions[0]['layers']] == [notes.id] and versions[1]['layers'] == []
    assert api(web, '/api/provenance?project=proj&layer=notes')[1]['prompt_version']['number'] == 3
    body = json.dumps({'name': 'practices', 'text': 'four\n', 'parent': 3})
    as_json = {'Content-Type': 'application/json'}
    assert request(web, '/api/save-prompt', method='POST', body=body,
                   headers={**as_json, 'Origin': 'http://rebound.example'})[0] == 403
    assert prompts.prompt_version('practices').number == 3
    own = {**as_json, 'Origin': f'http://127.0.0.1:{web}'}
    status, saved = api(web, '/api/save-prompt', method='POST', body=body, headers=own)
    assert status == 200 and (saved['number'], saved['parent_id']) == (4, third.version_id)
    assert prompts.prompt_version('practices', 3).text == 'three\n'
    assert api(web, '/api/provenance?project=proj&layer=notes')[1]['prompt_version']['number'] == 3
    status, same = api(web, '/api/save-prompt', method='POST', body=body.replace('"parent": 3', '"parent": 4'),
                       headers=own)
    assert same['number'] == 4 and [notice['where'] for notice in same['notices']] == ['text']


@pytest.mark.req('VIEW-013')
@pytest.mark.req('STORE-044')
def test_every_prompt_an_agent_is_sent_opens_by_role_and_saves_as_plain_text_before_it_was_ever_sent(run, web,
                                                                                                    mapped):
    """UX review round 2, prompt-authoring F2, F3 and F7: the Prompt tab lists each role's prompts on a fresh home,
    the system agent's among them; one never sent opens as its shipped text, version 0, written as plain text; a save
    from it goes through the gate, so what is saved is what is sent, and says what it keeps as written."""
    from metaform import prompt_files
    from metaform.data import prompts
    run('enable', 'dispatch')
    started(run)
    catalog = api(web, '/api/prompt-catalog?project=proj')[1]
    system = next(one for one in catalog['roles'] if one['role'] == 'system')
    assert system['prompts'][0] == 'dispatch:system' and catalog['stored'] == []
    read = api(web, '/api/prompt-versions?name=dispatch:system')[1]
    [shipped] = read['versions']
    assert (shipped['number'], read['written'], read['problem']) == (0, 'plain', None)
    assert '1. Language & Vocabulary' in shipped['plain'] and '<mascot />' in shipped['plain']
    own = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'}
    body = json.dumps({'name': 'dispatch:system', 'text': 'Plans & tickets, as <address>: <task>. <mascot/>',
                       'parent': 0})
    status, saved = api(web, '/api/save-prompt', method='POST', body=body, headers=own)
    assert status == 200 and saved['plain'] == 'Plans & tickets, as <address>: <task>. <mascot />'
    assert saved['said'] == []
    from importlib import resources
    assert prompt_files.served(resources.files('metaform.modules.dispatch'), 'system', project='proj',
                               mascot='M') == 'Plans & tickets, as <address>: <task>. M'
    assert [one.origin for one in prompts.prompt_versions('dispatch:system')] == ['edited', 'shipped']
    refused = json.dumps({'name': 'intake:intake.axiom', 'text': 'x', 'parent': 0})
    status, said = api(web, '/api/save-prompt', method='POST', body=refused, headers=own)
    assert status == 400 and 'never be sent' in said['error']


@pytest.mark.req('VIEW-013')
@pytest.mark.req('VIEW-012')
def test_a_layers_prompt_version_opens_in_the_editor_and_an_edit_saves_as_the_next_version(run, web, mapped,
                                                                                            browser):
    from metaform.data import Store, prompts
    prompts.add_prompt('practices', 'xml', '<practices>\n  <one/>\n</practices>\n')
    prompts.add_prompt_version('practices', '<practices>\n  <two/>\n</practices>\n', 1)
    third = prompts.add_prompt_version('practices', '<practices>\n  <three/>\n</practices>\n', 2)
    notes = Store('proj').layer_ref('notes')
    prompts.record_use(third.version_id, 'proj', notes.base_id, notes.id)
    started(run)
    page, problems, remote = opened(browser, web)
    page.click('#t-prov')
    page.click('#p-prov .layerlist button:has-text("notes")')
    page.click('#p-prov button.open-prompt')
    page.wait_for_function('() => window.metaform.editor() && window.metaform.editor().getValue().includes("three")')
    assert page.evaluate('window.metaform.editor().getValue()') == third.text
    assert page.evaluate('window.metaform.editor().getOption("mode")') == 'xml'
    assert page.locator('#p-prompt .CodeMirror-linenumber').count() >= 3
    assert page.locator('#p-prompt .cm-tag').count() > 0
    assert 'Version 3 made: notes.' in page.text_content('#promptNote')
    page.evaluate('window.metaform.editor().setValue("<practices>\\n  <four/>\\n</practices>\\n")')
    page.evaluate('window.metaform.editor().undo()')
    assert page.evaluate('window.metaform.editor().getValue()') == third.text
    page.evaluate('window.metaform.editor().setValue("<practices>\\n  <four/>\\n</practices>\\n")')
    page.click('#diffBtn')
    diff = page.inner_text('#diffOut')
    assert '- ' + '  <three/>' in diff and '+ ' + '  <four/>' in diff
    page.click('#p-prompt .CodeMirror')
    page.keyboard.press('Control+f')
    page.wait_for_selector('.CodeMirror-dialog')
    page.keyboard.press('Escape')
    page.click('#saveBtn')
    page.wait_for_function('() => document.querySelector("#verSel").value === "4"')
    saved = prompts.prompt_version('practices')
    assert (saved.number, saved.text, saved.parent_id) == (4, '<practices>\n  <four/>\n</practices>\n', third.version_id)
    assert prompts.use_of('proj', notes.base_id, notes.id).number == 3
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-013')
def test_the_system_agents_prompt_opens_on_a_fresh_home_and_saves_as_plain_text_from_the_page(run, web, mapped,
                                                                                              browser):
    """UX review round 2, prompt-authoring F7: before any system agent has run, the Prompt tab opens on the system
    agent's prompt, shown as the agent reads it, and the person's edit, a bare & and < included, is saved and sent."""
    from importlib import resources

    from metaform import prompt_files
    run('enable', 'dispatch')
    started(run)
    page, problems, remote = opened(browser, web)
    page.click('#t-prompt')
    page.wait_for_function('() => window.metaform.editor() && '
                           'window.metaform.editor().getValue().includes("Engineering Orchestrator")')
    assert page.evaluate('document.querySelector("#promptSel").value') == 'dispatch:system'
    assert page.evaluate('document.querySelector("#promptSel option:checked").parentElement.label') == 'system agent'
    assert '1. Language & Vocabulary' in page.evaluate('window.metaform.editor().getValue()')
    assert 'shipped text' in page.text_content('#promptNote')
    page.evaluate('window.metaform.editor().setValue("Plans & tickets for a < b. <mascot/>")')
    page.click('#saveBtn')
    page.wait_for_function('() => document.querySelector("#verSel").value === "2"')
    assert prompt_files.served(resources.files('metaform.modules.dispatch'), 'system', project='proj',
                               mascot='M') == 'Plans & tickets for a < b. M'
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-013')
def test_text_typed_into_a_prompt_just_opened_is_not_put_back_by_a_slower_read_of_it(run, web, mapped, browser):
    """In a parallel run on 2026-10-03 the prompt editor went back to 'one' after 'one, edited' was set in it: opening a
    layer's prompt read it more than once, and a read that came back after the typing put the stored text back. Every
    read of the prompt's versions after the first is held 1.5 s here, as a loaded machine can, and what was typed stays."""
    from metaform.data import Store, prompts
    prompts.add_prompt('practices', 'markdown', 'one\n')
    notes = Store('proj').layer_ref('notes')
    prompts.record_use(prompts.prompt_version('practices').version_id, 'proj', notes.base_id, notes.id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.evaluate('''() => { const real = window.fetch; let reads = 0; window.pending = 0;
        window.fetch = (path, ...rest) => {
            if (!String(path).startsWith('/api/prompt-versions') || reads++ === 0) return real(path, ...rest);
            window.pending++;
            return new Promise(done => setTimeout(() => done(real(path, ...rest)), 1500))
                .finally(() => setTimeout(() => window.pending--, 200)); }; }''')
    page.click('#t-prov')
    page.click('#p-prov .layerlist button:has-text("notes")')
    page.click('#p-prov button.open-prompt')
    page.wait_for_function('() => window.metaform.editor() && window.metaform.editor().getValue() === "one\\n"')
    page.evaluate('window.metaform.editor().setValue("one, edited\\n")')
    page.wait_for_function('() => window.pending === 0', timeout=10000)
    assert page.evaluate('window.metaform.editor().getValue()') == 'one, edited\n'
    assert problems == []


# ---------- clearing the project from the page, VIEW-019 and PROJ-025 ----------

CLEARED = ('Cleared proj: one base, main, and one report file. Its registration, folder, settings, origins, '
           'variants and conversations with agents stay.')
NO_METAFORM = 'proj has no metaform yet. The next intake creates one.'
LEFT = ('It could not be removed and is still on disk. Close any program that has it open, such as a running web GUI, '
        'or fix its permissions, then use Clear project again.')


def own_write(port):
    """The headers of a write from the GUI's own page: its Origin and a JSON body, VIEW-002."""
    return {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}'}


def clear(port, project='proj', **given):
    return api(port, '/api/clear-project', method='POST', body=json.dumps({'project': project, **given}),
               headers=own_write(port))


def caution_of(run, folder):
    """The caution `metaform clear project` prints when it stops without --confirm, PROJ-025."""
    return run('clear', 'project', cwd=folder, ok=False).stderr.splitlines()[0].removeprefix('Error: ')


def metaform_names(run, folder):
    return [line.split()[0] for line in run('list', 'bases', cwd=folder).stdout.splitlines()]


def kept(home):
    """The bytes of every store, the home's base and every report file, to show nothing changed."""
    paths = sorted((home / 'projects').rglob('*.sqlite3')) + [home / 'metaform.sqlite3'] + sorted(
        path for path in (home / 'projects').rglob('reports/*') if path.is_file())
    return {str(path): path.read_bytes() for path in paths}


def events_on(port):
    """Open the events stream as a page does; returns what it hears and an event set when the first arrives."""
    import threading
    heard, ready, first = [], threading.Event(), threading.Event()

    def listen():
        stream = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        try:
            stream.request('GET', '/api/events', headers={'Host': f'127.0.0.1:{port}'})
            answer = stream.getresponse()
            ready.set()
            for line in answer:
                if line.startswith(b'data:'):
                    heard.append(json.loads(line[5:]))
                    first.set()
        except OSError:
            pass
        finally:
            stream.close()
    threading.Thread(target=listen, daemon=True).start()
    assert ready.wait(10)
    return heard, first


@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('VIEW-002')
@pytest.mark.req('PROJ-025')
def test_the_page_reads_the_commands_caution_and_a_clear_without_confirm_or_from_elsewhere_changes_nothing(
        run, home, web, mapped):
    run('feedback', 'The subtype fields did not match.', cwd=mapped)
    started(run)
    before = kept(home)
    caution = caution_of(run, mapped)
    assert caution.startswith('Clearing proj removes one base, main, with its store, and one report file.')
    assert api(web, '/api/clear-preview?project=proj') == (200, {'project': 'proj', 'bases': ['main'],
                                                                 'reports': 1, 'caution': caution})
    for given in ({}, {'confirm': False}):
        assert clear(web, **given) == (400, {'error': caution, 'next': 'If you are sure: send confirm true'})
    confirmed = json.dumps({'project': 'proj', 'confirm': True})
    as_json = {'Content-Type': 'application/json'}
    assert request(web, '/api/clear-project', method='POST', body=confirmed, headers=as_json)[0] == 403
    assert request(web, '/api/clear-project', method='POST', body=confirmed,
                   headers={**as_json, 'Origin': 'http://rebound.example'})[0] == 403
    assert request(web, '/api/clear-project', method='POST', body=confirmed,
                   headers={'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'text/plain'})[0] == 415
    rebound = f'rebound.example:{web}'
    assert request(web, '/api/clear-project', method='POST', body=confirmed, host=rebound,
                   headers={**as_json, 'Origin': f'http://{rebound}'})[0] == 403
    status, answer = api(web, '/api/clear-preview?project=nobody')
    assert status == 404 and answer['next'] == 'metaform list projects'
    status, answer = clear(web, 'nobody', confirm=True)
    assert status == 404 and answer['next'] == 'metaform list projects'
    assert kept(home) == before
    assert metaform_names(run, mapped) == ['main']


@pytest.mark.req('VIEW-019')
@pytest.mark.req('PROJ-025')
@pytest.mark.req('VIEW-018')
def test_clearing_from_the_page_clears_what_the_command_clears_and_every_open_page_is_told(run, home, web, mapped,
                                                                                       tmp_path):
    remember(run, mapped, 'create_entities', [entity('drift', 'Drifts under load.')], 'element:code.timer.kitchen')
    run('add', 'base', 'fresh', cwd=mapped)
    run('feedback', 'The subtype fields did not match.', cwd=mapped)
    run('add', 'origin', cwd=mapped)
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'notes.txt').write_text('second\n', encoding='utf-8')
    run('add', 'variant', str(work), cwd=mapped)
    (mapped / 'notes.txt').write_text('first\n', encoding='utf-8')
    started(run)
    before = {'origins': run('list', 'origins', cwd=mapped).stdout,
              'variants': run('list', 'variants', cwd=mapped).stdout,
              'settings': run('config', '--show', '--json', cwd=mapped).stdout,
              'files': sorted(path.name for path in mapped.iterdir())}
    heard, first = events_on(web)
    status, answer = clear(web, confirm=True)
    backup = answer.pop('backup')
    assert backup and answer.pop('restore') == f'metaform restore project proj {backup}'  # PROJ-030, by name
    assert status == 200 and answer == {
        'project': 'proj', 'bases': ['main', 'fresh'], 'reports': 1,
        'said': ('Cleared proj: two bases, main and fresh, and one report file. Its registration, folder, '
                 'settings, origins, variants and conversations with agents stay.')}
    assert run('list', 'bases', cwd=mapped).stdout == ''
    assert not list(own('proj').glob('*.metaform.sqlite3'))
    assert not (own('proj') / 'reports').exists()
    assert run(cwd=mapped).stdout.count('Base: none yet') == 1
    assert run('list', 'origins', cwd=mapped).stdout == before['origins']
    assert run('list', 'variants', cwd=mapped).stdout == before['variants']
    assert run('config', '--show', '--json', cwd=mapped).stdout == before['settings']
    assert [line.split()[0] for line in run('list', 'projects').stdout.splitlines()] == ['proj']
    assert sorted(path.name for path in mapped.iterdir()) == before['files']
    assert (mapped / 'notes.txt').read_text(encoding='utf-8') == 'first\n'
    assert api(web, '/api/bases?project=proj')[1]['results'] == []
    assert first.wait(5)
    time.sleep(0.5)  # a second event, if one were sent, arrives within this
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'base_id': None}}]
    # the memory graph is the project's, kept by the clear as the command keeps it, its join orphaned, STORE-020
    kept = json.loads(run('memory', 'graph', '--json', cwd=mapped).stdout)
    assert [(one['name'], [seen['content'] for seen in one['observations']]) for one in kept['entities']] == [
        ('drift', ['Drifts under load.'])]
    lost = json.loads(run('memory', 'orphaned', '--json', cwd=mapped).stdout)['joins']
    assert [(one['entity'], one['address']) for one in lost] == [('drift', 'code.timer.kitchen')]


@pytest.mark.req('VIEW-019')
@pytest.mark.req('PROJ-025')
def test_a_clear_from_the_page_names_a_file_it_could_not_remove_with_its_reason_and_what_to_do(run, home, web, mapped,
                                                                                            unremovable):
    run('feedback', 'The subtype fields did not match.', cwd=mapped)
    reports = own('proj') / 'reports'
    (stuck,) = reports.iterdir()
    started(run)
    with unremovable(stuck):
        status, answer = clear(web, confirm=True)
        assert stuck.is_file()
    assert status == 200 and answer['said'] == CLEARED
    assert [entry['path'] for entry in answer['not_removed']] == [str(stuck)] and answer['not_removed'][0]['reason']
    assert answer['notices'] == [{'where': 'not_removed', 'message': LEFT}]
    assert run('list', 'bases', cwd=mapped).stdout == ''
    assert not list(own('proj').glob('*.metaform.sqlite3'))
    status, again = clear(web, confirm=True)
    backup = again.pop('backup')
    assert backup and again.pop('restore') == f'metaform restore project proj {backup}'  # PROJ-030, by name
    assert (status, again) == (200, {
        'project': 'proj', 'bases': [], 'reports': 1,
        'said': ('Cleared proj: no bases and one report file. Its registration, folder, settings, origins, '
                 'variants and conversations with agents stay.')})
    assert not reports.exists()


@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-002')
def test_on_another_bind_address_the_clear_and_its_preview_need_the_token(run, web, mapped):
    lan = lan_address()
    if lan is None:
        pytest.skip('this machine has no address besides loopback')
    run('set', '--web-bind=0.0.0.0')
    token = started(run)['token']
    body = json.dumps({'project': 'proj', 'confirm': True})
    headers = {'Content-Type': 'application/json', 'Origin': f'http://{lan}:{web}'}
    assert request(web, '/api/clear-preview?project=proj', address=lan)[0] == 403
    assert request(web, '/api/clear-project', address=lan, method='POST', body=body, headers=headers)[0] == 403
    assert metaform_names(run, mapped) == ['main']
    assert request(web, '/api/clear-preview?project=proj', address=lan, headers={'X-Metaform-Token': token})[0] == 200
    status, _, _ = request(web, '/api/clear-project', address=lan, method='POST', body=body,
                           headers={**headers, 'X-Metaform-Token': token})
    assert status == 200 and metaform_names(run, mapped) == []


def no_metaform_shown(page):
    """The page shows the project with no metaform: in the metaform list, the 2D map, the panel and the count line."""
    page.wait_for_function(f'() => document.querySelector("#viewport").innerText.includes("{NO_METAFORM}") && '
                           f'document.querySelector("#p-object").innerText.includes("{NO_METAFORM}")', timeout=5000)
    assert page.inner_text('#count') == 'no metaform yet'
    assert page.evaluate('[...document.querySelectorAll("#mf option")].map(option => option.textContent)') == [
        'none yet']
    assert page.is_disabled('#mf')
    assert page.evaluate('window.metaform.drawn().nodes') == 0


@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-012')
def test_clear_project_in_the_header_says_what_goes_asks_on_the_page_and_every_open_page_shows_no_metaform(
        run, home, web, mapped, browser):
    run('feedback', 'The subtype fields did not match.', cwd=mapped)
    started(run)
    caution = caution_of(run, mapped)
    page, problems, remote = opened(browser, web)
    other, other_problems, _ = opened(browser, web)
    for shown in (page, other):
        shown.wait_for_function('() => window.metaform.loaded()')
    assert page.inner_text('header #adminBtn') == 'Administration' and page.is_hidden('#clearBtn')  # VIEW-019
    page.click('#adminBtn')
    assert page.inner_text('#adminbox #clearBtn') == 'Clear project'
    page.keyboard.press('Escape')
    assert page.is_hidden('#adminbox')
    other.click('#t-prov')  # a tab left open is redrawn by the push, not only when clicked again
    other.wait_for_selector('#p-prov .layerlist button')
    before = kept(home)
    page.click('#adminBtn')
    page.click('#clearBtn')
    page.wait_for_selector('#clearbox .warn')
    assert caution in page.inner_text('#clearbox')
    page.keyboard.press('Escape')
    assert page.is_hidden('#clearbox')
    page.click('#adminBtn')
    page.click('#clearBtn')
    page.click('#clearbox button.keep')
    assert page.is_hidden('#clearbox')
    assert kept(home) == before and metaform_names(run, mapped) == ['main']
    page.click('#adminBtn')
    page.click('#clearBtn')
    page.fill('#clearbox input.typed', 'confirm')
    page.click('#clearbox button.confirm')
    page.wait_for_selector('#clearbox .said')
    assert page.inner_text('#clearbox .said') == CLEARED
    assert 'Not removed' not in page.inner_text('#clearbox')
    assert metaform_names(run, mapped) == []
    for shown in (page, other):
        no_metaform_shown(shown)
    other.wait_for_function(f'() => document.querySelector("#p-prov").innerText.includes("{NO_METAFORM}")',
                            timeout=5000)
    assert problems == [] and other_problems == [] and remote == []
    run('intake', 'start', cwd=mapped)
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=mapped)
    page.wait_for_function('() => window.metaform.live() !== null && window.metaform.drawn().nodes === 1',
                           timeout=15000)
    page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length === 1', timeout=15000)
    assert not page.is_disabled('#mf') and 'no metaform' not in page.inner_text('#count')
    run('intake', 'finish', cwd=mapped)
    page.wait_for_function('() => window.metaform.live() === null && window.metaform.loaded()', timeout=15000)
    # The finished map is drawn and the panel's reads for it have settled. The panel's text comes before its node read
    # ends, and a read still in flight at the clear answers 404 for the cleared metaform, which the browser logs.
    for shown in (page, other):
        shown.wait_for_function('() => window.metaform.live() === null && window.metaform.loaded() && '
                                'document.querySelector("#p-object").innerText.includes("code.timer.kitchen")',
                                timeout=15000)
    page.wait_for_timeout(300)
    run('clear', 'project', '--confirm', cwd=mapped)
    no_metaform_shown(page)
    assert problems == [] and other_problems == []  # through the live intake too


@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-012')
def test_the_page_names_what_the_clear_could_not_remove_with_its_reason_and_what_to_do(run, home, web, mapped, browser,
                                                                                      unremovable):
    run('feedback', 'The subtype fields did not match.', cwd=mapped)
    (stuck,) = (own('proj') / 'reports').iterdir()
    started(run)
    page, problems, _ = opened(browser, web)
    page.click('#adminBtn')
    page.click('#clearBtn')
    page.wait_for_selector('#clearbox button.confirm')
    page.fill('#clearbox input.typed', 'confirm')
    with unremovable(stuck):
        page.click('#clearbox button.confirm')
        page.wait_for_selector('#clearbox .left li')
    assert page.inner_text('#clearbox .said') == CLEARED
    assert 'Not removed, still on disk:' in page.inner_text('#clearbox')
    (line,) = page.locator('#clearbox .left li').all_inner_texts()
    assert line.startswith(f'{stuck}: ') and len(line) > len(f'{stuck}: ')
    assert page.inner_text('#clearbox .next') == LEFT
    assert problems == []


WATCHER = '''
    import json
    from pathlib import Path
    from metaform.module import Module, Subscription
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    LOG = Path(LOGPATH)
    def saw(payload, ctx):
        with LOG.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({**payload, 'surface': ctx.surface}) + '\\n')
    MODULE = Module(id='watcher', summary='x', purpose='Watches the map. Details: metaform help watcher.',
                    subscriptions=(Subscription('map.changed', saw),))
'''


def heard_by(log):
    """What the watcher heard since it was last asked, once."""
    found = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    log.unlink(missing_ok=True)
    return found


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-019')
@pytest.mark.req('PROJ-025')
@pytest.mark.req('BASE-010')
def test_a_write_from_the_page_is_announced_on_the_event_bus_as_a_command_is(run, home, web, mapped, tmp_path,
                                                                          user_module):
    """A module of the user's own hears the page's clear once, as it hears the command's, and the open pages still hear
    it once; a write that changes nothing is not announced."""
    log = tmp_path / 'heard.jsonl'
    user_module('watcher', WATCHER.replace('LOGPATH', repr(str(log))))
    started(run)
    heard, first = events_on(web)
    heard_by(log)
    status, answer = clear(web)  # the caution alone: nothing changes, nothing is announced
    assert status == 400
    time.sleep(0.5)
    assert heard_by(log) == [] and heard == []
    status, answer = clear(web, confirm=True)
    assert status == 200 and answer['bases'] == ['main']
    assert first.wait(5)
    time.sleep(0.5)
    assert heard_by(log) == [{'project': 'proj', 'base_id': None, 'surface': 'web'}]
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'base_id': None}}]
    run('clear', 'project', '--confirm', cwd=mapped)  # the command's clear reaches the same subscriber the same way
    assert heard_by(log) == [{'project': 'proj', 'base_id': None, 'surface': 'cli'}]


@pytest.mark.req('VIEW-018')
@pytest.mark.req('BASE-037')
@pytest.mark.req('BASE-052')
def test_a_module_enabled_after_the_server_started_hears_the_pages_writes_in_that_server(run, home, web, mapped,
                                                                                         tmp_path, user_module):
    """Ticket 9d2f9d52: dispatch's subscriber, which tells a runner to read its answered questions, runs in the
    server for an answer given on the page only if the server sees dispatch enabled. Here the watcher stands in for
    it: off when the server announces the page's first write, enabled on the command line after, and the page's next
    write reaches it."""
    log = tmp_path / 'heard.jsonl'
    user_module('watcher', WATCHER.replace('LOGPATH', repr(str(log))))
    run('disable', 'watcher')
    started(run)
    _heard, first = events_on(web)
    status, answer = note_write(web, 'element:code.alarm.audible', 'Set before the watcher is on.')
    assert status == 200, answer
    assert first.wait(5)  # the server has loaded its modules to announce the note
    time.sleep(0.5)
    assert heard_by(log) == []
    run('enable', 'watcher')
    heard_by(log)
    status, answer = clear(web, confirm=True)
    assert status == 200 and answer['bases'] == ['main']
    deadline = time.monotonic() + 5  # the server announces after the answer is sent
    while not log.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    time.sleep(0.5)
    assert heard_by(log) == [{'project': 'proj', 'base_id': None, 'surface': 'web'}]


def watching_toasts(page):
    """Every message the page shows, however briefly, as `window.toasts`."""
    page.evaluate('''() => { window.toasts = [];
        new MutationObserver(() => window.toasts.push(document.querySelector('#toast').textContent))
            .observe(document.querySelector('#toast'), {childList: true, characterData: true, subtree: true}); }''')


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-018')
def test_a_page_following_an_intake_says_it_stopped_when_the_project_is_cleared_and_finished_when_it_finishes(
        run, home, web, browser, tmp_path, dispatch_runners):
    started(run)
    folder = tmp_path / 'live'
    folder.mkdir()
    run('add', 'project', 'live', str(folder))
    agent = intake_agent(run, folder, tmp_path / 'fake.jsonl', dispatch_runners)
    run('intake', 'start', cwd=folder, env=agent)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', cwd=folder, env=agent)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    # the browser's console names no URL for a 404, so the response names it
    page.on('response', lambda answer: problems.append(f'{answer.status} {answer.url}') if answer.status == 404 else None)
    page.goto(f'http://127.0.0.1:{web}/#p=live')
    page.wait_for_function('() => window.metaform && window.metaform.live() !== null && window.metaform.drawn().nodes === 1',
                           timeout=30000)
    watching_toasts(page)
    run('clear', 'project', '--confirm', cwd=folder)
    page.wait_for_function('() => window.metaform.live() === null', timeout=15000)
    no_metaform_shown_for(page, 'live')
    said = page.evaluate('window.toasts')
    assert 'The intake stopped: live was cleared.' in said  # the layer is named intake, LAYER-025
    assert not [text for text in said if 'finished' in text]
    # the clear stopped the first; the same log, so the fake agent names its next session anew
    agent = intake_agent(run, folder, tmp_path / 'fake.jsonl', dispatch_runners)
    run('intake', 'start', cwd=folder, env=agent)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', cwd=folder, env=agent)
    page.wait_for_function('() => window.metaform.live() !== null && window.metaform.drawn().nodes === 1', timeout=15000)
    page.evaluate('window.toasts = []')
    run('intake', 'finish', cwd=folder, env=agent)
    page.wait_for_function('() => window.metaform.live() === null && window.metaform.loaded()', timeout=15000)
    said = page.evaluate('window.toasts')
    assert 'The intake finished.' in said
    assert not [text for text in said if 'stopped' in text]
    assert problems == []


def no_metaform_shown_for(page, project):
    line = f'{project} has no metaform yet. The next intake creates one.'
    page.wait_for_function(f'() => document.querySelector("#viewport").innerText.includes("{line}") && '
                           f'document.querySelector("#p-object").innerText.includes("{line}")', timeout=5000)
    assert page.inner_text('#count') == 'no metaform yet'


def page_file(name):
    from metaform.modules.web import server
    return (server.STATIC['page'] / name).read_text(encoding='utf-8')


def page_script():
    """The page's script: app.js and its parts under page/app, in one text."""
    from metaform.modules.web import server
    parts = sorted((server.STATIC['page'] / 'app').rglob('*.js'))
    return '\n'.join(path.read_text(encoding='utf-8') for path in [server.STATIC['page'] / 'app.js', *parts])


def themes():
    """Each theme of the page's styles with its colors: the blocks `:root[data-theme="<name>"]` of app.css."""
    import re
    found = {}
    for selector, body in re.findall(r'([^{}]*:root\[data-theme="[\w-]+"\][^{}]*)\{([^{}]*)\}', page_file('app.css')):
        colors = dict(re.findall(r'(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6}|[\d.]+)\s*;', body))
        for name in re.findall(r':root\[data-theme="([\w-]+)"\]', selector):
            found[name] = colors
    return found


def scheme(name):
    """A theme's color-scheme, light or dark, as its block of app.css says."""
    import re
    return re.search(r':root\[data-theme="' + re.escape(name) + r'"\]\{[^{}]*?color-scheme:(\w+)',
                     page_file('app.css')).group(1)


def rgb(color):
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))


def contrast(one, other):
    """The WCAG contrast ratio of two colors, 1 for the same color and 21 for black on white."""
    def luminance(color):
        red, green, blue = (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in color)
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


LAYER_COLORS = ['--intake', '--memory', '--k1', '--k2', '--k3', '--k4', '--k5', '--k6']
NODE_COLORS = ['--de', '--signal', '--text', '--broken', *LAYER_COLORS]
LINK_COLORS = ['--tree', *LAYER_COLORS]
LINES_2D = ['--node-line', '--edge', '--signal', '--intake', '--broken',
            *LAYER_COLORS]
LABELS_3D = ['--text', '--muted', '--faint', '--signal']
LABELS_2D = [('--text', '--node'), ('--text', '--node-sel'), ('--text', '--node-broken'), ('--text', '--group'),
             ('--muted', '--node-sub'), ('--text', '--node-sub')]


@pytest.mark.req('VIEW-023')
def test_the_picker_offers_each_theme_of_the_styles_none_of_them_glares_and_each_defines_every_color():
    import re
    found = themes()
    offered = re.findall(r'<option value="([\w-]+)"', re.search(r'<select id="theme".*?</select>',
                                                                 page_file('index.html'), re.DOTALL).group(0))
    assert sorted(offered) == sorted(found) and len(offered) == len(set(offered)) > 1
    assert all(colors.keys() == found['space'].keys() for colors in found.values())
    # A page is looked at for hours: no dark theme's background is bright enough to glare, and the dark themes still
    # differ in how dark they are, from near black to a dim paper. Glass is the one light theme, asked for on
    # 2026-10-17, and Tinted Glass its dark pair.
    light = sorted(name for name in found if scheme(name) == 'light')
    assert light == ['glass'] and scheme('tinted-glass') == 'dark'
    grounds = {name: contrast(rgb(colors['--ground']), (1, 1, 1)) for name, colors in found.items() if name not in light}
    assert all(ratio >= 9 for ratio in grounds.values()), grounds
    assert max(grounds.values()) > 19 and min(grounds.values()) < 15, grounds
    assert {'paper', 'mist', 'glass', 'tinted-glass'} <= set(found)
    from metaform.modules.web import THEMES
    assert sorted(THEMES) == sorted(found)
    assert len({colors['--ground'] for colors in found.values()}) == len(found)


@pytest.mark.req('VIEW-006')
@pytest.mark.req('VIEW-023')
def test_in_every_theme_each_color_of_the_graph_stands_clear_of_its_background():
    """Every node, link and line of both views holds 3 to 1 against the background it is drawn on, a link as it is
    seen at its drawn opacity, and every label of the 2D map holds 4.5 to 1 against its box."""
    assert ".linkOpacity(Number(css('--link-opacity')))" in page_script()
    assert "Number(css('--dim-keep'))" in page_script()
    low = []
    for name, colors in themes().items():
        ground, opacity = rgb(colors['--ground']), float(colors['--link-opacity'])
        for color in NODE_COLORS + LINES_2D + LABELS_3D:
            if contrast(rgb(colors[color]), ground) < 3:
                low.append((name, color, 'on the background'))
        keep = float(colors['--dim-keep'])  # a dimmed node keeps this much of its own color, the rest is the background
        for color in NODE_COLORS:
            seen = tuple(keep * own + (1 - keep) * back for own, back in zip(rgb(colors[color]), ground))
            if contrast(seen, ground) < 3:
                low.append((name, color, f'dimmed, keeping {keep}'))
        for color in LINK_COLORS:
            seen = tuple(opacity * own + (1 - opacity) * back for own, back in zip(rgb(colors[color]), ground))
            if contrast(seen, ground) < 3:
                low.append((name, color, f'as a link at {opacity}'))
        for text, box in LABELS_2D:
            if contrast(rgb(colors[text]), rgb(colors[box])) < 4.5:
                low.append((name, text, f'on {box}'))
        # the page's text on its panels, --faint included, and the edge of every control, WCAG 1.4.11
        for panel in ('--panel', '--panel-2'):
            for text, least in (('--text', 4.5), ('--muted', 4.5), ('--faint', 4.5), ('--control', 3)):
                if contrast(rgb(colors[text]), rgb(colors[panel])) < least:
                    low.append((name, text, f'on {panel}'))
    assert low == []


@pytest.mark.req('VIEW-006')
def test_the_colors_are_defined_once_in_the_styles_and_the_script_holds_none():
    import re
    assert re.findall(r'''['"]#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})['"]''', page_script()) == []
    styles = page_file('app.css')
    rules = re.sub(r'[^{}]*:root[^{}]*\{[^{}]*\}', '', styles)
    assert re.findall(r'#[0-9a-fA-F]{3,8}\b|rgba?\(', rules) == []


@pytest.mark.req('VIEW-023')
def test_choosing_a_theme_recolors_both_views_at_once_and_the_page_keeps_it(run, web, mapped, browser):
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    token = lambda name: page.evaluate(f'getComputedStyle(document.documentElement).getPropertyValue("{name}").trim()')
    box = 'getComputedStyle(document.querySelector("#map2d svg g.node rect")).stroke'
    assert page.evaluate('document.documentElement.dataset.theme') == 'space' == page.input_value('#theme')
    before = {'ground': token('--ground'), 'tree': token('--tree'), 'box': page.evaluate(box)}
    # with a node selected, the others are quieter in color and none is faded toward the background; a 3D label is
    # faded only by its depth, the nearest solid
    assert page.evaluate('window.metaform.selected()') and page.evaluate('''() => {
      const faded = node => Number(getComputedStyle(node).opacity) < 1;
      const others = [...document.querySelectorAll('#map2d svg g.node:not(.sel):not(.near), #map2d .edgePaths path')];
      const labels = window.metaform.labels3d();
      return others.length > 0 && !others.some(node => !/work-/.test(node.getAttribute('class') || '') && faded(node))
        && labels.length > 0 && Math.max(...labels.map(label => label.opacity)) === 1; }''')
    assert before['ground'] == themes()['space']['--ground']
    # the 2D map is drawn in a holder of no size, so drawing it adds nothing to the page and no scrollbar shows
    page.evaluate('''() => { window.added = [];
      new MutationObserver(list => { for (const change of list) for (const node of change.addedNodes)
        if (node.parentNode === document.body) window.added.push(node.id); }).observe(document.body, {childList: true}); }''')
    for name, colors in themes().items():
        if name == 'space':
            continue
        pick_theme(page, name)
        # the 2D map is laid out again in the theme's colors off the page's thread, and shown once it is drawn
        page.wait_for_function('() => window.metaform.loaded() && document.querySelectorAll("#map2d svg g.node").length > 0')
        assert page.evaluate('document.documentElement.dataset.theme') == name
        assert token('--ground') == colors['--ground'] == page.evaluate('window.metaform.ground()')
        drawn = page.evaluate('window.metaform.linkColors()')
        # a namespace edge where no join's edge draws the same two elements, as none in this map
        assert {link['color'] for link in drawn if link['k'] == 'tree'} <= {colors['--tree']}
        # the 3D labels are painted again in the theme's own colors, VIEW-038
        palette = [colors[token].lower() for token in ('--text', '--muted', '--signal', '--broken')]
        page.wait_for_function('palette => window.metaform.labels3d().every(label => label.hidden '
                               '|| palette.includes(label.color))', arg=palette, timeout=3000)
        assert page.evaluate(box) != before['box']
    assert page.evaluate('window.added') == []
    assert page.evaluate('[document.documentElement.scrollWidth, document.documentElement.scrollHeight]') == [1280, 800]
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    assert page.evaluate('document.documentElement.dataset.theme') == name == page.input_value('#theme')
    assert page.evaluate('window.metaform.ground()') == themes()[name]['--ground']
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-005')
def test_every_link_of_the_3d_map_is_a_straight_line(run, web, mapped, browser):
    """No curved edges. A link runs straight between the two nodes it joins."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    curves = page.evaluate('window.metaform.curves()')
    assert curves and 'encounter' in {link['k'] for link in curves}  # a join's edges
    assert [link for link in curves if link['curve'] != 0] == []
    assert problems == []


def answered(port, record, answer, project='proj'):
    return api(port, '/api/answer', method='POST', body=json.dumps({'project': project, 'id': record, 'answer': answer}),
               headers=own_write(port))


@pytest.mark.req('MAP-050')
@pytest.mark.req('VIEW-011')
def test_an_answer_written_from_the_page_is_kept_beside_the_question_and_closes_it(run, web, mapped):
    """The question sits at the node it concerns, as a work record does; the answer is kept beside it, so the agent
    that asked, or the next one there, finds it at the node."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.timer.kitchen'), 'Is the 1 Hz tick still wanted?')
    assert [notice.where for notice in asked.notices] == ['suggestions'] and asked.kind == 'question'  # told to suggest
    started(run)
    status, body = answered(web, asked.id, 'Yes, keep it.')
    assert status == 200 and body['answer'] == 'Yes, keep it.' and body['closed']
    kept = Store('proj').messages(Node('element', 'code.timer.kitchen'), 'question', False).results
    assert [(record.text, record.answer) for record in kept] == [('Is the 1 Hz tick still wanted?', 'Yes, keep it.')]
    assert Store('proj').messages(None, 'question', True).results == ()
    # only a question is answered from the page; any other record is left as it is
    other = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'unbuilt', task='build it')
    status, body = answered(web, other.id, 'done')
    assert status == 400 and Store('proj').work(None, 'unbuilt', True).results[0].done is None
    assert answered(web, asked.id, '   ')[0] == 400  # an answer says something


def reopened(port, record, project='proj'):
    return api(port, '/api/reopen', method='POST', body=json.dumps({'project': project, 'id': record}),
               headers=own_write(port))


@pytest.mark.req('MAP-050')
@pytest.mark.req('VIEW-011')
def test_a_question_answered_by_mistake_is_reopened_from_the_page(run, web, mapped):
    """A question answered with the wrong button can be reopened."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.timer.kitchen'), 'Is the 1 Hz tick still wanted?',
                      suggestions=['Yes, keep it.', 'No, drop it.'])
    started(run)
    assert reopened(web, asked.id)[0] == 400  # an open question has nothing to reopen
    answered(web, asked.id, 'No, drop it.')
    status, body = reopened(web, asked.id)
    assert status == 200 and (body['closed'], body['answer']) == (None, None)
    waiting = Store('proj').messages(None, 'question', True).results
    assert [(record.id, record.suggestions) for record in waiting] == [
        (asked.id, ('Yes, keep it.', 'No, drop it.'))]
    status, body = answered(web, asked.id, 'Yes, keep it.')
    assert status == 200 and body['answer'] == 'Yes, keep it.'
    told = store.tell(Node('element', 'code.timer.kitchen'), 'The driver is written.')
    store.reply(told.id)
    assert reopened(web, told.id)[0] == 400  # only a question is reopened from the page
    assert Store('proj').messages(None, 'message', False).results[0].closed


@pytest.mark.req('VIEW-021')
@pytest.mark.req('MAP-050')
@pytest.mark.parametrize('width', [1280, 1024, 820, 600])
def test_messages_arriving_and_being_answered_keep_the_header_and_maps_in_place(
        run, web, mapped, browser, width):
    from metaform.data import Node, Store

    started(run)
    page, problems, _ = opened(browser, web)
    page.set_viewport_size({'width': width, 'height': 800})
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate('document.fonts.ready')
    assert page.is_hidden('#messages')

    def positions():
        return {selector: page.locator(selector).bounding_box()
                for selector in ('header', '#map2d', '#big3d', '#layersBtn', '#settingsBtn')}

    before = positions()
    run('map', 'ask', 'element:code.alarm.audible', 'Is the tone right?', *ASK_FORM, cwd=mapped)
    page.wait_for_function('() => !document.querySelector("#messages").hidden')
    assert page.inner_text('#messages') == 'Messages 1'
    assert positions() == before
    page.click('#messages')
    page.wait_for_selector('#float textarea.answer')
    page.fill('#float textarea.answer', 'Yes.')
    page.click('#float button.answer')
    page.wait_for_function('() => document.querySelector("#messages").hidden')
    assert positions() == before
    assert Store('proj').messages(Node('element', 'code.alarm.audible'), 'question', True).results == ()
    assert problems == []


@pytest.mark.req('VIEW-021')
@pytest.mark.req('MAP-050')
def test_an_open_question_glows_at_its_node_and_messages_leads_to_the_oldest_where_it_is_answered(
        run, web, mapped, browser):
    from metaform.data import Node, Store
    store = Store('proj')
    # the alarm and the cook carry no record in the fixture; the kitchen carries a broken one
    first = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?')
    store.ask(Node('element', 'exterior.cook'), 'Who is the cook?')
    kitchen, cook = (store.element(address).id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.is_hidden('#messages') is False and page.inner_text('#messages').strip() == 'Messages 2'
    for node in (kitchen, cook):
        seen = page.evaluate(f'window.metaform.look("{node}")')
        assert (seen['work'], seen['classes'], seen['animated2d']) == (['question'], ['work-question'], True)
        page.wait_for_function(f'() => window.metaform.look("{node}").light3d > 1', timeout=3000)
    assert 'waiting: question' in page.inner_text('#legend')
    page.click('#messages')  # the oldest first
    page.wait_for_function(f'() => window.metaform.selected() === "{kitchen}"')
    page.wait_for_selector('#float textarea.answer')
    assert 'Is the quiet tone still wanted?' in page.inner_text('#float')
    assert 'Is the quiet tone still wanted?' not in page.inner_text('#p-object')  # the panel holds no question
    page.fill('#float textarea.answer', 'Yes, keep it.')
    page.click('#float button.answer')
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    page.wait_for_function(f'() => window.metaform.look("{kitchen}").work.length === 0 '
                           f'&& window.metaform.look("{kitchen}").light3d < 1')
    assert Store('proj').messages(None, 'question', False).results[0].answer == 'Yes, keep it.'
    assert Store('proj').messages(None, 'question', False).results[0].id == first.id
    # the answer stays at the node; the panel is drawn again once the page has read the change
    page.wait_for_function('() => document.querySelector("#float").innerText.includes("Answer: Yes, keep it.")',
                           timeout=5000)
    page.click('#messages')
    page.wait_for_function(f'() => window.metaform.selected() === "{cook}"')
    page.wait_for_selector('#float textarea.answer')
    page.fill('#float textarea.answer', 'Whoever sets the timer.')
    page.click('#float button.answer')
    page.wait_for_function('() => document.querySelector("#messages").hidden')
    assert problems == []


@pytest.mark.req('VIEW-021')
@pytest.mark.req('MAP-050')
def test_reopen_beside_an_answer_makes_the_question_wait_again_with_its_suggestions(run, web, mapped, browser):
    """A question answered with the wrong button can be reopened."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?',
                      suggestions=['Yes, keep it.', 'No, make it louder.'])
    alarm = store.element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#messages')
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"')
    page.click('#float button.suggestion:not(.recommended)')  # the wrong button
    page.wait_for_function('() => document.querySelector("#messages").hidden')
    page.wait_for_selector('#float button.reopen')
    assert 'Answer: No, make it louder.' in page.inner_text('#float')
    page.click('#float button.reopen')
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    assert Store('proj').messages(None, 'question', True).results[0].answer is None
    page.wait_for_function(f'() => window.metaform.look("{alarm}").work.includes("question")')
    seen = page.evaluate(f'window.metaform.look("{alarm}")')  # it glows again, as an open question does
    assert (seen['work'], seen['classes'], seen['animated2d']) == (['question'], ['work-question'], True)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").light3d > 1', timeout=3000)
    page.wait_for_selector('#float button.suggestion.recommended')
    assert page.locator('#float button.suggestion').all_inner_texts() == ['Yes, keep it.', 'No, make it louder.']
    assert 'Answer:' not in page.inner_text('#float') and page.locator('#float button.reopen').count() == 0
    page.click('#float button.suggestion.recommended')
    page.wait_for_function('() => document.querySelector("#messages").hidden')
    assert Store('proj').messages(None, 'question', False).results[0].id == asked.id
    assert Store('proj').messages(None, 'question', False).results[0].answer == 'Yes, keep it.'
    assert problems == []


@pytest.mark.req('VIEW-028')
def test_the_two_views_change_places_on_demand_and_each_works_in_either_place(run, web, mapped, browser):
    """The chart in the big view and the graph in the other, on demand, since the chart is so small
    it cannot be read."""
    from metaform.data import Store
    store = Store('proj')
    kitchen, alarm = (store.element(address).id for address in ('code.timer.kitchen', 'code.alarm.audible'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    boxes = lambda: page.evaluate("""() => Object.fromEntries(['#map2d', '#big3d', '#stage', '#stage canvas'].map(name => {
        const box = document.querySelector(name).getBoundingClientRect();
        return [name, [Math.round(box.width), Math.round(box.height)]]; }))""")
    area = lambda box: box[0] * box[1]
    first = boxes()
    assert area(first['#stage']) > 2 * area(first['#map2d']) and first['#stage canvas'] == first['#stage']
    map_key(page, 's')
    page.wait_for_function("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        const size = name => [Math.round(box(name).width), Math.round(box(name).height)].join();
        return box('#map2d').width * box('#map2d').height > 2 * box('#stage').width * box('#stage').height
            && size('#stage canvas') === size('#stage'); }""")  # the graph library sizes its canvas after the swap returns
    swapped = boxes()
    # each view is its map, filling its area, and the two areas are what change hands
    assert swapped['#map2d'] == first['#big3d'] and swapped['#stage canvas'] == swapped['#stage']
    assert swapped['#big3d'][0] == first['#map2d'][0] and swapped['#stage'] == first['#map2d']
    assert page.locator('#map2d svg g.node').count() > 0
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.evaluate(f'window.metaform.click3d("{alarm}")')  # the small 3D map takes a click
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"')
    page.evaluate('window.metaform.fit()')                # the whole map in view, so the kitchen's box is on screen
    still2d(page)
    box = page.evaluate(f'window.metaform.box2d("{kitchen}")')
    page.mouse.click(box['left'] + 6, box['top'] + 6)     # and so does the large 2D map
    page.wait_for_function(f'() => window.metaform.selected() === "{kitchen}"')
    chosen = page.evaluate('window.metaform.selected()')
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    assert boxes()['#map2d'] == swapped['#map2d']        # the choice is kept
    map_key(page, 's')
    page.wait_for_function("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        const size = name => [Math.round(box(name).width), Math.round(box(name).height)].join();
        return box('#stage').width * box('#stage').height > 2 * box('#map2d').width * box('#map2d').height
            && size('#stage canvas') === size('#stage'); }""")
    assert boxes() == first and chosen
    fresh = browser.new_page(viewport={'width': 1280, 'height': 800})  # a browser with no choice made
    fresh.goto(f'http://127.0.0.1:{web}/#p=proj')
    fresh.wait_for_function('() => window.metaform && document.querySelectorAll("#map2d svg g.node").length > 0', timeout=90000)
    assert fresh.evaluate("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        return box('#map2d').width * box('#map2d').height > 2 * box('#stage').width * box('#stage').height; }""")  # 2D large
    assert problems == []


@pytest.mark.req('VIEW-029')
def test_a_node_that_needs_attention_gives_off_light_in_both_views_and_no_other_does(run, web, mapped, browser):
    """When the nodes light up and flash they give off some glow, and the chart flashes too. A
    flash inside a node's outline is lost on a whole map; light that spreads past it is seen from across the map.
    the light is the material's own light emission, spread by the bloom, and no circles are drawn
    around a node."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?')
    kitchen, alarm, cook = (store.element(address).id
                            for address in ('code.timer.kitchen', 'code.alarm.audible', 'exterior.cook'))
    broken = [record for record in store.work(Node('element', 'code.timer.kitchen'), 'broken', True).results]
    assert broken  # the fixture's kitchen is broken
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    own = page.evaluate(f'window.metaform.look("{cook}").light3d')
    assert 0 < own < 1                                    # a node with no record: the glass's own little light
    assert page.evaluate(f'window.metaform.look("{cook}").around3d') == 0
    for node in (kitchen, alarm):
        for _ in range(2):                                # it comes and goes, and the bloom spreads it
            page.wait_for_function(f'() => window.metaform.look("{node}").light3d > 1 && window.metaform.bloom().on',
                                   timeout=4000)
            assert page.evaluate(f'window.metaform.look("{node}").around3d') == 0  # nothing is drawn around it
            page.wait_for_function(f'() => window.metaform.look("{node}").light3d <= {own}', timeout=4000)
            # between flashes the pass stays on, so the rest of the map does not blink with the node
            assert page.evaluate('window.metaform.bloom().on') is True
        page.wait_for_function(f'() => window.metaform.look("{node}").glow2d', timeout=4000)
    assert page.evaluate(f'window.metaform.look("{cook}").glow2d') is False
    # Closed from the command line and told to the page: the light goes back to the glass's own, and the pass goes off.
    for record in broken:
        run('map', 'work', 'op=done', f'id={record.id}', 'resolution=fixed', 'why=the test closes it', cwd=mapped)
    run('map', 'reply', asked.id, 'answer=Yes.', cwd=mapped)
    for record in store.work(None, None, True, limit=0).results:  # nothing on the map needs attention now
        if record.condition == 'broken':
            run('map', 'work', 'op=done', f'id={record.id}', 'resolution=done', 'why=the test closes it', cwd=mapped)
    page.wait_for_function(f'() => ["{kitchen}", "{alarm}"].every(id => window.metaform.look(id).light3d === {own}) '
                           '&& !window.metaform.bloom().on', timeout=5000)
    page.wait_for_timeout(1200)
    assert page.evaluate(f'["{kitchen}", "{alarm}"].map(id => window.metaform.look(id).light3d)') == [own, own]
    assert page.evaluate(f'["{kitchen}", "{alarm}"].map(id => window.metaform.look(id).around3d)') == [0, 0]
    assert page.evaluate('window.metaform.bloom().on') is False
    assert problems == []


def pixels(page, points):
    """The colors a person sees at the given points of the page, each the mean of the 5 by 5 pixels around it, read
    from a screenshot so that what is measured is what is shown."""
    import base64
    shot = base64.b64encode(page.screenshot()).decode()
    return page.evaluate("""async ([shot, points]) => {
        const image = new Image();
        image.src = 'data:image/png;base64,' + shot;
        await image.decode();
        const canvas = document.createElement('canvas');
        canvas.width = image.width; canvas.height = image.height;
        const pen = canvas.getContext('2d', {willReadFrequently: true});
        pen.drawImage(image, 0, 0);
        return points.map(([x, y]) => {
          const data = pen.getImageData(Math.round(x) - 2, Math.round(y) - 2, 5, 5).data, sum = [0, 0, 0];
          for (let at = 0; at < data.length; at += 4) for (let part = 0; part < 3; part++) sum[part] += data[at + part];
          return sum.map(part => part / 25); }); }""", [shot, points])


def staged(page, places, camera):
    """Stop the layout, put the named nodes where given, point the camera, and hide the names drawn over the nodes,
    so a picture of the 3D map can be read at known points. It waits first for the page's own fit of the whole map,
    which starts 2.2 seconds after the page selects its first node, once the 2D map is drawn (`selectLoaded` in
    loading/load.js), and takes 0.8 seconds. On a loaded machine that timer comes late, so the wait is on the page's own
    clock, 2.2 seconds past the selection, and then for the camera at rest; `fits3d` is no sign of it, since with reduced
    motion a fit for the pane's size ends at once and is counted before it."""
    page.wait_for_function('() => window.metaform.selected()')
    due = page.evaluate('performance.now()') + 2200
    page.wait_for_function('due => performance.now() > due', arg=due)
    still(page, '() => window.metaform.away3d()')
    map_key(page, 'p')
    for node, (x, y, z) in places.items():
        page.evaluate(f'window.metaform.pin3d("{node}", {x}, {y}, {z})')
    page.evaluate(f'window.metaform.view3d({json.dumps(camera[0])}, {json.dumps(camera[1])})')
    labels_shown(page, False)
    page.wait_for_timeout(800)


def labels_shown(page, on):
    """Show or hide the 3D map's labels, so a picture of the map can be read with them and without them."""
    page.evaluate('on => window.metaform.showLabels3d(on)', on)


def changed(page, one, two, box):
    """How much two screenshots differ inside a box of the page, read pixel by pixel: the change of each pixel is the
    largest change of its three channels, and the 50th and 90th percentiles of those changes are returned."""
    import base64
    shots = [base64.b64encode(shot).decode() for shot in (one, two)]
    return page.evaluate("""async ([shots, box]) => {
        const read = async shot => { const image = new Image(); image.src = 'data:image/png;base64,' + shot;
          await image.decode(); const canvas = document.createElement('canvas');
          canvas.width = image.width; canvas.height = image.height;
          const pen = canvas.getContext('2d', {willReadFrequently: true}); pen.drawImage(image, 0, 0);
          return pen.getImageData(Math.round(box.left), Math.round(box.top), Math.round(box.right - box.left),
            Math.round(box.bottom - box.top)).data; };
        const [a, b] = await Promise.all(shots.map(read)), changes = [];
        for (let at = 0; at < a.length; at += 4)
          changes.push(Math.max(Math.abs(a[at] - b[at]), Math.abs(a[at + 1] - b[at + 1]), Math.abs(a[at + 2] - b[at + 2])));
        changes.sort((x, y) => x - y);
        return [changes[Math.floor(changes.length * 0.5)], changes[Math.floor(changes.length * 0.9)]]; }""", [shots, box])


def reach_drawn(page, node):
    """Where a 3D node is drawn above its center, read from a picture: its center on the page and the farthest pixel
    straight up that differs from the background. Upward, since the nodes staged are at the height of the camera and
    their links run across the picture. A point read is the mean of the 5 by 5 pixels around it, so the drawn pixel
    is 2 nearer the center than the farthest point that differs."""
    at = page.evaluate(f'window.metaform.screen3d("{node}")')
    ground, *column = pixels(page, [(at['x'], at['y'] - 150)] + [(at['x'], at['y'] - up) for up in range(60)])
    far = max(up for up, seen in enumerate(column) if max(abs(a - b) for a, b in zip(seen, ground)) > 20) - 2
    assert far < 57, (node, far)  # the whole of it was read
    return at, far


def hovered(page, x, y):
    """The 3D map's hover card with the pointer at a point, or None when nothing there takes it. The card, not the
    name across the top, says what the pointer is on, by its address: the top name shows only where the map shows none
    to read, and the card carries no name of its own."""
    page.mouse.move(x, y)
    page.wait_for_timeout(250)
    return page.evaluate('(() => { const card = document.querySelector("#card3d");'
                         ' return card && card.classList.contains("on") ? card.textContent : null; })()')


def staged_pair(run, web, browser, alarm, kitchen):
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=30000)
    staged(page, {alarm: (2000, 0, 0), kitchen: (2300, 0, 0)},
           ({'x': 2150, 'y': 0, 'z': 900}, {'x': 2150, 'y': 0, 'z': 0}))
    names = {node['id']: node.get('name') for node in page.evaluate('window.metaform.graph().nodes')}
    assert names[alarm] and names[kitchen]
    return page, problems, names


@pytest.mark.req('VIEW-005')
def test_with_the_bloom_off_a_glass_node_is_drawn_to_its_sphere_and_takes_the_pointer_to_its_reach(
        run, web, mapped, browser):
    """With no record giving off light the bloom is off, and a glass node is drawn to its sphere and no farther. The
    pointer takes it on its sphere and on to its reach, half the distance to its nearest neighbour on the screen and
    never less than the sphere, and four pixels past its reach no longer takes it."""
    from metaform.data import Node, Store
    store = Store('proj')
    for record in store.work(Node('element', 'code.timer.kitchen'), 'broken', True).results:
        store.finish_work(record.id)
    alarm = store.element('code.alarm.audible').id
    kitchen = store.element('code.timer.kitchen').id
    run('set', '--no-web-node-shapes')  # the glass sphere every node was; with shapes on, code is a box
    page, problems, _names = staged_pair(run, web, browser, alarm, kitchen)
    page.wait_for_timeout(500)
    assert page.evaluate('window.metaform.bloom().on') is False
    at, far = reach_drawn(page, kitchen)
    assert far <= at['r'] + 3, (far, at['r'])  # drawn to its sphere
    timer = 'code.timer.kitchen'  # the card names what it is on by its address
    assert timer in (hovered(page, at['x'], at['y'] - far) or ''), (far, at['r'])
    reach = next(one['reach'] for one in page.evaluate('window.metaform.reaches("3d")') if one['id'] == kitchen)
    assert reach >= at['r'] - 0.5, (reach, at['r'])
    assert timer in (hovered(page, at['x'], at['y'] - reach + 2) or ''), (reach, at['r'])
    assert timer not in (hovered(page, at['x'], at['y'] - reach - 4) or ''), (reach, at['r'])
    assert not problems


@pytest.mark.req('VIEW-029')
def test_the_light_of_a_node_spreads_past_its_outline_and_stays_behind_a_node_nearer_the_eye(run, web, mapped, browser):
    """The glow was painted on top of everything when it should be behind. The broken kitchen timer
    gives off its light; another element is set nearer the eye, beside it, where its glow falls. The glow shows
    over the background around the timer and not over the nearer node."""
    from metaform.data import Node, Store
    store = Store('proj')
    store.ask(Node('element', 'code.alarm.audible'), 'Still wanted?')  # the pass stays on
    kitchen = store.element('code.timer.kitchen').id
    broken = store.work(Node('element', 'code.timer.kitchen'), 'broken', True).results
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.emulate_media(reduced_motion='reduce')           # the light is steady
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    front = store.element('code.loop.tick').id
    staged(page, {kitchen: (2000, 0, 0), front: (2000, 16, 150)},
           ({'x': 2000, 'y': 0, 'z': 300}, {'x': 2000, 'y': 0, 'z': 0}))
    page.wait_for_function(f'() => window.metaform.look("{kitchen}").light3d > 1 && window.metaform.bloom().on')
    lit, near = (page.evaluate(f'window.metaform.screen3d("{node}")') for node in (kitchen, front))
    across = ((lit['x'] - near['x']) ** 2 + (lit['y'] - near['y']) ** 2) ** 0.5
    toward = ((lit['x'] - near['x']) / across, (lit['y'] - near['y']) / across)
    # a point on the nearer node toward the lit one; the point as far from the lit node on its other side, over the
    # background; and a point of background far from both
    on_near = (near['x'] + toward[0] * near['r'] * 0.5, near['y'] + toward[1] * near['r'] * 0.5)
    beyond = (2 * lit['x'] - on_near[0], 2 * lit['y'] - on_near[1])
    ground = (lit['x'] + 300, lit['y'] + 100)
    assert across - near['r'] * 0.5 > lit['r'] + 4       # both points lie past the lit node's outline
    shown = pixels(page, [on_near, beyond, ground])
    assert sum(shown[1]) > sum(shown[2]) + 20, shown     # the light spreads past the outline, over the background
    for record in broken:
        run('map', 'work', 'op=done', f'id={record.id}', 'resolution=fixed', 'why=the test closes it', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{kitchen}").light3d < 1 && window.metaform.bloom().on')
    page.wait_for_timeout(800)
    dark = pixels(page, [on_near, beyond, ground])
    assert sum(dark[1]) < sum(dark[2]) + 6, dark          # with the light gone, that point is background again
    # the nearer node is drawn the same whether the node behind it gives off light or not: no halo reaches it (a halo
    # is the twenty and more the open point shows); the little the clear glass refracts of the lit node beside it is
    # the glass letting light through, VIEW-025, not the pass (2026-10-21)
    assert all(abs(one - two) <= 10 for one, two in zip(shown[0], dark[0])), (shown[0], dark[0])
    assert problems == []


@pytest.mark.req('VIEW-022')
def test_with_the_bloom_pass_on_what_it_does_not_light_keeps_its_colors(run, web, mapped, browser):
    """The pass spreads what is over full brightness, and the rest of the picture is the one drawn without it. It is
    read on paper, a theme whose background is far from black, where a picture taken apart in the wrong space turned the
    nodes dark while the pass was on."""
    from metaform.data import Store
    store = Store('proj')
    for record in store.work(None, None, True, limit=0).results:  # nothing needs attention: the pass is off
        store.finish_work(record.id, 'done')
    cook, alarm = (store.element(address).id for address in ('exterior.cook', 'code.alarm.audible'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')
    pick_theme(page, 'paper')
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    staged(page, {cook: (2000, 0, 0)}, ({'x': 2000, 'y': 0, 'z': 80}, {'x': 2000, 'y': 0, 'z': 0}))
    assert page.evaluate('window.metaform.bloom().on') is False
    node = page.evaluate(f'window.metaform.screen3d("{cook}")')
    # The glass's highlight, toward its upper left, is over full brightness and the pass spreads it as it spreads any
    # light, so the points read on the node are on its lower half, clear of that glow, and one is on the background.
    points = [(node['x'], node['y'] + node['r'] * 0.6), (node['x'] + node['r'] * 0.5, node['y'] + node['r'] * 0.5),
              (node['x'] + node['r'] * 3, node['y'] + node['r'] * 1.5)]
    before = pixels(page, points)
    # A broken record on the alarm, far out of view, lights it and turns the pass on.
    run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=broken', 'task=a cracked tone',
        'title=a cracked tone', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").light3d > 1 && window.metaform.bloom().on',
                           timeout=5000)
    page.wait_for_timeout(800)
    assert page.evaluate(f'window.metaform.screen3d("{cook}")') == node  # the points read are the same points
    after = pixels(page, points)
    for one, two in zip(before, after):
        assert all(abs(a - b) <= 3 for a, b in zip(one, two)), (before, after)
    assert problems == []


def drawn(page, frames=3):
    """Wait for the page to draw the given number of frames, however long a loaded machine takes to draw one."""
    page.evaluate("""frames => new Promise(done => { const next = () => --frames ? requestAnimationFrame(next) : done();
        requestAnimationFrame(next); })""", frames)


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-025')
def test_a_dot_passing_through_the_white_node_never_turns_it_dark(run, web, mapped, browser):
    """The big white nodes must not flash dark every time something goes through them. The
    dots that travel a join are drawn solid, as the approved prototype draws them. A dot inside the DE's white glass
    shows through it and takes no light from it; a dot in front of it, with the bloom pass on, has the color it has
    farther along its link, never black. The dots are held still, so what is read does not hang on how fast the page
    draws."""
    from metaform.data import Store
    store = Store('proj')
    for record in store.work(None, None, True, limit=0).results:  # the kitchen timer is drawn in its own white
        store.finish_work(record.id, 'done')
    run('set', '--no-web-node-shapes')  # the DE's white glass sphere, as the prototype draws it
    started(run)
    _, at = keys_of(web)
    kitchen = at['code.timer.kitchen']
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    # The join the kitchen timer receives: its dots leave the timer's center along the join's edge for an element it
    # holds, set in front of the timer, above it and nearer the eye; a join has no node of its own.
    purpose = next(link['target'] for link in page.evaluate('window.metaform.graph().links')
                   if link['k'] == 'encounter' and link['source'] == kitchen)
    camera = ({'x': 2000, 'y': 0, 'z': 40}, {'x': 2000, 'y': 0, 'z': 0})
    staged(page, {kitchen: (2000, 0, 0), purpose: (2000, 12, 25)}, camera)
    close = f'window.metaform.screen3d("{kitchen}").r > 100'
    for _ in range(20):  # on a loaded machine the page's own fit of the whole map can still be moving the camera
        page.evaluate(f'window.metaform.view3d({json.dumps(camera[0])}, {json.dumps(camera[1])})')
        page.wait_for_timeout(500)
        if page.evaluate(close):
            page.wait_for_timeout(500)
            if page.evaluate(close):
                break
    ball = page.evaluate(f'window.metaform.screen3d("{kitchen}")')
    assert ball['r'] > 100, ball

    def held(along):
        dots = page.evaluate(f'window.metaform.dots3d({along})')
        drawn(page)
        return next(dot for dot in dots if dot['source'] == kitchen and dot['target'] == purpose)

    # Inside the glass: every point of the node is as light as with the dot clear of it, at the purpose vertex.
    grid = [(ball['x'] + ball['r'] * across, ball['y'] + ball['r'] * down)
            for down in (-0.5, -0.25, 0, 0.25, 0.5) for across in (-0.5, -0.25, 0, 0.25, 0.5)]
    held(0.9)
    clear = pixels(page, grid)
    dot = held(0.12)
    assert (dot['x'] - ball['x']) ** 2 + (dot['y'] - ball['y']) ** 2 < (ball['r'] * 0.5) ** 2, (dot, ball)
    inside = pixels(page, grid)
    darker = [sum(one) - sum(two) for one, two in zip(clear, inside)]
    assert max(darker) <= 12, list(zip(clear, inside))
    # In front of the node, with the bloom pass on, the dot is drawn as it is farther along its link.
    run('map', 'ask', 'element:exterior.cook', 'Still wanted?', *ASK_FORM, cwd=mapped)  # the cook, out of view, lights
    page.wait_for_function('() => window.metaform.bloom().on', timeout=30000)
    drawn(page)  # the map read again with the question is drawn, its dots made again, before they are held
    front = held(0.3)
    assert ball['r'] * 0.3 < ((front['x'] - ball['x']) ** 2 + (front['y'] - ball['y']) ** 2) ** 0.5 < ball['r'] * 0.8
    over_node = pixels(page, [(front['x'], front['y'])])[0]
    away = held(0.6)
    assert ((away['x'] - ball['x']) ** 2 + (away['y'] - ball['y']) ** 2) ** 0.5 > ball['r'] * 1.5
    over_ground = pixels(page, [(away['x'], away['y'])])[0]
    assert all(abs(one - two) <= 12 for one, two in zip(over_node, over_ground)), (over_node, over_ground)
    assert problems == []


@pytest.mark.req('VIEW-021')
@pytest.mark.req('MAP-050')
def test_a_question_is_answered_with_one_click_on_a_choice_or_by_typing_and_each_form_part_can_become_a_ticket(
        run, web, mapped, browser):
    """The question form: a button for each choice, the one recommended first; a box to type an answer or a message
    is always there; each part of the form the agent filled shows under its heading with Create ticket."""
    from metaform.data import Node, Store
    store = Store('proj')
    first = store.ask(Node('element', 'code.alarm.audible'),
                      'Is the quiet tone still wanted?\n\n#1 Specifications reviewed:\n09-viewer.md',
                      suggestions=['Yes, keep it', 'No, make it louder'])
    second = store.ask(Node('element', 'exterior.cook'), 'Who is the cook?', suggestions=['Whoever sets the timer'])
    alarm, cook = (store.element(address).id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.unread')
    page.wait_for_selector('#float button.suggestion')
    shown = page.eval_on_selector_all('#float button.suggestion', 'found => found.map(one => one.textContent)')
    assert shown == ['Yes, keep it', 'No, make it louder']
    assert page.locator('#float button.suggestion').first.get_attribute('class').split() == ['suggestion', 'recommended']
    assert page.locator('#float textarea.answer').count() == 1       # the box to type in is always there
    assert page.locator('#float .form-part .heading').first.text_content() == '#1 Specifications reviewed:'
    assert page.locator('#float .form-part button.create-ticket').count() == 1
    assert page.locator('#float p.asked').first.text_content() == 'Is the quiet tone still wanted?'
    page.click('#float button.suggestion >> nth=1')
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    assert Store('proj').messages(Node('element', 'code.alarm.audible'), 'question', False).results[0].answer \
        == 'No, make it louder'
    page.evaluate(f'window.metaform.menu("{cook}")')
    page.click('#menu button.unread')
    page.wait_for_selector('#float textarea.answer')
    page.fill('#float textarea.answer', 'The person who is cooking.')
    page.click('#float button.answer')
    page.wait_for_function('() => document.querySelector("#messages").hidden')
    assert Store('proj').messages(Node('element', 'exterior.cook'), 'question', False).results[0].answer \
        == 'The person who is cooking.'
    assert first.id != second.id and problems == []


@pytest.mark.req('VIEW-028')
@pytest.mark.req('VIEW-021')
def test_the_maps_swap_zoom_and_fit_by_their_keys_and_the_messages_button_is_at_the_top(run, web, mapped, browser):
    """The maps have no bar: S swaps them, a Ctrl-click fits the 2D map and F the large 3D map, each moving only its
    own map; and the messages box goes to the top of the screen."""
    from metaform.data import Node, Store
    Store('proj').ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    larger = lambda: page.evaluate("""() => { const area = name => { const box = document.querySelector(name).getBoundingClientRect();
        return box.width * box.height; }; return area('#map2d') > area('#stage') ? '2d' : '3d'; }""")
    assert larger() == '3d' and page.evaluate("document.querySelectorAll('.bar2d, .bar3d').length") == 0
    assert page.evaluate('Boolean(document.querySelector("#messages").closest("header"))') and page.is_visible('#messages')
    map_key(page, 's')                                                # S swaps, the 2D map to the large area
    page.wait_for_function("""() => { const area = name => { const box = document.querySelector(name).getBoundingClientRect();
        return box.width * box.height; }; return area('#map2d') > area('#stage'); }""")
    assert larger() == '2d'
    still(page, '() => window.metaform.away3d()')                     # the swap's flight over
    zoomed_to(page, 3 * page.evaluate(HEADING))                       # zoomed in, full fit has a move to make
    still2d(page)
    whole, chart = page.evaluate('window.metaform.away3d()'), page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")')
    page.click('#map2d', modifiers=['Meta' if sys.platform == 'darwin' else 'Control'])  # a Ctrl-click: full fit
    still2d(page)
    assert abs(page.evaluate('window.metaform.away3d()') - whole) < 1  # the 3D map did not move
    assert page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")') != chart
    map_key(page, 's')                                                # and back
    page.wait_for_function("""() => { const area = name => { const box = document.querySelector(name).getBoundingClientRect();
        return box.width * box.height; }; return area('#stage') > area('#map2d'); }""")
    still(page, '() => window.metaform.away3d()')
    page.evaluate('window.metaform.zoom3d(0.2)')                      # far in, so the whole map is no longer in view
    page.wait_for_timeout(300)
    near, chart = page.evaluate('window.metaform.away3d()'), page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")')
    map_key(page, 'f')                                                # the 3D map's fit: the whole map, once
    page.wait_for_function(f'() => window.metaform.away3d() > {near} * 1.5', timeout=15000)
    still(page, '() => window.metaform.away3d()')
    assert page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")') == chart  # the 2D map did not move
    fitted3d = page.evaluate('window.metaform.away3d()')
    map_key(page, 'f')                                                # again: still the whole map, not in on the node
    still(page, '() => window.metaform.away3d()')
    assert page.evaluate('window.metaform.away3d()') == pytest.approx(fitted3d, rel=0.05)
    page.evaluate("try { localStorage.removeItem('metaform.swapped') } catch (error) {}")
    assert problems == []


@pytest.mark.req('VIEW-030')
@pytest.mark.req('MAP-050')
def test_a_right_click_on_a_node_opens_its_menu_and_its_messages_are_read_in_a_floating_window(run, web, mapped, browser):
    """Right-click a node to read its unread messages, past messages for review on the menu, in a
    floating window, from the 2D map and from the 3D map."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm_node = Node('element', 'code.alarm.audible')
    answered = store.ask(alarm_node, 'Was the tone ever louder?', suggestions=['Yes', 'No'])
    store.reply(answered.id, 'No')
    store.ask(alarm_node, 'Is the quiet tone still wanted?', suggestions=['Yes', 'No'])
    note = store.tell(alarm_node, 'The piezo driver is written and waits for a test on the board.')
    assert note.notices == ()
    alarm, cook = (store.element(address).id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    assert page.is_hidden('#menu') and page.is_hidden('#float')
    assert page.inner_text('#messages').strip() == 'Messages 2'       # a question and a note wait
    entries = lambda: page.eval_on_selector_all('#menu button', 'found => found.map(one => [one.className, one.textContent, one.disabled])')
    GIVE = (['memories', 'Memories 0', True],                           # the first of the further acts, VIEW-031
            ['notes', 'Notes 0', False], ['history', 'Work history 0', True],  # VIEW-034, VIEW-036
            ['chat', 'Chat about this', False],                         # talk about any node, VIEW-042
            ['raise', 'Raise an issue', False],                         # a sentinel on it, VIEW-045
            ['task', 'Add Task', False],                                # from the same menu, VIEW-032
            ['element', 'Add Element', False],                          # and VIEW-033
            ['agent', 'Start agent 0', True])                           # no open ticket waits here, VIEW-039
    # the 2D map: a right-click on the node's own box
    page.evaluate(f'window.metaform.select("{alarm}")')              # the chart goes to the node, at a size to read
    page.wait_for_timeout(1200)
    box = page.evaluate(f'window.metaform.box2d("{alarm}")')
    page.mouse.click((box['left'] + box['right']) / 2, (box['top'] + box['bottom']) / 2, button='right')
    page.wait_for_selector('#menu:not([hidden])')
    assert entries() == [['unread', 'Unread messages 2', False], ['past', 'Past messages 1', False], *GIVE]
    page.keyboard.press('Escape')
    assert page.is_hidden('#menu')
    # the 3D map: the node's right-click, and a node with no messages
    page.evaluate(f'window.metaform.menu("{cook}")')
    assert entries() == [['unread', 'Unread messages 0', True], ['past', 'Past messages 0', True], *GIVE]
    page.keyboard.press('Escape')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.unread')
    page.wait_for_selector('#float:not([hidden])')
    assert page.is_hidden('#menu')
    shown = page.inner_text('#float')
    assert 'Is the quiet tone still wanted?' in shown and 'The piezo driver is written' in shown
    assert 'Was the tone ever louder?' not in shown
    # the note shown is read; the question still waits
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    read = Store('proj').messages(alarm_node, 'message', False).results
    assert [record.id for record in read] == [note.id]
    before = page.evaluate('(() => { const box = document.querySelector("#float").getBoundingClientRect(); return [box.left, box.top]; })()')
    page.mouse.move(before[0] + 40, before[1] + 12)                   # it is moved by its title
    page.mouse.down()
    page.mouse.move(before[0] + 160, before[1] + 92, steps=4)
    page.mouse.up()
    after = page.evaluate('(() => { const box = document.querySelector("#float").getBoundingClientRect(); return [box.left, box.top]; })()')
    assert abs(after[0] - before[0] - 120) <= 2 and abs(after[1] - before[1] - 80) <= 2
    page.click('#float button.close')
    assert page.is_hidden('#float')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert entries() == [['unread', 'Unread messages 1', False], ['past', 'Past messages 2', False], *GIVE]
    page.click('#menu button.past')
    page.wait_for_selector('#float:not([hidden])')
    past = page.inner_text('#float')
    assert 'Was the tone ever louder?' in past and 'Answer: No' in past and 'The piezo driver is written' in past
    assert 'Is the quiet tone still wanted?' not in past
    assert problems == []


@pytest.mark.req('VIEW-032')
@pytest.mark.req('MAP-048')
def test_work_is_given_at_a_node_from_its_menu_with_nodes_linked_and_named_inline(run, web, mapped, browser):
    """A text editor window and a node selector on the right-click menu, where nodes are linked to
    the prompt or inserted inline by their proper noun, from a clickable browser of the namespace."""
    from metaform.data import Store
    store = Store('proj')
    alarm, kitchen, cook = (store.element(address).id
                            for address in ('code.alarm.audible', 'code.timer.kitchen', 'exterior.cook'))
    names = {address: store.element(address).name or store.element(address).short_name
             for address in ('code.timer.kitchen', 'exterior.cook')}
    before = len(store.work(None, None, None, limit=0).results)
    started(run)
    for absent in ({}, {'condition': ''}):  # a task needs no state on its part, it is written plain
        status, body = api(web, '/api/task', method='POST', headers=own_write(web), body=json.dumps({
            'project': 'proj', 'task': 'Improve the alarm.', 'nodes': [f'element:{alarm}'], **absent}))
        assert status == 200 and body['results'][0]['condition'] == ''
    assert len(store.work(None, None, None, limit=0).results) == before + 2
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.task')
    page.wait_for_selector('#task:not([hidden])')
    linked = lambda: page.eval_on_selector_all('#task .linked [data-address]', 'found => found.map(one => one.dataset.address)')
    assert linked() == ['code.alarm.audible']                        # the node it was opened at
    listed = page.eval_on_selector_all('#task .browser [data-address]', 'found => found.map(one => one.dataset.address)')
    assert listed == sorted(listed) and {'code.alarm.audible', 'code.timer.kitchen', 'exterior.cook'} <= set(listed)
    assert page.input_value('#task .condition') == ''
    page.select_option('#task .condition', 'unbuilt')
    page.click('#task .put')                                          # a task with no text is not written
    page.wait_for_timeout(400)
    assert len(Store('proj').work(None, None, None, limit=0).results) == before + 2 and page.is_visible('#task')
    page.click('#task .text')
    page.keyboard.type('Make the tone louder when ')
    page.select_option('#task .condition', '')
    assert page.is_enabled('#task .put')                               # a task needs no state on its part
    page.fill('#task .browser input', 'kitchen')                      # the browser is narrowed by typing
    shown = page.eval_on_selector_all('#task .browser [data-address]:not([hidden])', 'found => found.map(one => one.dataset.address)')
    assert shown == [address for address in listed if 'kitchen' in address] and 'code.timer.kitchen' in shown
    assert len(shown) < len(listed)
    page.click('#task .browser [data-address="code.timer.kitchen"]')
    page.click('#task .insert')
    page.click('#task .text')
    page.keyboard.press('End')
    page.keyboard.type(' runs out of time.')                        # an f is a letter here and not the key for Fit
    inline = page.eval_on_selector_all('#task .text span[data-address]', 'found => found.map(one => [one.textContent, one.dataset.address, one.title])')
    assert inline == [[names['code.timer.kitchen'], 'code.timer.kitchen', 'code.timer.kitchen']]
    page.fill('#task .browser input', '')
    page.click('#task .browser [data-address="exterior.cook"]')
    page.click('#task .link')
    assert linked() == ['code.alarm.audible', 'exterior.cook']
    assert page.eval_on_selector_all('#task .condition option', 'found => found.map(one => one.value)') == [
        '', 'unbuilt', 'under-construction', 'broken']             # none, then the part's states
    assert page.eval_on_selector_all('#task .ticket-kind option', 'found => found.map(one => one.value)') == [
        '', 'broken', 'flawed', 'enhancement']                       # a plain task, then the ticket's kinds
    page.select_option('#task .condition', 'broken')
    page.select_option('#task .ticket-kind', 'broken')
    assert page.is_enabled('#task .put')
    page.check('#task .backlog')
    page.click('#task .put')
    page.wait_for_function('() => document.querySelector("#task").hidden')
    written = [record for record in Store('proj').work(None, None, True, limit=0).results
               if record.task and record.task.startswith('Make the tone louder')]
    text = f"Make the tone louder when [[{names['code.timer.kitchen']}|code.timer.kitchen]] runs out of time."
    # one ticket, on the node it was opened at, linking every other node of the task for reference
    [ticket] = written
    # the ticket carries its kind; the part's stage went on its state record, MAP-046 as amended 2026-10-08
    assert (ticket.address, ticket.task, ticket.condition, ticket.kind, ticket.column) == (
        'code.alarm.audible', text, '', 'broken', 'backlog')
    assert [link.address for link in ticket.links] == ['exterior.cook', 'code.timer.kitchen']
    page.wait_for_function(f'() => window.metaform.look("{alarm}").work.includes("broken")', timeout=6000)
    assert 'broken' not in page.evaluate(f'window.metaform.look("{cook}").work')
    page.evaluate(f'window.metaform.task("{alarm}")')
    assert page.input_value('#task .condition') == ''                  # each task gets its own choice
    assert kitchen and problems == []


@pytest.mark.req('VIEW-032')
def test_the_task_editor_has_a_chart_of_its_own_to_browse_and_is_sized_or_made_full_screen(run, web, mapped, browser):
    """In the editor a 2D chart browser, independent from the other two, for seeing and browsing
    the project; the window sized or made full screen; the entry named Add Task."""
    from metaform.data import Store
    store = Store('proj')
    alarm, kitchen = (store.element(address).id for address in ('code.alarm.audible', 'code.timer.kitchen'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.select("{alarm}")')
    page.wait_for_timeout(1200)
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.inner_text('#menu button.task') == 'Add Task'
    page.click('#menu button.task')
    page.wait_for_selector('#task .chart svg g[data-address]')
    assert page.inner_text('#task .title').startswith('Add Task') and page.inner_text('#task .put') == 'Add task'
    drawn = page.eval_on_selector_all('#task .chart svg g[data-address]', 'found => found.map(one => one.dataset.address)')
    assert {'code.alarm.audible', 'code.timer.kitchen', 'exterior.cook'} <= set(drawn)
    view = lambda name: page.evaluate(f'document.querySelector("{name} svg").getAttribute("viewBox")')
    page.locator('#task .chart').scroll_into_view_if_needed()          # below the form, where the window scrolls to it
    before = view('#task .chart'), view('#map2d'), page.evaluate('window.metaform.selected()')
    box = page.evaluate('(() => { const box = document.querySelector("#task .chart").getBoundingClientRect(); return [box.left + box.width / 2, box.top + box.height / 2]; })()')
    page.mouse.move(*box)
    page.mouse.wheel(0, -400)                                         # it is looked around by itself
    page.wait_for_function(f'() => document.querySelector("#task .chart svg").getAttribute("viewBox") !== "{before[0]}"')
    assert view('#map2d') == before[1]
    page.evaluate('document.querySelector(\'#task .chart svg g[data-address="code.timer.kitchen"]\').dispatchEvent(new MouseEvent("click", {bubbles: true}))')
    chosen = page.eval_on_selector_all('#task .rows .chosen, #task .chart g.chosen', 'found => found.map(one => one.dataset.address)')
    assert chosen == ['code.timer.kitchen', 'code.timer.kitchen']    # chosen in the chart, and so in the list
    assert page.is_enabled('#task .insert') and page.evaluate('window.metaform.selected()') == before[2] and kitchen
    assert page.evaluate('getComputedStyle(document.querySelector("#task")).resize') == 'both'
    small = page.evaluate('(() => { const box = document.querySelector("#task").getBoundingClientRect(); return [box.width, box.height]; })()')
    page.click('#task .full')
    whole = page.evaluate('(() => { const box = document.querySelector("#task").getBoundingClientRect(); return [box.left, box.top, box.width, box.height, innerWidth, innerHeight]; })()')
    assert whole[:2] == [0, 0] and whole[2:4] == whole[4:]
    page.click('#task .full')
    again = page.evaluate('(() => { const box = document.querySelector("#task").getBoundingClientRect(); return [box.width, box.height]; })()')
    assert again == small
    assert problems == []


VALIDATE = ('Orient yourself only enough to validate the coherence of this element, approve addition or if element '
            'needs additional coherence submit questions w/ recommendations.')

WORKFLOW_ADDRESS = 'prompt.workflow.quality.code'
WORKFLOW_SCRIPT = '''@STATE_INIT:
 {target} := PARAM
@CONSTRAINT:
 +> Return the address of the supplied target.
@CONDITION (DONE):
 ?IF ( TRUE ) -> RETURN ( TRUE, {target}.address )
@ROUTER:
 EXECUTE_PIPELINE( Review )
@EXECUTE_PIPELINE (Review):
 [STEP 1]: RETURN ( TRUE, {target}.address ).
@VERIFY:
 [V1] Was the target returned? NO -> RECURSE Review.
'''


@pytest.mark.req('BASE-051')
@pytest.mark.req('VIEW-032')
@pytest.mark.req('VIEW-039')
def test_a_stored_workflow_runs_from_the_task_editor_through_acp(run, web, mapped, browser, tmp_path,
                                                               watch_dispatch):
    from metaform.data import Store
    from metaform.modules.dispatch.tests.test_dispatch import eventually
    ADDRESS, SCRIPT = WORKFLOW_ADDRESS, WORKFLOW_SCRIPT

    run('enable', 'workflow')
    run('enable', 'dispatch')
    run('workflow', 'submit', ADDRESS, 'procedures', 'name=Code quality', cwd=mapped)
    run('workflow', 'add_prompt', ADDRESS, 'procedures', 'review', SCRIPT, cwd=mapped)
    run('set', '--layers', ','.join([*TOGGLED, 'procedures']), cwd=mapped)
    log = tmp_path / 'fake.jsonl'
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'workflow'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.task("{alarm}")')
    page.wait_for_selector(f'#task .workflow option[value="{ADDRESS}.review"]', state='attached')
    page.select_option('#task .workflow', f'{ADDRESS}.review')
    call = f'({{ok}}, {{address}}) := {ADDRESS}.review(target=this)'
    page.fill('#task .workflow-call', call)
    page.select_option('#task .condition', 'unbuilt')
    page.check('#task .start-agent')
    choose_agent(page, '#task', 'codex')
    page.click('#task .put')
    page.wait_for_selector('#task', state='hidden')
    ticket = next(record for record in store.work(limit=0).results if 'Workflow input: ' in (record.task or ''))
    assert ticket.address == 'code.alarm.audible'
    launch = json.loads(ticket.task.split('Workflow input: ', 1)[1].splitlines()[0])
    assert launch == {'call': call, 'element': 'code.alarm.audible'}
    eventually(lambda: store.ticket(ticket.id).work.done)
    assert json.loads(store.ticket(ticket.id).work.resolution) == [True, 'code.alarm.audible']
    assert problems == []


@pytest.mark.req('BASE-051')
@pytest.mark.req('VIEW-032')
@pytest.mark.req('VIEW-039')
@pytest.mark.parametrize('start_now', [False, True])
def test_a_workflow_ticket_keeps_its_call_when_queued_or_acp_cannot_start(run, web, mapped, browser, start_now):
    import sys

    from metaform.data import Store
    ADDRESS, SCRIPT = WORKFLOW_ADDRESS, WORKFLOW_SCRIPT

    run('enable', 'workflow')
    run('enable', 'dispatch')
    run('workflow', 'submit', ADDRESS, 'procedures', cwd=mapped)
    run('workflow', 'add_prompt', ADDRESS, 'procedures', 'review', SCRIPT, cwd=mapped)
    run('set', '--layers', ','.join([*TOGGLED, 'procedures']), cwd=mapped)
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE_AGENT}"', cwd=mapped)  # found when the page reads the agents
    started(run)
    store = Store('proj')
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.task("{store.element("code.alarm.audible").id}")')
    page.wait_for_selector(f'#task .workflow option[value="{ADDRESS}.review"]', state='attached')
    page.select_option('#task .workflow', f'{ADDRESS}.review')
    page.fill('#task .workflow-call', f'{ADDRESS}.review(target=this)')
    page.fill('#task .text', 'Return the reviewed address.')
    page.select_option('#task .condition', 'unbuilt')
    choose_agent(page, '#task', 'codex')
    run('set', '--dispatch-codex', 'metaform-nonexistent-acp-adapter', cwd=mapped)  # and gone by the time it starts
    page.set_checked('#task .start-agent', start_now)
    if start_now:
        with page.expect_response(lambda response: '/api/dispatch-start' in response.url) as failed:
            page.click('#task .put')
        assert failed.value.status == 400 and 'not found' in failed.value.json()['error']
    else:
        page.click('#task .put')
    page.wait_for_selector('#task', state='hidden')
    ticket = next(record for record in store.work(limit=0).results if 'Workflow input: ' in (record.task or ''))
    assert ticket.task.startswith('Return the reviewed address.\n\n')
    assert f'{ADDRESS}.review(target=this)' in ticket.task
    assert ticket.taken is None and ticket.done is None
    assert problems == (['Failed to load resource: the server responded with a status of 400 (Bad Request)']
                        if start_now else [])


@pytest.mark.req('BASE-051')
def test_workflow_picker_follows_the_enabled_module_and_launches_no_nonce_on_a_read(run, web, mapped):
    from metaform.data import Store
    ADDRESS, SCRIPT = WORKFLOW_ADDRESS, WORKFLOW_SCRIPT

    run('enable', 'workflow')
    run('workflow', 'submit', ADDRESS, 'procedures', 'name=Code quality', cwd=mapped)
    run('workflow', 'add_prompt', ADDRESS, 'procedures', 'review', SCRIPT, cwd=mapped)
    started(run)
    status, listed = api(web, '/api/workflows?project=proj')
    assert status == 200 and listed == {'enabled': True, 'workflows': []}
    run('set', '--layers', ','.join([*TOGGLED, 'procedures']), cwd=mapped)
    status, listed = api(web, '/api/workflows?project=proj')
    assert status == 200 and listed['enabled'] is True
    assert any(item['address'] == ADDRESS and item['prompt'] == ['review'] for item in listed['workflows'])
    with Store('proj', module='workflow').tables(write=False) as tx:  # a read of the picker starts no workflow run
        assert list(tx.rows('runs', limit=0).results) == []
    run('disable', 'workflow')
    assert api(web, '/api/workflows?project=proj') == (200, {'enabled': False, 'workflows': []})


@pytest.fixture
def watch_dispatch(dispatch_runners, mapped, tmp_path):
    """Record each runner before its start response reaches the page, including starts from the editors."""
    def watch(page):
        def start(route):
            response = route.fetch()
            if response.ok:
                dispatch_runners.append((response.json(), mapped, tmp_path / 'fake.jsonl'))
            route.fulfill(response=response)
        page.route('**/api/dispatch-start', start)
    return watch


@pytest.mark.req('VIEW-033')
def test_a_person_adds_an_element_joined_to_a_node_and_an_agent_is_started_to_validate_it(run, web, mapped, browser,
                                                                                          tmp_path, watch_dispatch):
    """A new element tool so the user can add and join something into the map, with an option to
    kick off an agent to pre-validate the new element, prompted in his words."""
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.inner_text('#menu button.element') == 'Add Element'
    page.click('#menu button.element')
    page.wait_for_selector('#element:not([hidden])')
    assert 'audible alarm' in page.inner_text('#element .title') or 'alarm' in page.inner_text('#element .title')
    page.click('#element .add')                                       # an address that is not given is not written
    page.wait_for_timeout(400)
    assert page.is_visible('#element') and Store('proj').element('code.alarm.visible') is None
    page.fill('#element .address', 'code.alarm.visible')
    page.fill('#element .length', '2')
    page.fill('#element .name', 'Flash Alert')                         # its canonical name
    page.select_option('#element .receives', 'node')                  # the alarm holds the purpose; the new part serves it
    page.fill('#element .purpose', 'Tell a cook who cannot hear that the time is up.')
    page.fill('#element .ef', 'Flashes a lamp when the timer runs out.')
    page.check('#element .validate')
    choose_agent(page, '#element', 'codex')
    page.click('#element .add')
    page.wait_for_function('() => document.querySelector("#element").hidden')
    store = Store('proj')
    made = store.element('code.alarm.visible')
    assert made is not None and (made.layer, made.name_length, made.short_name, made.name) == (
        'additions', 2, 'visible alarm', 'Flash Alert')
    joined = [join for join in store.joins('code.alarm.audible').results
              if [held.element_id for held in join.elements] == [made.id]]
    assert [(join.receiver, join.layer, join.purpose, join.ef) for join in joined] == [
        (alarm, 'additions', 'Tell a cook who cannot hear that the time is up.', 'Flashes a lamp when the timer runs out.')]
    work = store.work(Node_of('code.alarm.visible'), 'unbuilt', True).results
    assert len(work) == 1 and work[0].task == f'{VALIDATE} The element is code.alarm.visible.'
    page.wait_for_function(f'() => window.metaform.look("{made.id}").ghost === true', timeout=8000)
    made_session = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/new')
    assert Path(made_session['message']['params']['cwd']).resolve() == Path(mapped).resolve()
    told = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt')
    assert work[0].id in told['message']['params']['prompt'][0]['text']
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=30000)
    assert Store('proj').ticket(work[0].id).work.taken_by.startswith('codex ')
    # without the option nothing is run
    page.evaluate(f'window.metaform.element("{alarm}")')
    page.fill('#element .address', 'code.alarm.silent')
    page.select_option('#element .receives', 'new')                   # here the new part holds the purpose
    page.fill('#element .purpose', 'Stay quiet at night.')
    page.fill('#element .ef', 'Sounds only when asked to.')
    page.uncheck('#element .validate')
    page.click('#element .add')
    page.wait_for_function('() => document.querySelector("#element").hidden')
    silent = Store('proj').element('code.alarm.silent')
    assert [[held.element_id for held in join.elements] for join in Store('proj').joins('code.alarm.silent').results] == [
        [alarm]] and silent is not None
    page.wait_for_timeout(1200)
    assert sum(json.loads(line).get('message', {}).get('method') == 'session/new'
               for line in log.read_text().splitlines()) == 1
    run('dispatch', 'stop', work[0].id, cwd=mapped)
    assert problems == []


def Node_of(address):
    from metaform.data import Node
    return Node('element', address)


@pytest.mark.req('VIEW-019')
@pytest.mark.req('PROJ-030')
def test_the_clear_is_in_the_administration_menu_asks_are_you_sure_and_its_backup_is_restored_from_the_menu(
        run, home, web, mapped, browser):
    """The clear is in an administration menu, says are you sure, backs the project up, allows
    restoration easily and tells the user. a clear that also offers to restore is not good design;
    the clear only clears, and a backup is restored from the menu's Restore a backup."""
    from metaform.data import Store
    started(run)
    before = sorted(entry['element']['address'] for entry in keys_of(web)[0]['elements'])
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#adminBtn')
    page.wait_for_timeout(500)
    assert page.is_disabled('#restoreBtn')                            # there is no backup yet
    page.click('#clearBtn')
    page.wait_for_selector('#clearbox .warn')
    asked = page.inner_text('#clearbox')
    assert asked.startswith('Are you sure?') and 'It is backed up first.' in asked
    assert 'bring it back' not in asked and page.locator('#clearbox button').count() == 2   # Clear it and Keep it
    page.fill('#clearbox input.typed', 'confirm')
    page.click('#clearbox button.confirm')
    page.wait_for_selector('#clearbox .said')
    told = page.inner_text('#clearbox')
    (kept,) = [path.name for path in (home / 'backups' / 'clear' / 'proj').iterdir()]
    assert f'Backed up as {kept}.' in told
    assert page.locator('#clearbox button.restore').count() == 0       # the clear offers no restore
    page.wait_for_function('() => document.querySelector("#count").textContent.includes("no metaform yet")')
    page.click('#clearbox button.keep')
    page.click('#adminBtn')                                           # restoring is the menu's own act
    page.wait_for_selector('#restoreBtn:not([disabled])')            # the page has looked for backups
    page.click('#restoreBtn')
    page.wait_for_selector('#clearbox .backups button')
    listed = page.locator('#clearbox .backups li').all_inner_texts()
    assert len(listed) == 1 and listed[0].startswith(kept)
    page.click('#clearbox .backups button')
    page.wait_for_selector('#clearbox .restored')
    assert page.inner_text('#clearbox .restored').startswith(f'Restored proj from {kept}: ')
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.graph().nodes.length > 0')
    assert sorted(entry['element']['address'] for entry in keys_of(web)[0]['elements']) == before
    assert Store('proj').element('code.timer.kitchen') is not None
    assert problems == []


@pytest.mark.req('VIEW-034')
def test_the_person_writes_the_note_at_a_node_in_the_page_and_an_agent_only_reads_it(run, web, mapped, browser):
    """The note is the person's: written for people to read on the node, not for agents, which have the memory
    server. One single note, not a list, of at most 2048 characters. The fixture's folder leaves memory out, and the note shows all the same."""
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').id
    noted = lambda: json.loads(run('memory', 'note', 'element:code.alarm.audible', '--json', cwd=mapped).stdout)['note']
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 0'
    page.click('#menu button.notes')
    page.wait_for_selector('#notes:not([hidden])')
    assert page.get_attribute('#notes textarea', 'maxlength') == '2048'
    page.fill('#notes textarea', 'The tone is 2 kHz. Too quiet in a loud kitchen; ask before changing the pitch.')
    assert page.inner_text('#notes .count') == '78 / 2048'
    page.click('#notes .save')                                        # the person writes the note in the page
    page.wait_for_function('() => document.querySelector("#notes .by").textContent.includes("you")')
    assert (noted()['text'], noted()['by']) == (
        'The tone is 2 kHz. Too quiet in a loud kitchen; ask before changing the pitch.', 'user')
    page.click('#notes .close')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 1'      # one note, never a list
    page.keyboard.press('Escape')
    refused = run('memory', 'note', 'element:code.alarm.audible', 'text=Raised to 3 kHz.', cwd=mapped, ok=False)
    assert refused.returncode == 2 and 'The note is written only from the web page.' in refused.stderr  # the AI reads it
    assert noted()['text'] == 'The tone is 2 kHz. Too quiet in a loud kitchen; ask before changing the pitch.'
    page.evaluate(f'window.metaform.note("{alarm}")')
    page.wait_for_function('() => document.querySelector("#notes textarea").value.startsWith("The tone is 2 kHz.")')
    page.fill('#notes textarea', '')
    page.click('#notes .save')                                        # empty, it is cleared
    page.wait_for_function('() => document.querySelector("#notes .by").textContent.includes("No note")')
    assert noted() is None
    page.click('#notes .close')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 0'
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-030')
@pytest.mark.req('VIEW-034')
@pytest.mark.req('VIEW-032')
@pytest.mark.req('VIEW-033')
@pytest.mark.req('VIEW-013')
def test_a_map_change_keeps_every_open_write_window_and_editor_open_with_its_text(run, web, mapped, browser):
    """A screen update must not close a message being typed or lose what was written. Each write window is opened and typed into, a map change reaches the page, and each is still open with
    what was typed in it."""
    from metaform.data import Node, Store, prompts
    store = Store('proj')
    store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?', suggestions=['Yes', 'No'])
    alarm = store.element('code.alarm.audible').id
    prompts.add_prompt('practices', 'markdown', 'one\n')
    notes = store.layer_ref('notes')
    prompts.record_use(prompts.prompt_version('practices').version_id, 'proj', notes.base_id, notes.id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    # the prompt editor, VIEW-013
    page.click('#t-prov')
    page.click('#p-prov .layerlist button:has-text("notes")')
    page.click('#p-prov button.open-prompt')
    page.wait_for_function('() => window.metaform.editor() && window.metaform.editor().getValue() === "one\\n"')
    page.evaluate('window.metaform.editor().setValue("one, edited\\n")')
    # answering at a node, VIEW-021 and VIEW-030: typed under Other
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.unread')
    page.wait_for_selector('#float textarea.answer')               # the box takes any answer beside the suggestions
    page.fill('#float textarea.answer', 'Keep it, but ask the cook.')
    # Notes, VIEW-034; Add Element, VIEW-033; Add Task, VIEW-032, typed into last
    page.evaluate(f'window.metaform.note("{alarm}")')
    page.wait_for_selector('#notes:not([hidden])')
    page.fill('#notes textarea', 'The tone is too quiet.')
    page.evaluate(f'window.metaform.element("{alarm}")')
    page.fill('#element .address', 'code.alarm.audible.chime')
    page.fill('#element .purpose', 'Ring a softer tone.')
    page.evaluate(f'window.metaform.task("{alarm}")')
    page.focus('#task .text')                                          # the windows overlap; it opens focused
    page.keyboard.type('Make the alarm louder')
    kept = '''() => { const $ = s => document.querySelector(s), shown = s => Boolean($(s)?.checkVisibility());
        return {open: ['#float', '#notes', '#element', '#task', '#p-prompt'].filter(shown),
            answer: $('#float textarea.answer')?.value ?? null, answering: shown('#float textarea.answer'),
            note: $('#notes textarea').value, address: $('#element .address').value, purpose: $('#element .purpose').value,
            task: $('#task .text').innerText.trim(), prompt: window.metaform.editor().getValue(),
            typing: $('#task .text').contains(document.activeElement)}; }'''
    typed = {'open': ['#float', '#notes', '#element', '#task', '#p-prompt'],
             'answer': 'Keep it, but ask the cook.', 'answering': True, 'note': 'The tone is too quiet.',
             'address': 'code.alarm.audible.chime', 'purpose': 'Ring a softer tone.',
             'task': 'Make the alarm louder', 'prompt': 'one, edited\n', 'typing': True}
    # a map change reaches the page: an agent asks another question at the node the answer is being written at
    before = page.evaluate('window.metaform.changes()')
    run('map', 'ask', 'element:code.alarm.audible', 'Is the tone too high?', *ASK_FORM, cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {before}', timeout=10000)  # read and drawn again
    assert page.inner_text('#messages').strip() == 'Messages 2'
    assert page.evaluate(kept) == typed
    # and one that shows another metaform, read as on opening
    before = page.evaluate('window.metaform.changes()')
    run('add', 'base', 'fresh', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {before}', timeout=10000)
    assert page.evaluate('[...document.querySelectorAll("#mf option")].find(o => o.selected).textContent') == 'fresh · active'
    assert page.evaluate(kept) == typed
    page.keyboard.type(' now')
    assert page.inner_text('#task .text').strip() == 'Make the alarm louder now'
    assert problems == []


SAMPLE_BOTH = '''key => { window.samples = []; window.sampling = true;
    ''' + FADES + '''
    const tick = () => { const svg = document.querySelector("#map2d svg"), box = svg ? svg.viewBox.baseVal : null;
        const seen = window.metaform.screen3d(key), stage = document.querySelector("#stage");
        window.samples.push({base: svg ? svg.dataset.base === "yes" : false, o: svg ? Number(getComputedStyle(svg).opacity) : 1,
            w: box ? box.width : 0, o3: Number(getComputedStyle(stage).opacity), f: svg ? part(svg) : null, f3: part(stage),
            r: seen ? seen.r : 0, memory: Boolean(window.metaform.memory())});
        if (window.sampling) requestAnimationFrame(tick); };
    requestAnimationFrame(tick); }'''


def within(inner, outer):
    return (outer['left'] - 1 <= inner['left'] and inner['right'] <= outer['right'] + 1
            and outer['top'] - 1 <= inner['top'] and inner['bottom'] <= outer['bottom'] + 1)


def rect_of(page, selector):
    return page.evaluate(f'''(() => {{ const box = document.querySelector("{selector}").getBoundingClientRect();
        return {{left: box.left, right: box.right, top: box.top, bottom: box.bottom}}; }})()''')


@pytest.mark.req('VIEW-031')
@pytest.mark.req('VIEW-030')
def test_the_memories_of_a_node_open_from_its_menu_as_a_graph_of_their_own_in_both_views(run, web, mapped, browser):
    """The menu of a node has an entry for its memories; choosing it, in the 2D map or the 3D map,
    shows the memory network of that node in both views; the view zooms into the node as the map gives way to it and
    opens with the whole memory network in view; going back returns to the map."""
    for name, observation, node in (('countdown drift', 'The countdown drifts under load.', 'code.timer.kitchen'),
                                    ('quiet tone', 'Too quiet.', 'code.alarm.audible'),
                                    ('cook waits', 'The cook waits at the stove.', 'exterior.cook'),
                                    ('display glow', 'The display glows.', 'code.timer.kitchen.display')):
        remember(run, mapped, 'create_entities', [entity(name, observation)], f'element:{node}')
    remember(run, mapped, 'create_relations', [
        {'from': 'countdown drift', 'to': 'quiet tone', 'relationType': 'drives'},      # one the kitchen's memory holds
        {'from': 'cook waits', 'to': 'countdown drift', 'relationType': 'waits on'},    # one held toward it
        {'from': 'quiet tone', 'to': 'cook waits', 'relationType': 'wakes'},           # between two it names
        # and one of the tone's own, to a memory the kitchen timer's memory does not name
        {'from': 'quiet tone', 'to': 'display glow', 'relationType': 'shown on'}])
    drift, tone, waits = 'e:countdown drift', 'e:quiet tone', 'e:cook waits'
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at = keys_of(web)
    kitchen, cook = at['code.timer.kitchen'], at['exterior.cook']
    outer = next(join['id'] for join in expected['joins'] if join['receiver'] == cook)
    still3d(page, 1)  # the page fits the whole 3D map into view once, a moment after it opens
    set_layer(page, 'memory', True)  # the fixture's folder leaves memory out; it is turned on in this view
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.loaded() && '
                           'window.metaform.graph().nodes.filter(node => node.layer === "memory").length === 4 && '
                           'document.querySelector("#p-object").textContent.includes("The countdown drifts")')
    entries = lambda: page.eval_on_selector_all(
        '#menu button', 'found => found.map(one => [one.className, one.textContent, one.disabled])')
    selected = lambda: page.evaluate('window.metaform.selected()')
    network = lambda: page.evaluate('window.metaform.memory()')
    base = page.evaluate('() => { const svg = document.querySelector("#map2d svg"); svg.dataset.base = "yes"; '
                         'return document.querySelectorAll("#map2d svg g.node").length; }')

    # from the 2D map: a right-click on the node's own box
    page.evaluate(f'window.metaform.select("{kitchen}")')
    still2d(page)  # both cameras settle on it
    still3d(page, 1)
    box = page.evaluate(f'window.metaform.box2d("{kitchen}")')
    page.mouse.click(box['left'] + 6, box['top'] + 6, button='right')  # its own box, clear of the tick loop inside it
    page.wait_for_selector('#menu:not([hidden])')
    assert entries()[2] == ['memories', 'Memories 1', False]  # the one memory kept at it
    page.evaluate(SAMPLE_BOTH, kitchen)
    page.click('#menu button.memories')
    page.wait_for_function(f'() => window.metaform.memory() && window.metaform.memory().key === "{kitchen}"')
    page.wait_for_function('() => { const last = window.samples.at(-1);'  # the network fades in
                           ' return last && last.memory && !last.base && last.o === 1 && last.o3 === 1; }')
    samples = page.evaluate('() => { window.sampling = false; return window.samples; }')
    going, shown = [one for one in samples if not one['memory']], [one for one in samples if one['memory']]
    assert going and shown
    assert max(one['r'] for one in going) > going[0]['r'] * 2  # the 3D view zooms into the node
    faded(page, '3d', 0, going, 'o3', 'f3')                      # as the map gives way to it
    faded(page, '3d', 1, shown, 'o3', 'f3')                      # and the memory network comes in
    assert shown[-1]['o3'] == 1
    was = [one for one in going if one['base']]
    # the 2D view the same; the kitchen timer is a large box, holding its tick loop, so the view narrows less onto it
    faded(page, 'base', 0, was)
    assert was[-1]['w'] < was[0]['w'] * 0.9
    own = [one for one in shown if not one['base']]
    faded(page, 'own', 1, own)
    assert own and own[-1]['o'] == 1

    # the memory network: the node's entities and the relations between them, and nothing else, in both views
    drawn = network()
    assert sorted(drawn['nodes']) == sorted([kitchen, drift, tone, waits]) == sorted(drawn['nodes2d'])
    assert sorted((link['source'], link['relation'], link['target']) for link in drawn['links']) == sorted(
        [(kitchen, None, drift),  # the memory join that ties its memory to it
         (drift, 'drives', tone), (waits, 'waits on', drift), (tone, 'wakes', waits)])
    words = page.evaluate('document.querySelector("#map2d svg").textContent')
    assert all(word in words for word in ('drives', 'waits on', 'wakes')) and 'shown on' not in words
    assert '4 nodes shown' in page.inner_text('#count')
    assert not page.query_selector('#map2d svg[data-base]')  # the map gave way to it
    # it opens with the whole of it in view, in both views
    stage, view = rect_of(page, '#stage'), rect_of(page, '#viewport')
    for key in drawn['nodes']:
        seen = page.evaluate(f'window.metaform.screen3d("{key}")')
        assert within({'left': seen['x'], 'right': seen['x'], 'top': seen['y'], 'bottom': seen['y']}, stage), key
        assert within(page.evaluate(f'window.metaform.box2d("{key}")'), view), key
    assert 'dish timer' in inside(page)[1]
    # the node is selected and the panel shows what is known about it
    assert selected() == kitchen
    panel = page.inner_text('#p-object')
    assert 'The countdown drifts under load.' in panel and 'drives' in panel and 'waits on' in panel
    page.evaluate(f'window.metaform.click3d("{tone}")')
    assert selected() == tone and 'wakes' in page.inner_text('#p-object')
    box = page.evaluate(f'window.metaform.box2d("{waits}")')
    page.mouse.click((box['left'] + box['right']) / 2, (box['top'] + box['bottom']) / 2)
    assert selected() == waits and network()['key'] == kitchen  # a click in it selects, and stays in it

    # going back returns to the map, the same 2D map, never laid out again, and the whole 3D map
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => !window.metaform.memory() && document.querySelector("#map2d svg[data-base]")')
    page.wait_for_function('() => window.metaform.drawn().nodes === window.metaform.graph().nodes.length')
    assert page.evaluate('document.querySelectorAll("#map2d svg g.node").length') == base
    assert selected() == kitchen and not page.is_visible('#crumbs')

    # from the 3D map: the node's right-click; back by the breadcrumb, and by Alt and Left
    page.evaluate(f'window.metaform.menu("{kitchen}")')
    page.click('#menu button.memories')
    page.wait_for_function(f'() => window.metaform.memory() && window.metaform.memory().key === "{kitchen}"')
    assert sorted(network()['nodes']) == sorted([kitchen, drift, tone, waits])
    page.click('#crumbs a')
    page.wait_for_function('() => !window.metaform.memory() && document.querySelector("#map2d svg[data-base]")')
    page.evaluate(f'window.metaform.memories("{kitchen}")')
    page.wait_for_function('() => window.metaform.memory()')
    map_key(page, 'Alt+ArrowLeft')
    page.wait_for_function('() => !window.metaform.memory() && document.querySelector("#map2d svg[data-base]")')

    # a node with no memories cannot open them
    page.evaluate(f'window.metaform.menu("p:{outer}")')
    assert entries()[2] == ['memories', 'Memories 0', True]
    page.keyboard.press('Escape')

    # with reduced motion the views change at once
    page.emulate_media(reduced_motion='reduce')
    page.evaluate(SAMPLE_BOTH, kitchen)
    page.evaluate(f'window.metaform.memories("{kitchen}")')
    page.wait_for_function('() => window.metaform.memory()')
    page.wait_for_timeout(400)
    still = page.evaluate('() => { window.sampling = false; return window.samples; }')
    assert still and all(one['o'] == 1 and one['o3'] == 1 for one in still)
    page.keyboard.press('Escape')  # lets go of the selection
    page.keyboard.press('Escape')  # and with nothing selected goes back
    page.wait_for_function('() => !window.metaform.memory()')

    # the memories are read as every read of the page is, with the layers in view, VIEW-004
    set_layer(page, 'memory', False)
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.loaded() && '
                           '!window.metaform.graph().nodes.some(node => node.layer === "memory")')
    page.evaluate(f'window.metaform.menu("{kitchen}")')
    assert entries()[2] == ['memories', 'Memories 0', True]
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_the_edges_of_the_3d_map_are_smoothed_where_a_graphics_card_draws_them(run, web, mapped, browser):
    """The 3D graph needs antialiasing, the joins break apart when zoomed out. The picture itself
    is judged by eye on a graphics card: the renderer these tests run on draws with the processor, where the samples
    changed nothing that could be measured and cost four frames in ten."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    for name in ('ANGLE (NVIDIA, NVIDIA GeForce RTX 5090 Direct3D11 vs_5_0 ps_5_0, D3D11)', 'Apple M3',
                 'ANGLE (Intel, Mesa Intel(R) UHD Graphics 630, OpenGL 4.6)'):
        assert page.evaluate('name => window.metaform.samplesFor(name)', name) == 4, name
    for name in ('ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)',
                 'llvmpipe (LLVM 17.0.6, 256 bits)', 'Microsoft Basic Render Driver'):
        assert page.evaluate('name => window.metaform.samplesFor(name)', name) == 0, name
    drawn_by = page.evaluate('window.metaform.drawnBy()')
    assert drawn_by and page.evaluate('window.metaform.samples3d()') == page.evaluate(
        'name => window.metaform.samplesFor(name)', drawn_by)  # the buffers take what the rule gives for this machine
    assert problems == []


def remove_project(port, project='proj', **given):
    return api(port, '/api/remove-project', method='POST', body=json.dumps({'project': project, **given}),
               headers=own_write(port))


HELD = ('proj holds one base, main, and no report files. Only an empty project is removed; clearing it backs it '
        'up first.')


@pytest.mark.req('PROJ-031')
@pytest.mark.req('VIEW-019')
def test_the_page_removes_only_an_empty_project_as_the_command_does_and_only_with_confirm(run, home, web, mapped):
    started(run)
    assert api(web, '/api/remove-preview?project=proj') == (200, {'project': 'proj', 'held': HELD})
    before = kept(home)
    assert remove_project(web, confirm=True) == (400, {'error': HELD, 'next': 'Use Clear project first.'})
    assert kept(home) == before
    run('clear', 'project', '--confirm', cwd=mapped)
    caution = run('remove', 'project', cwd=mapped, ok=False).stderr.splitlines()[0].removeprefix('Error: ')
    assert api(web, '/api/remove-preview?project=proj') == (200, {'project': 'proj', 'caution': caution})
    for given in ({}, {'confirm': False}):
        assert remove_project(web, **given) == (400, {'error': caution, 'next': 'If you are sure: send confirm true'})
    status, answer = remove_project(web, 'nobody', confirm=True)
    assert status == 404 and answer['next'] == 'metaform list projects'
    files = sorted(path.name for path in mapped.rglob('*'))
    assert remove_project(web, confirm=True) == (200, {'project': 'proj',
                                               'said': 'Removed proj. Its folder and files were not touched.'})
    assert 'proj' not in [line.split()[0] for line in run('list', 'projects').stdout.splitlines()]
    assert sorted(path.name for path in mapped.rglob('*')) == files
    assert (home / 'backups' / 'clear' / 'proj').is_dir()


@pytest.mark.req('PROJ-031')
@pytest.mark.req('VIEW-019')
def test_remove_project_in_the_administration_menu_names_what_a_project_holds_then_removes_it_once_empty(
        run, home, web, mapped, browser, tmp_path):
    other_folder = tmp_path / 'other'
    other_folder.mkdir()
    run('add', 'project', 'other', str(other_folder))
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.select_option('#proj', 'proj')
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#adminBtn')
    assert page.inner_text('#adminbox #removeBtn') == 'Remove project'
    page.click('#removeBtn')
    page.wait_for_selector('#clearbox .held')
    assert page.inner_text('#clearbox .held') == HELD and page.query_selector('#clearbox button.confirm') is None
    page.click('#clearbox button.keep')
    run('clear', 'project', '--confirm', cwd=mapped)
    caution = run('remove', 'project', cwd=mapped, ok=False).stderr.splitlines()[0].removeprefix('Error: ')
    page.click('#adminBtn')
    page.click('#removeBtn')
    page.wait_for_selector('#clearbox button.confirm')
    assert caution in page.inner_text('#clearbox')
    page.click('#clearbox button.keep')
    assert page.is_hidden('#clearbox')
    assert 'proj' in [line.split()[0] for line in run('list', 'projects').stdout.splitlines()]
    page.click('#adminBtn')
    page.click('#removeBtn')
    page.fill('#clearbox input.typed', 'confirm')
    page.click('#clearbox button.confirm')
    page.wait_for_function('() => ![...document.querySelectorAll("#proj option")].some(o => o.value === "proj")',
                           timeout=5000)
    assert page.input_value('#proj') == 'other'
    assert 'proj' not in [line.split()[0] for line in run('list', 'projects').stdout.splitlines()]
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-018')
def test_the_page_says_it_is_loaded_only_once_it_has_read_what_it_loads(run, web, mapped, browser):
    """Found 2026-10-02: choosing a project in the selector started a load whose first read came before the page
    counted itself as loading, and the panel's node read came after it said it was loaded, so a command run once
    loaded() was true could clear the map under the page's own reads. Every read the page makes is held back here, so
    the page is loading from the choice until each read of the load, the panel's node read among them, has answered."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate("""() => {
        window.held = {asked: 0, answered: 0};
        const fetched = window.fetch;
        window.fetch = async (url, ...rest) => {
            if (!String(url).startsWith('/api/') || String(url).startsWith('/api/events')) return fetched(url, ...rest);
            const node = String(url).startsWith('/api/node?');
            window.held.asked++;
            if (node) window.held.nodes = (window.held.nodes || 0) + 1;
            await new Promise(done => setTimeout(done, node ? 800 : 150));
            const response = await fetched(url, ...rest);
            window.held.answered++;
            return response;
        };
    }""")
    page.select_option('#proj', 'proj')
    assert page.evaluate('window.metaform.loaded()') is False
    page.wait_for_function('() => window.metaform.loaded()')
    held = page.evaluate('window.held')
    assert held.get('nodes', 0) >= 1 and held['answered'] == held['asked']
    assert problems == []


@pytest.mark.req('VIEW-032')
@pytest.mark.req('VIEW-008')
def test_dragging_the_2d_map_or_the_task_chart_moves_it_and_selects_no_label_text(run, web, mapped, browser):
    """Dragging the 2D map selected the label text of every node, and the next drag dragged the
    labels instead of the map. A drag that starts on a label and sweeps across the others moves the view, selects no
    text, and the drag after it moves the view again."""
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')

    def sweep(start, view):
        """Two drags from a label across the chart, each one checked for the view moving and no text selected."""
        for _ in range(2):
            before = [float(number) for number in view().split()]
            page.mouse.move(*start)
            page.mouse.down()
            for step in range(1, 13):
                page.mouse.move(start[0] - step * 20, start[1] - step * 8)
            assert page.evaluate('getSelection().toString()') == ''  # while it drags, not only once it is let go
            page.mouse.up()
            assert page.evaluate('getSelection().toString()') == ''
            after = [float(number) for number in view().split()]
            assert after[0] > before[0] and after[1] > before[1]  # dragged up and left, the view moves down and right
            page.wait_for_timeout(300)

    zoomed_to(page, 2 * page.evaluate(HEADING))  # where the map runs past the pane and a drag has somewhere to take it, VIEW-041
    still2d(page)
    label = page.evaluate("""(() => { const box = document.querySelector('#map2d svg g.node.sel text').getBoundingClientRect();
        return [box.left + box.width / 2, box.top + box.height / 2]; })()""")
    sweep(label, lambda: page.get_attribute('#map2d svg', 'viewBox'))
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.task')
    page.wait_for_selector('#task .chart svg g[data-address] text')
    page.wait_for_timeout(900)
    page.locator('#task .chart').scroll_into_view_if_needed()          # below the form, where the window scrolls to it
    label = page.evaluate("""(() => { const box = document.querySelector('#task .chart svg g[data-address] text').getBoundingClientRect();
        return [box.left + box.width / 2, box.top + box.height / 2]; })()""")
    sweep(label, lambda: page.get_attribute('#task .chart svg', 'viewBox'))
    assert problems == []



@pytest.mark.req('VIEW-036')
def test_a_nodes_menu_opens_its_work_history_every_ticket_open_and_closed_with_its_steps(run, web, mapped, browser):
    """Right-clicking a node gives access to its work history: every ticket on it, open and done,
    newest first, each with its kind, its column, who took it, the steps the agent filed and how it was resolved."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    old = store.add_work(Node('element', 'code.alarm.audible'), None, task='wire the tone', kind='broken')
    store.take_work(old.id, steps=2, by='codex')
    store.step_work(old.id, 'Traced the pin.')
    store.step_work(old.id, 'Wired the driver.')
    store.finish_work(old.id, 'wired')
    store.add_work(Node('element', 'code.alarm.audible'), None, task='a softer tone', held=True)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.history') == 'Work history 2'
    page.click('#menu button.history')
    page.wait_for_selector('#float:not([hidden]) .ticket')
    tickets = page.locator('#float .ticket').all_inner_texts()
    assert len(tickets) == 2
    newest, oldest = tickets
    assert 'task' in newest and 'backlog' in newest and 'a softer tone' in newest
    for words in ('broken', 'done', 'wire the tone', 'codex', 'Traced the pin.', 'Wired the driver.', 'wired'):
        assert words in oldest, (words, oldest)
    assert 'Work history' in page.text_content('#float .title')
    assert page.locator('#float .ticket .age').all_inner_texts() == ['now', 'now']  # every ticket shows its age now
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_the_board_holds_the_tickets_in_four_columns_and_a_card_dragged_moves_its_ticket(run, web, mapped, browser,
                                                                                     monkeypatch):
    """An actual classic kanban window you can open that mirrors the features in a traditional
    kanban: columns with counts, cards with their kind, nodes and progress, dragging between and within columns, a
    search and a filter by kind, and adding a card."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    kitchen = Node('element', 'code.timer.kitchen')
    todo = store.add_work(Node('element', 'code.alarm.audible'), None, task='a quieter tone', links=[kitchen],
                          kind='broken')
    store.add_work(kitchen, None, task='a second countdown', held=True)
    from datetime import UTC, datetime, timedelta

    from metaform import home
    with monkeypatch.context() as clock:
        earlier = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        clock.setattr(home, 'now', lambda: earlier)
        doing = store.add_work(Node('element', 'code.alarm.audible'), None, task='wire the tone', kind='broken')
    store.take_work(doing.id, steps=3, by='codex')
    store.step_work(doing.id, 'Traced the pin.')
    done = store.add_work(kitchen, None, task='the display')
    store.finish_work(done.id, 'built')
    # one card per finding: none for a record the intake replaced, one for a finding on an element and its join
    join = store.joins('code.timer.kitchen').results[0]
    finding = store.add_work(Node('element', join.elements[0].address), 'broken', note='never sounds')
    repeated = store.add_work(Node('join', join.id), 'broken', note='never sounds')
    replaced = store.add_work(kitchen, 'missing', note='no display')
    store.finish_work(replaced.id, 'Replaced by broken.')
    # a record with neither a task nor a marker is not work, open or closed: no card, MAP-046; the store refuses one
    # shown nowhere, so the one left is a stage, drawn on its node, ticket 97085c0e
    empty = store.add_work(kitchen, 'unbuilt')
    closed = store.add_work(kitchen, 'under-construction')
    store.finish_work(closed.id, 'Not a ticket.', outcome='cancelled')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.click('#boardBtn')
    page.wait_for_selector('#board:not([hidden]) .card')
    # the map's labels stay under the board, whatever their own draw order, VIEW-038
    assert page.evaluate('''window.metaform.labels3d().filter(label => !label.hidden).every(label => {
        const x = (label.left + label.right) / 2, y = (label.top + label.bottom) / 2;
        const board = document.querySelector("#board").getBoundingClientRect();
        if (x < board.left || x > board.right || y < board.top || y > board.bottom) return true;
        return document.querySelector("#board").contains(document.elementFromPoint(x, y)); })''')
    count = lambda column: page.text_content(f'#board .column[data-column="{column}"] .tally')
    held = [record for record in Store('proj').work(limit=0).results
            if record.id not in (repeated.id, replaced.id, empty.id, closed.id)]
    assert page.locator(f'#board .card[data-id="{finding.id}"]').count() == 1
    assert page.locator(f'#board .card[data-id="{empty.id}"], #board .card[data-id="{closed.id}"]').count() == 0
    expected = [str(sum(record.column == column for record in held)) for column in ('backlog', 'todo', 'doing', 'done')]
    assert [count(column) for column in ('backlog', 'todo', 'doing', 'done')] == expected
    card = page.locator(f'#board .card[data-id="{todo.id}"]')
    assert card.get_attribute('data-kind') == 'broken' and 'a quieter tone' in card.inner_text()
    chips = card.locator('.node').all_inner_texts()
    assert len(chips) == 2                                              # the node assigned and the one for reference
    worked = page.locator(f'#board .card[data-id="{doing.id}"]')
    assert 'codex' in worked.inner_text() and '1/3' in worked.inner_text()
    assert worked.locator('.age').inner_text() == 'now'
    # a card is drawn again only when what it shows changed: a move rebuilds the moved card, not the others
    page.evaluate('document.querySelectorAll("#board .card").forEach(card => { card.kept = true; })')
    start = page.locator(f'#board .card[data-id="{todo.id}"] .lead').bounding_box()
    end = page.locator('#board .column[data-column="doing"] .cards').bounding_box()
    page.mouse.move(start['x'] + 10, start['y'] + start['height'] / 2)
    page.mouse.down()
    page.mouse.move(end['x'] + end['width'] / 2, end['y'] + 40, steps=12)
    page.mouse.up()
    page.wait_for_function(f'() => document.querySelector(\'#board .column[data-column="doing"] .card[data-id="{todo.id}"]\')')
    moved = next(record for record in Store('proj').work(limit=0).results if record.id == todo.id)
    assert (moved.column, moved.taken_by, moved.kind) == ('doing', 'user', 'broken')
    assert int(count('doing')) == int(expected[2]) + 1 and int(count('todo')) == int(expected[1]) - 1
    kept = 'id => Boolean(document.querySelector(`#board .card[data-id="${id}"]`).kept)'
    assert not page.evaluate(kept, todo.id) and page.evaluate(kept, done.id)
    page.evaluate('document.querySelectorAll("#board .card").forEach(card => { card.kept = true; })')
    page.fill('#board .search', 'quieter')
    assert page.locator('#board .card:visible').count() == 1
    page.fill('#board .search', '')
    page.click('#board .kinds [data-kind="broken"]')                    # a kind toggled off hides its cards
    assert page.locator(f'#board .card[data-id="{todo.id}"]').is_hidden()
    page.click('#board .kinds [data-kind="broken"]')
    assert page.evaluate('[...document.querySelectorAll("#board .card")].every(card => card.kept)')  # drawn, none made
    # a ticket read again that differs only in the age the server counts is the ticket held, not a change
    assert page.evaluate('''async id => {
        const {S} = await import('/page/app/core/reads.js'), ops = await import('/page/app/live/ops.js');
        const held = S.tickets.find(one => one.id === id);
        await new Promise(done => setTimeout(done, 1500));  // its age_seconds is now another
        ops.ticketsHeard({work_ids: [id]});
        await ops.ticketsChanged();
        return Boolean(held) && S.tickets.find(one => one.id === id) === held; }''', doing.id)
    page.locator(f'#board .card[data-id="{todo.id}"] .node').first.click()
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"')
    page.click('#board .add')
    page.wait_for_selector('#task:not([hidden])')
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_board_priority_controls_save_order_with_filters_and_after_reloading(run, web, mapped, browser):
    from metaform.data import Node, Store
    store = Store('proj')
    node = Node('element', 'code.alarm.audible')
    tickets = [store.add_work(node, None, task=f'priority {name}') for name in ('first', 'second', 'third')]
    for position, ticket in enumerate(tickets):
        store.move_work(ticket.id, 'todo', position)
    started(run)
    page, problems, _ = opened(browser, web)
    page.click('#boardBtn')
    column = '#board .column[data-column="todo"]'
    ids = [ticket.id for ticket in tickets]
    def control(index, name):
        return page.locator(f'{column} .card[data-id="{ids[index]}"]').get_by_role('button', name=name, exact=True)

    def expect_order(expected):
        page.wait_for_function('''expected => [...document.querySelectorAll('#board .column[data-column="todo"] .card')]
            .map(card => card.dataset.id).filter(id => expected.includes(id)).join() === expected.join()''', arg=expected)
        saved = sorted((record for record in Store('proj').work(limit=0).results if record.id in ids),
                       key=lambda record: record.position)
        assert [record.id for record in saved] == expected
        assert all(record.column == 'todo' and record.taken is None for record in saved)

    expect_order(ids)
    assert control(0, 'Move up').is_disabled()
    control(2, 'Move to top').click()
    expect_order([ids[2], ids[0], ids[1]])
    assert page.locator('#float').is_hidden()  # ordering does not open the card's history
    control(2, 'Move down').click()
    expect_order([ids[0], ids[2], ids[1]])
    page.fill('#board .search', 'priority second')
    control(1, 'Move up').click()
    expect_order([ids[0], ids[1], ids[2]])
    assert page.locator(f'{column} .card:visible').count() == 1
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded()')
    page.click('#boardBtn')
    expect_order([ids[0], ids[1], ids[2]])
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_the_board_reads_only_open_and_recent_done_tickets_and_archives_the_rest(run, web, mapped, browser,
                                                                                 monkeypatch):
    import time
    from datetime import UTC, datetime, timedelta

    from metaform import home
    from metaform.data import Node, Store
    # a done ticket stays on the board for board_done_days, then goes to the Archive
    home.save(home.path_key(Path(mapped).resolve()), 'web', 'board_done_days', [1], folder=Path(mapped).resolve())
    store = Store('proj')
    node = Node('element', 'code.alarm.audible')
    stamp = lambda days: (datetime.now(UTC) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    old, recent = [], []
    with monkeypatch.context() as clock:
        clock.setattr(home, 'now', lambda: stamp(10))  # done before board_done_days
        for number in range(400):
            old.append(store.add_work(node, None, task=f'old {number}').id)
            store.finish_work(old[-1], 'built')
        clock.setattr(home, 'now', lambda: stamp(0.5))
        for number in range(5):
            recent.append(store.add_work(node, None, task=f'recent {number}').id)
            store.finish_work(recent[-1], 'built')
    opened_ids = [store.add_work(node, None, task=f'open {number}').id for number in range(20)]
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    shown = {record.id for record in store.work(limit=0).results if record.id not in old}  # the map's own too
    assert set(opened_ids + recent) <= shown
    began = time.monotonic()
    whole = lambda answer: '/api/work?' in answer.url and 'ids=' not in answer.url and 'node=' not in answer.url
    with page.expect_response(whole) as answered:  # the board's own read of its tickets
        page.click('#boardBtn')
    assert {ticket['id'] for ticket in answered.value.json()['results']} == shown  # nothing old crosses the wire
    page.wait_for_function('count => document.querySelectorAll("#board .card").length === count', arg=len(shown))
    drawn = time.monotonic() - began
    assert drawn < 1.0, f'the board took {drawn:.2f} s to draw'
    assert len(Store('proj').work(open=False, limit=0).results) == 405  # off the board, never deleted
    page.click('#board .line-in-sand')  # everything done up to now leaves the board in one step
    page.wait_for_function('count => document.querySelectorAll("#board .card").length === count',
                           arg=len(store.work(open=True, limit=0).results))
    assert len(Store('proj').work(open=False, limit=0).results) == 405
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_the_archive_route_pages_the_folders_git_log_and_filters_by_trailer(run, web, mapped):
    """The board's Archive reads the project folder's commits newest first, a page at a time, from the tip its first
    page was read at, so a commit made while the person pages shifts nothing; a ticket's commit carries its trailers, a
    hand commit none and is marked so; board and node are checked on the trailers exactly, never on words in prose."""
    def git(*words):
        subprocess.run(['git', '-c', 'user.name=Tester', '-c', 'user.email=tester@example.com', *words], cwd=mapped,
                       check=True, capture_output=True)

    def commit(subject, **trailers):
        block = '\n'.join(f'Metaform-{key.title()}: {value}' for key, value in trailers.items())
        git('commit', '-q', '--allow-empty', '-m', subject, *(['-m', block] if block else []))
    git('init', '-q')
    commit('hand 0')
    for number in range(5):
        commit(f'ticket {number}', ticket=f'{number:032x}', number=f'code.timer.kitchen#{number}',
               node='code.timer.kitchen' if number % 2 else 'code.alarm.audible', board='spring' if number < 3 else '',
               agent='claude')
    git('commit', '-q', '--allow-empty', '-m', 'hand 1',
        '-m', 'It says Metaform-Board: spring and Metaform-Node: code.timer.kitchen in prose.')
    started(run)
    subjects = lambda found: [one['subject'] for one in found['commits']]
    status, first = api(web, '/api/commits?project=proj&limit=3')
    assert status == 200, first
    assert subjects(first) == ['hand 1', 'ticket 4', 'ticket 3']
    assert first['commits'][0]['hand'] and first['commits'][0]['number'] is None
    assert first['commits'][1] | {'sha': '', 'when': ''} == {
        'sha': '', 'when': '', 'author': 'Tester', 'subject': 'ticket 4', 'ticket': f'{4:032x}',
        'number': 'code.timer.kitchen#4', 'node': 'code.alarm.audible', 'board': '', 'agent': 'claude', 'hand': False}
    commit('made while paging')
    _, second = api(web, f'/api/commits?project=proj&limit=3&after={first["next"]}')
    assert subjects(second) == ['ticket 2', 'ticket 1', 'ticket 0']
    _, last = api(web, f'/api/commits?project=proj&limit=3&after={second["next"]}')
    assert subjects(last) == ['hand 0'] and last['next'] is None
    assert subjects(api(web, '/api/commits?project=proj&board=spring')[1]) == ['ticket 2', 'ticket 1', 'ticket 0']
    assert subjects(api(web, '/api/commits?project=proj&board=')[1]) == ['ticket 4', 'ticket 3']  # the first board
    assert subjects(api(web, '/api/commits?project=proj&node=code.timer')[1]) == ['ticket 3', 'ticket 1']
    _, paged = api(web, '/api/commits?project=proj&board=spring&limit=2')
    assert subjects(paged) == ['ticket 2', 'ticket 1']
    assert subjects(api(web, f'/api/commits?project=proj&board=spring&limit=2&after={paged["next"]}')[1]) == [
        'ticket 0']
    assert subjects(api(web, '/api/commits?project=proj&words=IN+PROSE')[1]) == ['hand 1']


@pytest.mark.req('VIEW-037')
def test_a_board_of_500_tickets_opens_in_time_and_a_move_makes_no_other_card_again(run, web, mapped, browser):
    """A board of hundreds of open tickets draws in time, and a click redraws only the cards whose shown fields changed:
    a move renumbers the places below it, and every card made again for that held the page (2026-10-20, 400 of 500
    cards made again per move)."""
    import time

    from metaform.data import Node, Store
    store = Store('proj')
    nodes = [Node('element', address) for address in ('code.timer.kitchen', 'code.alarm.audible', 'code.loop.tick')]
    task = ('Hold the tick to one second at [[dish timer|code.timer.kitchen]]: the loop in src/timer/loop.py drifts '
            '40 ms a minute under load, VIEW-037 and MAP-046 name the stage it shows. Ticket {ref} found the cause; '
            'measure, fix, prove with a test.\nNote {number}: keep the loop small.')
    with store.atomic():
        ids = [store.add_work(nodes[number % 3], ['broken', None, 'trouble'][number % 3], links=[nodes[(number + 1) % 3]],
                              task=task.format(ref=f'{number:08x}', number=number),
                              kind=[None, 'broken', 'flawed', 'enhancement'][number % 4]).id for number in range(500)]
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    began = time.monotonic()
    page.click('#boardBtn')
    page.wait_for_function('() => document.querySelectorAll("#board .card").length >= 500', timeout=30000)
    drawn = time.monotonic() - began
    assert drawn < 5.0, f'the board of 500 tickets took {drawn:.2f} s to draw'
    page.evaluate('for (const box of document.querySelectorAll("#board .card")) box.kept = true')
    moved = f'#board .card[data-id="{ids[1]}"]'
    page.click(f'{moved} .priority button[title="Move down"]')
    page.wait_for_function('id => [...document.querySelectorAll(\'#board .column[data-column="todo"] .card\')]'
                           '.findIndex(box => box.dataset.id === id) === 2', arg=ids[1])
    page.wait_for_timeout(1500)  # past the live stream's read of the tickets the move renumbered
    made = page.evaluate('[...document.querySelectorAll("#board .card")].filter(box => !box.kept).length')
    assert made == 0, f'a move made {made} cards again'
    assert problems == []


dispatch_control_port = None  # supplied by the lazy visual-fixture control server below
ACTIVITY = {}  # what the visual fixtures' runners say a session is doing, by its token; working unless set
RUNNERS = []  # the stand-in runner processes of the visual fixtures' sessions


@pytest.fixture(autouse=True)
def simulated_dispatch_control(monkeypatch):
    """Visual fixtures have an authenticated status endpoint, as real runners do; open it only when used."""
    import socketserver
    import threading

    servers = []

    def start():
        if servers:
            return servers[0].server_address[1]

        class Status(socketserver.StreamRequestHandler):
            def handle(self):
                asked = json.loads(self.rfile.readline())
                self.wfile.write(json.dumps({'session_id': asked['token'], 'state': 'running',
                                             'agent_alive': True, 'how': None,
                                             'activity': ACTIVITY.get(asked['token'], 'working')}).encode() + b'\n')

        server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Status)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server.server_address[1]

    runners = []
    monkeypatch.setitem(globals(), 'dispatch_control_port', start)
    monkeypatch.setitem(globals(), 'ACTIVITY', {})
    monkeypatch.setitem(globals(), 'RUNNERS', runners)
    yield
    for server in servers:
        server.shutdown()
        server.server_close()
    for process in runners:
        process.kill()
        process.wait()


def live_session(work_id, agent='claude', state='running', project='proj', session=None):
    """A dispatch session row for a ticket, as the runner writes it, so the page counts its agent as working: a figure
    on the map and an entry in the agents key are drawn only for a live session, VIEW-035 and VIEW-039. `session`
    names another session on the same ticket, a new conversation."""
    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform.data import Store
    session = session or f's-{work_id}'
    with Store(project, module='dispatch').tables() as tx:
        held = tx.get('agent_sessions', {'session_id': session})
        if held is None:
            # a reader takes a session's pid for its runner only when the command line runs that ticket's runner
            runner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)', 'dispatch', 'run', work_id])
            RUNNERS.append(runner)
            tx.insert('agent_sessions', {'session_id': session, 'work_id': work_id, 'agent': agent, 'state': state,
                                         'pid': runner.pid, 'port': dispatch_control_port(), 'token': session,
                                         'started': '2026-10-03T00:00:00Z',
                                         'seq': len(work_id) + int(work_id[:6], 16) % 1000 + (session != f's-{work_id}')})
        else:
            tx.update('agent_sessions', {'session_id': session}, {'state': state})


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_workbench_and_cli_agree_when_a_runner_dies_with_a_running_row(
        run, home, web, mapped, browser, tmp_path):
    from metaform import relay
    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

    agent = Dispatch(run, home, mapped, tmp_path)
    try:
        agent.start('hold')  # a turn still executing, so the agent is listed as working
        eventually(lambda: agent.logged('grandchild'))
        started(run)
        page, problems, _ = opened(browser, web)
        button = f'#agents .agent[data-id="{agent.id}"]'
        page.wait_for_selector(button, timeout=15000)
        agent.process.kill()
        agent.process.wait()
        relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})
        page.wait_for_selector(button, state='hidden', timeout=15000)
        # the command and the server agreeing: test_the_server_and_the_command_read_the_same_sessions_when_a_runner_dies
        assert problems == []
    finally:
        agent.close()
        for pid in agent.logged('pid'):
            end_group(pid)


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-018')
def test_a_runner_that_dies_before_the_page_stream_opens_leaves_agent_deployed_when_it_opens(
        run, home, web, mapped, browser, tmp_path):
    """The page lists its agents while loading and opens its stream after, work f7cd3522: a dispatch change announced
    between the two reached no page and the dead runner stayed listed. Here the stream is held until after it."""
    from metaform import relay
    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

    agent = Dispatch(run, home, mapped, tmp_path)
    held = []
    try:
        agent.start('hold')
        eventually(lambda: agent.logged('grandchild'))
        started(run)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.route('**/api/events*', lambda route: held.append(route))  # the stream is not open yet
        page.goto(f'http://127.0.0.1:{web}/#p=proj')
        button = f'#agents .agent[data-id="{agent.id}"]'
        page.wait_for_selector(button, timeout=30000)
        agent.process.kill()
        agent.process.wait()
        delivered = relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})
        assert any(one['module'] == 'web' and one['status'] == 'completed' for one in delivered), delivered
        for _ in range(100):  # the page asks for its stream once it has read what it loads, which can come later
            if held:
                break
            page.wait_for_timeout(100)
        held[0].continue_()  # the server took the change while the page had no stream
        page.wait_for_selector(button, state='hidden', timeout=15000)
    finally:
        agent.close()
        for pid in agent.logged('pid'):
            end_group(pid)


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-035')
def test_only_agents_whose_turn_is_executing_are_shown_as_working_and_an_idle_one_stays_reachable(run, web, mapped,
                                                                                                  browser):
    """Five agents showed under Agent deployed and none on the map; all five were older sessions waiting on the person.
    Sessions that are not active are not shown, and the label stays as it is. Agent deployed and the map's figures follow what the runner says a session is doing, activity working;
    an idle session keeps its lifecycle, and its log, chat and Stop are opened from the node's work history."""
    from metaform.data import Node, Store

    store = Store('proj')
    run('enable', 'dispatch')
    alarm = store.element('code.alarm.audible').id
    idle = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Work on the alarm').id
    store.take_work(idle, by='claude')
    live_session(idle)
    ACTIVITY[f's-{idle}'] = 'idle'
    working = store.add_work(Node('element', 'exterior.cook'), 'broken', task='Work for the cook').id
    store.take_work(working, by='codex')
    live_session(working, 'codex')
    started(run)
    page, problems, _ = opened(browser, web)
    served = {one['work_id']: (one['state'], one.get('activity'))
              for one in api(web, '/api/dispatch-sessions?project=proj&thread=false')[1]['sessions']}
    assert served == {idle: ('running', 'idle'), working: ('running', 'working')}
    page.wait_for_selector(f'#agents .agent[data-id="{working}"]', timeout=15000)
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{working}")', timeout=15000)
    assert page.eval_on_selector_all('#agents .agent', 'found => found.map(one => one.dataset.id)') == [working]
    assert [one['work_id'] for one in page.evaluate('window.metaform.figures()')] == [working]
    assert page.eval_on_selector_all('#agents .title', 'found => found.map(one => one.textContent)') == ['Agent deployed']
    assert page.inner_text('#agents .agent small').endswith(' · working')

    ACTIVITY[f's-{working}'] = 'idle'
    page.reload()
    page.wait_for_function('() => window.metaform.loaded() && document.querySelectorAll("#map2d svg g.node").length > 0',
                           timeout=15000)  # the project is picked up again from the address before its menu is read
    assert page.is_hidden('#agents')
    assert page.eval_on_selector_all('#agents .agent', 'found => found.length') == 0
    assert page.evaluate('window.metaform.figures()') == []

    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.history')
    page.wait_for_selector('#float:not([hidden]) .dispatch button.log')
    page.click('#float .dispatch button.log')                               # Open in dock: its thread in the chat dock
    page.wait_for_selector('#helpdesk:not([hidden]) .threadbar:not([hidden])', timeout=10000)
    page.wait_for_function('() => document.querySelector("#helpdesk .status").textContent === "Ready"')  # not ended
    assert page.is_enabled('#helpdesk .threadbar .stop')                     # an idle session can still be stopped
    assert page.is_hidden('#agents')
    assert problems == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-035')
def test_a_session_whose_runner_is_not_verified_is_neither_in_the_agents_key_nor_on_the_map(run, web, mapped, browser):
    """An Unverified list beside Agent deployed was no solution: sessions that are not active are not shown. Only a
    verified running session is shown as at work."""
    from metaform.data import Node, Store

    store = Store('proj')
    run('enable', 'dispatch')
    older = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Work on the alarm').id
    store.take_work(older, by='claude')
    live_session(older)
    with Store('proj', module='dispatch').tables() as tx:  # its runner answers for another session, so this one is unproven
        tx.update('agent_sessions', {'session_id': f's-{older}'}, {'token': f'older-{older}'})
    working = store.add_work(Node('element', 'exterior.cook'), 'broken', task='Work for the cook').id
    store.take_work(working, by='codex')
    live_session(working, 'codex')
    started(run)
    served = {one['work_id']: one['state']
              for one in api(web, '/api/dispatch-sessions?project=proj&thread=false')[1]['sessions']}
    assert served[working] == 'running' and served[older] != 'running', served
    page, problems, _ = opened(browser, web)
    page.wait_for_selector(f'#agents .agent[data-id="{working}"]', timeout=15000)
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{working}")', timeout=15000)
    assert page.eval_on_selector_all('#agents .agent', 'found => found.map(one => one.dataset.id)') == [working]
    assert [one['work_id'] for one in page.evaluate('window.metaform.figures()')] == [working]
    assert page.eval_on_selector_all('#agents .title', 'found => found.map(one => one.textContent)') == ['Agent deployed']
    assert page.eval_on_selector_all('#agents > :not([hidden])', 'found => found.length') == 2   # the title and the one list
    assert page.eval_on_selector_all('#agents .list > *', 'found => found.length') == 1
    shown = page.inner_text('#agents')
    assert 'Claude Code' not in shown and 'alarm' not in shown and 'nverified' not in shown, shown
    assert problems == []


@pytest.mark.req('VIEW-035')
def test_an_agents_figure_walks_from_the_de_to_its_ticket_circles_it_and_walks_back_when_it_closes(run, web, mapped, browser):
    """The agents materialize on the most primary node and navigate the mesh to the node being
    worked on; they settle beside it until the ticket is closed, then navigate back; even if the agent
    finished, they still touch the node and walk back."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    cook = store.element('exterior.cook').id
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, steps=2, by='codex')
    live_session(worked.id, 'codex')
    other = store.add_work(Node('element', 'exterior.cook'), None, task='a third recipe')
    store.take_work(other.id, by='claude')
    live_session(other.id)
    orphan = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='left taken')   # no session behind it
    store.take_work(orphan.id, by='gone')
    quick = store.add_work(Node('element', 'exterior.cook'), None, task='a second recipe')
    store.take_work(quick.id, by='claude')
    store.finish_work(quick.id, 'added')
    live_session(quick.id, state='ended')                        # finished before the page opened
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 2', timeout=15000)
    # An agent that is not active is not on the map, and the key lists only agents at work
    assert {one['work_id'] for one in page.evaluate('window.metaform.figures()')} == {worked.id, other.id}
    assert sorted(page.eval_on_selector_all('#agents .agent', 'found => found.map(one => one.dataset.id)')) == sorted(
        [worked.id, other.id])
    page.evaluate('''() => { window.stages = {}; setInterval(() => { for (const figure of window.metaform.figures())
        (window.stages[figure.work_id] ||= new Set()).add(figure.stage); }, 50); }''')
    glyphs = page.evaluate('window.metaform.figures().map(figure => figure.glyph)')
    assert len(set(glyphs)) == 2                                      # no two at work look alike
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{worked.id}" && one.stage === "circling")',
                           timeout=20000)
    page.wait_for_timeout(1000)                                      # settling beside the label
    figure = next(one for one in page.evaluate('window.metaform.figures()') if one['work_id'] == worked.id)
    node = page.evaluate(f'window.metaform.at3d("{alarm}")')
    away = sum((figure[axis] - node[axis]) ** 2 for axis in 'xyz') ** 0.5
    assert node['r'] < away, (away, node, figure)                     # clear of the node, framing its label
    run('map', 'work', 'op=done', f'id={worked.id}', 'resolution=quieter', 'why=the test closes it', cwd=mapped)
    live_session(worked.id, 'codex', state='ended')
    page.wait_for_function(f'() => (window.stages["{worked.id}"] || new Set()).has("returning")', timeout=10000)
    page.wait_for_function(f'() => !window.metaform.figures().some(one => one.work_id === "{worked.id}")', timeout=20000)
    live_session(other.id, state='ended')                        # stopped with its ticket open: it goes too
    relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})  # its runner announces the session ended
    page.wait_for_function('() => window.metaform.figures().length === 0', timeout=20000)
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=10000)
    assert cook and problems == []


@pytest.mark.req('VIEW-035')
def test_an_agent_whose_session_works_again_after_a_pause_gets_its_figure_back(run, web, mapped, browser):
    """Each reply to the person ends a turn, so a session goes idle and works again. Its figure walked back and was
    gone, and the page never drew it again, so web_look refused the agent. Working again on its way back, it turns
    round; working again once it was gone, it walks on as a new figure, on both maps."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='codex')
    live_session(worked.id, 'codex')
    started(run)
    page, problems, _ = opened(browser, web)
    drawn = f'window.metaform.figures().find(one => one.work_id === "{worked.id}")'
    flat = f'window.metaform.figures2d().find(one => one.work_id === "{worked.id}")'
    page.wait_for_function(f'() => {drawn}?.stage === "circling" && {flat}?.stage === "circling"', timeout=20000)

    def activity(now):
        ACTIVITY[f's-{worked.id}'] = now
        relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})

    activity('idle')                                                 # a turn ended: it walks back
    page.wait_for_function(f'() => {drawn}?.stage === "returning"', timeout=20000)
    page.evaluate(f'''() => {{ window.vanished = false;
        setInterval(() => {{ if (!{drawn}) window.vanished = true; }}, 20); }}''')
    activity('working')                                              # working again before it is gone: it turns round
    page.wait_for_function(f'() => {drawn}?.stage === "circling" && {flat}?.stage === "circling"', timeout=20000)
    assert page.evaluate('window.vanished') is False
    activity('idle')
    page.wait_for_function(f'() => !{drawn} && !{flat}', timeout=20000)
    activity('working')                                              # working again once it was gone: a new figure
    page.wait_for_function(f'() => {drawn}?.stage === "circling" && {flat}?.stage === "circling"', timeout=20000)
    assert problems == []


@pytest.mark.req('VIEW-035')
def test_each_native_subagent_a_running_agent_reports_is_a_figure_of_its_own_that_opens_its_own_thread(
        run, web, mapped, browser):
    """An agent's native subagents, the child sessions its runner records from subagent_spawned and
    subagent_state_update, each walk out as a figure of their own beside their parent, never taking its figure: one
    asking for input waits, a click on one opens its own thread in its parent's chat, and one that ends walks back."""
    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    live_session(worked.id)
    parent = f's-{worked.id}'

    def child(kid, state, seq):
        with Store('proj', module='dispatch').tables() as tx:
            line = {'session_id': parent, 'name': f'subagent:{kid}', 'work_id': worked.id, 'kind': 'subagent',
                    'text': json.dumps({'session_id': kid, 'name': f'Reader {kid}', 'task': 'read', 'state': state,
                                        'started': '2026-10-13T16:00:00Z', 'fork': False}), 'seq': seq}
            if tx.get('session_lines', {'session_id': parent, 'name': f'subagent:{kid}'}) is None:
                tx.insert('session_lines', line)
            else:
                tx.update('session_lines', {'session_id': parent, 'name': f'subagent:{kid}'}, {'text': line['text']})
        relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch', 'work_ids': [worked.id],
                                     'session_ids': [parent], 'kinds': ['session']})

    child('kid-a', 'running', 1)
    child('kid-b', 'running', 2)
    started(run)
    page, problems, _ = opened(browser, web)
    shown = '() => Object.fromEntries(window.metaform.figures().map(one => [one.work_id, [one.stage, one.target]]))'
    page.wait_for_function(f'''() => {{ const f = ({shown})();
        return ["{worked.id}", "child:kid-a", "child:kid-b"].every(id => f[id]?.[0] === "circling"); }}''', timeout=25000)
    figures = page.evaluate(shown)
    assert figures['child:kid-a'][1] == figures[worked.id][1]           # beside its parent, at the node it works on
    child('kid-b', 'input_required', 2)
    page.wait_for_function('() => window.metaform.figures().find(one => one.work_id === "child:kid-b")?.mood '
                           '=== "waiting"', timeout=15000)
    page.evaluate('''async () => (await import('/page/app/figures/ask.js')).openFigure('child:kid-a')''')
    page.wait_for_selector('#helpdesk .subagents button[aria-pressed="true"]:has-text("Reader kid-a")', timeout=15000)
    sent = []

    def child_message(route):
        sent.append(route.request.post_data_json)
        route.fulfill(json={'sent': True, 'child': 'kid-a', 'queued': True})

    page.route('**/api/dispatch-message', child_message)
    page.locator('#helpdesk .say').fill('Check the child result')
    with page.expect_response('**/api/dispatch-message'):
        page.locator('#helpdesk .say').press('Enter')
    page.wait_for_function('() => document.querySelector("#helpdesk .say").value === ""')
    assert sent and sent[-1]['fork'] == 'kid-a', sent
    assert sent[-1]['session'] == parent and sent[-1]['work_id'] == worked.id, sent
    assert sent[-1]['text'] == 'Check the child result', sent
    child('kid-a', 'completed', 1)
    page.wait_for_function('() => !window.metaform.figures().some(one => one.work_id === "child:kid-a")', timeout=20000)
    assert worked.id in page.evaluate(shown) and 'child:kid-b' in page.evaluate(shown)
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_an_intake_agent_between_turns_on_a_mapped_project_reads_idle_not_starting(run, web, mapped, browser):
    """code.interface.graphical#13: an intake session kept running after its turns, idle, with nothing being
    recorded, read Starting on its bar for as long as it ran. It is an intake session still, so the bar stays and
    names it; idle it says so, and working again it reads the project."""
    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform import relay
    from metaform.data import Store
    run('enable', 'dispatch')
    intake = 'intake-' + 'ab' * 16
    runner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)', 'dispatch', 'run', intake])
    RUNNERS.append(runner)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': f's-{intake}', 'work_id': intake, 'agent': 'claude', 'state': 'running',
                               'pid': runner.pid, 'port': dispatch_control_port(), 'token': f's-{intake}',
                               'started': '2026-10-03T00:00:00Z', 'seq': 1})
    ACTIVITY[f's-{intake}'] = 'idle'
    started(run)
    page, problems, _ = opened(browser, web)
    bar = '#intakeBar:not([hidden])'
    page.wait_for_selector(f'{bar}:has-text("Intake")', timeout=20000)
    page.wait_for_selector(f'{bar} .doing:has-text("Idle")', timeout=20000)
    assert 'Starting' not in page.inner_text('#intakeBar')
    ACTIVITY[f's-{intake}'] = 'working'
    relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})
    page.wait_for_selector(f'{bar} .doing:has-text("Reading the project")', timeout=20000)
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_an_agent_reads_the_pointers_ray_and_what_it_takes_and_captures_the_view_and_the_shared_screen(
        run, web, mapped, browser, tmp_path):
    """What the person points at and sees, asked by an agent: the ray the person's 3D camera casts through the mouse
    pointer and what a click there would take, nothing once the pointer leaves the map or the page goes to another
    project; a picture of their own 3D view; and frames of the screen they share, refused with how to share before the
    share and once it ends."""
    from metaform.data import Store
    folder = tmp_path / 'other'
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    build(Store('other'))
    alarm = Store('proj').element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    map_key(page, 'p')  # the layout holds still under the pointer
    on_screen = '''async id => { const {G} = await import('/page/app/map3d/graph3d.js');
        const THREE = await import('three'); const node = G.graphData().nodes.find(one => one.id === id);
        const v = new THREE.Vector3(node.x, node.y, node.z).project(G.camera());
        const box = document.querySelector('#stage').getBoundingClientRect();
        return [box.left + (v.x + 1) / 2 * box.width, box.top + (1 - v.y) / 2 * box.height]; }'''
    box = page.evaluate('() => { const b = document.querySelector("#stage").getBoundingClientRect(); '
                        'return [b.left, b.top, b.width, b.height]; }')

    def viewing(cwd=mapped):
        return json.loads(run('web', 'viewing', '--json', cwd=cwd).stdout)

    page.mouse.move(*page.evaluate(on_screen, alarm))
    pointed = viewing()['pointer']
    assert pointed['pane'] == '3d' and pointed['hit']['address'] == 'code.alarm.audible', pointed
    assert len(pointed['ray']['origin']) == 3 and abs(sum(one * one for one in pointed['ray']['direction']) - 1) < 0.01
    view = json.loads(run('web', 'capture', '--json', cwd=mapped).stdout)
    assert view['source'] == 'view' and view['pointer']['hit']['address'] == 'code.alarm.audible'
    assert Path(view['file']).read_bytes().startswith(b'\x89PNG') and view['width'] == round(min(1280, box[2]))
    page.mouse.move(box[0] + 4, box[1] + box[3] - 4)                   # a corner of the map, nothing there
    assert viewing()['pointer']['hit'] is None
    page.mouse.move(box[0] + box[2] / 2, 4)                            # off the map, onto the header
    assert viewing()['pointer'] is None
    page.mouse.move(*page.evaluate(on_screen, alarm))
    assert viewing()['pointer']['hit']['address'] == 'code.alarm.audible'
    page.select_option('#proj', 'other')                              # the pointer has not moved, the project has
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    assert viewing(folder)['pointer'] is None
    refused = run('web', 'capture', 'source=screen', cwd=folder, ok=False)
    assert 'Nothing is shared with agents' in refused.stderr + refused.stdout
    page.evaluate('''() => { navigator.mediaDevices.getDisplayMedia = async () => {
        const canvas = Object.assign(document.createElement('canvas'), {width: 640, height: 360});
        const pen = canvas.getContext('2d'); pen.fillStyle = '#c00';
        setInterval(() => pen.fillRect(0, 0, 640, 360), 50); return canvas.captureStream(10); }; }''')
    page.evaluate('() => document.querySelector("#shareBtn").click()')  # the person's click in the Agents menu
    for _ in range(100):                                             # the share is live once its first frame shows
        if page.evaluate('''async () => (await import('/page/app/figures/eyes.js')).sharing()'''):
            break
        page.wait_for_timeout(100)
    frame = json.loads(run('web', 'capture', 'source=screen', '--json', cwd=folder).stdout)
    assert frame['source'] == 'screen' and (frame['width'], frame['height']) == (640, 360)
    assert Path(frame['file']).read_bytes().startswith(b'\xff\xd8\xff')
    page.evaluate('''async () => (await import('/page/app/figures/eyes.js')).SHARE.stream.getVideoTracks()[0]
        .dispatchEvent(new Event('ended'))''')                         # the browser's own Stop sharing
    refused = run('web', 'capture', 'source=screen', cwd=folder, ok=False)
    assert 'Nothing is shared with agents' in refused.stderr + refused.stdout
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_what_the_person_last_clicked_is_named_to_their_system_agent_with_their_next_message(
        run, home, web, mapped, browser, tmp_path):
    """code.interface.graphical#124: the person points at something and asks their system agent about it. The page
    keeps the last thing they clicked, a node in the 3D map, a join in the 2D map, a banner's button, and web_viewing
    gives it as `clicked`, with the state a part shows and the ticket behind it. Their next message to the system
    agent within two minutes starts with one line naming it, and their bubble shows it as a chip; a second message, or
    one sent three minutes after the click, carries none, and a message to another agent carries none and leaves the
    click untold. The chat's own box and buttons are never recorded, nor a
    click on the mascot, and a question asked through the mascot carries the line as the chat does, the click as it
    was when the person asked even while their system agent starts; two asked while it is called go together, once,
    and one waiting on the chat's call when that call fails is told so, its click going with the next message; another
    agent's failed start leaves a question waiting on the system agent's call as it is."""
    from metaform.data import Store
    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

    agent = Dispatch(run, home, mapped, tmp_path)
    agent.id = agent.store.add_work(agent.node, None, task='Conversation with the system agent', held=True).id
    trouble = json.loads(run('map', 'work', 'op=add', 'receiver=code.timer.kitchen', 'provider=code.alarm.audible',
                             'condition=trouble', 'task=It rings late.', 'title=The alarm rings late', '--json',
                             cwd=mapped).stdout)
    item, join = trouble['map']['item'], trouble['node_id']             # the ticket's join, kitchen timer > alarm
    alarm = Store('proj').element('code.alarm.audible').id
    run('set', '--web-mascot=owl')                                     # the person's mascot, to ask through
    agent.start('plain', 'system=true')
    try:
        session = agent.session().extra['session_id']
        eventually(lambda: agent.received('session/prompt'))
        started(run)
        page, problems, _ = opened(browser, web)
        page.route('**/api/system-chat', lambda route: route.fulfill(
            status=200, content_type='application/json', body=json.dumps(
                {'work_id': agent.id, 'session_id': session, 'agent': 'claude', 'state': 'running'})))
        page.wait_for_function('() => window.metaform.loaded()', timeout=15000)

        def clicked():
            return json.loads(run('web', 'viewing', '--json', cwd=mapped).stdout)['clicked']

        page.click('#dockTab')                                         # the chat's own controls are not recorded
        page.click('#helpdesk .call')
        page.wait_for_selector('#helpdesk .threadbar .stop:not([hidden])')
        assert clicked() is None
        map_key(page, 'p')                                             # the layout holds still under the pointer
        node_at = '''async id => { const {G} = await import('/page/app/map3d/graph3d.js');
            const THREE = await import('three'); const node = G.graphData().nodes.find(one => one.id === id);
            const v = new THREE.Vector3(node.x, node.y, node.z).project(G.camera());
            const box = document.querySelector('#stage').getBoundingClientRect();
            return [box.left + (v.x + 1) / 2 * box.width, box.top + (1 - v.y) / 2 * box.height]; }'''
        page.mouse.click(*page.evaluate(node_at, alarm))               # a node in the 3D map
        node = clicked()
        assert (node['kind'], node['address']) == ('element', 'code.alarm.audible'), node
        to_large_area(page)
        on_edge = '''async id => { const {M} = await import('/page/app/map2d/build.js');
            const {nodeAt2d, edgeAt2d} = await import('/page/app/map2d/hover.js');
            const edge = M.edges.find(one => one.join?.id === id), path = edge.path, length = path.getTotalLength();
            for (let share = 0.5, step = 0; step < 40; step++, share = 0.5 + (step % 2 ? 1 : -1) * Math.ceil(step / 2) / 50) {
                const on = path.getPointAtLength(length * share);
                const at = new DOMPoint(on.x, on.y).matrixTransform(path.getScreenCTM());
                if (!nodeAt2d(at.x, at.y) && edgeAt2d(at.x, at.y) === edge) return [at.x, at.y];
            }
            return null; }'''

        page.evaluate("async () => { window.__build = await import('/page/app/map2d/build.js'); }")

        def click_join():
            map_key(page, 'Escape')                                    # a selection let go, the map drawn whole
            page.wait_for_function('id => window.__build.M.edges'
                                   '.some(one => one.join?.id === id && one.path?.isConnected)', arg=join)
            still2d(page)
            point = page.evaluate(on_edge, join)
            assert point
            page.mouse.click(*point)
        click_join()                                                   # a join in the 2D map, its ticket in trouble
        joined = clicked()
        assert (joined['kind'], joined['address']) == ('join', 'code.timer.kitchen > code.alarm.audible'), joined
        assert joined['state'] == 'flashing red' and joined['record'] == f'#{item.split("#")[-1]} trouble', joined
        page.evaluate('''async () => (await import('/page/app/core/banner.js')).banner('test-retry',
            {tone: 'warn', title: 'The map was not read', actions: [{label: 'Read again', run: () => {}}]})''')
        page.click('.banner[data-key="test-retry"] .acts button')     # a banner's button
        told = clicked()
        assert (told['kind'], told['label'], told['control'], told['state']) == (
            'banner', 'The map was not read', 'Read again', 'a warning'), told
        # a button that answers a question is named with the question, graphical#146: "No" alone says nothing
        page.route('**/api/answer', lambda route: route.fulfill(status=200, content_type='application/json', body='{}'))
        page.evaluate('''async alarm => { const {asked} = await import('/page/app/selection/select.js');
            document.querySelector('#qa .body').replaceChildren(asked({id: 'q-146', node_kind: 'element',
                node_id: alarm, text: 'Is the container still needed?', suggestions: ['No', 'Yes']}));
            document.querySelector('#qa').hidden = false; }''', alarm)
        page.click('#qa .suggestion:text-is("No")')
        answered = clicked()
        assert answered['said'] == 'question "Is the container still needed?", its button "No" in Question', answered
        page.evaluate("document.querySelector('#qa').hidden = true")
        page.evaluate('''async () => { (await import('/page/app/core/controls.js')).confirmAct(
            {title: 'Remove project Demo?', verb: 'Remove'}); }''')
        page.click('#confirm button.confirm')                          # a confirmation's act button closes it
        removed = clicked()
        assert removed['said'].startswith('question "Remove project Demo?", its button "Remove"'), removed
        click_join()                                                   # the join again, then the chat
        page.click('#helpdesk .say')
        page.keyboard.type('Why is this flashing red?')
        assert clicked()['kind'] == 'join'                             # the box and what is typed are never recorded
        asked = len(agent.received('session/prompt'))

        def prompts():
            return [' '.join(part.get('text', '') for part in one['params']['prompt'])
                    for one in agent.received('session/prompt')[asked:]]
        page.keyboard.press('Enter')
        first = eventually(lambda: next((one for one in prompts() if 'Why is this flashing red?' in one), None))
        line = (f'The person clicked, {{}} s before: join code.timer.kitchen > code.alarm.audible, flashing red '
                f'(#{item.split("#")[-1]} trouble).')
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+') + '\n\nWhy is this flashing red\\?$', first), first
        chip = page.wait_for_selector('#helpdesk .msg.mine .bubble:has-text("Why is this flashing red?") .clickedchip')
        assert chip.inner_text().startswith('Clicked: join code.timer.kitchen > code.alarm.audible, flashing red')
        assert 'The person clicked' not in page.inner_text('#helpdesk .msg.mine .bubble:has-text("flashing red?")')
        page.fill('#helpdesk .say', 'And what is this one?')        # no click since the last message
        page.press('#helpdesk .say', 'Enter')
        second = eventually(lambda: next((one for one in prompts() if 'what is this one' in one), None))
        assert second == 'And what is this one?', second
        click_join()
        page.evaluate("async () => { (await import('/page/app/figures/eyes.js')).CLICKED.at -= 180000; }")  # 3 min on
        page.fill('#helpdesk .say', 'Still there?')
        page.press('#helpdesk .say', 'Enter')
        late = eventually(lambda: next((one for one in prompts() if 'Still there?' in one), None))
        assert late == 'Still there?', late
        assert page.locator('#helpdesk .clickedchip').count() == 1
        click_join()                                                   # the join, then the mascot to ask about it
        map_key(page, 's')                                             # the 3D map back in the large area
        clear = '''() => { const m = window.metaform.mascot(); if (m.sx === undefined) return null;
            const e = document.elementFromPoint(m.sx, m.sy); return e?.closest('#stage') ? [m.sx, m.sy] : null; }'''
        page.wait_for_function(clear, timeout=15000)                   # the mascot where no chat covers it
        page.mouse.click(*page.evaluate(clear))
        page.wait_for_selector('input.reply')
        assert clicked()['kind'] == 'join'                             # the mascot's ask field never takes the click
        page.fill('input.reply', 'Why is this red?')
        page.press('input.reply', 'Enter')
        asked_mascot = eventually(lambda: next((one for one in prompts() if 'Why is this red?' in one), None))
        pattern = re.escape(line).replace(r'\{\}', r'\d+') + '\n\nWhy is this red\\?$'
        assert re.match(pattern, asked_mascot), asked_mascot
        page.wait_for_selector('#helpdesk .msg.mine .bubble:has-text("Why is this red?") .clickedchip')
        # asked through the mascot while the system agent is not running: the line is the click as the person asked,
        # not a click made while the agent starts
        map_key(page, 's')                                             # the 2D map in the large area, for the join
        click_join()
        assert clicked()['kind'] == 'join'
        map_key(page, 's')

        def not_running(route):
            response = route.fetch()
            body = response.json()
            for one in body.get('sessions', []):
                if one.get('work_id') == agent.id:
                    one['state'] = 'starting'
            route.fulfill(response=response, json=body)
        page.route('**/api/dispatch-sessions*', not_running)
        page.evaluate("async () => (await import('/page/app/agents/dispatch.js')).renderAgents()")
        page.wait_for_function(clear, timeout=15000)
        page.mouse.click(*page.evaluate(clear))
        page.wait_for_selector('input.reply')
        assert clicked()['kind'] == 'join', clicked()
        page.fill('input.reply', 'Why is that red?')
        page.press('input.reply', 'Enter')
        # a predicate must be synchronous to be waited on: an async one is a promise, truthy at once
        page.evaluate("async () => { window.__ask = await import('/page/app/figures/ask.js'); }")
        page.wait_for_function("() => window.__ask.ASKING.pending")
        page.mouse.click(*page.evaluate(node_at, alarm))               # another node, before the session is live
        assert clicked()['address'] == 'code.alarm.audible'
        assert not any('Why is that red?' in one for one in prompts())
        page.unroute('**/api/dispatch-sessions*', not_running)
        page.evaluate("async () => (await import('/page/app/agents/dispatch.js')).renderAgents()")  # now it is live
        asked_waiting = eventually(lambda: next((one for one in prompts() if 'Why is that red?' in one), None))
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+') + '\n\nWhy is that red\\?$', asked_waiting), \
            asked_waiting
        # two questions to the mascot while the person's system agent is still being called: the agent is called
        # once, and both go in one prompt, in order, under the click line once
        map_key(page, 's')                                             # the 2D map in the large area, for the join
        click_join()
        map_key(page, 's')
        page.evaluate("async () => { (await import('/page/app/dock/embody.js')).DOCK.mine = null; }")  # none yet
        calls = []

        def hold_call(route):                                          # held until both are asked
            calls.append(route)
        page.route('**/api/system-chat', hold_call)
        for question in ('Is the alarm late?', 'Or is the timer slow?'):
            page.wait_for_function(clear, timeout=15000)
            page.mouse.click(*page.evaluate(clear))
            page.wait_for_selector('input.reply')
            page.fill('input.reply', question)
            page.press('input.reply', 'Enter')
            page.wait_for_function('q => window.__ask.ASKING.pending?.endsWith(q)', arg=question)
        page.evaluate('''() => { window.__said = [];  // the mascot's words, told by the bubbles' status, bubble3d.js
            new MutationObserver(() => window.__said.push(document.querySelector('#bubbles .heard')
              ?.textContent)).observe(document.body, {childList: true, subtree: true, characterData: true}); }''')
        page.unroute('**/api/system-chat', hold_call)
        for call in calls:  # answered here: a handler in Python runs only while the test waits on the page
            call.fulfill(json={'work_id': agent.id, 'session_id': session, 'agent': 'claude', 'state': 'running'})
        both = eventually(lambda: next((one for one in prompts() if 'timer slow' in one), None))
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+')
                        + '\n\nIs the alarm late\\?\n\nOr is the timer slow\\?$', both), both
        assert len(calls) == 1 and sum('alarm late' in one for one in prompts()) == 1, (calls, prompts())
        assert 'I could not reach your system agent.' not in page.evaluate('window.__said')
        # a question to the mascot that waits on the chat's own call, which then fails: the person is told, and the
        # click it named goes with their next message
        map_key(page, 's')                                             # the 2D map in the large area, for the join
        click_join()
        map_key(page, 's')
        page.route('**/api/dispatch-sessions*', not_running)
        page.evaluate("async () => { window.__dispatch = await import('/page/app/agents/dispatch.js');"
                      " window.__dock = (await import('/page/app/dock/embody.js')).DOCK;"
                      " await window.__dispatch.renderAgents(); }")
        page.wait_for_function('id => !window.__dispatch.D.sessions.some(one => one.work_id === id'
                               ' && one.state === "running")', arg=agent.id)
        failing = []

        def hold_failing(route):                                       # held until the mascot's ask waits on it
            failing.append(route)
        page.route('**/api/system-chat', hold_failing)
        # the chat's call, as its Call button makes it, held; the button is hidden while the agent's thread is open
        page.evaluate("async () => { (await import('/page/app/dock/commands.js')).callSystem(); }")
        page.wait_for_function('() => window.__dock.calling')
        eventually(lambda: page.evaluate('() => 0') or failing)        # the route runs inside a Playwright call
        page.wait_for_function(clear, timeout=15000)
        page.mouse.click(*page.evaluate(clear))
        page.wait_for_selector('input.reply')
        page.fill('input.reply', 'Is it the battery?')
        page.press('input.reply', 'Enter')
        page.wait_for_function("() => window.__ask.ASKING.pending === 'Is it the battery?'")
        page.unroute('**/api/system-chat', hold_failing)
        failing[0].fulfill(status=409, json={'error': 'The agent did not start.'})
        page.wait_for_function("() => window.__said.some(one => one?.includes('I could not reach your system agent.'))")
        assert page.evaluate('() => window.__ask.ASKING.pending') is None
        assert clicked()['told'] is False, clicked()
        assert not any('battery' in one for one in prompts())
        page.unroute('**/api/dispatch-sessions*', not_running)
        page.evaluate('() => window.__dispatch.renderAgents()')       # live again
        page.wait_for_function('id => window.__dispatch.D.sessions.some(one => one.work_id === id'
                               ' && one.state === "running")', arg=agent.id)
        page.fill('#helpdesk .say', 'Did that reach you?')
        page.press('#helpdesk .say', 'Enter')
        reached = eventually(lambda: next((one for one in prompts() if 'Did that reach you?' in one), None))
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+') + '\n\nDid that reach you\\?$', reached), reached
        # another agent's start fails while the question waits on the system agent's call: the question still waits,
        # nothing says the system agent was not reached, and it goes once the call answers
        map_key(page, 's')                                             # the 2D map in the large area, for the join
        click_join()
        map_key(page, 's')
        page.evaluate("() => { window.__dock.mine = null; }")         # none yet
        reaching_system = []

        def hold_system(route):                                        # held while the other start fails
            reaching_system.append(route)
        page.route('**/api/system-chat', hold_system)
        page.wait_for_function(clear, timeout=15000)
        page.mouse.click(*page.evaluate(clear))
        page.wait_for_selector('input.reply')
        page.fill('input.reply', 'Is the bell broken?')
        page.press('input.reply', 'Enter')
        page.wait_for_function("() => window.__ask.ASKING.pending === 'Is the bell broken?' && window.__dock.calling")
        # the bubble's status keeps its last words, the failed step's, until the mascot's 'Asking…' replaces them
        page.wait_for_function("() => document.querySelector('#bubbles .heard')?.textContent.includes('Asking')")
        page.evaluate('() => { window.__said = []; }')
        page.route('**/api/talk', lambda route: route.fulfill(status=409, json={'error': 'The ticket agent is busy.'}),
                   times=1)
        page.evaluate("async () => { await (await import('/page/app/dock/commands.js'))"
                      ".talkAbout({node: 'code.alarm.audible'}, 'the alarm'); }")
        page.wait_for_function("() => window.__dock.notes.some(one => one.text.includes('The ticket agent is busy.'))")
        # after any answer startFailed's import of ask.js would give
        assert page.evaluate("async () => { await import('/page/app/figures/ask.js');"
                             " await new Promise(done => setTimeout(done, 100));"
                             " return window.__ask.ASKING.pending; }") == 'Is the bell broken?'
        assert not any('could not reach' in (one or '') for one in page.evaluate('window.__said'))
        page.unroute('**/api/system-chat', hold_system)
        for call in reaching_system:  # answered here: a handler in Python runs only while the test waits on the page
            call.fulfill(json={'work_id': agent.id, 'session_id': session, 'agent': 'claude', 'state': 'running'})
        bell = eventually(lambda: next((one for one in prompts() if 'Is the bell broken?' in one), None))
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+') + '\n\nIs the bell broken\\?$', bell), bell
        assert len(reaching_system) == 1, reaching_system
        # a message written while the system agent starts, whose send then fails: the person's words come back in the
        # box without the line, and the resend carries the line once, as the click was never told
        map_key(page, 's')                                             # the 2D map in the large area, for the join
        click_join()
        page.route('**/api/dispatch-sessions*', not_running)
        page.evaluate("async () => (await import('/page/app/dock/helpdesk.js')).drawHelpdesk()")
        eventually(lambda: page.evaluate("async () => !(await import('/page/app/dock/embody.js')).DOCK.live"))
        refused = []

        def refuse_once(route):
            refused.append(route.request.post_data_json['text'])
            route.fulfill(status=409, json={'error': 'The session is busy.'})
        page.route('**/api/dispatch-message', refuse_once, times=1)
        page.fill('#helpdesk .say', 'Is it still red?')
        page.press('#helpdesk .say', 'Enter')
        dock = "async () => (await import('/page/app/dock/embody.js')).DOCK"
        assert eventually(lambda: page.evaluate(f"{dock}.queue.some(one => one.state === 'waiting')"))  # queued
        page.unroute('**/api/dispatch-sessions*', not_running)                # live now: the queued send fails
        page.evaluate("async () => (await import('/page/app/dock/helpdesk.js')).drawHelpdesk()")
        page.wait_for_function("() => document.querySelector('#helpdesk .say').value === 'Is it still red?'")
        assert refused and refused[0].startswith('The person clicked'), refused  # the queued send carried the line
        assert page.input_value('#helpdesk .say') == 'Is it still red?'
        page.press('#helpdesk .say', 'Enter')                          # the resend, the session live
        resent = eventually(lambda: next((one for one in prompts() if 'Is it still red?' in one), None))
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+') + '\n\nIs it still red\\?$', resent), resent
        assert resent.count('The person clicked') == 1, resent
        page.fill('#helpdesk .say', 'And now?')
        page.press('#helpdesk .say', 'Enter')
        after = eventually(lambda: next((one for one in prompts() if 'And now?' in one), None))
        assert after == 'And now?', after
        # a send that carried no line fails after the person clicked something new: the new click stays untold
        held = []
        page.route('**/api/dispatch-message', lambda route: held.append(route), times=1)
        page.fill('#helpdesk .say', 'Still there?')
        page.press('#helpdesk .say', 'Enter')
        eventually(lambda: page.evaluate('() => 0') or held)          # the route runs inside a Playwright call
        click_join()                                                  # a new click while the send goes
        held[0].fulfill(status=409, json={'error': 'The session is busy.'})
        page.wait_for_function("() => document.querySelector('#helpdesk .say').value === 'Still there?'")
        assert clicked()['told'] is False, clicked()
        # a message to another agent tells the system agent nothing: it carries no line and leaves the click untold,
        # and the next message to the system agent carries it once
        other = agent.store.add_work(agent.node, None, task='Another agent at work', held=True).id
        sent_other = []

        def to_other(route):
            sent_other.append(route.request.post_data_json)
            route.fulfill(json={'ok': True})
        page.route('**/api/dispatch-message', to_other, times=1)
        click_join()
        page.evaluate('''async other => { const {DOCK} = await import('/page/app/dock/embody.js');
            window.__system = [DOCK.target, DOCK.session, DOCK.chat];
            // the other agent's thread on view and running, set with the send so no redraw comes between
            Object.assign(DOCK, {target: other, session: null, chat: null, live: true});
            document.querySelector('#helpdesk .say').value = 'Are you on the alarm?';
            document.querySelector('#helpdesk .compose').requestSubmit(); }''', other)
        eventually(lambda: page.evaluate('() => 0') or sent_other)     # the route runs inside a Playwright call
        assert sent_other[0]['work_id'] == other and 'The person clicked' not in sent_other[0]['text'], sent_other
        assert clicked()['told'] is False, clicked()
        page.evaluate('''async () => { const {DOCK} = await import('/page/app/dock/embody.js');
            [DOCK.target, DOCK.session, DOCK.chat] = window.__system;
            await (await import('/page/app/dock/helpdesk.js')).drawHelpdesk(); }''')
        page.fill('#helpdesk .say', 'Back to the join.')
        page.press('#helpdesk .say', 'Enter')
        back = eventually(lambda: next((one for one in prompts() if 'Back to the join.' in one), None))
        assert re.match(re.escape(line).replace(r'\{\}', r'\d+') + '\n\nBack to the join\\.$', back), back
        assert back.count('The person clicked') == 1, back
        assert problems == ['Failed to load resource: the server responded with a status of 409 (Conflict)'] * 4, \
            problems
    finally:
        agent.close()
        for pid in agent.logged('pid'):
            end_group(pid)


@pytest.mark.req('VIEW-005')
def test_an_agent_brings_its_own_figure_to_what_the_pointer_takes_for_as_long_as_it_chooses(run, web, mapped, browser):
    """web_come moves the calling agent's own figure, here a chat's, as it chooses: beside what the pointer takes,
    under the pointer, or before the view, for its seconds, and seconds=0 ends it; a place that is not there now is
    refused, never guessed. A line asked aloud is said in its own bubble and says whether it was spoken, by the
    person's voice settings."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    cook = store.element('exterior.cook').id
    import metaform.modules.dispatch  # noqa: F401  declares its tables
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'exterior.cook'), None, task='a third recipe')
    store.take_work(worked.id, by='codex')
    store.finish_work(worked.id, 'added')
    # a chat about the done ticket, as dispatch talk starts one, begun after it was done: a conversation's own figure
    runner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)', 'dispatch', 'run', worked.id,
                               'system=true', f'talk=ticket:{worked.id}'])
    RUNNERS.append(runner)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': f's-{worked.id}', 'work_id': worked.id, 'agent': 'claude',
                               'state': 'running', 'pid': runner.pid, 'port': dispatch_control_port(),
                               'token': f's-{worked.id}', 'seq': 1,
                               'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 2))})
    started(run)
    page, problems, _ = opened(browser, web)
    drawn = f'window.metaform.figures().find(one => one.work_id === "{worked.id}")'
    page.wait_for_function(f'() => {drawn}?.stage === "circling"', timeout=20000)
    map_key(page, 'p')  # the layout holds still under the pointer
    on_screen = '''async id => { const {G} = await import('/page/app/map3d/graph3d.js');
        const THREE = await import('three'); const node = G.graphData().nodes.find(one => one.id === id);
        const v = new THREE.Vector3(node.x, node.y, node.z).project(G.camera());
        const box = document.querySelector('#stage').getBoundingClientRect();
        return [box.left + (v.x + 1) / 2 * box.width, box.top + (1 - v.y) / 2 * box.height]; }'''
    box = page.evaluate('() => { const b = document.querySelector("#stage").getBoundingClientRect(); '
                        'return [b.left, b.top, b.width, b.height]; }')
    own = {'METAFORM_WORK': worked.id}
    near = f'''() => {{ const f = {drawn}, n = window.metaform.at3d("{alarm}");
        return f && Math.hypot(f.x - n.x, f.y - n.y, f.z - n.z) < n.r + 3 * f.scale; }}'''
    page.mouse.move(box[0] + box[2] / 2, 4)                            # off the map
    refused = run('web', 'come', 'to=pointer', cwd=mapped, env=own, ok=False)
    assert 'pointer is not on the 3D map' in refused.stderr
    page.mouse.move(box[0] + 4, box[1] + box[3] - 4)                   # on the map, over nothing
    refused = run('web', 'come', 'to=hit', cwd=mapped, env=own, ok=False)
    assert 'takes nothing' in refused.stderr
    page.mouse.move(*page.evaluate(on_screen, alarm))
    came = json.loads(run('web', 'come', 'to=hit', 'seconds=60', 'follow=false', '--json', cwd=mapped, env=own).stdout)
    assert (came['who'], came['to'], came['follow'], came['seconds']) == ('your figure', 'hit', False, 60)
    page.wait_for_function(near, timeout=15000)                        # its own figure, beside the alarm it points at
    ended = json.loads(run('web', 'come', 'seconds=0', '--json', cwd=mapped, env=own).stdout)
    assert ended['ended'] is True
    page.wait_for_function(f'() => !({near})()', timeout=15000)        # back to its own ticket's node
    assert page.evaluate(f'() => {drawn}.target') == cook
    said = json.loads(run('web', 'say', 'over here', 'speak=true', '--json', cwd=mapped, env=own).stdout)
    speaks = page.evaluate('async () => (await import("/page/voice.js")).mayAnnounce()')
    assert said['spoken'] is speaks and (speaks or 'voice settings' in said['why'])  # as the voice settings have it
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_the_system_agent_takes_its_own_figure_whose_acts_arrive_and_say_where_it_ended_up_and_sees_what_it_can(
        run, web, mapped, browser):
    """web_embody from the system agent gives it its own figure, never the person's mascot. Its acts move that figure
    and answer once it is done: a move to an address arrives beside it, a step forward goes the distance asked, a turn
    faces what it names, each saying where it is, which way it faces, whether it is at rest and what stopped it. A look
    at an address is taken once the figure faces it, and see lists only what it perceives, nearest first, capped."""
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    system = store.add_work(Node('element', 'code.alarm.audible'), None, task='Conversation with the system agent',
                            held=True)
    live_session(system.id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    own = {'METAFORM_WORK': system.id, 'METAFORM_ROLE': 'system'}
    taken = json.loads(run('web', 'embody', 'owl', '--json', cwd=mapped, env=own).stdout)
    assert (taken['figure'], taken['mascot']) == (True, False), taken
    drawn = f'window.metaform.figures().find(one => one.work_id === "{system.id}")'
    page.wait_for_function(f'() => ["going", "circling"].includes({drawn}?.stage)', timeout=20000)
    assert page.evaluate('window.metaform.mascot().shown') is False   # the person's mascot is not its body
    # a body sent beside a node follows it while the layout moves it, and is at rest only once the node is: the move
    # waits for the layout to have stopped moving the kitchen timer, which a loaded machine makes slow
    kitchen = store.element('code.timer.kitchen').id
    still(page, f'() => {{ const node = window.metaform.at3d("{kitchen}");'
                ' return node && [node.x, node.y, node.z].map(Math.round).join(); }')
    went = json.loads(run('web', 'move', 'address=code.timer.kitchen', '--json', cwd=mapped, env=own).stdout)
    assert (went['who'], went['stopped_by'], went['at_rest']) == ('your figure', 'arrived', True), went
    assert went['target']['address'] == 'code.timer.kitchen' and went['off'] < 1, went
    assert abs(went['moved'] - went['asked']) < went['asked'] * 0.1, went
    stepped = json.loads(run('web', 'move', 'forward=12', '--json', cwd=mapped, env=own).stdout)
    assert stepped['stopped_by'] == 'arrived' and stepped['asked'] == 12 and abs(stepped['moved'] - 12) < 1, stepped
    turned = json.loads(run('web', 'turn', 'address=exterior.cook', '--json', cwd=mapped, env=own).stdout)
    assert turned['stopped_by'] in ('turned', 'arrived') and turned['at_rest'], turned
    looked = json.loads(run('web', 'look', 'address=code.alarm.audible', '--json', cwd=mapped, env=own).stdout)
    assert looked['turn'] in ('turned', 'arrived') and looked['from']['as'] == 'your figure', looked
    alarm = [one for one in looked['in_view'] if one['address'] == 'code.alarm.audible']
    assert not alarm or 'ahead' in alarm[0]['bearing'], looked     # faced, unless something nearer hides it
    seen = json.loads(run('web', 'see', '--json', cwd=mapped, env=own).stdout)
    distances = [one['distance'] for one in seen['in_view']]
    assert distances == sorted(distances) and len(distances) <= 12 and 'nearest' not in seen, seen
    assert max(abs(one - two) for one, two in zip(seen['from']['gaze'], looked['from']['gaze'])) < 0.1, seen  # held
    assert all('visible' not in one and one['distance'] <= seen['range'] for one in seen['in_view']), seen
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_the_body_the_person_gives_the_system_agent_is_their_mascot_in_every_conversation_and_on_every_page(
        run, web, mapped, browser):
    """The body the person gives the system agent in the chat is their mascot, web_mascot, one record the server
    holds: a new conversation is drawn in it without an offer, another browser draws it too, and the system agent's
    prompt names it. Before, the body was kept in one browser for one conversation, and the prompt named web_mascot."""
    import metaform.modules.web  # noqa: F401  declares web_mascot
    from metaform import settings
    from metaform.data import Node, Store
    from metaform.modules.dispatch import mascot_line
    from metaform.modules.dispatch.tests.test_dispatch import eventually
    store = Store('proj')
    run('enable', 'dispatch')
    system = store.add_work(Node('element', 'code.alarm.audible'), None, task='Conversation with the system agent',
                            held=True)
    live_session(system.id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    assert page.evaluate('window.metaform.mascot().glyph') is None and mascot_line(mapped) == ''
    given = page.evaluate(f'window.metaform.embody("{system.id}", "seahorse")')
    assert given['mascot'] is True, given
    eventually(lambda: settings.value('web_mascot', mapped) == 'seahorse')
    assert 'seahorse' in mascot_line(mapped)
    kept = page.evaluate('[localStorage.getItem("metaform.bodies") || "", localStorage.getItem("metaform.embodied")]')
    assert 'seahorse' not in kept[0] and kept[1] is None, kept
    # the conversation ends and a new one begins: the system agent is the seahorse again, its body chosen, no offer
    live_session(system.id, state='ended')
    live_session(system.id, session='s-again')
    mine = f'window.metaform.bodies().find(one => one.work === "{system.id}")'
    page.wait_for_function(f'() => {mine}?.character === "seahorse" && {mine}.by === "person"', timeout=15000)
    assert page.evaluate('window.metaform.mascot().glyph') == 'seahorse'
    other, troubles, _ = opened(browser, web)  # another browser profile: its own storage, the same mascot
    other.wait_for_function('() => window.metaform.mascot().glyph === "seahorse"', timeout=15000)
    # changed elsewhere, on the command line, both pages draw the new mascot
    run('set', '--web-mascot=owl')
    for one in (page, other):
        one.wait_for_function('() => window.metaform.mascot().glyph === "owl"', timeout=15000)
    assert problems == [] and troubles == []


@pytest.mark.req('VIEW-035')
def test_an_agent_talking_about_a_done_ticket_is_drawn_so_it_has_eyes(run, web, mapped, browser):
    """A chat about a done ticket runs on that ticket, and the page drew no figure for a done ticket, so web_look
    refused the agent. A session begun after the ticket was done is a conversation about it, and is drawn on both maps;
    the worker's, begun before, is not, `test_an_agents_figure_walks_..._when_it_closes`."""
    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), None, task='a quieter tone')
    store.take_work(worked.id, by='codex')
    store.finish_work(worked.id, 'quieter')
    # a summoned runner, as dispatch talk starts one, begun after the ticket was done
    runner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)', 'dispatch', 'run', worked.id,
                               'system=true', f'talk=ticket:{worked.id}'])
    RUNNERS.append(runner)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': f's-{worked.id}', 'work_id': worked.id, 'agent': 'claude',
                               'state': 'running', 'pid': runner.pid, 'port': dispatch_control_port(),
                               'token': f's-{worked.id}', 'seq': 1,
                               'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 2))})
    started(run)
    page, problems, _ = opened(browser, web)
    drawn = f'window.metaform.figures().find(one => one.work_id === "{worked.id}")'
    flat = f'window.metaform.figures2d().find(one => one.work_id === "{worked.id}")'
    page.wait_for_function(f'() => {drawn}?.stage === "circling" && {flat}?.stage === "circling"', timeout=20000)
    assert problems == []


@pytest.mark.req('VIEW-035')
@pytest.mark.req('VIEW-039')
def test_each_projects_agents_are_drawn_when_the_person_switches_to_it_and_back(run, web, mapped, browser, tmp_path):
    """Reported by the person, code.interface.graphical#e: agents stopped drawing after a switch of projects. Each
    project's agent at work is drawn on both maps and in the agents key when it is chosen, with no new event from its
    session, and nothing of the project left stays."""
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    folder = tmp_path / 'other'
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    build(Store('other'))
    run('set', '--layers', ','.join(TOGGLED), cwd=folder)
    works = {}
    for project in ('proj', 'other'):
        store = Store(project)
        works[project] = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone').id
        store.take_work(works[project], by='codex')
        live_session(works[project], 'codex', project=project)
    started(run)
    page, problems, _ = opened(browser, web)
    shown = '''() => ({figures: window.metaform.figures().map(one => one.work_id),
        flat: window.metaform.figures2d().map(one => one.work_id),
        key: [...document.querySelectorAll('#agents .agent')].map(one => one.dataset.id)})'''

    def drawn_for(project):
        work = works[project]
        page.wait_for_function(f'''() => window.metaform.loaded()
            && window.metaform.figures().some(one => one.work_id === "{work}" && one.stage === "circling")
            && window.metaform.figures2d().some(one => one.work_id === "{work}" && one.stage === "circling")''',
                               timeout=20000)
        page.wait_for_timeout(500)   # anything of the project left would have been drawn by now
        assert page.evaluate(shown) == {'figures': [work], 'flat': [work], 'key': [work]}

    drawn_for('proj')
    page.select_option('#proj', 'other')
    drawn_for('other')
    page.select_option('#proj', 'proj')
    drawn_for('proj')
    assert problems == []


@pytest.mark.req('VIEW-035')
@pytest.mark.req('VIEW-039')
def test_switching_projects_on_the_page_ends_no_running_agent_and_its_figure_returns(run, web, mapped, browser,
                                                                                   tmp_path, dispatch_runners):
    """Reported by the person, code.dispatcher.agent#5c: switching the page to another project ended the agents running
    in the project left. Each project's real runner, the fake agent held in its turn, is still running after the page
    goes to the other project and back, and the figure of the first comes back; only the person's stop ends one."""
    from metaform.data import Node, Store
    from metaform.modules.dispatch.tests.test_dispatch import alive, eventually
    run('enable', 'dispatch')
    folder = tmp_path / 'other'
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    build(Store('other'))
    run('set', '--layers', ','.join(TOGGLED), cwd=folder)
    folders, works, pids = {'proj': mapped, 'other': folder}, {}, {}
    for project, where in folders.items():
        log = tmp_path / f'{project}.jsonl'
        works[project] = Store(project).add_work(Node('element', 'code.alarm.audible'), 'broken',
                                                 task='a quieter tone').id
        launched = json.loads(run('dispatch', 'start', works[project], 'claude', '--json', cwd=where,
                                  env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}).stdout)
        dispatch_runners.append((launched, where, log))
        pids[project] = launched['pid']
        logged_by(log, lambda entry: 'grandchild' in entry)   # in its turn, held there until it is cancelled
        # and the person's system agent, kept connected, as the person keeps theirs
        run('set', '--dispatch-stay-connected', cwd=where)
        system = json.loads(run('dispatch', 'system', '--json', cwd=where,
                                env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}).stdout)
        dispatch_runners.append((system, where, log))
        works[f'{project}:system'] = system['work_id']

    def sessions():
        found = {}
        for named, work in works.items():
            with Store(named.split(':')[0], module='dispatch').tables(write=False) as tx:
                found[named] = [(row['state'], row.get('how')) for row in tx.rows('agent_sessions', limit=0).results
                                if row['work_id'] == work]
        return found

    def running():
        return all(rows == [('running', None)] for rows in sessions().values()) \
            and all(alive(pid) for pid in pids.values())

    eventually(running)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#dockTab')                                    # the system agent's chat open, as the person has it
    page.click('#helpdesk .call')
    page.wait_for_selector('#helpdesk .threadbar .stop:not([hidden])', timeout=20000)

    def drawn_for(project):
        work = works[project]
        page.wait_for_function(f'''() => window.metaform.loaded()
            && window.metaform.figures().some(one => one.work_id === "{work}" && one.stage === "circling")''',
                               timeout=20000)

    drawn_for('proj')
    page.select_option('#proj', 'other')
    drawn_for('other')
    page.wait_for_timeout(2000)   # whatever the switch set off has run by now
    assert running(), sessions()
    page.select_option('#proj', 'proj')
    drawn_for('proj')
    page.wait_for_timeout(2000)
    assert running(), sessions()
    assert problems == []


@pytest.mark.req('VIEW-035')
def test_an_agent_on_the_2d_map_is_its_flat_glyph_and_walks_to_its_ticket_circles_it_and_walks_back(run, web, mapped, browser):
    """VIEW-035 in 2D: the same agents as the 3D figures, each drawn as the flat glyph its figure is drawn with, walk the
    2D map's edges from the DE to the ticket's box, circle it while the ticket is open and walk back when it closes."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='codex')
    live_session(worked.id, 'codex')
    orphan = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='left taken')   # no session behind it
    store.take_work(orphan.id, by='gone')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures2d().length === 1', timeout=15000)
    figure = page.evaluate('window.metaform.figures2d()')[0]
    assert figure['work_id'] == worked.id and figure['shown']
    page.wait_for_function('() => window.metaform.figures().length === 1', timeout=15000)
    assert figure['glyph'] == page.evaluate('window.metaform.figures()')[0]['glyph']      # the same agent in both views
    assert figure['icon'] == f"/page/agent-glyphs/{figure['glyph']}.svg"
    page.evaluate('''() => { window.stages2d = new Set(); setInterval(() => { for (const one of window.metaform.figures2d())
        window.stages2d.add(one.stage); }, 50); }''')
    page.wait_for_function('() => window.metaform.figures2d().some(one => one.stage === "circling")', timeout=20000)
    page.wait_for_timeout(800)                                        # out onto its orbit
    figure, node = page.evaluate(f'[window.metaform.figures2d()[0], window.metaform.at2d("{alarm}")]')
    away = ((figure['x'] - node['x']) ** 2 + (figure['y'] - node['y']) ** 2) ** 0.5
    assert 0 < away < 400 and figure['size'] > 0, (figure, node)                          # around the alarm's box
    run('map', 'work', 'op=done', f'id={worked.id}', 'resolution=quieter', 'why=the test closes it', cwd=mapped)
    live_session(worked.id, 'codex', state='ended')
    page.wait_for_function('() => window.stages2d.has("returning")', timeout=10000)
    page.wait_for_function('() => window.metaform.figures2d().length === 0', timeout=20000)
    assert page.locator('.agents2d image').count() == 0 and problems == []


@pytest.mark.req('VIEW-035')
@pytest.mark.req('VIEW-027')
def test_an_agents_figure_is_big_enough_to_see_while_steps_speed_up_its_nodes_light(
        run, web, mapped, browser):
    """A figure stays legible with a large map seen whole. Progress speeds up the node's flashing. The working
    figure's separate stationary-pose regression covers its position and gaze."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    far = store.element('code.timer.kitchen.display').id
    run('enable', 'dispatch')
    flawed = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(flawed.id, steps=4, by='codex')
    live_session(flawed.id, 'codex')
    missing = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='a second recipe')
    store.take_work(missing.id, steps=4, by='claude')
    live_session(missing.id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 2'
                           ' && window.metaform.figures().every(one => one.stage === "circling")', timeout=30000)
    page.wait_for_timeout(2600)                                       # the page's own fit of the whole map
    map_key(page, 'p')
    page.evaluate(f'window.metaform.pin3d("{far}", 600, 0, 0)')       # a map that spans hundreds of units
    page.evaluate('window.metaform.view3d({x: 300, y: 0, z: 900}, {x: 300, y: 0, z: 0})')  # seen whole
    page.wait_for_timeout(800)
    assert 0 < page.evaluate(f'window.metaform.screen3d("{far}").x') < page.evaluate('innerWidth')
    for figure in page.evaluate('window.metaform.figures()'):
        assert figure['px'] >= 40, figure                             # big enough to see what it is

    pace = page.evaluate(f'window.metaform.look("{alarm}").pace')
    for said in ('Found the gain.', 'Lowered it.'):
        run('map', 'work', 'op=step', f'id={flawed.id}', f'said={said}', cwd=mapped)
        run('map', 'work', 'op=step', f'id={missing.id}', f'said={said}', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").pace < {pace}', timeout=15000)  # the flashing quickens
    assert problems == []


@pytest.mark.req('VIEW-038')
def test_the_labels_wrap_keep_the_draw_order_and_the_hover_says_what_a_part_does(run, web, mapped, browser):
    """Make these labels actually useful and respect the draw order; word wrap rather than cut off;
    the hover said the name, then the name again, then the name in reverse; the data is in the joins. Labels
    observe the depth order: the alarm is
    selected, and its label still goes under the nearer timer's."""
    from metaform.data import Store
    store = Store('proj')
    kitchen = store.element('code.timer.kitchen').id
    alarm = store.element('code.alarm.audible').id
    store.add_element('notes', 'code.controller.address.fallback', name_length=3)
    long = store.element('code.controller.address.fallback').id
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.wait_for_function(f'() => window.metaform.labels3d().some(label => label.id === "{long}" && !label.hidden)')
    camera, target = {'x': 2000, 'y': 0, 'z': 300}, {'x': 2000, 'y': 0, 'z': 0}
    staged(page, {kitchen: (2000, 0, 0), alarm: (2000, 0, -150)}, (camera, target))
    page.evaluate('id => window.metaform.select(id)', alarm)
    page.wait_for_timeout(1200)                                       # the camera's flight to it ends
    page.evaluate(f'window.metaform.view3d({json.dumps(camera)}, {json.dumps(target)})')
    labels_shown(page, True)
    page.wait_for_timeout(900)
    assert page.evaluate('window.metaform.selected()') == alarm
    labels = {label['id']: label for label in page.evaluate('window.metaform.labels3d()')}
    near, far = labels[kitchen], labels[alarm]
    assert near['z'] > far['z'] and not near['under'] and far['under'], (near, far)
    signal = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--signal").trim()')
    assert far['color'] == signal, far                                # under, it keeps the selected label's color
    in_depth_order(page, camera, target)
    assert far['scene'] and far['depthTest']                          # in the scene, ordered by depth
    assert near['opacity'] == 1 and far['opacity'] < near['opacity']  # the nearest solid, a farther one faded by its depth
    names = {node['id']: node.get('name') for node in page.evaluate('window.metaform.graph().nodes') if node['t'] == 'el'}
    assert all(label['text'] == names[id] for id, label in labels.items() if id in names)  # whole, never cut off
    assert all(' '.join(label['lines']) == label['text'] for label in labels.values() if not label['hidden'])
    assert len(labels[long]['lines']) > 1, labels[long]               # a long name wraps at word breaks
    strong = [label for label in labels.values() if not label['under'] and not label['hidden']]
    for index, one in enumerate(strong):
        for two in strong[index + 1:]:
            assert (one['right'] <= two['left'] or two['right'] <= one['left'] or one['bottom'] <= two['top']
                    or two['bottom'] <= one['top']), (one, two)
    # The hover's details are in the card at the lower left; the name across the top shows only for a node whose
    # own label cannot be read. In Organic a sign faces out from the middle and may be seen edge on; in Flat every
    # sign faces the eye, and the kitchen timer's can be read.
    page.locator('body').press('3')
    page.wait_for_function('() => window.metaform.physics() === "flat"')
    page.wait_for_function('() => Math.abs(Math.sin(window.metaform.cameraAt().tilt) * Math.cos(window.metaform.cameraAt().turn))'
                           ' > 0.99', timeout=15000)  # the camera turned to face the plane
    page.evaluate(f'window.metaform.select("{kitchen}")')  # and comes in close to it, where its sign can be read
    page.wait_for_timeout(1800)
    page.wait_for_function('() => Math.abs(Math.sin(window.metaform.cameraAt().tilt) * Math.cos(window.metaform.cameraAt().turn))'
                           ' > 0.99', timeout=15000)
    page.evaluate(f'window.metaform.hover3d("{kitchen}")')
    card = page.locator('#card3d.on')
    card.wait_for(state='visible')
    # the EF of a join it serves, as written: the card has room for one; it names the node by its address, its name
    # being on its sign
    assert 'code.timer.kitchen' in card.inner_text() and 'dish timer' not in card.inner_text()
    assert page.evaluate('document.querySelector("#card3d .text").textContent') in ('Counts down and rings.',
                                                                                   'Reports the time left.')
    page.wait_for_timeout(400)  # past the moment a name waits to show, `READOUT.settle`
    assert page.evaluate('window.metaform.readout("3d")') is None
    # No subject rule; each ef is shown as written, with no receiver or provider put before it.
    page.evaluate(f'window.metaform.hover3d("{alarm}")')
    page.wait_for_function('() => document.querySelector("#card3d").textContent.includes("Plays a tone")')
    assert page.evaluate('[...document.querySelectorAll("#card3d .text")].map(e => e.textContent)') == [
        'Plays a tone.']
    assert problems == []


@pytest.mark.req('VIEW-038')
@pytest.mark.req('VIEW-025')
def test_a_node_between_the_camera_and_a_label_hides_the_label(run, web, mapped, browser):
    """Labels were in depth order but drawn in front of the nodes. The alarm's label is
    read on the screen first with nothing in front of it, then with the cook's glass node set between the camera and
    it. With nothing in front, showing the labels changes those pixels; with the node in front, the label is behind
    the node and is seen only as the glass lets it through, blurred, so showing the labels hardly changes them; with
    the glass made clear, the label is seen through it."""
    from metaform.data import Store
    store = Store('proj')
    cook = store.element('exterior.cook').id
    alarm = store.element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.emulate_media(reduced_motion='reduce')                       # nothing moves between two pictures
    page.reload(wait_until='commit')  # the page's own condition below is the wait, as the first draw's is in `opened`
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0',
                           timeout=90000)
    camera, target = {'x': 2000, 'y': 0, 'z': 300}, {'x': 2000, 'y': 0, 'z': 0}
    staged(page, {cook: (5000, 0, 0), alarm: (2000, 0, -150)}, (camera, target))
    for other in page.evaluate('window.metaform.graph().nodes.map(node => node.id)'):  # the map's middle far behind the
        if other not in (cook, alarm):                                                  # alarm, so its sign faces the eye
            page.evaluate(f'window.metaform.pin3d("{other}", 2000, 0, -4000)')

    drawn = f'window.metaform.labels3d().find(one => one.id === "{alarm}")'

    def label_change():
        page.evaluate('id => window.metaform.showLabels3d(true, [id])', alarm)  # the alarm's alone: the cook's own
        # label stands over the cook's ball; the picture is taken once the label is drawn and steady over three frames,
        # which a loaded machine makes slow
        page.wait_for_function(f'() => {{ const label = {drawn}; return label && !label.hidden && label.right > label.left; }}')
        still(page, f'() => JSON.stringify({drawn})')
        label = page.evaluate(drawn)
        inner = {'left': label['left'] + 3, 'right': label['right'] - 3, 'top': label['top'] + 2,
                 'bottom': label['bottom'] - 2}
        shown = page.screenshot()
        labels_shown(page, False)
        still(page, '() => window.metaform.labels3d().length')  # three frames drawn without the labels
        return label, inner, changed(page, shown, page.screenshot(), inner)

    label, inner, open_change = label_change()
    text = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--text").trim()')
    assert not label['under'] and label['color'] == text, label          # its own color, with nothing in front
    assert inner['right'] - inner['left'] > 20 and inner['bottom'] - inner['top'] > 6, label
    assert open_change[1] > 60, open_change                           # the label is drawn there
    page.evaluate(f'window.metaform.pin3d("{cook}", 2000, 0, 270)')   # between the camera and the alarm's label
    page.wait_for_timeout(800)
    front = page.evaluate(f'window.metaform.screen3d("{cook}")')
    for x in (inner['left'], inner['right']):
        for y in (inner['top'], inner['bottom']):
            assert math.dist((x, y), (front['x'], front['y'])) < front['r'] * 0.9, (front, inner)  # all of it behind
    covered, _, covered_change = label_change()
    assert covered_change[1] < open_change[1] / 3, (covered_change, open_change)  # hidden behind the node
    # a covered label keeps its own color, and whatever is in front hides it by depth or shows it through the glass
    assert covered['under'] and covered['color'] == label['color'], (covered, label)
    # with the glass made clear, letting all the light through, with no frosting, absorption, bending or light of its
    # own, the label behind the node is seen through it: the glass shows what is behind it, labels included
    page.evaluate('window.metaform.glass(true, {transmission: 1, emissiveIntensity: 0, clearcoat: 0, roughness: 0, '
                  'thickness: 0, attenuationDistance: Infinity, anisotropicBlur: 0, chromaticAberration: 0, distortion: 0})')
    page.wait_for_timeout(600)
    _, _, clear_change = label_change()
    assert clear_change[1] > covered_change[1] * 2, (clear_change, covered_change)  # seen through, not hidden
    assert problems == []


def in_depth_order(page, camera, target):
    """Every pair of labels in the 3D map, VIEW-038: the label of the node nearer the camera is drawn over the farther
    one's, and a label whose box falls on a nearer one's goes under it. Nothing is ranked over depth. Nearer is
    measured along the camera's view, from the camera toward what it looks at, as the depth buffer measures it."""
    labels = [label for label in page.evaluate('window.metaform.labels3d()') if not label['hidden']]
    # the rank is the page's own count; what draws a nearer label over a farther one, and a nearer node over a label,
    # is the depth buffer, so every label is in the scene, tested against it and written into it
    for label in labels:
        assert label['scene'] and label['depthTest'] and not label['depthWrite'], label  # hidden by what is nearer, hiding nothing behind
    view = [target[axis] - camera[axis] for axis in 'xyz']
    length = math.hypot(*view)
    away = {}
    for label in labels:
        at = page.evaluate('id => window.metaform.at3d(id)', label['id'])
        away[label['id']] = sum((at[axis] - camera[axis]) * view[index] / length for index, axis in enumerate('xyz'))
    for one in labels:
        for two in labels:
            if away[one['id']] < away[two['id']] - 1e-6:
                assert one['z'] > two['z'], (one, two)                # nearer over farther, always
                if not (one['right'] <= two['left'] or two['right'] <= one['left'] or one['bottom'] <= two['top']
                        or two['bottom'] <= one['top']):
                    assert two['under'], (one, two)                   # the farther one goes under the nearer


@pytest.mark.req('VIEW-038')
@pytest.mark.parametrize('case', ['unbuilt', 'selected', 'neighbor', 'broken', 'question', 'reach'])
def test_a_record_that_lights_nothing_leaves_the_label_in_depth_order(run, web, mapped, browser, case):
    """Text labels are depth sorted, whatever is blinking or selected: keeping the selected node and its neighbors on
    top reads as a bug on a navigation surface, and looks worse the more nodes there are. The alarm stands behind the cook, who carries nothing, and is in turn: a missing record, which lights
    nothing; the selected node; a neighbor of the selected node; broken, blinking; asked a question, glowing; reached by
    a property. Each time the cook's label is drawn over the alarm's, and the alarm's goes under it where they meet."""
    from metaform.data import Node, Store
    store = Store('proj')
    cook = store.element('exterior.cook').id
    alarm = store.element('code.alarm.audible').id
    display = store.element('code.timer.kitchen.display').id
    store.add_element('notes', 'code.bell', name_length=1)
    bell = store.element('code.bell').id
    store.add_join('notes', 'code.bell', 'code.alarm.audible', purpose='Ring.', ef='Rings the bell.')
    if case == 'unbuilt':
        store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='a second tone')
    elif case == 'broken':
        store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a cracked tone')
    elif case == 'question':
        store.ask(Node('element', 'code.alarm.audible'), 'Still wanted?')
    elif case == 'reach':
        key = 'r:' + store.add_property('notes', 'code.alarm.audible', 'rings at 2 kHz').id
    started(run)
    page, problems, _ = opened(browser, web)
    if case == 'reach':
        page.wait_for_function(f'() => window.metaform.graph().nodes.some(node => node.id === "{key}")', timeout=5000)
    camera, target = {'x': 2000, 'y': 0, 'z': 300}, {'x': 2000, 'y': 0, 'z': 0}
    staged(page, {cook: (2000, 0, 0), alarm: (2000, 0, -150)}, (camera, target))
    # neither the cook nor the alarm is the display's neighbor; the alarm is the bell's, and the cook is not
    chosen = {'selected': alarm, 'neighbor': bell, 'reach': key if case == 'reach' else None}.get(case, display)
    page.evaluate('id => window.metaform.select(id)', chosen)
    page.wait_for_timeout(1200)                                       # the camera's flight to it ends
    page.evaluate(f'window.metaform.view3d({json.dumps(camera)}, {json.dumps(target)})')
    labels_shown(page, True)
    page.wait_for_timeout(900)
    assert page.evaluate('window.metaform.selected()') == chosen
    if case == 'reach':
        assert 'code.alarm.audible' in page.evaluate('window.metaform.reach()')['elements']
        assert 'exterior.cook' not in page.evaluate('window.metaform.reach()')['elements']
    if case in ('broken', 'question'):
        assert case in page.evaluate('id => window.metaform.look(id)', alarm)['work'], case
    labels = {label['id']: label for label in page.evaluate('window.metaform.labels3d()')}
    near, far = labels[cook], labels[alarm]
    assert near['z'] > far['z'], (near, far)                          # nearer over farther
    assert not near['under'], (near, far)
    if case != 'unbuilt':  # a part not built is drawn as text, its label set higher, clear of the cook's
        assert far['under'], (near, far)                              # on the nearer label, so under it
    in_depth_order(page, camera, target)
    assert problems == []


AGENT_GLYPHS = ('jelly', 'gearling', 'kite', 'moth', 'drone', 'snail', 'crystal', 'wisp', 'comet', 'beetle', 'slime',
                'plane', 'puffer', 'owl', 'cubebot', 'mushroom', 'seahorse')


def logged_by(log, check, limit=60):
    """The first entry of the fake agent's log that `check` accepts, waited for up to `limit` seconds."""
    deadline = time.monotonic() + limit
    while True:
        entries = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines() if line.strip()] \
            if log.exists() else []
        found = next((entry for entry in entries if check(entry)), None)
        if found is not None:
            return found
        assert time.monotonic() < deadline, f'not in the agent\'s log within {limit} s'
        time.sleep(0.1)


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-011')
def test_the_dispatch_writes_are_taken_only_from_the_page_and_say_what_to_do_next(run, threaded, mapped, monkeypatch):
    import re

    from metaform.data import Node, Store
    from metaform.modules.web import server
    monkeypatch.setattr(server.chassis, 'page_caller', lambda *_: None)
    web = threaded
    work = Store('proj').add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Write notes.txt').id
    own, as_json = f'http://127.0.0.1:{web}', own_write(web)
    given = {'/api/dispatch-start': {'work_id': work, 'agent': 'claude'},
             '/api/dispatch-message': {'work_id': work, 'text': 'also run the tests'},
             '/api/dispatch-broadcast': {'text': 'stop and commit'},
             '/api/dispatch-fork': {'work_id': work, 'text': 'what else did you consider?'},
             '/api/dispatch-stop': {'work_id': work},
             '/api/dispatch-interrupt': {'work_id': work},
             '/api/dispatch-permit': {'work_id': work, 'request': 'r1', 'option': 'allow'},
             '/api/dispatch-configure': {'work_id': work, 'setting': 'model', 'value': 'large'},
             '/api/dispatch-resume': {'work_id': work},
             '/api/dispatch-intake': {'agent': 'claude'},
             '/api/dispatch-agents': {'default': 'claude'},
             '/api/dispatch-cancel': {'work_id': work, 'reason': 'no longer needed'}}
    for path, body in given.items():
        sent = json.dumps({'project': 'proj', **body})
        assert request(web, path, method='POST', body=sent,
                       headers={**as_json, 'Origin': 'http://rebound.example'})[0] == 403, path
    for path, body in given.items():                                   # dispatch ships disabled
        status, said = api(web, path, method='POST', headers={**as_json, 'Origin': own},
                           body=json.dumps({'project': 'proj', **body}))
        assert status == 400 and said['next'] == 'metaform enable dispatch', (path, said)
    run('enable', 'dispatch')
    status, said = api(web, '/api/dispatch-start', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', 'work_id': work, 'agent': 'someone'}))
    assert status == 400 and 'claude, codex, antigravity' in said['error'], said
    for path in ('/api/dispatch-message', '/api/dispatch-fork', '/api/dispatch-interrupt', '/api/dispatch-permit',
                 '/api/dispatch-configure'):
        status, said = api(web, path, method='POST', headers={**as_json, 'Origin': own},
                           body=json.dumps({'project': 'proj', **given[path]}))
        assert status == 400 and said['next'] == f'metaform dispatch start {work} <agent>', (path, said)
    # A recorded owner can keep a message before its session starts. An unassigned ticket above cannot.
    from metaform.module import context
    from metaform.modules.orchestration.state import SERVICE
    run('enable', 'orchestration')
    SERVICE.claim(context('orchestration', mapped, project='proj',
                          nouns={'work': work, 'role': 'gc', 'mode': 'adaptive'}))
    status, said = api(web, '/api/dispatch-message', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', **given['/api/dispatch-message']}))
    assert status == 200 and said['held'] is True, said
    # the person's Stop on a ticket no agent runs still names its delivery: its recorded assignment and descendants
    # are cancelled and nothing starts in their place (orchestration, kept 2026-10-20)
    status, said = api(web, '/api/dispatch-stop', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', **given['/api/dispatch-stop']}))
    assert status == 200 and said['stopped'] is True and said['work_id'] == work, said
    status, said = api(web, '/api/dispatch-broadcast', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', **given['/api/dispatch-broadcast']}))
    assert status == 400 and said['error'] == 'No agent is working on this project.', said
    assert Store('proj').ticket(work).work.taken is None
    # the board's Cancel is dispatch cancel: closed with the outcome cancelled and the reason, never completed, P232
    status, said = api(web, '/api/dispatch-cancel', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', **given['/api/dispatch-cancel']}))
    assert status == 200 and said['state'] == 'cancelled', said
    closed = Store('proj').ticket(work).work
    assert (closed.outcome, closed.resolution) == ('cancelled', 'Cancelled: no longer needed')
    # every figure's flat icon is served with the page, VIEW-003
    names = re.search(r'export const GLYPHS = \[(.*?)\]', (Path(__file__).parents[1] / 'page' / 'agents3d.js')
                      .read_text(encoding='utf-8'), re.DOTALL).group(1)
    assert tuple(re.findall(r"'(\w+)'", names)) == AGENT_GLYPHS
    for name in AGENT_GLYPHS:
        status, body, headers = request(web, f'/page/agent-glyphs/{name}.svg')
        assert status == 200 and headers['Content-Type'] == 'image/svg+xml' and body.startswith('<svg'), name


@pytest.mark.req('VIEW-039')
def test_a_message_naming_a_fork_goes_to_the_fork_through_dispatch_fork_and_never_with_a_recording(monkeypatch):
    """`dispatch message` names no fork, so a message written in a fork's thread reached the session it was forked
    from. Naming the fork sends it with `dispatch fork fork=<id>`, which takes the text alone."""
    from metaform.modules.web import server
    ran = []
    monkeypatch.setattr(server, 'cli_result', lambda given, module_id, verb, nouns, text=None: ran.append(
        (module_id, verb, nouns, text)) or (200, {}))
    handler = _Handler()
    handler.dispatched = lambda given, verb, nouns, text=None: server.Handler.dispatched(handler, given, verb, nouns, text)
    server.Handler.dispatch_message(handler, {'project': 'proj', 'work_id': 'w1', 'session': 's1', 'fork': 'c1',
                                              'text': ' what else? '})
    assert ran == [('dispatch', 'fork', ['w1', 'session=s1', 'fork=c1'], 'what else?')], ran
    server.Handler.dispatch_message(handler, {'project': 'proj', 'work_id': 'w1', 'fork': 'c1', 'text': 'said aloud',
                                              'audio': 'clip-1'})
    assert handler.answers[-1][0] == 400 and len(ran) == 1, handler.answers
    # /fork makes a new fork of the session, which names none; with no text the fork is made and waits
    server.Handler.dispatch_fork(handler, {'project': 'proj', 'work_id': 'w1', 'session': 's1', 'text': '  '})
    assert ran[-1] == ('dispatch', 'fork', ['w1', 'session=s1'], None), ran


@pytest.mark.req('VIEW-045')
@pytest.mark.parametrize('mode', ['extend', 'new'])
def test_intake_handler_forwards_both_modes(mode, monkeypatch):
    """The server forwards the explicit map choice and user focus without launching inference."""
    from metaform.modules.web import server
    ran = []
    monkeypatch.setattr(server, 'cli_result', lambda given, module_id, verb, nouns, text=None: ran.append(
        (module_id, verb, nouns, text)) or (200, {}))
    handler = _Handler()
    handler.dispatched = lambda given, verb, nouns, text=None: server.Handler.dispatched(handler, given, verb, nouns, text)
    given = {'project': 'proj', 'agent': 'claude', 'map': mode, 'text': ' Inspect current capabilities. '}
    server.Handler.dispatch_intake(handler, given)
    assert ran == [('dispatch', 'intake', ['agent=claude', f'map={mode}'], 'Inspect current capabilities.')]
    assert handler.answers[-1][0] == 200


@pytest.mark.req('VIEW-039')
def test_dispatch_from_the_page_runs_on_the_base_it_shows_and_an_intake_on_the_active_one(mapped, monkeypatch):
    """The board's Start, Stop, Cancel and chat run dispatch with METAFORM_BASE set to the base the page shows when it
    is not the active one; on the active base nothing is bound, and an intake follows the active base."""
    from metaform.data import Store
    from metaform.modules.web import server
    other = Store('proj').add_base('other', activate=False).id
    active = Store('proj').active_base().id
    bound = []
    monkeypatch.setattr(server.subprocess, 'run', lambda command, **given: bound.append(
        (given.get('env') or {}).get('METAFORM_BASE')) or subprocess.CompletedProcess(command, 0, '{}', ''))
    server.cli_result({'project': 'proj', 'base': other}, 'dispatch', 'start', ['w1', 'claude'])
    server.cli_result({'project': 'proj', 'base': other}, 'dispatch', 'intake', [])
    server.cli_result({'project': 'proj', 'base': active}, 'dispatch', 'stop', ['w1'])
    server.cli_result({'project': 'proj', 'base': other}, 'workflow', 'cancel', ['run=r1'])
    server.run_dispatch('proj', 'sessions', ['id=w1'], server.chosen_base({'project': 'proj', 'base': other}))
    assert bound == [other, None, None, None, other]


@pytest.mark.req('VIEW-039')
def test_the_page_lists_the_agents_with_whether_each_is_found_and_sets_the_default(run, web, mapped):
    """The page offers each agent with whether its start command is found on this machine, and the person makes one
    the default, kept in the settings as `metaform set --dispatch-agent` keeps it."""
    started(run)
    own, as_json = f'http://127.0.0.1:{web}', {'Content-Type': 'application/json'}
    status, said = api(web, '/api/dispatch-agents?project=proj')
    assert status == 200 and said == {'enabled': False, 'agents': [], 'default': None, 'next': 'metaform enable dispatch'}
    for read in ('dispatch-agents', 'dispatch-sessions', 'dispatch-claims'):  # a project not registered is said
        assert api(web, f'/api/{read}?project=gone')[0] == 404, read
    run('enable', 'dispatch')
    run('set', '--dispatch-antigravity', 'metaform-no-such-acp-adapter --acp', cwd=mapped)
    status, said = api(web, '/api/dispatch-agents', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', 'default': 'claude'}))
    assert status == 200 and said['enabled'] and said['default'] == 'claude' and said['room'] >= 1, said
    found = {one['agent']: (one['label'], one['available'], one['default']) for one in said['agents']}
    assert found['claude'] == ('Claude Code', True, True) and found['antigravity'] == ('Google Antigravity', False, False)
    assert api(web, '/api/dispatch-agents?project=proj')[1]['default'] == 'claude'
    kept = json.loads(run('config', '--json', cwd=mapped).stdout)
    assert next(entry for entry in kept if entry['key'] == 'dispatch_agent')['value'] == 'claude'
    status, said = api(web, '/api/dispatch-agents', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', 'default': 'someone'}))
    assert status == 400 and 'claude' in said['error'], said


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('VIEW-003')
def test_an_agent_is_started_on_a_ticket_followed_messaged_and_stopped_from_the_page(run, web, mapped, browser,
                                                                                     tmp_path, watch_dispatch):
    """A box on screen says Agent deployed, with each agent's icon and harness, so the person can watch an agent and
    message it to see whether it is doing the task right; the box says it, not a color."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    work = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Write notes.txt').id
    other = store.add_work(Node('element', 'exterior.cook'), None, task='Name the cook').id
    store.ask(Node('element', 'code.alarm.audible'), 'Is the tone too high?')  # a question of no agent, at the same node
    log, gate, end_gate = tmp_path / 'fake.jsonl', tmp_path / 'ask', tmp_path / 'turn-end'
    run('enable', 'dispatch')
    # the test says when the agent's turn stops on its permission prompt, and the turn goes on working after the answer
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask', 'FAKE_ACP_WORK': work,
                              'FAKE_ACP_ASK_GATE': str(gate), 'FAKE_ACP_ASK_HOLD': '1',
                              'FAKE_ACP_ASK_END': str(end_gate), 'FAKE_ACP_HOLD_LATER': '1'})
    page, problems, remote = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    # started from the node's menu, choosing the agent
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.agent') == 'Start agent 1'
    page.click('#menu button.agent')
    page.wait_for_selector('#dispatch:not([hidden])')
    page.click('#dispatch .agentpicker .choice > .btn')                 # the agents dispatch knows, VIEW-039
    assert page.eval_on_selector_all('.listbox:not([hidden]) [role=option]', 'found => found.map(one => [one.dataset.value, one.firstChild.textContent])') \
        == [['claude', 'Claude Code'], ['codex', 'Codex'], ['antigravity', 'Google Antigravity']]
    page.keyboard.press('Escape')
    assert page.eval_on_selector_all('#dispatch .ticket', 'found => found.map(one => one.dataset.id)') == [work]
    choose_agent(page, '#dispatch', 'codex')               # not the first, so the choice is what starts
    page.click(f'#dispatch .ticket[data-id="{work}"] button.start')
    # the agent deployed box: the agent's flat icon, the same character as its 3D figure, and in words what it is
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=60000)
    assert page.is_hidden('#dispatch')
    shown = page.inner_text('#agents')
    assert 'Agent deployed' in shown and 'Codex' in shown and 'on audible alarm' in shown, shown
    assert Store('proj').ticket(work).work.taken_by == 'codex fake-session-1'
    page.evaluate(f'window.metaform.menu("{alarm}")')                   # a taken ticket waits for no agent
    page.wait_for_selector('#menu:not([hidden])')
    # the taken ticket is not offered; the Facilitator's commission at the node, making its specialist, may be
    offered = page.text_content('#menu button.agent')
    assert offered in ('Start agent 0', 'Start agent 1'), offered
    if offered == 'Start agent 0':
        assert page.is_disabled('#menu button.agent')
    else:
        page.click('#menu button.agent')
        page.wait_for_selector('#dispatch:not([hidden])')
        assert work not in page.eval_on_selector_all('#dispatch .ticket', 'found => found.map(one => one.dataset.id)')
        page.click('#dispatch .close')
    page.keyboard.press('Escape')
    icon = page.get_attribute(f'#agents .agent[data-id="{work}"] img', 'src')  # the ticket's own agent: the Facilitator making its specialist runs beside it
    glyph = icon.rsplit('/', 1)[-1].removesuffix('.svg')
    assert icon == f'/page/agent-glyphs/{glyph}.svg' and glyph in AGENT_GLYPHS, icon
    page.wait_for_function(f'() => document.querySelector(\'#agents .agent[data-id="{work}"] img\').naturalWidth > 0')
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{work}")', timeout=30000)
    assert next(one for one in page.evaluate('window.metaform.figures()') if one['work_id'] == work)['glyph'] == glyph
    # the same character on every load of the page, it comes from the ticket, never from chance
    reloaded, _, _ = opened(browser, web)
    reloaded.wait_for_selector('#agents:not([hidden]) .agent', timeout=30000)
    assert reloaded.get_attribute('#agents .agent img', 'src') == icon
    # its live activity, its session's thread in the chat dock
    page.click('#agents .agent')
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.wait_for_selector('#helpdesk .log .bubble.theirs', timeout=30000)
    page.evaluate('document.activeElement.blur()')
    page.keyboard.press('w')                                           # its thinking and tool calls too, code.interface.graphical#3c
    page.wait_for_selector('#helpdesk .log .tool[data-status="completed"]', timeout=30000)
    activity = page.inner_text('#helpdesk .log')
    assert -1 < activity.find('Thinking it over') < activity.find('Hello from fake') < activity.find('Read file'), \
        activity                                                       # in the order written
    page.click('#helpdesk .min')                                       # put away; its thread stays open in it
    # its turn stops on a permission prompt: waiting on the person, so it leaves the key, VIEW-035, and its figure waits
    # still beside its node, turned toward the chat dock; it is reached from the node's work history, where its session
    # is still running
    gate.touch()
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=30000)
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{work}" && one.mood === "waiting")',
                           timeout=30000)
    waiting = api(web, '/api/dispatch-sessions?project=proj&thread=false')[1]['sessions']
    # the ticket's own session; the Facilitator making its specialist runs beside it as a helper (2026-10-20)
    assert [(one['state'], one['activity']) for one in waiting if one['work_id'] == work] == [('running', 'waiting')], waiting
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.history')
    page.wait_for_selector('#float:not([hidden]) .dispatch button.log')
    page.click('#float .dispatch button.log')
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.wait_for_selector('#helpdesk .permission.waiting .answers button', timeout=30000)
    assert page.eval_on_selector_all('#helpdesk .permission.waiting .answers button[data-option]',
                                     'found => found.map(one => one.textContent)') \
        == ['Allow once', 'Reject']                                    # the agent's own options, VIEW-039
    assert 'Is the tone too high?' not in page.inner_text('#helpdesk .asked')  # only the questions this agent asked
    page.click('#helpdesk .permission.waiting button[data-option="allow"]')
    assert logged_by(log, lambda entry: 'permission' in entry)['permission']['outcome'] \
        == {'outcome': 'selected', 'optionId': 'allow'}
    # answered, its turn executes again, so it is back under Agent deployed with the same icon
    page.wait_for_selector(f'#agents:not([hidden]) .agent[data-id="{work}"]', timeout=30000)
    assert page.get_attribute(f'#agents .agent[data-id="{work}"] img', 'src') == icon
    # a message to it, kept while it is written as the map changes, VIEW-018
    page.fill('#helpdesk textarea.say', 'also run the tests')
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    run('map', 'ask', 'element:code.timer.kitchen', 'Is one second right?', *ASK_FORM, cwd=mapped)
    # the drawn count, not changes(), which the answer's own change can move first
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 2"', timeout=10000)
    assert page.is_visible('#helpdesk') and page.input_value('#helpdesk textarea.say') == 'also run the tests'
    page.press('#helpdesk textarea.say', 'Enter')                          # Enter sends; there is no Send button
    page.wait_for_function('() => document.querySelector("#helpdesk textarea.say").value === ""')
    assert len([entry for entry in log.read_text().splitlines()
                if json.loads(entry).get('message', {}).get('method') == 'session/prompt']) == 1
    end_gate.touch()
    logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt'
              and entry['message']['params']['prompt'][0].get('text') == 'also run the tests')
    page.wait_for_function('() => document.querySelector("#helpdesk textarea.say").value === ""')  # sent, so cleared
    # a chat: the person's message in the thread with what the agent says, thinks and runs, newest in view, and the
    # dock moved by its head to float where the person wants it, resized from its corner
    page.wait_for_function('() => [...document.querySelectorAll("#helpdesk .log .bubble.mine")]'
                           '.some(one => one.innerText.includes("also run the tests"))', timeout=30000)
    for kind in ('.bubble.theirs', '.thought', '.tool', '.bubble.mine'):
        assert page.locator(f'#helpdesk .log {kind}').count(), kind
    assert page.evaluate('''() => { const list = document.querySelector("#helpdesk .log");
        return list.scrollTop + list.clientHeight >= list.scrollHeight - 2; }''')
    head = page.locator('#helpdesk .head .who').bounding_box()
    page.mouse.move(head['x'] + 20, head['y'] + 8)
    page.mouse.down()
    page.mouse.move(head['x'] - 280, head['y'] - 120, steps=6)
    page.mouse.up()
    assert page.evaluate('window.metaform.dock().place') == 'float'
    for edge in ('n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw'):                # sized from every edge and corner
        assert page.locator(f'#helpdesk .grip-{edge}').is_visible(), edge
    grip = page.locator('#helpdesk .grip-se').bounding_box()
    width = page.locator('#helpdesk').bounding_box()['width']
    page.mouse.move(grip['x'] + 6, grip['y'] + 6)
    page.mouse.down()
    page.mouse.move(grip['x'] + 66, grip['y'] + 46, steps=4)
    page.mouse.up()
    assert abs(page.locator('#helpdesk').bounding_box()['width'] - (width + 60)) <= 2
    # stopping it
    page.click('#helpdesk .threadbar .stop')
    page.click('#confirm button.confirm')
    # the agents key lists only agents at work, so a stopped one leaves it; its log is in the node's work history
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=30000)
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert [row['state'] for row in tx.rows('agent_sessions', limit=0).results] == ['ended']
    assert 'dispatch' not in [layer.name for layer in Store('proj').layers(limit=0).results]  # nothing on the map
    # the node's work history: why an agent was sent here, each dispatch of its tickets, and its thread
    page.click('#helpdesk .min')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.history')
    page.wait_for_function('() => document.querySelector("#float:not([hidden]) .dispatch")?.innerText.includes("ended")',
                           timeout=10000)                              # the history opened while it ran is read again
    assert 'Codex' in page.inner_text('#float .dispatch')
    page.click('#float .dispatch button.log')
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("Hello from fake")')
    page.click('#helpdesk .min')
    page.click('#float .close')
    # started from the board: a ticket not taken has the control, one taken has not
    page.click('#boardBtn')
    page.wait_for_selector(f'#board .card[data-id="{other}"]')
    # the stopped agent's ticket stays taken for the person to put back; nothing restarts by itself
    assert Store('proj').ticket(work).work.taken
    assert page.locator(f'#board .card[data-id="{work}"] button.start').count() == 0
    page.click(f'#board .card[data-id="{other}"] button.start')
    page.wait_for_selector('#dispatch:not([hidden])')
    assert page.eval_on_selector_all('#dispatch .ticket', 'found => found.map(one => one.dataset.id)') == [other]
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('BASE-052')
def test_the_admin_sets_how_agent_prompts_are_answered_and_the_choice_is_kept_in_the_settings(run, web, mapped, browser):
    """Agent permissions in the Agents menu, changed on the fly; the default is whatever the administrator sets, kept
    in the settings and read from them, so it never reverts on a refresh, follows the settings screen, and a refused
    save keeps the one in force and says why."""
    from metaform import loader, settings
    run('enable', 'dispatch')
    loader.get('dispatch')
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#agentsMenuBtn')
    page.wait_for_function('() => !document.querySelector("#promptsPick").disabled')  # shown as the menu opens
    assert page.eval_on_selector_all('#promptsPick option', 'found => found.map(one => one.value)') == [
        'approve-all', 'approve-reads', 'ask_all']
    assert page.locator('#promptsPick').input_value() == 'ask_all'
    page.select_option('#promptsPick', 'approve-reads')
    page.wait_for_function('() => document.querySelector("#promptsSaid").textContent.includes("approve-reads")')
    assert settings.value('dispatch_prompts', mapped) == 'approve-reads'   # in the settings, as metaform set keeps it
    again, again_problems, _ = opened(browser, web)
    again.wait_for_function('() => window.metaform.loaded()')
    again.click('#agentsMenuBtn')
    again.wait_for_function('() => document.querySelector("#promptsPick").value === "approve-reads"')
    # the settings screen changes it once the person confirms approving every prompt, and the menu says so
    again.click('#allSettingsBtn')  # it opens on Essentials, where the permission prompts are
    pick = '#settings .setrow[data-key="dispatch_prompts"] select'
    again.select_option(pick, 'approve-all')
    again.click('#confirm .btn.keep')  # kept as it is: nothing saved, and the select shows the one in force
    again.wait_for_function(f'() => document.querySelector({json.dumps(pick)}).value === "approve-reads"')
    assert settings.value('dispatch_prompts', mapped) == 'approve-reads'
    again.select_option(pick, 'approve-all')
    again.click('#confirm .btn.confirm')
    again.wait_for_function('() => document.querySelector("#promptsPick").value === "approve-all"')
    assert settings.value('dispatch_prompts', mapped) == 'approve-all'
    again.keyboard.press('Escape')
    again.click('#agentsMenuBtn')
    again.wait_for_function('() => document.querySelector("#promptsPick").value === "approve-all"'
                            ' && document.querySelector("#promptsSaid").classList.contains("risk")')

    def refuse(route):
        if route.request.method != 'POST':
            return route.fallback()
        route.fulfill(status=400, content_type='application/json', body=json.dumps({'error': 'Fixture refusal'}))

    again.route('**/api/dispatch-prompts*', refuse)
    again.select_option('#promptsPick', 'ask_all')
    again.wait_for_function('() => document.querySelector("#promptsSaid").textContent.includes("Fixture refusal")')
    assert again.locator('#promptsPick').input_value() == 'approve-all', 'the choice in force is put back'
    assert 'Not changed' in again.text_content('#promptsSaid')
    assert settings.value('dispatch_prompts', mapped) == 'approve-all'
    again.unroute('**/api/dispatch-prompts*', refuse)
    again_problems = [one for one in again_problems if 'status of 400' not in one]
    own, as_json = f'http://127.0.0.1:{web}', {'Content-Type': 'application/json'}
    assert request(web, '/api/dispatch-prompts', method='POST', headers={**as_json, 'Origin': 'http://rebound.example'},
                   body=json.dumps({'project': 'proj', 'value': 'approve-all'}))[0] == 403
    status, said = api(web, '/api/dispatch-prompts', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', 'value': 'everything'}))
    assert status == 400 and settings.value('dispatch_prompts', mapped) == 'approve-all', said
    assert problems == [] and again_problems == [] and remote == []


# ---------- the memory graph in the web GUI, VIEW-031, VIEW-034 and LAYER-012 ----------

def memory_write(port, *steps, project='proj', origin=None):
    """The page's write of the memory graph: steps, each a memory command and its arguments, VIEW-011."""
    return api(port, '/api/memory', method='POST', body=json.dumps({'project': project, 'steps': [
        {'command': command, 'arguments': arguments} for command, arguments in steps]}),
        headers={'Content-Type': 'application/json', 'Origin': origin or f'http://127.0.0.1:{port}'})


def note_write(port, node, text, project='proj'):
    return api(port, '/api/note', method='POST', body=json.dumps({'project': project, 'node': node, 'text': text}),
               headers=own_write(port))


@pytest.mark.req('VIEW-031')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('LAYER-013')
@pytest.mark.req('BASE-035')
def test_the_page_reads_the_memory_graph_and_writes_it_through_the_memory_commands(run, web, mapped):
    """The person shows the memories in the graph and manages them, and memories that lost their node show what they
    were attached to through an orphaned menu. The page reads the whole graph with whether each join's memory shows at its node in the page's layers, the
    orphaned joins, and a node's read with what the modules add, as `map node` gives it; it writes through the memory
    commands, from its own page only."""
    started(run)
    kitchen = 'element:code.timer.kitchen'
    status, said = memory_write(web, ('create_entities', {'entities': [
        {'name': 'drift', 'entityType': 'behavior', 'observations': ['Drifts under load.']}], 'node': kitchen}),
        ('create_entities', {'entities': [{'name': 'tone', 'entityType': 'behavior', 'observations': []}],
                             'node': 'element:code.alarm.audible'}),
        ('create_relations', {'relations': [{'from': 'drift', 'to': 'tone', 'relationType': 'delays'}]}))
    assert status == 200 and said['done'][0] == {'entities': [
        {'name': 'drift', 'entityType': 'behavior', 'observations': ['Drifts under load.']}],
        'items': ['code.timer.kitchen#2  Drifts under load.']}  # each observation numbered at its node
    assert memory_write(web, ('create_entities', {'entities': []}), origin='http://rebound.example')[0] == 403
    status, said = memory_write(web, ('read_graph', {}))
    assert status == 400 and 'create_entities' in said['error']  # only the commands that write
    status, said = memory_write(web, ('add_observations', {'observations': [{'entityName': 'nobody', 'contents': ['x']}]}))
    assert status == 400 and said['error'] == 'Entity with name nobody not found'
    # steps run in order and stop at the first that fails, saying what the ones before it did; an edit is written
    # new before old, so the old is still there when the second step fails
    status, said = memory_write(web, ('add_observations', {'observations': [{'entityName': 'drift', 'contents': ['Hot.']}]}),
                                ('add_observations', {'observations': [{'entityName': 'nobody', 'contents': ['x']}]}),
                                ('delete_observations', {'deletions': [{'entityName': 'drift', 'observations': ['Drifts under load.']}]}))
    assert status == 400 and said['done'] == [{'results': [{'entityName': 'drift', 'addedObservations': ['Hot.']}]}]
    held = next(one for one in json.loads(run('memory', 'graph', '--json', cwd=mapped).stdout)['entities']
                if one['name'] == 'drift')
    assert [one['content'] for one in held['observations']] == ['Drifts under load.', 'Hot.']
    # the whole graph, each join saying whether it shows at its node in the page's layers
    on = ','.join([*TOGGLED, 'memory'])
    status, whole = api(web, f'/api/memory-graph?project=proj&layers={on}')
    assert status == 200 and [one['name'] for one in whole['entities']] == ['drift', 'tone']
    assert sorted(whole) == ['entities', 'joins', 'relations']  # the memory module's graph as it gives it
    assert whole['entities'][1] == {'name': 'tone', 'entityType': 'behavior', 'observations': []}
    assert [(one['from'], one['relationType'], one['to']) for one in whole['relations']] == [('drift', 'delays', 'tone')]
    assert {one['entity']: (one['address'], one['shows'], one['orphaned']) for one in whole['joins']} == {
        'drift': ('code.timer.kitchen', True, False), 'tone': ('code.alarm.audible', True, False)}
    folder = {one['entity']: one['shows'] for one in api(web, '/api/memory-graph?project=proj')[1]['joins']}
    assert folder == {'drift': False, 'tone': False}  # the folder's layers leave memory out
    # a node's read carries what memory adds to it, as map node does
    status, node = api(web, f'/api/node?project=proj&target={kitchen}&layers={on}')
    assert status == 200 and node['memory']['entities'] == [
        {'name': 'drift', 'entityType': 'behavior', 'observations': ['Drifts under load.', 'Hot.']}]
    assert 'memory' not in api(web, f'/api/node?project=proj&target={kitchen}')[1]
    # the orphaned menu: a join whose address the map no longer holds
    assert api(web, '/api/memory-orphaned?project=proj')[1] == {'joins': []}
    run('clear', 'project', '--confirm', cwd=mapped)
    lost = api(web, '/api/memory-orphaned?project=proj')[1]['joins']
    assert sorted((one['entity'], one['address']) for one in lost) == [('drift', 'code.timer.kitchen'),
                                                                     ('tone', 'code.alarm.audible')]
    status, said = memory_write(web, ('unjoin', {'id': lost[0]['join_id']}))
    assert status == 200 and said == {'done': [{'deleted': 1}]}
    assert len(api(web, '/api/memory-orphaned?project=proj')[1]['joins']) == 1
    assert [one['name'] for one in api(web, '/api/memory-graph?project=proj')[1]['entities']] == ['drift', 'tone']


@pytest.mark.req('VIEW-034')
@pytest.mark.req('VIEW-011')
def test_the_page_writes_a_nodes_one_note_through_memory_note(run, web, mapped):
    """One single note, not a list, of at most 2048 characters, edited in place. The page's note is the node's one note, written in place as the user's."""
    started(run)
    alarm = 'element:code.alarm.audible'
    status, said = note_write(web, alarm, 'Too quiet in a loud kitchen.')
    assert status == 200 and said['note']['text'] == 'Too quiet in a loud kitchen.' and said['note']['by'] == 'user'
    note_write(web, alarm, 'Ask before changing the pitch.')
    read = json.loads(run('memory', 'note', alarm, '--json', cwd=mapped).stdout)['note']
    assert (read['text'], read['by']) == ('Ask before changing the pitch.', 'user')  # replaced, not added to
    assert api(web, f'/api/memory-note?project=proj&node={alarm}')[1]['note']['text'] == 'Ask before changing the pitch.'
    # the next agent reads it at the node, with memory left out by the folder's layers, VIEW-034
    shown = json.loads(run('map', 'node', alarm, '--json', cwd=mapped).stdout)['memory']['note']
    assert (shown['text'], shown['by']) == ('Ask before changing the pitch.', 'user')
    assert note_write(web, alarm, 'x' * 2048)[0] == 200
    status, said = note_write(web, alarm, 'x' * 2049)
    assert status == 400 and '2049' in said['error']
    assert json.loads(run('memory', 'note', alarm, '--json', cwd=mapped).stdout)['note']['text'] == 'x' * 2048
    assert note_write(web, alarm, '')[1]['note'] is None  # empty text clears it
    assert json.loads(run('memory', 'note', alarm, '--json', cwd=mapped).stdout)['note'] is None
    assert 'memory' not in json.loads(run('map', 'node', alarm, '--json', cwd=mapped).stdout)


@pytest.mark.req('VIEW-031')
@pytest.mark.req('LAYER-012')
@pytest.mark.req('LAYER-013')
@pytest.mark.req('VIEW-018')
def test_a_person_shows_and_manages_the_memories_in_the_graph_and_finds_the_orphaned_ones(run, web, mapped, browser):
    """Memory shows as a layer in the page called memory: the person shows the memories in the graph and manages
    them, and memories that lost their node show what they were attached to through an orphaned menu."""
    remember(run, mapped, 'create_entities', [entity('countdown drift', 'Drifts under load.', 'Worse when hot.')],
             'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'Too quiet.')], 'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'quiet tone', 'relationType': 'drives'}])
    remember(run, mapped, 'create_entities', [entity('old tone', 'Long ago.')], 'element:code.alarm.audible')
    whole = lambda: json.loads(run('memory', 'graph', '--json', cwd=mapped).stdout)
    observed = lambda name: next(one for one in whole()['entities'] if one['name'] == name)['observations']
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    # the memory layer in the layer list, turned on
    set_layer(page, 'memory', True)
    page.wait_for_function('() => window.metaform.loaded() && '
                           'window.metaform.graph().nodes.some(node => node.id === "e:old tone")')
    remember(run, mapped, 'delete_entities', ['old tone'])
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.loaded() && '
                           '!window.metaform.graph().nodes.some(node => node.id === "e:old tone")', timeout=10000)
    # an agent's memory reaches the open page at once
    page.evaluate('window.metaform.select("e:countdown drift")')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("Worse when hot.")')
    assert page.text_content('#p-object .eyebrow') == 'Memory'
    remember(run, mapped, 'add_observations', [{'entityName': 'countdown drift', 'contents': ['Seen at noon.']}])
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("Seen at noon.")',
                           timeout=10000)
    # an observation edited, one deleted and one added
    row = '#p-object .obs:has-text("{}")'
    page.click(row.format('Worse when hot.') + ' button.edit')
    page.fill(row.format('Worse when hot.') + ' textarea', 'Worse above 40 C.')
    page.click(row.format('Worse when hot.') + ' button.save')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("Worse above 40 C.")')
    assert 'Worse when hot.' not in page.inner_text('#p-object')
    assert sorted(one['content'] for one in observed('countdown drift')) == [
        'Drifts under load.', 'Seen at noon.', 'Worse above 40 C.']
    page.click(row.format('Seen at noon.') + ' button.delete')
    page.wait_for_function('() => !document.querySelector("#p-object").textContent.includes("Seen at noon.")')
    page.fill('#p-object textarea.add-obs', 'Fine at night.')
    page.click('#p-object button.add-obs')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("Fine at night.")')
    assert [one['content'] for one in observed('countdown drift')] == [
        'Drifts under load.', 'Worse above 40 C.', 'Fine at night.']
    # renamed and retyped, keeping its observations, its relation and its join
    page.click('#p-object button.rename')
    page.fill('#p-object input.name', 'tick drift')
    page.fill('#p-object input.type', 'fault')
    page.click('#p-object button.save-entity')
    page.wait_for_function('() => window.metaform.selected() === "e:tick drift"')
    drift = next(one for one in whole()['entities'] if one['name'] == 'tick drift')
    assert drift['entityType'] == 'fault' and [one['content'] for one in drift['observations']] == [
        'Drifts under load.', 'Worse above 40 C.', 'Fine at night.']
    assert [(one['from'], one['relationType'], one['to']) for one in whole()['relations']] == [
        ('tick drift', 'drives', 'quiet tone')]
    assert [(one['entity'], one['address']) for one in whole()['joins'] if one['entity'] == 'tick drift'] == [
        ('tick drift', 'code.timer.kitchen')]
    assert 'countdown drift' not in [one['name'] for one in whole()['entities']]
    # its relation deleted, and its memory join taken away
    page.wait_for_selector('#p-object .rel:has-text("drives")')
    page.click('#p-object .rel:has-text("drives") button.delete')
    page.wait_for_function('() => !document.querySelector("#p-object .rel")')
    assert whole()['relations'] == []
    page.click('#p-object .join:has-text("dish timer") button.unjoin')
    page.wait_for_function('() => window.metaform.loaded() && '
                           '!window.metaform.graph().nodes.some(node => node.id === "e:tick drift")')
    assert [one for one in whole()['joins'] if one['entity'] == 'tick drift'] == []
    # the orphaned menu: what the memories were attached to, once the map no longer holds it
    assert page.text_content('#orphanBtn') == 'Orphaned memories 0'
    run('clear', 'project', '--confirm', cwd=mapped)
    page.wait_for_function('() => document.querySelector("#orphanBtn").textContent === "Orphaned memories 1"',
                           timeout=10000)
    page.click('#adminBtn')                                            # in the Administration menu
    page.click('#orphanBtn')
    page.wait_for_selector('#float:not([hidden]) .orphan')
    assert page.locator('#float .orphan').all_inner_texts()[0].startswith('quiet tone')
    assert 'code.alarm.audible' in page.inner_text('#float .orphan')
    assert 'tick drift' in page.inner_text('#float .loose')  # joined to no node at all
    page.click('#float .loose:has-text("tick drift") button.forget')  # deleted from the graph
    page.wait_for_function('() => !document.querySelector("#float .loose")')
    page.click('#float .orphan button.unjoin')                         # its join taken away, the memory kept
    page.click('#confirm button.confirm')                              # it cannot be made again, so it is asked first
    page.wait_for_function('() => document.querySelector("#orphanBtn").textContent === "Orphaned memories 0"')
    assert [one['name'] for one in whole()['entities']] == ['quiet tone'] and whole()['joins'] == []
    assert problems == []


def distributed(port, agents, project='proj'):
    return api(port, '/api/distribute', method='POST', body=json.dumps({'project': project, 'agents': agents}),
               headers=own_write(port))


def glyph_of(record):
    """The glyph the map module keeps on a work record, under its own id, BASE-035 and STORE-045; None for none."""
    return (record.get('map') or {}).get('glyph')


def glyph_held(run, folder, work_id):
    """A ticket's glyph as an agent reads it, from `map work id=`."""
    return glyph_of(json.loads(run('map', 'work', f'id={work_id}', '--json', cwd=folder).stdout))


@pytest.mark.req('VIEW-040')
@pytest.mark.req('VIEW-011')
def test_the_page_distributes_the_open_tickets_over_n_agents_through_the_store_and_only_from_its_own_page(run, web, mapped):
    from metaform.data import Node, Store
    from metaform.modules.map import AGENT_GLYPHS as GIVEN
    store = Store('proj')
    made = [store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task=f'part {n}').id for n in range(3)]
    started(run)
    refused, _ = api(web, '/api/distribute', method='POST', body=json.dumps({'project': 'proj', 'agents': 2}),
                     headers={'Content-Type': 'application/json', 'Origin': 'http://evil.example'})
    assert refused == 403 and glyph_held(run, mapped, made[0]) is None
    assert distributed(web, 'two')[0] == 400 and distributed(web, 0)[0] == 400 and distributed(web, 18)[0] == 400
    status, body = distributed(web, 2)
    assert status == 200, body
    # the fixture's own open tickets come first; every one not taken or done is given a glyph, in turn
    given = [(one['id'], glyph_of(one)) for one in body['results']]
    assert [glyph for _, glyph in given] == [GIVEN[place % 2] for place in range(len(given))]
    assert set(made) <= {work_id for work_id, _ in given}
    assert all(glyph_held(run, mapped, work_id) == glyph for work_id, glyph in given)


@pytest.mark.req('VIEW-040')
def test_the_page_distributes_and_reads_glyphs_on_the_metaform_it_chose_and_shows_none_with_map_off(run, web, mapped):
    """VIEW-040: the work read adds the glyphs and `/api/distribute` runs `map work op=distribute`, both on the
    metaform the page chose; with the map module not on the surface the board shows no glyphs."""
    from metaform.data import Node, Store
    from metaform.modules.map import AGENT_GLYPHS as GIVEN
    chosen = Store('proj').add_base('other', activate=False).id
    other = Store('proj', base=chosen)
    other.add_element(None, 'code', name_length=1, name='code', role='DE')
    made = [other.add_work(Node('element', 'code'), 'unbuilt', task=f'part {n}').id for n in range(2)]
    active = {one['id'] for one in plain(Store('proj').work(limit=0))['results']}
    started(run)
    status, body = api(web, '/api/distribute', method='POST', headers=own_write(web),
                       body=json.dumps({'project': 'proj', 'base': chosen, 'agents': 2}))
    assert status == 200, body
    assert [(one['id'], glyph_of(one)) for one in body['results']] == list(zip(made, GIVEN[:2]))
    shown = api(web, f'/api/work?project=proj&base={chosen}')[1]['results']
    assert {one['id']: glyph_of(one) for one in shown} == dict(zip(made, GIVEN[:2]))
    assert all(glyph_of(one) is None for one in api(web, '/api/work?project=proj')[1]['results']
               if one['id'] in active)                            # the active metaform's tickets were not dealt
    run('disable', 'map', cwd=mapped)                                  # after the server started
    status, body = api(web, f'/api/work?project=proj&base={chosen}')
    assert status == 200 and [one['id'] for one in body['results']] == made
    assert all('map' not in one for one in body['results'])


@pytest.mark.req('VIEW-040')
@pytest.mark.req('VIEW-037')
@pytest.mark.req('VIEW-039')
def test_each_card_shows_its_agents_glyph_and_the_same_glyph_is_its_figure_and_its_icon_under_agent_deployed(
        run, web, mapped, browser):
    """The board shows each ticket's agent glyph, the same glyph everywhere. Tickets with the same glyph are one agent's, done one at a time, and a button distributes work over N agents
    by assigning N glyphs evenly."""
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    tickets = [store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task=f'part {n}').id
               for n in range(4)]
    early = store.add_work(Node('element', 'exterior.cook'), None, task='already at work').id
    store.take_work(early, by='claude')                               # taken before the work is distributed
    live_session(early)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 1', timeout=15000)
    page.click('#boardBtn')
    page.wait_for_selector('#board:not([hidden]) .card')
    glyph = lambda work_id: page.get_attribute(f'#board .card[data-id="{work_id}"] .glyph', 'alt')
    figure_of = lambda work_id: next((one['glyph'] for one in page.evaluate('window.metaform.figures()')
                                      if one['work_id'] == work_id), None)
    # a ticket with no glyph of its own shows its figure's while its agent is at work, and none before
    assert glyph(early) == figure_of(early) and glyph(early) in AGENT_GLYPHS
    assert all(page.locator(f'#board .card[data-id="{work_id}"] .glyph').count() == 0 for work_id in tickets)
    page.fill('#board .distribute input', '2')
    page.click('#board .distribute button')
    page.wait_for_function(f'() => document.querySelector(\'#board .card[data-id="{tickets[-1]}"] .glyph\')')
    lanes = [glyph(work_id) for work_id in tickets]
    assert lanes == [glyph_held(run, mapped, work_id) for work_id in tickets]
    # given in turn: four tickets side by side in To do alternate between the two glyphs, and the two are even
    assert set(lanes) == set(AGENT_GLYPHS[:2]) and lanes[0] == lanes[2] != lanes[1] == lanes[3]
    spread = [glyph_of(record) for record in json.loads(run('map', 'work', 'open=true', 'limit=0', '--json',
                                                            cwd=mapped).stdout)['results'] if not record['taken']]
    assert abs(spread.count(AGENT_GLYPHS[0]) - spread.count(AGENT_GLYPHS[1])) <= 1
    assert glyph_held(run, mapped, early) is None and glyph(early) == figure_of(early)
    for work_id, lane in zip(tickets, lanes):
        assert page.get_attribute(f'#board .card[data-id="{work_id}"] .glyph', 'src') == f'/page/agent-glyphs/{lane}.svg'
    src = page.get_attribute(f'#board .card[data-id="{tickets[1]}"] .glyph', 'src')
    page.wait_for_function(f'() => document.querySelector(\'#board .card[data-id="{tickets[1]}"] .glyph\').naturalWidth > 0')
    # an agent at work on a distributed ticket is drawn as that ticket's glyph, on the map and under Agent deployed
    live_session(tickets[1])
    run('map', 'work', 'op=take', f'id={tickets[1]}', 'by=claude', cwd=mapped)
    from metaform import relay  # the runner announces its session, as every agent test delivers it
    relay.deliver('map.changed', {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch'})
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{tickets[1]}")', timeout=20000)
    assert figure_of(tickets[1]) == lanes[1]
    page.wait_for_selector(f'#agents .agent[data-id="{tickets[1]}"]', timeout=10000)
    assert page.get_attribute(f'#agents .agent[data-id="{tickets[1]}"] img', 'src') == src
    assert glyph(tickets[1]) == lanes[1]
    page.click('#board .close')
    page.click(f'#agents .agent[data-id="{tickets[1]}"]')                 # and in its thread in the dock, VIEW-039
    page.wait_for_selector('#helpdesk:not([hidden]) .threadbar .icon:not([hidden])')
    assert page.get_attribute('#helpdesk .threadbar .icon', 'src') == src
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-039')
def test_a_line_of_an_agents_thread_reads_the_agents_again_and_never_the_map(run, web, mapped, browser):
    """Each line an agent streams is announced. Reading the whole map again for each one kept the page reading and
    never showing a finished ticket, so a line reads only the agents key, without threads, and the open window's own
    thread."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    reads = []
    page.on('request', lambda sent: reads.append(sent.url))
    live_session(worked.id)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': f's-{worked.id}', 'name': 'said-1', 'work_id': worked.id,
                            'kind': 'agent_message_chunk', 'text': 'Hello from the line', 'seq': 1})
    payload = {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch',
               'work_ids': [worked.id], 'session_ids': [f's-{worked.id}'], 'kinds': ['session']}
    relay.deliver('map.changed', payload)  # as the runner's process announces it
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=10000)
    page.click('#agents .agent')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("Hello from the line")',
                           timeout=10000)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': f's-{worked.id}', 'name': 'said-2', 'work_id': worked.id,
                            'kind': 'agent_message_chunk', 'text': 'and a second line', 'seq': 2})
    heard = page.evaluate('window.metaform.heard()')
    relay.deliver('map.changed', {**payload, 'kinds': ['line']})  # as the runner's process announces it
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("a second line")',
                           timeout=10000)
    assert not [url for url in reads if '/api/graph' in url or '/api/memory-graph' in url], reads
    sessions = [url for url in reads if '/api/dispatch-sessions' in url]
    assert sessions and all('thread=false' in url or f'id={worked.id}' in url for url in sessions), sessions
    # A ticket closed changes only tickets: the page reads work and the open messages, at most three reads, never the map.
    # the second line heard and the agents read it caused done, so only the close's own reads are counted below
    page.wait_for_function(f'() => window.metaform.heard() > {heard} && window.metaform.agentsIdle()', timeout=10000)
    handled, mark = page.evaluate('window.metaform.changes()'), len(reads)
    run('map', 'work', 'op=done', f'id={worked.id}', 'resolution=quieter', 'why=the test closes it', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {handled}', timeout=15000)
    asked = [url.split('/api/')[1].split('?')[0] for url in reads[mark:] if '/api/' in url]
    assert len(asked) <= 3 and set(asked) <= {'work', 'messages'}, asked
    live_session(worked.id, state='ended')
    relay.deliver('map.changed', payload)  # its runner announces the session ended
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=15000)
    run('enable', 'hello')
    with page.expect_request(lambda sent: '/api/graph' in sent.url, timeout=15000):  # a write to the map redraws it
        run('hello', 'greet', 'world', cwd=mapped)
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-044')
def test_a_burst_of_changes_reads_only_what_each_change_names(run, web, mapped, browser):
    """CLAUDE.md Architecture section 2: a page's handler decides from the event alone, then reads only the record it
    names. Session writes never read the merges, a change already drawn reads nothing, and a ticket's step reads that
    ticket alone, never every ticket and the open messages."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, steps=2, by='claude')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.agentsIdle()', timeout=15000)
    base = store.active_base().id
    reads = []
    page.on('request', lambda sent: reads.append(sent.url))
    asked = lambda mark: [url.split('/api/')[1] for url in reads[mark:] if '/api/' in url]
    # a runner's session writes, 50 of them: the agents key for the one ticket, never the merges
    mark, heard = len(reads), page.evaluate('window.metaform.heard()')
    session = {'project': 'proj', 'base_id': base, 'tables': 'dispatch', 'dispatch_tables': ['dispatch.sessions'],
               'kinds': ['session'], 'work_ids': [worked.id]}
    for _ in range(50):
        relay.deliver('map.changed', session)
    page.wait_for_function(f'() => window.metaform.heard() > {heard} && window.metaform.agentsIdle()', timeout=15000)
    assert not [url for url in asked(mark) if url.startswith('merges')], asked(mark)
    with page.expect_request(lambda sent: '/api/merges' in sent.url, timeout=15000):  # a merge put up reads them once
        relay.deliver('map.changed', {**session, 'dispatch_tables': ['dispatch.merges'], 'kinds': ['merge']})
    page.wait_for_function('() => window.metaform.agentsIdle()', timeout=15000)
    assert len([url for url in asked(mark) if url.startswith('merges')]) == 1, asked(mark)
    # 50 changes whose ops the page has drawn, then a ticket's step: that ticket alone is read, nothing else
    mark, handled = len(reads), page.evaluate('window.metaform.changes()')
    drawn = {'project': 'proj', 'base_id': base, 'tables': ['objects', 'ops'], 'seq': store.sequence(),
             'kinds': ['map'], 'work_ids': []}
    for _ in range(50):
        relay.deliver('map.changed', drawn)
    with page.expect_response(lambda answer: '/api/work?' in answer.url, timeout=15000) as answered:
        run('map', 'work', 'op=step', f'id={worked.id}', 'said=Found the gain.', cwd=mapped)
    assert [one['steps_done'] for one in answered.value.json()['results']] == [1]
    page.wait_for_function(f'() => window.metaform.changes() > {handled} && window.metaform.liveIdle()',
                           timeout=15000)
    assert asked(mark) == [f'work?project=proj&base={base}&ids={worked.id}&limit=0'], asked(mark)
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-035')
def test_opening_the_page_reads_the_open_tickets_alone_and_a_step_reads_its_ticket_alone(run, web, mapped, browser):
    """Opening the page costs what it shows, not the project's history (work 57bffbda): with 400 done tickets the load
    reads the open ones alone, under 50 KB, and each node's light is paced from them; a ticket's step reads that ticket
    alone and its node's pace follows, VIEW-035."""
    from metaform.data import Node, Store
    store = Store('proj')
    for number in range(400):  # each about as long as a real ticket's task
        done = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task=f'old work {number} ' + 'x' * 4000)
        store.finish_work(done.id, 'Done long ago.')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, steps=2, by='claude')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    with page.expect_response(lambda answer: '/api/work?' in answer.url, timeout=15000) as loaded:
        page.reload()
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.liveIdle()', timeout=15000)
    assert 'open=true' in loaded.value.url and len(loaded.value.body()) < 50_000, loaded.value.url
    held = loaded.value.json()['results']
    assert worked.id in [one['id'] for one in held] and not [one for one in held if one['done']], held
    pace = f'document.querySelector(\'#map2d svg g.node[data-key="{worked.node_id}"]\').style.getPropertyValue("--pace")'
    assert page.evaluate(pace) == '1.2s'  # taken, no step filed: the slow beat
    reads = []
    page.on('request', lambda sent: reads.append(sent.url))
    run('map', 'work', 'op=step', f'id={worked.id}', 'said=Found the gain.', cwd=mapped)
    page.wait_for_function(f'() => {pace} === "0.72s"', timeout=15000)  # one step of two: halfway to the fast beat
    base = store.active_base().id
    worked_reads = [url.split('/api/')[1] for url in reads if '/api/work?' in url]
    assert worked_reads == [f'work?project=proj&base={base}&ids={worked.id}&limit=0'], worked_reads
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-039')
def test_a_line_written_while_the_server_restarts_shows_in_the_open_agent_window_when_the_page_reconnects(
        run, web, mapped, browser):
    """A Codex agent restarted the web GUI right after it answered the person, work 109ae725: the announcements of its answer
    reached no page, and the open window showed it only when some later line came. On its reconnect the page reads the
    agents and the open window's thread again, with no further line announced."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='codex')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    live_session(worked.id, agent='codex')
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': f's-{worked.id}', 'name': 'said-1', 'work_id': worked.id,
                            'kind': 'person', 'text': 'Just checking in how is it going?', 'seq': 1})
    payload = {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch'}
    relay.deliver('map.changed', payload)
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=10000)
    page.click('#agents .agent')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("how is it going")',
                           timeout=10000)
    run('web', 'stop')
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': f's-{worked.id}', 'name': 'said-2', 'work_id': worked.id,
                            'kind': 'agent_message_chunk', 'text': 'The routes are in place.', 'seq': 2})
    relay.deliver('map.changed', payload)  # announced while no server listens
    started(run)
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("routes are in place")',
                           timeout=15000)
    assert problems == []


def thread_line(work_id, seq, text, kind='agent_message_chunk', session=None):
    """One line of a session's thread, as the runner writes it."""
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': session or f's-{work_id}', 'name': f'line:{seq}', 'work_id': work_id,
                            'kind': kind, 'text': text, 'seq': seq})


def published(work_id, seq, ident, name, data, project='proj'):
    """A file an agent attached, kept and noted as `dispatch attach` keeps it: its bytes and meta.json under the
    project's folder in the Metaform home, and its line in the session's thread."""
    import hashlib

    from metaform import home as metaform_home
    session = f's-{work_id}'
    kept = metaform_home.project_folder(project) / 'published' / session / ident
    kept.mkdir(parents=True)
    (kept / name).write_bytes(data)
    meta = {'id': ident, 'name': name, 'size': len(data), 'type': 'text/plain', 'source': f'artifacts/{name}',
            'sha256': hashlib.sha256(data).hexdigest(), 'work_id': work_id, 'session_id': session}
    (kept / 'meta.json').write_text(json.dumps(meta))
    from metaform.data import Store
    with Store(project, module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': session, 'name': f'attachment:{ident}', 'work_id': work_id,
                            'kind': 'attachment', 'text': json.dumps(meta), 'seq': seq})
    return kept / name


@pytest.mark.req('VIEW-039')
def test_an_agents_attachments_download_their_own_bytes_and_its_diagrams_are_drawn_in_its_messages(
        run, web, mapped, browser):
    """code.interface.graphical#18: a file the agent attached is a card with its name, size and type whose Download
    gives exactly its bytes, two files of one name each their own, and a file no longer kept says so; a Mermaid block
    in a message is drawn in place with its source a click away, one still being written or one Mermaid cannot read
    shows its source and why, ordinary code stays code, and the drawings come back after a reload."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    live_session(worked.id)
    thread_line(worked.id, 1, 'The flow:\n\n```mermaid\nflowchart LR\n  agent[The agent] --> person[The person]\n```\n\n'
                              'And the code:\n\n```python\nprint("kept as code")\n```')
    thread_line(worked.id, 2, 'A broken one:\n\n```mermaid\nflowchart LR\n  A --> B --> ]]]\n```\nStill read.')
    thread_line(worked.id, 3, 'Being written:\n\n```mermaid\nflowchart TD\n  X --> Y')
    first = 'The brief, é ✓\r\n'.encode() + bytes(range(256))
    brief = published(worked.id, 4, '0123456789abcdef', 'brief.txt', first)
    published(worked.id, 5, 'fedcba9876543210', 'brief.txt', b'a later brief of the same name')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    payload = {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch',
               'dispatch_tables': ['dispatch.lines']}

    def thread():
        page.wait_for_selector('#agents:not([hidden]) .agent', timeout=10000)
        page.click('#agents .agent')
        page.wait_for_selector('#helpdesk .log .diagram[data-state="drawn"] svg', timeout=15000)

    thread()
    log = '#helpdesk .log'
    assert page.locator(f'{log} .diagram[data-state="failed"] .diagramnote').text_content().startswith(
        'Mermaid could not read this diagram')
    assert 'Still read.' in page.locator(log).inner_text()                  # the message reads on past it
    assert page.locator(f'{log} .diagram[data-state="writing"] pre').text_content() == 'flowchart TD\n  X --> Y'
    assert page.locator(f'{log} .code:not(.diagram) pre').text_content() == 'print("kept as code")'
    assert 'The person' in page.locator(f'{log} .diagram[data-state="drawn"] svg').text_content()
    page.click(f'{log} .diagram[data-state="drawn"] .codehead .btn')        # its source, one click away
    assert page.locator(f'{log} .diagram[data-state="drawn"] pre').is_visible()
    page.click(f'{log} .diagram[data-state="drawn"] [aria-label="Enlarge the diagram"]')
    page.wait_for_selector('.window.diagramwin svg')
    page.keyboard.press('Escape')
    page.wait_for_selector('.window.diagramwin', state='detached')
    with Store('proj', module='dispatch').tables() as tx:                  # the block being written is finished
        tx.update('session_lines', {'session_id': f's-{worked.id}', 'name': 'line:3'},
                  {'text': 'Being written:\n\n```mermaid\nflowchart TD\n  X --> Y\n```'})
    relay.deliver('map.changed', payload)
    page.wait_for_function(f'() => document.querySelectorAll("{log} .diagram[data-state=drawn] svg").length === 2',
                           timeout=15000)
    cards = page.locator(f'{log} .attachment')
    assert cards.count() == 2
    assert 'brief.txt' in cards.nth(0).inner_text() and f'{len(first)} bytes · text/plain' in cards.nth(0).inner_text()
    for index, expected in ((0, first), (1, b'a later brief of the same name')):
        with page.expect_download() as downloading:
            cards.nth(index).locator('a').click()
        assert downloading.value.suggested_filename == 'brief.txt'
        assert Path(downloading.value.path()).read_bytes() == expected
    page.reload()                                                           # drawn again from the stored thread
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    thread()
    assert page.locator(f'{log} .diagram[data-state="drawn"] svg').count() == 2
    brief.unlink()
    page.locator(f'{log} .attachment').nth(0).locator('a').click()
    page.wait_for_selector(f'{log} .attachment.missing')
    assert 'no longer kept' in page.locator(f'{log} .attachment.missing').inner_text()
    assert problems == ['Failed to load resource: the server responded with a status of 404 (Not Found)']


@pytest.mark.req('VIEW-039')
@pytest.mark.req('MCP-037')
def test_a_metaform_calls_view_runs_in_the_chat_as_its_sessions_and_goes_with_its_project(
        run, web, mapped, browser, tmp_path):
    """code.interface.graphical#18: the node view a map_item call shows is the real view from the folder's MCP
    server, handed the call's input and result in the thread; its reads go as the thread's session; what the person
    selects in it goes to that session with their next message; a request this host does not offer is said over it;
    it pops out to a panel and back; and leaving the project tears every view down."""
    from metaform import prompt_files
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    live_session(worked.id)
    item = json.loads(run('map', 'work', f'id={worked.id}', '--json', cwd=mapped).stdout)['map']['item']
    args = {'item': item}
    said = run('map', 'item', f'item={item}', cwd=mapped).stdout
    structured = json.loads(run('map', 'item', f'item={item}', '--json', cwd=mapped).stdout)
    call = {'tool': 'map_item', 'input': args,
            'result': {'content': [{'type': 'text', 'text': said}], 'structuredContent': structured, 'isError': False}}
    detail = {'tool_call_id': 't1', 'title': 'mcp__metaform__map_item', 'kind': 'other', 'status': 'completed',
              'diffs': [], 'locations': [], 'terminals': [], 'nodes': [], 'call': call}
    session = f's-{worked.id}'
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('session_lines', {'session_id': session, 'name': 'tool:t1', 'work_id': worked.id, 'kind': 'tool_call',
                            'text': 'mcp__metaform__map_item (completed)', 'seq': 1})
        tx.insert('session_lines', {'session_id': session, 'name': 'detail:t1', 'work_id': worked.id, 'kind': 'tool_detail',
                            'text': json.dumps(detail), 'seq': 2})
    other = tmp_path / 'other'
    other.mkdir()
    run('add', 'project', 'other', str(other))
    build(Store('other'))
    started(run)
    page, problems, _ = opened(browser, web)
    calls, sent = [], []
    page.on('request', lambda asked: calls.append(json.loads(asked.post_data or '{}'))
            if '/api/mcp-call' in asked.url else None)

    def taken(route):
        sent.append(json.loads(route.request.post_data))
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'sent': True}))
    page.route('**/api/dispatch-message', taken)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=10000)
    page.click('#agents .agent')
    view = page.frame_locator('#helpdesk .mcpapp iframe.appframe')
    view.locator('.row').first.wait_for(timeout=40000)
    assert 'a quieter tone' in view.locator('#item').inner_text()             # the call's own result, in the thread
    assert calls and all((one.get('work_id'), one.get('session')) == (worked.id, session) for one in calls)
    view.locator('.row').first.click()                                        # the person selects in the view
    page.wait_for_function('() => document.querySelector("#helpdesk .mcpapp .appnote")?.textContent'
                           '.includes("with your next message")', timeout=10000)
    frame = next(one for one in page.frames if '/api/mcp-app' in one.url)
    frame.evaluate('window.parent.postMessage({jsonrpc: "2.0", id: 99, method: "ui/download-file", params: {}}, "*")')
    page.wait_for_function('() => document.querySelector("#helpdesk .mcpapp .appnote").textContent'
                           '.includes("ui/download-file, which this chat does not offer")')
    page.fill('#helpdesk .say', 'Is that the one?')
    page.press('#helpdesk .say', 'Enter')
    for _ in range(50):
        if sent:
            break
        page.wait_for_timeout(100)
    line = prompt_files.module('mcp', 'view_selected', address=item)
    assert (sent[0]['work_id'], sent[0]['session']) == (worked.id, session)
    assert sent[0]['text'] == f'[From the Node view: {line}\n{{"address":"{item}"}}]\n\nIs that the one?'
    page.click('#helpdesk .mcpapp .appbar .btn')                              # Pop out
    page.frame_locator('.window.mcpwin iframe.appframe').locator('.row').first.wait_for(timeout=20000)
    assert 'Shown in a panel of its own' in page.locator('#helpdesk .mcpapp').inner_text()
    page.click('.window.mcpwin .bar .btn:has-text("Back into the chat")')
    view.locator('.row').first.wait_for(timeout=20000)
    assert page.locator('.window.mcpwin').count() == 0
    page.click('#helpdesk .mcpapp .appbar .btn')                              # out again, then the project is left
    page.wait_for_selector('.window.mcpwin iframe.appframe')
    page.select_option('#proj', 'other')
    page.wait_for_function('() => !document.querySelector("iframe.appframe") && !document.querySelector(".mcpwin")',
                           timeout=10000)
    assert problems == []


@pytest.mark.req('VIEW-039')
def test_a_queued_message_that_fails_puts_back_only_the_persons_words_and_keeps_the_views_context(
        run, home, web, mapped, browser, tmp_path):
    """code.interface.graphical#12e: what a view asked the agent be told goes with the person's next message, after
    the line naming their click. A queued message that the server refuses comes back to the box as the person typed
    it, with neither line, and the view's context is kept, so the resend carries it once and the message after none."""
    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually

    agent = Dispatch(run, home, mapped, tmp_path)
    agent.id = agent.store.add_work(agent.node, None, task='Conversation with the system agent', held=True).id
    agent.start('plain', 'system=true')
    try:
        session = agent.session().extra['session_id']
        eventually(lambda: agent.received('session/prompt'))
        started(run)
        page, problems, _ = opened(browser, web)
        page.route('**/api/system-chat', lambda route: route.fulfill(
            status=200, content_type='application/json', body=json.dumps(
                {'work_id': agent.id, 'session_id': session, 'agent': 'claude', 'state': 'running'})))
        refused = []

        def refuse_once(route):
            if refused:
                return route.continue_()
            refused.append(json.loads(route.request.post_data)['text'])
            route.fulfill(status=409, content_type='application/json',
                          body=json.dumps({'error': 'The agent did not take it.'}))
        page.route('**/api/dispatch-message', refuse_once)
        page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
        page.evaluate('''async thread => (await import('/page/app/session/apps.js')).MODEL_CONTEXT.set(thread,
            new Map([['Node view', 'The person selected code.alarm.audible.']]))''', f'{agent.id}:{session}')
        page.click('#dockTab')
        page.evaluate('''async () => (await import('/page/app/core/banner.js')).banner('test-retry',
            {tone: 'warn', title: 'The map was not read', actions: [{label: 'Read again', run: () => {}}]})''')
        page.click('.banner[data-key="test-retry"] .acts button')     # the click the line names
        asked = len(agent.received('session/prompt'))

        def prompts():
            return [' '.join(part.get('text', '') for part in one['params']['prompt'])
                    for one in agent.received('session/prompt')[asked:]]
        page.fill('#helpdesk .say', 'Is that the one?')
        page.press('#helpdesk .say', 'Enter')                         # no agent there yet: it waits, then is refused
        page.wait_for_function('() => document.querySelector("#helpdesk .say").value', timeout=20000)
        assert page.input_value('#helpdesk .say') == 'Is that the one?'
        told = (r'The person clicked, \d+ s before: [^\n]+\n\n'
                r'\[From the Node view: The person selected code\.alarm\.audible\.\]\n\nIs that the one\?$')
        assert len(refused) == 1 and re.match(told, refused[0]), refused
        page.press('#helpdesk .say', 'Enter')                         # sent again
        resent = eventually(lambda: next((one for one in prompts() if 'Is that the one?' in one), None))
        assert re.match(told, resent) and resent.count('[From the ') == 1, resent
        page.fill('#helpdesk .say', 'And the next?')                  # while the resend may still be going
        page.press('#helpdesk .say', 'Enter')
        after = eventually(lambda: next((one for one in prompts() if 'And the next?' in one), None))
        assert '[From the ' not in after and after.endswith('And the next?'), after   # the context was said once
        assert problems == ['Failed to load resource: the server responded with a status of 409 (Conflict)']
    finally:
        agent.close()
        for pid in agent.logged('pid'):
            end_group(pid)


@pytest.mark.req('VIEW-039')
def test_a_message_that_fails_after_its_project_was_left_gives_back_none_of_the_views_context(
        run, web, mapped, browser):
    """code.interface.graphical#137: a message taken a view's context, then the project left while it went, and then
    refused. Leaving tore those views down, so what they told is given back to no thread, even one the person returns
    to in the same project."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    assert page.evaluate('''async () => {
        const apps = await import('/page/app/session/apps.js');
        apps.MODEL_CONTEXT.set('w1:s1', new Map([['Node view', 'The person selected code.alarm.audible.']]));
        const taken = apps.takeContext({work: 'w1', session: 's1'});
        apps.leaveApps();
        apps.contextBack(taken);
        return [taken !== null, apps.MODEL_CONTEXT.size];
    }''') == [True, 0]
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-039')
def test_a_burst_of_thread_lines_is_drawn_in_few_reads_and_the_agent_window_only_appends(run, web, mapped, browser):
    """An agent streams about five lines a second, each announced. Redrawing for each one kept the page reading and
    refilled the agent window, so its lines flickered. A burst is read together, a line touches neither the merges nor
    the advice, and the lines already drawn stay the same nodes."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    live_session(worked.id)
    thread_line(worked.id, 1, 'The first line')
    payload = {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch',
               'dispatch_tables': ['dispatch.lines']}
    relay.deliver('map.changed', payload)
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=10000)
    page.click('#agents .agent')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("The first line")',
                           timeout=10000)
    page.wait_for_timeout(1000)  # the dock's own reads are done
    page.evaluate('() => { window.firstLine = document.querySelector("#helpdesk .log .bubble"); }')
    reads = []
    page.on('request', lambda sent: reads.append(sent.url.split('/api/')[1].split('?')[0]) if '/api/' in sent.url else None)
    for seq in range(2, 22):
        thread_line(worked.id, seq, f'Line number {seq}')
        relay.deliver('map.changed', payload)
    page.wait_for_function('() => document.querySelector("#helpdesk .log").innerText.includes("Line number 21")',
                           timeout=10000)
    page.wait_for_timeout(1000)  # any read still coming for the burst
    assert page.evaluate('() => document.querySelector("#helpdesk .log .bubble") === window.firstLine'), 'refilled'
    assert page.locator('#helpdesk .log .bubble').count() == 21
    assert 'merges' not in reads and 'advice' not in reads, reads
    assert reads.count('dispatch-sessions') <= 10, reads  # 40 or more when each line is read alone
    assert problems == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-044')
def test_the_chat_dock_stays_with_its_session_when_a_newer_session_of_the_ticket_starts(run, web, mapped, browser):
    """The dock showed the ticket's newest session, so a session started later on the same ticket swapped the
    conversation the person was having for another. The dock keeps the session it opened on."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    live_session(worked.id)
    thread_line(worked.id, 1, 'Our first conversation')
    payload = {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch',
               'work_ids': [worked.id], 'session_ids': [f's-{worked.id}'], 'kinds': ['session']}
    relay.deliver('map.changed', payload)
    page.wait_for_selector('#agents:not([hidden]) .agent-row button.chat', timeout=10000)
    page.click('#agents .agent-row button.chat')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent.includes("Our first conversation")',
                           timeout=10000)
    runner = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)', 'dispatch', 'run', worked.id])
    RUNNERS.append(runner)
    with Store('proj', module='dispatch').tables() as tx:  # a newer session of the same ticket
        tx.insert('agent_sessions', {'session_id': 'newer', 'work_id': worked.id, 'agent': 'claude', 'state': 'running',
                               'pid': runner.pid, 'port': dispatch_control_port(), 'token': 'newer',
                               'started': '2026-10-03T00:01:00Z', 'seq': 100000})
    thread_line(worked.id, 1, 'Another conversation', session='newer')
    relay.deliver('map.changed', {**payload, 'session_ids': ['newer']})
    page.wait_for_function('() => [...document.querySelectorAll("#agents .agent")]'
                           '.some(one => one.dataset.session === "newer")', timeout=10000)
    page.wait_for_timeout(1000)  # the dock's read for the same change
    log = page.locator('#helpdesk .log').text_content()
    assert 'Our first conversation' in log and 'Another conversation' not in log, log
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_each_open_chat_is_a_tab_in_the_dock_and_closing_keeps_the_threads(run, web, mapped, browser):
    """Several agents can be talked with at once, sentinels among them; the dock keeps each conversation as a tab,
    switching shows that one's thread, and closing preserves every thread and session."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    first = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    second = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a longer tone')
    for worked, words in ((first, 'About the quieter tone'), (second, 'About the longer tone')):
        store.take_work(worked.id, by='claude')
        live_session(worked.id)
        thread_line(worked.id, 1, words)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    relay.deliver('map.changed', {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch'})
    page.wait_for_function('() => document.querySelectorAll("#agents .agent-row button.chat").length === 2',
                           timeout=10000)
    for index in (0, 1):
        page.locator('#agents .agent-row button.chat').nth(index).click()
    # My agent first and pinned, then each agent's thread
    page.wait_for_function('() => document.querySelectorAll("#helpdesk .tabs .tab").length === 3', timeout=10000)
    assert page.locator('#helpdesk .tabs .tab').first.text_content() == 'My agent'
    shown = lambda: page.locator('#helpdesk .log').text_content()
    page.wait_for_function('() => /About the (quieter|longer) tone/.test(document.querySelector("#helpdesk .log").textContent)')
    on_view = 'About the longer tone' if 'About the longer tone' in shown() else 'About the quieter tone'
    page.locator('#helpdesk .tabs .tabpair .tab:not(.on)').click()
    other = ({'About the longer tone', 'About the quieter tone'} - {on_view}).pop()
    page.wait_for_function(f'() => document.querySelector("#helpdesk .log").textContent.includes("{other}")')
    assert on_view not in shown()
    page.click('#helpdesk .close')
    page.wait_for_selector('#helpdesk', state='hidden')
    page.click('#dockTab')
    assert page.locator('#helpdesk .tabs .tab').count() == 3
    assert other in shown()
    page.locator('#helpdesk .tabs .tabpair .tab:not(.on)').click()
    page.wait_for_function(f'() => document.querySelector("#helpdesk .log").textContent.includes("{on_view}")')
    # Escape on an agent's thread goes back to My agent: no system agent runs, so it is ready to Call
    asked = []
    page.on('request', lambda sent: asked.append(sent.url) if '/api/' in sent.url else None)
    page.focus('#helpdesk .say')
    page.keyboard.press('Escape')
    page.wait_for_selector('#helpdesk .tabs .tab.mine.on', timeout=10000)
    assert page.locator('#helpdesk').is_visible() and page.locator('#helpdesk .call').is_visible()
    assert on_view not in shown() and other not in shown()
    # the × closes a thread on this page only; the one on view gives way to My agent
    page.locator('#helpdesk .tabs .tabpair .tab').first.click()
    page.wait_for_selector('#helpdesk .tabs .tabpair.on', timeout=10000)
    page.locator('#helpdesk .tabs .tabpair.on .tabx').click()
    page.wait_for_selector('#helpdesk .tabs .tab.mine.on', timeout=10000)
    assert page.locator('#helpdesk .tabs .tabpair').count() == 1
    page.locator('#helpdesk .tabs .tabpair .tabx').click()
    page.wait_for_selector('#helpdesk .tabs', state='hidden')
    assert not any('/api/dispatch-stop' in url or '/api/dispatch-cancel' in url for url in asked), asked
    page.wait_for_timeout(500)
    assert page.locator('#agents .agent-row').count() == 2  # both agents keep working
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_the_full_size_dock_lists_its_agents_with_their_tasks_and_a_step_updates_its_row(run, web, mapped, browser):
    """At full size the dock lists My agent and each running agent down its left, each row with its ticket's item, title
    and steps done of planned; a click opens that agent's thread, a step it reports updates its row from the live
    stream, and back at its size the list goes and the tabs do its job."""
    from metaform import relay
    from metaform.data import Store
    store = Store('proj')
    run('enable', 'dispatch')
    for title, words in (('A quieter tone', 'About the quieter tone'), ('A longer tone', 'About the longer tone')):
        run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'condition=broken', f'task={title.lower()}',
            f'title={title}', cwd=mapped)
        worked = next(one for one in store.work(open=True, limit=0).results if one.task == title.lower())
        store.take_work(worked.id, steps=3, by='claude')
        live_session(worked.id)
        thread_line(worked.id, 1, words)
    second = worked
    started(run)
    page, problems, _ = opened(browser, web)
    page.set_viewport_size({'width': 1600, 'height': 900})
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    relay.deliver('map.changed', {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch'})
    page.wait_for_function('() => document.querySelectorAll("#agents .agent-row button.chat").length === 2',
                           timeout=10000)
    page.locator('#agents .agent-row button.chat').first.click()
    page.wait_for_selector('#helpdesk .tabs .tabpair', timeout=10000)
    assert page.locator('#helpdesk .agentlist').is_hidden()
    page.click('#helpdesk .big')
    page.wait_for_selector('#helpdesk .agentlist .agentrow', timeout=10000)
    assert page.locator('#helpdesk .tabs').is_hidden()
    rows = page.locator('#helpdesk .agentlist .agentrow')
    assert rows.count() == 3 and rows.first.inner_text().startswith('My agent')
    row = f'#helpdesk .agentlist .agentrow[data-session="s-{second.id}"]'
    said = page.locator(row).inner_text()
    assert 'code.alarm.audible#' in said and 'A longer tone' in said and '0 of 3 steps' in said, said
    page.click(row)
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent.includes("longer tone")')
    page.wait_for_selector(f'{row}.on', timeout=5000)
    run('map', 'work', 'op=step', f'id={second.id}', 'said=Found the tone.', cwd=mapped)
    page.wait_for_function(f'() => document.querySelector(\'{row}\')?.innerText.includes("1 of 3 steps")',
                           timeout=15000)
    page.click('#helpdesk .big')
    page.wait_for_selector('#helpdesk .agentlist', state='hidden')
    assert page.locator('#helpdesk .tabs').is_visible()
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_the_system_agent_started_elsewhere_opens_as_the_system_agent_and_closing_preserves_its_thread(
        run, web, mapped, browser):
    """A system agent the page did not start, by the phone, `dispatch system` or before a reload, opened as an agent at
    work with a spend box. What its session is about says what it is: it opens as the system agent, and since the page
    did not summon it, closing hides its thread and leaves it running; /fork there forks its session. The person's chat
    about a node hangs on the same held ticket and keeps its name and its chip, however it is opened again."""
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    system = store.add_work(Node('element', 'code.alarm.audible'), None, task='Conversation with the system agent',
                            held=True)
    live_session(system.id)
    with Store('proj', module='dispatch').tables() as tx:  # a node's conversation, run by the same kind of runner
        row = dict(tx.get('agent_sessions', {'session_id': f's-{system.id}'}) or {})
        tx.insert('agent_sessions', {**row, 'session_id': 's-node', 'seq': int(row['seq']) + 1})
        for session, about in ((f's-{system.id}', 'system'), ('s-node', 'node:code.alarm.audible')):
            tx.insert('session_lines', {'session_id': session, 'name': 'state', 'work_id': system.id, 'kind': 'state',
                                'seq': 1, 'text': json.dumps({'about': about})})
    alarm = store.element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    threads = lambda: page.evaluate('window.metaform.dock().threads')
    page.evaluate(f'window.metaform.agent("{system.id}", "s-{system.id}")')
    page.wait_for_function('() => window.metaform.dock().threads[0]?.source === "system"', timeout=10000)
    assert threads()[0]['label'] == 'your system agent', threads()
    page.wait_for_timeout(500)  # the spend box is drawn with the thread
    assert page.locator('#helpdesk .spend').is_hidden()
    forked = []  # /fork asks for a fork of the session on view, its words the fork's first turn
    page.route('**/api/dispatch-fork', lambda route: forked.append(route.request.post_data_json) or route.fulfill(
        status=200, content_type='application/json', body='{}'))
    page.fill('#helpdesk .say', '/fork  what else did you consider?')
    page.press('#helpdesk .say', 'Enter')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent'
                           '.includes("The fork was made; its thread is under Subagents.")', timeout=10000)
    assert [{key: one.get(key) for key in ('work_id', 'session', 'text')} for one in forked] == [
        {'work_id': system.id, 'session': f's-{system.id}', 'text': 'what else did you consider?'}], forked
    asked = []
    page.on('request', lambda sent: asked.append(sent.url) if '/api/' in sent.url else None)
    page.click('#helpdesk .close')
    page.wait_for_selector('#helpdesk', state='hidden')
    assert threads()[0]['session'] == f's-{system.id}'
    assert not any('/api/dispatch-stop' in url for url in asked), asked
    # Chat about the node: its conversation hangs on the held ticket; the start is answered here, no agent is run
    page.route('**/api/talk', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps(
        {'work_id': system.id, 'session_id': 's-node', 'agent': 'claude', 'state': 'running', 'conversation': True})))
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.chat')
    page.wait_for_function('() => window.metaform.dock().threads.some(one => one.session === "s-node")', timeout=10000)
    chat = next(one for one in threads() if one['session'] == 's-node')
    assert chat['source'] == 'conversation', chat
    page.evaluate(f'window.metaform.agent("{system.id}", "s-node")')  # as an attention card or its figure opens it
    page.wait_for_timeout(1000)  # its thread is read, and what it is about is said there
    assert next(one for one in threads() if one['session'] == 's-node') == chat, threads()
    assert problems == []


@pytest.mark.req('VIEW-045')
@pytest.mark.req('LAYER-029')
def test_the_box_beside_an_agent_shows_the_part_its_work_is_using_in_white_and_unchecked_hides_it(
        run, web, mapped, browser):
    """What sections of the map are in use is worth seeing: checked beside the agent, what its work reserves, the
    node it is on and the rest of its work claim, is white; unchecked, it is hidden while the rest is reviewed."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone')
    store.take_work(worked.id, by='claude')
    live_session(worked.id)
    run('dispatch', 'claim', 'Quieter alarm', 'nodes=["code.alarm.audible", "code.timer.kitchen"]',
        f'work=["{worked.id}"]', cwd=mapped)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    relay.deliver('map.changed', {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch'})
    page.wait_for_selector('#agents:not([hidden]) .agent-row input.inuse', timeout=10000)
    assert page.locator('#agents .agent-row input.inuse').is_checked()
    page.wait_for_function('() => document.querySelectorAll(".map2d .node.inuse").length === 2', timeout=10000)
    page.locator('#agents .agent-row input.inuse').uncheck()
    page.wait_for_function('() => document.querySelectorAll(".map2d .node.reserved").length === 2'
                           ' && !document.querySelector(".map2d .node.inuse")')
    assert not page.locator('.map2d .node.reserved').first.is_visible()
    page.locator('#agents .agent-row input.inuse').check()
    page.wait_for_function('() => document.querySelectorAll(".map2d .node.inuse").length === 2'
                           ' && !document.querySelector(".map2d .node.reserved")')
    assert problems == []


@pytest.mark.req('VIEW-045')
@pytest.mark.req('LAYER-029')
def test_a_sentinels_proposal_shows_what_it_reserves_and_shows_its_reach_on_the_map_in_white(run, web, mapped, browser):
    """A proposal is more than a button: in the sentinel's chat it shows its grounds, benefit and trade-off, how much
    of the map it reserves, and Show on the map paints its reach white."""
    import time as clock

    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    issue = store.add_work(Node('element', 'code.alarm.audible'), None, task='Issue raised by the person: too loud')
    live_session(issue.id)
    proposal = {'title': 'Lower the gain', 'grounds': 'alarm.c:12 sets 0 dB', 'disruption': 'the alarm and the timer',
                'reach': ['code.alarm.audible', 'code.timer.kitchen'], 'benefit': 'quieter at once',
                'tradeoff': 'the timer is held while it is built'}
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('proposals', {'issue': issue.id, 'text': json.dumps([proposal]), 'seq': clock.time_ns()})
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    relay.deliver('map.changed', {'project': 'proj', 'base_id': store.active_base().id, 'tables': 'dispatch'})
    page.wait_for_selector('#agents:not([hidden]) .agent-row button.chat', timeout=10000)
    page.click('#agents .agent-row button.chat')
    page.wait_for_selector('#helpdesk .proposals:not([hidden]) .proposal', timeout=10000)
    card = page.locator('#helpdesk .proposal').inner_text()
    total = len(store.graph(limit=0).elements)
    assert 'Lower the gain' in card and f'Reserves 2 of {total} parts' in card and 'quieter at once' in card
    page.click('#helpdesk .proposal button.reach')
    page.wait_for_function('() => document.querySelectorAll(".map2d .node.inuse").length === 2')
    assert page.locator('#helpdesk .proposal button.reach').text_content() == 'Hide from the map'
    assert problems == []


@pytest.mark.req('VIEW-001')
def test_the_side_column_and_its_split_are_dragged_to_size_kept_and_reset(run, web, mapped, browser):
    """The panes are resized by hand: the side column's width and the split between its small map and its panes are
    dragged, kept by the browser across a reload, and put back by a double-click."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    width = lambda: page.locator('aside').bounding_box()['width']
    height = lambda: page.locator('#small').bounding_box()['height']
    before = (width(), height())
    handle = page.locator('#sideSplit').bounding_box()
    middle = handle['y'] + handle['height'] / 2  # the edge is grabbed halfway down the column
    # the side column opens on the right by default: its edge is dragged away from it, to the left, to widen it
    side = -1 if page.evaluate("document.querySelector('.app').classList.contains('side-right')") else 1
    page.mouse.move(handle['x'] + 4, middle)
    page.mouse.down()
    page.mouse.move(handle['x'] + 4 + 150 * side, middle, steps=5)
    page.mouse.up()
    split = page.locator('#smallSplit').bounding_box()
    page.mouse.move(split['x'] + 100, split['y'] + 3)
    page.mouse.down()
    page.mouse.move(split['x'] + 100, split['y'] - 80, steps=5)
    page.mouse.up()
    dragged = (width(), height())
    assert dragged[0] > before[0] + 100 and dragged[1] < before[1] - 50, (before, dragged)
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    assert abs(width() - dragged[0]) < 3 and abs(height() - dragged[1]) < 3  # kept by this browser
    page.dblclick('#sideSplit')
    page.dblclick('#smallSplit')
    assert abs(width() - before[0]) < 3 and abs(height() - before[1]) < 3  # and put back
    assert problems == []


@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-018')
def test_an_intake_started_in_another_project_takes_the_page_there_and_it_follows_the_intake(
        run, web, mapped, browser, tmp_path, dispatch_runners):
    """An intake was followed only in the project the page had open: one started in another project went unseen.
    The page goes to the project where an intake agent starts, at its launch, not its first record, which may be
    minutes later (UX review round 2, 2026-10-17, new-project-intake F3), and follows it, once for that intake."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    assert page.evaluate('location.hash') == '#p=proj'
    folder = tmp_path / 'other'  # registered after the page opened, as a first run registers the folder
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    page.wait_for_function('() => [...document.querySelectorAll("#proj option")].some(o => o.value === "other")',
                           timeout=5000)  # the chooser lists it at once, VIEW-002
    assert page.evaluate('location.hash') == '#p=proj', 'a registration alone moves no page'
    agent = intake_agent(run, folder, tmp_path / 'fake.jsonl', dispatch_runners)
    page.wait_for_function('() => location.hash === "#p=other"', timeout=5000)  # before anything is recorded
    page.wait_for_selector('#intakeBar:not([hidden])', timeout=10000)
    run('intake', 'start', cwd=folder, env=agent)
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=folder, env=agent)
    page.wait_for_function('() => window.metaform.live() !== null', timeout=20000)
    page.wait_for_function('() => window.metaform.drawn() && window.metaform.drawn().nodes === 1', timeout=15000)
    assert page.locator('#proj').input_value() == 'other'  # the project list has it, chosen
    assert problems == []


@pytest.mark.req('VIEW-019')
def test_a_page_opened_with_no_project_follows_the_first_run_intake_without_a_reload(
        run, home, web, browser, tmp_path, dispatch_runners):
    """On a first run the page was opened before the folder was registered, said no project is registered, and had to be
    reloaded again and again until the intake showed. It now hears the intake start and goes to it."""
    started(run)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.goto(f'http://127.0.0.1:{web}/')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("No project is registered")')
    folder = tmp_path / 'fresh'
    folder.mkdir()
    run('add', 'project', 'fresh', str(folder))
    agent = intake_agent(run, folder, tmp_path / 'fake.jsonl', dispatch_runners)
    page.wait_for_function('() => location.hash === "#p=fresh"', timeout=10000)
    run('intake', 'start', cwd=folder, env=agent)
    run('intake', 'element', 'code.timer.kitchen', 'role=DE', cwd=folder, env=agent)
    page.wait_for_function('() => window.metaform.live() !== null', timeout=20000)
    page.wait_for_function('() => window.metaform.drawn() && window.metaform.drawn().nodes === 1', timeout=15000)
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_my_agent_never_opens_the_intake_nor_calls_it_your_system_agent(run, web, mapped, browser, tmp_path,
                                                                      dispatch_runners):
    """UX review round 2, 2026-10-17 (combined F3): with only an intake agent running, My agent opened a chat titled
    "Your system agent" over the intake's thread, so a message meant for the person's own agent went to the intake.
    The intake is told apart by what it is: My agent opens no thread of it, and the Agents menu calls it the intake."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    intake_agent(run, mapped, tmp_path / 'fake.jsonl', dispatch_runners)
    page.wait_for_selector('#intakeBar:not([hidden])', timeout=15000)
    page.evaluate("() => import('/page/app/dock/threads.js').then(part => part.showMine())")
    page.wait_for_timeout(500)
    head = page.inner_text('#helpdesk')
    assert 'The intake of' not in head and 'intake' not in page.evaluate(
        "() => import('/page/app/dock/embody.js').then(part => String(part.DOCK.target || ''))"), head
    menu = page.evaluate("() => import('/page/app/dock/threads.js').then(part => "
                         "import('/page/app/agents/dispatch.js').then(dispatch => dispatch.D.sessions.map("
                         "one => part.sessionTask(one))))")
    assert 'Conversation with your system agent' not in menu and 'The intake' in menu, menu
    assert problems == []


@pytest.mark.req('VIEW-018')
def test_a_burst_of_changes_in_another_project_that_concern_no_intake_makes_the_page_read_nothing(
        run, web, mapped, browser, tmp_path):
    """CLAUDE.md section 2, rule 5, for the page's handlers of other projects' changes (UX review round 2, 2026-10-17,
    new-project-intake F1): its tickets, its bases and its registration decide nothing from a read; only the chooser
    is read again for a registration, once."""
    from metaform.data import Store
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    folder = tmp_path / 'quiet'
    folder.mkdir()
    asked = []
    page.on('request', lambda request: asked.append(request.url) if '/api/' in request.url else None)
    run('add', 'project', 'quiet', str(folder))
    page.wait_for_function('() => [...document.querySelectorAll("#proj option")].some(o => o.value === "quiet")',
                           timeout=5000)
    store = Store('quiet')
    store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.timer.kitchen')
    for number in range(10):  # its tickets, each its own command and its own event
        run('map', 'work', 'op=add', 'node=element:code.timer.kitchen', f'title=Ticket {number}', 'task=Do it',
            cwd=folder)
    run('map', 'add-base', 'other', '--confirm', cwd=folder)
    page.wait_for_timeout(1500)
    assert [url for url in asked if 'project=quiet' in url or '/api/intake-recording' in url] == [], asked
    assert len([url for url in asked if '/api/projects' in url]) == 1, asked
    assert page.evaluate('location.hash') == '#p=proj' and problems == []


# An agent's harness talking to Metaform's MCP server over stdio, as the person's own AI tool does: it starts the
# intake and holds it, recording nothing, until its standard input closes. The first call to a tool in a session may
# answer with how to use it, so intake_start is called twice.
HOLDING_INTAKE = """import asyncio, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    params = StdioServerParameters(command=sys.executable, args=['-m', 'metaform', 'mcp', 'serve'], cwd=sys.argv[1],
                                   env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for _ in range(2):
                await session.call_tool('intake_start', {})
            print('started', flush=True)
            await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)
asyncio.run(main())
"""


@pytest.mark.req('VIEW-018')
def test_an_intake_an_agent_starts_over_mcp_in_another_project_takes_the_page_there_before_its_first_record(
        run, web, mapped, browser, tmp_path):
    """UX review round 2, 2026-10-17 (new-project-intake F1): an agent's intake_start in a new project sends the
    project's bases changing, then its recorder, in one burst; the page was busy reading for the first and threw the
    second away, so it went there only at the agent's first record, minutes later with a real agent. It filters first
    and keeps what comes while it reads, so it goes there with nothing recorded."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    folder = tmp_path / 'gamma'
    folder.mkdir()
    run('add', 'project', 'gamma', str(folder))
    agent = subprocess.Popen([sys.executable, '-c', HOLDING_INTAKE, str(folder)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)
    try:
        assert agent.stdout is not None and agent.stdout.readline().strip() == 'started'
        page.wait_for_function('() => location.hash === "#p=gamma"', timeout=5000)
    finally:
        assert agent.stdin is not None
        agent.stdin.close()
        agent.wait(30)
    assert problems == []


@pytest.mark.req('VIEW-002')
@pytest.mark.req('CLI-041')
def test_metaform_start_in_a_new_folder_takes_an_open_page_there_at_once(run, web, mapped, browser, tmp_path):
    """UX review round 2, 2026-10-17 (new-project-intake F2): metaform start in a new folder registered it and said
    "the page shows the project meanwhile", while the open page went on showing another project with the new one not
    even listed, and a reload kept the address it showed. Registration and the project opened are announced as such,
    before any intake agent is launched, and every open page goes there."""
    run('enable', 'dispatch')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    folder = tmp_path / 'beta'
    folder.mkdir()
    (folder / 'notes.txt').write_text('A small project.\n', encoding='utf-8')
    shown = run('start', cwd=folder, env={'PATH': os.path.dirname(sys.executable)}).stdout  # no AI tool on PATH
    assert 'Project: beta, registered' in shown and 'Intake: not started' in shown, shown
    page.wait_for_function('() => location.hash === "#p=beta"', timeout=5000)
    assert page.locator('#proj').input_value() == 'beta'
    page.wait_for_selector('#emptyStage:not([hidden])', timeout=15000)  # its empty map, with Start the intake
    assert problems == []


@pytest.mark.req('VIEW-002')
def test_a_folder_is_mapped_from_the_page_and_the_intake_window_opens_on_it(run, web, mapped, browser, tmp_path):
    """UX review round 2, 2026-10-17 (new-project-intake, PROPOSED-VIEW-D): the page had no way to begin a new
    project. Map a folder…, under Administration, registers a folder, named as metaform start names it, goes to it and
    opens the intake window; one that does not exist is refused in place."""
    from metaform import home as metaform_home
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    folder = tmp_path / 'Kitchen Timer'
    folder.mkdir()
    page.click('#adminBtn')
    page.click('#mapFolderBtn')
    page.wait_for_selector('#clearbox:not([hidden]) input.folderpath')
    page.fill('#clearbox input.folderpath', str(tmp_path / 'missing'))
    page.click('#clearbox button:has-text("Map it")')
    page.wait_for_selector('#clearbox p.next:not([hidden])')
    assert 'No folder at' in page.inner_text('#clearbox p.next')
    page.fill('#clearbox input.folderpath', str(folder))
    page.click('#clearbox button:has-text("Map it")')
    page.wait_for_function('() => location.hash === "#p=kitchen-timer"', timeout=10000)
    page.wait_for_selector('#intake:not([hidden])', timeout=10000)
    assert metaform_home.folder_project(folder) == 'kitchen-timer'
    assert [one.project_id for one in metaform_home.projects()].count('kitchen-timer') == 1
    assert [one for one in problems if 'status of 400' not in one] == [], 'the missing folder\'s refusal alone'


def newcomer(browser):
    """A page in a browser of its own, as a person opening the web GUI for the first time has: nothing dismissed in it."""
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    page.set_default_timeout(10_000)
    problems = []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    return context, page, problems


def welcome_shown(page):
    """Whether the first-time welcome is on view."""
    return page.evaluate('() => !document.querySelector("#welcome").hidden')


def help_opens(page, opener):
    """The help window opens from `opener`, the same one the View menu's Keyboard shortcuts opens, and closes again."""
    page.click(opener)
    page.wait_for_selector('#help', state='visible')
    assert page.inner_text('#help .title') == 'Keyboard shortcuts' and page.locator('#help .keyrow').count() > 0
    page.click('#help .close')
    page.wait_for_selector('#help', state='hidden')


@pytest.mark.req('VIEW-002')
def test_a_first_time_person_gets_one_plain_welcome_once_and_a_returning_person_none(run, home, web, browser, tmp_path):
    """A person opening the page for the first time, on the one project their AI tool mapped, gets one small plain
    welcome over a page that stays usable: what Metaform is, and that help is a ? away, which opens the help, as the
    header's Help does. It stands clear of the agents list and the intake bar. OK closes it for good, so a reload never
    brings it back; Help › Getting started shows it again. Someone who has used Metaform before gets none."""
    started(run)
    folder = tmp_path / 'live'
    folder.mkdir()
    run('add', 'project', 'live', str(folder))
    run('intake', 'start', cwd=folder)                                  # as the agent in their AI tool maps it
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', cwd=folder)
    run('intake', 'finish', cwd=folder)
    context, page, problems = newcomer(browser)
    page.goto(f'http://127.0.0.1:{web}/#p=live')
    page.wait_for_selector('#welcome', state='visible', timeout=90000)
    assert page.inner_text('#welcome .title') == 'Welcome'
    said = page.inner_text('#welcome .body')
    assert 'Metaform shows your project as a living map that your agents work on' in said
    assert 'Help can be found by pressing ?' in said
    assert page.locator('#welcome button').count() == 2                 # the ? and OK, and nothing else
    assert page.is_hidden('#scrim') and not page.evaluate('document.querySelector(".app").inert')
    page.evaluate('''() => { for (const id of ['agents', 'intakeBar']) document.getElementById(id).hidden = false;
        document.getElementById('intakeBar').textContent = 'Intake · Claude Code — Waiting for the first record'; }''')
    assert page.evaluate('''() => ['#agents', '#intakeBar'].filter(s => {
        const a = document.querySelector('#welcome').getBoundingClientRect(), b = document.querySelector(s).getBoundingClientRect();
        return b.width && b.height && a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom; })''') == []
    page.evaluate('''() => { for (const id of ['agents', 'intakeBar']) document.getElementById(id).hidden = true; }''')
    page.wait_for_selector('#map2d svg g.node')
    node = page.locator('#map2d svg g.node').first.bounding_box()      # the map beside the welcome takes a click
    page.mouse.click(node['x'] + node['width'] / 2, node['y'] + node['height'] / 2)
    page.wait_for_function('() => window.metaform.selected() !== null')
    help_opens(page, '#welcome .helpkey')                               # the ? opens the help
    help_opens(page, '#helpBtn')                                        # and so does the header's Help
    assert welcome_shown(page)                                          # only OK puts it away
    page.click('#welcome .ok')
    page.wait_for_selector('#welcome', state='hidden')
    assert api(web, '/api/hints')[1] == {'dismissed': ['newcomer', 'welcome']}
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=90000)
    page.wait_for_timeout(2500)                                         # time for a welcome that should not come
    assert not welcome_shown(page)
    page.click('#helpBtn')                                              # Help › Getting started shows it again
    page.click('#help .getstarted')
    page.wait_for_selector('#welcome', state='visible')
    assert page.is_hidden('#help')
    page.click('#welcome .ok')
    page.wait_for_selector('#welcome', state='hidden')
    assert problems == [], problems
    context.close()
    (home / 'web' / 'hints.json').unlink()                              # someone new to this home, who has used
    run('add', 'project', 'other', str(tmp_path))                      # Metaform before: two projects
    context, page, problems = newcomer(browser)
    page.goto(f'http://127.0.0.1:{web}/#p=live')
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=90000)
    page.wait_for_timeout(2500)
    assert not welcome_shown(page) and api(web, '/api/hints')[1] == {'dismissed': ['returning']}
    help_opens(page, '#helpBtn')
    assert problems == [], problems
    context.close()


@pytest.mark.req('VIEW-018')
def test_a_change_that_adds_or_removes_no_node_redraws_the_3d_map_in_place_without_starting_its_layout_again(
        run, web, mapped, browser):
    """Handing the 3D map new data starts its force layout again at full strength, which shook the whole map at every
    change, an agent taking a ticket among them. A change that adds or removes no node or link redraws what is drawn
    in place; one that adds a node lays it out."""
    from metaform.data import Store
    run('enable', 'hello')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    alarm = Store('proj').element('code.alarm.audible').id
    layouts = page.evaluate('window.metaform.layouts()')
    drawn = page.evaluate('window.metaform.drawn()')
    changes = page.evaluate('window.metaform.changes()')
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=broken', 'note=too loud', 'title=too loud',
        cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {changes} && window.metaform.loaded()', timeout=15000)
    page.wait_for_function(f'() => window.metaform.drawnWork("{alarm}") === 1', timeout=15000)  # the ticket's light
    assert page.evaluate('window.metaform.drawn()') == drawn
    assert page.evaluate('window.metaform.layouts()') == layouts
    run('hello', 'greet', 'world', cwd=mapped)
    page.click('#layersBtn')
    page.wait_for_selector('#layerlist input[data-layer="hello.greetings"]', timeout=15000)
    set_layer(page, 'hello.greetings', True)
    page.wait_for_function(f'() => window.metaform.drawn().nodes > {drawn["nodes"]}', timeout=10000)
    assert page.evaluate('window.metaform.layouts()') > layouts           # a new node is laid out
    assert problems == []


@pytest.mark.req('VIEW-008')
def test_down_goes_to_the_child_drawn_closest_below_and_not_to_the_first(run, web, mapped, browser):
    """With seven nodes below, Down goes down the edge to the one drawn nearest under the selected node, about the
    middle one, so the walk does not swing to the far left; Left and Right still go across the same row."""
    from metaform.data import Store
    from metaform.modules.web import view
    view.keep(view.OWNER, 'web_map_direction', 'down')
    store = Store('proj')
    for n in range(1, 8):
        store.add_element('notes', f'code.alarm.audible.tone{n}', name_length=1)
        store.add_join('notes', 'code.alarm.audible', f'code.alarm.audible.tone{n}', purpose=f'Ring tone {n}.',
                       ef=f'Plays tone {n}.')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    _, at = keys_of(web)
    alarm = at['code.alarm.audible']
    tones = [at[f'code.alarm.audible.tone{n}'] for n in range(1, 8)]
    page.evaluate(f'window.metaform.select("{alarm}")')
    drawn = page.evaluate('ids => ids.map(id => window.metaform.at2d(id))', [alarm, *tones])
    vertical = page.evaluate('window.metaform.vertical()')
    across = 'x' if vertical else 'y'
    here, below = drawn[0], dict(zip(tones, drawn[1:]))
    nearest = min(tones, key=lambda tone: abs(below[tone][across] - here[across]))
    order = sorted(tones, key=lambda tone: below[tone][across])
    assert order.index(nearest) not in (0, 6), (order.index(nearest), drawn)   # not an end of the row
    page.keyboard.press('ArrowDown')
    assert page.evaluate('window.metaform.selected()') == nearest
    page.keyboard.press('ArrowRight')
    assert page.evaluate('window.metaform.selected()') == order[order.index(nearest) + 1]
    page.keyboard.press('ArrowUp')
    assert page.evaluate('window.metaform.selected()') == alarm
    assert problems == []


@pytest.mark.req('VIEW-008')
def test_left_and_right_past_the_end_of_a_row_go_on_to_the_next_parents_nodes_on_that_level(run, web, mapped, browser):
    """At the end of one parent's nodes, Right goes on to the nodes of the next parent over on the same level, and Left
    the same way back, so no node of a level is out of reach; Up then goes to the parent of the node reached."""
    from metaform.data import Store
    from metaform.modules.web import view
    view.keep(view.OWNER, 'web_map_direction', 'down')
    store = Store('proj')
    store.add_element('notes', 'code.light.flash', name_length=2)
    store.add_join('notes', 'code.timer.kitchen', 'code.light.flash', purpose='Show it is done.', ef='Flashes.')
    for parent, leaf in (('code.alarm.audible', 'tone'), ('code.light.flash', 'blink')):
        for n in (1, 2, 3):
            store.add_element('notes', f'{parent}.{leaf}{n}', name_length=1)
            store.add_join('notes', parent, f'{parent}.{leaf}{n}', purpose=f'{leaf} {n}.', ef=f'Does {leaf} {n}.')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    _, at = keys_of(web)
    alarm, light = at['code.alarm.audible'], at['code.light.flash']
    kids = {alarm: [at[f'code.alarm.audible.tone{n}'] for n in (1, 2, 3)],
            light: [at[f'code.light.flash.blink{n}'] for n in (1, 2, 3)]}
    axis = 'x' if page.evaluate('window.metaform.vertical()') else 'y'
    where = lambda id: page.evaluate(f'window.metaform.at2d("{id}")')[axis]
    left, right = sorted((alarm, light), key=where)
    edge = max(kids[left], key=where)                      # the last node of the left parent's row
    page.evaluate(f'window.metaform.select("{left}")')
    page.keyboard.press('ArrowDown')
    while page.evaluate('window.metaform.selected()') != edge:
        page.keyboard.press('ArrowRight')
    page.keyboard.press('ArrowRight')                      # past the end of the row
    reached = page.evaluate('window.metaform.selected()')
    assert reached in kids[right], (reached, kids)
    row = sorted(kids[right], key=where)
    while reached != row[0]:                               # Left now walks the right parent's row
        page.keyboard.press('ArrowLeft')
        assert page.evaluate('window.metaform.selected()') == row[row.index(reached) - 1]
        reached = row[row.index(reached) - 1]
    page.keyboard.press('ArrowLeft')                       # and past its left end, back across
    assert page.evaluate('window.metaform.selected()') == edge
    page.keyboard.press('ArrowRight')
    page.keyboard.press('ArrowUp')
    assert page.evaluate('window.metaform.selected()') == right
    assert problems == []


@pytest.mark.req('VIEW-008')
def test_past_the_end_of_a_row_the_node_drawn_beside_is_reached_whatever_level_its_parent_hangs_from(run, web, mapped, browser):
    """A node drawn on the same row as the selected one is reached by Left or Right even when its parent hangs from
    another branch of the tree, here a root of its own, so what is drawn side by side is never out of reach."""
    from playwright.sync_api import TimeoutError as Waited

    from metaform.data import Store
    from metaform.modules.web import view
    view.keep(view.OWNER, 'web_map_direction', 'down')
    store = Store('proj')
    for address in ('code.alarm.audible.tone1', 'code.alarm.audible.tone1.pitch', 'code.panel', 'code.panel.cover',
                    'code.panel.cover.latch'):
        store.add_element('notes', address, name_length=1)
    for receiver, provider in (('code.alarm.audible', 'code.alarm.audible.tone1'),
                               ('code.alarm.audible.tone1', 'code.alarm.audible.tone1.pitch'),
                               ('code.panel', 'code.panel.cover'), ('code.alarm.audible', 'code.panel.cover'),
                               ('code.panel.cover', 'code.panel.cover.latch')):
        store.add_join('notes', receiver, provider, purpose=f'Needs {provider}.', ef=f'Gives {provider}.')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    _, at = keys_of(web)
    tone, pitch, cover, latch = (at[a] for a in ('code.alarm.audible.tone1', 'code.alarm.audible.tone1.pitch',
                                                 'code.panel.cover', 'code.panel.cover.latch'))
    depth = 'y' if page.evaluate('window.metaform.vertical()') else 'x'
    assert abs(page.evaluate(f'window.metaform.at2d("{pitch}")')[depth]
               - page.evaluate(f'window.metaform.at2d("{latch}")')[depth]) < 2   # drawn on one row
    selected = lambda key, limit=5000: page.wait_for_function(
        f'() => window.metaform.selected() === "{key}"', timeout=limit)
    for key in ('ArrowRight', 'ArrowLeft'):
        page.evaluate(f'window.metaform.select("{tone}")')
        selected(tone)
        page.keyboard.press('ArrowDown')
        selected(pitch)
        page.keyboard.press(key)
        try:
            selected(latch, 2000)
            break
        except Waited:  # this way round reached another node; the other key is tried
            continue
    else:
        raise AssertionError('the latch drawn beside the pitch was not reached by Left or Right')
    page.keyboard.press('ArrowUp')
    selected(cover)
    assert problems == []


@pytest.mark.req('VIEW-032')
@pytest.mark.req('VIEW-039')
def test_a_task_can_be_created_and_started_in_acp_from_its_editor(run, web, mapped, browser, tmp_path, watch_dispatch):
    from metaform.data import Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.task("{alarm}")')
    page.fill('#task .text', 'Inspect the alarm and report what you find.')
    page.select_option('#task .condition', 'broken')
    page.check('#task .start-agent')
    choose_agent(page, '#task', 'codex')
    page.click('#task .put')
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=30000)
    ticket = next(work for work in store.work(limit=0).results
                  if work.task == 'Inspect the alarm and report what you find.')
    assert ticket.taken_by.startswith('codex ') and ticket.address == 'code.alarm.audible'
    told = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt')
    assert ticket.id in told['message']['params']['prompt'][0]['text']
    assert page.is_hidden('#task')
    run('dispatch', 'stop', ticket.id, cwd=mapped)
    assert problems == []
    # A task can still just be queued; failure to start keeps the new ticket for another attempt.
    run('set', '--dispatch-codex', 'metaform-nonexistent-acp-adapter', cwd=mapped)
    page.evaluate(f'window.metaform.task("{alarm}")')
    assert not page.is_checked('#task .start-agent')
    page.fill('#task .text', 'Keep this task if the adapter cannot start.')
    page.select_option('#task .condition', 'broken')
    page.check('#task .start-agent')
    with page.expect_response(lambda response: '/api/dispatch-start' in response.url) as failed:
        page.click('#task .put')
    assert failed.value.status == 400 and 'not found' in failed.value.json()['error']
    page.wait_for_function('() => document.querySelector("#task").hidden')
    kept = next(work for work in store.work(limit=0).results
                if work.task == 'Keep this task if the adapter cannot start.')
    assert kept.taken is None and kept.done is None
    assert problems == ['Failed to load resource: the server responded with a status of 400 (Bad Request)']


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-040')
@pytest.mark.parametrize('glyphed', [False, True])
def test_start_is_not_offered_or_accepted_for_an_untaken_ticket_with_a_live_session(
        run, web, mapped, browser, glyphed):
    from metaform import relay
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    busy = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Busy ticket').id
    later = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='Same agent later').id
    if glyphed:
        for work_id in (busy, later):
            run('map', 'work', 'op=edit', f'id={work_id}', 'glyph=kite', cwd=mapped)
    live_session(busy)
    ACTIVITY[f's-{busy}'] = 'waiting'  # awaiting permission still owns the session and glyph
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    page.wait_for_selector(f'#board .card[data-id="{busy}"]')
    assert store.ticket(busy).work.taken is None
    for work_id in ((busy, later) if glyphed else (busy,)):
        assert page.locator(f'#board .card[data-id="{work_id}"] .start').count() == 0
    # the command and the server refusing it: test_a_start_the_server_is_asked_for_is_refused_as_the_command_refuses_it
    # Session-only changes redraw start controls even though no ticket changed.
    live_session(busy, state='ended')
    relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})
    for work_id in (busy, later):
        page.wait_for_selector(f'#board .card[data-id="{work_id}"] .start')
    assert problems == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-040')
@pytest.mark.parametrize('distributed', [False, True])
def test_start_all_uses_one_agent_choice_and_starts_each_free_glyph_once_in_board_order(
        run, web, mapped, browser, tmp_path, watch_dispatch, distributed):
    from metaform.data import Node, Store
    from metaform.modules.dispatch.tests.test_dispatch import eventually

    run('enable', 'dispatch')
    store = Store('proj')
    # Remove the fixture's ordinary waiting work so only this controlled queue is launched.
    for record in store.work(open=True, limit=0).results:
        store.finish_work(record.id, 'fixture setup')
    tickets = [store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task=f'Queue {i}').id
               for i in range(4)]
    for work_id, column, position in zip(tickets, ['backlog', 'todo', 'todo', 'todo'], [0, 2, 0, 1]):
        store.move_work(work_id, column, position=position)
    if distributed:
        for work_id, glyph in zip(tickets, ['kite', 'moth', 'kite', 'moth']):
            run('map', 'work', 'op=edit', f'id={work_id}', f'glyph={glyph}', cwd=mapped)
    excluded = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', note='no task: never started').id
    busy = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='Already running').id
    live_session(busy)
    log = tmp_path / 'all.jsonl'
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    sent = []
    page.on('request', lambda req: sent.append(req.post_data_json) if '/api/dispatch-start' in req.url else None)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    page.click('#board .start-all')
    page.wait_for_selector('#dispatch:not([hidden])')
    choose_agent(page, '#dispatch', 'codex')
    # the Backlog ticket is held: Start all never starts it, UX review round 1 (orchestrator F5)
    expected = [tickets[2], tickets[3]] if distributed else [tickets[2], tickets[3], tickets[1]]
    assert page.eval_on_selector_all('#dispatch .ticket', 'rows => rows.map(row => row.dataset.id)') == expected
    # the launches' own permissions, at the project's setting until chosen, approving everything saying its risk
    page.wait_for_selector('#dispatch .permissions select.prompts')
    assert page.text_content('#dispatch .permissions select.prompts option') == 'Project setting: Ask every prompt as ' \
        'a question at the ticket' and page.is_hidden('#dispatch .permissions .risk')
    page.select_option('#dispatch .permissions select.prompts', 'approve-all')
    assert 'without asking' in page.text_content('#dispatch .permissions .risk:not([hidden])')
    page.click('#dispatch .start-all')
    page.wait_for_selector('#dispatch', state='hidden', timeout=30000)
    assert [(one['work_id'], one['agent'], one.get('prompts')) for one in sent] \
        == [(work_id, 'codex', 'approve-all') for work_id in expected]
    from metaform.modules.dispatch import launch_options
    assert all(launch_options(store, work_id) == {'prompts': 'approve-all'} for work_id in expected)
    for work_id in expected:
        eventually(lambda work_id=work_id: store.ticket(work_id).work.taken)
    assert store.ticket(excluded).work.taken is None and store.ticket(busy).work.taken is None
    assert store.ticket(tickets[0]).work.taken is None, 'a held ticket waits for the person'
    if distributed:
        assert store.ticket(tickets[0]).work.taken is None and store.ticket(tickets[1]).work.taken is None
    shown = page.evaluate(TOPMOST_TOAST)
    assert shown['on_top'] and str(len(expected)) in shown['text'], shown
    assert problems == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-040')
def test_start_all_keeps_failed_tickets_retryable_and_does_not_restart_successes(
        run, web, mapped, browser, tmp_path, watch_dispatch):
    from metaform.data import Node, Store

    run('enable', 'dispatch')
    store = Store('proj')
    for record in store.work(open=True, limit=0).results:
        store.finish_work(record.id, 'fixture setup')
    failed, success = [store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task=f'Ticket {i}').id
                       for i in range(2)]
    run('web', '--json', env={'FAKE_ACP_LOG': str(tmp_path / 'retry.jsonl'), 'FAKE_ACP_MODE': 'ask'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    sent = []
    page.on('request', lambda req: sent.append(req.post_data_json) if '/api/dispatch-start' in req.url else None)

    held = []

    def refuse_one(route):
        if route.request.post_data_json['work_id'] == failed:
            held.append(route)  # keep a launch in flight while the person tries opening Start all again
        else:
            route.fallback()

    page.route('**/api/dispatch-start', refuse_one)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    page.click('#board .start-all')
    choose_agent(page, '#dispatch', 'codex')
    page.click('#dispatch .start-all')
    assert page.locator('#board .start-all').is_disabled()
    # A stale click queued before the board disabled must not replace the launch window or submit another batch.
    page.evaluate('async () => { await document.querySelector("#board .start-all").onclick(); }')
    # while the run goes on its button is Stop starting, which ends the run between two starts (spawn-gate-stop-all)
    assert page.locator('#dispatch .start-all').text_content() == 'Stop starting'
    assert [one['work_id'] for one in sent] == [failed]
    held[0].fulfill(status=400, content_type='application/json', body=json.dumps({'error': 'Fixture refusal'}))
    page.wait_for_function('() => { const all = document.querySelector("#dispatch .start-all");'
                           ' return !all.disabled && all.textContent !== "Stop starting"; }')
    assert page.is_visible('#dispatch')
    assert page.locator(f'#dispatch .ticket[data-id="{failed}"] .start').is_enabled()
    assert page.locator(f'#dispatch .ticket[data-id="{success}"] .start').is_disabled()
    shown = page.evaluate(TOPMOST_TOAST)
    assert shown['on_top'] and '1 could not start' in shown['text'], shown
    assert store.ticket(failed).work.taken is None
    page.unroute('**/api/dispatch-start', refuse_one)
    page.click('#dispatch .start-all')
    page.wait_for_selector('#dispatch', state='hidden', timeout=30000)
    assert [one['work_id'] for one in sent].count(success) == 1
    assert [one['work_id'] for one in sent].count(failed) == 2
    assert problems == ['Failed to load resource: the server responded with a status of 400 (Bad Request)']


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-037')
def test_the_start_window_says_the_free_slots_and_a_card_says_why_its_agent_ended(run, web, mapped, browser):
    """UX review round 1, web-gui-controls F10 and F11: with no slot free the Start window offered nine enabled Start
    buttons, and a card read `Ended · dispatch starting <32 hex>` with its cause only in the session row. Round 2,
    held-and-signals F2 and F5: the page never received `after_work`, so a waiting ticket never said Waiting on and
    Start all offered it first; a failed start's card said Did not start and Starting… at once."""
    import re

    from metaform.data import Node, Store
    from metaform.modules import dispatch as modules
    run('enable', 'dispatch')
    run('set', '--dispatch-agents=1', cwd=mapped)
    store = Store('proj')
    for record in store.work(open=True, limit=0).results:
        store.finish_work(record.id, 'fixture setup')
    node = Node('element', 'code.alarm.audible')
    busy = store.add_work(node, 'unbuilt', task='Running').id
    store.take_work(busy, by=f'claude s-{busy}')
    live_session(busy)
    store.add_work(node, 'unbuilt', task='Waiting for a slot')
    after = store.add_work(node, 'unbuilt', task='Waits on Running').id
    with Store('proj', module='map').tables() as tx:  # as `map work op=edit after_work=` keeps it
        tx.insert('after', {'work_id': after, 'works': [busy]})
    failed = store.add_work(node, 'unbuilt', task='Its launch failed').id
    token = 'dispatch starting ' + 'a' * 32
    store.take_work(failed, by=token)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('agent_sessions', {'session_id': 'failed-launch', 'work_id': failed, 'agent': 'claude',
                                     'state': 'ended', 'how': 'it did not start: Connection closed',
                                     'started': '2999-01-01T00:00:00Z', 'seq': 10 ** 9, 'origin': modules.origin()})
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    card = page.locator(f'#board .card[data-id="{failed}"]')
    card.locator('.ended .why').wait_for()
    shown = card.text_content()
    assert 'Connection closed' in shown and 'Did not start' in shown and 'Starting…' not in shown, shown
    assert not re.search('[0-9a-f]{32}', shown), 'no reservation token on the card'
    assert card.locator('.ended button.back').is_visible()
    waits = page.locator(f'#board .card[data-id="{after}"] .waiting-on').text_content()
    assert re.fullmatch(r'Waiting on code\.alarm\.audible#\d+', waits), waits
    page.evaluate('async () => { await document.querySelector("#board .start-all").onclick(); }')
    page.wait_for_selector('#dispatch:not([hidden])')
    assert page.locator(f'#dispatch .ticket[data-id="{after}"]').count() == 0, 'Start all leaves a waiting ticket out'
    page.wait_for_function('() => document.querySelector("#dispatch .slots").textContent.startsWith("0 of 1")')
    assert page.locator('#dispatch .start-all').is_disabled()
    assert all(button.is_disabled() for button in page.locator('#dispatch .ticket .start').all())
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-039')
def test_a_read_that_fails_while_the_map_is_read_again_keeps_the_map_the_node_chosen_and_the_agents_at_work(
        run, web, mapped, browser):
    """The graph suddenly disappeared while the person browsed, shortly after chatting to an agent, and no
    agents were then shown working. A change pushed to the page reads the map and the agents again; when those reads
    fail, as every read does while the server is restarted, the page had already let go of the map it drew and drew
    nothing, and drew an empty agents key. The failure is said, and what was drawn stays."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    run('enable', 'dispatch')
    work = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone').id
    store.take_work(work, by='claude')
    live_session(work)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 1', timeout=15000)
    page.evaluate(f'window.metaform.select("{alarm}")')
    page.wait_for_function(f'() => window.metaform.loaded() && window.metaform.selected() === "{alarm}"')
    drawn, nodes2d = page.evaluate('window.metaform.drawn()'), page.eval_on_selector_all('#map2d svg g.node', 'found => found.length')
    changes = page.evaluate('window.metaform.changes()')
    page.evaluate("""() => { window.failed = []; const fetched = window.fetch;
        window.fetch = (url, ...rest) => {
            const read = String(url).match(/^\\/api\\/(graph|dispatch-sessions)\\?/);
            if (!read) return fetched(url, ...rest);
            window.failed.push(read[1]);
            return Promise.reject(new TypeError('Failed to fetch')); }; }""")
    relay.deliver('map.changed', {'project': 'proj'})  # a change that may have changed anything reads the map again
    page.wait_for_function(f'() => window.metaform.changes() > {changes} && window.metaform.loaded()', timeout=15000)
    relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})  # and a runner's line, the agents
    page.wait_for_function('() => window.failed.includes("dispatch-sessions")', timeout=15000)
    assert 'graph' in page.evaluate('window.failed')
    assert page.inner_text('#toast') == 'The server was restarting and did not get that. Try again in a moment.'
    assert page.evaluate('window.metaform.drawn()') == drawn
    assert page.eval_on_selector_all('#map2d svg g.node', 'found => found.length') == nodes2d
    assert page.evaluate('window.metaform.selected()') == alarm
    assert page.eval_on_selector_all('#agents .agent', 'found => found.map(one => one.dataset.id)') == [work]
    assert [one['work_id'] for one in page.evaluate('window.metaform.figures()')] == [work]
    assert problems == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-035')
def test_choosing_another_project_takes_the_agents_of_the_project_left_off_the_page(
        run, web, mapped, browser, tmp_path):
    """After switching projects the agents stayed on screen. The agents key, the threads open in the chat dock and
    the figures on the map are the project's own: choosing another project closes the threads and draws that project's
    agents only, even when a read of the agents of the project left answers after the choice."""
    from metaform import relay
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    work = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a quieter tone').id
    store.take_work(work, by='claude')
    live_session(work)
    folder = tmp_path / 'other'
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    build(Store('other'))
    run('set', '--layers', ','.join(TOGGLED), cwd=folder)
    others = {entry.element.id for entry in Store('other').graph(limit=0).elements}
    started(run)
    page, problems, _ = opened(browser, web)
    button = f'#agents .agent[data-id="{work}"]'
    page.wait_for_selector(button, timeout=15000)
    page.click(button)
    page.wait_for_selector('#helpdesk:not([hidden]) .threadbar:not([hidden])', timeout=10000)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 1', timeout=15000)
    page.evaluate("""() => { window.held = 0; const fetched = window.fetch;
        window.fetch = async (url, ...rest) => {
            if (/^\\/api\\/dispatch-sessions\\?project=proj&.*thread=false/.test(String(url))) {
                window.held++; await new Promise(done => setTimeout(done, 1500)); }
            return fetched(url, ...rest); }; }""")
    relay.deliver('map.changed', {'project': 'proj', 'tables': 'dispatch'})  # a line the agent wrote
    page.wait_for_function('() => window.held === 1', timeout=10000)
    page.select_option('#proj', 'other')
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    page.wait_for_timeout(2500)  # past the answer held for the project left
    page.wait_for_function('wanted => { const drawn = window.metaform.graph().nodes.filter(node => node.t === "el")'
                           '.map(node => node.id).sort(); return JSON.stringify(drawn) === JSON.stringify(wanted); }',
                           arg=sorted(others), timeout=15000)  # the project chosen is drawn, and only it
    assert page.query_selector_all('#agents .agent') == []
    page.wait_for_selector('#agents', state='hidden', timeout=10000)   # the window slides away once none is at work
    assert page.evaluate('window.metaform.dock().threads') == []          # the threads went with the project left
    page.wait_for_function('() => window.metaform.figures().length === 0', timeout=20000)
    assert problems == []


@pytest.mark.req('VIEW-018')
def test_a_read_of_the_map_of_the_project_left_that_answers_after_the_choice_is_not_drawn(
        run, web, mapped, browser, tmp_path):
    """Found 2026-10-03 with the agents that stayed after a switch of projects: a change pushed for the project shown
    reads its map again, and when that read answers after the person has chosen another project, while the page still
    reads the new project's layers, the map of the project left came back into the page."""
    from metaform import relay
    from metaform.data import Store
    folder = tmp_path / 'other'
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    build(Store('other'))
    run('set', '--layers', ','.join(TOGGLED), cwd=folder)
    left = {entry.element.id for entry in Store('proj').graph(limit=0).elements}
    others = {entry.element.id for entry in Store('other').graph(limit=0).elements}
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate("""() => { window.held = 0; const fetched = window.fetch;
        window.fetch = async (url, ...rest) => {
            const held = /^\\/api\\/graph\\?project=proj&/.test(String(url)) ? 1200
                : /^\\/api\\/layers\\?project=other&/.test(String(url)) ? 2500 : 0;
            if (held) { window.held++; await new Promise(done => setTimeout(done, held)); }
            return fetched(url, ...rest); };
        window.shown = []; setInterval(() => window.shown.push(window.metaform.graph().nodes
            .filter(node => node.t === 'el').map(node => node.id)), 20); }""")
    relay.deliver('map.changed', {'project': 'proj'})
    page.wait_for_function('() => window.held === 1', timeout=10000)
    page.select_option('#proj', 'other')
    page.wait_for_function('() => window.held === 2 && window.metaform.loaded()', timeout=15000)
    shown = page.evaluate('window.shown')
    emptied = next(at for at, ids in enumerate(shown) if not ids)  # the new project's load begins with no map
    assert not [ids for ids in shown[emptied:] if set(ids) & left]
    assert set(shown[-1]) == others
    assert problems == []


@pytest.mark.req('VIEW-018')
def test_the_metaforms_of_a_project_left_that_answer_after_the_next_choice_do_not_choose_the_metaform_shown(
        run, web, mapped, browser, tmp_path):
    """Found 2026-10-03 in review: two quick choices of project, and the first one's list of metaforms answering after
    the second, chose the project left's metaform for the project shown, whose map then could not be read."""
    from metaform.data import Store
    folder = tmp_path / 'other'
    folder.mkdir()
    run('add', 'project', 'other', str(folder))
    build(Store('other'))
    run('set', '--layers', ','.join(TOGGLED), cwd=folder)
    shown = {entry.element.id for entry in Store('proj').graph(limit=0).elements}
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    chosen = page.input_value('#mf')
    page.evaluate("""() => { window.held = 0; const fetched = window.fetch;
        window.fetch = async (url, ...rest) => {
            if (/^\\/api\\/bases\\?project=other&/.test(String(url))) {
                window.held++; await new Promise(done => setTimeout(done, 1500)); }
            return fetched(url, ...rest); }; }""")
    page.select_option('#proj', 'other')
    page.wait_for_function('() => window.held === 1', timeout=10000)
    page.select_option('#proj', 'proj')
    page.wait_for_timeout(2500)  # past the answer held for the project left
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    assert page.input_value('#proj') == 'proj' and page.input_value('#mf') == chosen
    assert {node['id'] for node in page.evaluate('window.metaform.graph()')['nodes'] if node['t'] == 'el'} == shown
    assert problems == []


TOPMOST_TOAST = '''() => { const box = document.querySelector("#toast"); if (box.hidden) return null;
    const at = box.getBoundingClientRect(), hit = document.elementFromPoint(at.left + at.width / 2, at.top + at.height / 2);
    return {text: box.textContent, on_top: box.contains(hit), hit: hit && (hit.id || hit.className)}; }'''


@pytest.mark.req('VIEW-037')
@pytest.mark.req('VIEW-039')
def test_starting_an_agent_from_the_board_says_what_happened_above_the_board(run, web, mapped, browser, tmp_path,
                                                                              watch_dispatch):
    """Starting agents from the board seemed to do nothing. Start says whether the agent is
    starting or why it is not only in a toast, and the toast was drawn under the open board, so the start window
    closed or its Start came back with nothing to see. The toast is the topmost thing where it is drawn."""
    import sys

    from metaform.data import Node, Store
    store = Store('proj')
    refused = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Write notes.txt').id
    begun = store.add_work(Node('element', 'exterior.cook'), None, task='Name the cook').id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE_AGENT}"', cwd=mapped)  # found when the page reads the agents
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    # an agent that cannot start: why, above the board, and the window stays for another choice
    page.click(f'#board .card[data-id="{refused}"] button.start')
    page.wait_for_selector('#dispatch:not([hidden])')
    choose_agent(page, '#dispatch', 'codex')
    run('set', '--dispatch-codex', 'metaform-nonexistent-acp-adapter', cwd=mapped)  # and gone by the time it starts
    with page.expect_response(lambda response: '/api/dispatch-start' in response.url) as failed:
        page.click(f'#dispatch .ticket[data-id="{refused}"] button.start')
    assert failed.value.status == 400
    page.wait_for_selector('#toast:not([hidden])')
    shown = page.evaluate(TOPMOST_TOAST)
    assert shown['on_top'] and 'not found' in shown['text'], shown
    page.screenshot(path=str(tmp_path / 'refused.png'))
    page.click('#dispatch .close')
    page.evaluate('document.querySelector("#toast").hidden = true')
    # an agent that starts: that it is starting, above the board
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE_AGENT}"', cwd=mapped)
    page.click(f'#board .card[data-id="{begun}"] button.start')
    page.wait_for_selector('#dispatch:not([hidden])')
    choose_agent(page, '#dispatch', 'codex')
    page.click(f'#dispatch .ticket[data-id="{begun}"] button.start')
    page.wait_for_selector('#toast:not([hidden])', timeout=30000)
    shown = page.evaluate(TOPMOST_TOAST)
    assert shown['on_top'] and 'is starting' in shown['text'], shown
    page.screenshot(path=str(tmp_path / 'started.png'))
    assert problems == ['Failed to load resource: the server responded with a status of 400 (Bad Request)']


@pytest.mark.req('VIEW-044')
@pytest.mark.kind('fixture')
def test_a_named_board_is_made_in_the_picker_and_a_card_moves_to_it_and_back(run, web, mapped, browser):
    """The person's need of 2026-10-20: a board gets a name, a new one is made from the board's picker, and a ticket is
    moved from one board to another with its card's selector; each board shows its own tickets, and a move is one
    change the page hears as a change to that ticket."""
    from metaform.data import Node, Store
    work = Store('proj').add_work(Node('element', 'code.alarm.audible'), None, task='A quieter alarm').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    card = f'#board .card[data-id="{work}"]'
    page.wait_for_selector(card)
    assert [one.text_content() for one in page.locator('#board .boards option').all()] == [
        'Board · active', 'New board…', 'Wipe this board…']
    page.once('dialog', lambda dialog: dialog.accept('Later'))
    page.select_option('#board .boards', index=1)
    page.wait_for_selector('#board .boards option[value="Later"]', state='attached')  # an option of a closed select
    assert page.locator('#board .boards').input_value() == 'Later'
    page.wait_for_function(f'() => !document.querySelector({card!r})')  # the new board holds nothing yet
    page.select_option('#board .boards', '')
    page.wait_for_selector(f'{card} select.board-of')
    page.select_option(f'{card} select.board-of', 'Later')
    page.wait_for_function(f'() => !document.querySelector({card!r})')  # it left the first board
    page.select_option('#board .boards', 'Later')
    page.wait_for_selector(card)
    with Store('proj', module='map').tables(write=False) as tx:
        assert tx.get('ticket_settings', {'work_id': work})['board'] == 'Later'
    page.select_option(f'{card} select.board-of', '')
    page.wait_for_function(f'() => !document.querySelector({card!r})')  # back to the first board
    page.select_option('#board .boards', '')
    page.wait_for_selector(card)
    assert not problems, problems


def test_a_waiting_merge_shows_review_and_review_asks_about_help_in_a_support_window(run, web, mapped, browser):
    """VIEW-044: done work that waits shows Review.; Review takes it over for good and asks whether an agent should help
    prepare the code; Yes opens the support window at the lower right, waiting for the next available agent."""
    import time as clock

    from metaform.data import Node, Store
    run('enable', 'dispatch')
    work = Store('proj').add_work(Node('element', 'code.alarm.audible'), None, task='A quieter alarm').id
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('merges', {'work_id': work, 'branch': f'metaform/{work[:12]}', 'worktree': str(mapped),
                             'state': 'ready', 'reason': '', 'ready': clock.time(), 'deadline': clock.time() + 900,
                             'seq': clock.time_ns()})
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.wait_for_selector('#reviewNotice .notice')
    assert page.locator('#reviewNotice .notice b').text_content() == 'Review.'
    page.click('#reviewNotice .notice button')
    page.wait_for_selector('#mergeAsk:not([hidden])')
    assert page.locator('#mergeAsk p').text_content() == \
        "Would you like agent assistance with prepping code so it doesn't conflict with the ongoing work?"
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('merges', {'work_id': work})['state'] == 'review', 'Review cancels the countdown for good'
    page.click('#mergeAsk .yes')
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent'
                           '.includes("Waiting for the next available agent.")')
    assert page.locator('#helpdesk .who b').text_content() == 'An agent'  # whom the chat is with is its title
    box = page.locator('#helpdesk').bounding_box()
    width, height = page.viewport_size['width'], page.viewport_size['height']
    assert box['x'] + box['width'] > width - 40 and box['y'] + box['height'] > height - 40, 'it sits at the lower right'
    run('dispatch', 'stop', work, cwd=mapped, ok=False)
    assert problems == []


@pytest.mark.req('VIEW-044')
@pytest.mark.kind('fixture')
def test_the_chat_dock_rests_as_a_sliver_lifts_near_the_pointer_and_opens_into_the_chat(run, web, mapped, home,
                                                                                        browser):
    """The chat dock: a sliver at the bottom edge that lifts when the pointer comes near and settles when it leaves;
    a click opens the chat, the size button takes most of the screen, and minimizing returns it to a sliver. Call asks
    the person to stand by and preserves the session when the dock closes. An attached file is kept under the Metaform home with a safe name,
    never in the person's source tree."""
    run('enable', 'dispatch')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.locator('#dock').get_attribute('class') == 'resting' and page.locator('#helpdesk').is_hidden()
    tab = page.locator('#dockTab').bounding_box()
    page.mouse.move(tab['x'] + tab['width'] / 2, tab['y'] - 30)
    page.wait_for_function('() => document.querySelector("#dock").className === "near"')
    page.mouse.move(100, 100)
    page.wait_for_function('() => document.querySelector("#dock").className === "resting"')
    page.click('#dockTab', force=True)
    page.wait_for_selector('#helpdesk:not([hidden])')
    # it grows out of its tab in about 260 to 340 ms, a transform alone, and is measured once it has
    settled = '() => !document.getAnimations().some(one => one.effect && one.effect.target && one.effect.target.id === "helpdesk")'
    page.wait_for_function(settled)
    page.click('#helpdesk .big')
    page.wait_for_function(settled)
    box = page.locator('#helpdesk').bounding_box()
    assert box['width'] >= page.viewport_size['width'] * 0.75, 'the large chat takes most of the screen'
    page.fill('#helpdesk .say', '/help')
    page.press('#helpdesk .say', 'Enter')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent.includes("/list shows")')
    page.click('#helpdesk .call')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent'
                           '.includes("Please stand by while we contact an agent for you.")')
    page.click('#helpdesk .close')
    page.wait_for_selector('#helpdesk', state='hidden')
    page.click('#dockTab')
    page.wait_for_function(settled)
    # Reopening from the dock tab uses the regular size. Keep that size for the close/reopen geometry check.
    if page.locator('#dock').get_attribute('class') == 'open big':
        page.click('#helpdesk .big')
    rect = '''() => { const box = document.querySelector("#helpdesk"), at = box.getBoundingClientRect();
        return [box.style.left, box.style.top, box.style.width, box.style.height, at.left, at.top, at.width, at.height]; }'''
    kept = page.evaluate(rect)
    page.click('#helpdesk .min')                         # it shrinks into its tab, then rests as a sliver
    page.wait_for_function('() => document.querySelector("#helpdesk").hidden'
                           ' && document.querySelector("#dock").className === "resting"')
    page.click('#dockTab', force=True)                   # and grows back out of it, as it was
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.wait_for_function(settled)
    assert page.evaluate(rect) == kept
    page.click('#helpdesk .min')
    page.wait_for_function('() => document.querySelector("#helpdesk").hidden')
    saved = page.evaluate("""fetch('/api/attach', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({project: 'proj', name: '../../a plan.txt', data: btoa('the plan')})}).then(r => r.json())""")
    path = Path(saved['path'])
    assert path.read_text() == 'the plan' and path.name.endswith('-a_plan.txt')
    assert str(path).startswith(str(home)) and not str(path).startswith(str(mapped))
    assert problems == []


@pytest.mark.req('VIEW-042')
@pytest.mark.kind('fixture')
def test_a_message_sent_with_no_agent_starts_one_waits_in_the_thread_and_reaches_it_in_order(
        run, web, mapped, browser, monkeypatch, tmp_path):
    """Enter with no agent there starts the system agent as Call does: the message waits in the thread, marked as
    waiting, and is never lost; one written while it connects waits behind it; both reach the agent in order."""
    run('enable', 'dispatch')
    log = tmp_path / 'acp.log'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'plain')  # its first turn ends at once, so later prompts are taken
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#dockTab', force=True)
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.fill('#helpdesk .say', 'First, before any agent')
    page.press('#helpdesk .say', 'Enter')
    page.wait_for_selector('#helpdesk .log .bubble.mine.pending')
    assert page.input_value('#helpdesk .say') == ''
    assert page.locator('#helpdesk .call').text_content() == 'Call'
    page.fill('#helpdesk .say', 'Second, while it connects')
    page.press('#helpdesk .say', 'Enter')
    said = ('First, before any agent', 'Second, while it connects')
    logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt'
              and entry['message']['params']['prompt'][0].get('text') == said[1])
    prompts = [entry['message']['params']['prompt'][0].get('text') for entry in map(json.loads, log.read_text().splitlines())
               if entry.get('message', {}).get('method') == 'session/prompt']
    assert prompts.index(said[0]) < prompts.index(said[1]), prompts
    page.wait_for_function('() => !document.querySelector("#helpdesk .log .bubble.pending")', timeout=30000)
    page.click('#helpdesk .threadbar .stop')
    page.click('#confirm button.confirm')
    page.wait_for_selector('#helpdesk .stopped-agent')
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_new_and_clear_end_the_system_agents_conversation_and_start_one_resuming_nothing(
        run, web, mapped, browser, monkeypatch, tmp_path):
    """/new and /clear, the chat's own commands, code.interface.graphical#9b: the system agent's session on view ends
    and a new one starts with nothing resumed though Resume is on and its agent could load the old one; Resume and Stay
    connected are left as they were, and the ended thread stays listed. The agent's own /clear never takes the name."""
    from metaform.data import Store
    run('enable', 'dispatch')
    log = tmp_path / 'acp.log'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'plain')  # each turn ends at once
    monkeypatch.setenv('FAKE_ACP_LOAD', '1')  # it can load an earlier conversation, so a resume would show
    monkeypatch.setenv('FAKE_ACP_CLEAR', '1')  # and it offers a /clear of its own
    settings = lambda: {entry['key']: entry['value'] for entry in json.loads(run('config', '--json', cwd=mapped).stdout)
                        if entry['key'] in ('dispatch_resume_chats', 'dispatch_stay_connected')}
    kept = settings()
    assert kept['dispatch_resume_chats'] is True
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#dockTab', force=True)
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.fill('#helpdesk .say', '/help')
    page.press('#helpdesk .say', 'Enter')
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent.includes("/new or /clear")')
    page.fill('#helpdesk .say', 'Remember the word heron')
    page.press('#helpdesk .say', 'Enter')
    method = lambda entry: entry.get('message', {}).get('method')
    logged_by(log, lambda entry: method(entry) == 'session/prompt'
              and entry['message']['params']['prompt'][0].get('text') == 'Remember the word heron')
    page.wait_for_function('() => !document.querySelector("#helpdesk .log .bubble.pending")', timeout=30000)
    dock = lambda: page.evaluate('window.metaform.dock()')
    ended = []
    for command in ('/new', '/clear'):
        before = dock()['on']
        page.wait_for_function('() => document.querySelector("#helpdesk .call").hidden')  # its session is live
        page.fill('#helpdesk .say', command)
        page.press('#helpdesk .say', 'Enter')
        page.wait_for_function(f'() => {{ const on = window.metaform.dock().on; return on && on !== "{before}"; }}',
                               timeout=30000)
        ended.append(before)
        now = dock()
        assert [one['source'] for one in now['threads'] if one['session'] in ended] == ['system'] * len(ended), now
        page.wait_for_function('() => document.querySelector("#helpdesk .call").hidden', timeout=30000)
        page.fill('#helpdesk .say', f'What was the word? after {command[1:]}')
        page.press('#helpdesk .say', 'Enter')
        question = f'What was the word? after {command[1:]}'
        asked = logged_by(log, lambda entry, question=question: method(entry) == 'session/prompt'
                          and entry['message']['params']['prompt'][0].get('text') == question)
        assert asked['message']['params']['sessionId'] == now['on'], (asked, now)
        entries = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines() if line.strip()]
        turns = [json.dumps(entry['message']['params']['prompt']) for entry in entries if method(entry) == 'session/prompt'
                 and entry['message']['params']['sessionId'] == now['on']]
        assert turns and not any('heron' in turn for turn in turns), turns  # no earlier conversation in its turns
    entries = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert not [entry for entry in entries if method(entry) in ('session/load', 'session/resume')]
    assert not any(method(entry) == 'session/prompt' and '/clear' in json.dumps(entry['message']['params']['prompt'])
                   for entry in entries), 'the agent was sent its own /clear'
    with Store('proj', module='dispatch').tables(write=False) as tx:
        rows = {row['session_id']: row for row in tx.rows('agent_sessions', limit=0).results}
    assert [(rows[one]['state'], rows[one]['how']) for one in ended] == [('ended', 'stopped by the person')] * 2, rows
    assert rows[dock()['on']]['state'] == 'running'
    assert settings() == kept  # the Resume box and Stay connected are left as they were
    run('dispatch', 'stop', rows[dock()['on']]['work_id'], f'session={dock()["on"]}', cwd=mapped)
    assert problems == []


@pytest.mark.req('VIEW-042')
@pytest.mark.kind('fixture')
def test_a_pasted_picture_and_dropped_files_attach_as_the_paperclip_does_and_reach_the_agent(
        run, web, mapped, home, browser, monkeypatch, tmp_path):
    """A screenshot pasted into the box and files dropped on the conversation are saved by /api/attach, shown as
    chips, and named to the agent with the message; pasted text stays text; a file the server refuses is named in the
    chat with why. Ticket code.interface.graphical#92."""
    run('enable', 'dispatch')
    log = tmp_path / 'acp.log'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'plain')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#dockTab', force=True)
    page.wait_for_selector('#helpdesk:not([hidden])')
    # files given to the page as a browser gives them: a paste on the box, a drag and a drop on the conversation
    page.evaluate("""() => {
        const png = atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==');
        window.given = (...files) => { const list = new DataTransfer(); for (const file of files) list.items.add(file); return list; };
        window.png = new File([Uint8Array.from(png, c => c.charCodeAt(0))], 'image.png', {type: 'image/png'});
        window.fire = (selector, type, init) => {
          const event = type === 'paste' ? new ClipboardEvent(type, {bubbles: true, cancelable: true, ...init})
            : new DragEvent(type, {bubbles: true, cancelable: true, ...init});
          document.querySelector(selector).dispatchEvent(event);
          return event.defaultPrevented;
        };
    }""")
    assert page.evaluate("fire('#helpdesk .say', 'paste', {clipboardData: given(png)})")
    page.wait_for_function('() => document.querySelector("#helpdesk .files").textContent.includes("image.png")')
    # text pasted is left to the browser to paste as text, even with a picture of itself beside it, and attaches none
    words = page.evaluate("""() => { const list = given(png); list.setData('text/plain', 'cells A1:B2');
        return fire('#helpdesk .say', 'paste', {clipboardData: list}); }""")
    assert words is False
    page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
    page.evaluate("navigator.clipboard.writeText('Look at these')")
    page.focus('#helpdesk .say')
    page.keyboard.press('Control+V')
    page.wait_for_function('() => document.querySelector("#helpdesk .say").value === "Look at these"')
    # a drag of files marks where they land; a drag of text does not
    assert page.evaluate("""() => { const list = new DataTransfer(); list.setData('text/plain', 'x');
        fire('#helpdesk .log', 'dragover', {dataTransfer: list});
        return document.querySelector('#helpdesk').classList.contains('dropping'); }""") is False
    assert page.evaluate("fire('#helpdesk .log', 'dragover', {dataTransfer: given(png)})")
    assert page.evaluate("getComputedStyle(document.querySelector('#helpdesk .files'), '::after').content") \
        == '"Drop to attach to your message"'
    # one too large for the attach path is refused with the server's reason, in the chat; the two beside it attach
    page.evaluate("""() => fire('#helpdesk .log', 'drop', {dataTransfer: given(
        new File(['the plan'], 'plan.txt', {type: 'text/plain'}),
        new File([new Uint8Array(25 * 1024 * 1024 + 1)], 'huge.bin'),
        new File(['a,b'], 'rows.csv', {type: 'text/csv'}))})""")
    assert page.evaluate("document.querySelector('#helpdesk').classList.contains('dropping')") is False
    page.wait_for_function('() => document.querySelector("#helpdesk .files").textContent.includes("rows.csv")',
                           timeout=30000)
    page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent'
                           '.includes("huge.bin was not attached: An attachment is at most 25 MB.")')
    page.set_input_files('#helpdesk .clip input', files=[{'name': 'notes.md', 'mimeType': 'text/markdown',
                                                          'buffer': b'# notes'}])  # the paperclip, by the same path
    page.wait_for_function('() => document.querySelector("#helpdesk .files").textContent.includes("notes.md")')
    chips = page.locator('#helpdesk .files .chip').all_text_contents()
    assert [chip.split('-', 3)[-1] for chip in chips] == ['image.png', 'plan.txt', 'rows.csv', 'notes.md'], chips
    page.press('#helpdesk .say', 'Enter')
    prompt = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt'
                       and 'Look at these' in entry['message']['params']['prompt'][0].get('text', ''))
    text = prompt['message']['params']['prompt'][0]['text']
    paths = [Path(line[2:]) for line in text.splitlines() if line.startswith('- ') and 'attachments' in line]
    assert [path.name.split('-', 3)[-1] for path in paths] == ['image.png', 'plan.txt', 'rows.csv', 'notes.md'], text
    assert all(str(path).startswith(str(home)) and path.parent.name == 'attachments' for path in paths)
    assert paths[0].read_bytes().startswith(b'\x89PNG') and paths[1].read_text() == 'the plan'
    assert page.locator('#helpdesk .files .chip').count() == 0
    page.click('#helpdesk .threadbar .stop')
    page.click('#confirm button.confirm')
    page.wait_for_selector('#helpdesk .stopped-agent')
    assert [one for one in problems if '413' not in one] == []  # the refused file's answer, which the chat names


@pytest.mark.req('VIEW-042')
@pytest.mark.kind('fixture')
def test_a_done_ticket_has_chat_and_it_opens_the_chat_dock_with_an_agent(run, web, mapped, browser, monkeypatch,
                                                                          tmp_path):
    """Nothing is off limits for talking: a done ticket's card has Chat, and Chat opens the lower-right chat with an
    agent started to talk about that ticket; the ticket stays done and untaken."""
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    monkeypatch.setenv('METAFORM_PROMPTS', str(FAKE_AGENT.with_name('trial_prompts.xml')))  # test-only prompts
    monkeypatch.setenv('FAKE_ACP_LOG', str(tmp_path / 'acp.log'))
    monkeypatch.setenv('FAKE_ACP_MODE', 'hold')
    store = Store('proj')
    work = store.add_work(Node('element', 'code.alarm.audible'), None, task='A quieter alarm').id
    store.finish_work(work, 'Quieter now')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    card = page.locator(f'#board .card[data-id="{work}"]')
    card.locator('button.chat').click()
    page.wait_for_selector('#helpdesk:not([hidden])')
    page.wait_for_function('() => document.querySelector("#helpdesk .with").textContent.startsWith("With ")')
    assert page.locator('#helpdesk .call').text_content() == 'Call'
    session = None
    for _ in range(100):
        rows = json.loads(run('dispatch', 'sessions', f'id={work}', 'thread=false', '--json', cwd=mapped).stdout)['sessions']
        session = next((row for row in rows if row['state'] == 'running'), None)
        if session:
            break
        time.sleep(0.2)
    assert session, f'an agent started to talk about the done ticket: {rows}'
    assert Store('proj').work(Node('element', 'code.alarm.audible'), limit=0).results[0].done
    page.click('#helpdesk .threadbar .stop')
    page.click('#confirm button.confirm')
    page.wait_for_selector('#helpdesk .stopped-agent')
    run('dispatch', 'stop', work, cwd=mapped, ok=False)
    assert problems == []


@pytest.mark.req('VIEW-042')
@pytest.mark.kind('fixture')
def test_a_spec_code_and_a_ticket_id_in_a_question_open_what_they_refer_to(run, web, mapped, browser):
    """References in what the person reads are links: a spec record's code shows its record, a ticket's first
    characters show the ticket with Chat; a code nothing defines stays plain text."""
    from metaform.data import Node, Store
    (mapped / 'specifications').mkdir(exist_ok=True)
    (mapped / 'specifications' / '09-viewer.md').write_text(
        '# Viewer\n\n### VIEW-042 A question never holds up work\n\nThe record text.\n- Why: a test.\n\n### VIEW-043 Next\n')
    store = Store('proj')
    work = store.add_work(Node('element', 'code.alarm.audible'), None, task='A quieter alarm').id
    store.ask(Node('element', 'code.alarm.audible'), f'Per VIEW-042 and ZZZ-999, should ticket {work[:8]} wait?',
              suggestions=['Yes', 'No'])
    alarm = store.element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    from urllib.parse import parse_qs, urlsplit
    asked = []  # the references of each lookup read: those drawn together go in one read, not one read each
    page.on('request', lambda sent: asked.append(parse_qs(urlsplit(sent.url).query).get('refs', [''])[0].split())
            if '/api/lookup' in sent.url else None)
    page.click('#messages')
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"')
    page.wait_for_selector('#float .asked span.ref-link[data-ref="VIEW-042"]')
    page.wait_for_selector(f'#float .asked span.ref-link[data-ref="{work[:8]}"]')
    page.wait_for_selector('#float .asked span.ref[data-ref="ZZZ-999"][data-looked]')
    assert page.locator('#float .asked span.ref-link[data-ref="ZZZ-999"]').count() == 0, 'an unknown code stays plain'
    assert any({'VIEW-042', 'ZZZ-999', work[:8]} <= set(refs) for refs in asked), asked
    page.click('#float .asked span.ref-link[data-ref="VIEW-042"]')
    page.wait_for_selector('#refPop:not([hidden])')
    assert 'VIEW-042 A question never holds up work' in page.locator('#refPop h4').text_content()
    assert 'The record text.' in page.locator('#refPop').text_content() and 'VIEW-043' not in page.locator('#refPop').text_content()
    page.keyboard.press('Escape')
    page.click(f'#float .asked span.ref-link[data-ref="{work[:8]}"]')
    page.wait_for_function('() => document.querySelector("#refPop h4")?.textContent === "A quieter alarm"')
    assert page.locator('#refPop button.chat').count() == 1
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.kind('fixture')
def test_the_mouse_wheel_zooms_the_2d_map_at_once_and_nothing_eases_after_it(run, web, mapped, browser):
    """The wheel zooms the 2D map as it turns, VIEW-041, by how far it turned; nothing moves after the wheel stops. An
    eased zoom that lags the wheel and lands after it, far in or far out, is not how a mouse works."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    still2d(page)
    before = view_box(page)[2]
    page.mouse.move(*page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                                   ' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; })()'))
    page.mouse.wheel(0, 100)
    page.wait_for_function(f'() => Number(document.querySelector("#map2d svg").getAttribute("viewBox").split(" ")[2])'
                           f' !== {before}')
    landed = view_box(page)[2]
    page.wait_for_timeout(800)
    assert view_box(page)[2] == landed, 'the zoom landed with the wheel and did not drift on after it'
    assert landed > before, 'turning the wheel down zooms out'
    assert problems == []


@pytest.mark.req('STORE-041')
@pytest.mark.req('VIEW-011')
def test_a_base_is_activated_and_removed_from_the_header_and_the_active_one_is_refused(run, home, web, mapped, browser):
    """The page's base chooser only changed what it showed, and the one base operation the page had
    was clearing the whole project. Activate and Remove sit beside the chooser; neither acts on the active base, and
    Remove keeps a copy of the store."""
    from metaform.data import Store
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    options = 'document.querySelectorAll("#mf option")'
    run('add', 'base', 'fresh', cwd=mapped)  # fresh is active now, main is not; the page follows
    page.wait_for_function(f'() => [...{options}].some(o => o.selected && o.textContent === "fresh · active")',
                           timeout=5000)
    Store('proj').add_element(None, 'code.part', role='SE')  # fresh has a store now, so removing it keeps a copy
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.is_disabled('#activateBase') and page.is_disabled('#removeBase')  # the active base: nothing to do
    main_id = next(base.id for base in Store('proj').bases(limit=0).results if base.name == 'main')
    page.select_option('#mf', main_id)
    assert page.is_enabled('#activateBase') and page.is_enabled('#removeBase')
    page.click('#activateBase')
    page.wait_for_selector('#confirm button.confirm')  # it asks first, naming what leaves view, UX review round 1
    assert 'This changes the active map for every agent' in page.inner_text('#confirm')
    page.click('#confirm button.confirm')
    page.wait_for_function(f'() => [...{options}].some(o => o.selected && o.textContent === "main · active")', timeout=5000)
    assert [line.split()[0] for line in run('list', 'bases', cwd=mapped).stdout.splitlines() if '(active)' in line] == ['main']
    assert page.is_disabled('#activateBase') and page.is_disabled('#removeBase')
    fresh_id = next(base.id for base in Store('proj').bases(limit=0).results if base.name == 'fresh')
    page.select_option('#mf', fresh_id)
    page.click('#removeBase')
    page.click('#confirm button.confirm')  # removing a base cannot be undone from the page, so it is asked first
    page.wait_for_function(f'() => ![...{options}].some(o => o.textContent.startsWith("fresh"))', timeout=5000)
    assert [line.split()[0] for line in run('list', 'bases', cwd=mapped).stdout.splitlines()] == ['main']
    kept = list((home / 'backups' / 'remove-base' / 'proj').glob('*/fresh.metaform.sqlite3'))
    assert len(kept) == 1
    # the server refusing the active base: test_the_server_refuses_to_remove_the_active_base_and_activates_another
    assert problems == []


@pytest.mark.req('MAP-046')
@pytest.mark.req('MAP-048')
def test_a_task_carries_its_kind_and_its_stage_goes_on_the_parts_state_record(run, web, mapped):
    """A ticket's kind and a part's stage are kept apart. The task form sends both: the kind is the
    ticket's, and the stage goes on the part's state record, as the node's state control sets it."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    started(run)
    status, body = api(web, '/api/task', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'task': 'Build the alarm.', 'nodes': [f'element:{alarm}'], 'kind': 'broken',
        'condition': 'unbuilt'}))
    assert status == 200
    ticket = body['results'][0]
    assert (ticket['kind'], ticket['condition']) == ('broken', '')
    stated = [record for record in store.work(Node('element', alarm), None, True, limit=0).results if not record.task]
    assert [record.condition for record in stated] == ['unbuilt']
    status, body = api(web, '/api/task', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'task': 'x', 'nodes': [f'element:{alarm}'], 'kind': 'sideways'}))
    assert status == 400 and "'sideways' is not a kind of ticket" in body['error']


@pytest.mark.req('MAP-050')
def test_role_never_binds_the_page(run, web, mapped):
    """The page is the person's: a server started by a worker's command carries no role, and the page's writes are
    never refused by one, so the person adds a ticket and holds it there."""
    from metaform.data import Store
    json.loads(run('web', '--json', cwd=mapped, env={'METAFORM_ROLE': 'worker', 'METAFORM_WORK': 'w1'}).stdout)
    status, body = api(web, '/api/task', method='POST', headers=own_write(web), body=json.dumps({
        'project': 'proj', 'task': 'The person\'s work.', 'nodes': ['element:code.timer.kitchen'], 'hold': True}))
    assert status == 200, body
    assert 'The person\'s work.' in [record.task for record in Store('proj').work(open=True, limit=0).results]


# What the server answers, checked without a browser: these ran inside browser tests, which the default run leaves out.

@pytest.fixture
def threaded(home):
    """The web server in a thread of this process, on a port of its own, for a test of what it answers: no server
    process and no browser."""
    import threading

    from metaform.modules.web.server import Server
    server = Server('127.0.0.1', 0, 'nonce')
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.mark.req('MAP-052')
@pytest.mark.req('MAP-059')
@pytest.mark.req('VIEW-024')
def test_the_exports_the_server_answers_are_the_documents_the_commands_write(run, mapped, threaded):
    """The page and the command give one document, written by one piece of the chassis; the XML holds what the
    layers in view hold, so a hidden layer and a layer masked at an address leave nothing in it. Both are served with
    the map module off."""
    import xml.etree.ElementTree as ET
    markdown = run('map', 'markdown', cwd=mapped).stdout
    assert '## dish timer' in markdown
    status, body, headers = request(threaded, '/api/markdown?project=proj')
    assert status == 200 and body == markdown and headers['Content-Type'].startswith('text/markdown')
    around = request(threaded, '/api/markdown?project=proj&address=code.timer.kitchen')[1]
    assert around == run('map', 'markdown', 'address=code.timer.kitchen', cwd=mapped).stdout
    xml = run('map', 'xml', cwd=mapped).stdout
    status, body, headers = request(threaded, '/api/xml?project=proj')
    assert status == 200 and body == xml and headers['Content-Type'].startswith('application/xml')
    addresses = {element.get('namespace_address') for element in ET.fromstring(xml).iter('element')}
    assert {'exterior.cook', 'code.timer.kitchen', 'code.loop.tick', 'code.timer.kitchen.display'} <= addresses
    assert 'code.secret' not in addresses and 'code.alarm.audible.loud' not in addresses and 'code.gone' not in addresses
    assert ('broken', 'drifts') in {(work.get('condition'), work.text) for work in ET.fromstring(xml).iter('work')}
    run('disable', 'map')
    assert request(threaded, '/api/markdown?project=proj')[:2] == (200, markdown)
    assert request(threaded, '/api/xml?project=proj')[:2] == (200, xml)


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-040')
def test_a_start_the_server_is_asked_for_is_refused_as_the_command_refuses_it(run, mapped, threaded):
    """A ticket whose session is live is not started again, and an agent that cannot start is refused with its
    reason, from the command and from the page's request alike."""
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    store = Store('proj')
    busy = store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Busy ticket').id
    live_session(busy)
    for verb in ('start', 'run'):
        refused = run('dispatch', verb, busy, 'codex', cwd=mapped, ok=False)
        assert refused.returncode != 0 and busy in refused.stderr and 'session' in refused.stderr
    status, said = api(threaded, '/api/dispatch-start', method='POST', headers=own_write(threaded),
                       body=json.dumps({'project': 'proj', 'work_id': busy, 'agent': 'codex'}))
    # refusals name the ticket, never its 32-hex id (UX review round 2, held-and-signals F6)
    assert status == 400 and '"Busy ticket"' in said['error'] and 'session' in said['error']
    run('set', '--dispatch-codex', 'metaform-nonexistent-acp-adapter', cwd=mapped)
    free = store.add_work(Node('element', 'exterior.cook'), 'unbuilt', task='Nothing runs this yet').id
    status, said = api(threaded, '/api/dispatch-start', method='POST', headers=own_write(threaded),
                       body=json.dumps({'project': 'proj', 'work_id': free, 'agent': 'codex'}))
    assert status == 400 and 'not found' in said['error']
    assert store.ticket(free).work.taken is None


@pytest.mark.req('VIEW-039')
def test_a_message_to_a_ticket_whose_agent_has_not_started_is_kept_and_read_when_it_starts(
        run, home, project_folder, threaded, tmp_path, monkeypatch):
    """A click on an agent's figure whose ticket had no session yet, a specialist owner's or one reserved and not
    started, opened a chat whose message went nowhere (2026-10-21). The message route keeps it on the ticket's
    assignment, and the session reads it as the person's own message once it starts."""
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules.dispatch import own_store
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually
    from metaform.modules.orchestration.state import SERVICE
    agent = Dispatch(run, home, project_folder, tmp_path, orchestration=True)
    gates = tmp_path / 'turns'
    gates.mkdir()
    for name, value in agent.env('replace', FAKE_ACP_TURN_GATES=str(gates)).items():
        if name.startswith('FAKE_'):
            monkeypatch.setenv(name, value)  # the runner the assignment launches is the fake agent, logging
    # the ticket's agent, model and thinking level as the person chose them, so its own session launches without
    # waiting for Jev or the Facilitator to choose them
    with Store('proj', module='map').tables() as tx:
        tx.insert('ticket_settings', {'work_id': agent.id, 'agent': 'claude'})
    with own_store(agent.store).tables() as tx:
        tx.insert('ticket_options', {'work_id': agent.id, 'model': 'default', 'effort': 'medium', 'seq': 1})
    owner = context('orchestration', project_folder, project='proj', nouns={'work': agent.id, 'role': 'gc'})
    SERVICE.claim(owner)
    try:
        status, said = api(threaded, '/api/dispatch-message', method='POST', headers=own_write(threaded),
                           body=json.dumps({'project': 'proj', 'work_id': agent.id, 'text': 'start with the tests'}))
        assert status == 200 and said['held'] is True, said
        SERVICE.drain(owner)  # its launch: the session starts
        eventually(lambda: agent.received('session/prompt'))
        for turn in ('1', '2'):
            (gates / turn).touch()  # its opening turns end, whichever of them carries the person's words
        # read as the person wrote them, once, in the session's first turns, where notes kept for it are read
        said = eventually(lambda: [block['text'] for one in agent.received('session/prompt')
                                   for block in one['params']['prompt'] if 'start with the tests' in block.get('text', '')])
        assert len(said) == 1 and '\n\nstart with the tests' in f'\n\n{said[0]}', said
    finally:
        run('dispatch', 'stop-all', cwd=project_folder, ok=False)
        agent.close()


@pytest.mark.req('BASE-052')
@pytest.mark.req('VIEW-039')
def test_the_server_and_the_command_read_the_same_sessions_when_a_runner_dies(run, home, mapped, threaded, tmp_path):
    """A runner that dies with its session row still running reads as ended, the same from the command and from the
    server, while the row itself is left as the runner wrote it."""
    from metaform.modules.dispatch import end_group
    from metaform.modules.dispatch.tests.test_dispatch import Dispatch, eventually
    agent = Dispatch(run, home, mapped, tmp_path)
    try:
        agent.start('hold')  # a turn still executing
        eventually(lambda: agent.logged('grandchild'))
        sessions = '/api/dispatch-sessions?project=proj&thread=false'
        assert api(threaded, sessions)[1]['sessions'][0]['state'] == 'running'
        agent.process.kill()
        agent.process.wait()
        cli = json.loads(run('dispatch', 'sessions', 'thread=false', '--json', cwd=mapped).stdout)
        assert cli == api(threaded, sessions)[1] and cli['sessions'][0]['state'] == 'ended'
        assert agent.session().extra['state'] == 'running'
    finally:
        agent.close()
        for pid in agent.logged('pid'):
            end_group(pid)


@pytest.mark.req('STORE-041')
def test_the_server_refuses_to_remove_the_active_base_and_activates_another(run, mapped, threaded):
    """Neither Activate nor Remove acts on the active base: removing it is refused with the reason."""
    run('add', 'base', 'fresh', cwd=mapped)  # fresh is active now
    status, said = api(threaded, '/api/remove-base', method='POST', headers=own_write(threaded),
                       body=json.dumps({'project': 'proj', 'name': 'fresh', 'confirm': True}))
    assert status == 400 and 'active' in said['error']
    status, said = api(threaded, '/api/activate-base', method='POST', headers=own_write(threaded),
                       body=json.dumps({'project': 'proj', 'name': 'main'}))
    assert status == 400 and said['error'].startswith('This changes the active map')  # asked first, UX review round 1
    assert said['next'] == 'If you are sure: send confirm true'
    status, _ = api(threaded, '/api/activate-base', method='POST', headers=own_write(threaded),
                    body=json.dumps({'project': 'proj', 'name': 'main', 'confirm': True}))
    assert status == 200
    active = [line.split()[0] for line in run('list', 'bases', cwd=mapped).stdout.splitlines() if '(active)' in line]
    assert active == ['main']


@pytest.mark.req('VIEW-042')
def test_a_reference_is_looked_up_as_a_spec_record_a_ticket_or_nothing_with_its_reason(mapped, threaded,
                                                                                      monkeypatch):
    """What a reference in text stands for: a spec record by its code, a ticket by a prefix of its id, and nothing,
    with a plain reason, for what names nothing; the rich/ folder is never read."""
    from metaform.data import Node, Store
    (mapped / 'specifications').mkdir()
    (mapped / 'specifications' / '01-map.md').write_text('# Map\n\n### MAP-001 A record\n\nWhat it says.\n',
                                                          encoding='utf-8')
    (mapped / 'rich').mkdir()
    (mapped / 'rich' / 'notes.md').write_text('private\n', encoding='utf-8')
    ticket = Store('proj').add_work(Node('element', 'exterior.cook'), None, task='Name the cook').id

    # every reference a page drew is answered in one read, the tickets read once for all of them
    from metaform.data import store as stores
    reads, invoke = [], stores.operations.invoke
    monkeypatch.setattr(stores.operations, 'invoke', lambda tx, name, *args, **kwargs: (
        reads.append(name) if name == 'work' else None) or invoke(tx, name, *args, **kwargs))
    status, said = api(threaded, f'/api/lookup?project=proj&refs=MAP-001+{ticket[:8]}+MAP-999+rich/notes.md+'
                                 f'{ticket[:9]}')
    assert status == 200 and len(reads) == 1
    found = said['found']
    record = found['MAP-001']
    assert (record['kind'], record['title'], record['text'], record['file']) == (
        'spec', 'MAP-001 A record', 'What it says.', 'specifications/01-map.md')
    assert found[ticket[:8]]['id'] == found[ticket[:9]]['id'] == ticket
    nothing = found['MAP-999']
    assert nothing['kind'] is None and 'MAP-999' in nothing['reason']
    assert found['rich/notes.md']['kind'] is None


@pytest.mark.browser
@pytest.mark.req('VIEW-039')
def test_chat_shows_busy_and_interrupts_a_turn_while_the_conversation_stays_available(
        run, web, mapped, browser, tmp_path, monkeypatch):
    from metaform.data import Node, Store
    log = tmp_path / 'chat-interrupt.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'ask')
    monkeypatch.setenv('FAKE_ACP_ASK_GATE', str(tmp_path / 'permission-gate'))
    run('enable', 'dispatch')
    run('set', '--no-dispatch-worktrees', cwd=mapped)
    work = Store('proj').add_work(Node('element', 'code.alarm.audible'), None, task='A quieter alarm').id
    run('dispatch', 'start', work, 'claude', cwd=mapped)
    try:
        started(run)
        page, problems, _ = opened(browser, web)
        page.wait_for_function('() => window.metaform.loaded()')
        page.wait_for_selector('#agents .agent', timeout=30000)
        page.click('#agents .agent')                                     # its thread, in the chat dock
        page.wait_for_selector('#helpdesk:not([hidden])')
        page.wait_for_function('() => document.querySelector("#helpdesk .status").textContent === "Busy"')
        page.wait_for_function('() => document.querySelector("#helpdesk .log").textContent.includes("Hello from fake")')
        assert page.locator('#helpdesk .status').text_content() == 'Busy'
        assert page.locator('#helpdesk .typing').is_visible(), 'busy persists after the first reply'
        assert page.locator('#helpdesk .waiting').text_content().endswith(' is working')   # quiet, its note on hover
        assert 'working on a task' in page.locator('#helpdesk .waiting').get_attribute('title')
        page.fill('#helpdesk .say', 'Draft to keep')
        page.click('#helpdesk .interrupt')
        page.wait_for_function('() => document.querySelector("#helpdesk .status").textContent === "Ready"', timeout=15000)
        assert page.locator('#helpdesk .interrupt').is_disabled()
        assert page.locator('#helpdesk .say').input_value() == 'Draft to keep'
        assert page.locator('#helpdesk .typing').count() == 0
        page.fill('#helpdesk .say', 'Continue after interruption')
        page.press('#helpdesk .say', 'Enter')
        logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt'
                  and entry['message']['params']['prompt'] == [{'type': 'text', 'text': 'Continue after interruption'}])
        assert Store('proj').ticket(work).work.taken
        assert problems == []
    finally:
        run('dispatch', 'stop', work, cwd=mapped, ok=False)


@pytest.mark.req('BASE-060')
def test_the_build_panel_lists_its_choices_builds_an_archive_with_progress_and_downloads_it(run, home, web, mapped):
    import io
    import zipfile
    (mapped / 'main.py').write_text('print("hi")\n', encoding='utf-8')
    started(run)
    status, options = api(web, '/api/build/options')
    assert status == 200
    assert [kind['id'] for kind in options['kinds']] == ['archive', 'project', 'installer', 'full']
    remote = {module['id']: module['remote'] for module in options['modules']}
    assert remote['map'] is True and remote['web'] is False
    assert next(shape for shape in options['shapes'] if shape['id'] == 'remote')['modules'] == \
        sorted(name for name, on in remote.items() if on)
    assert {'map', 'intake', 'mcp', 'web', 'dispatch'} <= set(options['defaults']['installer'])  # start's chain
    assert options['prompts']['wrapper']['name'] == 'remote_wrapper' and '{task}' in options['prompts']['wrapper']['text']
    heard, _ = events_on(web)
    own = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'}
    body = json.dumps({'kind': 'archive', 'project': 'proj', 'files': True})
    assert request(web, '/api/build', method='POST', body=body, headers={'Content-Type': 'application/json'})[0] == 403
    status, started_build = api(web, '/api/build', method='POST', body=body, headers=own)
    assert status == 200 and started_build['stages'] == ['pack project', 'write']
    build_id = started_build['build_id']
    deadline = time.monotonic() + 30
    while not any(event.get('topic') == 'build' and event['payload']['state'] != 'running' for event in heard):
        assert time.monotonic() < deadline, heard
        time.sleep(0.05)
    states = [event['payload'] for event in heard if event.get('topic') == 'build']
    assert [state['stage'] for state in states] == ['pack project', 'write', 'write']
    assert states[-1]['state'] == 'done' and states[-1]['build_id'] == build_id, states[-1]
    status, found = api(web, f'/api/build/{build_id}')
    assert status == 200 and found['file'] == states[-1]['file'] and found['file'].startswith('proj-')
    status, _, headers = request(web, f'/api/build/{build_id}/download')
    assert status == 200 and headers['Content-Disposition'] == f'attachment; filename="{found["file"]}"'
    downloaded = next((home / 'builds').rglob(found['file'])).read_bytes()
    assert int(headers['Content-Length']) == len(downloaded) == found['size']
    with zipfile.ZipFile(io.BytesIO(downloaded)) as held:
        assert {'origin.zip', '.metaform/manifest', '.metaform/data/export.json'} <= set(held.namelist())
    assert api(web, '/api/build', method='POST', body=json.dumps({'kind': 'full', 'project': 'proj'}),
               headers=own) == (400, {'error': 'A full build carries no project, BASE-048.',
                                      'next': 'metaform build kind=project project=<id>'})


@pytest.mark.req('VIEW-030')
@pytest.mark.req('VIEW-008')
def test_escape_closes_only_the_window_on_top_and_the_focus_goes_back_to_the_control_that_opened_it(
        run, web, mapped, browser):
    """Every window, menu and popover is on one stack: Escape closes the one on top and nothing else, never moving the
    map behind it, and the focus goes back to the control that opened it; while a window is open over the map, the
    map's keys rest."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    kitchen = at['code.timer.kitchen']
    selected = lambda: page.evaluate('window.metaform.selected()')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.click('#adminBtn')
    page.wait_for_function('() => document.activeElement.closest("#adminbox")')  # the focus moved into the menu
    page.keyboard.press('Escape')
    assert page.is_hidden('#adminbox') and page.evaluate('document.activeElement.id') == 'adminBtn'
    assert selected() == kitchen  # the map behind the menu did not back out
    page.click('#boardBtn')
    page.wait_for_selector('#board:not([hidden])')
    page.click('#board .add')  # Add card opens the task editor over the board
    page.wait_for_selector('#task:not([hidden])')
    assert page.evaluate('window.metaform.overlays()') == ['board', 'task']
    page.keyboard.press('Escape')
    assert page.is_hidden('#task') and page.is_visible('#board')
    assert page.evaluate('document.activeElement.classList.contains("add")')  # back on the board's Add card
    page.keyboard.press('ArrowDown')  # the map's keys rest while the board is open
    assert selected() == kitchen
    page.keyboard.press('Escape')
    assert page.is_hidden('#board') and page.evaluate('document.activeElement.id') == 'boardBtn'
    assert page.evaluate('window.metaform.overlays()') == [] and problems == []


@pytest.mark.req('VIEW-004')
@pytest.mark.req('VIEW-008')
def test_slash_searches_the_map_and_the_result_chosen_is_selected_in_both_views(run, web, mapped, browser):
    """/ opens the search; the parts drawn are found as each letter is typed, the arrows and Enter choose one, and it is
    selected in both views as a click on it selects it, the keys going on with the map."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    page.keyboard.press('/')
    page.wait_for_selector('#search:not([hidden])')
    page.keyboard.type('audible')
    page.wait_for_selector('#search [role=option][aria-selected=true]')
    assert 'audible alarm' in page.inner_text('#search [role=option][aria-selected=true]')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.selected() === "{at["code.alarm.audible"]}"')
    assert page.is_hidden('#search')
    assert page.evaluate('[...document.querySelectorAll("#map2d svg g.node.sel")].map(g => g.dataset.title)') == [
        'code.alarm.audible']
    assert page.evaluate('Boolean(document.activeElement.closest("#stage, #map2d"))')  # the keys go on with the map
    assert problems == []


@pytest.mark.req('VIEW-031')
def test_a_memory_deleted_from_the_panel_is_made_again_by_undo(run, web, mapped, browser):
    """A memory whose nodes the map still holds is deleted at once, with Undo: Undo makes it again with its
    observations, its join to its node and its relation."""
    remember(run, mapped, 'create_entities', [entity('countdown drift', 'Drifts under load.')], 'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'Too quiet.')], 'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'quiet tone', 'relationType': 'drives'}])
    whole = lambda: json.loads(run('memory', 'graph', '--json', cwd=mapped).stdout)
    drawn = '() => window.metaform.loaded() && window.metaform.graph().nodes.some(node => node.id === "e:countdown drift")'
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    set_layer(page, 'memory', True)
    page.keyboard.press('Escape')
    page.wait_for_function(drawn)
    page.evaluate('window.metaform.select("e:countdown drift")')
    page.click('#p-object button.forget')
    page.wait_for_function(f'() => !({drawn})()', timeout=10000)
    assert 'countdown drift' not in [one['name'] for one in whole()['entities']]
    page.click('#toast button:has-text("Undo")')
    page.wait_for_function(drawn, timeout=10000)
    again = whole()
    drift = next(one for one in again['entities'] if one['name'] == 'countdown drift')
    assert [one['content'] for one in drift['observations']] == ['Drifts under load.']
    assert [(one['from'], one['relationType'], one['to']) for one in again['relations']] == [
        ('countdown drift', 'drives', 'quiet tone')]
    assert [(one['entity'], one['address']) for one in again['joins'] if one['entity'] == 'countdown drift'] == [
        ('countdown drift', 'code.timer.kitchen')]
    assert problems == []


@pytest.mark.req('VIEW-002')
def test_the_page_is_told_the_project_of_the_folder_metaform_web_last_ran_in(run, web, tmp_path):
    """The folder `metaform web` runs in chooses which project the page shows first, whether it started the server or
    found it running; a folder of no project chooses none."""
    for name in ('alpha', 'beta', 'outside'):
        (tmp_path / name).mkdir()
    for name in ('alpha', 'beta'):
        run('add', 'project', name, str(tmp_path / name))
    opened_first = lambda: json.loads(request(web, '/api/projects')[1])['opened']
    assert started(run, tmp_path / 'beta')['state'] == 'started' and opened_first() == 'beta'
    assert started(run, tmp_path / 'alpha')['state'] == 'running' and opened_first() == 'alpha'
    started(run, tmp_path / 'outside')
    assert opened_first() is None
    # `recent` is the project the person's page showed last, never the one whose files background work wrote last
    from metaform import home as metaform_home
    from metaform.data import Store
    shown = lambda project: request(web, '/api/shown', method='POST', body=json.dumps({'project': project}), headers={
        'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'application/json'})
    assert json.loads(shown('alpha')[1])['kept'] is True
    Store('beta', module='dispatch')
    for entry in metaform_home.project_folder('beta').iterdir():
        os.utime(entry, (time.time() + 60, time.time() + 60))
    assert json.loads(request(web, '/api/projects')[1])['recent'] == 'alpha'


@pytest.mark.browser
@pytest.mark.req('VIEW-002')
def test_a_page_opened_after_choosing_a_project_opens_on_it(run, web, mapped, browser, tmp_path):
    """The chat reaches the system agent of the project shown, so a new page opens on the project the person last had
    open in this browser, before the project of the folder `metaform web` ran in."""
    from metaform.data import Store
    (tmp_path / 'beta').mkdir()
    run('add', 'project', 'beta', str(tmp_path / 'beta'))
    build(Store('beta'))
    started(run, mapped)
    assert json.loads(request(web, '/api/projects')[1])['opened'] == 'proj'
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    context.add_init_script(RETURNING)
    own = f'http://127.0.0.1:{web}/'
    shown = "() => window.metaform && new URLSearchParams(location.hash.slice(1)).get('p')"
    first = context.new_page()
    first.goto(own)
    assert first.wait_for_function(shown).json_value() == 'proj'
    first.select_option('#proj', 'beta')
    first.wait_for_function("() => location.hash.includes('p=beta')")
    second = context.new_page()
    second.goto(own)
    assert second.wait_for_function(shown).json_value() == 'beta'
    context.close()


@pytest.mark.req('VIEW-049')
@pytest.mark.req('BASE-060')
def test_the_build_panel_builds_an_archive_and_the_browser_saves_the_file(run, web, mapped, browser):
    """The person picks Project Archive and presses Build once; the bar runs through the build's stages and the browser
    saves the file, with no folder to go and find it in, and the panel keeps the choice for the project."""
    (mapped / 'main.py').write_text('print("hi")\n', encoding='utf-8')
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#buildBtn')
    page.click('#build .kindcard[data-kind="archive"]')
    assert page.get_attribute('#build .kindcard[data-kind="archive"]', 'aria-checked') == 'true'
    assert page.locator('#build .modules').count() == 0 and page.is_checked('#build input[role=switch]')
    with page.expect_download(timeout=60000) as saved:
        page.click('#build .go')
    name = saved.value.suggested_filename
    assert name.startswith('proj-') and name.endswith('.zip'), name
    page.wait_for_selector(f'#build .run .result:has-text("{name}")')
    assert page.eval_on_selector_all('#build .buildsteps li', 'found => found.map(one => one.className)') == ['done', 'done']
    assert page.evaluate('JSON.parse(localStorage.getItem("metaform.build.proj")).kind') == 'archive'
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-039')
def test_an_agents_permission_request_is_answered_from_its_own_buttons(run, web, mapped, browser, tmp_path,
                                                                       watch_dispatch):
    """The agent asks before it writes a file; the request shows with the agent's own options as buttons, the person
    presses one, and the agent is told that option."""

    from metaform.data import Node, Store
    work = Store('proj').add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='Write notes.txt').id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#boardBtn')
    page.click(f'#board .card[data-id="{work}"] button.start')
    choose_agent(page, '#dispatch', 'codex')
    page.click(f'#dispatch .ticket[data-id="{work}"] button.start')
    page.wait_for_selector('#dockTab.asks', timeout=60000)              # the chat's tab counts the request waiting
    page.keyboard.press('Escape')
    page.evaluate(f'window.metaform.agent("{work}")')                     # its thread, in the chat dock
    card = '#helpdesk .permission.waiting'
    page.wait_for_selector(f'{card} .answers button', timeout=30000)
    assert page.eval_on_selector_all(f'{card} .answers button[data-option]', 'found => found.map(one => one.dataset.option)') \
        == ['allow', 'reject'] and 'Write notes.txt' in page.inner_text(card)
    page.click(f'{card} button[data-option="reject"]')
    assert logged_by(log, lambda entry: 'permission' in entry)['permission']['outcome'] \
        == {'outcome': 'selected', 'optionId': 'reject'}
    page.wait_for_selector('#helpdesk .permission.answered', timeout=30000)
    assert 'Reject' in page.inner_text('#helpdesk .permission.answered')
    assert problems == []


@pytest.mark.browser
@pytest.mark.req('VIEW-039')
def test_permission_requests_off_screen_pop_up_stacked_and_allow_all_answers_the_sessions_later_ones(
        run, web, mapped, browser, tmp_path, dispatch_runners):
    """code.interface.graphical#72: requests whose thread is not on screen show in one non-modal pop-up, 1 of N, with
    every option of the agent, Allow all and how the session's requests are answered; a thread open on screen takes its
    own request back, an answer from the pop-up reaches its agent, and Allow all, confirmed once, answers the request
    and the session's later one with no pop-up."""
    from metaform.data import Node, Store
    again, log = tmp_path / 'again', tmp_path / 'fake.jsonl'  # one log, so each agent's session has its own id
    run('enable', 'dispatch')
    run('set', '--no-dispatch-worktrees', cwd=mapped)
    works = {}
    for agent in ('claude', 'codex', 'antigravity'):
        works[agent] = Store('proj').add_work(Node('element', 'code.alarm.audible'), None, task=f'Notes by {agent}').id
        env = {'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask', **({'FAKE_ACP_ASK_AGAIN': str(again)}
                                                                    if agent == 'claude' else {})}
        begun = json.loads(run('dispatch', 'start', works[agent], agent, '--json', cwd=mapped, env=env).stdout)
        dispatch_runners.append((begun, mapped, log))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    count = lambda said: page.wait_for_function(
        '(said) => document.querySelector("#asking:not([hidden]) .stackcount")?.textContent === said', arg=said,
        timeout=60000)
    count('1 of 3')                                                    # three agents' requests, one window
    card = '#asking .permission.waiting'
    assert page.eval_on_selector_all(f'{card} .answers button[data-option]', 'found => found.map(b => b.dataset.option)') \
        == ['allow', 'reject'] and page.is_visible(f'{card} .allowall')
    assert page.eval_on_selector(f'{card} .answering select', 'one => one.value') == 'ask_all'
    assert 'project setting' in page.inner_text(f'{card} .answering')
    assert page.evaluate('getComputedStyle(document.querySelector("#asking")).position') == 'fixed'
    page.click('#asking .next')
    count('2 of 3')
    page.click('#asking .openchat')                                    # its thread on screen takes its request back
    page.wait_for_selector('#helpdesk:not([hidden]) .permission.waiting .answering select', timeout=30000)
    count('1 of 2')
    page.wait_for_function('() => !document.querySelector("#helpdesk").getAnimations().length'
                           ' && !document.querySelector("#dock").getAnimations().length')  # the chat has opened
    assert page.evaluate('''() => {
        const a = document.querySelector('#asking').getBoundingClientRect();
        const b = document.querySelector('#helpdesk').getBoundingClientRect();
        return a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top;
    }'''), 'the pop-up stands beside the open chat, neither covering the other'
    page.evaluate("import('/page/app/dock/helpdesk.js').then(part => part.putChatAway())")
    count('1 of 3')
    shown = lambda: page.inner_text("#asking .bar .title b").lower()

    def show(agent):
        for _ in range(3):
            if agent in shown():
                return
            page.click('#asking .next')
            page.wait_for_timeout(100)
        raise AssertionError(f'{agent} is not in the pop-up')
    show('codex')
    page.click(f'{card} button[data-option="reject"]')                 # an answer from the pop-up reaches its agent
    assert logged_by(log, lambda entry: 'permission' in entry)['permission']['outcome'] \
        == {'outcome': 'selected', 'optionId': 'reject'}
    count('1 of 2')
    show('claude')
    page.click(f'{card} .allowall')
    page.click('#confirm .keep')                                       # Keep asking: nothing is approved
    page.wait_for_timeout(300)
    assert page.is_visible(f'{card} .allowall') and log.read_text(encoding='utf-8').count('{"permission"') == 1
    page.click(f'{card} .allowall')
    page.click('#confirm button.confirm')
    assert logged_by(log, lambda entry: entry.get('permission', {}).get('outcome', {}).get('optionId') == 'allow')
    page.wait_for_function('() => !document.querySelector("#asking .stackcount")', timeout=30000)
    assert 'antigravity' in shown()
    again.touch()                                                      # the session's later request: no pop-up
    assert logged_by(log, lambda entry: 'permission_again' in entry)['permission_again']['outcome'] \
        == {'outcome': 'selected', 'optionId': 'allow'}
    page.wait_for_timeout(1500)
    assert 'antigravity' in shown() and page.locator('#asking .stackcount').count() == 0
    assert problems == []


@pytest.mark.req('VIEW-039')
def test_an_agents_question_is_answered_from_its_card_and_its_notices_show(run, web, mapped, browser, tmp_path,
                                                                          watch_dispatch):
    """ACP's elicitation on the page: the head agent's AskUserQuestion, a choice and its "Other" box, shows as a card
    with the choices as buttons beside Decline; the person presses one and the agent gets that choice. Only the sentinel
    and the head agent ask the person, VIEW-045. The agent's session notice is a line of its own."""
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold', 'FAKE_ACP_ELICIT': 'ask',
                              'FAKE_ACP_NOTICE': '1'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    work = page.evaluate("""fetch('/api/system-chat', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({project: 'proj', agent: 'codex'})}).then(r => r.json())""")['work_id']
    page.wait_for_selector('#dockTab.asks', timeout=60000)              # a question waiting counts on the tab
    page.keyboard.press('Escape')
    page.evaluate(f'window.metaform.agent("{work}")')
    card = '#helpdesk .elicitation.waiting'
    page.wait_for_selector(f'{card} .answers button', timeout=30000)
    assert page.eval_on_selector_all(f'{card} .answers button', 'found => found.map(one => one.textContent)') \
        == ['Red', 'Blue', 'Send', 'Decline'] and 'Which colour?' in page.inner_text(card)
    assert 'MCP server unavailable' in page.inner_text('#helpdesk .agent-notice.warning')
    page.click(f'{card} .answers button:text-is("Blue")')
    assert logged_by(log, lambda entry: 'elicited' in entry)['elicited'] \
        == {'action': 'accept', 'content': {'question_0': 'Blue'}}
    page.wait_for_selector('#helpdesk .elicitation.answered', timeout=30000)
    run('dispatch', 'stop', work, cwd=mapped)
    assert problems == []


@pytest.mark.req('CLI-011')
@pytest.mark.req('VIEW-045')
def test_a_consent_card_shows_what_runs_and_the_persons_allow_answers_the_waiting_call(run, web, mapped, browser,
                                                                                     tmp_path, watch_dispatch):
    """UX review round 2, person-consent F5: the system agent's call that is the person's decision waits on a card in
    its chat that says who asks, the caution and the command it runs; Allow once answers the waiting call, and the
    card then says it was allowed once."""
    import threading

    from metaform.data import Store
    from metaform.modules.dispatch import ask_consent
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    work = page.evaluate("""fetch('/api/system-chat', {method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({project: 'proj', agent: 'codex'})}).then(r => r.json())""")['work_id']
    deadline = time.monotonic() + 60
    while True:  # the session's runner, once it holds its session
        rows = json.loads(run('dispatch', 'sessions', f'id={work}', '--json', cwd=mapped).stdout)['sessions']
        runner = next((row['runner'] for row in rows if row.get('state') == 'running' and row.get('runner')), None)
        if runner or time.monotonic() > deadline:
            break
        time.sleep(0.1)
    assert runner, rows
    answers: list[dict] = []
    asking = threading.Thread(target=lambda: answers.append(ask_consent(
        Store('proj'), 'Switching to fresh takes main out of view.', tool='map_add-base',
        command='metaform map add-base name=fresh --confirm', caution='Switching to fresh takes main out of view.',
        wait=60, work=work, runner=runner)))
    asking.start()
    page.evaluate(f'window.metaform.agent("{work}")')
    card = '#helpdesk .elicitation.waiting'
    page.wait_for_selector(f'{card} .answers button', timeout=30000)
    shown = page.inner_text(card)
    assert 'asks for your consent' in shown and 'Switching to fresh takes main out of view.' in shown
    assert 'metaform map add-base name=fresh --confirm' in shown
    assert page.eval_on_selector_all(f'{card} .answers button', 'found => found.map(one => one.textContent)') \
        == ['Allow once', 'Decline']
    page.click(f'{card} .answers button:text-is("Allow once")')
    asking.join(timeout=30)
    assert answers and answers[0]['action'] == 'accept', answers
    page.wait_for_selector('#helpdesk .elicitation.answered:has-text("Allowed once")', timeout=30000)
    run('dispatch', 'stop', work, cwd=mapped)
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_an_intake_is_started_from_the_page_with_the_agent_the_person_chose(run, home, web, browser, tmp_path,
                                                                             dispatch_runners):
    """A project with no map offers its intake over the map; the person chooses the agent, adds a note and starts it,
    and that agent runs the intake with the note, holding no ticket, while a bar over the map says it runs. The
    Administration menu's Run an intake… opens the same box."""
    folder, log = tmp_path / 'fresh', tmp_path / 'fake.jsonl'
    folder.mkdir()
    run('add', 'project', 'fresh', str(folder))
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask'})
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.goto(f'http://127.0.0.1:{web}/#p=fresh')
    page.wait_for_selector('#emptyStage:not([hidden])', timeout=60000)
    page.click('#adminBtn')                                             # the Intake button opens the intake's box
    page.click('#intakeBtn')
    page.wait_for_selector('#intake:not([hidden])')
    page.click('#intake .cancel')
    page.click('#emptyStage .start')                                    # and so does the empty map's Start
    page.wait_for_selector('#intake:not([hidden])')
    choose_agent(page, '#intake', 'claude')                            # not the default, so the choice is what starts
    page.fill('#intake textarea.note', 'Map the command line first.')
    with page.expect_response(lambda response: '/api/dispatch-intake' in response.url) as answered:
        page.click('#intake .start')
    started_intake = answered.value.json()
    dispatch_runners.append((started_intake, folder, log))
    assert started_intake['agent'] == 'claude' and started_intake['work_id'].startswith('intake-'), started_intake
    page.wait_for_selector('#intakeBar:not([hidden]):has-text("Claude Code")', timeout=30000)
    told = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt')
    assert 'Map the command line first.' in told['message']['params']['prompt'][0]['text']
    assert api(web, '/api/work?project=fresh')[1]['results'] == []    # an intake holds no ticket
    assert page.is_hidden('#emptyStage') and problems == []


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
@pytest.mark.skipif(os.name == 'nt', reason='the slow start is a POSIX shell script')
def test_an_intake_launched_from_the_command_line_shows_starting_on_the_page_with_a_stop_that_works(
        run, home, web, browser, tmp_path, dispatch_runners):
    """UX review round 1, 2026-10-17 (cross-surface F1, F5): an intake launched from the command line, its agent slow
    to start, is shown on an open page as starting within moments, never the empty map's Start the intake; a second
    is not offered there; and the bar's Stop ends it before its agent starts, the empty map returning."""
    folder, log = tmp_path / 'cli', tmp_path / 'fake.jsonl'
    folder.mkdir()
    run('add', 'project', 'cli', str(folder))
    run('enable', 'dispatch')
    slow = tmp_path / 'slow-agent.sh'
    slow.write_text(f'#!/bin/sh\nsleep 60\nexec "{sys.executable}" "{FAKE_AGENT}" "$@"\n', encoding='utf-8')
    slow.chmod(0o755)
    run('set', '--dispatch-claude', str(slow), cwd=folder)
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'})
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.goto(f'http://127.0.0.1:{web}/#p=cli')
    page.wait_for_selector('#emptyStage:not([hidden])', timeout=60000)
    started = json.loads(run('dispatch', 'intake', 'agent=claude', '--json', cwd=folder,
                             env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}).stdout)
    dispatch_runners.append((started, folder, log))
    page.wait_for_selector('#intakeBar:not([hidden]) .doing:has-text("Starting")', timeout=5000)
    assert page.is_hidden('#emptyStage')
    page.click('#adminBtn')
    page.click('#intakeBtn')                                            # no second intake is offered
    page.wait_for_selector('#toast:has-text("An intake is starting")', timeout=5000)
    assert page.is_hidden('#intake')
    page.click('#intakeBar button:has-text("Stop")')
    with page.expect_response(lambda response: '/api/dispatch-stop' in response.url) as answered:
        page.click('#confirm button.confirm')
    assert answered.value.ok and answered.value.json()['how'] == 'stopped while starting', answered.value.json()
    page.wait_for_selector('#intakeBar', state='hidden', timeout=10000)
    page.wait_for_selector('#emptyStage:not([hidden])', timeout=10000)
    assert problems == []


@pytest.mark.req('VIEW-045')
def test_running_the_intake_again_offers_refine_and_fresh_intake(run, web, mapped, browser):
    """Mapped projects offer both modes. Refine stays default, Fresh sends new, and reopening restores Refine.
    Intercept launch requests so checking mode selection never starts an actual intake."""
    run('enable', 'dispatch')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes > 0', timeout=30000)
    page.click('#adminBtn')
    page.click('#intakeBtn')
    page.wait_for_selector('#intake:not([hidden])')
    assert page.get_by_label('Refine', exact=True).is_checked()
    assert page.get_by_label('Fresh intake', exact=True).is_visible()
    assert page.inner_text('#intake .start') == 'Refine'
    assert 'tickets' in page.inner_text('#intake .lead')
    choose_agent(page, '#intake', 'claude')
    sent = []
    page.route('**/api/dispatch-intake', lambda route: (sent.append(route.request.post_data_json), route.fulfill(
        status=400, content_type='application/json', body=json.dumps(
            {'error': 'stand-in', 'next': 'metaform dispatch intake resume=true'}))))
    page.click('#intake .start')
    page.wait_for_selector('#intake .failed:not([hidden])')
    assert sent and sent[0]['map'] == 'extend' and 'name' not in sent[0], sent
    page.get_by_label('Fresh intake', exact=True).check()
    assert page.inner_text('#intake .start') == 'Fresh intake'
    assert 'separate map' in page.inner_text('#intake .lead')
    assert page.is_hidden('#intake .suggest')
    page.click('#intake .start')
    page.wait_for_function('() => !document.querySelector("#intake .start").disabled')
    assert len(sent) == 2 and sent[1]['map'] == 'new' and 'name' not in sent[1], sent
    page.click('#intake .cancel')
    page.click('#adminBtn')
    page.click('#intakeBtn')
    assert page.get_by_label('Refine', exact=True).is_checked()
    assert page.is_visible('#intake .suggest')
    page.click('#intake .start')
    page.wait_for_selector('#intake .failed:not([hidden])')
    page.click('#intake .failed button:has-text("Take it over")')
    assert page.is_hidden('#intake .mapchoice')
    assert page.inner_text('#intake .start') == 'Take over the intake'
    assert 'existing map' in page.inner_text('#intake .lead')
    page.click('#intake .start')
    page.wait_for_function('() => !document.querySelector("#intake .start").disabled')
    assert len(sent) == 4 and sent[-1]['resume'] is True and 'map' not in sent[-1], sent
    page.unroute('**/api/dispatch-intake')
    status, body = page.evaluate('''() => fetch('/api/dispatch-intake', {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({project: 'proj', map: 'extend', name: 'v2'})}).then(r => r.json().then(b => [r.status, b]))''')
    assert status == 400 and 'new map' in body['error'], body
    assert [one for one in problems if 'status of 400' not in one] == []  # expected launch refusals, nothing else


@pytest.mark.req('VIEW-023')
def test_the_text_size_buttons_scale_the_page_and_reset_puts_every_size_back(run, web, mapped, browser):
    """The View menu's Text size list makes the whole page's text larger or smaller, header and panel alike, and the size
    is kept in this browser; the default puts every size back and forgets the choice. There is no button for it in the
    header: a button that grows with the text it sizes moves out from under the mouse."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    size = lambda selector: page.evaluate(f'parseFloat(getComputedStyle(document.querySelector("{selector}")).fontSize)')
    ui = lambda: page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--ui").trim()')
    before = ui(), size('#boardBtn'), size('#p-object h2')
    assert before[0] == '1.08'                                          # one step larger than the sizes were drawn at
    assert page.locator('#textUp, #textDown, #sizesReset').count() == 0
    page.locator('#textsize').select_option('5', force=True)  # its list, in the View menu
    assert float(ui()) > 1.08 and size('#boardBtn') > before[1] and size('#p-object h2') > before[2]
    assert page.evaluate('localStorage.getItem("metaform.textSize")') == ui()
    assert page.evaluate('document.querySelector("#textsize").value') == '5'  # the View menu's list says so
    page.reload(wait_until='commit')  # a reload draws as slowly as the first draw, so its wait is the same, `opened`
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=90000)
    assert float(ui()) > 1.08                                           # kept in this browser
    page.locator('#textsize').select_option('3', force=True)  # the default
    assert ui() == '1.08' and size('#boardBtn') == before[1]
    assert page.evaluate('localStorage.getItem("metaform.textSize")') is None
    assert problems == []


@pytest.mark.req('VIEW-028')
def test_the_side_column_moves_to_the_right_by_its_splitter_and_stays_there(run, web, mapped, browser):
    """Dragging the side column's splitter on to the right edge of the page puts the column on the right, and a reload
    keeps it there; its edge is grabbed anywhere along the column. The maps have no bar to drag it by."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.evaluate("localStorage.setItem('metaform.sideAt', 'left')")  # it opens on the right unless left is chosen
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    assert not page.evaluate("document.querySelector('.app').classList.contains('side-right')")
    assert page.evaluate("document.querySelectorAll('aside .bar2d, aside .bar3d').length") == 0
    edge = page.locator('#sideSplit').bounding_box()
    assert edge['height'] == pytest.approx(page.locator('aside').bounding_box()['height'], abs=1)
    y = edge['y'] + edge['height'] / 2
    page.mouse.move(edge['x'] + edge['width'] / 2, y)
    page.mouse.down()
    page.mouse.move(page.viewport_size['width'] - 100, y, steps=10)
    assert not page.evaluate("document.querySelector('.app').classList.contains('side-right')")  # not near enough
    page.mouse.move(page.viewport_size['width'] - 10, y, steps=4)
    page.mouse.up()
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.evaluate("document.querySelector('.app').classList.contains('side-right')")
    assert page.locator('aside').bounding_box()['x'] > page.viewport_size['width'] / 2
    assert not problems


# ---------- the settings screen: every setting, saved as metaform set saves it ----------

@pytest.mark.req('CLI-010')
@pytest.mark.req('VIEW-011')
def test_essentials_names_a_ready_unused_speaker_fits_the_screen_and_keeps_modules_compact(
        run, web, mapped, browser, monkeypatch):
    from metaform import settings
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'settings-readiness-test')
    run('enable', 'dispatch')
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#settingsGearBtn')
    speaker = '#settings .setrow[data-key="voice_tts"]'
    page.wait_for_selector(f'{speaker} .readyhint')
    notice = page.inner_text(f'{speaker} .readyhint')
    assert 'ElevenLabs' in notice and 'ready' in notice and '--voice-tts' in notice and 'elevenlabs' in notice
    assert settings.value('voice_tts', mapped) == 'browser'
    assert settings.value('voice_speak', mapped) == 'minimized'
    bounds = page.eval_on_selector('#settings .setmain', '''box => ({height: box.clientHeight,
      content: box.scrollHeight, rows: [...box.querySelectorAll('.setrow')].map(row =>
        [row.dataset.key, row.getBoundingClientRect().height])})''')
    assert bounds['content'] <= bounds['height'] + 1, bounds
    page.set_viewport_size({'width': 1280, 'height': 768})
    assert page.eval_on_selector('#settings .setmain', 'box => box.scrollHeight <= box.clientHeight + 1')
    page.screenshot(path=str(mapped.parent / 'essentials.png'))
    page.select_option(f'{speaker} select', 'elevenlabs')
    page.wait_for_function('''() => document.querySelector('#settings .setrow[data-key="voice_tts"] .state.ok')
      && !document.querySelector('#settings .setrow[data-key="voice_tts"] .readyhint')''')
    assert settings.value('voice_tts', mapped) == 'elevenlabs'
    page.click('#settings .setside button[data-page="modules"]')
    page.wait_for_selector('#settings .setlist.modules .module')
    cells = page.locator('#settings .setlist.modules .module')
    first, second = cells.nth(0).bounding_box(), cells.nth(1).bounding_box()
    assert abs(first['y'] - second['y']) < 2 and second['x'] > first['x']
    # A compact menu still saves through enable/disable and retains its keyboard switches.
    hello = '#settings .module[data-module="hello"] input'
    with page.expect_response(lambda response: '/api/modules' in response.url and response.request.method == 'POST'):
        page.check(hello)
    page.wait_for_function('''() => { const input = document.querySelector('#settings .module[data-module="hello"] input');
      return input?.checked && !input.disabled; }''')
    assert next(one for one in api(web, '/api/settings?project=proj')[1]['modules'] if one['id'] == 'hello')['enabled']
    page.fill('#settings .search', 'nothing matches this')
    page.click('#settings .close')
    page.click('#settingsGearBtn')
    page.wait_for_selector('#settings .setlist.essentials')
    assert page.input_value('#settings .search') == ''
    assert not problems and not remote


def setting_write(port, path, **given):
    return api(port, path, method='POST', headers=own_write(port), body=json.dumps({'project': 'proj', **given}))


# A process an AI tool started: it runs as `claude` and starts the program it is given by its interpreter's own path,
# never sys.executable, which under the name claude would be found on the PATH.
UNDER_CLAUDE = """import os, subprocess, sys
sys.exit(subprocess.run([os.environ['AGENT_PYTHON'], *sys.argv[1:]]).returncode)
"""
FORGED = """import http.client, json, sys
port = int(sys.argv[1])
connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
body = json.dumps({'project': 'proj', 'key': 'jev', 'value': True})
connection.request('POST', '/api/settings', body, {'Content-Type': 'application/json',
                                                   'Origin': f'http://127.0.0.1:{port}'})
answer = connection.getresponse()
print(answer.status, answer.read().decode())
"""

# The forged write sent from a process its parent leaves at once, so it is re-parented to init: `( cmd & )` in a shell.
REPARENTED = """import os, subprocess, sys
subprocess.Popen([os.environ['AGENT_PYTHON'], '-c', sys.argv[3], sys.argv[1]], stdout=open(sys.argv[2], 'w'))
"""
# A page asked for by an agent's process: the cookies it is given, one per line.
FETCHED = """import http.client, sys
connection = http.client.HTTPConnection('127.0.0.1', int(sys.argv[1]), timeout=10)
connection.request('GET', '/')
answer = connection.getresponse()
answer.read()
print('\\n'.join(answer.msg.get_all('Set-Cookie') or []))
"""


def under_claude(home, *args, **extra):
    """`args` run by a parent that runs as `claude` in the same home, with METAFORM_ROLE cleared. It is named by a
    path beside the base interpreter, so a Python before 3.14, which finds its library from that name, finds it there
    rather than looking up `claude` on the PATH."""
    env = {**os.environ, 'METAFORM_HOME': str(home), 'METAFORM_ROLE': '', 'METAFORM_HOLD': '',
           'AGENT_PYTHON': sys.executable, 'AGENT_NAME': os.path.join(sys.base_prefix, 'bin', 'claude'), **extra}
    return subprocess.Popen(['bash', '-c', 'exec -a "$AGENT_NAME" "$0" -c "$1" "${@:2}"', sys.executable, UNDER_CLAUDE,
                             *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@pytest.mark.req('CLI-011')
@pytest.mark.req('VIEW-011')
@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='the process behind a connection is read on Linux')
def test_a_persons_write_from_an_agents_process_is_refused_whatever_origin_it_sends(run, mapped, home):
    """UX review round 1, settings-govern-behavior F2: a write of the person's alone sent with the page's own Origin
    by an agent's process is refused, whether METAFORM_ROLE is set or cleared, since the server reads the process at
    the other end of the connection; the person's own write runs even when the server itself was started by an agent,
    since the command it runs carries the server's vouch."""
    from metaform import settings
    port = free_port()
    server = under_claude(home, '-m', 'metaform.modules.web.server', '--bind', '127.0.0.1', '--port', str(port),
                          '--nonce', 'test')
    assert server.stdout is not None
    ready = json.loads(server.stdout.readline())
    try:
        assert ready['port'] == port
        for extra in ({'METAFORM_ROLE': 'worker'}, {}):
            if extra:
                sent = subprocess.run([sys.executable, '-c', FORGED, str(port)], capture_output=True, text=True,
                                      timeout=60, env={**os.environ, 'METAFORM_HOME': str(home), **extra}, check=False)
                said = sent.stdout
            else:
                sender = under_claude(home, '-c', FORGED, str(port))
                said = sender.communicate(timeout=60)[0]
            assert said.startswith('403 ') and "is the person's to do on the page" in said, said
            assert settings.state('jev', mapped) == 'default', 'the forged write changed nothing'
        # person-consent F1: the same write re-parented to init passed every guard; the page's key now stops it
        out = home.parent / 'reparented.out'
        under_claude(home, '-c', REPARENTED, str(port), str(out), FORGED).communicate(timeout=60)
        deadline = time.monotonic() + 60
        while not out.read_text().strip():  # the re-parented sender, which nothing can wait on
            assert time.monotonic() < deadline, 'the re-parented sender did not answer'
            time.sleep(0.05)
        assert out.read_text().startswith('403 ') and 'carries no key' in out.read_text(), out.read_text()
        assert settings.state('jev', mapped) == 'default', 'the re-parented write changed nothing'
        given = under_claude(home, '-c', FETCHED, str(port)).communicate(timeout=60)[0]
        assert 'metaform_page_' not in given, given  # an agent's process is served the page without a key
        status, saved = setting_write(port, '/api/settings', key='jev', value=False)  # the person, from this process
        assert status == 200, saved
        assert settings.value('jev', mapped) is False
    finally:
        os.kill(int(ready['pid']), 15)  # the stop signal, as metaform web stop sends it; its parent then ends
        server.communicate(timeout=30)
    assert not list((home / 'run' / 'vouch').iterdir())  # its vouch went with it


def test_the_phone_checks_problem_is_never_a_notice_on_the_page(run, web, mapped, home, monkeypatch):
    """twilio's last check found a problem, and the page is told nothing of it: it goes to the person's system agent
    as the setup-not-working signal instead (ticket bd730760, 2026-10-15, reversing the phone's banner of 0a044360).
    No Twilio credential is here, so nothing asks Twilio."""
    for name in ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_API_KEY', 'TWILIO_API_SECRET'):
        monkeypatch.delenv(name, raising=False)
    run('set', '--twilio-number', '+15550100002')
    kept = home / 'run' / 'twilio'
    kept.mkdir(parents=True, exist_ok=True)
    problem = 'Your Twilio number sends its calls to https://gone.trycloudflare.com/voice, which does not answer.'
    (kept / 'check.json').write_text(json.dumps({'number': '+1••••••0002', 'checked': '2026-10-15T06:00:00Z',
                                                 'problems': [{'problem': problem, 'next': 'metaform twilio check'}]}),
                                     encoding='utf-8')
    started(run)
    assert api(web, '/api/notices?project=proj') == (200, {'notices': []})
    assert 'Notice from twilio' not in (home / 'run' / 'web.log').read_text(encoding='utf-8')
    assert api(web, '/api/notices?project=not-registered') == (200, {'notices': []})


@pytest.mark.req('VIEW-011')
def test_the_settings_screen_reads_every_setting_and_saves_resets_and_narrows_as_the_command_line_does(run, web, mapped):
    from metaform import settings
    started(run)
    status, found = api(web, '/api/settings?project=proj')
    rows = {row['key']: row for row in found['settings']}
    assert status == 200 and found['folder'] == str(mapped), found
    assert rows['debug']['kind'] == 'bool' and rows['debug']['state'] == 'default'
    assert rows['agents_may_set_control']['person_only'] is True and rows['agents_may_set_control']['label']
    assert {'chassis', 'map', 'web'} <= set(rows['modules']['choices']) and 'modules' in found['all_when_empty']
    assert {'id': 'web', 'enabled': True} == {key: one[key] for one in found['modules'] if one['id'] == 'web'
                                              for key in ('id', 'enabled')}
    status, saved = setting_write(web, '/api/settings', key='debug', value=True)
    assert status == 200 and settings.value('debug', mapped) is True, saved
    assert next(row for row in saved['settings'] if row['key'] == 'debug')['state'] == 'set'
    status, reset = setting_write(web, '/api/settings/reset', key='debug')
    assert status == 200 and settings.value('debug', mapped) is False
    assert next(row for row in reset['settings'] if row['key'] == 'debug')['state'] == 'default'
    # the checklist of the modules this folder shows: some of them, then every one again, which is all
    assert setting_write(web, '/api/settings', key='modules', value=['chassis', 'map'])[0] == 200
    assert settings.value('modules', mapped) == ['chassis', 'map']
    assert setting_write(web, '/api/settings', key='modules', value=[])[0] == 200
    assert settings.value('modules', mapped) == [] and settings.state('modules', mapped) == 'default'
    # a module turned on brings its settings, read with what its declaration says
    assert setting_write(web, '/api/modules', module='hello', enabled=True) == (200, {'module': 'hello', 'enabled': True})
    rows = {row['key']: row for row in api(web, '/api/settings?project=proj')[1]['settings']}
    assert rows['times']['owner'] == 'hello' and (rows['times']['min'], rows['times']['max']) == (1, 10)


@pytest.mark.req('VIEW-011')
def test_a_setting_the_command_line_would_refuse_is_refused_with_its_next_step_and_nothing_is_saved(run, web, mapped):
    from metaform import settings
    started(run)
    status, said = setting_write(web, '/api/settings', key='connect_instructions', value='everything')
    assert status == 400 and "no choice 'everything'" in said['error'] and said['key'] == 'connect_instructions', said
    status, said = setting_write(web, '/api/settings', key='debug', value='yes')
    assert status == 400 and 'true or false' in said['error'], said
    status, said = setting_write(web, '/api/settings', key='modules', value='chassis,map')  # a list is never its text
    assert status == 400 and 'send its items as an array' in said['error'] and said['key'] == 'modules', said
    assert settings.state('connect_instructions', mapped) == settings.state('debug', mapped) == 'default'
    assert settings.state('modules', mapped) == 'default'
    # a list of another project's own module, which this server never loads, is still saved item by item
    other = mapped.parent / 'other'
    place = other / '.metaform' / 'modules' / 'listy'
    place.mkdir(parents=True)
    (place / '__init__.py').write_text("from metaform import settings\nfrom metaform.module import Module\n"
                                       "SUPPORTED_OS = ('linux', 'macos', 'windows')\n"
                                       "settings.items('listy_things', [])\n"
                                       "MODULE = Module(id='listy', summary='Lists.', purpose='Lists. Details: "
                                       "metaform help listy.')\n")
    run('add', 'project', 'other', str(other))
    status, said = setting_write(web, '/api/settings', project='other', key='listy_things', value=['*.{js,ts}'])
    assert status == 200, said
    rows = json.loads(run('config', '--show', '--json', cwd=other).stdout)
    assert next(row['value'] for row in rows if row['key'] == 'listy_things') == ['*.{js,ts}']


@pytest.mark.req('VIEW-002')
def test_the_header_gives_back_room_in_steps_and_folds_only_when_its_row_still_does_not_fit(run, web, mapped, browser):
    """Ticket 7d: at 1920 px the whole row stands, the search with its words; narrower, the search keeps its icon
    alone, then the spacing tightens, then the labels go, and every control, Help, View's name and Settings included,
    stays on the row down to 1280 px; below 1100 px it folds behind the menu button."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate('window.metaform.pause3d(true)')
    state = '''() => { const shown = id => document.getElementById(id).getBoundingClientRect().width > 0;
      return [document.querySelector('header').className, shown('helpBtn'), shown('settingsGearBtn'),
        document.querySelector('#settingsBtn .lbl').getBoundingClientRect().width > 0,
        document.querySelector('#searchBtn .lbl').getBoundingClientRect().width > 0]; }'''
    frames = '() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))'
    seen = {}
    for width in (1920, 1700, 1600, 1280, 1000):
        page.set_viewport_size({'width': width, 'height': 800})
        page.evaluate(frames)                                            # the resize is handled with the next frame
        seen[width] = page.evaluate(state)
    assert seen[1920] == ['', True, True, True, True], seen              # it was folded at 1920, with Help
    assert seen[1700][0] in ('compact', 'compact tight') and seen[1700][1:4] == [True, True, True] \
        and seen[1700][4] is False, seen                                 # the search's icon before any button folds
    assert 'fold' not in seen[1600][0].split() and seen[1600][1:4] == [True, True, True], seen
    assert seen[1280][0] == 'compact tight tighter' and seen[1280][1:4] == [True, True, True], seen
    assert page.evaluate("document.getElementById('boardBtn').getBoundingClientRect().width") == 0  # folded at 1000
    assert problems == [], problems


@pytest.mark.req('VIEW-002')
def test_a_tools_description_cut_short_in_edit_toolbar_opens_in_place_and_enter_leaves_the_tool_where_it_is(
        run, web, mapped, browser):
    """Ticket 7d: the page's one helper for text cut short, shared with the Settings screen, opens a tool's
    description in Edit Toolbar… at a click or Enter; Enter on the text does not move the tool, as Enter on the tool
    does."""
    run('set', '--web-panes')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#toolbar .wsslot.more')
    page.click('#wsmenu button:has-text("Edit Toolbar")')
    page.wait_for_selector('#wsedit .wsedititem .why.cut')
    unread = page.evaluate('''() => [...document.querySelectorAll('#wsedit .why')].filter(one =>
      one.scrollWidth > one.clientWidth + 1 && !(one.classList.contains('cut') && one.tabIndex === 0)).length''')
    assert unread == 0                                                   # every description cut takes the click
    order = '() => [...document.querySelectorAll("#wsedit li[data-id]")].map(one => one.dataset.id)'
    before = page.evaluate(order)
    item = page.get_attribute('#wsedit .wsedititem:has(.why.cut)', 'data-id')
    why = f'#wsedit .wsedititem[data-id="{item}"] .why'
    page.focus(why)
    page.keyboard.press('Enter')
    page.wait_for_selector(f'#wsedit .wsedititem[data-id="{item}"].unfolded')
    assert page.evaluate(order) == before and page.get_attribute(why, 'aria-expanded') == 'true'
    page.click(why)                                                      # and a click folds it again
    page.wait_for_selector(f'#wsedit .wsedititem[data-id="{item}"]:not(.unfolded)')
    assert problems == [], problems


@pytest.mark.req('VIEW-011')
def test_a_settings_line_cut_short_opens_in_place_at_a_click_or_enter_and_folds_again(run, web, mapped, browser):
    """A module's line of help cut short with an ellipsis opens in place, wrapped, at a click or Enter, and folds again
    the same way; the cursor says it takes the click, and it stays open through the screen's redraws. Every row's
    control stands at the row's right edge, the line between taking the width."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#settingsGearBtn')
    edges = '''() => [...document.querySelectorAll("#settings .setrow")].filter(row => row.querySelector(".control > *"))
      .map(row => row.getBoundingClientRect().right
        - row.querySelector(".control > :last-child").getBoundingClientRect().right)'''
    page.wait_for_selector('#settings .setlist.essentials .setrow .control > *')
    assert max(page.evaluate(edges)) < 20                               # each control at its row's right edge
    page.click('#settings .setside button[data-page="modules"]')
    page.wait_for_selector('#settings .setrow.module .help.cut')
    assert max(page.evaluate(edges)) < 20
    name = page.get_attribute('#settings .setrow.module:has(.help.cut)', 'data-module')
    row = f'#settings .setrow.module[data-module="{name}"]'
    looks = f'''() => {{ const help = document.querySelector('{row} .help'), style = getComputedStyle(help);
      return [help.getBoundingClientRect().height, style.cursor, style.whiteSpace,
        help.getAttribute('aria-expanded')]; }}'''
    height, cursor, wrap, expanded = page.evaluate(looks)
    assert (cursor, wrap, expanded) == ('pointer', 'nowrap', 'false')
    page.click(f'{row} .help')                                          # a click opens it, wrapped
    page.wait_for_selector(f'{row}.unfolded')
    unfolded, _, wrap, expanded = page.evaluate(looks)
    assert unfolded > height * 1.5 and (wrap, expanded) == ('normal', 'true')
    page.evaluate('document.dispatchEvent(new Event("metaform:settings"))')  # read again elsewhere: it stays open
    page.wait_for_timeout(1000)
    assert page.is_visible(f'{row}.unfolded')
    page.click(f'{row} .help')                                          # and folds again
    page.wait_for_selector(f'{row}:not(.unfolded)')
    page.focus(f'{row} .help')                                          # Enter does the same
    page.keyboard.press('Enter')
    page.wait_for_selector(f'{row}.unfolded')
    page.keyboard.press('Enter')
    page.wait_for_selector(f'{row}:not(.unfolded)')
    assert problems == [], problems


@pytest.mark.req('VIEW-011')
def test_the_settings_screen_opens_from_the_agents_menu_and_saves_each_change_as_it_is_made(run, web, mapped, browser):
    from metaform import settings
    from metaform.data import Store
    run('enable', 'dispatch')
    with Store('proj', module='dispatch').tables() as tx:  # what Claude Code offered at its last session here
        tx.insert('catalog', {'agent': 'claude', 'version': '1', 'name': 'Claude', 'seen': '2026-10-14T00:00:00Z',
                              'seq': 1, 'settings': [{'id': 'mode', 'category': 'mode', 'type': 'select', 'options': [
                                  {'value': 'default', 'name': 'Manual'},
                                  {'value': 'acceptEdits', 'name': 'Accept edits', 'description': 'Accepts edits'}]}]})
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#settingsGearBtn')                                      # the gear opens it, on Essentials
    row = '#settings .setrow[data-key="{}"]'.format
    page.wait_for_selector(row('dispatch_agent'))
    side = page.eval_on_selector_all('#settings .setside button', 'all => all.map(one => one.dataset.page)')
    assert side[0] == 'essentials' and side[-2:] == ['advanced', 'modules'], side  # Modules last, under Advanced
    assert page.get_attribute('#settings .setside button[aria-current="page"]', 'data-page') == 'essentials'
    page.select_option(f'{row("dispatch_agent")} select', 'claude')     # the default agent: the gear and a pick
    page.wait_for_selector(f'{row("dispatch_agent")} .state.ok')
    assert settings.value('dispatch_agent', mapped) == 'claude'
    run('set', '--dispatch-agents', '3', cwd=mapped)                    # changed elsewhere, the screen follows, F13
    page.wait_for_function(f'''() => document.querySelector('{row("dispatch_agents")} input')?.value === "3"''',
                           timeout=10000)
    page.fill('#settings .search', 'agent questions')                   # found in its category, and gone to
    page.wait_for_selector(f'#settings .setmain .setgroup[data-group="Agents"] {row("dispatch_elicitation")[10:]}')
    page.press('#settings .search', 'Enter')
    page.wait_for_selector('#settings .setside button[data-page="agents"][aria-current="page"]')
    focused = f'''() => document.activeElement === document.querySelector('{row("dispatch_elicitation")} select')'''
    page.wait_for_function(focused)
    def to(name):  # a category, from the side
        page.click(f'#settings .setside button[data-page="{name}"]')
    def unfold(group):  # Advanced folds each module's settings until one is opened
        page.click(f'#settings details.setgroup[data-group="{group}"]:not([open]) > summary')
    to('advanced')
    unfold('Metaform')
    page.focus(f'{row("debug")} input[role=switch]')
    page.keyboard.press('ArrowRight')                                   # Left and Right change a switch
    page.wait_for_selector(f'{row("debug")} .state.ok')
    assert settings.value('debug', mapped) is True
    page.focus(f'{row("connect_instructions")} select')
    page.keyboard.press('ArrowRight')                                   # and a choice
    page.wait_for_selector(f'{row("connect_instructions")} .state.ok')
    assert settings.value('connect_instructions', mapped) == 'full'
    to('modules')
    page.uncheck(f'{row("modules")} input[value="hello"]')              # the modules this folder shows
    page.wait_for_selector(f'{row("modules")} .state.ok')
    assert 'hello' not in settings.value('modules', mapped) and 'chassis' in settings.value('modules', mapped)
    to('agents')
    # the roles are a list of choices, checked and never typed, ticket e3a3a2e4
    assert not page.query_selector(f'{row("roles_without_authority")} textarea')
    page.check(f'{row("roles_without_authority")} input[value="system"]')
    page.wait_for_selector(f'{row("roles_without_authority")} .state.ok')
    assert sorted(settings.value('roles_without_authority', mapped)) == ['prep', 'system', 'worker']
    to('advanced')                                                      # the module opened stays open
    page.click(f'{row("debug")} button.reset')
    page.wait_for_selector(f'{row("debug")} .state.off')
    assert settings.value('debug', mapped) is False
    to('agents')                                                        # an agent's options, under its own heading
    page.wait_for_selector('#settings .setgroup[data-group="Claude Code"] .setrow[data-key="dispatch_claude_mode"]')
    page.select_option(f'{row("dispatch_claude_mode")} select', 'acceptEdits')
    page.wait_for_selector(f'{row("dispatch_claude_mode")} .state.ok')
    assert settings.value('dispatch_claude_mode', mapped) == 'acceptEdits'
    assert settings.state('dispatch_claude_model', mapped) == 'default', 'one option set leaves the others'
    assert 'Accept edits' in page.inner_text(f'{row("dispatch_claude_mode")} .hint')
    assert [one for one in problems if 'status of 400' not in one] == [] and remote == []  # the refusal's own 400


@pytest.mark.req('VIEW-039')
def test_a_dispatched_sessions_thread_opens_in_the_dock_with_its_messages_and_tool_calls(
        run, web, mapped, browser, tmp_path, monkeypatch):
    """The page had two places that drew an agent's conversation, the agent window and the chat dock, so a session
    could be followed in one and talked with in the other. The dock is the one thread renderer, by session: the agents
    key opens the session's thread there, its chip says where it comes from, the agent's words, its thinking and its
    tool call are lines of it, its plan is above it, and its agent's figure in 3D and its part on the map are shown.
    code.interface.graphical#3c: by default the thread shows only what the agent says, a line it said on the map with
    web_say once, never again as its message; W shows its thinking and tool calls on this page and saves nothing.
    code.interface.graphical#45: while that message is still being written toward the line, one bubble holds it."""
    from metaform.data import Node, Store
    said = 'Hello, I am the fake owl.'
    monkeypatch.setenv('FAKE_ACP_SAY', said)                         # web_say, then the same words as a message
    monkeypatch.setenv('FAKE_ACP_SAY_STREAM', '0.6')                 # that message written a word at a time
    monkeypatch.setenv('FAKE_ACP_SAY_GATE', str(tmp_path / 'say-gate'))  # once the thread is open and watched
    monkeypatch.setenv('FAKE_ACP_LOG', str(tmp_path / 'thread.jsonl'))
    monkeypatch.setenv('FAKE_ACP_MODE', 'ask')                       # its turn waits on the gate, so it stays at work
    monkeypatch.setenv('FAKE_ACP_ASK_GATE', str(tmp_path / 'permission-gate'))
    run('enable', 'dispatch')
    run('set', '--no-dispatch-worktrees', cwd=mapped)
    store = Store('proj')
    alarm = store.element('code.alarm.audible').id
    work = store.add_work(Node('element', 'code.alarm.audible'), None, task='A quieter alarm').id
    run('dispatch', 'start', work, 'claude', cwd=mapped)
    try:
        started(run)
        page, problems, _ = opened(browser, web)
        page.wait_for_function('() => window.metaform.loaded()')
        page.wait_for_selector(f'#agents .agent[data-id="{work}"]', timeout=30000)
        session = next(one['session_id'] for one in api(web, '/api/dispatch-sessions?project=proj&thread=false')[1]
                       ['sessions'] if one['work_id'] == work and one['state'] == 'running')
        page.click(f'#agents .agent[data-id="{work}"]')
        page.wait_for_selector('#helpdesk:not([hidden]) .threadbar:not([hidden])')
        page.evaluate("""() => {  // the most bubbles holding the line at once, at every change of the thread
            const log = document.querySelector('#helpdesk .log');
            const held = () => { window.heldAtOnce = Math.max(window.heldAtOnce || 0, [...log.querySelectorAll(
              '.bubble.theirs p')].filter(p => p.textContent.startsWith('Hello,')).length); };
            held();
            new MutationObserver(held).observe(log, {childList: true, subtree: true, characterData: true});
        }""")
        (tmp_path / 'say-gate').touch()                              # the message is written now, a word at a time
        partial, end = False, time.monotonic() + 30
        while time.monotonic() < end:                                # until the message is written whole
            written = [one['text'] for one in api(web, f'/api/dispatch-sessions?project=proj&id={work}')[1]['lines']
                       if one['kind'] == 'agent_message_chunk' and one['text'].startswith('Hello,')]
            if written and written[-1] == said:
                break
            partial = partial or bool(written)
            page.wait_for_timeout(100)
        assert partial, 'the thread was open while the message was still being written'
        page.wait_for_selector(f'#helpdesk .log .bubble.theirs:has-text("{said}")', timeout=30000)
        page.wait_for_timeout(1000)                                  # the whole message drawn in its place
        assert page.evaluate('window.heldAtOnce') == 1
        assert page.locator('#helpdesk .log .tool, #helpdesk .log .thought').count() == 0  # its work, hidden
        assert page.locator('#helpdesk .log .bubble.theirs', has_text=said).count() == 1
        page.evaluate('document.activeElement.blur()')
        page.keyboard.press('w')                                     # the agent's work, on this page
        page.wait_for_selector('#helpdesk .log .tool[data-status="completed"]', timeout=30000)
        assert page.locator('#helpdesk .log .bubble.theirs', has_text=said).count() == 1
        assert next(one['value'] for one in api(web, '/api/settings?project=proj')[1]['settings']
                    if one['key'] == 'web_chat_details') is False       # W saves nothing
        # a line said on the map with no message saying it again is the agent's words in the thread
        alone = page.evaluate("""async () => {
            const {threadRows} = await import('/page/app/session/apps.js');
            const call = (seq, text) => ({session_id: 's', seq, name: `tool:${seq}`, kind: 'tool_call', text: 'say',
              data: {status: 'completed', call: {tool: 'web_say', input: {text}}}});
            const rows = threadRows([call(1, 'Over here'), {session_id: 's', seq: 2, name: 'm', kind: 'turn'},
              call(3, 'Again'), {session_id: 's', seq: 4, name: 'flow:1', kind: 'agent_message_chunk',
              text: 'again!'}, {session_id: 's', seq: 5, name: 'm2', kind: 'turn'}, call(6, 'Look'),
              {session_id: 's', seq: 7, name: 'flow:2', kind: 'agent_message_chunk', text: 'Looking at it.'}],
              {work: 'w', agent: 'claude'});
            return rows.filter(row => row.key.startsWith('said:'))
              .map(row => row.make().querySelector('.bubble p').textContent);
        }""")
        assert alone == ['Over here', 'Look'], alone                  # whole words: 'Looking' does not say 'Look'
        thread = page.inner_text('#helpdesk .log')
        assert -1 < thread.find('Thinking it over') < thread.find('Hello from fake') < thread.find('Read file'), thread
        assert page.locator('#helpdesk .log .bubble.theirs', has_text='Hello from fake').count() == 1
        assert page.inner_text('#helpdesk .log .tool .toolhead .title') == 'Read file'
        assert page.inner_text('#helpdesk .threadbar .src') == 'Agent at work'
        assert page.inner_text('#helpdesk .threadbar .task') == 'A quieter alarm'
        assert page.inner_text('#helpdesk .planbox .tally') == '1 of 2 done'
        docked = page.evaluate('window.metaform.dock()')
        assert docked['on'] == session and [(one['session'], one['source']) for one in docked['threads']] \
            == [(session, 'agent')]
        page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{work}" && one.focused)',
                               timeout=20000)
        assert page.evaluate('window.metaform.selected()') == alarm
        assert problems == []
    finally:
        run('dispatch', 'stop', work, cwd=mapped, ok=False)


@pytest.mark.req('VIEW-051')
def test_4_sets_the_depth_and_a_click_breaks_out_a_nodes_next_level_in_place_on_both_maps(run, web, mapped, browser):
    """4 steps the depth through the map's own levels, from the least that draws a join to one short of its deepest,
    and all, kept in web_map_depth (Rich, 2026-10-16); a part deeper than the depth stays inside the node it serves,
    which counts what it holds, in both maps alike. A click on that node breaks out its next level on the same map and
    a click again folds it; a part chosen while held is broken out; Enter still goes inside."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    cook, kitchen, tick, alarm = (at[one] for one in ('exterior.cook', 'code.timer.kitchen', 'code.loop.tick',
                                                       'code.alarm.audible'))
    drawn = lambda: page.evaluate("""async () => {
        const [{G}, {M}] = await Promise.all([import('/page/app/map3d/graph3d.js'), import('/page/app/map2d/build.js')]);
        const nodes = G.graphData().nodes.filter(node => node.t === 'el');
        return {d3: nodes.map(node => node.id).sort(), d2: [...M.nodes.keys()].sort(),
                names: Object.fromEntries(nodes.map(node => [node.id, node.name]))};
    }""")

    def shows(want, hidden=()):  # both maps draw the same parts, these among them and not those
        deadline, now = time.monotonic() + 15, drawn()
        while not (now['d3'] == now['d2'] and set(want) <= set(now['d3']) and not set(hidden) & set(now['d3'])):
            assert time.monotonic() < deadline, (want, hidden, now)
            page.wait_for_timeout(100)
            now = drawn()
        return now

    def kept(value):  # each press's save lands one after another
        deadline = time.monotonic() + 10
        while (now := api(web, '/api/view?project=proj')[1]['view']).get('web_map_depth') != value:
            assert time.monotonic() < deadline, now.get('web_map_depth')
            page.wait_for_timeout(100)

    shows([cook, kitchen, tick, alarm])  # all levels, the default
    map_key(page, '4')  # the least depth that draws a join: 2, as the cook alone at 1 would be a lone element
    now = shows([cook, kitchen, tick], [alarm])
    assert now['names'][kitchen].endswith(' +1')  # the timer holds the alarm beneath it
    assert page.evaluate('document.querySelector("#note2d")?.textContent') == 'Depth: 2 levels'
    kept('2')
    still2d(page)
    box = box_of(page, 'code.timer.kitchen')
    page.mouse.click(box['x'] + 6, box['y'] + 6)  # breaks out its next level, in place, and selects it
    shows([cook, kitchen, tick, alarm])
    assert page.evaluate('window.metaform.selected()') == kitchen and not page.evaluate('window.metaform.inside()')
    still2d(page)
    box = box_of(page, 'code.timer.kitchen')
    page.mouse.click(box['x'] + 6, box['y'] + 6)  # folds it back
    shows([cook, kitchen, tick], [alarm])
    assert not page.evaluate('window.metaform.inside()')
    page.evaluate(f'window.metaform.select("{alarm}")')  # chosen while held: its way down is broken out
    shows([cook, kitchen, alarm])
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')  # Enter alone still goes inside
    page.wait_for_function('() => window.metaform.inside().length > 0')
    page.keyboard.press('Shift+Enter')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    map_key(page, '4')  # one level short of the map's deepest, 3, is the most: then all, never a depth drawing all
    shows([cook, kitchen, tick, alarm])
    assert page.evaluate('document.querySelector("#note2d")?.textContent') == 'Depth: all levels'
    kept('all')
    assert not problems


@pytest.mark.req('VIEW-051')
def test_a_collapsed_map_opens_the_branch_of_the_work_in_hand_and_of_the_selection_and_closes_it_after(
        run, web, mapped, browser):
    """Collapsed, the map opens the branch down to a part whose ticket is taken, and closes it when the ticket is done;
    it opens the branch down to the part selected, by a jump as search, a link or the board makes it, and closes it
    when the selection goes (Rich, 2026-10-17). Both maps draw the same parts each time, and the parts drawn before
    the branch opened keep their places in 3D."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    kitchen, alarm = at['code.timer.kitchen'], at['code.alarm.audible']
    drawn = lambda: page.evaluate("""async () => {
        const [{G}, {M}] = await Promise.all([import('/page/app/map3d/graph3d.js'), import('/page/app/map2d/build.js')]);
        const nodes = G.graphData().nodes.filter(node => node.t === 'el');
        return {d3: nodes.map(node => node.id).sort(), d2: [...M.nodes.keys()].sort(),
                at: Object.fromEntries(nodes.map(node => [node.id, [node.x, node.y, node.z]]))};
    }""")

    def shows(alarm_drawn):
        deadline, now = time.monotonic() + 20, drawn()
        while not (now['d3'] == now['d2'] and (alarm in now['d3']) == alarm_drawn):
            assert time.monotonic() < deadline, (alarm_drawn, now)
            page.wait_for_timeout(100)
            now = drawn()
        return now

    map_key(page, '4')  # depth 2: the alarm is held inside the timer
    shows(False)
    # the layout at rest before the branch opens: still over ten frames drawn, or with no frame to come; a pause of
    # wall time alone passed while a slow frame was late and the layout was still settling (2026-10-17)
    frames = ("async () => { const {FRAMES} = await import('/page/app/map3d/graph3d.js');"
              " return [FRAMES.drawn, FRAMES.id]; }")
    deadline, before, since = time.monotonic() + 30, None, None
    while True:
        now, (count, pending) = drawn(), page.evaluate(frames)
        if before is not None and before['at'] == now['at'] and (count - since >= 10 or not pending):
            break
        if before is None or before['at'] != now['at']:
            before, since = now, count
        assert time.monotonic() < deadline, 'the 3D layout never came to rest'
        page.wait_for_timeout(300)
    ticket = json.loads(run('map', 'work', 'op=add', 'node=element:code.alarm.audible', 'task=Make it louder.',
                            'title=Louder', '--json', cwd=mapped).stdout)['id']
    run('map', 'work', 'op=take', f'id={ticket}', 'by=claude', cwd=mapped)
    opened_now = shows(True)  # taken: its branch opens
    assert all(opened_now['at'][key] == spot for key, spot in before['at'].items()), 'what was drawn stays put'
    run('map', 'work', 'op=done', f'id={ticket}', 'resolution=Louder.', 'why=It rings louder.', cwd=mapped)
    shows(False)  # done: the branch closes
    page.evaluate(f'window.metaform.select("{alarm}")')  # a jump to a held part opens its way down
    shows(True)
    page.evaluate(f'window.metaform.select("{kitchen}")')  # the selection moves on: closed again
    shows(False)
    page.evaluate(f'window.metaform.select("{alarm}")')
    shows(True)
    map_key(page, 'Escape')  # the selection let go of: closed
    shows(False)
    assert not problems


@pytest.mark.req('VIEW-051')
def test_depth_counts_its_levels_in_what_the_viewer_sees_with_an_edge_of_the_project_hidden(run, web, mapped, browser):
    """The levels are counted among the parts drawn, and the least depth draws a join: with the edge holding the top
    hidden, what the top receives from are the tops, so the least depth draws them with what serves them, never an
    empty map (2026-10-16: downstream hidden left depth 1 with nothing, its CQUs being the only tops)."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at = keys_of(web)
    cook, kitchen, tick, alarm, display = (at[one] for one in (
        'exterior.cook', 'code.timer.kitchen', 'code.loop.tick', 'code.alarm.audible', 'code.timer.kitchen.display'))
    page.evaluate("localStorage.setItem('metaform.rootsOff', JSON.stringify(['exterior']))")
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded()')
    map_key(page, '4')  # tick and display are tops now, the timer serves the display at 2, the alarm is at 3
    deadline, want = time.monotonic() + 15, sorted([tick, display, kitchen])
    while True:
        now = page.evaluate("""async () => {
            const {G} = await import('/page/app/map3d/graph3d.js');
            const {nodes, links} = G.graphData();
            return {els: nodes.filter(node => node.t === 'el').map(node => [node.id, node.name]),
                    joins: new Set(links.filter(link => link.k === 'encounter').map(link => link.join)).size};
        }""")
        if sorted(one for one, _ in now['els']) == want or time.monotonic() > deadline:
            break
        page.wait_for_timeout(100)
    assert sorted(one for one, _ in now['els']) == want, now  # the cook hidden, nothing of it counted
    assert now['joins'] >= 1 and dict(now['els'])[kitchen].endswith(' +1'), now  # a join drawn; the alarm held
    assert page.evaluate('document.querySelector("#note2d")?.textContent') == 'Depth: 2 levels'
    assert cook and alarm and not problems


@pytest.mark.req('VIEW-005')
def test_2_steps_the_flow_through_every_mode_then_each_again_with_the_edges_hidden(run, web, mapped, browser):
    """2 steps the flow through every mode, off, hover, the selection, all and live, with the joins' lines drawn, then
    the five again with the lines hidden so only what flows shows, and round again; each step is said at the 2D map's
    corner and kept in web_flow_mode and web_flow_edges. In hover the 2D map's flow runs on the edges of the node the
    pointer is on."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    note = lambda: page.evaluate('document.querySelector("#note2d.on")?.textContent || ""')
    hidden = lambda: page.evaluate('document.querySelector("#map2d").classList.contains("noedges")')
    seen = []
    assert (page.evaluate('window.metaform.flowMode()'), hidden()) == ('selected', False)  # the default
    reads = page.evaluate('window.metaform.changes()')
    for _ in range(9):
        map_key(page, '2')
        seen.append((page.evaluate('window.metaform.flowMode()'), hidden(), note()))
    assert seen == [('all', False, 'Flow: All'), ('live', False, 'Flow: Live'),
                    ('off', True, 'Flow: Off, edges hidden'), ('hover', True, 'Flow: Hover, edges hidden'),
                    ('selected', True, 'Flow: Selection, edges hidden'), ('all', True, 'Flow: All, edges hidden'),
                    ('live', True, 'Flow: Live, edges hidden'), ('off', False, 'Flow: Off'), ('hover', False, 'Flow: Hover')]
    kept = lambda: api(web, '/api/view?project=proj')[1]['view']  # the person's view, view.py
    # each key's saves land one after another, in order: one more of each, of the value in force, lands after all
    page.evaluate("""() => import('/page/app/views/settings.js').then(part => Promise.all(
        [part.saveView('web_flow_mode', 'hover'), part.saveView('web_flow_edges', true)]))""")
    assert (kept()['web_flow_mode'], kept()['web_flow_edges']) == ('hover', True)
    page.wait_for_timeout(1000)
    assert page.evaluate('window.metaform.changes()') == reads  # a saved view choice reads no map again
    _, at = keys_of(web)
    page.evaluate(f'window.metaform.select("{at["code.timer.kitchen"]}")')  # selected, but the flow follows the pointer
    box = page.locator('#map2d svg g.node[data-title="code.alarm.audible"]').bounding_box()
    page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    page.wait_for_function('() => window.metaform.flow().shapes2d.length > 0', timeout=10000)
    # in all, every join flows in both maps, with nothing selected
    page.evaluate('window.metaform.flowMode("all")')
    page.keyboard.press('Escape')
    edges = page.evaluate('document.querySelectorAll("#map2d svg .edgePaths path").length')
    page.wait_for_function('() => window.metaform.flow().points > 0', timeout=10000)
    page.wait_for_function('n => new Set(window.metaform.flow().shapes2d.map(() => 1)).size > 0 && '
                           'document.querySelectorAll("#map2d svg g.flows2d .ask").length >= n', arg=edges, timeout=10000)
    assert problems == []


@pytest.mark.req('VIEW-005')
def test_choosing_flat_turns_the_camera_to_face_the_plane_and_a_selection_keeps_it_facing(run, web, mapped, browser):
    """Flat lays the map on one plane; choosing it turns the camera square on to that plane, so the map is seen flat
    at once, and choosing a node there keeps it facing the plane instead of swinging round to the node's side."""
    import math
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.cameraAt()')
    page.evaluate('window.metaform.view3d({x: 300, y: 120, z: 40}, {x: 0, y: 0, z: 0})')  # seen from the side
    square = 'Math.abs(Math.sin(window.metaform.cameraAt().tilt) * Math.cos(window.metaform.cameraAt().turn)) > 0.99'
    assert not page.evaluate(square)
    page.locator('body').press('3')
    assert page.evaluate('window.metaform.physics()') == 'flat'
    page.wait_for_function(f'() => {square}', timeout=15000)
    page.evaluate('window.metaform.select(window.metaform.graph().nodes.find(node => node.t === "el"'
                  ' && node.id !== window.metaform.selected()).id)')
    page.wait_for_timeout(1800)  # the selection's flight, which a slow machine may still be making
    page.wait_for_function(f'() => {square}', timeout=15000)
    at = page.evaluate('window.metaform.cameraAt()')
    assert abs(math.sin(at['tilt']) * math.cos(at['turn'])) > 0.99, at
    assert not problems


@pytest.mark.req('VIEW-008')
def test_the_2d_map_is_laid_out_by_elk_the_way_that_fits_its_pane_and_again_when_the_pane_turns(
        run, web, mapped, browser):
    """The 2D map was drawn top to bottom whatever its pane, so a map wider than it was deep came out as a thin strip.
    ELK lays it out the way that fits its pane, and a pane reshaped far enough lays it out again: its nodes ease to
    their new places, and the selection and the arrows of each join's flow stay, P043."""
    from metaform.data import Store
    store = Store('proj')
    parts = [f'code.timer.kitchen.part{n}' for n in range(6)]
    for address in parts:  # a wide map: one join holding six parts, its information going both ways
        store.add_element('notes', address, name_length=1)
    store.add_join('notes', 'code.timer.kitchen', parts, purpose='Be put together.', ef='Holds its parts.', ifd='both')
    started(run)
    page, problems, _ = opened(browser, web)
    to_large_area(page)
    svg = '#map2d svg'
    assert page.get_attribute(svg, 'data-layout') == 'elk'
    # never the thin strip plain top to bottom draws in this pane: left to right, or top to bottom with its layers
    # held narrow, whichever is drawn larger
    assert page.get_attribute(svg, 'data-direction') == 'LR' or page.get_attribute(svg, 'data-layering')
    _, at = keys_of(web)
    kitchen = at['code.timer.kitchen']
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.wait_for_function(f'() => document.querySelector("{svg} g.node.sel")?.dataset.key === "{kitchen}"')
    still2d(page)
    page.evaluate(f'window.drawn2d = document.querySelector("{svg}")')
    page.set_viewport_size({'width': 1240, 'height': 760})  # the same shape: not laid out again
    page.wait_for_timeout(600)
    assert page.evaluate(f'window.drawn2d === document.querySelector("{svg}")')
    page.set_viewport_size({'width': 2200, 'height': 560})  # far wider than tall: top to bottom fits better
    # the new drawing's nodes start where they stood and move, rather than jumping
    page.wait_for_function(f'''() => {{ const now = document.querySelector("{svg}");
        return now !== window.drawn2d && now.dataset.direction === "TB"
            && [...now.querySelectorAll("g.node")].some(g => g.style.translate); }}''')
    page.wait_for_function(f'() => [...document.querySelectorAll("{svg} g.node")].every(g => !g.style.translate)')
    assert page.get_attribute(svg, 'data-layout') == 'elk' and page.evaluate('window.metaform.vertical()') is True
    assert page.evaluate(f'document.querySelector("{svg} g.node.sel")?.dataset.key') == kitchen
    both = page.evaluate(f'''() => [...document.querySelectorAll("{svg} .edgePaths path")]
        .filter(path => path.getAttribute("marker-start") && path.getAttribute("marker-end")).length''')
    assert both >= len(parts)
    assert problems == []


@pytest.mark.req('VIEW-027')
def test_a_ghosts_name_is_as_faint_as_its_node_at_rest_and_full_when_it_is_selected(run, web, mapped, browser):
    """A part not built is a ghost, and its name was drawn at full strength, so a map with many parts still to come
    filled the view with text. Its name is faint with it, in both views, and full once the part is selected."""
    from metaform.data import Node, Store
    store = Store('proj')
    store.add_work(Node('element', 'code.alarm.audible'), 'unbuilt', task='build the piezo driver')
    alarm = store.element('code.alarm.audible').id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function(f'() => window.metaform.loaded() && window.metaform.look("{alarm}").ghost === true', timeout=5000)
    label2d = f'Number(getComputedStyle(document.querySelector(\'#map2d svg g.node[data-key="{alarm}"] :is(text,.nodeLabel)\')).opacity)'
    # at rest: nothing selected and the camera far, so the name is small on the screen
    if page.evaluate('window.metaform.selected()'):
        page.keyboard.press('Escape')
    page.wait_for_function('() => !window.metaform.selected()')
    still3d(page, 1)                                     # the page's own fit, which takes back a camera moved before it
    page.evaluate('window.metaform.zoom3d(3)')
    page.wait_for_function(f'() => Math.abs(window.metaform.look("{alarm}").sign3d - 0.35) < 1e-6', timeout=5000)
    rest = page.evaluate(f'window.metaform.look("{alarm}")')
    assert rest['signOpacity3d'] <= 0.35 + 1e-6 and rest['opacity3d'] == pytest.approx(0.25)
    assert page.evaluate(label2d) == pytest.approx(0.35)
    page.evaluate(f'window.metaform.select("{alarm}")')
    page.wait_for_function(f'() => window.metaform.look("{alarm}").sign3d === 1', timeout=5000)
    assert page.evaluate(f'window.metaform.look("{alarm}").signOpacity3d') > rest['signOpacity3d']
    assert page.evaluate(label2d) == 1
    assert problems == []


# The toolbar and the panes, /api/workspace: the merge of the person's arrangement over the declared defaults, and the
# endpoints, answered through a stand-in for the server's request handler, so no server process starts.

def _contributions():
    from metaform.module import Pane, ToolbarItem
    toolbar = (ToolbarItem('search', 'Search', 'Find a node by its words.', page='search', order=10),
               ToolbarItem('brief', 'Brief', 'Read a node in full.', pane='brief', order=20),
               ToolbarItem('add-task', 'Add task', 'Write a ticket.', page='add-task', group='write', order=60),
               ToolbarItem('add-element', 'Add element', 'Add a part.', page='add-element', group='write', order=61),
               ToolbarItem('export', 'Export', 'Save the map as a document.', page='export-xml', placement='extra'),
               ToolbarItem('greet', 'Greet', 'Say hello on the map.', verb='greet', order=70))
    panes = (Pane('map2d', '2D map', 'See the map flat.', page='map2d', area='left', visible=True, order=10),
             Pane('object', 'Object', 'Read the node.', page='object', group='node', visible=True, order=10),
             Pane('brief', 'Brief', 'Read a node in full.', verb='where', selection='address', group='node',
                  visible=True, order=40),
             Pane('settings', 'Settings', 'Change a setting.', page='settings', group='node', order=90))
    return toolbar, panes


def _offered(owner='mine'):
    toolbar, panes = _contributions()
    return ({f'{owner}.{item.id}': (owner, item) for item in toolbar},
            {f'{owner}.{pane.id}': (owner, pane) for pane in panes})


@pytest.mark.req('VIEW-011')
def test_the_default_arrangement_comes_from_the_declarations():
    from metaform.modules.web import workspace
    items, panes = _offered()
    assert workspace.merge_toolbar(None, items) == {
        'toolbar': [['mine.search'], ['mine.brief'], ['mine.add-task', 'mine.add-element'], ['mine.greet']],
        'extra': ['mine.export']}
    layout = workspace.merge_layout(None, panes)
    assert layout['areas']['left']['groups'] == [{'id': 'map2d', 'tabs': ['mine.map2d'], 'active': 'mine.map2d',
                                                  'size': None}]
    assert layout['areas']['right']['groups'] == [{'id': 'node', 'tabs': ['mine.object', 'mine.brief',
                                                                         'mine.settings'],
                                                   'active': 'mine.object', 'size': None}]
    assert layout['off'] == ['mine.settings'] and layout['floating'] == []


@pytest.mark.req('VIEW-011')
def test_a_saved_arrangement_keeps_the_persons_places_and_new_contributions_land_in_their_group():
    from metaform.modules.web import workspace
    items, panes = _offered()
    saved = {'toolbar': [['mine.brief', 'gone.tool'], ['mine.add-element']], 'extra': ['mine.search']}
    assert workspace.merge_toolbar(saved, items) == {
        'toolbar': [['mine.brief'], ['mine.add-element', 'mine.add-task'], ['mine.greet']],
        'extra': ['mine.search', 'mine.export']}
    moved = {'areas': {'bottom': {'size': 200, 'groups': [{'id': 'node', 'tabs': ['mine.object', 'gone.pane'],
                                                          'active': 'gone.pane', 'size': None}]}},
             'floating': [{'pane': 'mine.map2d', 'x': 10, 'y': 20, 'w': 300, 'h': 200}], 'off': ['gone.pane']}
    layout = workspace.merge_layout(workspace.layout_shape(moved), panes)
    assert layout['areas']['bottom']['groups'] == [{'id': 'node', 'tabs': ['mine.object', 'mine.brief',
                                                                          'mine.settings'],
                                                    'active': 'mine.object', 'size': None}]
    assert layout['areas']['right']['groups'] == [] and layout['areas']['left']['groups'] == []
    assert layout['floating'] == [{'pane': 'mine.map2d', 'x': 10, 'y': 20, 'w': 300, 'h': 200}]
    assert layout['off'] == ['mine.settings']
    # What a module turned off had is kept when the page saves, so it comes back where it was.
    kept = workspace.kept_toolbar({'toolbar': [['mine.brief']], 'extra': []}, saved, items)
    assert kept == {'toolbar': [['mine.brief'], ['gone.tool']], 'extra': []}
    again = workspace.kept_layout(layout, workspace.layout_shape(moved), panes)
    assert again['areas']['bottom']['groups'][0]['tabs'][-1] == 'gone.pane' and 'gone.pane' in again['off']


@pytest.mark.req('VIEW-011')
def test_an_arrangement_that_is_not_its_shape_is_refused():
    from metaform.modules.web import workspace
    for shape, text in ((workspace.toolbar_shape, '{"toolbar": [["a"], "b"]}'),
                        (workspace.layout_shape, '{"areas": {"top": {}}}'),
                        (workspace.workspaces_shape, '{"Default": {}}'),
                        (workspace.toolbar_shape, 'not json')):
        with pytest.raises(ValueError):
            workspace._parsed(text, shape)
    assert workspace._parsed('', workspace.layout_shape) is None


class _Handler:
    """What the workspace endpoints use of the server's request handler: its headers, body and answers."""

    def __init__(self, body=None):
        self.headers = {'Origin': 'http://127.0.0.1:7433', 'Host': '127.0.0.1:7433',
                        'Content-Type': 'application/json'}
        self.body, self.answers, self.pushed, self.changes = body, [], [], []
        self.gui = self
        self.gate = None  # no Node's gate in front: the view kept is the owner's

    def json_body(self):
        return self.body

    def same_origin(self):
        return self.headers.get('Origin') == f'http://{self.headers["Host"]}'

    def holds(self, needed, path):  # no Node's gate in front: every class is the person's
        return True

    def send(self, status, data):
        self.answers.append((status, data))

    def reply(self, status, body, kind, headers):
        self.answers.append((status, json.loads(body) if kind == 'application/json' else body))

    def refuse(self, error, status):
        self.answers.append((status, {'error': str(error), 'next': getattr(error, 'next_step', None)}))

    def push(self, event):
        self.pushed.append(event)

    def changed(self, payload):
        self.changes.append(payload)


@pytest.fixture
def offered(home, monkeypatch):
    """The workspace endpoints with one module's contributions, `mine`, whatever modules this home has on."""
    import metaform.modules.web  # noqa: F401  declares the web settings
    from metaform import module as chassis
    from metaform.module import Module, Noun, Verb
    from metaform.modules.web import workspace
    toolbar, panes = _contributions()
    mine = Module(id='mine', summary='Mine.', purpose='Mine.',
                  verbs=(Verb('greet', lambda ctx: 'hello', 'Greet.', caution='This greets everyone.'),
                         Verb('where', lambda ctx: None, 'Read.', nouns=(Noun('address', 'An address.'),),
                              effect='read')),
                  toolbar=toolbar, panes=panes)
    monkeypatch.setattr(chassis, 'contributions', lambda folder: [('mine', toolbar, panes)])
    monkeypatch.setattr(workspace, '_module', lambda owner, folder: mine)
    return workspace


def _call(workspace, method, path, body=None, query=None):
    handler = _Handler(body)
    workspace.answer(handler, method, path, query or {})
    return handler


@pytest.mark.req('VIEW-011')
def test_the_workspace_read_merges_the_saved_arrangement_and_a_write_saves_it_in_the_view(offered):
    from metaform.modules.web import view
    got = _call(offered, 'GET', '/api/workspace').answers[-1]
    assert got[0] == 200
    state = got[1]
    assert state['workspace'] == 'Default' and state['workspaces'] == ['Default']
    assert state['toolbar'] == state['defaults']['toolbar']
    greet = next(item for item in state['items'] if item['id'] == 'mine.greet')
    assert greet['action'] == {'kind': 'verb', 'verb': 'greet', 'arguments': {}, 'effect': 'write',
                               'caution': 'This greets everyone.'}
    brief = next(pane for pane in state['panes'] if pane['id'] == 'mine.brief')
    assert brief['content']['url'] == '/api/workspace/pane?pane=mine.brief' and brief['selection'] == 'address'
    toolbar = {'toolbar': [['mine.greet'], ['mine.search']], 'extra': ['mine.brief', 'mine.export']}
    saved = _call(offered, 'POST', '/api/workspace/arrangement', {'toolbar': toolbar})
    assert saved.answers[-1][0] == 200 and saved.pushed == [{'topic': 'workspace', 'payload': {'workspace': 'Default'}}]
    assert json.loads(view.value('web_toolbar')) == toolbar
    drawn = saved.answers[-1][1]['toolbar']['toolbar']  # the tools it does not name land by their declared order
    assert drawn == [['mine.add-task', 'mine.add-element'], ['mine.greet'], ['mine.search']]
    refused = _call(offered, 'POST', '/api/workspace/arrangement', {'toolbar': {'toolbar': 'mine.greet'}})
    assert refused.answers[-1][0] == 400
    stranger = _Handler({'toolbar': toolbar})
    stranger.headers['Origin'] = 'http://elsewhere.example'
    offered.answer(stranger, 'POST', '/api/workspace/arrangement', {})
    assert stranger.answers[-1][0] == 403


@pytest.mark.req('VIEW-011')
def test_a_stored_view_survives_its_move_out_of_the_settings_and_each_account_keeps_its_own(home):
    """Settings cleanup 2026-10-15: the page's view is no setting. A value stored in the old global settings is carried
    into the owner's view once, as the web module starts, and its row removed; a value the key no longer takes falls
    to the default. Behind a Node's gate each account keeps its own over the owner's; a key or value the view does not take
    is refused; and none of it is in config's settings."""
    from metaform import home as homes
    from metaform import settings
    from metaform.modules.web import view
    homes.save('global', 'web', 'web_signs', ['facing'])
    homes.save('global', 'web', 'web_map_depth', ['2'])
    homes.save('global', 'web', 'web_lens', ['not-a-lens'])
    assert view.value('web_map_depth') == 'auto', 'a read carries nothing'
    with homes.chassis(write=True) as db:  # the test home's own start carried nothing and marked it; undo the mark
        db.execute("DELETE FROM meta WHERE key='carried:web-view-state'")
    settings._carried.clear()
    assert view.carry() == ["web_signs = 'facing'", "web_map_depth = '2'"] and view.carry() == []
    assert (view.value('web_signs'), view.value('web_map_depth'), view.value('web_lens')) == ('facing', '2', 'natural')
    assert homes.stored('global', 'web', 'web_signs') is None and 'web_signs' not in settings.SCHEMA
    gated = _Handler({'key': 'web_signs', 'value': 'outward'})
    gated.gate, gated.headers['X-Metaform-Account'] = 'secret', 'bob'
    view.answer(gated, 'POST')
    assert gated.answers[-1][1]['view']['web_signs'] == 'outward' and view.value('web_signs') == 'facing'
    assert view.values('bob')['web_map_depth'] == '2', "an account reads the owner's view under its own"
    for given in ({'key': 'web_signs', 'value': 'sideways'}, {'key': 'web_port', 'value': 1}):
        refused = _Handler(given)
        view.answer(refused, 'POST')
        assert refused.answers[-1][0] == 400


@pytest.mark.req('VIEW-038')
def test_the_maps_names_face_the_eye_by_default_and_no_carry_moves_a_kept_choice(home):
    """2026-10-17: facing is the signs' default, and the web module's start moves nobody's kept choice."""
    from metaform import home as homes
    from metaform import settings
    from metaform.modules.web import view
    assert view.value('web_signs') == 'facing'
    view.keep('', 'web_signs', 'facing')
    view.keep('bob', 'web_signs', 'outward')
    with homes.chassis(write=True) as db:  # the test home's own start marked its carries; undo the marks
        db.execute("DELETE FROM meta WHERE key LIKE 'carried:web-%'")
    settings._carried.clear()
    assert view.carry() == []
    assert view.value('web_signs') == 'facing' and view.values('bob')['web_signs'] == 'outward'


@pytest.mark.req('VIEW-011')
def test_workspaces_are_saved_selected_reset_and_deleted_and_default_stays(offered):
    from metaform.modules.web import view
    toolbar = {'toolbar': [['mine.greet']], 'extra': []}
    _call(offered, 'POST', '/api/workspace/arrangement', {'toolbar': toolbar})
    state = _call(offered, 'POST', '/api/workspace/save', {'name': 'Review'}).answers[-1][1]
    assert state['workspace'] == 'Review' and state['workspaces'] == ['Default', 'Review']
    assert _call(offered, 'POST', '/api/workspace/save', {'name': 'default'}).answers[-1][0] == 400
    _call(offered, 'POST', '/api/workspace/arrangement', {'toolbar': {'toolbar': [['mine.search']], 'extra': []}})
    _call(offered, 'POST', '/api/workspace/reset', {'part': 'toolbar'})
    assert ['mine.greet'] in json.loads(view.value('web_toolbar'))['toolbar']
    state = _call(offered, 'POST', '/api/workspace/select', {'name': 'Default'}).answers[-1][1]
    assert state['workspace'] == 'Default' and view.value('web_toolbar') == ''
    assert state['toolbar'] == state['defaults']['toolbar']
    assert _call(offered, 'POST', '/api/workspace/delete', {'name': 'Default'}).answers[-1][0] == 400
    _call(offered, 'POST', '/api/workspace/select', {'name': 'Review'})
    state = _call(offered, 'POST', '/api/workspace/delete', {'name': 'Review'}).answers[-1][1]
    assert state['workspaces'] == ['Default'] and state['workspace'] == 'Default'


@pytest.mark.req('VIEW-011')
def test_a_tool_runs_only_its_declared_verb_a_caution_one_with_confirm_and_a_pane_reads_with_the_selection(
        offered, monkeypatch):
    from metaform.modules.web import server
    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, owner, verb, arguments: calls.append(
        (owner, verb, arguments)) or {'ran': verb})
    asked = _call(offered, 'POST', '/api/workspace/run', {'item': 'mine.greet'})
    assert asked.answers[-1][0] == 409 and asked.answers[-1][1]['confirm'] is True and calls == []
    assert _call(offered, 'POST', '/api/workspace/run', {'item': 'mine.search'}).answers[-1][0] == 404
    ran = _call(offered, 'POST', '/api/workspace/run', {'item': 'mine.greet', 'confirm': True})
    assert ran.answers[-1] == (200, {'item': 'mine.greet', 'result': {'ran': 'greet'}})
    assert calls == [('mine', 'greet', {})]
    unselected = _call(offered, 'GET', '/api/workspace/pane', query={'pane': ['mine.brief']})
    assert unselected.answers[-1][0] == 400
    read = _call(offered, 'GET', '/api/workspace/pane', query={'pane': ['mine.brief'], 'selection': ['code.app']})
    assert read.answers[-1][0] == 200 and read.answers[-1][1]['result'] == {'ran': 'where'}
    assert read.answers[-1][1]['chars'] > 0
    assert calls[-1] == ('mine', 'where', {'address': 'code.app'})


def briefed(run, mapped):
    """The kitchen timer with a memory linked to one at the alarm, a question and a ticket numbered at it, and memory
    in the folder's layers, so an agent there reads all of them, MCP-037."""
    remember(run, mapped, 'create_entities', [{**entity('countdown drift', 'Drifts under load.'),
                                               'title': 'Countdown drifts', 'why': 'A cook trusts the time left.'}],
             'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'Too quiet.')], 'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'quiet tone', 'relationType': 'drives'}])
    run('map', 'ask', 'element:code.timer.kitchen', 'Monotonic clock?', 'title=Which tick source?',
        'why=The drift depends on it', cwd=mapped)
    run('set', '--layers', ','.join([*TOGGLED, 'memory']), cwd=mapped)


@pytest.mark.req('MCP-037')
def test_the_page_reads_a_nodes_brief_and_items_exactly_as_an_agent_reads_them(run, web, mapped):
    from metaform.modules.mcp import server as mcp
    briefed(run, mapped)
    started(run)
    status, body = api(web, '/api/brief?project=proj&address=code.timer.kitchen')
    assert status == 200, body
    assert body['text'] == mcp.brief(mapped, 'code.timer.kitchen')            # the resource an agent reads, exactly
    assert body['uri'] == 'metaform://code.timer.kitchen' and body['budget'] == 2048
    assert body['bytes'] == len(body['text'].encode('utf-8')) and body['brief']['element']['address'] == 'code.timer.kitchen'
    numbers = [item['number'] for item in body['items']]
    assert numbers == sorted(numbers, reverse=True) and body['latest']['number'] == numbers[0]
    by_kind = {item['kind']: item for item in body['items']}
    assert by_kind['question']['title'] == 'Which tick source?' and by_kind['question']['why'] == 'The drift depends on it'
    memory = by_kind['memory']
    assert (memory['title'], memory['why']) == ('Countdown drifts', 'A cook trusts the time left.')
    assert 'nextCursor' not in body                                        # one page holds them all
    status, found = api(web, f'/api/item?project=proj&item={memory["item"].replace("#", "%23")}')
    assert status == 200 and found['text'] == mcp.item(mapped, 'code.timer.kitchen', memory['number'])
    assert any('code.alarm.audible#' in link for link in found['links'])  # a link to walk to, address#n
    assert api(web, '/api/item?project=proj&item=code.timer.kitchen%23fff')[0] == 404
    assert api(web, '/api/brief?project=proj&address=code.nowhere')[0] == 400
    # the AI tool's map view reads the same answers through metaform_view, so it draws the same brief and items
    assert plain(mcp.view_read(mapped, 'brief', {'address': 'code.timer.kitchen'})) == body
    assert plain(mcp.view_read(mapped, 'item', {'item': memory['item']})) == found


@pytest.mark.req('MCP-037')
def test_the_page_shows_what_an_agent_connecting_here_receives_from_the_folders_own_mcp_server(run, web, mapped,
                                                                                                monkeypatch):
    from metaform import loader, settings
    from metaform.modules.mcp import server as mcp
    loaded = {'chassis', *(module.id for module in loader.enabled())}
    for key in [key for key, setting in settings.SCHEMA.items() if setting.owner not in loaded]:
        monkeypatch.delitem(settings.SCHEMA, key)  # declared by a test's own import of a module that ships disabled
    started(run)
    status, body = api(web, '/api/agent-view?project=proj&address=code.timer.kitchen')
    assert status == 200, body
    assert body['connect']['text'] == mcp.connect_instructions(mapped)  # the person's own session's directive and links
    assert 'metaform://role/person' in body['connect']['text']
    assert body['connect']['chars'] == len(body['connect']['text']) and body['host_limit'] == 2048
    assert body['glossary']['text'] == mcp.glossary(mapped)
    assert body['glossary']['index']['text'] == mcp.modules_text(mapped)
    # what a connecting agent is listed, as the Inspector lists it: the catalog that finds the rest by purpose, MCP-003
    assert [tool['name'] for tool in body['tools']] == ['metaform_catalog']
    costs = [tool['model_bytes'] for tool in body['tools']]
    assert costs == sorted(costs, reverse=True)  # the costliest first, by what the model receives
    assert {one['entry']['uri'] for one in body['resources']} >= {one['uri'] for one in mcp.resource_list(mapped)}
    assert {one['entry']['name'] for one in body['prompts']} == set(mcp.slashes(mapped))
    assert {'tools', 'resources', 'prompts'} <= set(body['capabilities']) and body['templates']
    assert body['brief']['text'] == mcp.brief(mapped, 'code.timer.kitchen')
    assert body['tool_bytes'] == sum(tool['bytes'] for tool in body['tools'])
    # what is paid, as Claude Code sends tools to the model: mcp__<server>__<tool>, description and input schema only
    sent = [json.dumps({'name': f'mcp__metaform__{tool["name"]}', 'description': tool['entry'].get('description', ''),
                        'input_schema': tool['entry']['inputSchema']}, ensure_ascii=False).encode('utf-8')
            for tool in body['tools']]
    connect = len(body['connect']['text'].encode('utf-8'))
    named = sum(len(f'mcp__metaform__{tool["name"]}'.encode()) for tool in body['tools'])
    always = sum(tool['model_bytes'] for tool in body['tools'] if tool['always'])
    assert body['paid']['upfront'] == connect + sum(len(one) for one in sent)
    assert body['paid']['deferred'] == connect + named + always            # tool search hands the names first
    assert 'loaded' not in body['paid']  # the connect message no longer asks for every tool to be loaded
    assert body['paid']['tokens'] == {key: round(body['paid'][key] / 4) for key in ('deferred', 'upfront', 'glossary')}
    run('disable', 'mcp')
    status, body = api(web, '/api/agent-view?project=proj')
    assert status == 400 and 'metaform enable mcp' in body['next']


@pytest.mark.req('VIEW-024')
def test_the_mermaid_export_is_the_map_mermaid_command_with_the_pages_layers_direction_and_roots(run, web, mapped):
    from metaform import outline
    started(run)
    status, text, _ = request(web, '/api/mermaid?project=proj')
    assert status == 200 and text == run('map', 'mermaid', cwd=mapped).stdout
    # the title and the page's layout in the frontmatter, https://mermaid.js.org/config/configuration.html
    assert text.startswith('---\ntitle: "proj functional map"\nconfig:\n  layout: elk\n  elk:\n'
                           '    nodePlacementStrategy: NETWORK_SIMPLEX\n---\nflowchart TB\n')
    assert 'code_timer_kitchen["dish timer<br>code.timer.kitchen"]' in text
    assert '  exterior_cook --> code_timer_kitchen' in text and '  code_timer_kitchen --> code_alarm_audible' in text
    assert '  class exterior_cook cqu' in text and '  class code_timer_kitchen de' in text  # the roles' classes
    assert (outline._edge('r', 'p', 'both', ''), outline._edge('r', 'p', 'receives', 'x')) == (
        '  r <--> p', '  p -->|"x"| r')                                    # each join points the way it flows
    told = request(web, '/api/mermaid?project=proj&labels=purpose')[1]
    assert '  exterior_cook -->|"Know when food is done."| code_timer_kitchen' in told
    assert told == run('map', 'mermaid', 'labels=purpose', cwd=mapped).stdout
    across = request(web, '/api/mermaid?project=proj&direction=LR&leave_out=exterior')[1]
    assert '\nflowchart LR\n' in across and 'exterior' not in across.split('flowchart', 1)[1]
    assert across == run('map', 'mermaid', 'direction=LR', 'leave_out=exterior', cwd=mapped).stdout
    around = request(web, '/api/mermaid?project=proj&address=code.alarm.audible')[1]
    assert 'code_loop_tick' not in around and 'code_timer_kitchen --> code_alarm_audible' in around
    assert request(web, '/api/mermaid?project=proj&direction=up')[0] == 400
    assert request(web, '/api/mermaid?project=proj&labels=all')[0] == 400
    long = outline.mermaid_limits('flowchart TB\n' + '  a --> b\n' * 501)  # past what GitHub's Mermaid draws
    assert long and '501 edges' in long and outline.mermaid_limits(text) is None


KITCHEN = ("[...document.querySelectorAll('#map2d svg g.node')]"
           ".find(node => node.textContent.includes('dish timer')).dataset.key")


def select_kitchen(page):
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.select({KITCHEN})')


def brief_page(run, web, mapped, browser):
    briefed(run, mapped)
    started(run)
    page, problems, _ = opened(browser, web)
    select_kitchen(page)
    return page, problems


@pytest.mark.req('MCP-037')
def test_the_brief_tab_shows_the_agents_brief_its_items_and_walks_a_memory_link_to_its_node(
        run, web, mapped, browser):
    page, problems = brief_page(run, web, mapped, browser)
    page.click('#t-brief')
    page.wait_for_selector('#p-brief ul.items .itemrow')
    assert page.locator('#p-brief .uri code').text_content() == 'metaform://code.timer.kitchen'
    assert '2,048 bytes' in page.locator('#p-brief .budget').text_content()
    assert page.locator('#p-brief .budget').get_attribute('role') == 'meter'
    latest = api(web, '/api/brief?project=proj&address=code.timer.kitchen')[1]['latest']['number']
    assert page.locator('#p-brief .itemrow .num').first.text_content() == f'#{latest:x}'  # newest first
    assert page.locator('#p-brief h2').text_content() == 'dish timer'     # named as the map names it
    assert page.locator('#p-brief .around').count() == 0                  # the neighbours once, in the tree
    assert 'Get attention.' in page.locator('#p-brief pre.tree .purpose').all_text_contents()[-1]
    page.click('#p-brief .segmented [data-value="memory"]')              # only the memories, asked of the server
    page.wait_for_function("() => [...document.querySelectorAll('#p-brief .itemrow .pill[class*=kind-]')]"
                           ".every(pill => pill.textContent === 'memory')")
    assert page.locator('#p-brief .itemrow').count() == 1
    row = page.locator('#p-brief .itemrow').first
    assert 'Countdown drifts' in row.text_content() and 'A cook trusts the time left.' in row.text_content()
    row.locator('.itemhead').focus()
    page.keyboard.press('Enter')                                          # opened by the keyboard
    page.wait_for_selector('#p-brief .itemopen .links a')
    assert row.locator('.itemhead').get_attribute('aria-expanded') == 'true'
    page.click('#p-brief .itemopen .links a')                             # the link walked to its own node
    page.wait_for_function("() => document.querySelector('#p-brief .uri code')?.textContent === 'metaform://code.alarm.audible'")
    page.wait_for_selector('#p-brief .itemrow.open .itemopen pre')
    assert 'quiet tone' in page.locator('#p-brief .itemrow.open').text_content()
    assert page.locator('#t-brief').get_attribute('aria-selected') == 'true'  # the brief stayed on view
    page.click('#p-brief .walk button')                                   # and Back returns along the walk
    page.wait_for_function("() => document.querySelector('#p-brief .uri code')?.textContent === 'metaform://code.timer.kitchen'")
    run('memory', 'create_entities', json.dumps([{**entity('late bell', 'Rings late.'), 'why': 'Seen twice.'}]),
        'node=element:code.timer.kitchen', cwd=mapped)
    page.reload()
    page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length > 0')
    select_kitchen(page)
    page.click('#t-brief')
    page.wait_for_selector('#p-brief .itemrow.new')                       # unseen since this browser last looked
    assert page.locator('#p-brief .itemrow.new').count() == 1 and 'Rings late.' in page.locator('#p-brief .itemrow.new').text_content()
    assert page.locator('#p-brief .itemrow.new .pill.fresh').text_content() == 'unseen'
    assert problems == []


@pytest.mark.req('MCP-037')
def test_what_an_agent_sees_opens_from_the_brief_with_each_part_and_its_size_by_keyboard(run, web, mapped, browser):
    page, problems = brief_page(run, web, mapped, browser)
    page.click('#t-brief')
    page.wait_for_selector('#p-brief .seeall')
    page.click('#p-brief .seeall')
    page.wait_for_selector('#agentview .views [role=tab]', timeout=60000)
    assert page.locator('#agentview').get_attribute('aria-modal') == 'true'
    assert 'characters' in page.locator('#agentview .budget').text_content()
    assert 'Before beginning work, read metaform://metaform' in page.locator('#agentview pre').text_content()
    paid = page.locator('#agentview dl.paid').text_content()
    assert 'Without tool search' in paid and 'tokens' in paid and 'as asked' not in paid  # both ways tools load
    page.focus('#av-connect')
    for key in ('glossary', 'tools'):                                    # the parts, one after another by arrow
        page.keyboard.press('ArrowRight')
        assert page.evaluate('document.activeElement.id') == f'av-{key}'
    work = page.locator('#agentview details.entry', has=page.locator('summary code', has_text='map_work'))
    work.locator('summary').focus()
    page.keyboard.press('Enter')                                          # a tool opened to its schema, by keyboard
    assert '"properties"' in work.locator('pre').text_content() and '"op"' in work.locator('pre').text_content()
    page.focus('#av-tools')
    for key in ('resources', 'prompts', 'brief'):
        page.keyboard.press('ArrowRight')
        assert page.evaluate('document.activeElement.id') == f'av-{key}'
        if key == 'resources':
            assert 'metaform://metaform' in page.locator('#av-panel').text_content()
    assert '2,048 bytes' in page.locator('#agentview .budget').text_content()
    assert '"address": "code.timer.kitchen"' in page.locator('#agentview pre').text_content()
    page.keyboard.press('Escape')
    assert page.locator('#agentview').is_hidden()
    assert page.evaluate("document.activeElement.classList.contains('seeall')")  # the focus is back where it was
    assert problems == []


@pytest.mark.req('VIEW-024')
def test_the_export_menu_copies_and_saves_the_2d_map_as_mermaid_that_mermaid_draws(run, web, mapped, browser):
    from metaform.data import Store
    # a join whose receiver receives, and one both ways: each edge runs the way its information goes, on both
    Store('proj').add_join('notes', 'code.loop.tick', 'code.alarm.audible', purpose='Hear the alarm.',
                           ef='Rings on the tick.', ifd='receives')
    Store('proj').add_join('notes', 'code.alarm.audible', 'code.timer.kitchen', purpose='Be set.', ef='Sets.',
                           ifd='both')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=f'http://127.0.0.1:{web}')
    page.click('#exportBtn')
    with page.expect_download() as saving:
        page.click('#exportMermaid')
    saved = saving.value
    assert saved.suggested_filename == 'proj-map.mmd'
    text = Path(saved.path()).read_text(encoding='utf-8')
    direction = page.evaluate("document.querySelector('#map2d svg').dataset.direction")
    assert text == run('map', 'mermaid', f'direction={direction}', cwd=mapped).stdout
    # the export holds what the 2D map draws: its nodes, and an edge for each join's element, by address
    ids = dict(re.findall(r'^  (\w+)\["[^"]*?(?:<br>)?([\w.]+)"\]$', text, re.MULTILINE))
    links = re.findall(r'^  (\w+) (<-->|-->)(?:\|"[^"]*"\|)? (\w+)$', text, re.MULTILINE)
    edges = sorted((ids[start], ids[end], arrow) for start, arrow, end in links)
    drawn = page.evaluate('window.metaform.drawn2d()')
    assert sorted(ids.values()) == sorted(drawn['nodes'])
    assert edges == sorted(tuple(edge) for edge in drawn['edges'])          # ordered: ELK lays out the same graph
    assert ('code.alarm.audible', 'code.loop.tick', '-->') in edges        # a receives join runs to its receiver
    assert ('code.alarm.audible', 'code.timer.kitchen', '<-->') in edges
    page.click('#exportBtn')
    page.click('#copyMermaid')
    page.wait_for_function('() => document.querySelector("#toast").textContent.includes("Mermaid")')
    assert page.evaluate('navigator.clipboard.readText()') == text
    # Mermaid itself draws what is exported, with its own defaults, not the page's, and lays it out by ELK as asked
    fresh = page.evaluate('''async text => { window.mermaid.initialize({startOnLoad: false});
      const svg = (await window.mermaid.render("exported", text)).svg; return svg; }''', text)
    assert fresh.count('class="node') >= 5 and 'proj functional map' in fresh
    asked = page.evaluate('async text => (await window.mermaid.parse(text)).config', text)
    assert asked['layout'] == 'elk' and asked['elk']['nodePlacementStrategy'] == 'NETWORK_SIMPLEX'
    assert problems == []


@pytest.mark.req('MCP-037')
def test_the_brief_and_the_mcp_view_list_a_nodes_items_from_one_read_per_module_past_deleted_ones(
        run, web, mapped, monkeypatch):
    import time

    from metaform import module as chassis
    from metaform.modules.mcp import server as mcp
    run('set', '--layers', ','.join([*TOGGLED, 'memory']), cwd=mapped)
    made = [{**entity(f'drift {n}', f'Drift seen {n}.'), 'why': f'Seen {n}.'} for n in range(80)]
    remember(run, mapped, 'create_entities', made, 'element:code.timer.kitchen')
    remember(run, mapped, 'delete_entities', [f'drift {n}' for n in range(40, 80)])
    started(run)
    used = []
    listed = chassis.node_items
    monkeypatch.setattr(chassis, 'node_items', lambda *args, **kwargs: used.append(args[1]) or listed(*args, **kwargs))
    read_one = chassis.item_read
    monkeypatch.setattr(chassis, 'item_read', lambda *args, **kwargs: used.append('item_read') or read_one(*args,
                                                                                                          **kwargs))
    began = time.monotonic()
    status, body = api(web, '/api/brief?project=proj&address=code.timer.kitchen&kind=memory')
    took = time.monotonic() - began
    assert status == 200, body
    assert len(body['items']) == 40 and 'nextCursor' not in body
    assert [one['title'] for one in body['items'][:2]] == ['Drift seen 39.', 'Drift seen 38.']
    assert body['items'][0]['why'] == 'Seen 39.' and body['kinds'] == ['memory']
    viewed = mcp.view_read(mapped, 'items', {'address': 'code.timer.kitchen'})
    assert [one['item'] for one in viewed['items'] if one['kind'] == 'memory'] == [one['item'] for one in body['items']]
    assert used == ['code.timer.kitchen']                                 # the view's list is node_items's, read
    direct = listed(mapped, 'code.timer.kitchen', kinds=('memory',), project='proj')  # without one item_read
    assert [one['item'] for one in direct['items']] == [one['item'] for one in body['items']]  # and the page's too
    assert took < 3, took                                                 # one read per module, not one per number
    assert api(web, '/api/brief?project=proj&address=code.timer.kitchen&cursor=zz')[0] == 400  # not a cursor given
    work = api(web, '/api/brief?project=proj&address=code.timer.kitchen&kind=work')[1]['items']
    assert [one['kind'] for one in work] == ['work']                     # past forty memories, the one ticket


@pytest.mark.req('MCP-037')
def test_on_a_phone_the_brief_wraps_its_tree_names_its_node_as_the_map_and_clears_the_chat_tab(
        run, web, mapped, browser):
    page, problems = brief_page(run, web, mapped, browser)
    assert [tab.text_content() for tab in page.locator('.tabs[role=tablist] > [role=tab]:visible').all()] == [
        'Object', 'Brief', 'Provenance', 'Prompt']                        # the node group's panes, in their order
    assert 'memories, messages and work' in page.locator('#t-brief').get_attribute('title')
    page.set_viewport_size({'width': 390, 'height': 800})
    page.click('#t-brief')
    page.wait_for_selector('#p-brief ul.items .itemrow')
    tree = page.locator('#p-brief pre.brieftext.tree')
    assert tree.evaluate('box => box.scrollWidth <= box.clientWidth')       # the read it names is never cut off
    assert page.locator('#p-brief h2').text_content() == 'dish timer'
    page.locator('#p-brief ul.items .itemrow').last.scroll_into_view_if_needed()
    page.evaluate("document.querySelector('#p-brief').scrollTop = 1e6")
    covered = page.evaluate("""() => { const tab = document.querySelector('#dockTab')?.getBoundingClientRect();
      if (!tab || !tab.width) return false;
      const last = [...document.querySelectorAll('#p-brief .itemrow')].at(-1).getBoundingClientRect();
      return !(last.bottom <= tab.top || last.top >= tab.bottom || last.right <= tab.left || last.left >= tab.right); }""")
    assert not covered
    page.locator('#p-brief .seeall').focus()
    page.keyboard.press('Enter')
    page.wait_for_selector('#agentview .views [role=tab]', timeout=60000)
    edge = page.evaluate("document.querySelector('#agentview').getBoundingClientRect().right")
    widest = page.evaluate("Math.max(...[...document.querySelectorAll('#agentview .body > :not(.tabs), "
                           "#agentview dl.paid > *, #av-panel > *')].map(box => box.getBoundingClientRect().right))")
    assert widest <= edge + 1, (widest, edge)                             # nothing cut off at the right
    assert problems == []


@pytest.mark.req('MCP-037')
def test_the_brief_and_what_the_agent_sees_are_page_views_and_no_tool_runs_a_verb_that_writes_or_takes_a_file(
        run, web, mapped):
    from metaform import module as chassis
    started(run)
    status, body = api(web, '/api/workspace?project=proj')
    assert status == 200, body
    panes = {pane['id']: pane for pane in body['panes']}
    assert panes['map.brief']['content'] == {'kind': 'page', 'page': 'brief'}
    assert panes['map.agent-view']['content'] == {'kind': 'page', 'page': 'agent-view'}
    assert panes['map.agent-view']['area'] == 'float'                    # the dialog the page opens
    node = next(group for area in body['defaults']['layout']['areas'].values() for group in area['groups']
                if group['id'] == 'node')
    shown = [one for one in node['tabs'] if one not in body['defaults']['layout']['off']]
    assert [panes[one]['content'].get('page') for one in shown if panes[one]['content']['kind'] == 'page'] == [
        'object', 'brief', 'provenance', 'prompt']                        # the page's node tabs, in this order
    items = {item['id']: item for item in body['items']}
    assert items['map.export-mermaid']['action'] == {'kind': 'page', 'page': 'export-mermaid'}
    assert items['map.copy-mermaid']['action'] == {'kind': 'page', 'page': 'copy-mermaid'}
    for owner, toolbar, _ in chassis.contributions(mapped):
        verbs = {verb.name: verb for module in chassis.surface(mapped) if module.id == owner for verb in module.verbs}
        for item in toolbar:
            if item.verb is not None:
                verb = verbs[item.verb]
                assert verb.effect == 'read' and 'file' not in {noun.name for noun in verb.nouns}, (owner, item.id)


@pytest.mark.req('MCP-037')
def test_the_mcp_views_items_page_through_with_the_cursor_each_page_gives_and_kinds_skip_other_modules(
        run, mapped, monkeypatch):
    import dataclasses

    from metaform import module as chassis
    from metaform.data import Store
    from metaform.modules.mcp import server as mcp
    run('set', '--layers', ','.join([*TOGGLED, 'memory']), cwd=mapped)
    remember(run, mapped, 'create_entities', [entity(f'drift {n}', f'Drift seen {n}.') for n in range(20)],
             'element:code.timer.kitchen')
    whole = [one['item'] for one in chassis.node_items(mapped, 'code.timer.kitchen', limit=1000)['items']]
    monkeypatch.setattr(mcp, 'VIEW_LIMIT', 7)
    pages, cursor = [], None
    while True:  # each page's nextCursor passed back unchanged, as MCP pages a list
        page = mcp.view_read(mapped, 'items', {'address': 'code.timer.kitchen', **({'cursor': cursor} if cursor else {})})
        pages.append([one['item'] for one in page['items']])
        cursor = page.get('nextCursor')
        if cursor is None:
            break
    assert len(pages) >= 3 and [item for page in pages for item in page] == whole and len(set(whole)) == len(whole)
    with pytest.raises(chassis.Stop):
        mcp.view_read(mapped, 'items', {'address': 'code.timer.kitchen', 'cursor': 'not one'})
    # a list of one kind reads only the modules that number that kind
    real, asked = chassis.surface, []
    monkeypatch.setattr(chassis, 'surface', lambda folder: [dataclasses.replace(
        module, items_at=lambda ctx, *rest, module=module: asked.append(module.id) or module.items_at(ctx, *rest))
        if module.items_at else module for module in real(folder)])
    work = chassis.node_items(mapped, 'code.timer.kitchen', kinds=('work',))['items']
    assert [one['kind'] for one in work] == ['work'] and 'memory' not in asked and 'map' in asked
    # completing #n reads the address's counter, not its items
    read = []
    monkeypatch.setattr(chassis, 'node_items', lambda *args, **kwargs: read.append(args))
    monkeypatch.setattr(chassis, 'item_read', lambda *args, **kwargs: read.append(args))
    top = Store('proj').latest_number('code.timer.kitchen')
    assert mcp._numbers(mapped, 'code.timer.kitchen', '1') == [f'{n:x}' for n in range(top, 0, -1)
                                                               if f'{n:x}'.startswith('1')]
    assert mcp._numbers(mapped, 'code.timer.kitchen', 'zz') == [] and read == []


@pytest.mark.req('VIEW-011')
def test_a_tool_whose_verb_takes_more_opens_a_typed_form_and_runs_only_with_its_fields(home, monkeypatch):
    """A verb tool that leaves nouns open carries them as a typed form, as the term tool of the glossary does: the
    page fills it in, and the run takes those fields and no others, the fixed arguments and the selection kept."""
    import metaform.modules.web  # noqa: F401  declares the web settings
    from metaform import module as chassis
    from metaform.module import Module, Noun, ToolbarItem, Verb
    from metaform.modules.web import server, workspace
    tool = ToolbarItem('add-term', 'Add term', 'Add a term of the project.', verb='term', arguments={'op': 'add'},
                       selection='node')
    nouns = (Noun('op', 'add or edit.', required=False, schema={'type': 'string', 'enum': ['add', 'edit']}),
             Noun('term', 'Required: the term.', required=False), Noun('node', 'Where.', required=False),
             Noun('count', 'How many.', kind='int', required=False))
    mine = Module(id='mine', summary='Mine.', purpose='Mine.', verbs=(Verb('term', lambda ctx: None, 'Term.', nouns=nouns),),
                  toolbar=(tool,))
    monkeypatch.setattr(chassis, 'contributions', lambda folder: [('mine', (tool,), ())])
    monkeypatch.setattr(workspace, '_module', lambda owner, folder: mine)
    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, owner, verb, arguments: calls.append(arguments) or {'ok': 1})
    state = _call(workspace, 'GET', '/api/workspace').answers[-1][1]
    form = next(item for item in state['items'] if item['id'] == 'mine.add-term')['action']['form']
    assert [(one['name'], one['kind'], one['required']) for one in form] == [('term', 'str', True), ('count', 'int', False)]
    refused = _call(workspace, 'POST', '/api/workspace/run', {'item': 'mine.add-term', 'selection': 'code.app',
                                                              'values': {'op': 'remove'}})
    assert refused.answers[-1][0] == 400 and calls == []                 # a fixed argument is never the form's
    ran = _call(workspace, 'POST', '/api/workspace/run', {'item': 'mine.add-term', 'selection': 'code.app',
                                                          'values': {'term': 'kitchen timer', 'count': ''}})
    assert ran.answers[-1][0] == 200
    assert calls == [{'op': 'add', 'node': 'code.app', 'term': 'kitchen timer'}]


@pytest.mark.req('VIEW-011')
def test_the_developer_panes_and_prompts_exist_only_with_the_developer_level_on(offered, run):
    """Off, the default, there is no developer pane and no prompts read; with web_debug on, both, the prompts read-only
    as the files hold them, each with the comment that says when it is sent and its size."""
    from metaform.modules.web import debug
    state = _call(offered, 'GET', '/api/workspace').answers[-1][1]
    assert {key: state['view'][key] for key in ('shapes', 'flow_seconds', 'idle_flow', 'debug')} == {
        'shapes': True, 'flow_seconds': 30, 'idle_flow': True, 'debug': 'off'}
    assert not [pane for pane in state['panes'] if pane['id'].startswith('web.dev-')]
    handler = _Handler()
    debug.answer(handler, '/api/debug/prompts', {})
    assert handler.answers[-1][0] == 404
    run('set', '--web-debug', 'verbose')
    state = _call(offered, 'GET', '/api/workspace').answers[-1][1]
    assert state['view']['debug'] == 'verbose'
    assert {'web.dev-prompts', 'web.dev-trace'} <= {pane['id'] for pane in state['panes']}
    handler = _Handler()
    debug.answer(handler, '/api/debug/prompts', {})
    status, found = handler.answers[-1]
    assert status == 200 and found['editable'] is False
    resume = next(one for one in found['prompts'] if (one['owner'], one['name']) == ('web', 'resume_run'))
    assert resume['text'] == 'Run <run/> is answered; resume it with metaform workflow resume run=<run/>'
    assert set(resume['fills']) == {'run'} and 'Runs pane' in resume['when'] and resume['bytes'] == len(resume['text'])
    connect = next(one for one in found['prompts'] if (one['owner'], one['name']) == ('web', 'connect'))
    assert connect['budget']['limit'] == 2048 and connect['budget']['unit'] == 'characters'


def test_web_start_and_stop_declare_their_effects_and_the_web_wording_names_the_per_verb_tools():
    from pathlib import Path

    from metaform.modules.web import MODULE
    verbs = {verb.name: verb for verb in MODULE.verbs}
    assert (verbs['start'].effect, verbs['start'].open_world) == ('write', False)
    assert (verbs['stop'].effect, verbs['stop'].open_world) == ('write', False)
    text = (Path(__file__).parents[1] / 'resources' / 'prompts.xml').read_text(encoding='utf-8')
    assert 'with no command' not in text and 'metaform_instructions with module web' in text


@pytest.mark.req('VIEW-005')
def test_what_the_mascot_sees_is_asked_of_the_open_page_and_its_answer_returned_and_with_no_page_it_is_refused(
        run, web, mapped):
    """web see, look and viewing ask the page that shows the project: the server hands the act to the page's event
    stream with an id and returns the page's answer under it; with no page open the act is refused with what to do."""
    import threading
    started(run)
    own = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'}
    asked = json.dumps({'project': 'proj', 'act': 'see'})
    status, body, _ = request(web, '/api/mascot', method='POST', headers=own, body=asked)
    assert status == 409 and 'open the page' in json.loads(body)['next']
    heard = []

    def page():  # a page open on the project: it hears the act and answers it
        connection = http.client.HTTPConnection('127.0.0.1', web, timeout=10)
        connection.request('GET', '/api/events?project=proj', headers={'Host': f'127.0.0.1:{web}'})
        stream = connection.getresponse()
        while True:
            line = stream.fp.readline().decode('utf-8')
            if line.startswith('data: '):
                event = json.loads(line[6:])
                if event['topic'] == 'mascot':
                    heard.append(event['payload'])
                    if event['payload']['act'] == 'see':
                        request(web, '/api/mascot-result', method='POST', headers=own, body=json.dumps(
                            {'project': 'proj', 'id': event['payload']['id'], 'result': {'in_view': ['code.alarm.audible']}}))
                        return
    listening = threading.Thread(target=page, daemon=True)
    listening.start()
    for _ in range(50):  # the page's stream is open once the server counts it
        status, body, _ = request(web, '/api/mascot', method='POST', headers=own,
                                  body=json.dumps({'project': 'proj', 'act': 'say', 'text': 'hello'}))
        if status == 200:
            break
        time.sleep(0.1)
    status, body, _ = request(web, '/api/mascot', method='POST', headers=own, body=asked)
    listening.join(10)
    assert status == 200 and json.loads(body) == {'in_view': ['code.alarm.audible']}
    assert heard[-1]['act'] == 'see' and heard[-1]['id'] and {one['act'] for one in heard} == {'say', 'see'}


@pytest.mark.req('VIEW-042')
def test_a_run_paused_on_the_person_is_listed_with_its_reason_answered_and_cancelled_from_the_page(run, web, mapped):
    """H03's page side: the Runs pane reads the open runs with what stopped a paused one, takes the person's answer
    through the person's own command line, and cancels a run, asked first on the page; with workflow off it says so."""
    from metaform.data import Store
    from metaform.modules.workflow import executor, runs
    from metaform.modules.workflow.tests.test_executor import begin
    started(run)
    assert api(web, '/api/workflow-runs?project=proj') == (200, {'enabled': False, 'runs': []})
    run('enable', 'workflow')
    store = Store('proj', module='workflow')
    word = begin(store)
    executor.pause(store, word, 'The target code.timer.kitchen is gone and the logic names no other.')
    status, found = api(web, '/api/workflow-runs?project=proj')
    assert status == 200 and found['enabled'] is True
    paused = next(one for one in found['runs'] if one['run'] == word)
    assert paused['state'] == 'input_required' and 'is gone' in paused['message']
    own = {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'}
    status, body, _ = request(web, '/api/workflow-answer', method='POST', headers=own,
                              body=json.dumps({'project': 'proj', 'run': word, 'answer': 'use the alarm', 'resume': True}))
    assert status == 200, body
    assert executor.view(store, word)['answer']['answer'] == 'use the alarm'
    assert 'resumed' not in json.loads(body)                       # no ticket's agent paused it, so none is told
    status, body, _ = request(web, '/api/workflow-cancel', method='POST', headers=own,
                              body=json.dumps({'project': 'proj', 'run': word, 'reason': 'not needed'}))
    assert status == 200, body
    assert runs.read(store, word).state == 'cancelled'
    stranger = {**own, 'Origin': 'http://elsewhere.example'}
    assert request(web, '/api/workflow-cancel', method='POST', headers=stranger,
                   body=json.dumps({'project': 'proj', 'run': word}))[0] == 403


@pytest.mark.req('MCP-037')
def test_the_brief_read_names_the_latest_item_and_the_range_the_last_session_numbered(run, web, mapped):
    """H19's page side: /api/brief, the read every surface shares, carries the latest item with its title and the
    range of numbers the last agent session took at the node, as the brief's line under the node says them."""
    for title in ('First look', 'Second look'):
        run('map', 'ask', 'element:code.timer.kitchen', 'Which clock?', f'title={title}', 'why=The drift depends on it',
            cwd=mapped, env={'METAFORM_SESSION': 'session-one'})
    started(run)
    status, body = api(web, '/api/brief?project=proj&address=code.timer.kitchen')
    assert status == 200, body
    assert body['latest']['title'] == 'Second look'
    last = body['last_session']
    assert last['session'] == 'session-one' and last['count'] == 2 and last['last'] == body['latest']['number']
    assert last['first'] == last['last'] - 1


@pytest.mark.req('BASE-045')
def test_report_a_problem_saves_one_zip_with_the_browser_the_console_errors_and_no_secret(run, web, mapped, browser,
                                                                                            home):
    """Report a problem, in the View menu, saves the report `metaform report` makes, with this browser and the page's
    console errors, every secret masked and none of the project's files; it says where to send it."""
    import io
    import zipfile
    (home / 'run').mkdir(parents=True, exist_ok=True)
    (home / 'run' / 'web.log').write_text(
        'Traceback (most recent call last):\n  File "x.py", line 1, in y\nValueError: PLANTED-WEB-ERROR\n'
        'asked with api_key=sk-or-v1-PLANTEDKEY0123456789abcdef\n', encoding='utf-8')
    (mapped / 'own.py').write_text('PROJECT-OWN-TEXT\n', encoding='utf-8')
    started(run)
    page, problems, _ = opened(browser, web, plain=True)
    page.evaluate("console.error('PLANTED-PAGE-ERROR Bearer ghp_PLANTEDTOKEN0123456789abcdefABCD')")
    page.click('#settingsBtn')
    page.click('#reportBtn')
    page.fill('#reportWhat', 'The map went blank after I opened Agents.')
    with page.expect_download() as caught:
        page.click('#reportMake')
    download = caught.value
    assert re.fullmatch(r'metaform-report-\d{8}T\d{6}Z\.zip', download.suggested_filename)
    page.wait_for_function("() => document.querySelector('#reportSaid').textContent.includes('rchgrav on Discord')")
    with zipfile.ZipFile(io.BytesIO(Path(download.path()).read_bytes())) as made:
        texts = {name: made.read(name).decode('utf-8') for name in made.namelist()}
    assert 'The map went blank after I opened Agents.' in texts['report.txt']
    assert 'HeadlessChrome' in texts['report.txt'] and 'Metaform: ' in texts['report.txt']
    assert 'PLANTED-PAGE-ERROR' in texts['page/console.txt'] and 'PLANTED-WEB-ERROR' in texts['errors.txt']
    every = ''.join(texts.values())
    assert 'PLANTEDKEY' not in every and 'PLANTEDTOKEN' not in every and '****ef' in every
    assert 'PROJECT-OWN-TEXT' not in every and not any(name.startswith('project/') for name in texts)
    assert [problem for problem in problems if 'PLANTED-PAGE-ERROR' not in problem] == []


@pytest.mark.req('VIEW-002')
def test_a_fault_or_refusal_on_a_read_is_answered_as_error_and_next_json_and_logged_once(run, web, mapped, home):
    """A read the server fails on, here a store that is no database, is answered 500 with {error, next}, never a
    dropped connection; a refusal is answered with its next step; each is logged once, however often it is asked."""
    started(run)
    store = own('proj') / 'project.sqlite3'
    kept = store.read_bytes()
    try:
        store.write_bytes(b'not a database ' * 400)
        for _ in range(2):
            status, body, headers = request(web, '/api/graph?project=proj')
            assert status == 500 and headers['Content-Type'] == 'application/json', body
            said = json.loads(body)
            assert 'DatabaseError' in said['error'] and said['next'].startswith('metaform report'), said
    finally:
        store.write_bytes(kept)
    for _ in range(2):
        status, said = api(web, '/api/graph?project=nothing-here')
        assert status == 404 and said['error'] and said['next'], said
    status, body, headers = request(web, '/api/graph', method='PUT')  # the standard library's own refusal
    assert status == 501 and headers['Content-Type'] == 'application/json' and json.loads(body)['error'], body
    log = (home / 'run' / 'web.log').read_text(encoding='utf-8')
    assert log.count('Fault answering GET /api/graph') == 1, log
    assert log.count('Refused GET /api/graph (404)') == 1, log


@pytest.mark.req('VIEW-051')
def test_a_refused_map_read_and_a_page_fault_each_show_a_banner_with_the_next_step_and_report(run, web, mapped,
                                                                                               browser):
    """The server refusing the map read leaves no blank page: a banner says what happened, the server's next step and
    offers Report a problem, which opens the report with the problem's words; the map is not called empty. An
    exception in a page part shows a banner too."""
    started(run)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    refusal = {'error': 'PLANTED refusal of the map read.', 'next': 'metaform map where code'}
    page.route('**/api/graph?*', lambda route: route.fulfill(status=404, content_type='application/json',
                                                             body=json.dumps(refusal)))
    page.goto(f'http://127.0.0.1:{web}/#p=proj')
    page.wait_for_selector('#banners .banner.error', state='visible')
    words = page.inner_text('#banners .banner')
    assert 'The map could not be read' in words and refusal['error'] in words and refusal['next'] in words, words
    assert page.is_hidden('#emptyStage')  # a map that could not be read is not called empty
    page.click('#banners .banner .btn.primary')
    page.wait_for_selector('#report', state='visible')
    assert refusal['error'] in page.input_value('#reportWhat')
    page.keyboard.press('Escape')
    page.evaluate("() => { setTimeout(() => { throw new Error('PLANTED fault in a page part'); }); }")
    page.wait_for_function("() => [...document.querySelectorAll('#banners .banner')].some(one =>"
                           " one.innerText.includes('Part of the page failed')"
                           " && one.innerText.includes('PLANTED fault in a page part'))")


@pytest.mark.req('CLI-042')
def test_the_demo_card_is_served_only_from_the_home_the_demo_wrote_it_in(home):
    from metaform.modules.web.server import demo_card
    assert demo_card() == {'demo': None}
    home.mkdir(parents=True, exist_ok=True)
    (home / 'demo.json').write_text(json.dumps({'lines': ['one', 'two']}), encoding='utf-8')
    assert demo_card() == {'demo': {'lines': ['one', 'two']}}


@pytest.mark.req('VIEW-005')
def test_web_viewing_reads_how_the_mascot_moved_on_the_page_so_a_shake_can_be_named(run, web, mapped, browser):
    """web_viewing answers with the mascot's last seconds of motion on the page that answered: per channel its range,
    its usual step and how often its steps turn back a second, with the frame times, the page and whether it speaks.
    A body that shakes shows as a channel turning back many times a second; speaking, its size pulses. Before,
    nothing read how the body moved on the person's own page, 2026-10-16, code.assistant.navigation#6."""
    from metaform.data import Node, Store
    run('enable', 'dispatch')
    run('set', '--web-mascot=seahorse')
    system = Store('proj').add_work(Node('element', 'code.alarm.audible'), None,
                                    task='Conversation with the system agent', held=True)
    live_session(system.id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    page.evaluate(f'window.metaform.embody("{system.id}", "seahorse")')  # the person gives it its body
    page.wait_for_function('() => window.metaform.mascot().shown', timeout=15000)
    page.wait_for_timeout(2500)

    def motion():
        return json.loads(run('web', 'viewing', '--json', cwd=mapped).stdout)['mascot_motion']

    still = motion()
    assert still['glyph'] == 'seahorse' and still['frames'] > 10 and still['speaking'] == 0, still
    assert {'screen_x', 'yaw', 'scale', 'body_lean', 'want_x', 'camera_z'} <= set(still['channels']), still
    assert len(still['frame_ms']) == 3 and still['loaded'] and still['page'], still
    assert still['channels']['scale'][3] < 1, still                    # at rest its size holds
    page.evaluate('window.metaform.mascotSpeaking(true)')
    page.wait_for_timeout(2500)
    talking = motion()
    assert talking['speech']['mascot'] is True and talking['speaking'] > 0.3, talking
    assert talking['channels']['scale'][3] > 2, talking                # the speaking pulse turns back, about 5.7 a second
    page.evaluate('window.metaform.mascotSpeaking(false)')
    assert problems == []


@pytest.mark.req('VIEW-045')
@pytest.mark.req('BASE-039')
@pytest.mark.skipif(os.name == 'nt', reason='SIGKILL')
def test_an_intake_agent_killed_leaves_the_page_at_once_with_nothing_read_by_hand(
        run, home, web, browser, tmp_path, dispatch_runners):
    """UX review round 2, 2026-10-17 (intake-single-flight F1): a dispatched intake whose runner was killed went on
    showing as at work on the page for as long as anyone watched, since a death said nothing and the page reads again
    only when a change is announced. The runner's lease wakes the page server's watch as it dies; the server ends what
    it left and announces the change, and the bar goes within moments, with no other call made."""
    import signal

    from metaform.data import Store
    from metaform.modules.dispatch.tests.test_dispatch import eventually, gone
    folder, log = tmp_path / 'cli', tmp_path / 'fake.jsonl'
    folder.mkdir()
    run('add', 'project', 'cli', str(folder))
    run('enable', 'dispatch')
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'})
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.goto(f'http://127.0.0.1:{web}/#p=cli')
    page.wait_for_selector('#emptyStage:not([hidden])', timeout=60000)
    started = json.loads(run('dispatch', 'intake', 'agent=claude', '--json', cwd=folder,
                             env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}).stdout)
    dispatch_runners.append((started, folder, log))
    page.wait_for_selector('#intakeBar:not([hidden]) .doing:has-text("Waiting for the first record")', timeout=30000)
    agent = eventually(lambda: next((one['pid'] for one in map(json.loads, log.read_text().splitlines())
                                     if 'pid' in one), None) if log.exists() else None)

    def launch_kept():
        with Store('cli', module='dispatch').tables(write=False) as tx:
            return tx.rows('raised', limit=0).results
    eventually(lambda: not launch_kept())  # the last change its start makes is heard before the kill, not after it
    page.wait_for_timeout(1500)
    os.killpg(started['pid'], signal.SIGKILL)
    page.wait_for_selector('#intakeBar', state='hidden', timeout=5000)
    assert gone([agent]), 'its agent, in a group of its own, is ended by the server that heard the death'


@pytest.mark.req('VIEW-018')
@pytest.mark.req('VIEW-042')
def test_an_agent_started_and_recalled_from_the_page_moves_no_part_drawn_on_a_large_collapsed_map(
        run, home, tmp_path, web, browser, dispatch_runners):
    """UX recheck 2026-10-17, Findings 1 and 2: on a map of about a thousand parts, opened collapsed, starting an agent
    on a ticket and recalling it from the board each sent a change that named nothing, so the page read the whole map
    again, gave the 3D graph three datasets and every part drawn moved, by up to 519 units. Each now names its tables
    and its ticket: no change without tables reaches the page, the 3D graph is given at most one dataset, and the parts
    drawn before stay within a unit of where they stood. The board offers Recall agent only on the ticket an agent
    runs on, and says when the recall is done."""
    from metaform.data import Node, Store
    from metaform.modules.dispatch.tests.test_dispatch import eventually
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance=PROVENANCE, ready=True)
        store.add_element(intake.name, 'stakeholder.person', name_length=1, role='CQU')
        store.add_element(intake.name, 'code.engine', name_length=1, role='DE')
        store.add_join(intake.name, 'stakeholder.person', 'code.engine', purpose='Get the job done.', ef='Runs it.')
        for branch in range(40):
            part = f'code.engine.part{branch}'
            store.add_element(intake.name, part, name_length=1, role='SE')
            store.add_join(intake.name, 'code.engine', part, purpose=f'Need part {branch}.', ef=f'Gives {branch}.')
            for leaf in range(24):
                store.add_element(intake.name, f'{part}.unit{leaf}', name_length=1, role='SE')
                store.add_join(intake.name, part, f'{part}.unit{leaf}', purpose=f'Need unit {leaf}.',
                               ef=f'Does unit {leaf}.')
    ticket = store.add_work(Node('element', 'code.engine.part7.unit3'), 'unbuilt', task='Make unit 3 faster.',
                            title='Faster unit').id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    fake = {'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'hold'}
    # a project agents have worked in before: one start and stop made the tables they keep, whose making is a change
    # to the store's own schema, which a page reads whole
    before = store.add_work(Node('element', 'code.engine.part2.unit1'), 'unbuilt', task='Warm up.').id
    dispatch_runners.append((json.loads(run('dispatch', 'start', before, 'claude', '--json', cwd=folder,
                                            env=fake).stdout), folder, log))
    eventually(lambda: (Store('proj').ticket(before).work.taken_by or '').startswith('claude '), limit=30)
    run('dispatch', 'stop', before, cwd=folder)
    run('web', '--json', env=fake)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=60000)
    assert page.evaluate('window.metaform.drawn().nodes') < 400, 'the large map opens collapsed'
    # what reaches the page on its stream, and each dataset the 3D graph is given
    page.evaluate("""async () => {
        window.heard = []; window.given = [];
        const stream = new EventSource('/api/events?project=proj');
        stream.onmessage = message => { const event = JSON.parse(message.data);
            if (event.topic === 'map.changed') window.heard.push(event.payload); };
        const {G} = await import('/page/app/map3d/graph3d.js');
        const graphData = G.graphData.bind(G);
        G.graphData = (...given) => { if (given.length) window.given.push(given[0].nodes.length);
            return graphData(...given); };
    }""")
    places = """async () => { const {G} = await import('/page/app/map3d/graph3d.js');
        return Object.fromEntries(G.graphData().nodes.filter(node => node.x !== undefined)
            .map(node => [node.id, [node.x, node.y, node.z]])); }"""
    frames = "async () => { const {FRAMES} = await import('/page/app/map3d/graph3d.js'); return FRAMES.drawn; }"

    def at_rest():
        """The 3D layout still over ten frames drawn."""
        deadline, before, since = time.monotonic() + 60, None, None
        while True:
            now, count = page.evaluate(places), page.evaluate(frames)
            if before is not None and before == now and count - since >= 10:
                return now
            if before != now:
                before, since = now, count
            assert time.monotonic() < deadline, 'the 3D layout never came to rest'
            page.wait_for_timeout(300)

    def most_moved(before):
        now = page.evaluate(places)
        return max(math.dist(spot, now[key]) for key, spot in before.items() if key in now)

    def watched(act):
        """What an act of the person's sends the page over five seconds, and how far the parts drawn before it move."""
        before = at_rest()
        page.evaluate('window.heard.length = 0; window.given.length = 0')
        act()
        page.wait_for_timeout(5000)
        return page.evaluate('window.heard'), page.evaluate('window.given'), most_moved(before)

    def start():
        page.evaluate(f"async () => (await import('/page/app/agents/dispatch.js')).startAgent('{ticket}', 'claude')")
        eventually(lambda: [one for one in store_sessions() if one['state'] == 'running' and one['work_id'] == ticket],
                   limit=30)

    def store_sessions():
        with Store('proj', module='dispatch').tables(write=False) as tx:
            return [dict(row) for row in tx.rows('agent_sessions', limit=0).results]

    heard, given, moved = watched(start)
    dispatch_runners.extend((dict(one), folder, log) for one in store_sessions() if one['work_id'] == ticket)
    assert [one for one in heard if 'tables' not in one] == [], heard
    assert any(one.get('work_ids') == [ticket] and 'ticket' in one.get('kinds', []) for one in heard), heard
    assert len(given) <= 1 and moved <= 1, (given, moved, heard)
    page.click('#boardBtn')
    page.wait_for_selector('#board:not([hidden]) .card')
    page.wait_for_function('() => document.querySelectorAll("#board button.recall").length === 1')
    page.evaluate("""() => { window.toasts = [];
        new MutationObserver(() => window.toasts.push(document.querySelector('#toast').textContent))
            .observe(document.querySelector('#toast'), {childList: true, characterData: true, subtree: true}); }""")
    heard, given, moved = watched(lambda: page.evaluate('document.querySelector("#board button.recall").click()'))
    assert not [one for one in store_sessions() if one['state'] == 'running']
    assert [one for one in heard if 'tables' not in one] == [], heard
    assert len(given) <= 1 and moved <= 1, (given, moved)
    assert any('recalled' in toast for toast in page.evaluate('window.toasts')), page.evaluate('window.toasts')
    assert page.evaluate('document.querySelectorAll("#board button.recall").length') == 0
    assert not problems


@pytest.mark.parametrize('selected', [None, False, True])
def test_roundtable_creation_forwards_explicit_automation_with_default_off(monkeypatch, selected):
    from metaform.modules.web import server

    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda given, owner, verb, arguments: calls.append(
        (owner, verb, arguments)) or {'table': 'created'})
    given = {'topic': ' Prepare tickets ', 'address': ' code.timer.kitchen ', 'seats': ['codex/sol']}
    if selected is not None:
        given['automate_ticket_creation'] = selected
    handler = _Handler()
    server.Handler.roundtable_open(handler, given)
    assert handler.answers == [(200, {'table': 'created'})]
    assert calls == [('roundtables', 'open', {'topic': 'Prepare tickets', 'address': 'code.timer.kitchen',
        'seats': ['codex/sol'], 'automate_ticket_creation': selected is True})]


@pytest.mark.parametrize('invalid', ['false', 'true', 0, 1, None, []])
def test_roundtable_creation_rejects_non_boolean_automation(monkeypatch, invalid):
    from metaform.modules.web import server

    calls = []
    monkeypatch.setattr(server, 'module_verb', lambda *args: calls.append(args))
    handler = _Handler()
    server.Handler.roundtable_open(handler, {'topic': 'Prepare tickets', 'automate_ticket_creation': invalid})
    assert handler.answers == [(400, {'error': 'Automate Ticket Creation is true or false.'})]
    assert calls == []


def test_roundtable_saved_files_are_read_from_its_own_record(run, web, mapped):
    from metaform.data import Store

    run('enable', 'roundtables', cwd=mapped)
    saved = 'docs/roundtables/7-results'
    record = mapped / saved
    record.mkdir(parents=True)
    (record / 'export.json').write_text('{"topics": []}\n', encoding='utf-8')
    (record / 'mechanical-report.md').write_text('Full transcript.\n', encoding='utf-8')
    (record / 'private.txt').write_text('Private.\n', encoding='utf-8')
    store = Store('proj', module='roundtables')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'finished', 'topic': 'Results?', 'opening': '.', 'seats': [],
                             'spend': 0.0, 'state': 'ended', 'created': '2026-10-21T00:00:00Z',
                             'followed': {'saved': saved, 'result_topics': []}})
        tx.insert('tables', {'table_id': 'not-saved', 'topic': 'Pending?', 'opening': '.', 'seats': [],
                             'spend': 0.0, 'state': 'running', 'created': '2026-10-21T00:00:00Z'})
    started(run)
    url = '/api/roundtable?project=proj&table=finished&file='
    status, body, _ = request(web, url + 'export.json')
    assert status == 200 and json.loads(body) == {'topics': []}
    status, body, _ = request(web, url + 'mechanical-report.md')
    assert status == 200 and body == 'Full transcript.\n'
    assert api(web, url + 'private.txt')[0] == 400
    assert api(web, url + '..%2Fprivate.txt')[0] == 400
    assert api(web, '/api/roundtable?project=proj&table=not-saved&file=export.json')[0] == 404
    assert api(web, '/api/roundtable?project=proj&table=missing&file=export.json')[0] == 400


def test_roundtable_pipeline_review_and_person_decision_use_the_exact_revision(run, web, mapped):
    import hashlib

    from metaform.data import Store

    run('enable', 'roundtables', cwd=mapped)
    saved = 'docs/roundtables/8-pipeline'
    folder = mapped / saved
    folder.mkdir(parents=True)
    text = '# Full plan\nRetain every proposed task.\n'
    (folder / 'plan.md').write_text(text, encoding='utf-8')
    digest = hashlib.sha256(text.encode()).hexdigest()
    store = Store('proj', module='roundtables')
    with store.tables() as tx:
        tx.insert('tables', {'table_id': 'pipeline', 'topic': 'What next?', 'opening': '.', 'seats': [],
                             'spend': 0.0, 'state': 'ended', 'created': '2026-10-21T00:00:00Z',
                             'followed': {'saved': saved}})
        tx.insert('pipelines', {'table_id': 'pipeline', 'stage': 'plan_review', 'state': 'awaiting',
                               'file': f'{saved}/plan.md', 'digest': digest, 'revision': 1,
                               'created': '2026-10-21T00:00:00Z'})
    started(run)
    url = '/api/roundtable?project=proj&table=pipeline'
    status, reviewed = api(web, url + '&pipeline=1')
    assert status == 200 and reviewed['output_text'] == text
    assert reviewed['pipeline']['digest'] == digest
    assert request(web, url + '&file=plan.md')[1] == text
    (folder / 'facilitation.md').write_text('Delivered board outcomes.', encoding='utf-8')
    assert request(web, url + '&file=facilitation.md')[1] == 'Delivered board outcomes.'
    assert 'output_text' not in api(web, url + '&whole=1')[1]['status']

    def decide(action, revision=1, comment=''):
        return request(web, '/api/roundtable-decision', method='POST', body=json.dumps({
            'project': 'proj', 'table': 'pipeline', 'action': action, 'digest': digest,
            'revision': revision, 'comment': comment}), headers={
                'Origin': f'http://127.0.0.1:{web}', 'Content-Type': 'application/json'})

    # Plan review requires approval, so a generic yes cannot start Decomposer.
    assert decide('yes')[0] == 400
    response = decide('comment', comment='Keep the full task list.')
    assert response[0] == 200, response
    kept = json.loads(response[1])['pipeline']
    assert kept['stage'] == 'plan_review' and kept['state'] == 'awaiting' and kept['revision'] == 2
    assert 'Keep the full task list.' in kept['feedback']
    assert decide('no')[0] == 400  # Same bytes cannot authorize a stale revision.
    changed = '# Full plan\nA different task list.\n'
    (folder / 'plan.md').write_text(changed, encoding='utf-8')
    stale = decide('no', revision=2)
    assert stale[0] == 400 and 'changed' in json.loads(stale[1])['error'].lower()
    (folder / 'plan.md').write_text(text, encoding='utf-8')
    response = decide('no', revision=2)
    assert response[0] == 200 and json.loads(response[1])['pipeline']['state'] == 'stopped', response
