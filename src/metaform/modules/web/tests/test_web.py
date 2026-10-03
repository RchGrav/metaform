"""The web module: one web GUI server per Metaform home, started and stopped from any folder, VIEW-001, VIEW-002, VIEW-015."""
from __future__ import annotations

import http.client
import json
import math
import socket
import time
from pathlib import Path

import pytest


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
        return response.status, response.read().decode('utf-8', errors='replace'), dict(response.getheaders())
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
    served = Path(__file__).parents[5] / 'specifications' / 'Intake_2.1.md'  # the served intake, BASE-039
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


@pytest.mark.req('VIEW-015')
def test_the_autostart_setting_puts_the_web_message_in_what_agents_read_only_while_it_is_on(run, tmp_path):
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    line = prompt('instructions') + ' ' + prompt('autostart')
    assert line in run('help', 'agents', cwd=folder).stdout.splitlines()
    run('set', '--no-web-autostart', cwd=folder)
    served = run('help', 'agents', cwd=folder).stdout
    assert prompt('instructions') in served.splitlines() and prompt('autostart') not in served


PROVENANCE = {'module': 'test', 'workflow': 'fixture', 'prompt': 'Write the fixture.', 'model': 'none',
              'role': 'fixture writer', 'blinded': False}
KNOWLEDGE = ['notes', 'extra', 'secret']
TOGGLED = ['intake-1', *KNOWLEDGE]


def build(store):
    """An intake with a DE carrying a broken work record and a subtype; a knowledge layer on, one masked at code.alarm, one hidden; and a
    knowledge item orphaned when a refinement removes its element, VIEW-004 and LAYER-025."""
    from metaform.data import Node
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance=PROVENANCE, ready=True)
        store.add_element(intake.name, 'exterior.cook', name_length=1, role='CQU')
        store.add_element(intake.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(intake.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_element(intake.name, 'code.gone', name_length=1, role='SE')
        outer = store.add_join(intake.name, 'exterior.cook', 'code.timer.kitchen', name='dish timer',
                               purpose='Know when food is done.',
                               ef='Counts down and rings.')
        store.add_join(intake.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
        store.add_subtype(intake.name, outer.join_id, 'code.loop.tick', ef='Advances each countdown.',
                          name='one-second tick', name_length=2, role='SE')
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
    store.refine(store.element('code.gone').element_id, remove=True, reason='It is not there.')


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
    assert body != api(web, '/api/node?project=proj&target=element:code.timer.kitchen&layers=intake-1')[1]
    assert api(web, '/api/roots?project=nobody')[0] == 404


@pytest.mark.req('VIEW-004')
def test_the_page_data_for_a_node_is_what_map_node_returns(run, web, mapped):
    from metaform.data import Store
    started(run)
    store = Store('proj')
    tick = store.subtypes(store.joins('exterior.cook').results[0].join_id).results[0].join_id
    for node in ('element:code.timer.kitchen', 'element:exterior.cook', f'join:{tick}', 'element:code.loop.tick'):
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
    remember(run, mapped, 'create_entities', [entity('drift', 'Drifts under load.')], 'element:code.timer.kitchen')
    run('memory', 'note', 'element:code.timer.kitchen', 'text=Keep the loop small.', cwd=mapped)
    started(run)
    stores = sorted((home / 'projects').rglob('*.sqlite3')) + [home / 'metaform.sqlite3']
    assert any(path.name == 'memory.sqlite3' for path in stores)  # the memory module's store, with rows, is read too
    before = [path.read_bytes() for path in stores]
    shown = run('config', '--show', '--json', cwd=mapped).stdout
    for path in ('/api/projects', '/api/metaforms?project=proj', '/api/roots?project=proj',
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
    assert script.split() == ['script-src', "'self'", f"'sha256-{digest}'"]
    assert json.loads(inline[0][1]) == {'imports': {'three': '/vendor/three.module.min.js',
                                                    'three/addons/': '/vendor/three-addons/'}}  # the figures, VIEW-035
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
    licenses = ['mermaid.LICENSE', '3d-force-graph.LICENSE', 'three.LICENSE', 'fonts/IBM-Plex.LICENSE',
                'codemirror/LICENSE', 'drei-vanilla/LICENSE']
    assert all(f'metaform/modules/web/vendor/{license}' in names for license in licenses)


@pytest.fixture
def browser():
    """Headless Chromium through Playwright, a dev dependency; WebGL runs in software, VIEW-012."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as driver:
        launched = driver.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                                                '--ignore-gpu-blocklist'])
        yield launched
        launched.close()


def opened(browser, port, clock=False):
    """The page open on the project; with `clock`, on Playwright's clock, which runs as time does until a test holds
    it and steps it."""
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    if clock:
        page.clock.install()
    own = f'http://127.0.0.1:{port}/'
    problems, remote = [], []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
    page.on('request', lambda sent: None if sent.url.startswith((own, 'data:', 'blob:')) else remote.append(sent.url))
    page.goto(own + '#p=proj')
    page.wait_for_function('() => window.metaform && document.querySelectorAll("#map2d svg g.node").length > 0',
                           timeout=30000)
    return page, problems, remote


def set_layer(page, name, on):
    """Tick or untick a layer in the header's Layers list, opening the list first when it is closed."""
    if not page.is_visible('#layerlist'):
        page.click('#layersBtn')
    page.set_checked(f'#layerlist input[data-layer="{name}"]', on)


def config_layers(run, folder):
    return next(row for row in json.loads(run('config', '--show', '--json', cwd=folder).stdout)
                if row['key'] == 'layers')['value']


def drawn_as_paths(graph, expected):
    """The page's graph against the store's: one vertex per element, each join one path from its receiver to its own
    purpose vertex and on to its provider with nothing back to the receiver, MAP-002, its subtypes hung from its
    purpose vertex, and each element's namespace edge from its nearest parent element, VIEW-005."""
    elements = {entry['element']['element_id'] for entry in expected['elements']}
    by_address = {entry['element']['address']: entry['element']['element_id'] for entry in expected['elements']}
    links = graph['links']
    assert sorted(node['id'] for node in graph['nodes'] if node['t'] == 'el') == sorted(elements)
    by_join = {}
    for link in links:
        if link.get('join'):
            by_join.setdefault(link['join'], []).append((link['source'], link['target'], link['k']))
    for join in expected['joins']:
        purpose = 'p:' + join['join_id']
        assert sorted(by_join.pop(join['join_id'])) == sorted(
            [(join['receiver'], purpose, 'purpose'), (purpose, join['provider'], 'encounter')]
            + [(purpose, 's:' + subtype['join_id'], 'layer') for subtype in join['subtypes']])
    assert by_join == {}
    assert sorted((link['source'], link['target']) for link in links if link['k'] == 'tree') == sorted(
        (by_address[entry['parent']], entry['element']['element_id']) for entry in expected['elements'] if entry['parent'])
    assert not [link for link in links if link['k'] != 'tree' and {link['source'], link['target']} <= elements]
    assert len([node for node in graph['nodes'] if node['t'] == 'purpose']) == len(expected['joins'])
    assert len([node for node in graph['nodes'] if node['t'] == 'sub']) == sum(len(j['subtypes']) for j in expected['joins'])


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-003')
@pytest.mark.req('VIEW-012')
def test_the_page_draws_each_join_as_its_path_and_both_views_select_together(run, web, mapped, browser):
    started(run)
    page, problems, remote = opened(browser, web)
    graph = page.evaluate('window.metaform.graph()')
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    elements = {entry['element']['element_id'] for entry in expected['elements']}
    drawn_as_paths(graph, expected)
    page.wait_for_function('([count]) => window.metaform.labels3d().filter(label => !label.hidden).length === count',
                           arg=[len(elements)])
    names = {entry['element'].get('short_name') or entry['element']['address'] for entry in expected['elements']}
    assert {label['text'] for label in page.evaluate('window.metaform.labels3d()')} == names
    assert page.locator('#map2d svg g.node').count() == len(elements)
    assert page.locator('#map2d svg .edgePaths path').count() == len(expected['joins'])
    assert page.evaluate('[...document.querySelectorAll("#map2d svg .edgeLabel")].map(e => e.textContent.trim())'
                         '.filter(Boolean)') == []
    alarm = next(entry['element'] for entry in expected['elements'] if entry['element']['address'] == 'code.alarm.audible')
    page.evaluate(f'window.metaform.select("{alarm["element_id"]}")')
    assert page.evaluate('[...document.querySelectorAll("#map2d svg g.node.sel title")].map(t => t.textContent)') == [
        'code.alarm.audible']
    page.evaluate('[...document.querySelectorAll("#map2d svg g.node")].find(g => g.querySelector("title").textContent '
                  '=== "exterior.cook").dispatchEvent(new MouseEvent("click", {bubbles: true}))')
    cook = next(entry['element'] for entry in expected['elements'] if entry['element']['address'] == 'exterior.cook')
    assert page.evaluate('window.metaform.selected()') == cook['element_id']
    assert page.text_content('#p-object h2') == 'cook'
    page.keyboard.press('f')
    page.wait_for_timeout(300)
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-008')
def test_the_layers_list_opens_from_the_header_and_back_and_forward_sit_clear_of_the_2d_map(run, web, mapped, browser):
    """Rich, 2026-09-26: the layers are chosen with checkboxes from a Layers button at the top right of the header;
    Back and Forward sit in the 2D map's top left corner on a strip of their own, never under the map's nodes."""
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
    assert sorted(by_name) == ['extra', 'intake-1', 'notes', 'secret']  # nothing about refinements, LAYER-025
    assert page.is_visible('#layerlist #apply')
    page.keyboard.press('Escape')
    assert not page.is_visible('#layerlist')
    page.evaluate('() => { const svg = document.querySelector("#map2d svg"); svg.setAttribute("viewBox", "-400 -400 1600 1600"); }')
    for name in ('#backBtn', '#forwardBtn', '#fitBtn'):
        hit = page.evaluate(f"""(() => {{ const box = document.querySelector('{name}').getBoundingClientRect();
            const found = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
            return found && found.closest('{name}') !== null; }})()""")
        assert hit, name  # nothing of the map covers it
    strip = page.locator('#map2d .bar2d').bounding_box()
    assert page.locator('#map2d svg').bounding_box()['y'] >= strip['y'] + strip['height'] - 1
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
    """Rich, 2026-10-01: refinements should not be changing things' colors, and need not be in layer select."""
    from metaform.data import Store
    held = Store('proj').joins('code.timer.kitchen').results[0]
    join = held.join_id
    named = (f'receiver={held.receiver_address}', f'provider={held.provider_address}')
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
    assert again.evaluate(f'window.metaform.graph().nodes.find(node => node.id === "p:{join}").layer') == 'intake-1'
    again.click('#layersBtn')
    rows = again.evaluate("[...document.querySelectorAll('#layerlist .layerrow .name')].map(name => name.textContent)")
    assert sorted(rows) == ['extra', 'intake-1', 'notes', 'secret']
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
    store.answer(challenged.item_id, 'A')
    run('set', '--layers', ','.join([*TOGGLED, 'memory']), cwd=mapped)
    started(run)
    page, problems, _ = opened(browser, web)
    kitchen = store.element('code.timer.kitchen').element_id
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("written in C")')
    panel = page.inner_text('#p-object')
    for shown in ('kitchen timer', 'code.timer.kitchen', 'DE', 'intake-1',
                  'provider · audible alarm', 'receiver · cook', 'receiver · display', 'tick loop', 'Advances each countdown.',
                  'MEMORY', 'drifts under load', 'Nothing recovers a hung loop. · A', 'written in C', 'notes'):
        assert shown in panel, shown
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-009')
@pytest.mark.req('VIEW-027')
@pytest.mark.req('MAP-046')
def test_a_node_with_open_missing_work_is_drawn_in_characters_a_broken_one_flashes_red_until_resolved_and_the_panel_lists_the_records(
        run, web, mapped, browser):
    """Rich, 2026-09-28: a part not built is drawn in characters, which is the one mark of it, and the circles are
    removed, VIEW-027; the agent that completes its task makes it solid; a node with an open issue flashes red; exclude
    is drawn by the test below. The fixture's kitchen timer carries an open broken record."""
    from metaform.data import Node, Store
    store = Store('proj')
    missing = store.add_work(Node('element', 'code.alarm.audible'), 'missing', note='in the spec', task='build the piezo driver')
    store.add_work(Node('element', 'exterior.cook'), 'exclude', task='review whether the cook belongs in the artifact scope')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    ids = {address: store.element(address).element_id for address in ('code.alarm.audible', 'code.timer.kitchen', 'exterior.cook')}
    look = lambda address: page.evaluate(f'window.metaform.look("{ids[address]}")')
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").text3d === true', timeout=5000)
    alarm = look('code.alarm.audible')
    # A part not built yet keeps its own color and its full opacity. In 3D it is drawn in characters and has no
    # circles; in 2D a glow around it marks it.
    assert alarm['around3d'] == 0 and alarm['material'] == 'ShaderMaterial'
    assert (alarm['work'], alarm['classes'], alarm['opacity2d'], alarm['animated2d']) == (['missing'], ['work-missing'], 1, False)
    assert alarm['opacity3d'] is None or alarm['opacity3d'] >= 0.95
    assert alarm['color3d'] == page.evaluate('window.metaform.own(' + json.dumps(ids['code.alarm.audible']) + ')')
    assert alarm['bloom2d'] is True and alarm['label3d'] == ['work-missing']
    assert look('exterior.cook')['around3d'] == 0 and look('exterior.cook')['bloom2d'] is False
    assert look('code.timer.kitchen')['label3d'] == ['work-broken']
    cook = look('exterior.cook')
    assert (cook['work'], cook['classes'], cook['red3d']) == (['exclude'], ['work-exclude'], False)
    kitchen = look('code.timer.kitchen')
    assert (kitchen['work'], kitchen['classes'], kitchen['opacity2d'], kitchen['animated2d']) == (['broken'], ['work-broken'], 1, True)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.timer.kitchen"]}").red3d === true', timeout=3000)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.timer.kitchen"]}").red3d === false', timeout=3000)
    legend = page.inner_text('#legend')
    assert 'work: missing' in legend and 'work: broken' in legend and 'work: exclude' in legend
    # The panel lists the selected node's work records.
    page.evaluate(f'window.metaform.select("{ids["code.timer.kitchen"]}")')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("hold the tick to one second")')
    panel = page.inner_text('#p-object')
    for shown in ('WORK', 'broken', 'drifts', 'hold the tick to one second', 'open'):
        assert shown in panel, shown
    # Its task done, pushed to the page, the alarm turns solid without a reload.
    run('map', 'work', 'op=done', f'id={missing.work_id}', 'resolution=driver written', cwd=mapped)
    # glass, as every built element, once the text has given way to it
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").material === "MeshTransmissionMaterial"',
                           timeout=60000)  # the ending runs on a clock of at most 0.1 s a frame, slower as frames slow
    assert look('code.alarm.audible')['text3d'] is False
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").bloom2d === false', timeout=5000)
    solid = look('code.alarm.audible')
    assert (solid['work'], solid['classes'], solid['opacity2d']) == ([], [], 1)
    page.evaluate(f'window.metaform.select("{ids["code.alarm.audible"]}")')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("driver written")')
    assert 'done' in page.inner_text('#p-object')
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-027')
@pytest.mark.req('MAP-046')
def test_a_join_that_is_not_built_yet_is_marked_in_both_views(run, web, mapped, browser):
    """An open missing record on a join shows on the join itself: its purpose node is drawn in characters in 3D,
    VIEW-027, and its edge has a glow in 2D, with its color and opacity as they are."""
    from metaform.data import Node, Store
    store = Store('proj')
    joins = list(store.joins('code.timer.kitchen').results)
    store.add_work(Node('join', joins[0].join_id), 'missing', task='build it')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    links = page.evaluate('window.metaform.linkColors()')
    assert not any(link['color'].startswith('rgba(') for link in links)  # its links keep their color and opacity
    page.wait_for_function(f'() => window.metaform.look("p:{joins[0].join_id}").text3d === true', timeout=5000)
    assert page.evaluate(f'window.metaform.look("p:{joins[0].join_id}").around3d') == 0
    built = [join['join_id'] for join in keys_of(web)[0]['joins'] if join['join_id'] != joins[0].join_id]
    assert built and page.evaluate(f'window.metaform.look("p:{built[0]}").text3d') is False
    assert page.evaluate(f'window.metaform.edge2d("{joins[0].join_id}")') == ['work-missing']
    glow = page.evaluate("""(() => { const path = document.querySelector('#map2d svg path.work-missing');
        const style = getComputedStyle(path); return [Number(style.opacity), style.filter]; })()""")
    assert glow[0] == 1 and 'drop-shadow' in glow[1]
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-027')
@pytest.mark.req('MAP-046')
def test_the_text_of_a_part_being_worked_on_quickens_that_of_a_part_waiting_is_slow_and_a_part_done_is_normal(run, web, mapped, browser):
    """The text of a part says it needs building; it changes slowly while the part waits and quickens once an agent
    has taken the task, so the map shows where work is happening now; and it gives way to the node when the work is
    done, VIEW-027."""
    from metaform.data import Node, Store
    store = Store('proj')
    waiting = store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='build it')
    working = store.add_work(Node('element', 'exterior.cook'), 'missing', task='build that')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    ids = {address: store.element(address).element_id for address in ('code.alarm.audible', 'exterior.cook')}
    run('map', 'work', 'op=take', f'id={working.work_id}', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{ids["exterior.cook"]}").work[0] === "in-progress"', timeout=15000)  # pushed, read and drawn again
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").text3d === true', timeout=15000)
    page.wait_for_timeout(600)  # the page redraws once for the change it was pushed
    samples = page.evaluate(f"""async () => {{ const seen = {{still: [], moving: []}};
        for (let at = 0; at < 24; at++) {{ await new Promise(done => setTimeout(done, 80));
          seen.still.push(window.metaform.look("{ids['code.alarm.audible']}").turns);
          seen.moving.push(window.metaform.look("{ids['exterior.cook']}").turns); }}
        return seen; }}""")
    assert len(set(samples['still'])) == 1  # a part waiting changes at one slow speed
    assert samples['moving'] == sorted(samples['moving'])  # a part in work never slows
    assert samples['moving'][-1] > samples['moving'][0] > samples['still'][0]  # it quickens, from above the waiting speed
    assert all(page.evaluate(f'window.metaform.look("{ids[address]}").around3d') == 0 for address in ids)
    cook = page.evaluate(f'window.metaform.look("{ids["exterior.cook"]}")')
    assert cook['classes'] == ['work-in-progress'] and cook['animated2d'] is True
    assert 'work: in-progress' in page.inner_text('#legend')
    run('map', 'work', 'op=done', f'id={working.work_id}', 'resolution=built', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{ids["exterior.cook"]}").material === "MeshTransmissionMaterial"',
                           timeout=60000)  # the ending runs on a clock of at most 0.1 s a frame, slower as frames slow
    assert page.evaluate(f'window.metaform.look("{ids["exterior.cook"]}").text3d') is False
    page.wait_for_function(f'() => window.metaform.look("{ids["exterior.cook"]}").classes.length === 0', timeout=5000)
    assert waiting.work_id and problems == []


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
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    _, at, _ = keys_of(web)
    names = {at[address]: address for address in at}
    assert {key: page.evaluate('window.metaform.bloom()')[key] for key in ('pass', 'levels')} == {'pass': True, 'levels': 3}
    assert page.evaluate('window.metaform.reach()') == {'property': None, 'elements': [], 'edges': 0}
    page.evaluate('window.metaform.waveTimes({every: 2.4, cross: 0.5, hold: 0.3, gaussian: false})')
    key = 'r:' + written.property_id
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


@pytest.mark.req('VIEW-005')
@pytest.mark.req('MAP-046')
def test_an_open_exclude_record_stands_out_on_an_element_and_on_a_join_in_both_views(run, web, mapped, browser):
    """An exclusion finding remains visible for review: the object pulses in the exclude color,
    which nothing else on the map uses, whether it is an element or a join."""
    from metaform.data import Node, Store
    store = Store('proj')
    join = next(iter(store.joins('code.timer.kitchen').results))
    store.add_work(Node('element', 'exterior.cook'), 'exclude', task='review whether the cook belongs in the artifact scope')
    store.add_work(Node('join', join.join_id), 'exclude', task='review whether this relationship belongs in the artifact scope')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    cook, purpose = store.element('exterior.cook').element_id, 'p:' + join.join_id
    exclude = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--exclude").trim().toLowerCase()')
    others = page.evaluate("""() => { const style = getComputedStyle(document.documentElement);
        return ['--broken', '--missing', '--signal', '--de', '--intake', '--memory',
                '--danger', '--tree', '--k1', '--k2', '--k3', '--k4', '--k5', '--k6']
            .map(name => style.getPropertyValue(name).trim().toLowerCase()); }""")
    assert exclude and exclude not in others
    for node in (cook, purpose):
        page.wait_for_function(f'() => window.metaform.look("{node}").exclude3d === true', timeout=3000)
        page.wait_for_function(f'() => window.metaform.look("{node}").exclude3d === false', timeout=3000)
    seen = page.evaluate(f'window.metaform.look("{cook}")')
    assert (seen['classes'], seen['animated2d']) == (['work-exclude'], True)
    colors = {link['color'].lower() for link in page.evaluate('window.metaform.linkColors()')
              if link['join'] == join.join_id}
    assert colors == {exclude}
    assert page.evaluate(f'window.metaform.edge2d("{join.join_id}")') == ['work-exclude']
    assert problems == []


@pytest.mark.req('VIEW-006')
@pytest.mark.req('MAP-020')
@pytest.mark.req('VIEW-012')
def test_each_encounter_keeps_its_layers_color_and_nothing_names_a_perspective(run, web, mapped, browser):
    """Rich, 2026-10-02: "drop perspective drop the duality , EF infers fine". An encounter link and a subtype's link
    take their layer's color in both views; the legend and the panel name no Function or Encounter word."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    color = {name: page.evaluate(f'getComputedStyle(document.documentElement).getPropertyValue("--{name}").trim()')
             for name in ('intake', 'k1')}
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    drawn = page.evaluate('window.metaform.linkColors()')
    for join in expected['joins']:
        assert 'perspective' not in join
        encounter = next(link for link in drawn if link['join'] == join['join_id'] and link['k'] == 'encounter')
        assert encounter['color'] == color['k1' if join['layer'] == 'notes' else 'intake'], join
        for subtype in join['subtypes']:
            assert 'perspective' not in subtype
            link = next(link for link in drawn if link['target'] == 's:' + subtype['join_id'])
            assert link['color'] == color['intake']
    assert page.locator('#map2d svg .edgePaths path[class*="perspective-"]').count() == 0
    legend = page.inner_text('#legend')
    assert 'Function ·' not in legend and 'Encounter ·' not in legend
    kitchen = next(entry['element']['element_id'] for entry in expected['elements']
                   if entry['element']['address'] == 'code.timer.kitchen')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    assert page.locator('#p-object .join .perspective').count() == 0
    assert problems == []


def keys_of(web):
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    by_address = {entry['element']['address']: entry['element']['element_id'] for entry in expected['elements']}
    subtypes = {subtype['address']: 's:' + subtype['join_id'] for join in expected['joins'] for subtype in join['subtypes']}
    return expected, by_address, subtypes


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_arrow_keys_go_deeper_back_to_the_parent_and_across_the_parents_nodes(run, web, mapped, browser):
    """Rich, 2026-09-26: left and right move between the nodes connected to the parent, down goes deeper, up goes
    back to the parent."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, inside = keys_of(web)
    cook, kitchen, alarm, display = (at[address] for address in (
        'exterior.cook', 'code.timer.kitchen', 'code.alarm.audible', 'code.timer.kitchen.display'))
    tick = inside['code.loop.tick']
    page.evaluate(f'window.metaform.select("{cook}")')
    walk = []
    for key in ('ArrowDown', 'ArrowDown', 'ArrowRight', 'ArrowRight', 'ArrowUp', 'ArrowUp', 'ArrowRight', 'ArrowLeft'):
        page.keyboard.press(key)
        walk.append(page.evaluate('window.metaform.selected()'))
    # cook receives from the kitchen timer, which receives from the alarm and holds the tick loop inside it; the
    # display, which nothing receives from, sits beside the cook at the root.
    assert walk == [kitchen, alarm, tick, alarm, kitchen, cook, display, cook]
    assert problems == []


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_every_element_and_subtype_can_be_reached_with_the_arrow_keys(run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, inside = keys_of(web)
    everything = set(at.values()) | set(inside.values())
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
def test_clicking_a_subtype_or_a_join_in_3d_shows_that_object_and_the_2d_map_holds_subtypes_inside_their_element(
        run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at, inside = keys_of(web)
    tick = inside['code.loop.tick']
    page.evaluate(f'window.metaform.click3d("{tick}")')
    assert page.evaluate('window.metaform.selected()') == tick
    assert page.text_content('#p-object .eyebrow') == 'Subtype'
    assert page.text_content('#p-object h2') == 'tick loop'
    assert 'Advances each countdown.' in page.inner_text('#p-object')
    assert 'Joins held by this element' not in page.inner_text('#p-object')
    outer = next(join for join in expected['joins'] if join['subtypes'])
    page.evaluate(f'window.metaform.click3d("p:{outer["join_id"]}")')
    assert page.evaluate('window.metaform.selected()') == 'p:' + outer['join_id']
    assert page.text_content('#p-object .eyebrow') == 'Join'
    assert outer['purpose'] in page.inner_text('#p-object')
    held = page.evaluate("""() => {
        const box = title => [...document.querySelectorAll('#map2d svg title')].find(t => t.textContent === title)
            ?.parentNode.getBoundingClientRect();
        const outer = box('code.timer.kitchen'), inner = box('code.loop.tick');
        return outer && inner && inner.left >= outer.left && inner.right <= outer.right
            && inner.top >= outer.top && inner.bottom <= outer.bottom;
    }""")
    assert held
    page.evaluate(f'window.metaform.select("{at["code.timer.kitchen"]}")')
    assert 'visible from above' not in page.inner_text('#p-object')
    assert problems == []


@pytest.mark.req('VIEW-009')
@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-016')
@pytest.mark.req('MAP-012')
@pytest.mark.req('MAP-020')
def test_an_element_and_a_subtype_are_named_by_their_short_name_and_a_join_by_its_own_name(run, web, mapped, browser):
    """Rich, 2026-09-27: the namespace address is the name index, so an element's name is its address read through
    name_length; the project's own name for a functionality is on the join, and shows wherever the join does."""
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at, inside = keys_of(web)
    outer = next(join for join in expected['joins'] if join['subtypes'])
    assert outer['name'] == 'dish timer'
    page.evaluate(f'window.metaform.click3d("p:{outer["join_id"]}")')
    assert page.text_content('#p-object h2') == 'dish timer'
    page.evaluate(f'window.metaform.click3d("{inside["code.loop.tick"]}")')
    assert page.text_content('#p-object h2') == 'tick loop'
    assert 'one-second tick' in page.inner_text('#p-object')
    page.evaluate(f'window.metaform.select("{at["code.timer.kitchen"]}")')
    assert page.text_content('#p-object h2') == 'kitchen timer'
    assert 'dish timer' in page.inner_text('#p-object')
    cook = at['exterior.cook']
    page.evaluate(f'window.metaform.select("{cook}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    page.wait_for_function('() => document.querySelector("#map2d").textContent.includes("dish timer")')
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
        const title = [...document.querySelectorAll('#map2d svg title')].find(t => t.textContent === '{address}');
        const box = title?.parentNode.getBoundingClientRect();
        return box && {{x: box.left, y: box.top, w: box.width, h: box.height}};
    }}""")


@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-012')
def test_enter_or_a_click_on_the_selected_node_goes_inside_it_and_escape_backs_out(run, web, mapped, browser):
    """Rich, 2026-09-26: one click selects a node, a click on the selected node goes inside it, and so does Enter;
    Escape or Shift+Enter backs out."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, inside = keys_of(web)
    kitchen, cook, tick = at['code.timer.kitchen'], at['exterior.cook'], inside['code.loop.tick']
    selected = lambda: page.evaluate('window.metaform.selected()')
    now_inside = lambda: page.evaluate('window.metaform.inside()')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}")')
    assert selected() == kitchen
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert selected() == kitchen and 'focused' in page.get_attribute('#map2d', 'class')
    page.keyboard.press('Escape')
    assert selected() == kitchen and 'focused' not in page.get_attribute('#map2d', 'class')
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
    page.keyboard.press('Enter')  # the cook holds no subtypes and still has an inside, VIEW-016
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    assert selected() == cook and now_inside()
    assert problems == []


def remember(run, folder, command, value, node=None):
    """An agent's memory, written with the memory module's commands, LAYER-013: `value` is the command's one JSON
    argument, and `node` the map node it is written at."""
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
        page.evaluate('window.metaform.fit()')  # the view opens at a readable size, so a node may be outside it
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
    """Rich, 2026-09-27: the zoom in and fade effect when going inside was nice and was lost when going inside became a
    swap to the node's own graph. The base map zooms into the node as it fades out, the node's graph fades in, and
    going back out runs the other way; with reduced motion the views change at once."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, _ = keys_of(web)
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
    page.keyboard.press('Escape')
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
    """Rich, 2026-09-26: any node can be entered, whether or not it holds subtypes; going inside a node replaces the map
    with another graph, and the other layers show only what is attached to the node being viewed, as busy as the
    layers turned on; the base map stays the project's current shape."""
    remember(run, mapped, 'create_entities', [entity('countdown drift', 'The countdown drifts under load.')],
             'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'Too quiet in a loud kitchen.')],
             'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'quiet tone', 'relationType': 'drives'}])
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, subtypes = keys_of(web)
    kitchen, cook, alarm = at['code.timer.kitchen'], at['exterior.cook'], at['code.alarm.audible']
    assert 'The countdown drifts' not in page.inner_text('#p-object')  # the folder's layers leave memory off
    set_layer(page, 'memory', True)  # turned on in this view only
    page.keyboard.press('Escape')  # the first Escape closes the Layers list, and only that
    assert not page.is_visible('#layerlist')
    page.wait_for_function('() => window.metaform.loaded() && '
                           'document.querySelector("#p-object").textContent.includes("The countdown drifts")')
    base = page.evaluate('() => { const svg = document.querySelector("#map2d svg"); svg.dataset.base = "yes"; '
                         'return document.querySelectorAll("#map2d svg g.node").length; }')

    page.evaluate(f'window.metaform.select("{cook}")')
    page.keyboard.press('Enter')  # the cook holds no subtypes and can still be entered
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    keys, crumbs = inside(page)
    assert crumbs.split('›')[-1].strip() == 'cook' and not page.query_selector('#map2d svg[data-base]')
    assert any(key.startswith('p:') for key in keys)  # the join it holds, as its purpose
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert page.query_selector('#map2d svg[data-base="yes"]') is not None  # the same map, never laid out again
    assert page.evaluate('document.querySelectorAll("#map2d svg g.node").length') == base
    assert page.evaluate('window.metaform.selected()') == cook and not page.is_visible('#crumbs')

    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{kitchen}") && '
                           'window.metaform.inside().some(key => key.startsWith("e:"))')
    keys, crumbs = inside(page)
    assert [part.strip() for part in crumbs.split('›')] == ['map', 'kitchen timer']
    # its subtype, its memory, the memory that memory relates to, and the node that one is kept at
    assert {subtypes['code.loop.tick'], 'e:countdown drift', 'e:quiet tone', alarm} <= set(keys)
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
    assert [part.strip() for part in inside(page)[1].split('›')] == ['map', 'kitchen timer', 'audible alarm']
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length && '
                           '!document.querySelector("#crumbs").textContent.includes("audible alarm")')
    assert page.evaluate('window.metaform.selected()') == alarm  # the node left, selected where it shows
    click_node(page, 'audible alarm')  # the alarm is selected: a click on it goes inside
    page.wait_for_function('() => window.metaform.inside().length && '
                           'document.querySelector("#crumbs").textContent.includes("audible alarm")')
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length && '
                           '!document.querySelector("#crumbs").textContent.includes("audible alarm")')
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    assert page.evaluate('window.metaform.selected()') == kitchen and not page.is_visible('#crumbs')
    assert problems == []


@pytest.mark.req('VIEW-016')
@pytest.mark.req('VIEW-008')
def test_inside_a_node_the_graph_keeps_the_maps_orientation_and_fit_still_zooms(run, web, mapped, browser):
    """Rich, 2026-09-26, after going inside a node: the map seemed to turn on its side, and Fit did not zoom there.
    The inside graph runs the way the whole map does, and Fit's zoomed-in view works inside."""
    from metaform.data import Store
    store = Store('proj')
    for name in ('dial', 'buzzer', 'battery'):  # enough elements that the map runs top to bottom, as a real one does
        store.add_element('notes', f'code.timer.kitchen.{name}', name_length=1)
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, subtypes = keys_of(web)
    kitchen, tick = at['code.timer.kitchen'], subtypes['code.loop.tick']
    across = page.evaluate('window.metaform.vertical()')
    assert across is True
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}")')
    assert page.evaluate('window.metaform.vertical()') == across
    center, held = (page.evaluate(f"""(() => {{ const title = [...document.querySelectorAll('#map2d svg title')]
        .find(t => t.textContent === '{name}'); const box = title.parentNode.getBoundingClientRect();
        return [box.left + box.width / 2, box.top + box.height / 2]; }})()""") for name in ('kitchen timer', 'tick loop'))
    if across:  # top to bottom: what the node holds sits below it
        assert held[1] > center[1]
    else:
        assert held[0] > center[0]
    width = lambda: float(page.get_attribute('#map2d svg', 'viewBox').split()[2])
    whole = width()
    page.keyboard.press('f')
    page.keyboard.press('f')
    still2d(page)  # the camera eases for 700 ms
    assert width() < whole * 0.8  # zoomed in on the selected node
    assert problems == []


@pytest.mark.req('VIEW-003')
def test_the_page_files_are_checked_with_the_server_on_every_load(run, web):
    """A page file the browser keeps would show a person the page as it was before an update, with nothing to say
    so. Each page file tells the browser to ask again before using its copy."""
    started(run)
    for path in ('/', '/page/app.js', '/page/app.css'):
        status, _, headers = request(web, path)
        assert status == 200 and headers['Cache-Control'] == 'no-cache', path


@pytest.mark.req('VIEW-025')
@pytest.mark.req('VIEW-003')
def test_in_every_theme_the_elements_are_glass_and_the_page_loads_nothing_from_outside(run, web, mapped, browser):
    """A node is made of a material that lets light through, in each theme alike, with no mode to choose. The glass
    comes from the copy of three.js the page carries, so it works with no network."""
    started(run)
    page, problems, _ = opened(browser, web)
    fetched = []
    page.on('request', lambda request: fetched.append(request.url))
    page.reload()
    page.wait_for_function('() => window.metaform.loaded()')
    _, at, subtypes = keys_of(web)
    themes = page.evaluate('[...document.querySelectorAll("#theme option")].map(option => option.value)')
    assert len(themes) > 1
    checked = (at['code.timer.kitchen'], at['code.alarm.audible'], subtypes['code.loop.tick'])
    made = f'() => {json.dumps(checked)}.every(node => window.metaform.look(node).material)'
    page.wait_for_function(made, timeout=10000)
    for theme in themes:
        page.select_option('#theme', theme)
        page.wait_for_timeout(250)
        page.wait_for_function(made, timeout=10000)  # a node's object can be missing a moment after the theme changes
        for node in checked:
            seen = page.evaluate(f'window.metaform.look("{node}")')
            # drei's glass, Rich 2026-09-29: it lets light through, parts its colors, bends it and draws its far wall
            assert seen['material'] == 'MeshTransmissionMaterial' and seen['transmission'] > 0, (theme, node, seen)
            assert seen['chromatic'] > 0 and seen['distortion'] > 0 and seen['backside'] is True, (theme, node, seen)
    # one shape for every node of a size, however many nodes there are
    sizes = page.evaluate('new Set(window.metaform.graph().nodes.filter(node => node.t === "el" || node.t === "sub")'
                          '.map(node => window.metaform.look(node.id).shape)).size')
    assert sizes <= 4
    assert any(url.endswith('/vendor/three.module.min.js') for url in fetched)
    assert any(url.endswith('/vendor/drei-vanilla/MeshTransmissionMaterial.js') for url in fetched)
    assert all(url.startswith((f'http://127.0.0.1:{web}/', 'data:', 'blob:')) for url in fetched), fetched
    assert problems == []


@pytest.mark.req('VIEW-025')
def test_what_is_behind_a_node_reaches_its_glass_through_the_pictures_the_page_draws(run, web, mapped, browser):
    """What is behind the glass reaches it through the pictures the page draws each frame, as drei's component does.
    It is read with the frosting and the absorption off, since with them what is behind is blurred into the node's
    own color: a join's purpose node set behind the cook shows through the cook, and moving it away changes the cook."""
    from metaform.data import Store
    store = Store('proj')
    for record in store.work(None, None, True, limit=0).results:  # nothing lit, nothing drawn in characters
        store.finish_work(record.work_id, 'done')
    cook = store.element('exterior.cook').element_id
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')           # the distortion is still
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate('window.metaform.glass(true, {roughness: 0, attenuationDistance: 1e9, transmission: 1})')
    behind = next(node['id'] for node in page.evaluate('window.metaform.graph().nodes') if node['id'].startswith('p:'))
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
    one document, written by one piece of the chassis."""
    started(run)
    written = run('map', 'markdown', cwd=mapped).stdout
    assert '## kitchen timer' in written
    status, body, headers = request(web, '/api/markdown?project=proj')
    assert status == 200 and body == written
    assert headers['Content-Type'].startswith('text/markdown')
    around = request(web, '/api/markdown?project=proj&address=code.timer.kitchen')[1]
    assert around == run('map', 'markdown', 'address=code.timer.kitchen', cwd=mapped).stdout
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    with page.expect_download() as saved:
        page.click('#exportBtn')
    assert saved.value.suggested_filename == 'proj-map.md'
    assert Path(saved.value.path()).read_text(encoding='utf-8') == written
    assert problems == []


@pytest.mark.req('VIEW-008')
def test_the_2d_map_opens_at_a_size_that_can_be_read_and_only_fit_changes_the_zoom(run, web, mapped, browser):
    """Zoom is the person's choice: the map opens with its labels readable, selecting a node moves the view to it at
    the same zoom, and the zoom changes only when Fit is asked."""
    from metaform.data import Store
    store = Store('proj')
    for index in range(30):  # a map far wider than the view
        store.add_element('notes', f'code.part.number{index}', name_length=2)
        store.add_join('notes', 'code.timer.kitchen', f'code.part.number{index}', purpose='Keep the timer working.',
                       ef='serves the timer')
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, _ = keys_of(web)
    page.wait_for_function('() => window.metaform.loaded() && document.querySelector("#map2d svg")')
    width = lambda: float(page.get_attribute('#map2d svg', 'viewBox').split()[2])
    view = page.evaluate('document.querySelector("#viewport").getBoundingClientRect().width')
    assert view / width() >= 0.99  # labels are drawn at the size they are written in, or larger
    before = width()
    for address in ('code.part.number3', 'code.part.number27', 'code.timer.kitchen'):
        page.evaluate(f'window.metaform.select("{at[address]}")')
        still2d(page)  # the camera eases for 700 ms
        assert width() == pytest.approx(before, rel=0.01)
        shown = page.evaluate(f"""(() => {{ const view = document.querySelector('#viewport').getBoundingClientRect();
            const box = window.metaform.box2d("{at[address]}");
            return box.left >= view.left && box.right <= view.right && box.top >= view.top && box.bottom <= view.bottom; }})()""")
        assert shown, address
    page.evaluate('window.metaform.fit()')
    still2d(page)
    assert width() > before * 1.5  # Fit shows the whole map
    whole = width()
    page.evaluate(f'window.metaform.select("{at["code.part.number3"]}")')
    still2d(page)
    assert width() == pytest.approx(whole, rel=0.01)  # and a click leaves it there
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
# How much of the 2D map's area the drawn diagram spans, across or down, whichever is more.
SPAN = '''() => { const view = document.querySelector("#viewport").getBoundingClientRect();
    const scene = document.querySelector("#map2d svg > g").getBoundingClientRect();
    return Math.max(scene.width / view.width, scene.height / view.height); }'''
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


def readable_at(page, px, key):
    """Mode two holding its minimum: the smallest text `px` tall on the screen, within a pixel, and the node centered."""
    return page.evaluate(TEXT_PX) == pytest.approx(px, abs=1) and centered(page, key) <= 2


def to_large_area(page):
    """The 2D map put in the large area, VIEW-028, drawn there and still."""
    page.click('#swapBtn')
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
    run('map', 'knowledge', 'op=add-join', 'layer=notes', 'receiver=code.timer.kitchen', f'provider={address}',
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
        return [...document.querySelectorAll('#map2d svg g.node')].map(node => [node.querySelector('title').textContent,
            node.getBoundingClientRect()]).filter(([title, box]) => (box.left + box.right) / 2 > view.left + 10
            && (box.left + box.right) / 2 < view.right - 10 && (box.top + box.bottom) / 2 > view.top + 10
            && (box.top + box.bottom) / 2 < view.bottom - 10).map(([title]) => title); })()""")
    keys = [at[name] for name in title if name in at and at[name] != besides]
    assert keys, title
    return keys[0]


def wheel(page, delta):
    """The wheel turned over the middle of the 2D map's area, and the camera still."""
    still2d(page)
    before = view_box(page)[2]
    page.mouse.move(*page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                                   ' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; })()'))
    page.mouse.wheel(0, delta)
    page.wait_for_function(f'() => Number(document.querySelector("#map2d svg").getAttribute("viewBox")'
                           f'.split(" ")[2]) !== {before}')  # the browser has delivered the wheel and its ease began
    still2d(page)


def acted(page, act, must=True, until='true'):
    """Do `act` on the held clock, and return the viewBox the 2D camera eased to."""
    return eased(stepped(page, act, until), must)


def arrival(page):
    """What holds in the page once it has read and drawn the next change to the map."""
    return f'window.metaform.changes() > {page.evaluate("window.metaform.changes()")} && window.metaform.loaded()'


def press(page, selector):
    """A click on a button at its place on the screen, which waits for nothing, so it can be done on the held clock."""
    box = page.evaluate(f'(() => {{ const box = document.querySelector("{selector}").getBoundingClientRect();'
                        f' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; }})()')
    page.mouse.click(*box)


@pytest.mark.req('VIEW-041')
def test_in_the_large_area_mode_one_keeps_the_whole_diagram_fitted_and_eases_to_each_new_fit(
        run, web, mapped, browser):
    """Rich, 2026-10-03: with the 2D map in the large area, mode one, the default, keeps the whole diagram fitted and
    eases to each new fit as nodes arrive or go and as the area changes size, so an intake can be watched filling in
    without the camera jumping; Fit, F and Home go back to it."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run)
    assert fitted(page) and page.evaluate(TEXT_PX) < 8   # nothing pressed: the whole diagram, however small its text
    acted(page, lambda: arrives(run, mapped), until=arrival(page))  # a node arrives: it eases out to hold it too
    assert page.evaluate('[...document.querySelectorAll("#map2d svg title")].some(t => t.textContent === "code.part.added")')
    assert fitted(page)
    expected, at, _ = keys_of(web)
    joined = next(join['join_id'] for join in expected['joins'] if join['provider'] == at['code.part.added'])
    gone = '![...document.querySelectorAll("#map2d svg title")].some(t => t.textContent === "code.part.added")'
    acted(page, lambda: [run('map', 'knowledge', 'op=remove', 'layer=notes', f'id={thing}', cwd=mapped)
                         for thing in (joined, at['code.part.added'])],
          until=f'{arrival(page)} && {gone}')             # it goes: the row is narrower again
    assert fitted(page)
    acted(page, lambda: page.set_viewport_size({'width': 1100, 'height': 760}))  # the area changes size
    assert fitted(page)
    kitchen = at['code.timer.kitchen']                    # selected as the map opened, as its DE
    assert page.evaluate('window.metaform.selected()') == kitchen
    for back in (lambda: press(page, '#fitBtn'), lambda: page.keyboard.press('f'), lambda: page.keyboard.press('Home')):
        acted(page, lambda: page.keyboard.press('5'))     # a digit from mode one goes to mode two
        assert readable_at(page, 16, kitchen)
        acted(page, back)                                 # and Fit, F and Home back to mode one
        assert fitted(page)
    page.keyboard.press('f')                              # in the large area F does not go on to other views
    page.wait_for_timeout(300)
    still2d(page)
    assert fitted(page)
    assert problems == []


@pytest.mark.req('VIEW-041')
def test_in_the_large_area_a_click_goes_to_mode_two_which_holds_the_minimum_text_centered_on_the_selected_node(
        run, web, mapped, browser):
    """Rich, 2026-10-03: mode two fits the whole diagram but never draws its text below a minimum, keys 1 to 9 at 8 to
    24 px, 5 the default; when the minimum wins it keeps the selected node at the center, following each selection; a
    click on a node goes to mode two, and after the wheel a click goes back to it."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run)
    _, at, _ = keys_of(web)
    whole_px = page.evaluate(TEXT_PX)
    part = lambda number: at[f'code.part.number{number}']
    page.evaluate(f'window.metaform.click3d("{part(5)}")')  # a click in the 3D map
    still2d(page)
    assert readable_at(page, 16, part(5))
    acted(page, lambda: page.keyboard.press('Home'))
    assert fitted(page)
    acted(page, lambda: click_center(page, part(3)))      # a click in the 2D map
    assert page.evaluate('window.metaform.selected()') == part(3) and readable_at(page, 16, part(3))
    wheel(page, 400)                                      # the wheel leaves mode two; a click goes back to it
    other = shown(page, at, part(3))
    acted(page, lambda: click_center(page, other))
    assert page.evaluate('window.metaform.selected()') == other and readable_at(page, 16, other)
    wheel(page, 400)                                      # and Fit to mode one
    acted(page, lambda: press(page, '#fitBtn'))
    assert fitted(page)
    acted(page, lambda: click_center(page, part(3)))
    acted(page, lambda: page.keyboard.press('9'))
    assert readable_at(page, 24, part(3))
    acted(page, lambda: page.keyboard.press('ArrowRight'))  # the camera follows each new selection
    following = page.evaluate('window.metaform.selected()')
    assert following != part(3) and readable_at(page, 24, following)
    tick = keys_of(web)[2]['code.loop.tick']              # a node inside an element's box is centered too
    acted(page, lambda: page.evaluate(f'window.metaform.select("{tick}")'), must=following != tick)
    assert readable_at(page, 24, tick)
    acted(page, lambda: page.keyboard.press('1'))         # 8 px, as the whole diagram draws its text smaller still
    assert whole_px < 7 and readable_at(page, 8, tick)
    acted(page, lambda: page.keyboard.press('5'))
    acted(page, lambda: arrives(run, mapped), must=False, until=arrival(page))  # a node arrives in mode two
    assert readable_at(page, 16, tick)
    assert problems == []


@pytest.mark.req('VIEW-041')
def test_in_the_large_area_the_wheel_leaves_both_modes_and_a_digit_typed_in_a_field_moves_nothing(
        run, web, mapped, browser):
    """The wheel leaves both modes and its zoom holds through the map drawn again, VIEW-008; a digit after it goes to
    mode two; the digit keys are taken only when no text field has the focus."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run)
    _, at, _ = keys_of(web)
    kitchen = at['code.timer.kitchen']
    wheel(page, -400)
    zoom = view_box(page)[2]
    changed_by(page, lambda: run('map', 'ask', 'element:code.timer.kitchen', 'Is one second right?', cwd=mapped))
    page.wait_for_timeout(300)
    still2d(page)
    assert view_box(page)[2] == pytest.approx(zoom, rel=0.01)
    acted(page, lambda: page.keyboard.press('5'))         # a digit after the wheel goes to mode two
    assert readable_at(page, 16, kitchen)
    wheel(page, 400)                                      # and the wheel leaves mode two: its zoom holds too
    zoom = view_box(page)[2]
    changed_by(page, lambda: run('map', 'ask', 'element:code.alarm.audible', 'Is the tone right?', cwd=mapped))
    page.wait_for_timeout(300)
    still2d(page)
    assert view_box(page)[2] == pytest.approx(zoom, rel=0.01)
    page.click('#messages')                               # the answer box: a digit typed there is a letter of the answer
    page.wait_for_selector('#float textarea.answer')
    still2d(page)
    held = view_box(page)
    page.focus('#float textarea.answer')
    page.keyboard.type('9')
    page.evaluate(f'window.metaform.element("{kitchen}")')  # and in the address field of Add Element
    page.wait_for_selector('#element .address')
    page.focus('#element .address')
    page.keyboard.type('7')
    page.wait_for_timeout(300)
    still2d(page)
    assert view_box(page) == held
    assert page.input_value('#float textarea.answer') == '9' and page.input_value('#element .address').endswith('7')
    assert problems == []


@pytest.mark.req('VIEW-041')
def test_in_the_large_area_a_click_on_a_map_of_three_nodes_shows_the_whole_diagram(run, web, home, tmp_path, browser):
    """Mode two holds the minimum only when the whole diagram fits below it; a map of a few nodes shows whole, as
    large as the area allows, its text drawn larger than the minimum."""
    from metaform.data import Store
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    store = Store('proj')
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance=PROVENANCE, ready=True)
        store.add_element(intake.name, 'exterior.cook', name_length=1, role='CQU')
        store.add_element(intake.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(intake.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_join(intake.name, 'exterior.cook', 'code.timer.kitchen', purpose='Know when food is done.',
                       ef='Counts down and rings.')
        store.add_join(intake.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.')
    store.layer('notes', 'test', 'What notes says.', mutable=True, hideable=True, provenance=PROVENANCE)
    store.finish('notes')
    run('set', '--layers', 'intake-1,notes', cwd=folder)
    page, problems = opened_on(browser, web, run)
    page.set_viewport_size({'width': 2200, 'height': 1400})  # an area where the whole diagram draws its text above 24 px
    page.wait_for_timeout(300)
    still2d(page)
    _, at, _ = keys_of(web)
    whole = view_box(page)
    assert fitted(page) and page.evaluate(TEXT_PX) > 25
    assert stepped(page, lambda: click_center(page, at['exterior.cook']))[-1] == pytest.approx(whole, abs=1)
    assert page.evaluate('window.metaform.selected()') == at['exterior.cook']
    for key in ('9', '1'):                                # mode two has no upper limit, at either end of the keys
        assert stepped(page, lambda key=key: page.keyboard.press(key))[-1] == pytest.approx(whole, abs=1)
    # a node arriving and going in mode two: the fit changes and the camera eases to it
    acted(page, lambda: (Store('proj').add_element('notes', 'code.alarm.loud', name_length=2),
                         run('map', 'knowledge', 'op=add-join', 'layer=notes', 'receiver=code.alarm.audible',
                             'provider=code.alarm.loud', 'purpose=Be heard.', 'ef=rings loudly', cwd=folder)),
          until=arrival(page))
    assert fitted(page) and view_box(page) != pytest.approx(whole, abs=1)
    loud = keys_of(web)[1]['code.alarm.loud']
    acted(page, lambda: run('map', 'knowledge', 'op=remove', 'layer=notes', f'id={loud}', cwd=folder),
          until=arrival(page))
    assert fitted(page) and view_box(page) == pytest.approx(whole, abs=1)
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.req('VIEW-008')
def test_in_the_small_area_the_2d_map_keeps_its_zoom_and_every_camera_move_eases(run, web, mapped, browser):
    """Rich, 2026-10-03: in the small area the 2D map keeps VIEW-008's zoom as it is, and every camera move there eases
    in and out too, never set at once: a selection, a click, Fit, a key, Back, and the map drawn again as a node
    arrives. The modes and their digit keys are the large area's."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run, large=False)
    _, at, _ = keys_of(web)
    wheel(page, 200)                                      # the person's zoom
    zoom = view_box(page)[2]
    part = at['code.part.number27']
    assert acted(page, lambda: page.evaluate(f'window.metaform.select("{part}")'))[2] == pytest.approx(zoom, rel=0.01)
    middle = page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                           ' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; })()')
    page.mouse.move(*middle)                              # the map dragged away from the node
    page.mouse.down()
    page.mouse.move(middle[0] + 150, middle[1] + 60, steps=8)
    page.mouse.up()
    still2d(page)
    assert centered(page, part) > 50
    # a node arrives: the map is drawn again with the zoom kept, and the camera eases back to the node selected
    assert acted(page, lambda: arrives(run, mapped), until=arrival(page))[2] == pytest.approx(zoom, rel=0.01)
    assert centered(page, part) <= 2
    other = shown(page, at, part)
    assert acted(page, lambda: click_center(page, other))[2] == pytest.approx(zoom, rel=0.01)  # a click
    assert page.evaluate('window.metaform.selected()') == other
    held = view_box(page)
    page.keyboard.press('9')                              # the digits set nothing here
    page.wait_for_timeout(300)
    still2d(page)
    assert view_box(page) == held
    for act in (lambda: press(page, '#fitBtn'), lambda: page.keyboard.press('ArrowUp'), lambda: press(page, '#backBtn')):
        acted(page, act)
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.req('VIEW-008')
@pytest.mark.parametrize('large', [False, True], ids=['small-area', 'large-area'])
def test_wheel_zoom_eases_and_a_second_turn_keeps_the_zoom_already_requested(run, web, mapped, browser, large):
    """Every change of camera size and center eases, including wheel zoom, in both areas; wheel turns arriving
    during the ease build on the zoom requested rather than dropping it, and leave the camera at that manual zoom."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run, large=large)
    _, at, _ = keys_of(web)
    middle = page.evaluate('(() => { const box = document.querySelector("#viewport").getBoundingClientRect();'
                           ' return [(box.left + box.right) / 2, (box.top + box.bottom) / 2]; })()')
    page.mouse.move(*middle)
    width = view_box(page)[2]
    cam = acted(page, lambda: page.mouse.wheel(0, -400))
    assert cam[2] == pytest.approx(width * 0.87)
    page.clock.pause_at(page.evaluate('Date.now()') / 1000 + 1)
    try:
        page.mouse.wheel(0, -400)
        for _ in range(10):
            page.clock.run_for(FRAME)
        page.mouse.wheel(0, -400)
        for _ in range(80):
            page.clock.run_for(FRAME)
        assert view_box(page)[2] == pytest.approx(width * 0.87 ** 3)
        page.evaluate(f'window.metaform.select("{at["code.part.number27"]}")')
        page.clock.run_for(160)
        visible = view_box(page)  # the wheel interrupts a selection at the camera's visible position
        page.mouse.wheel(0, -400)
        for _ in range(80):
            page.clock.run_for(FRAME)
        assert view_box(page) == pytest.approx([
            visible[0] + visible[2] * 0.13 / 2, visible[1] + visible[3] * 0.13 / 2,
            visible[2] * 0.87, visible[3] * 0.87], abs=1)
    finally:
        page.clock.resume()
    assert problems == []


@pytest.mark.req('VIEW-041')
@pytest.mark.req('VIEW-008')
def test_a_drag_interrupts_an_eased_2d_camera_move(run, web, mapped, browser):
    """Dragging during a selection's eased move takes the camera away from that move; its remaining frames never
    pull the view back from the place the person dragged it to, VIEW-008's interruptible camera."""
    from metaform.data import Store
    thirty(Store('proj'))
    page, problems = opened_on(browser, web, run, large=False)
    _, at, _ = keys_of(web)
    page.clock.pause_at(page.evaluate('Date.now()') / 1000 + 1)
    try:
        before = view_box(page)
        page.evaluate(f'window.metaform.select("{at["code.part.number27"]}")')
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
def test_inside_a_node_with_many_joins_the_graph_opens_at_a_size_that_can_be_read(run, web, mapped, browser):
    """A node that holds many joins has an inside graph far wider than the view. It opens on the node at a size whose
    labels can be read, and Fit still shows the whole of it."""
    from metaform.data import Store
    store = Store('proj')
    for index in range(14):
        store.add_element('notes', f'code.part.number{index}', name_length=2)
        store.add_join('notes', 'code.timer.kitchen', f'code.part.number{index}',
                       name=f'the long name of part number {index} of the kitchen timer',
                       purpose='Keep the timer working.', ef='serves the timer')
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, _ = keys_of(web)
    kitchen = at['code.timer.kitchen']
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function('() => window.metaform.inside().length > 14')
    still2d(page)
    scale = lambda: page.evaluate("""(() => { const view = document.querySelector('#viewport').getBoundingClientRect();
        return view.width / Number(document.querySelector('#map2d svg').getAttribute('viewBox').split(' ')[2]); })()""")
    opened_at = scale()
    assert opened_at >= 0.99  # a label's 11px text is drawn at 11px or larger
    inside = page.evaluate("""(() => { const view = document.querySelector('#viewport').getBoundingClientRect();
        const title = [...document.querySelectorAll('#map2d svg title')].find(t => t.textContent === 'kitchen timer');
        const box = title.parentNode.getBoundingClientRect();
        return box.left >= view.left && box.right <= view.right && box.top >= view.top && box.bottom <= view.bottom; })()""")
    assert inside  # the node entered is in view
    page.evaluate('window.metaform.fit()')
    still2d(page)
    assert scale() < opened_at  # Fit shows the whole graph
    assert problems == []


@pytest.mark.req('VIEW-017')
@pytest.mark.req('VIEW-005')
def test_in_3d_every_item_of_the_layers_turned_on_is_its_own_node_joined_to_its_node_and_what_it_links(
        run, web, mapped, browser):
    """Rich, 2026-09-26: the 3D map shows everything with no drilling, every memory and item its own node, relations
    as links, seen connected together like a brain, as busy as the layers turned on."""
    from metaform.data import Store
    started(run)
    expected, at, subtypes = keys_of(web)
    kitchen, alarm = at['code.timer.kitchen'], at['code.alarm.audible']
    to_alarm = next(join['join_id'] for join in expected['joins'] if join['receiver'] == kitchen)
    tick = subtypes['code.loop.tick']
    remember(run, mapped, 'create_entities', [entity('countdown drift', 'The countdown drifts under load.')],
             'element:code.timer.kitchen')
    remember(run, mapped, 'create_entities', [entity('alarm pitch', 'Two kilohertz.')], 'element:code.alarm.audible')
    remember(run, mapped, 'create_relations', [{'from': 'countdown drift', 'to': 'alarm pitch', 'relationType': 'drives'}])
    remember(run, mapped, 'create_entities', [entity('quiet tone', 'The tone is too quiet.')], f'join:{to_alarm}')
    remember(run, mapped, 'create_entities', [entity('lost tick', 'One tick can be lost.')], f'join:{tick[2:]}')
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
            ('p:' + to_alarm, memory['quiet tone'], 'item'),
            (tick, memory['lost tick'], 'item')} <= edges  # from the element, the join and the subtype
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
def test_back_and_forward_step_through_the_selected_nodes_and_fit_cycles_three_views(run, web, mapped, browser):
    """Rich, 2026-09-26: back and forward buttons in the 2D map's top left corner; Fit goes through three modes,
    zoomed out, zoomed in and regular."""
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, _ = keys_of(web)
    cook, kitchen, alarm, display = (at[address] for address in (
        'exterior.cook', 'code.timer.kitchen', 'code.alarm.audible', 'code.timer.kitchen.display'))
    selected = lambda: page.evaluate('window.metaform.selected()')
    for key in (cook, kitchen, alarm):
        page.evaluate(f'window.metaform.select("{key}")')
    page.click('#backBtn')
    assert selected() == kitchen
    page.click('#backBtn')
    assert selected() == cook
    page.click('#forwardBtn')
    assert selected() == kitchen
    page.evaluate(f'window.metaform.select("{display}")')
    assert page.is_disabled('#forwardBtn')
    page.click('#backBtn')
    assert selected() == kitchen
    width = lambda: float(page.get_attribute('#map2d svg', 'viewBox').split()[2])
    still2d(page)
    page.click('#fitBtn')
    still2d(page)
    out = width()
    assert 'focused' not in page.get_attribute('#map2d', 'class')
    page.keyboard.press('Home')  # Home always shows the whole map
    still2d(page)
    assert abs(width() - out) < 1
    page.click('#fitBtn')
    still2d(page)
    zoomed = width()
    page.click('#fitBtn')
    still2d(page)
    regular = width()
    assert regular > zoomed and out > zoomed
    page.click('#fitBtn')  # and round again to the whole map
    still2d(page)
    assert abs(width() - out) < 1
    assert selected() == kitchen
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-012')
def test_pointing_at_a_node_shows_its_name_above_the_node_clear_of_the_pointer(run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.wait_for_timeout(2500)
    page.click('#pauseBtn')  # hold the layout still so the node stays where the pointer goes
    stage = page.locator('#stage').bounding_box()
    kitchen = page.evaluate('(() => { const tag = window.metaform.labels3d().find(label => label.text === "kitchen timer");'
                            ' return window.metaform.screen3d(tag.id); })()')
    x, y = kitchen['x'], kitchen['y']
    page.mouse.move(x - 40, y - 40)
    page.mouse.move(x, y, steps=4)
    tip = page.locator('#tip3d')
    tip.wait_for(state='visible')
    assert 'kitchen timer' in tip.inner_text()
    box = tip.bounding_box()
    assert box['y'] + box['height'] < y - 4, (box, y)  # the whole text sits above the node, not under the hand
    page.mouse.move(stage['x'] + 5, stage['y'] + stage['height'] - 5)
    tip.wait_for(state='hidden')
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
        for n in range(600):
            join = big.add_join(layer.name, f'code.g{n % 20}.e{n}', f'code.g{(n + 1) % 20}.e{(n + 1) % 600}',
                                purpose='p', ef='f')
            if n < 10:
                big.add_subtype(layer.name, join.join_id, f'code.loop.s{n}', ef='f', role='SE')
        # e0 receives from e1 above; e1 also receives from e0: two joins, two paths, no loop, MAP-002.
        big.add_join(layer.name, 'code.g1.e1', 'code.g0.e0', purpose='q', ef='g')
    page, problems, _ = opened(browser, web)
    page.goto(f'http://127.0.0.1:{web}/#p=big')
    page.reload()
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn() '
                           '&& window.metaform.drawn().nodes > 1000', timeout=60000)
    assert page.evaluate('window.metaform.drawn()') == {'nodes': 620 + 601 + 10, 'links': 600 + 2 * 601 + 10}
    assert page.inner_text('#count').startswith('620 elements · 601 joins')
    drawn_as_paths(page.evaluate('window.metaform.graph()'), api(web, '/api/graph?project=big&limit=0')[1])
    assert problems == []


@pytest.mark.req('VIEW-005')
@pytest.mark.req('BASE-039')
def test_an_intake_being_recorded_is_drawn_live_as_each_object_arrives(run, home, web, browser, tmp_path):
    """Rich, 2026-09-26: the page reacts to the intake's records as they happen, then shows the finished map."""
    started(run)
    folder = tmp_path / 'live'
    folder.mkdir()
    run('add', 'project', 'live', str(folder))
    run('intake', 'start', cwd=folder)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', cwd=folder)
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
    page.wait_for_timeout(500)  # the first reads settle
    asked.clear()
    page.wait_for_timeout(3000)  # nothing happens: a page that is told asks nothing, QUAL-015
    assert asked == []
    run('intake', 'add_requirement', 'stakeholder.cook.home', 'code.timer.kitchen', 'purpose=p', 'ef=f', 'verb=tells',
        cwd=folder)
    page.wait_for_function('() => window.metaform.drawn().nodes === 3', timeout=1500)  # pushed, not waited for
    page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length === 2', timeout=15000)
    page.wait_for_timeout(300)  # the panel's reads for the selected node settle
    assert not [text for text in page.evaluate('window.toasts') if 'Nothing for' in text]  # an unfinished layer is no error
    run('intake', 'subtype', 'stakeholder.cook.home', 'code.timer.kitchen', 'code.loop.tick', 'ef=f', 'verb=advances',
        'role=SE', cwd=folder)
    page.wait_for_function('() => window.metaform.drawn().nodes === 4', timeout=15000)
    run('intake', 'finish', cwd=folder)
    page.wait_for_function('() => window.metaform.live() === null', timeout=15000)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes === 4', timeout=15000)
    assert 'intake being recorded' not in page.inner_text('#count')
    drawn_as_paths(page.evaluate('window.metaform.graph()'), api(web, '/api/graph?project=live&limit=0')[1])
    assert problems == []  # the console stayed clean through the whole intake: no read that could only find nothing


@pytest.mark.req('VIEW-005')
@pytest.mark.req('BASE-039')
def test_following_a_new_intake_with_nothing_recorded_clears_the_panel_of_the_earlier_metaform(run, home, web,
                                                                                               browser, tmp_path):
    """Rich, 2026-09-27: following a new, empty intake, the map cleared and the panel kept the earlier metaform's
    element."""
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
    run('intake', 'start', cwd=folder)
    page.wait_for_function('() => window.metaform.live() !== null', timeout=15000)
    page.wait_for_function('() => window.metaform.drawn().nodes === 0', timeout=15000)
    page.wait_for_timeout(300)  # the panel's reads settle
    assert 'code.timer.kitchen' not in page.inner_text('#p-object')
    assert problems == []


@pytest.mark.req('VIEW-018')
@pytest.mark.req('QUAL-016')
@pytest.mark.req('BASE-019')
def test_a_module_that_writes_to_the_map_is_seen_live_as_hello_greetings_appear_in_3d(run, web, mapped, browser):
    """Rich, 2026-09-26: a capability added for a feature gets a demonstration in hello; here a greeting,
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
        assert server.changed({'project': 'gone', 'metaform_id': None}) == 0
        assert page.empty()
        assert server.changed({'project': 'proj', 'metaform_id': None}) == 1
        assert page.get_nowait() == {'topic': 'map.changed', 'payload': {'project': 'proj', 'metaform_id': None}}
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
    run('add', 'metaform', 'fresh', cwd=mapped)
    listener.join(5)
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'metaform_id': None}}]


@pytest.mark.req('QUAL-015')
@pytest.mark.req('VIEW-018')
def test_the_page_keeps_no_repeating_timer():
    """No polling, QUAL-015: the page is told what changed, so it holds no timer that repeats; an idle window only
    shows that nothing polled within it."""
    from metaform.modules.web import server
    page = (server.STATIC['page'] / 'app.js').read_text(encoding='utf-8')
    assert 'setInterval' not in page


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
    socket.create_connection(('127.0.0.1', server.port), timeout=5).close()
    serving.join(10)
    assert not serving.is_alive()
    assert 'time.sleep' not in Path(gui.__file__).read_text(encoding='utf-8')
    assert 'time.sleep' not in Path(served.__file__).read_text(encoding='utf-8')


@pytest.mark.req('VIEW-018')
@pytest.mark.req('QUAL-015')
def test_a_new_metaform_an_activation_and_a_memory_reach_the_open_page_without_a_reload(run, web, mapped, browser):
    """Rich, 2026-09-27: clearing the project left the page on data that no longer existed until he refreshed. Any
    command that changes the map is announced by the chassis, so the page follows it."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes > 0')
    whole = page.evaluate('window.metaform.drawn().nodes')
    options = 'document.querySelectorAll("#mf option")'
    run('add', 'metaform', 'fresh', cwd=mapped)
    page.wait_for_function(f'() => [...{options}].some(o => o.selected && o.textContent === "fresh · active")',
                           timeout=3000)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.drawn().nodes === 0', timeout=5000)
    run('activate', 'metaform', 'main', cwd=mapped)
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
    prompts.record_use(third.version_id, 'proj', notes.metaform_id, notes.layer_id)
    started(run)
    assert [item['name'] for item in api(web, '/api/prompts')[1]['prompts']] == ['practices']
    assert api(web, '/api/prompt?name=practices&number=3')[1]['text'] == 'three\n'
    versions = api(web, '/api/prompt-versions?name=practices')[1]['versions']
    assert [item['number'] for item in versions] == [3, 2, 1]
    assert [use['layer_id'] for use in versions[0]['layers']] == [notes.layer_id] and versions[1]['layers'] == []
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
@pytest.mark.req('VIEW-012')
def test_a_layers_prompt_version_opens_in_the_editor_and_an_edit_saves_as_the_next_version(run, web, mapped,
                                                                                            browser):
    from metaform.data import Store, prompts
    prompts.add_prompt('practices', 'xml', '<practices>\n  <one/>\n</practices>\n')
    prompts.add_prompt_version('practices', '<practices>\n  <two/>\n</practices>\n', 1)
    third = prompts.add_prompt_version('practices', '<practices>\n  <three/>\n</practices>\n', 2)
    notes = Store('proj').layer_ref('notes')
    prompts.record_use(third.version_id, 'proj', notes.metaform_id, notes.layer_id)
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
    assert prompts.use_of('proj', notes.metaform_id, notes.layer_id).number == 3
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-013')
def test_text_typed_into_a_prompt_just_opened_is_not_put_back_by_a_slower_read_of_it(run, web, mapped, browser):
    """In a parallel run on 2026-10-03 the prompt editor went back to 'one' after 'one, edited' was set in it: opening a
    layer's prompt read it more than once, and a read that came back after the typing put the stored text back. Every
    read of the prompt's versions after the first is held 1.5 s here, as a loaded machine can, and what was typed stays."""
    from metaform.data import Store, prompts
    prompts.add_prompt('practices', 'markdown', 'one\n')
    notes = Store('proj').layer_ref('notes')
    prompts.record_use(prompts.prompt_version('practices').version_id, 'proj', notes.metaform_id, notes.layer_id)
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


@pytest.mark.req('VIEW-016')
@pytest.mark.req('MAP-030')
@pytest.mark.req('MAP-031')
def test_a_subtype_shows_what_is_attached_to_its_subtype_join_and_to_the_element_it_holds(run, web, mapped, browser):
    """Rich, 2026-09-27: an absorbed element stays one element record inside its parent's join, and is never drawn as
    a node of the outer map; so what is attached to it, and to its subtype join, is read at its subtype."""
    from metaform.data import Node, Store
    started(run)
    _, at, subtypes = keys_of(web)
    tick = subtypes['code.loop.tick']
    held = Store('proj').element('code.loop.tick').element_id
    assert held not in at.values()  # the element a subtype join holds is no node of the outer map
    remember(run, mapped, 'create_entities', [entity('own interrupt', 'The tick is its own interrupt.')], f'join:{tick[2:]}')
    remember(run, mapped, 'create_entities', [entity('one loop', 'One loop serves every timer.')], 'element:code.loop.tick')
    Store('proj').add_work(Node('element', 'code.loop.tick'), 'missing', task='count in milliseconds')
    page, problems, _ = opened(browser, web)
    set_layer(page, 'memory', True)
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.loaded() && '
                           'window.metaform.graph().nodes.filter(node => node.layer === "memory").length === 2')
    graph = page.evaluate('window.metaform.graph()')
    memory = {node['text']: node['id'] for node in graph['nodes'] if node['t'] == 'item' and node['layer'] == 'memory'}
    edges = {(link['source'], link['target'], link['k']) for link in graph['links']}
    assert {(tick, memory['own interrupt'], 'item'), (tick, memory['one loop'], 'item')} <= edges
    page.evaluate(f'window.metaform.select("{tick}")')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("count in milliseconds")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}") && '
                           'window.metaform.inside().filter(key => key.startsWith("e:")).length === 2')
    words = page.evaluate('document.querySelector("#map2d svg").textContent')
    assert 'own interrupt' in words and 'one loop' in words
    assert problems == []


# ---------- clearing the project from the page, VIEW-019 and PROJ-025 ----------

CLEARED = ('Cleared proj: one metaform, main, and one report file. Its registration, folder, settings, origins and '
           'variants stay.')
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
    return [line.split()[0] for line in run('list', 'metaforms', cwd=folder).stdout.splitlines()]


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
    assert caution.startswith('Clearing proj removes one metaform, main, with its store, and one report file.')
    assert api(web, '/api/clear-preview?project=proj') == (200, {'project': 'proj', 'metaforms': ['main'],
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
    run('add', 'metaform', 'fresh', cwd=mapped)
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
    assert answer.pop('backup') and answer.pop('restore') == 'metaform restore project proj'  # PROJ-030
    assert status == 200 and answer == {
        'project': 'proj', 'metaforms': ['main', 'fresh'], 'reports': 1,
        'said': ('Cleared proj: two metaforms, main and fresh, and one report file. Its registration, folder, '
                 'settings, origins and variants stay.')}
    assert run('list', 'metaforms', cwd=mapped).stdout == ''
    assert not list(own('proj').glob('*.metaform.sqlite3'))
    assert not (own('proj') / 'reports').exists()
    assert run(cwd=mapped).stdout.count('Metaform: none yet') == 1
    assert run('list', 'origins', cwd=mapped).stdout == before['origins']
    assert run('list', 'variants', cwd=mapped).stdout == before['variants']
    assert run('config', '--show', '--json', cwd=mapped).stdout == before['settings']
    assert [line.split()[0] for line in run('list', 'projects').stdout.splitlines()] == ['proj']
    assert sorted(path.name for path in mapped.iterdir()) == before['files']
    assert (mapped / 'notes.txt').read_text(encoding='utf-8') == 'first\n'
    assert api(web, '/api/metaforms?project=proj')[1]['results'] == []
    assert first.wait(5)
    time.sleep(0.5)  # a second event, if one were sent, arrives within this
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'metaform_id': None}}]
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
    assert run('list', 'metaforms', cwd=mapped).stdout == ''
    assert not list(own('proj').glob('*.metaform.sqlite3'))
    status, again = clear(web, confirm=True)
    assert again.pop('backup') and again.pop('restore') == 'metaform restore project proj'  # PROJ-030
    assert (status, again) == (200, {
        'project': 'proj', 'metaforms': [], 'reports': 1,
        'said': ('Cleared proj: no metaforms and one report file. Its registration, folder, settings, origins and '
                 'variants stay.')})
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
    for shown in (page, other):  # the finished map is drawn and the panel's reads for it have settled
        shown.wait_for_function('() => document.querySelector("#p-object").innerText.includes("code.timer.kitchen")',
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
    assert status == 200 and answer['metaforms'] == ['main']
    assert first.wait(5)
    time.sleep(0.5)
    assert heard_by(log) == [{'project': 'proj', 'metaform_id': None, 'surface': 'web'}]
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'metaform_id': None}}]
    run('clear', 'project', '--confirm', cwd=mapped)  # the command's clear reaches the same subscriber the same way
    assert heard_by(log) == [{'project': 'proj', 'metaform_id': None, 'surface': 'cli'}]


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
    heard, first = events_on(web)
    status, answer = note_write(web, 'element:code.alarm.audible', 'Set before the watcher is on.')
    assert status == 200, answer
    assert first.wait(5)  # the server has loaded its modules to announce the note
    time.sleep(0.5)
    assert heard_by(log) == []
    run('enable', 'watcher')
    heard_by(log)
    status, answer = clear(web, confirm=True)
    assert status == 200 and answer['metaforms'] == ['main']
    deadline = time.monotonic() + 5  # the server announces after the answer is sent
    while not log.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    time.sleep(0.5)
    assert heard_by(log) == [{'project': 'proj', 'metaform_id': None, 'surface': 'web'}]


def watching_toasts(page):
    """Every message the page shows, however briefly, as `window.toasts`."""
    page.evaluate('''() => { window.toasts = [];
        new MutationObserver(() => window.toasts.push(document.querySelector('#toast').textContent))
            .observe(document.querySelector('#toast'), {childList: true, characterData: true, subtree: true}); }''')


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-019')
@pytest.mark.req('VIEW-018')
def test_a_page_following_an_intake_says_it_stopped_when_the_project_is_cleared_and_finished_when_it_finishes(
        run, home, web, browser, tmp_path):
    started(run)
    folder = tmp_path / 'live'
    folder.mkdir()
    run('add', 'project', 'live', str(folder))
    run('intake', 'start', cwd=folder)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', cwd=folder)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    problems = []
    page.on('console', lambda message: problems.append(message.text) if message.type == 'error' else None)
    page.on('pageerror', lambda error: problems.append(str(error)))
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
    run('intake', 'start', cwd=folder)
    run('intake', 'element', 'stakeholder.cook.home', 'role=CQU', cwd=folder)
    page.wait_for_function('() => window.metaform.live() !== null && window.metaform.drawn().nodes === 1', timeout=15000)
    page.evaluate('window.toasts = []')
    run('intake', 'finish', cwd=folder)
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


def themes():
    """Each theme of the page's styles with its colors: the blocks `:root[data-theme="<name>"]` of app.css."""
    import re
    found = {}
    for selector, body in re.findall(r'([^{}]*:root\[data-theme="[\w-]+"\][^{}]*)\{([^{}]*)\}', page_file('app.css')):
        colors = dict(re.findall(r'(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6}|[\d.]+)\s*;', body))
        for name in re.findall(r':root\[data-theme="([\w-]+)"\]', selector):
            found[name] = colors
    return found


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
NODE_COLORS = ['--de', '--signal', '--text', '--exclude', '--broken', *LAYER_COLORS]
LINK_COLORS = ['--tree', *LAYER_COLORS]
LINES_2D = ['--node-line', '--edge', '--signal', '--intake', '--broken', '--exclude',
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
    # A page is looked at for hours: no theme's background is bright enough to glare, and the themes still differ in
    # how dark they are, from near black to a dim paper.
    grounds = {name: contrast(rgb(colors['--ground']), (1, 1, 1)) for name, colors in found.items()}
    assert all(ratio >= 9 for ratio in grounds.values()), grounds
    assert max(grounds.values()) > 19 and min(grounds.values()) < 15, grounds
    assert {'paper', 'mist'} <= set(found)
    assert len({colors['--ground'] for colors in found.values()}) == len(found)


@pytest.mark.req('VIEW-006')
@pytest.mark.req('VIEW-023')
def test_in_every_theme_each_color_of_the_graph_stands_clear_of_its_background():
    """Every node, link and line of both views holds 3 to 1 against the background it is drawn on, a link as it is
    seen at its drawn opacity, and every label of the 2D map holds 4.5 to 1 against its box."""
    assert ".linkOpacity(Number(css('--link-opacity')))" in page_file('app.js')
    assert "Number(css('--dim-keep'))" in page_file('app.js')
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
    assert low == []


@pytest.mark.req('VIEW-006')
def test_the_colors_are_defined_once_in_the_styles_and_the_script_holds_none():
    import re
    assert re.findall(r'''['"]#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})['"]''', page_file('app.js')) == []
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
    # with a node selected, the others are quieter in color and none is faded toward the background
    assert page.evaluate('window.metaform.selected()') and page.evaluate('''() => {
      const faded = node => Number(getComputedStyle(node).opacity) < 1;
      const others = [...document.querySelectorAll('#map2d svg g.node:not(.sel):not(.near), #map2d .edgePaths path')];
      const labels = window.metaform.labels3d();
      return others.length > 0 && !others.some(node => !/work-/.test(node.getAttribute('class') || '') && faded(node))
        && labels.length > 0 && labels.every(label => label.opacity === 1); }''')
    assert before['ground'] == themes()['space']['--ground']
    # the 2D map is drawn in a holder of no size, so drawing it adds nothing to the page and no scrollbar shows
    page.evaluate('''() => { window.added = [];
      new MutationObserver(list => { for (const change of list) for (const node of change.addedNodes)
        if (node.parentNode === document.body) window.added.push(node.id); }).observe(document.body, {childList: true}); }''')
    for name, colors in themes().items():
        if name == 'space':
            continue
        page.select_option('#theme', name)
        page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length > 0')
        assert page.evaluate('document.documentElement.dataset.theme') == name
        assert token('--ground') == colors['--ground'] == page.evaluate('window.metaform.ground()')
        drawn = page.evaluate('window.metaform.linkColors()')
        assert {link['color'] for link in drawn if link['k'] == 'tree'} == {colors['--tree']}
        # the 3D labels are painted again in the theme's own colors, VIEW-038
        palette = [colors[token].lower() for token in ('--text', '--muted', '--signal', '--broken', '--exclude')]
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
    """Rich, 2026-09-28: no curved edges. A link runs straight between the two nodes it joins."""
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    curves = page.evaluate('window.metaform.curves()')
    assert curves and {link['k'] for link in curves} >= {'purpose', 'encounter', 'tree'}
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
    status, body = answered(web, asked.message_id, 'Yes, keep it.')
    assert status == 200 and body['answer'] == 'Yes, keep it.' and body['closed']
    kept = Store('proj').messages(Node('element', 'code.timer.kitchen'), 'question', False).results
    assert [(record.text, record.answer) for record in kept] == [('Is the 1 Hz tick still wanted?', 'Yes, keep it.')]
    assert Store('proj').messages(None, 'question', True).results == ()
    # only a question is answered from the page; any other record is left as it is
    other = Store('proj').add_work(Node('element', 'code.timer.kitchen'), 'missing', task='build it')
    status, body = answered(web, other.work_id, 'done')
    assert status == 400 and Store('proj').work(None, 'missing', True).results[0].done is None
    assert answered(web, asked.message_id, '   ')[0] == 400  # an answer says something


def reopened(port, record, project='proj'):
    return api(port, '/api/reopen', method='POST', body=json.dumps({'project': project, 'id': record}),
               headers=own_write(port))


@pytest.mark.req('MAP-050')
@pytest.mark.req('VIEW-011')
def test_a_question_answered_by_mistake_is_reopened_from_the_page(run, web, mapped):
    """Rich, 2026-10-03: "How do I reopen a question when I hit the wrong button"."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.timer.kitchen'), 'Is the 1 Hz tick still wanted?',
                      suggestions=['Yes, keep it.', 'No, drop it.'])
    started(run)
    assert reopened(web, asked.message_id)[0] == 400  # an open question has nothing to reopen
    answered(web, asked.message_id, 'No, drop it.')
    status, body = reopened(web, asked.message_id)
    assert status == 200 and (body['closed'], body['answer']) == (None, None)
    waiting = Store('proj').messages(None, 'question', True).results
    assert [(record.message_id, record.suggestions) for record in waiting] == [
        (asked.message_id, ('Yes, keep it.', 'No, drop it.'))]
    status, body = answered(web, asked.message_id, 'Yes, keep it.')
    assert status == 200 and body['answer'] == 'Yes, keep it.'
    told = store.tell(Node('element', 'code.timer.kitchen'), 'The driver is written.')
    store.reply(told.message_id)
    assert reopened(web, told.message_id)[0] == 400  # only a question is reopened from the page
    assert Store('proj').messages(None, 'message', False).results[0].closed


@pytest.mark.req('VIEW-021')
@pytest.mark.req('MAP-050')
def test_an_open_question_glows_at_its_node_and_messages_leads_to_the_oldest_where_it_is_answered(
        run, web, mapped, browser):
    from metaform.data import Node, Store
    store = Store('proj')
    # the alarm and the cook carry no record in the fixture; the kitchen carries a broken one
    first = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?')
    store.ask(Node('element', 'exterior.cook'), 'Who is the cook?')
    kitchen, cook = (store.element(address).element_id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    assert page.is_hidden('#messages') is False and page.inner_text('#messages').strip() == 'Messages 2'
    for node in (kitchen, cook):
        seen = page.evaluate(f'window.metaform.look("{node}")')
        assert (seen['work'], seen['classes'], seen['animated2d']) == (['question'], ['work-question'], True)
        page.wait_for_function(f'() => window.metaform.look("{node}").light3d > 1', timeout=3000)
    assert 'work: question' in page.inner_text('#legend')
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
    assert Store('proj').messages(None, 'question', False).results[0].message_id == first.message_id
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
    """Rich, 2026-10-03: "How do I reopen a question when I hit the wrong button"."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?',
                      suggestions=['Yes, keep it.', 'No, make it louder.'])
    alarm = store.element('code.alarm.audible').element_id
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
    assert Store('proj').messages(None, 'question', False).results[0].message_id == asked.message_id
    assert Store('proj').messages(None, 'question', False).results[0].answer == 'Yes, keep it.'
    assert problems == []


@pytest.mark.req('VIEW-028')
def test_the_two_views_change_places_on_demand_and_each_works_in_either_place(run, web, mapped, browser):
    """Rich, 2026-09-28: the chart in the big view and the graph in the other, on demand, since the chart is so small
    it cannot be read."""
    from metaform.data import Store
    store = Store('proj')
    kitchen, alarm = (store.element(address).element_id for address in ('code.timer.kitchen', 'code.alarm.audible'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    boxes = lambda: page.evaluate("""() => Object.fromEntries(['#map2d', '#big3d', '#stage', '#stage canvas'].map(name => {
        const box = document.querySelector(name).getBoundingClientRect();
        return [name, [Math.round(box.width), Math.round(box.height)]]; }))""")
    area = lambda box: box[0] * box[1]
    first = boxes()
    assert area(first['#stage']) > 2 * area(first['#map2d']) and first['#stage canvas'] == first['#stage']
    page.click('#swapBtn')
    page.wait_for_function("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        const size = name => [Math.round(box(name).width), Math.round(box(name).height)].join();
        return box('#map2d').width * box('#map2d').height > 2 * box('#stage').width * box('#stage').height
            && size('#stage canvas') === size('#stage'); }""")  # the graph library sizes its canvas after the swap returns
    swapped = boxes()
    # each view is its bar and its map, and the two areas are what change hands
    assert swapped['#map2d'] == first['#big3d'] and swapped['#stage canvas'] == swapped['#stage']
    assert swapped['#big3d'][0] == first['#map2d'][0]
    assert page.locator('#map2d svg g.node').count() > 0 and page.is_visible('#fitBtn') and page.is_visible('#swapBtn')
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
    page.click('#swapBtn')
    page.wait_for_function("""() => { const box = name => document.querySelector(name).getBoundingClientRect();
        return box('#stage').width * box('#stage').height > 2 * box('#map2d').width * box('#map2d').height; }""")
    assert boxes() == first and chosen
    assert problems == []


@pytest.mark.req('VIEW-029')
def test_a_node_that_needs_attention_gives_off_light_in_both_views_and_no_other_does(run, web, mapped, browser):
    """Rich, 2026-09-28: when the nodes light up and flash they give off some glow, and the chart flashes too. A
    flash inside a node's outline is lost on a whole map; light that spreads past it is seen from across the map.
    Rich, 2026-09-29: the light is the material's own light emission, spread by the bloom, and no circles are drawn
    around a node."""
    from metaform.data import Node, Store
    store = Store('proj')
    asked = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?')
    kitchen, alarm, cook = (store.element(address).element_id
                            for address in ('code.timer.kitchen', 'code.alarm.audible', 'exterior.cook'))
    broken = [record for record in store.work(Node('element', 'code.timer.kitchen'), 'broken', True).results]
    assert broken  # the fixture's kitchen is broken
    started(run)
    page, problems, _ = opened(browser, web)
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
        run('map', 'work', 'op=done', f'id={record.work_id}', 'resolution=fixed', cwd=mapped)
    run('map', 'reply', asked.message_id, 'answer=Yes.', cwd=mapped)
    for record in store.work(None, None, True, limit=0).results:  # nothing on the map needs attention now
        if record.condition in ('broken', 'fixing', 'exclude'):
            run('map', 'work', 'op=done', f'id={record.work_id}', 'resolution=done', cwd=mapped)
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
    which starts 2.2 seconds after the page selects its first node, once the 2D map is drawn, and takes 0.8 seconds."""
    page.wait_for_function('() => window.metaform.selected()')
    page.wait_for_timeout(3300)
    page.click('#pauseBtn')
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
    """The tooltip of the 3D map with the pointer at a point, or None when nothing there takes it."""
    page.mouse.move(x, y)
    page.wait_for_timeout(250)
    return page.inner_text('#tip3d') if page.is_visible('#tip3d') else None


def staged_pair(run, web, browser, alarm, kitchen):
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform && window.metaform.loaded()', timeout=30000)
    staged(page, {alarm: (2000, 0, 0), kitchen: (2300, 0, 0)},
           ({'x': 2150, 'y': 0, 'z': 900}, {'x': 2150, 'y': 0, 'z': 0}))
    names = {node['id']: node.get('name') for node in page.evaluate('window.metaform.graph().nodes')}
    assert names[alarm] and names[kitchen]
    return page, problems, names


@pytest.mark.req('VIEW-005')
def test_a_node_takes_the_pointer_anywhere_it_is_drawn(run, web, mapped, browser):
    """Rich, 2026-10-03: only a tiny region in the center of a node took a click; anyplace on a node should. The alarm,
    not built, is drawn in characters far wider than its sphere. Read from a picture, the farthest point above its
    center that is drawn takes a hover and a click; a point well past it, over the background, takes neither."""
    from metaform.data import Node, Store
    store = Store('proj')
    store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='build it')
    alarm = store.element('code.alarm.audible').element_id
    kitchen = store.element('code.timer.kitchen').element_id
    page, problems, names = staged_pair(run, web, browser, alarm, kitchen)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").text3d', timeout=20000)
    assert page.evaluate('window.metaform.selected()') == kitchen
    at, far = reach_drawn(page, alarm)
    assert far > 3 * at['r'], (far, at['r'])  # what is drawn reaches far past the sphere
    assert names[alarm] in (hovered(page, at['x'], at['y'] - far) or ''), (far, at['r'])
    assert hovered(page, at['x'], at['y'] - max(1.4 * far, far + 6)) is None, far
    page.mouse.click(at['x'], at['y'] - far)
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"', timeout=5000)
    assert not problems


@pytest.mark.req('VIEW-005')
def test_with_the_bloom_off_a_glass_node_takes_the_pointer_on_its_sphere_and_not_past_it(run, web, mapped, browser):
    """With no record giving off light the bloom is off, and a glass node is drawn to its sphere and no farther: the
    farthest point drawn above the kitchen timer takes a hover, and a point four pixels past it does not."""
    from metaform.data import Node, Store
    store = Store('proj')
    for record in store.work(Node('element', 'code.timer.kitchen'), 'broken', True).results:
        store.finish_work(record.work_id)
    alarm = store.element('code.alarm.audible').element_id
    kitchen = store.element('code.timer.kitchen').element_id
    page, problems, names = staged_pair(run, web, browser, alarm, kitchen)
    page.wait_for_timeout(500)
    assert page.evaluate('window.metaform.bloom().on') is False
    at, far = reach_drawn(page, kitchen)
    assert far <= at['r'] + 3, (far, at['r'])  # drawn to its sphere
    assert names[kitchen] in (hovered(page, at['x'], at['y'] - far) or ''), (far, at['r'])
    assert hovered(page, at['x'], at['y'] - far - 4) is None, (far, at['r'])
    assert not problems


@pytest.mark.req('VIEW-029')
def test_the_light_of_a_node_spreads_past_its_outline_and_stays_behind_a_node_nearer_the_eye(run, web, mapped, browser):
    """Rich, 2026-09-29: the glow was painted on top of everything when it should be behind. The broken kitchen timer
    gives off its light; a join's purpose node is set nearer the eye, beside it, where its glow falls. The glow shows
    over the background around the timer and not over the nearer node."""
    from metaform.data import Node, Store
    store = Store('proj')
    store.ask(Node('element', 'code.alarm.audible'), 'Still wanted?')  # the pass stays on
    kitchen = store.element('code.timer.kitchen').element_id
    broken = store.work(Node('element', 'code.timer.kitchen'), 'broken', True).results
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')           # the light is steady
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    front = next(node['id'] for node in page.evaluate('window.metaform.graph().nodes') if node['id'].startswith('p:'))
    staged(page, {kitchen: (2000, 0, 0), front: (2000, 7, 150)},
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
        run('map', 'work', 'op=done', f'id={record.work_id}', 'resolution=fixed', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{kitchen}").light3d < 1 && window.metaform.bloom().on')
    page.wait_for_timeout(800)
    dark = pixels(page, [on_near, beyond, ground])
    assert sum(dark[1]) < sum(dark[2]) + 6, dark          # with the light gone, that point is background again
    # the nearer node is drawn the same whether the node behind it gives off light or not
    assert all(abs(one - two) <= 3 for one, two in zip(shown[0], dark[0])), (shown[0], dark[0])
    assert problems == []


@pytest.mark.req('VIEW-022')
def test_with_the_bloom_pass_on_what_it_does_not_light_keeps_its_colors(run, web, mapped, browser):
    """The pass spreads what is over full brightness, and the rest of the picture is the one drawn without it. It is
    read on paper, a theme whose background is far from black, where a picture taken apart in the wrong space turned the
    nodes dark while the pass was on."""
    from metaform.data import Store
    store = Store('proj')
    for record in store.work(None, None, True, limit=0).results:  # nothing needs attention: the pass is off
        store.finish_work(record.work_id, 'done')
    cook, alarm = (store.element(address).element_id for address in ('exterior.cook', 'code.alarm.audible'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')
    page.select_option('#theme', 'paper')
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
    # a question on the alarm, far out of view, lights it, and the pass comes on
    run('map', 'ask', 'element:code.alarm.audible', 'Still wanted?', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").light3d > 1 && window.metaform.bloom().on',
                           timeout=5000)
    page.wait_for_timeout(800)
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
    """Rich, 2026-09-29: please fix the big white balls from flashing dark every time something goes through them. The
    dots that travel a join are drawn solid, as the approved prototype draws them. A dot inside the DE's white glass
    shows through it and takes no light from it; a dot in front of it, with the bloom pass on, has the color it has
    farther along its link, never black. The dots are held still, so what is read does not hang on how fast the page
    draws."""
    from metaform.data import Store
    store = Store('proj')
    for record in store.work(None, None, True, limit=0).results:  # the kitchen timer is drawn in its own white
        store.finish_work(record.work_id, 'done')
    started(run)
    _, at, _ = keys_of(web)
    kitchen = at['code.timer.kitchen']
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    # The join the kitchen timer receives: its dots leave the timer's center for the purpose vertex, set in front of the
    # timer, above it and nearer the eye.
    purpose = next(link['target'] for link in page.evaluate('window.metaform.graph().links')
                   if link['k'] == 'purpose' and link['source'] == kitchen)
    camera = ({'x': 2000, 'y': 0, 'z': 40}, {'x': 2000, 'y': 0, 'z': 0})
    staged(page, {kitchen: (2000, 0, 0), purpose: (2000, 12, 25), at['code.alarm.audible']: (2100, 40, 80)}, camera)
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
    run('map', 'ask', 'element:code.alarm.audible', 'Still wanted?', cwd=mapped)  # the alarm, out of view, lights
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


@pytest.mark.req('VIEW-027')
def test_the_characters_of_a_part_not_built_keep_changing_and_glow_when_a_signal_reaches_them(run, web, mapped, browser):
    """Rich, 2026-09-28: numbers and letters in both cases, the strings moving all the time; a signal reaching a part
    still drawn in characters is a pulsing bloom."""
    from metaform.data import Node, Store
    store = Store('proj')
    store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='build it')
    store.add_work(Node('element', 'exterior.cook'), 'missing', task='build that')
    asked = store.ask(Node('element', 'exterior.cook'), 'Is the cook still wanted?')
    alarm, cook = (store.element(address).element_id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.wait_for_function(f'() => window.metaform.look("{alarm}").text3d && window.metaform.look("{cook}").text3d')
    texts = [page.evaluate(f'window.metaform.look("{alarm}").text')]
    for _ in range(3):  # a part waiting turns 1.5 times a second of the text's clock, which moves at most 0.1 s a
        # frame, so each change comes within 10 frames or a second, whichever is later, however slow the frames
        texts.append(page.evaluate('''async ([id, last]) => { const began = performance.now();
            for (let frames = 0; window.metaform.look(id).text === last; frames++) {
              if (frames >= 10 && performance.now() - began > 1000) return null;
              await new Promise(done => requestAnimationFrame(done)); }
            return window.metaform.look(id).text; }''', [alarm, texts[-1]]))
        assert texts[-1] is not None, texts                         # the strings move all the time
    assert len(set(texts)) >= 3
    assert all(len(text) >= 32 and text.isalnum() and text.isascii() for text in texts)
    assert any(letter.islower() for letter in ''.join(texts)) and any(letter.isupper() for letter in ''.join(texts))
    assert any(letter.isdigit() for letter in ''.join(texts))
    assert page.evaluate(f'window.metaform.look("{alarm}").signal3d') == 0  # no signal has reached the alarm
    for _ in range(2):                                              # the cook's text glows, and the glow swells and fades
        page.wait_for_function(f'() => window.metaform.look("{cook}").signal3d > 0.6', timeout=10000)
        page.wait_for_function(f'() => window.metaform.look("{cook}").signal3d < 0.2', timeout=10000)
    question = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--question").trim().toLowerCase()')
    page.wait_for_function(f'() => window.metaform.look("{cook}").signal3d > 0.5', timeout=10000)
    assert page.evaluate(f'window.metaform.look("{cook}").signalColor3d') == question
    store.reply(asked.message_id, 'Yes.')
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded()')
    page.wait_for_function(f'() => window.metaform.look("{cook}").text3d === true')
    page.wait_for_timeout(1500)
    assert page.evaluate(f'window.metaform.look("{cook}").signal3d') == 0
    assert problems == []


@pytest.mark.req('VIEW-021')
@pytest.mark.req('MAP-050')
def test_a_question_is_answered_with_one_click_on_a_suggestion_or_by_typing_under_other(run, web, mapped, browser):
    """Rich, 2026-09-28: always make a suggestion when asking; a button for each suggestion, or Other and type."""
    from metaform.data import Node, Store
    store = Store('proj')
    first = store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?', suggestions=['Yes, keep it', 'No, make it louder'])
    second = store.ask(Node('element', 'exterior.cook'), 'Who is the cook?', suggestions=['Whoever sets the timer'])
    alarm, cook = (store.element(address).element_id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.unread')
    page.wait_for_selector('#float button.suggestion')
    shown = page.eval_on_selector_all('#float button.suggestion, #float button.other', 'found => found.map(one => one.textContent)')
    assert shown == ['Yes, keep it', 'No, make it louder', 'Other']
    assert page.locator('#float button.suggestion').first.get_attribute('class').split() == ['suggestion', 'recommended']
    assert page.locator('#float textarea.answer').count() == 0       # the box for typing shows under Other only
    page.click('#float button.suggestion >> nth=1')
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    assert Store('proj').messages(Node('element', 'code.alarm.audible'), 'question', False).results[0].answer \
        == 'No, make it louder'
    page.evaluate(f'window.metaform.menu("{cook}")')
    page.click('#menu button.unread')
    page.wait_for_selector('#float button.other')
    page.click('#float button.other')
    page.fill('#float textarea.answer', 'The person who is cooking.')
    page.click('#float button.answer')
    page.wait_for_function('() => document.querySelector("#messages").hidden')
    assert Store('proj').messages(Node('element', 'exterior.cook'), 'question', False).results[0].answer \
        == 'The person who is cooking.'
    assert first.message_id != second.message_id and problems == []


@pytest.mark.req('VIEW-028')
@pytest.mark.req('VIEW-021')
def test_each_view_has_its_own_fit_and_swap_and_the_messages_button_is_at_the_top(run, web, mapped, browser):
    """Rich, 2026-09-29: both views get a Fit button and a Swap button, and the messages box goes to the top of the
    screen."""
    from metaform.data import Node, Store
    Store('proj').ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    seen = lambda: [page.is_visible(name) for name in ('#fitBtn', '#swapBtn', '#fit3dBtn', '#swap3dBtn')]
    larger = lambda: page.evaluate("""() => { const area = name => { const box = document.querySelector(name).getBoundingClientRect();
        return box.width * box.height; }; return area('#map2d') > area('#stage') ? '2d' : '3d'; }""")
    assert seen() == [True] * 4 and larger() == '3d'
    assert page.evaluate('Boolean(document.querySelector("#messages").closest("header"))') and page.is_visible('#messages')
    page.click('#swap3dBtn')                                          # the 3D view's own Swap
    page.wait_for_function("""() => { const area = name => { const box = document.querySelector(name).getBoundingClientRect();
        return box.width * box.height; }; return area('#map2d') > area('#stage'); }""")
    assert seen() == [True] * 4 and larger() == '2d'                  # each still has both, in either place
    still3d(page, 2)                                                  # the page's fit on opening and the swap's
    page.evaluate('window.metaform.zoom3d(0.2)')                      # far in, so the whole map is no longer in view
    page.wait_for_timeout(300)
    near = page.evaluate('window.metaform.away3d()')
    page.click('#fit3dBtn')
    page.wait_for_function(f'() => window.metaform.away3d() > {near} * 1.5', timeout=15000)
    # Rich, 2026-09-29: the Fit on the right reacted to the one on the left, and only zoomed out. Each Fit moves its
    # own map, and the 3D map's goes between the whole map and close on the selected node.
    still3d(page, 3)
    wheel(page, -400)  # the 2D map in the large area shows the whole diagram, VIEW-041; zoomed in, its Fit has a move
    whole, chart = page.evaluate('window.metaform.away3d()'), page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")')
    page.click('#fitBtn')                                             # the 2D map's Fit
    still2d(page)
    assert abs(page.evaluate('window.metaform.away3d()') - whole) < 1  # the 3D map did not move
    assert page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")') != chart
    chart = page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")')
    page.click('#fit3dBtn')                                           # the 3D map's Fit: in on the selected node
    page.wait_for_function(f'() => window.metaform.away3d() < {whole} * 0.7', timeout=15000)
    assert page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")') == chart  # the 2D map did not move
    page.click('#fit3dBtn')                                           # and out again
    page.wait_for_function(f'() => window.metaform.away3d() > {whole} * 0.9', timeout=15000)
    page.click('#swapBtn')                                            # and the 2D view's own
    page.wait_for_function("""() => { const area = name => { const box = document.querySelector(name).getBoundingClientRect();
        return box.width * box.height; }; return area('#stage') > area('#map2d'); }""")
    page.evaluate("try { localStorage.removeItem('metaform.swapped') } catch (error) {}")
    assert problems == []


@pytest.mark.req('VIEW-030')
@pytest.mark.req('MAP-050')
def test_a_right_click_on_a_node_opens_its_menu_and_its_messages_are_read_in_a_floating_window(run, web, mapped, browser):
    """Rich, 2026-09-29: right-click a node to read its unread messages, past messages for review on the menu, in a
    floating window, from the 2D map and from the 3D map."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm_node = Node('element', 'code.alarm.audible')
    answered = store.ask(alarm_node, 'Was the tone ever louder?', suggestions=['Yes', 'No'])
    store.reply(answered.message_id, 'No')
    store.ask(alarm_node, 'Is the quiet tone still wanted?', suggestions=['Yes', 'No'])
    note = store.tell(alarm_node, 'The piezo driver is written and waits for a test on the board.')
    assert note.notices == ()
    alarm, cook = (store.element(address).element_id for address in ('code.alarm.audible', 'exterior.cook'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    assert page.is_hidden('#menu') and page.is_hidden('#float')
    assert page.inner_text('#messages').strip() == 'Messages 2'       # a question and a note wait
    entries = lambda: page.eval_on_selector_all('#menu button', 'found => found.map(one => [one.className, one.textContent, one.disabled])')
    GIVE = (['memories', 'Memories 0', True],                           # the first of the further acts, VIEW-031
            ['notes', 'Notes 0', False], ['history', 'Work history 0', True],  # VIEW-034, VIEW-036
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
    assert [record.message_id for record in read] == [note.message_id]
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
    """Rich, 2026-09-29: a text editor window and a node selector on the right-click menu, where nodes are linked to
    the prompt or inserted inline by their proper noun, from a clickable browser of the namespace."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm, kitchen, cook = (store.element(address).element_id
                            for address in ('code.alarm.audible', 'code.timer.kitchen', 'exterior.cook'))
    names = {address: store.element(address).short_name for address in ('code.timer.kitchen', 'exterior.cook')}
    before = len(store.work(None, None, None, limit=0).results)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.task')
    page.wait_for_selector('#task:not([hidden])')
    linked = lambda: page.eval_on_selector_all('#task .linked [data-address]', 'found => found.map(one => one.dataset.address)')
    assert linked() == ['code.alarm.audible']                        # the node it was opened at
    listed = page.eval_on_selector_all('#task .browser [data-address]', 'found => found.map(one => one.dataset.address)')
    assert listed == sorted(listed) and {'code.alarm.audible', 'code.timer.kitchen', 'exterior.cook'} <= set(listed)
    page.click('#task .put')                                          # a task with no text is not written
    page.wait_for_timeout(400)
    assert len(Store('proj').work(None, None, None, limit=0).results) == before and page.is_visible('#task')
    page.click('#task .text')
    page.keyboard.type('Make the tone louder when ')
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
        'missing', 'broken', 'flawed', 'enhancement']                 # the four kinds of ticket, VIEW-035
    page.select_option('#task .condition', 'flawed')
    page.check('#task .backlog')
    page.click('#task .put')
    page.wait_for_function('() => document.querySelector("#task").hidden')
    written = [record for record in Store('proj').work(None, None, True, limit=0).results
               if record.task and record.task.startswith('Make the tone louder')]
    text = f"Make the tone louder when [[{names['code.timer.kitchen']}|code.timer.kitchen]] runs out of time."
    # one ticket, on the node it was opened at, linking every other node of the task for reference, Rich 2026-10-01
    [ticket] = written
    assert (ticket.address, ticket.task, ticket.condition, ticket.column) == ('code.alarm.audible', text, 'flawed',
                                                                               'backlog')
    assert [link.address for link in ticket.links] == ['exterior.cook', 'code.timer.kitchen']
    page.wait_for_function(f'() => window.metaform.look("{alarm}").work.includes("flawed")', timeout=6000)
    assert 'flawed' not in page.evaluate(f'window.metaform.look("{cook}").work')
    assert kitchen and problems == []


@pytest.mark.req('VIEW-032')
def test_the_task_editor_has_a_chart_of_its_own_to_browse_and_is_sized_or_made_full_screen(run, web, mapped, browser):
    """Rich, 2026-09-29: in the editor a 2D chart browser, independent from the other two, for seeing and browsing
    the project; the window sized or made full screen; the entry named Add Task."""
    from metaform.data import Store
    store = Store('proj')
    alarm, kitchen = (store.element(address).element_id for address in ('code.alarm.audible', 'code.timer.kitchen'))
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
    """Rich, 2026-09-29: a new element tool so the user can add and join something into the map, with an option to
    kick off an agent to pre-validate the new element, prompted in his words."""
    import sys

    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').element_id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE_AGENT}"', cwd=mapped)
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask'})
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
    page.fill('#element .name', 'Flash Alert')                         # its canonical name, Rich 2026-10-01
    page.select_option('#element .receives', 'node')                  # the alarm holds the purpose; the new part serves it
    page.fill('#element .purpose', 'Tell a cook who cannot hear that the time is up.')
    page.fill('#element .ef', 'Flashes a lamp when the timer runs out.')
    page.check('#element .validate')
    page.select_option('#element select.agent', 'codex')
    page.click('#element .add')
    page.wait_for_function('() => document.querySelector("#element").hidden')
    store = Store('proj')
    made = store.element('code.alarm.visible')
    assert made is not None and (made.layer, made.name_length, made.short_name, made.name) == (
        'additions', 2, 'visible alarm', 'Flash Alert')
    joined = [join for join in store.joins('code.alarm.audible').results if join.provider == made.element_id]
    assert [(join.receiver, join.layer, join.purpose, join.ef) for join in joined] == [
        (alarm, 'additions', 'Tell a cook who cannot hear that the time is up.', 'Flashes a lamp when the timer runs out.')]
    work = store.work(Node_of('code.alarm.visible'), 'missing', True).results
    assert len(work) == 1 and work[0].task == f'{VALIDATE} The element is code.alarm.visible.'
    page.wait_for_function(f'() => window.metaform.look("{made.element_id}").text3d === true', timeout=8000)
    made_session = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/new')
    assert Path(made_session['message']['params']['cwd']).resolve() == Path(mapped).resolve()
    told = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt')
    assert work[0].work_id in told['message']['params']['prompt'][0]['text']
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=30000)
    assert Store('proj').ticket(work[0].work_id).work.taken_by.startswith('codex ')
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
    assert [join.provider for join in Store('proj').joins('code.alarm.silent').results] == [alarm] and silent is not None
    page.wait_for_timeout(1200)
    assert sum(json.loads(line).get('message', {}).get('method') == 'session/new'
               for line in log.read_text().splitlines()) == 1
    run('dispatch', 'stop', work[0].work_id, cwd=mapped)
    assert problems == []


def Node_of(address):
    from metaform.data import Node
    return Node('element', address)


@pytest.mark.req('VIEW-019')
@pytest.mark.req('PROJ-030')
def test_the_clear_is_in_the_administration_menu_asks_are_you_sure_and_its_backup_is_restored_from_the_menu(
        run, home, web, mapped, browser):
    """Rich, 2026-09-29: the clear is in an administration menu, says are you sure, backs the project up, allows
    restoration easily and tells the user. Rich, 2026-10-01: a clear that also offers to restore is not good design;
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
def test_a_person_and_an_agent_keep_their_notes_at_a_node_in_one_place(run, web, mapped, browser):
    """Rich, 2026-09-29: notes where both he and an agent put notes in place. Rich, 2026-10-02: "Allow one single note
    not a list, limit its characters to 2048, make it so you can edit the note and so can the user, its not protected,
    it doesnt expire, they dont build up." The fixture's folder leaves memory out, and the note shows all the same."""
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').element_id
    noted = lambda: json.loads(run('memory', 'note', 'element:code.alarm.audible', '--json', cwd=mapped).stdout)['note']
    run('memory', 'note', 'element:code.alarm.audible', 'text=The tone is 2 kHz.', 'by=agent', cwd=mapped)  # an agent's
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 1'
    page.click('#menu button.notes')
    page.wait_for_selector('#notes:not([hidden])')
    assert page.input_value('#notes textarea') == 'The tone is 2 kHz.' and 'agent' in page.inner_text('#notes .by')
    assert page.get_attribute('#notes textarea', 'maxlength') == '2048'
    page.fill('#notes textarea', 'The tone is 2 kHz. Too quiet in a loud kitchen; ask before changing the pitch.')
    assert page.inner_text('#notes .count') == '78 / 2048'
    page.click('#notes .save')                                        # the person edits the agent's note in place
    page.wait_for_function('() => document.querySelector("#notes .by").textContent.includes("you")')
    assert (noted()['text'], noted()['by']) == (
        'The tone is 2 kHz. Too quiet in a loud kitchen; ask before changing the pitch.', 'user')
    page.click('#notes .close')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 1'      # one note, never a list
    page.keyboard.press('Escape')
    run('memory', 'note', 'element:code.alarm.audible', 'text=Raised to 3 kHz.', 'by=agent', cwd=mapped)  # and the agent
    page.evaluate(f'window.metaform.note("{alarm}")')
    page.wait_for_function('() => document.querySelector("#notes textarea").value === "Raised to 3 kHz."')
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
    """Rich, 2026-10-02: "Every time the screen updates it closes the message you are typing and you lose what you
    wrote". Each write window is opened and typed into, a map change reaches the page, and each is still open with
    what was typed in it."""
    from metaform.data import Node, Store, prompts
    store = Store('proj')
    store.ask(Node('element', 'code.alarm.audible'), 'Is the quiet tone still wanted?', suggestions=['Yes', 'No'])
    alarm = store.element('code.alarm.audible').element_id
    prompts.add_prompt('practices', 'markdown', 'one\n')
    notes = store.layer_ref('notes')
    prompts.record_use(prompts.prompt_version('practices').version_id, 'proj', notes.metaform_id, notes.layer_id)
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
    page.wait_for_selector('#float button.other')
    page.click('#float button.other')
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
    run('map', 'ask', 'element:code.alarm.audible', 'Is the tone too high?', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {before}', timeout=10000)  # read and drawn again
    assert page.inner_text('#messages').strip() == 'Messages 2'
    assert page.evaluate(kept) == typed
    # and one that shows another metaform, read as on opening
    before = page.evaluate('window.metaform.changes()')
    run('add', 'metaform', 'fresh', cwd=mapped)
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
    """Rich, 2026-09-29: the menu of a node has an entry for its memories; choosing it, in the 2D map or the 3D map,
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
    expected, at, _ = keys_of(web)
    kitchen, cook = at['code.timer.kitchen'], at['exterior.cook']
    outer = next(join['join_id'] for join in expected['joins'] if join['receiver'] == cook)
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
    assert 'kitchen timer' in inside(page)[1]
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
    page.keyboard.press('Escape')
    page.wait_for_function('() => !window.metaform.memory() && document.querySelector("#map2d svg[data-base]")')
    page.wait_for_function('() => window.metaform.drawn().nodes === window.metaform.graph().nodes.length')
    assert page.evaluate('document.querySelectorAll("#map2d svg g.node").length') == base
    assert selected() == kitchen and not page.is_visible('#crumbs')

    # from the 3D map: the node's right-click; back by the breadcrumb, and by the Back button
    page.evaluate(f'window.metaform.menu("{kitchen}")')
    page.click('#menu button.memories')
    page.wait_for_function(f'() => window.metaform.memory() && window.metaform.memory().key === "{kitchen}"')
    assert sorted(network()['nodes']) == sorted([kitchen, drift, tone, waits])
    page.click('#crumbs a')
    page.wait_for_function('() => !window.metaform.memory() && document.querySelector("#map2d svg[data-base]")')
    page.evaluate(f'window.metaform.memories("{kitchen}")')
    page.wait_for_function('() => window.metaform.memory()')
    page.click('#backBtn')
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
    page.keyboard.press('Escape')
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
    """Rich, 2026-09-29: the 3D graph needs antialiasing, the joins break apart when zoomed out. The picture itself
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


HELD = ('proj holds one metaform, main, and no report files. Only an empty project is removed; clearing it backs it '
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
    """Rich, 2026-10-01: dragging the 2D map selected the label text of every node, and the next drag dragged the
    labels instead of the map. A drag that starts on a label and sweeps across the others moves the view, selects no
    text, and the drag after it moves the view again."""
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').element_id
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

    label = page.evaluate(f"""(() => {{ const box = document.querySelector('#map2d svg g.node text').getBoundingClientRect();
        return [box.left + box.width / 2, box.top + box.height / 2]; }})()""")
    sweep(label, lambda: page.get_attribute('#map2d svg', 'viewBox'))
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.task')
    page.wait_for_selector('#task .chart svg g[data-address] text')
    page.wait_for_timeout(900)
    label = page.evaluate("""(() => { const box = document.querySelector('#task .chart svg g[data-address] text').getBoundingClientRect();
        return [box.left + box.width / 2, box.top + box.height / 2]; })()""")
    sweep(label, lambda: page.get_attribute('#task .chart svg', 'viewBox'))
    assert problems == []



@pytest.mark.req('VIEW-036')
def test_a_nodes_menu_opens_its_work_history_every_ticket_open_and_closed_with_its_steps(run, web, mapped, browser):
    """Rich, 2026-10-01: right-clicking a node gives access to its work history: every ticket on it, open and done,
    newest first, each with its kind, its column, who took it, the steps the agent filed and how it was resolved."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    old = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='wire the tone')
    store.take_work(old.work_id, steps=2, by='codex')
    store.step_work(old.work_id, 'Traced the pin.')
    store.step_work(old.work_id, 'Wired the driver.')
    store.finish_work(old.work_id, 'wired')
    store.add_work(Node('element', 'code.alarm.audible'), 'enhancement', task='a softer tone', held=True)
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
    assert 'enhancement' in newest and 'backlog' in newest and 'a softer tone' in newest
    for words in ('broken', 'done', 'wire the tone', 'codex', 'Traced the pin.', 'Wired the driver.', 'wired'):
        assert words in oldest, (words, oldest)
    assert 'Work history' in page.text_content('#float .title')
    assert page.locator('#float .ticket .age').all_inner_texts() == ['now']
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_the_board_holds_the_tickets_in_four_columns_and_a_card_dragged_moves_its_ticket(run, web, mapped, browser,
                                                                                     monkeypatch):
    """Rich, 2026-10-01: an actual classic kanban window you can open that mirrors the features in a traditional
    kanban: columns with counts, cards with their kind, nodes and progress, dragging between and within columns, a
    search and a filter by kind, and adding a card."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    kitchen = Node('element', 'code.timer.kitchen')
    todo = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone', links=[kitchen])
    store.add_work(kitchen, 'enhancement', task='a second countdown', held=True)
    from datetime import UTC, datetime, timedelta

    from metaform import home
    with monkeypatch.context() as clock:
        earlier = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        clock.setattr(home, 'now', lambda: earlier)
        doing = store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='wire the tone')
    store.take_work(doing.work_id, steps=3, by='codex')
    store.step_work(doing.work_id, 'Traced the pin.')
    done = store.add_work(kitchen, 'missing', task='the display')
    store.finish_work(done.work_id, 'built')
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
    held = Store('proj').work(limit=0).results
    expected = [str(sum(record.column == column for record in held)) for column in ('backlog', 'todo', 'doing', 'done')]
    assert [count(column) for column in ('backlog', 'todo', 'doing', 'done')] == expected
    card = page.locator(f'#board .card[data-id="{todo.work_id}"]')
    assert card.get_attribute('data-kind') == 'flawed' and 'a quieter tone' in card.inner_text()
    chips = card.locator('.node').all_inner_texts()
    assert len(chips) == 2                                              # the node assigned and the one for reference
    worked = page.locator(f'#board .card[data-id="{doing.work_id}"]')
    assert 'codex' in worked.inner_text() and '1/3' in worked.inner_text()
    assert worked.locator('.age').inner_text() == 'now'
    page.drag_and_drop(f'#board .card[data-id="{todo.work_id}"]', '#board .column[data-column="doing"] .cards')
    page.wait_for_function(f'() => document.querySelector(\'#board .column[data-column="doing"] .card[data-id="{todo.work_id}"]\')')
    moved = next(record for record in Store('proj').work(limit=0).results if record.work_id == todo.work_id)
    assert (moved.column, moved.taken_by, moved.condition) == ('doing', 'user', 'flawed')
    assert int(count('doing')) == int(expected[2]) + 1 and int(count('todo')) == int(expected[1]) - 1
    page.fill('#board .search', 'quieter')
    assert page.locator('#board .card:visible').count() == 1
    page.fill('#board .search', '')
    page.click('#board .kinds [data-kind="flawed"]')                    # a kind toggled off hides its cards
    assert page.locator(f'#board .card[data-id="{todo.work_id}"]').is_hidden()
    page.click('#board .kinds [data-kind="flawed"]')
    page.locator(f'#board .card[data-id="{todo.work_id}"] .node').first.click()
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"')
    page.click('#board .add')
    page.wait_for_selector('#task:not([hidden])')
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_board_priority_controls_save_order_with_filters_and_after_reloading(run, web, mapped, browser):
    from metaform.data import Node, Store
    store = Store('proj')
    node = Node('element', 'code.alarm.audible')
    tickets = [store.add_work(node, 'enhancement', task=f'priority {name}') for name in ('first', 'second', 'third')]
    for position, ticket in enumerate(tickets):
        store.move_work(ticket.work_id, 'todo', position)
    started(run)
    page, problems, _ = opened(browser, web)
    page.click('#boardBtn')
    column = '#board .column[data-column="todo"]'
    ids = [ticket.work_id for ticket in tickets]
    def control(index, name):
        return page.locator(f'{column} .card[data-id="{ids[index]}"]').get_by_role('button', name=name, exact=True)

    def expect_order(expected):
        page.wait_for_function('''expected => [...document.querySelectorAll('#board .column[data-column="todo"] .card')]
            .map(card => card.dataset.id).filter(id => expected.includes(id)).join() === expected.join()''', arg=expected)
        saved = sorted((record for record in Store('proj').work(limit=0).results if record.work_id in ids),
                       key=lambda record: record.position)
        assert [record.work_id for record in saved] == expected
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


@pytest.mark.req('VIEW-035')
def test_a_ticket_flashes_its_node_in_its_kinds_light_faster_with_each_step_filed(run, web, mapped, browser):
    """Rich, 2026-10-01: broken flashes red, not broken but not right flashes yellow, an enhancement green; flashing
    lets you see the real node color and sense how far along it is by the flashing speed."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    kitchen = store.element('exterior.cook').element_id  # the timer itself has a broken ticket in the fixture
    flawed = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone')
    store.take_work(flawed.work_id, steps=4, by='codex')
    store.add_work(Node('element', 'exterior.cook'), 'enhancement', task='a second recipe')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    color = lambda name: page.evaluate(f'getComputedStyle(document.documentElement).getPropertyValue("{name}").trim().toLowerCase()')
    for node, light in ((alarm, color('--flawed')), (kitchen, color('--enhancement'))):
        page.wait_for_function(f'() => window.metaform.look("{node}").color3d === "{light}"', timeout=4000)
        page.wait_for_function(f'() => window.metaform.look("{node}").color3d !== "{light}"', timeout=4000)  # its own between
    slow = page.evaluate(f'window.metaform.look("{alarm}").pace')
    for said in ('Found the gain.', 'Lowered it.'):
        run('map', 'work', 'op=step', f'id={flawed.work_id}', f'said={said}', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").pace < {slow}', timeout=6000)
    faster = page.evaluate(f'window.metaform.look("{alarm}").pace')
    assert faster < slow and page.evaluate(f'window.metaform.look("{kitchen}").pace') == slow
    assert problems == []


def live_session(work_id, agent='claude', state='running'):
    """A dispatch session row for a ticket, as the runner writes it, so the page counts its agent as working: a figure
    on the map and an entry in the agents key are drawn only for a live session, VIEW-035 and VIEW-039."""
    import metaform.modules.dispatch  # noqa: F401  declares its tables
    from metaform.data import Store
    with Store('proj', module='dispatch').tables() as tx:
        held = tx.get('sessions', {'session_id': f's-{work_id}'})
        if held is None:
            tx.insert('sessions', {'session_id': f's-{work_id}', 'work_id': work_id, 'agent': agent, 'state': state,
                                   'started': '2026-10-03T00:00:00Z', 'seq': len(work_id) + int(work_id[:6], 16) % 1000})
        else:
            tx.update('sessions', {'session_id': f's-{work_id}'}, {'state': state})


@pytest.mark.req('VIEW-035')
def test_an_agents_figure_walks_from_the_de_to_its_ticket_circles_it_and_walks_back_when_it_closes(run, web, mapped, browser):
    """Rich, 2026-10-01: the agents materialize on the most primary node and navigate the mesh to the node being
    worked on; they go onto it and circle it until the ticket is closed, then navigate back; even if the agent
    finished, they still touch the node and walk back."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    cook = store.element('exterior.cook').element_id
    run('enable', 'dispatch')
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone')
    store.take_work(worked.work_id, steps=2, by='codex')
    live_session(worked.work_id, 'codex')
    other = store.add_work(Node('element', 'exterior.cook'), 'enhancement', task='a third recipe')
    store.take_work(other.work_id, by='claude')
    live_session(other.work_id)
    orphan = store.add_work(Node('element', 'exterior.cook'), 'missing', task='left taken')   # no session behind it
    store.take_work(orphan.work_id, by='gone')
    quick = store.add_work(Node('element', 'exterior.cook'), 'enhancement', task='a second recipe')
    store.take_work(quick.work_id, by='claude')
    store.finish_work(quick.work_id, 'added')
    live_session(quick.work_id, state='ended')                        # finished before the page opened
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 2', timeout=15000)
    # Rich, 2026-10-03: an agent that is not active is not on the map, and the key lists only agents at work
    assert {one['work_id'] for one in page.evaluate('window.metaform.figures()')} == {worked.work_id, other.work_id}
    assert sorted(page.eval_on_selector_all('#agents .agent', 'found => found.map(one => one.dataset.id)')) == sorted(
        [worked.work_id, other.work_id])
    page.evaluate('''() => { window.stages = {}; setInterval(() => { for (const figure of window.metaform.figures())
        (window.stages[figure.work_id] ||= new Set()).add(figure.stage); }, 50); }''')
    glyphs = page.evaluate('window.metaform.figures().map(figure => figure.glyph)')
    assert len(set(glyphs)) == 2                                      # no two at work look alike
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{worked.work_id}" && one.stage === "circling")',
                           timeout=20000)
    page.wait_for_timeout(1000)                                      # out onto its orbit
    figure = next(one for one in page.evaluate('window.metaform.figures()') if one['work_id'] == worked.work_id)
    node = page.evaluate(f'window.metaform.at3d("{alarm}")')
    away = sum((figure[axis] - node[axis]) ** 2 for axis in 'xyz') ** 0.5
    assert node['r'] < away < node['r'] + 2.5 * figure['scale'], (away, node, figure)  # on the node and around it
    run('map', 'work', 'op=done', f'id={worked.work_id}', 'resolution=quieter', cwd=mapped)
    live_session(worked.work_id, 'codex', state='ended')
    page.wait_for_function(f'() => (window.stages["{worked.work_id}"] || new Set()).has("returning")', timeout=10000)
    page.wait_for_function(f'() => !window.metaform.figures().some(one => one.work_id === "{worked.work_id}")', timeout=20000)
    live_session(other.work_id, state='ended')                        # stopped with its ticket open: it goes too
    run('map', 'ask', 'element:code.timer.kitchen', 'Is one second right?', cwd=mapped)  # a change the page hears
    page.wait_for_function('() => window.metaform.figures().length === 0', timeout=20000)
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=10000)
    assert cook and problems == []


@pytest.mark.req('VIEW-035')
@pytest.mark.req('VIEW-027')
def test_an_agents_figure_is_big_enough_to_see_with_the_whole_map_in_view_and_circles_at_one_slow_pace_as_steps_are_filed(
        run, web, mapped, browser):
    """Rich, 2026-10-02: "its so tint", "Its too fast to even see what it is", "the agent doesnt speed up the nodes
    flashing or text is supposed to", "sloyly moving around it should be much bigger though I couldnt even see it and I
    was watching it closely". The map is spread to hundreds of units, as a real map is, and seen whole: each figure
    stands tall enough on screen to see what it is, and circles its node slowly at one pace while steps are filed,
    while the node's flashing, and the text of a part not built, quicken."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    cook = store.element('exterior.cook').element_id
    far = store.element('code.timer.kitchen.display').element_id
    run('enable', 'dispatch')
    flawed = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone')
    store.take_work(flawed.work_id, steps=4, by='codex')
    live_session(flawed.work_id, 'codex')
    missing = store.add_work(Node('element', 'exterior.cook'), 'missing', task='a second recipe')
    store.take_work(missing.work_id, steps=4, by='claude')
    live_session(missing.work_id)
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 2'
                           ' && window.metaform.figures().every(one => one.stage === "circling")', timeout=30000)
    page.wait_for_timeout(2600)                                       # the page's own fit of the whole map
    page.click('#pauseBtn')
    page.evaluate(f'window.metaform.pin3d("{far}", 600, 0, 0)')       # a map that spans hundreds of units
    page.evaluate('window.metaform.view3d({x: 300, y: 0, z: 900}, {x: 300, y: 0, z: 0})')  # seen whole
    page.wait_for_timeout(800)
    assert 0 < page.evaluate(f'window.metaform.screen3d("{far}").x') < page.evaluate('innerWidth')
    for figure in page.evaluate('window.metaform.figures()'):
        assert figure['px'] >= 40, figure                             # big enough to see what it is

    def lap(work_id):  # seconds for one turn around the node, on the figure's own clock, whatever the frame rate
        turned = page.evaluate(f'''async () => {{ const one = () => window.metaform.figures()
            .find(figure => figure.work_id === "{work_id}"); const from = one();
            await new Promise(done => setTimeout(done, 2000));
            const to = one(); return [to.angle - from.angle, to.clock - from.clock]; }}''')
        return 2 * math.pi * turned[1] / turned[0]
    before = {work_id: lap(work_id) for work_id in (flawed.work_id, missing.work_id)}
    pace = page.evaluate(f'window.metaform.look("{alarm}").pace')
    turns = page.evaluate(f'window.metaform.look("{cook}").turns')
    for said in ('Found the gain.', 'Lowered it.'):
        run('map', 'work', 'op=step', f'id={flawed.work_id}', f'said={said}', cwd=mapped)
        run('map', 'work', 'op=step', f'id={missing.work_id}', f'said={said}', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{alarm}").pace < {pace}', timeout=6000)  # the flashing quickens
    page.wait_for_function(f'() => window.metaform.look("{cook}").turns > {turns}', timeout=6000)  # so does the text
    after = {work_id: lap(work_id) for work_id in (flawed.work_id, missing.work_id)}
    for work_id in before:
        assert before[work_id] >= 10, before                          # slowly around its node
        assert abs(after[work_id] - before[work_id]) < 0.1 * before[work_id], (before, after)  # one pace, never faster
    assert problems == []


@pytest.mark.req('VIEW-038')
def test_the_labels_wrap_keep_the_draw_order_and_the_hover_says_what_a_part_does(run, web, mapped, browser):
    """Rich, 2026-10-01: make these labels actually useful and respect the draw order; word wrap rather than cut off;
    the hover said the name, then the name again, then the name in reverse; the data is in the joins. Rich,
    2026-10-02: "I never said that I was like what the fuck maybe try observing the depth order": the alarm is
    selected, and its label still goes under the nearer timer's."""
    from metaform.data import Store
    store = Store('proj')
    kitchen = store.element('code.timer.kitchen').element_id
    alarm = store.element('code.alarm.audible').element_id
    store.add_element('notes', 'code.controller.address.fallback', name_length=3)
    long = store.element('code.controller.address.fallback').element_id
    started(run)
    page, problems, _ = opened(browser, web)
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
    assert far['opacity'] == 1 and far['scene'] and far['depthTest']  # never faded; in the scene, ordered by depth
    names = {node['id']: node.get('name') for node in page.evaluate('window.metaform.graph().nodes') if node['t'] == 'el'}
    assert all(label['text'] == names[id] for id, label in labels.items() if id in names)  # whole, never cut off
    assert all(' '.join(label['lines']) == label['text'] for label in labels.values() if not label['hidden'])
    assert len(labels[long]['lines']) > 1, labels[long]               # a long name wraps at word breaks
    strong = [label for label in labels.values() if not label['under'] and not label['hidden']]
    for index, one in enumerate(strong):
        for two in strong[index + 1:]:
            assert (one['right'] <= two['left'] or two['right'] <= one['left'] or one['bottom'] <= two['top']
                    or two['bottom'] <= one['top']), (one, two)
    page.evaluate(f'window.metaform.hover3d("{kitchen}")')
    tip = page.locator('#tip3d')
    tip.wait_for(state='visible')
    assert 'kitchen timer' in tip.inner_text() and 'Counts down and rings.' in tip.inner_text()
    assert 'code.timer.kitchen' not in tip.inner_text()               # the address is the name read the other way
    # Rich, 2026-10-02: no subject rule; each ef is shown as written, where the relation was, with no receiver or
    # provider put before it.
    page.evaluate(f'window.metaform.hover3d("{alarm}")')
    page.wait_for_function('() => document.querySelector("#tip3d").textContent.includes("Plays a tone")')
    assert page.evaluate('[...document.querySelectorAll("#tip3d .why")].map(e => e.textContent)') == [
        'Plays a tone.']
    assert problems == []


@pytest.mark.req('VIEW-038')
@pytest.mark.req('VIEW-025')
def test_a_node_between_the_camera_and_a_label_hides_the_label(run, web, mapped, browser):
    """Rich, 2026-10-02: "The labels are in depth order but they are in front of the nodes". The alarm's label is
    read on the screen first with nothing in front of it, then with the cook's glass node set between the camera and
    it. With nothing in front, showing the labels changes those pixels; with the node in front, the label is behind
    the node and is seen only as the glass lets it through, blurred, so showing the labels hardly changes them; with
    the glass made clear, the label is seen through it."""
    from metaform.data import Store
    store = Store('proj')
    cook = store.element('exterior.cook').element_id
    alarm = store.element('code.alarm.audible').element_id
    started(run)
    page, problems, _ = opened(browser, web)
    page.emulate_media(reduced_motion='reduce')                       # nothing moves between two pictures
    page.reload()
    page.wait_for_function('() => window.metaform && window.metaform.loaded() && window.metaform.linkColors().length > 0')
    camera, target = {'x': 2000, 'y': 0, 'z': 300}, {'x': 2000, 'y': 0, 'z': 0}
    staged(page, {cook: (5000, 0, 0), alarm: (2000, 0, -150)}, (camera, target))

    def label_change():
        labels_shown(page, True)
        page.wait_for_timeout(600)
        label = next(label for label in page.evaluate('window.metaform.labels3d()') if label['id'] == alarm)
        inner = {'left': label['left'] + 3, 'right': label['right'] - 3, 'top': label['top'] + 2,
                 'bottom': label['bottom'] - 2}
        shown = page.screenshot()
        labels_shown(page, False)
        page.wait_for_timeout(600)
        return label, inner, changed(page, shown, page.screenshot(), inner)

    label, inner, open_change = label_change()
    text = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--text").trim()')
    assert not label['under'] and label['color'] == text, label          # its own color, with nothing in front
    assert inner['right'] - inner['left'] > 20 and inner['bottom'] - inner['top'] > 6, label
    assert open_change[1] > 60, open_change                           # the label is drawn there
    page.evaluate(f'window.metaform.pin3d("{cook}", 2000, 0, 250)')   # between the camera and the alarm's label
    page.wait_for_timeout(800)
    front = page.evaluate(f'window.metaform.screen3d("{cook}")')
    for x in (inner['left'], inner['right']):
        for y in (inner['top'], inner['bottom']):
            assert math.dist((x, y), (front['x'], front['y'])) < front['r'] * 0.9, (front, inner)  # all of it behind
    covered, _, covered_change = label_change()
    assert covered_change[1] < open_change[1] / 3, (covered_change, open_change)  # hidden behind the node
    # Rich, 2026-10-02, at code.gui.web: "Drop the quieter color: a covered label keeps its own color, and whatever
    # is in front hides it by depth or shows it through the glass"
    assert covered['under'] and covered['color'] == label['color'], (covered, label)
    # with the glass made clear, letting all the light through, with no frosting, absorption, bending or light of its
    # own, the label behind the node is seen through it: the glass shows what is behind it, labels included
    page.evaluate('window.metaform.glass(true, {transmission: 1, emissiveIntensity: 0, clearcoat: 0, roughness: 0, '
                  'thickness: 0, attenuationDistance: Infinity, anisotropicBlur: 0, chromaticAberration: 0, distortion: 0})')
    page.wait_for_timeout(600)
    _, _, clear_change = label_change()
    assert clear_change[1] > open_change[1] / 3, (clear_change, open_change)
    assert problems == []


def in_depth_order(page, camera, target):
    """Every pair of labels in the 3D map, VIEW-038: the label of the node nearer the camera is drawn over the farther
    one's, and a label whose box falls on a nearer one's goes under it. Nothing is ranked over depth. Nearer is
    measured along the camera's view, from the camera toward what it looks at, as the depth buffer measures it."""
    labels = [label for label in page.evaluate('window.metaform.labels3d()') if not label['hidden']]
    # the rank is the page's own count; what draws a nearer label over a farther one, and a nearer node over a label,
    # is the depth buffer, so every label is in the scene, tested against it and written into it
    for label in labels:
        assert label['scene'] and label['depthTest'] and label['depthWrite'], label
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
@pytest.mark.parametrize('case', ['missing', 'selected', 'neighbor', 'broken', 'question', 'reach'])
def test_a_record_that_lights_nothing_leaves_the_label_in_depth_order(run, web, mapped, browser, case):
    """Rich, 2026-10-02: "Text labels need to be depth sorted"; "Not if somethning is in front of it of something is
    blinking you spin the map the more nodes there are the worse it looks its literally a terrible thing to not
    observe depth ordering"; on keeping the selected node and its neighbors on top: "How is that physically possible
    to happen I would rather have a true navigation surface... its not a benefit, it surfaces as a bug and bad
    design". The alarm stands behind the cook, who carries nothing, and is in turn: a missing record, which lights
    nothing; the selected node; a neighbor of the selected node; broken, blinking; asked a question, glowing; reached by
    a property. Each time the cook's label is drawn over the alarm's, and the alarm's goes under it where they meet."""
    from metaform.data import Node, Store
    store = Store('proj')
    cook = store.element('exterior.cook').element_id
    alarm = store.element('code.alarm.audible').element_id
    display = store.element('code.timer.kitchen.display').element_id
    store.add_element('notes', 'code.bell', name_length=1)
    bell = store.element('code.bell').element_id
    store.add_join('notes', 'code.bell', 'code.alarm.audible', purpose='Ring.', ef='Rings the bell.')
    if case == 'missing':
        store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='a second tone')
    elif case == 'broken':
        store.add_work(Node('element', 'code.alarm.audible'), 'broken', task='a cracked tone')
    elif case == 'question':
        store.ask(Node('element', 'code.alarm.audible'), 'Still wanted?')
    elif case == 'reach':
        key = 'r:' + store.add_property('notes', 'code.alarm.audible', 'rings at 2 kHz').property_id
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
    if case != 'missing':  # a part not built is drawn as text, its label set higher, clear of the cook's
        assert far['under'], (near, far)                              # on the nearer label, so under it
    in_depth_order(page, camera, target)
    assert problems == []


FAKE_AGENT = Path(__file__).parents[2] / 'dispatch' / 'tests' / 'fake_agent.py'  # dispatch's ACP agent, no model
AGENT_GLYPHS = ('jelly', 'gearling', 'kite', 'moth', 'drone', 'snail', 'crystal', 'wisp', 'comet', 'beetle', 'slime',
                'plane', 'puffer', 'owl', 'cubebot', 'mushroom')


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
def test_the_dispatch_writes_are_taken_only_from_the_page_and_say_what_to_do_next(run, web, mapped):
    import re
    from metaform.data import Node, Store
    work = Store('proj').add_work(Node('element', 'code.alarm.audible'), 'missing', task='Write notes.txt').work_id
    started(run)
    own, as_json = f'http://127.0.0.1:{web}', {'Content-Type': 'application/json'}
    given = {'/api/dispatch-start': {'work_id': work, 'agent': 'claude'},
             '/api/dispatch-message': {'work_id': work, 'text': 'also run the tests'},
             '/api/dispatch-stop': {'work_id': work}}
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
    assert status == 400 and 'claude, codex, gemini' in said['error'], said
    for path in ('/api/dispatch-message', '/api/dispatch-stop'):
        status, said = api(web, path, method='POST', headers={**as_json, 'Origin': own},
                           body=json.dumps({'project': 'proj', **given[path]}))
        assert status == 400 and said['next'] == f'metaform dispatch start {work} <agent>', (path, said)
    assert Store('proj').ticket(work).work.taken is None
    # every figure's flat icon is served with the page, VIEW-003
    names = re.search(r'export const GLYPHS = \[(.*?)\]', (Path(__file__).parents[1] / 'page' / 'agents3d.js')
                      .read_text(encoding='utf-8'), re.DOTALL).group(1)
    assert tuple(re.findall(r"'(\w+)'", names)) == AGENT_GLYPHS
    for name in AGENT_GLYPHS:
        status, body, headers = request(web, f'/page/agent-glyphs/{name}.svg')
        assert status == 200 and headers['Content-Type'] == 'image/svg+xml' and body.startswith('<svg'), name


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('VIEW-003')
def test_an_agent_is_started_on_a_ticket_followed_messaged_and_stopped_from_the_page(run, web, mapped, browser,
                                                                                     tmp_path, watch_dispatch):
    """Rich, 2026-10-02: "agents complete their work, memory server created, acp controls implemented"; "Maybe
    onscreen if it had a box someplace that said agent deployed and showed the agent icon ... and the harness"; "This
    little box is supposed to tell you that not the color"; "or whatever the agent is"; "every other system I know
    allows monitoring and sending messages to agents this way you can see if they are doing the task right"."""
    import sys
    from metaform.data import Item, Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    work = store.add_work(Node('element', 'code.alarm.audible'), 'missing', task='Write notes.txt').work_id
    other = store.add_work(Node('element', 'exterior.cook'), 'enhancement', task='Name the cook').work_id
    store.ask(Node('element', 'code.alarm.audible'), 'Is the tone too high?')  # a question of no agent, at the same node
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE_AGENT}"', cwd=mapped)
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask', 'FAKE_ACP_WORK': work})
    page, problems, remote = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    # started from the node's menu, choosing the agent
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.agent') == 'Start agent 1'
    page.click('#menu button.agent')
    page.wait_for_selector('#dispatch:not([hidden])')
    assert page.eval_on_selector_all('#dispatch select.agent option', 'found => found.map(one => [one.value, one.textContent])') \
        == [['claude', 'Claude Code'], ['codex', 'Codex'], ['gemini', 'Gemini CLI']]
    assert page.eval_on_selector_all('#dispatch .ticket', 'found => found.map(one => one.dataset.id)') == [work]
    page.select_option('#dispatch select.agent', 'codex')               # not the first, so the choice is what starts
    page.click(f'#dispatch .ticket[data-id="{work}"] button.start')
    # the agent deployed box: the agent's flat icon, the same character as its 3D figure, and in words what it is
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=60000)
    assert page.is_hidden('#dispatch')
    shown = page.inner_text('#agents')
    assert 'Agent deployed' in shown and 'Codex' in shown and 'on audible alarm' in shown, shown
    assert Store('proj').ticket(work).work.taken_by == 'codex fake-session-1'
    page.evaluate(f'window.metaform.menu("{alarm}")')                   # a taken ticket waits for no agent
    page.wait_for_selector('#menu:not([hidden])')
    assert page.text_content('#menu button.agent') == 'Start agent 0' and page.is_disabled('#menu button.agent')
    page.keyboard.press('Escape')
    icon = page.get_attribute('#agents .agent img', 'src')
    glyph = icon.rsplit('/', 1)[-1].removesuffix('.svg')
    assert icon == f'/page/agent-glyphs/{glyph}.svg' and glyph in AGENT_GLYPHS, icon
    page.wait_for_function('() => document.querySelector("#agents .agent img").naturalWidth > 0')
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{work}")', timeout=30000)
    assert next(one for one in page.evaluate('window.metaform.figures()') if one['work_id'] == work)['glyph'] == glyph
    # the same character on every load of the page, Rich 2026-10-03: it comes from the ticket, never from chance
    reloaded, _, _ = opened(browser, web)
    reloaded.wait_for_selector('#agents:not([hidden]) .agent', timeout=30000)
    assert reloaded.get_attribute('#agents .agent img', 'src') == icon
    # its live activity, from the dispatch layer at the ticket's node, and its permission question
    page.click('#agents .agent')
    page.wait_for_selector('#agent:not([hidden])')
    page.wait_for_function('() => document.querySelector("#agent .activity").innerText.includes("Hello from fake")',
                           timeout=30000)
    activity = page.inner_text('#agent .activity')
    assert -1 < activity.find('Thinking it over') < activity.find('Hello from fake') < activity.find('Read file (completed)'), \
        activity                                                       # in the order written
    page.wait_for_selector('#agent button.suggestion', timeout=30000)
    assert page.eval_on_selector_all('#agent button.suggestion', 'found => found.map(one => one.textContent)') \
        == ['Allow once', 'Reject']
    assert 'Is the tone too high?' not in page.inner_text('#agent .asked')  # only the questions this agent asked
    page.click('#agent button.suggestion >> nth=0')                   # answered as every question is
    assert logged_by(log, lambda entry: 'permission' in entry)['permission']['outcome'] \
        == {'outcome': 'selected', 'optionId': 'allow'}
    # a message to it, kept while it is written as the map changes, VIEW-018
    page.fill('#agent textarea.say', 'also run the tests')
    page.wait_for_function('() => document.querySelector("#messages").textContent.trim() === "Messages 1"')
    before = page.evaluate('window.metaform.changes()')
    run('map', 'ask', 'element:code.timer.kitchen', 'Is one second right?', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {before}', timeout=10000)
    assert page.inner_text('#messages').strip() == 'Messages 2'
    assert page.is_visible('#agent') and page.input_value('#agent textarea.say') == 'also run the tests'
    page.click('#agent button.send')
    logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt'
              and entry['message']['params']['prompt'][0].get('text') == 'also run the tests')
    page.wait_for_function('() => document.querySelector("#agent textarea.say").value === ""')  # sent, so cleared
    # a chat: the person's message in the thread with what the agent says, thinks and runs, newest in view, and the
    # window resized as the person wants, Rich 2026-10-03
    page.wait_for_function('() => [...document.querySelectorAll("#agent .activity .you")]'
                           '.some(one => one.innerText.includes("also run the tests"))', timeout=30000)
    kinds = page.eval_on_selector_all('#agent .activity li', 'found => found.map(one => one.className)')
    assert {'said', 'thought', 'tool', 'you'} <= set(kinds), kinds
    assert page.evaluate('''() => { const list = document.querySelector("#agent .activity");
        return list.scrollTop + list.clientHeight >= list.scrollHeight - 2; }''')
    assert page.evaluate('getComputedStyle(document.querySelector("#agent")).resize') == 'both'
    # stopping it
    page.click('#agent button.stop')
    # the agents key lists only agents at work, so a stopped one leaves it; its log is in the node's work history
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=30000)
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert [row['state'] for row in tx.rows('sessions', limit=0).results] == ['ended']
    assert 'dispatch' not in [layer.name for layer in Store('proj').layers(limit=0).results]  # nothing on the map
    # the node's work history: why an agent was sent here, each dispatch of its tickets, and its log, Rich 2026-10-03
    page.click('#agent .close')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    page.click('#menu button.history')
    page.wait_for_selector('#float:not([hidden]) .dispatch')
    assert 'Codex' in page.inner_text('#float .dispatch') and 'ended' in page.inner_text('#float .dispatch')
    page.click('#float .dispatch button.log')
    page.wait_for_selector('#agent:not([hidden])')
    page.wait_for_function('() => document.querySelector("#agent .activity").innerText.includes("Hello from fake")')
    page.click('#agent .close')
    page.click('#float .close')
    # started from the board: a ticket not taken has the control, one taken has not
    page.click('#boardBtn')
    page.wait_for_selector(f'#board .card[data-id="{other}"]')
    # the stopped agent gave its ticket back, so it waits for the next agent and has the control again, BASE-052
    assert Store('proj').ticket(work).work.taken is None
    assert page.locator(f'#board .card[data-id="{work}"] button.start').count() == 1
    page.click(f'#board .card[data-id="{other}"] button.start')
    page.wait_for_selector('#dispatch:not([hidden])')
    assert page.eval_on_selector_all('#dispatch .ticket', 'found => found.map(one => one.dataset.id)') == [other]
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-039')
@pytest.mark.req('VIEW-011')
@pytest.mark.req('BASE-052')
def test_the_admin_sets_how_agent_prompts_are_answered_and_the_choice_is_kept_in_the_settings(run, web, mapped, browser):
    """Rich, 2026-10-03: agent permissions in Administration, changed on the fly; the default is whatever the
    administrator sets, kept in the settings and read from them, so it never reverts on a refresh."""
    from metaform import loader, settings
    run('enable', 'dispatch')
    loader.get('dispatch')
    started(run)
    page, problems, remote = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    page.click('#adminBtn')
    page.click('#promptsBtn')
    page.wait_for_selector('#prompts:not([hidden])')
    assert page.eval_on_selector_all('#prompts input[name=prompts]', 'found => found.map(one => one.value)') == [
        'approve-all', 'approve-reads', 'ask_all']
    assert page.eval_on_selector('#prompts input[name=prompts]:checked', 'one => one.value') == 'ask_all'
    page.check('#prompts input[value="approve-reads"]')
    page.wait_for_function('() => document.querySelector("#prompts .saved").textContent.includes("approve-reads")')
    assert settings.value('dispatch_prompts', mapped) == 'approve-reads'   # in the settings, as metaform set keeps it
    again, again_problems, _ = opened(browser, web)
    again.wait_for_function('() => window.metaform.loaded()')
    again.click('#adminBtn')
    again.click('#promptsBtn')
    again.wait_for_selector('#prompts:not([hidden])')
    assert again.eval_on_selector('#prompts input[name=prompts]:checked', 'one => one.value') == 'approve-reads'
    own, as_json = f'http://127.0.0.1:{web}', {'Content-Type': 'application/json'}
    assert request(web, '/api/dispatch-prompts', method='POST', headers={**as_json, 'Origin': 'http://rebound.example'},
                   body=json.dumps({'project': 'proj', 'value': 'approve-all'}))[0] == 403
    status, said = api(web, '/api/dispatch-prompts', method='POST', headers={**as_json, 'Origin': own},
                       body=json.dumps({'project': 'proj', 'value': 'everything'}))
    assert status == 400 and settings.value('dispatch_prompts', mapped) == 'approve-reads', said
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
    """Rich, 2026-10-02: "The user can show the memories in the graph, and manage them memories can be fricking poison
    to a project", and "the memory chains can just show what they were attached to, like through an orphaned menu".
    The page reads the whole graph with whether each join's memory shows at its node in the page's layers, the
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
        {'name': 'drift', 'entityType': 'behavior', 'observations': ['Drifts under load.']}]}
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
    """Rich, 2026-10-02: "Allow one single note not a list, limit its characters to 2048, make it so you can edit the
    note and so can the user". The page's note is the node's one note, written in place as the user's."""
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
    """Rich, 2026-10-02: memory "shows as a layer in the gui called memory", "The user can show the memories in the
    graph, and manage them memories can be fricking poison to a project", and "the memory chains can just show what
    they were attached to, like through an orphaned menu"."""
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
    page.click('#p-object .join:has-text("kitchen timer") button.unjoin')
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
    made = [store.add_work(Node('element', 'code.alarm.audible'), 'missing', task=f'part {n}').work_id for n in range(3)]
    started(run)
    refused, _ = api(web, '/api/distribute', method='POST', body=json.dumps({'project': 'proj', 'agents': 2}),
                     headers={'Content-Type': 'application/json', 'Origin': 'http://evil.example'})
    assert refused == 403 and glyph_held(run, mapped, made[0]) is None
    assert distributed(web, 'two')[0] == 400 and distributed(web, 0)[0] == 400 and distributed(web, 17)[0] == 400
    status, body = distributed(web, 2)
    assert status == 200, body
    # the fixture's own open tickets come first; every one not taken or done is given a glyph, in turn
    given = [(one['work_id'], glyph_of(one)) for one in body['results']]
    assert [glyph for _, glyph in given] == [GIVEN[place % 2] for place in range(len(given))]
    assert set(made) <= {work_id for work_id, _ in given}
    assert all(glyph_held(run, mapped, work_id) == glyph for work_id, glyph in given)


@pytest.mark.req('VIEW-040')
def test_the_page_distributes_and_reads_glyphs_on_the_metaform_it_chose_and_shows_none_with_map_off(run, web, mapped):
    """VIEW-040: the work read adds the glyphs and `/api/distribute` runs `map work op=distribute`, both on the
    metaform the page chose; with the map module not on the surface the board shows no glyphs."""
    from metaform.data import Node, Store
    from metaform.modules.map import AGENT_GLYPHS as GIVEN
    chosen = Store('proj').add_metaform('other', activate=False).metaform_id
    other = Store('proj', metaform=chosen)
    other.add_element(None, 'code', name_length=1, name='code', role='DE')
    made = [other.add_work(Node('element', 'code'), 'missing', task=f'part {n}').work_id for n in range(2)]
    active = {one['work_id'] for one in plain(Store('proj').work(limit=0))['results']}
    started(run)
    status, body = api(web, '/api/distribute', method='POST', headers=own_write(web),
                       body=json.dumps({'project': 'proj', 'metaform': chosen, 'agents': 2}))
    assert status == 200, body
    assert [(one['work_id'], glyph_of(one)) for one in body['results']] == list(zip(made, GIVEN[:2]))
    shown = api(web, f'/api/work?project=proj&metaform={chosen}')[1]['results']
    assert {one['work_id']: glyph_of(one) for one in shown} == dict(zip(made, GIVEN[:2]))
    assert all(glyph_of(one) is None for one in api(web, '/api/work?project=proj')[1]['results']
               if one['work_id'] in active)                            # the active metaform's tickets were not dealt
    run('disable', 'map', cwd=mapped)                                  # after the server started
    status, body = api(web, f'/api/work?project=proj&metaform={chosen}')
    assert status == 200 and [one['work_id'] for one in body['results']] == made
    assert all('map' not in one for one in body['results'])


@pytest.mark.req('VIEW-040')
@pytest.mark.req('VIEW-037')
@pytest.mark.req('VIEW-039')
def test_each_card_shows_its_agents_glyph_and_the_same_glyph_is_its_figure_and_its_icon_under_agent_deployed(
        run, web, mapped, browser):
    """Rich, 2026-10-03: "Show tiny agent glyphs on kanban, use thaty glyph consistently, using glyphs on tasks can
    signify 1 single agent meaning perform these tasks one at a timne since they all have the same glyph, add a button
    to distribute work over N agents hitting it will evenly assign work using N glyphs"."""
    from metaform.data import Node, Store
    store = Store('proj')
    run('enable', 'dispatch')
    tickets = [store.add_work(Node('element', 'code.alarm.audible'), 'missing', task=f'part {n}').work_id
               for n in range(4)]
    early = store.add_work(Node('element', 'exterior.cook'), 'enhancement', task='already at work').work_id
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
    page.wait_for_function(f'() => window.metaform.figures().some(one => one.work_id === "{tickets[1]}")', timeout=20000)
    assert figure_of(tickets[1]) == lanes[1]
    page.wait_for_selector(f'#agents .agent[data-id="{tickets[1]}"]', timeout=10000)
    assert page.get_attribute(f'#agents .agent[data-id="{tickets[1]}"] img', 'src') == src
    assert glyph(tickets[1]) == lanes[1]
    page.click('#board .close')
    page.click(f'#agents .agent[data-id="{tickets[1]}"]')                 # and in the agent's window, VIEW-039
    page.wait_for_selector('#agent:not([hidden])')
    assert page.get_attribute('#agent .icon', 'src') == src
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
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone')
    store.take_work(worked.work_id, by='claude')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    reads = []
    page.on('request', lambda sent: reads.append(sent.url))
    live_session(worked.work_id)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('lines', {'session_id': f's-{worked.work_id}', 'name': 'said-1', 'work_id': worked.work_id,
                            'kind': 'agent_message_chunk', 'text': 'Hello from the line', 'seq': 1})
    payload = {'project': 'proj', 'metaform_id': store.active_metaform().metaform_id, 'tables': 'dispatch'}
    relay.deliver('map.changed', payload)  # as the runner's process announces it
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=10000)
    page.click('#agents .agent')
    page.wait_for_function('() => document.querySelector("#agent .activity").innerText.includes("Hello from the line")',
                           timeout=10000)
    with Store('proj', module='dispatch').tables() as tx:
        tx.insert('lines', {'session_id': f's-{worked.work_id}', 'name': 'said-2', 'work_id': worked.work_id,
                            'kind': 'agent_message_chunk', 'text': 'and a second line', 'seq': 2})
    relay.deliver('map.changed', payload)  # as the runner's process announces it
    page.wait_for_function('() => document.querySelector("#agent .activity").innerText.includes("a second line")',
                           timeout=10000)
    assert not [url for url in reads if '/api/graph' in url or '/api/memory-graph' in url], reads
    sessions = [url for url in reads if '/api/dispatch-sessions' in url]
    assert sessions and all('thread=false' in url or f'id={worked.work_id}' in url for url in sessions), sessions
    run('map', 'work', 'op=done', f'id={worked.work_id}', 'resolution=quieter', cwd=mapped)  # a write to the map
    page.wait_for_function('() => document.querySelector("#agents").hidden', timeout=15000)
    assert [url for url in reads if '/api/graph' in url]
    assert problems == []


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
    alarm = Store('proj').element('code.alarm.audible').element_id
    layouts = page.evaluate('window.metaform.layouts()')
    drawn = page.evaluate('window.metaform.drawn()')
    changes = page.evaluate('window.metaform.changes()')
    run('map', 'work', 'op=add', 'node=code.alarm.audible', 'condition=flawed', 'note=too loud', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.changes() > {changes} && window.metaform.loaded()', timeout=15000)
    assert page.evaluate(f'window.metaform.drawnWork("{alarm}")') == 1   # the ticket's light, on the node drawn
    assert page.evaluate('window.metaform.drawn()') == drawn
    assert page.evaluate('window.metaform.layouts()') == layouts
    run('hello', 'greet', 'world', cwd=mapped)
    page.click('#layersBtn')
    page.wait_for_selector('#layerlist input[data-layer="hello.greetings"]', timeout=5000)
    set_layer(page, 'hello.greetings', True)
    page.wait_for_function(f'() => window.metaform.drawn().nodes > {drawn["nodes"]}', timeout=10000)
    assert page.evaluate('window.metaform.layouts()') > layouts           # a new node is laid out
    assert problems == []


@pytest.mark.req('VIEW-008')
def test_down_goes_to_the_child_drawn_closest_below_and_not_to_the_first(run, web, mapped, browser):
    """With seven nodes below, Down goes down the edge to the one drawn nearest under the selected node, about the
    middle one, so the walk does not swing to the far left; Left and Right still go across the same row."""
    from metaform.data import Store
    store = Store('proj')
    for n in range(1, 8):
        store.add_element('notes', f'code.alarm.audible.tone{n}', name_length=1)
        store.add_join('notes', 'code.alarm.audible', f'code.alarm.audible.tone{n}', purpose=f'Ring tone {n}.',
                       ef=f'Plays tone {n}.')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()', timeout=15000)
    _, at, _ = keys_of(web)
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
    _, at, _ = keys_of(web)
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
    from metaform.data import Store
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
    _, at, _ = keys_of(web)
    tone, pitch, cover, latch = (at[a] for a in ('code.alarm.audible.tone1', 'code.alarm.audible.tone1.pitch',
                                                 'code.panel.cover', 'code.panel.cover.latch'))
    depth = 'y' if page.evaluate('window.metaform.vertical()') else 'x'
    assert abs(page.evaluate(f'window.metaform.at2d("{pitch}")')[depth]
               - page.evaluate(f'window.metaform.at2d("{latch}")')[depth]) < 2   # drawn on one row
    for key in ('ArrowRight', 'ArrowLeft'):
        page.evaluate(f'window.metaform.select("{tone}")')
        page.keyboard.press('ArrowDown')
        assert page.evaluate('window.metaform.selected()') == pitch
        page.keyboard.press(key)
        if page.evaluate('window.metaform.selected()') == latch:
            break
    else:
        raise AssertionError('the latch drawn beside the pitch was not reached by Left or Right')
    page.keyboard.press('ArrowUp')
    assert page.evaluate('window.metaform.selected()') == cover
    assert problems == []


@pytest.mark.req('VIEW-032')
@pytest.mark.req('VIEW-039')
def test_a_task_can_be_created_and_started_in_acp_from_its_editor(run, web, mapped, browser, tmp_path, watch_dispatch):
    import sys

    from metaform.data import Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    log = tmp_path / 'fake.jsonl'
    run('enable', 'dispatch')
    run('set', '--dispatch-codex', f'"{sys.executable}" "{FAKE_AGENT}"', cwd=mapped)
    run('web', '--json', env={'FAKE_ACP_LOG': str(log), 'FAKE_ACP_MODE': 'ask'})
    page, problems, _ = opened(browser, web)
    watch_dispatch(page)
    page.wait_for_function('() => window.metaform.loaded()')
    page.evaluate(f'window.metaform.task("{alarm}")')
    page.fill('#task .text', 'Inspect the alarm and report what you find.')
    page.check('#task .start-agent')
    page.select_option('#task select.agent', 'codex')
    page.click('#task .put')
    page.wait_for_selector('#agents:not([hidden]) .agent', timeout=30000)
    ticket = next(work for work in store.work(limit=0).results
                  if work.task == 'Inspect the alarm and report what you find.')
    assert ticket.taken_by.startswith('codex ') and ticket.address == 'code.alarm.audible'
    told = logged_by(log, lambda entry: entry.get('message', {}).get('method') == 'session/prompt')
    assert ticket.work_id in told['message']['params']['prompt'][0]['text']
    assert page.is_hidden('#task')
    run('dispatch', 'stop', ticket.work_id, cwd=mapped)
    assert problems == []
    # A task can still just be queued; failure to start keeps the new ticket for another attempt.
    run('set', '--dispatch-codex', 'metaform-nonexistent-acp-adapter', cwd=mapped)
    page.evaluate(f'window.metaform.task("{alarm}")')
    assert not page.is_checked('#task .start-agent')
    page.fill('#task .text', 'Keep this task if the adapter cannot start.')
    page.check('#task .start-agent')
    with page.expect_response(lambda response: '/api/dispatch-start' in response.url) as failed:
        page.click('#task .put')
    assert failed.value.status == 400 and 'not found' in failed.value.json()['error']
    page.wait_for_function('() => document.querySelector("#task").hidden')
    kept = next(work for work in store.work(limit=0).results
                if work.task == 'Keep this task if the adapter cannot start.')
    assert kept.taken is None and kept.done is None
    assert problems == ['Failed to load resource: the server responded with a status of 400 (Bad Request)']
