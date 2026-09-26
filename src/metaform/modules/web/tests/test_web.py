"""The web module: one web GUI server per Metaform home, started and stopped from any folder, VIEW-001, VIEW-002, VIEW-015."""
from __future__ import annotations

import http.client
import json
import socket
import time

import pytest

pytestmark = pytest.mark.kind('fixture')

NOTICE = ('After an intake, start the web GUI with metaform web, or the web_start tool, if it is not already running. '
          'If it was not running, tell the user its address once it starts, and its token when it gives one.')


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def request(port, path='/', *, address='127.0.0.1', host=None, method='GET', body=None, headers=None):
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
        return response.status, response.read().decode('utf-8'), dict(response.getheaders())
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
    assert run('intake', 'prompt', cwd=folder).stdout.startswith('<')
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
    assert request(web, '/api/projects', address=lan, headers={'Cookie': cookie[:-1] + 'x'})[0] == 403
    assert started(run)['token'] == token


@pytest.mark.req('VIEW-015')
def test_the_autostart_setting_puts_the_notice_in_what_agents_read(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    assert NOTICE in run('help', 'agents', cwd=folder).stdout
    run('set', '--no-web-autostart', cwd=folder)
    assert NOTICE not in run('help', 'agents', cwd=folder).stdout


PROVENANCE = {'module': 'test', 'workflow': 'fixture', 'prompt': 'Write the fixture.', 'model': 'none',
              'role': 'fixture writer', 'blinded': False}
KNOWLEDGE = ['notes', 'extra', 'secret']
TOGGLED = ['intake-1', *KNOWLEDGE]


def build(store):
    """An intake with a flagged DE and a subtype; a knowledge layer on, one masked at code.alarm, one hidden; and a
    knowledge item orphaned when a correction removes its element, VIEW-004."""
    from metaform.data import Node
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance=PROVENANCE, ready=True)
        store.add_element(intake.name, 'exterior.cook', name='cook', name_length=1, role='VE')
        store.add_element(intake.name, 'code.timer.kitchen', name='kitchen timer', name_length=2, role='DE',
                          flag='broken', flag_note='drifts')
        store.add_element(intake.name, 'code.alarm.audible', name='audible alarm', name_length=2, role='SE')
        store.add_element(intake.name, 'code.gone', name='gone', name_length=1, role='SE')
        outer = store.add_join(intake.name, 'exterior.cook', 'code.timer.kitchen', purpose='Know when food is done.',
                               function='Counts down and rings.', relation='The timer tells the cook.',
                               observation='One countdown per dish.')
        store.add_join(intake.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       function='Plays a tone.', relation='The alarm rings for the timer.', observation='A piezo.')
        store.add_subtype(intake.name, outer.join_id, 'code.loop.tick', function='Advances each countdown.',
                          relation='The tick loop drives the timer.', observation='One tick a second.',
                          name='tick loop', name_length=2, role='SE')
    for name in KNOWLEDGE:
        store.layer(name, 'test', f'What {name} says.', mutable=True, hideable=True, provenance=PROVENANCE)
    store.add_element('notes', 'code.timer.kitchen.display', name='display', name_length=1)
    store.add_join('notes', 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='Show the time left.',
                   function='Reports the time left.', relation='The timer feeds the display.', observation='LCD')
    store.add_item('notes', Node('element', 'code.timer.kitchen'), 'keep the loop small')
    store.add_item('notes', Node('element', 'code.gone'), 'the loop drifts here')
    store.add_element('extra', 'code.alarm.audible.loud', name='loud', name_length=1)
    store.add_item('extra', Node('element', 'code.alarm.audible'), 'louder is better')
    store.add_element('secret', 'code.secret', name='secret', name_length=1)
    for name in KNOWLEDGE:
        store.finish(name)
    store.mask('code.alarm', 'extra')
    store.hide('secret')
    fix = store.layer('fix-1', 'test', 'Corrections.', kind='correction', mutable=False, hideable=False,
                      provenance=PROVENANCE)
    store.correct(fix.name, store.element('code.gone').element_id, remove=True, reason='It is not there.')
    store.finish(fix.name)


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
        '/api/findings': lambda raw: store.findings(raw=raw),
        '/api/search?text=loop': lambda raw: store.search('loop'),
        '/api/stack': lambda raw: store.stack(),
        '/api/provenance?layer=notes': lambda raw: store.provenance('notes'),
        '/api/metaforms': lambda raw: store.metaforms(),
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
    assert body != api(web, '/api/node?project=proj&target=element:code.timer.kitchen&layers=')[1]
    assert api(web, '/api/roots?project=nobody')[0] == 404


@pytest.mark.req('VIEW-004')
def test_the_page_data_for_a_node_is_what_map_node_returns(run, web, mapped):
    started(run)
    for node in ('element:code.timer.kitchen', 'element:exterior.cook', 'subtype:code.loop.tick'):
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
    assert pages == 2
    parents = {element['element']['address']: element['parent'] for element in elements}
    assert len(parents) == len(elements)
    assert parents == {'exterior.cook': None, 'code.timer.kitchen': None, 'code.alarm.audible': None,
                       'code.timer.kitchen.display': 'code.timer.kitchen'}
    pairs = sorted((join['receiver_address'], join['provider_address']) for join in joins)
    assert pairs == [('code.timer.kitchen', 'code.alarm.audible'), ('code.timer.kitchen.display', 'code.timer.kitchen'),
                     ('exterior.cook', 'code.timer.kitchen')]
    held = {join['provider_address']: [subtype['address'] for subtype in join['subtypes']] for join in joins}
    assert held['code.timer.kitchen'] == ['code.loop.tick'] and held['code.alarm.audible'] == []
    raw = api(web, '/api/graph?project=proj&raw=true&limit=0')[1]
    shown = {entry['element']['address'] for entry in raw['elements']}
    assert {'code.alarm.audible.loud', 'code.secret'} <= shown and 'code.gone' not in shown


@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('VIEW-002')
def test_reading_changes_nothing_and_applying_layers_is_a_write_only_from_the_gui_itself(run, home, web, mapped):
    started(run)
    stores = sorted((home / 'projects').rglob('*.sqlite3')) + [home / 'metaform.sqlite3']
    before = [path.read_bytes() for path in stores]
    shown = run('config', '--show', '--json', cwd=mapped).stdout
    for path in ('/api/projects', '/api/metaforms?project=proj', '/api/roots?project=proj',
                 '/api/graph?project=proj&limit=0', '/api/graph?project=proj&raw=true&layers=notes',
                 '/api/children?project=proj&address=code', '/api/node?project=proj&target=element:code.timer.kitchen',
                 '/api/joins?project=proj&element=code.timer.kitchen', '/api/layers?project=proj',
                 '/api/findings?project=proj', '/api/search?project=proj&text=loop', '/api/stack?project=proj',
                 '/api/provenance?project=proj&layer=notes'):
        assert request(web, path)[0] == 200, path
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
