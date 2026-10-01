"""The web module: one web GUI server per Metaform home, started and stopped from any folder, VIEW-001, VIEW-002, VIEW-015."""
from __future__ import annotations

import http.client
import json
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
                               ef='Counts down and rings.', perspective='Function', relation='The timer tells the cook.',
                               observation='One countdown per dish.')
        store.add_join(intake.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       ef='Plays a tone.', perspective='Encounter', relation='The alarm rings for the timer.',
                       observation='A piezo.')
        store.add_subtype(intake.name, outer.join_id, 'code.loop.tick', ef='Advances each countdown.',
                          perspective='Function', relation='The tick loop drives the timer.', observation='One tick a second.',
                          name='one-second tick', name_length=2, role='SE')
    store.add_work(Node('element', 'code.timer.kitchen'), 'broken', note='drifts', task='hold the tick to one second')
    for name in KNOWLEDGE:
        store.layer(name, 'test', f'What {name} says.', mutable=True, hideable=True, provenance=PROVENANCE)
    store.add_element('notes', 'code.timer.kitchen.display', name_length=1)
    store.add_join('notes', 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='Show the time left.',
                   ef='Reports the time left.', relation='The timer feeds the display.', observation='LCD')
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
    started(run)
    stores = sorted((home / 'projects').rglob('*.sqlite3')) + [home / 'metaform.sqlite3']
    before = [path.read_bytes() for path in stores]
    shown = run('config', '--show', '--json', cwd=mapped).stdout
    for path in ('/api/projects', '/api/metaforms?project=proj', '/api/roots?project=proj',
                 '/api/graph?project=proj&limit=0', '/api/graph?project=proj&raw=true&layers=notes',
                 '/api/children?project=proj&address=code', '/api/node?project=proj&target=element:code.timer.kitchen',
                 '/api/joins?project=proj&element=code.timer.kitchen', '/api/layers?project=proj',
                 '/api/work?project=proj', '/api/search?project=proj&text=loop',
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


def opened(browser, port):
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
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
    page.wait_for_function('([count]) => document.querySelectorAll("#labels3d span:not([hidden])").length === count',
                           arg=[len(elements)])
    names = {entry['element'].get('short_name') or entry['element']['address'] for entry in expected['elements']}
    assert set(page.evaluate('[...document.querySelectorAll("#labels3d span")].map(s => s.textContent)')) == names
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
    join = Store('proj').joins('code.timer.kitchen').results[0].join_id
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    colors = lambda shown: sorted((link['k'], link['color'].lower()) for link in
                                  shown.evaluate('window.metaform.linkColors()') if link['join'] == join)
    before = colors(page)
    assert before
    run('map', 'knowledge', 'op=refine', f'id={join}', 'purpose=Ring when the countdown ends.', 'reason=wording',
        cwd=mapped)
    run('map', 'knowledge', 'op=refine', f'id={join}', 'ef=Plays a loud tone.', 'reason=louder', cwd=mapped)
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
                           timeout=12000)
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
    page.wait_for_function(f'() => window.metaform.look("{ids["exterior.cook"]}").work[0] === "in-progress"', timeout=5000)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").text3d === true', timeout=5000)
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
                           timeout=12000)
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
    # Sampled until the wave has been everywhere it goes; a slow machine draws fewer frames, and the wave keeps its
    # order whatever the speed.
    seen = page.evaluate("""async count => { const seen = [], lit = new Set();
        for (let at = 0; at < 240 && lit.size < count; at++) {
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
        return ['--broken', '--missing', '--function', '--encounter', '--signal', '--de', '--intake', '--memory',
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
def test_each_encounter_is_colored_by_its_ef_in_both_views_and_named_in_the_legend_and_panel(run, web, mapped,
                                                                                           browser):
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    color = {name: page.evaluate(f'getComputedStyle(document.documentElement).getPropertyValue("--{name}").trim()')
             for name in ('function', 'encounter', 'k1')}
    assert color['function'] != color['encounter']
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    drawn = page.evaluate('window.metaform.linkColors()')
    for join in expected['joins']:
        encounter = next(link for link in drawn if link['join'] == join['join_id'] and link['k'] == 'encounter')
        if join['perspective']:
            assert encounter['color'] == color[join['perspective'].lower()]
        else:  # a knowledge join with no word keeps its layer's color, never one of the two
            assert join['layer'] == 'notes' and encounter['color'] == color['k1']
        for subtype in join['subtypes']:
            link = next(link for link in drawn if link['target'] == 's:' + subtype['join_id'])
            assert link['color'] == color[subtype['perspective'].lower()]
    assert sorted(join['perspective'] or '' for join in expected['joins']) == ['', 'Encounter', 'Function']
    assert page.locator('#map2d svg .edgePaths path.perspective-function').count() == 1
    assert page.locator('#map2d svg .edgePaths path.perspective-encounter').count() == 1
    legend = page.inner_text('#legend')
    assert 'Function · the encounter of a functionality' in legend
    assert 'Encounter · the functionality of the encounter' in legend
    kitchen = next(entry['element']['element_id'] for entry in expected['elements']
                   if entry['element']['address'] == 'code.timer.kitchen')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    assert sorted(page.evaluate('[...document.querySelectorAll("#p-object .join .perspective")].map(e => e.textContent)')) \
        == ['Encounter', 'Function', 'Function']
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
    page.wait_for_timeout(900)  # the camera settles on it
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


def click_node(page, title):
    """A real click on the 2D node whose full text is this title."""
    box = box_of(page, title)
    assert box, title
    view = page.evaluate("""(() => { const box = document.querySelector('#viewport').getBoundingClientRect();
        return {x: box.left, y: box.top, w: box.width, h: box.height}; })()""")
    x, y = box['x'] + box['w'] / 2, box['y'] + box['h'] / 2
    if not (view['x'] <= x <= view['x'] + view['w'] and view['y'] <= y <= view['y'] + view['h']):
        page.evaluate('window.metaform.fit()')  # the view opens at a readable size, so a node may be outside it
        page.wait_for_timeout(900)
        box = box_of(page, title)
    page.mouse.click(box['x'] + box['w'] / 2, box['y'] + box['h'] / 2)


def inside(page):
    """The current level's node keys and the breadcrumb's words."""
    return page.evaluate('window.metaform.inside()'), page.inner_text('#crumbs') if page.is_visible('#crumbs') else ''


SAMPLE_2D = '''() => { window.samples = []; window.sampling = true;
    const tick = () => { const svg = document.querySelector("#map2d svg");
        if (svg) { const box = svg.viewBox.baseVal;
            window.samples.push({base: svg.dataset.base === "yes", o: Number(getComputedStyle(svg).opacity),
                                 w: box ? box.width : 0}); }
        if (window.sampling) requestAnimationFrame(tick); };
    requestAnimationFrame(tick); }'''


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
    page.wait_for_timeout(900)  # the selection's own camera move settles first
    page.evaluate(SAMPLE_2D)
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{cook}")')
    page.wait_for_timeout(900)
    going_in = page.evaluate('() => { window.sampling = false; return window.samples; }')
    base = [sample for sample in going_in if sample['base']]
    own = [sample for sample in going_in if not sample['base']]
    assert base and own
    assert min(sample['o'] for sample in base) < 0.5  # the map fades as the camera goes in
    assert base[-1]['w'] < base[0]['w'] * 0.8  # and the camera zooms into the node
    assert own[0]['o'] < 0.5 and own[-1]['o'] == 1  # the node's own graph fades in

    page.evaluate(SAMPLE_2D)
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.inside().length === 0')
    page.wait_for_timeout(1200)
    going_out = page.evaluate('() => { window.sampling = false; return window.samples; }')
    own = [sample for sample in going_out if not sample['base']]
    back = [sample for sample in going_out if sample['base']]
    assert own and back
    assert min(sample['o'] for sample in own) < 0.5  # the node's graph fades out
    assert back[0]['o'] < 0.5 and back[-1]['o'] == 1  # the map fades back in
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
    run('memory', 'add-observations', 'element:code.timer.kitchen', 'The countdown drifts under load.', cwd=mapped)
    run('memory', 'create-relations', 'element:code.timer.kitchen', 'drives', 'element:code.alarm.audible',
        cwd=mapped)
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
                           'window.metaform.inside().some(key => key.startsWith("i:"))')
    keys, crumbs = inside(page)
    assert [part.strip() for part in crumbs.split('›')] == ['map', 'kitchen timer']
    assert subtypes['code.loop.tick'] in keys and alarm in keys  # its subtype, and the node its memory relates to
    words = page.evaluate('document.querySelector("#map2d svg").textContent')
    assert 'keep the loop small' in words and 'The countdown drifts' in words and 'louder is better' not in words
    click_node(page, 'The countdown drifts under load.')  # selecting a memory shows it whole in the panel
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("under load.")')
    assert page.text_content('#p-object .eyebrow') == 'Memory'

    set_layer(page, 'notes', False)  # turning a layer off takes its group away inside
    page.keyboard.press('Escape')
    page.wait_for_function('() => !document.querySelector("#map2d svg").textContent.includes("keep the loop small")')
    assert 'The countdown drifts' in page.evaluate('document.querySelector("#map2d svg").textContent')

    click_node(page, 'drives')  # the memory relation; its panel links across to the alarm
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
    page.wait_for_timeout(900)  # the camera eases for 700 ms
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
    page.wait_for_function(f'() => window.metaform.look("{at["code.timer.kitchen"]}").material', timeout=10000)
    for theme in themes:
        page.select_option('#theme', theme)
        page.wait_for_timeout(250)
        for node in (at['code.timer.kitchen'], at['code.alarm.audible'], subtypes['code.loop.tick']):
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
                       ef='Does one thing.', relation='serves the timer')
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
        page.wait_for_timeout(900)  # the camera eases for 700 ms
        assert width() == pytest.approx(before, rel=0.01)
        shown = page.evaluate(f"""(() => {{ const view = document.querySelector('#viewport').getBoundingClientRect();
            const box = window.metaform.box2d("{at[address]}");
            return box.left >= view.left && box.right <= view.right && box.top >= view.top && box.bottom <= view.bottom; }})()""")
        assert shown, address
    page.evaluate('window.metaform.fit()')
    page.wait_for_timeout(900)
    assert width() > before * 1.5  # Fit shows the whole map
    whole = width()
    page.evaluate(f'window.metaform.select("{at["code.part.number3"]}")')
    page.wait_for_timeout(900)
    assert width() == pytest.approx(whole, rel=0.01)  # and a click leaves it there
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
                       purpose='Keep the timer working.', ef='Does one thing.', relation='serves the timer')
    started(run)
    page, problems, _ = opened(browser, web)
    _, at, _ = keys_of(web)
    kitchen = at['code.timer.kitchen']
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('Enter')
    page.wait_for_function('() => window.metaform.inside().length > 14')
    page.wait_for_timeout(900)
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
    page.wait_for_timeout(900)
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
    run('memory', 'add-observations', 'element:code.timer.kitchen', 'The countdown drifts under load.', cwd=mapped)
    run('memory', 'create-relations', 'element:code.timer.kitchen', 'drives', 'element:code.alarm.audible',
        cwd=mapped)
    run('memory', 'add-observations', f'join:{to_alarm}', 'The tone is too quiet.', cwd=mapped)
    run('memory', 'add-observations', f'join:{tick[2:]}', 'One tick can be lost.', cwd=mapped)
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
    assert sorted(memory) == ['One tick can be lost.', 'The countdown drifts under load.', 'The tone is too quiet.',
                              'drives']
    edges = {(link['source'], link['target'], link['k']) for link in graph['links']}
    assert {(kitchen, memory['The countdown drifts under load.'], 'item'), (kitchen, memory['drives'], 'item'),
            ('p:' + to_alarm, memory['The tone is too quiet.'], 'item'),
            (tick, memory['One tick can be lost.'], 'item')} <= edges  # from the element, the join and the subtype
    assert (memory['drives'], alarm, 'relation') in edges
    page.wait_for_function('() => window.metaform.drawn().nodes === window.metaform.graph().nodes.length')
    page.evaluate(f'window.metaform.click3d("{memory["The countdown drifts under load."]}")')
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
    page.wait_for_timeout(900)
    page.click('#fitBtn')
    page.wait_for_timeout(900)
    out = width()
    assert 'focused' not in page.get_attribute('#map2d', 'class')
    page.keyboard.press('Home')  # Home always shows the whole map
    page.wait_for_timeout(900)
    assert abs(width() - out) < 1
    page.click('#fitBtn')
    page.wait_for_timeout(900)
    zoomed = width()
    page.click('#fitBtn')
    page.wait_for_timeout(900)
    regular = width()
    assert regular > zoomed and out > zoomed
    page.click('#fitBtn')  # and round again to the whole map
    page.wait_for_timeout(900)
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
    kitchen = page.evaluate('(() => { const tag = [...document.querySelectorAll("#labels3d span")]'
                            '.find(span => span.textContent === "kitchen timer");'
                            ' return {x: parseFloat(tag.style.left), y: parseFloat(tag.style.top)}; })()')
    x, y = stage['x'] + kitchen['x'], stage['y'] + kitchen['y']
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
                                purpose='p', ef='f', relation='r', observation='o')
            if n < 10:
                big.add_subtype(layer.name, join.join_id, f'code.loop.s{n}', ef='f', relation='r',
                                observation='o', role='SE')
        # e0 receives from e1 above; e1 also receives from e0: two joins, two paths, no loop, MAP-002.
        big.add_join(layer.name, 'code.g1.e1', 'code.g0.e0', purpose='q', ef='g', relation='r', observation='o')
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
    made = json.loads(run('intake', 'join', 'stakeholder.cook.home', 'code.timer.kitchen', 'purpose=p', 'ef=f',
                          'perspective=Function', 'relation=r', 'verb=tells', 'observation=o', '--json', cwd=folder).stdout)
    page.wait_for_function('() => window.metaform.drawn().nodes === 3', timeout=1500)  # pushed, not waited for
    page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length === 2', timeout=15000)
    page.wait_for_timeout(300)  # the panel's reads for the selected node settle
    assert not [text for text in page.evaluate('window.toasts') if 'Nothing for' in text]  # an unfinished layer is no error
    run('intake', 'subtype', made['join_id'], 'code.loop.tick', 'ef=f', 'perspective=Function', 'relation=r',
        'verb=advances', 'observation=o', 'role=SE', cwd=folder)
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
@pytest.mark.req('VIEW-011')
def test_only_a_local_process_holding_the_servers_nonce_can_push_to_the_open_pages(run, web, mapped):
    import http.client
    import threading

    from metaform.modules.web import recorded
    started(run)
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
    refused = [request(web, '/api/notify', method='POST', body=body, headers={'Content-Type': 'application/json'}),
               request(web, '/api/notify', method='POST', body=body, headers={
                   'Content-Type': 'application/json', 'X-Metaform-Nonce': 'guessed'}),
               request(web, '/api/notify', method='POST', body=body, headers={
                   'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{web}'})]
    assert [answer[0] for answer in refused] == [403, 403, 403]
    listener.join(1)
    assert heard == []
    taken = request(web, '/api/notify', method='POST', body=body, headers={
        'Content-Type': 'application/json', 'X-Metaform-Nonce': recorded()['nonce']})
    assert taken[0] == 200
    listener.join(5)
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'layer': 'x'}}]


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
def test_notify_is_taken_only_from_this_machines_loopback_address():
    from metaform.modules.web.server import local
    assert [local(address) for address in ('127.0.0.1', '127.8.9.1', '::1', '::ffff:127.0.0.1')] == [True] * 4
    assert [local(address) for address in ('192.168.1.5', '10.0.0.1', '::ffff:10.0.0.1', 'fe80::1%eth0', '')] == [
        False] * 5


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
    run('memory', 'add-observations', 'element:code.timer.kitchen', 'Drifts under load.', cwd=mapped)
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
    run('memory', 'add-observations', f'join:{tick[2:]}', 'The tick is its own interrupt.', cwd=mapped)
    run('memory', 'add-observations', 'element:code.loop.tick', 'One loop serves every timer.', cwd=mapped)
    Store('proj').add_work(Node('element', 'code.loop.tick'), 'missing', task='count in milliseconds')
    page, problems, _ = opened(browser, web)
    set_layer(page, 'memory', True)
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.loaded() && '
                           'window.metaform.graph().nodes.filter(node => node.layer === "memory").length === 2')
    graph = page.evaluate('window.metaform.graph()')
    memory = {node['text']: node['id'] for node in graph['nodes'] if node['t'] == 'item' and node['layer'] == 'memory'}
    edges = {(link['source'], link['target'], link['k']) for link in graph['links']}
    assert {(tick, memory['The tick is its own interrupt.'], 'item'),
            (tick, memory['One loop serves every timer.'], 'item')} <= edges
    page.evaluate(f'window.metaform.select("{tick}")')
    page.wait_for_function('() => document.querySelector("#p-object").textContent.includes("count in milliseconds")')
    page.keyboard.press('Enter')
    page.wait_for_function(f'() => window.metaform.inside().includes("{tick}") && '
                           'window.metaform.inside().filter(key => key.startsWith("i:")).length === 2')
    words = page.evaluate('document.querySelector("#map2d svg").textContent')
    assert 'The tick is its own interrupt.' in words and 'One loop serves every timer.' in words
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
    run('memory', 'add-observations', 'element:code.timer.kitchen', 'Drifts under load.', cwd=mapped)
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
LINK_COLORS = ['--tree', '--function', '--encounter', *LAYER_COLORS]
LINES_2D = ['--node-line', '--edge', '--signal', '--intake', '--function', '--encounter', '--broken', '--exclude',
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
      const others = [...document.querySelectorAll('#map2d svg g.node:not(.sel):not(.near), #map2d .edgePaths path, #labels3d span')];
      return others.length > 0 && !others.some(node => !/work-/.test(node.getAttribute('class') || '') && faded(node)); }''')
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
        return box('#map2d').width * box('#map2d').height > 2 * box('#stage').width * box('#stage').height; }""")
    swapped = boxes()
    # each view is its bar and its map, and the two areas are what change hands
    assert swapped['#map2d'] == first['#big3d'] and swapped['#stage canvas'] == swapped['#stage']
    assert swapped['#big3d'][0] == first['#map2d'][0]
    assert page.locator('#map2d svg g.node').count() > 0 and page.is_visible('#fitBtn') and page.is_visible('#swapBtn')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.evaluate(f'window.metaform.click3d("{alarm}")')  # the small 3D map takes a click
    page.wait_for_function(f'() => window.metaform.selected() === "{alarm}"')
    page.evaluate('window.metaform.fit()')                # the whole map in view, so the kitchen's box is on screen
    page.wait_for_timeout(700)
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
    which comes 2.2 seconds after it has loaded."""
    page.wait_for_timeout(2600)
    page.click('#pauseBtn')
    for node, (x, y, z) in places.items():
        page.evaluate(f'window.metaform.pin3d("{node}", {x}, {y}, {z})')
    page.evaluate(f'window.metaform.view3d({json.dumps(camera[0])}, {json.dumps(camera[1])})')
    page.evaluate('document.querySelector("#labels3d").style.visibility = "hidden"')
    page.wait_for_timeout(800)


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
    texts = []
    for _ in range(4):
        texts.append(page.evaluate(f'window.metaform.look("{alarm}").text'))
        page.wait_for_timeout(900)
    assert len(set(texts)) >= 3                                     # the strings move all the time
    assert all(len(text) >= 32 and text.isalnum() and text.isascii() for text in texts)
    assert any(letter.islower() for letter in ''.join(texts)) and any(letter.isupper() for letter in ''.join(texts))
    assert any(letter.isdigit() for letter in ''.join(texts))
    assert page.evaluate(f'window.metaform.look("{alarm}").signal3d') == 0  # no signal has reached the alarm
    for _ in range(2):                                              # the cook's text glows, and the glow swells and fades
        page.wait_for_function(f'() => window.metaform.look("{cook}").signal3d > 0.6', timeout=10000)
        page.wait_for_function(f'() => window.metaform.look("{cook}").signal3d < 0.2', timeout=10000)
    question = page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--question").trim().toLowerCase()')
    page.wait_for_function(f'() => window.metaform.look("{cook}").signal3d > 0.5', timeout=4000)
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
    page.evaluate('window.metaform.zoom3d(0.2)')                      # far in, so the whole map is no longer in view
    page.wait_for_timeout(300)
    near = page.evaluate('window.metaform.away3d()')
    page.click('#fit3dBtn')
    page.wait_for_function(f'() => window.metaform.away3d() > {near} * 1.5', timeout=5000)
    # Rich, 2026-09-29: the Fit on the right reacted to the one on the left, and only zoomed out. Each Fit moves its
    # own map, and the 3D map's goes between the whole map and close on the selected node.
    page.wait_for_timeout(900)
    whole, chart = page.evaluate('window.metaform.away3d()'), page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")')
    page.click('#fitBtn')                                             # the 2D map's Fit
    page.wait_for_timeout(900)
    assert abs(page.evaluate('window.metaform.away3d()') - whole) < 1  # the 3D map did not move
    assert page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")') != chart
    chart = page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")')
    page.click('#fit3dBtn')                                           # the 3D map's Fit: in on the selected node
    page.wait_for_function(f'() => window.metaform.away3d() < {whole} * 0.7', timeout=5000)
    assert page.evaluate('document.querySelector("#map2d svg").getAttribute("viewBox")') == chart  # the 2D map did not move
    page.click('#fit3dBtn')                                           # and out again
    page.wait_for_function(f'() => window.metaform.away3d() > {whole} * 0.9', timeout=5000)
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
            ['element', 'Add Element', False])                          # and VIEW-033
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


@pytest.mark.req('VIEW-033')
def test_a_person_adds_an_element_joined_to_a_node_and_an_agent_is_started_to_validate_it(run, web, mapped, browser,
                                                                                          tmp_path):
    """Rich, 2026-09-29: a new element tool so the user can add and join something into the map, with an option to
    kick off an agent to pre-validate the new element, prompted in his words."""
    import sys
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').element_id
    said = tmp_path / 'said.json'
    agent = tmp_path / 'agent.py'
    agent.write_text('import json, os, sys\n'
                     f'json.dump({{"args": sys.argv[1:], "cwd": os.getcwd()}}, open({str(said)!r}, "a"))\n'
                     f'open({str(said)!r}, "a").write("\\n")\n', encoding='utf-8')
    run('set', '--agent-command', f'{sys.executable} {agent} -p', cwd=mapped)
    started(run)
    page, problems, _ = opened(browser, web)
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
    page.select_option('#element .receives', 'node')                  # the alarm holds the purpose; the new part serves it
    page.fill('#element .purpose', 'Tell a cook who cannot hear that the time is up.')
    page.fill('#element .ef', 'Flashes a lamp when the timer runs out.')
    page.check('#element .validate')
    page.click('#element .add')
    page.wait_for_function('() => document.querySelector("#element").hidden')
    store = Store('proj')
    made = store.element('code.alarm.visible')
    assert made is not None and (made.layer, made.name_length, made.short_name) == ('additions', 2, 'visible alarm')
    joined = [join for join in store.joins('code.alarm.audible').results if join.provider == made.element_id]
    assert [(join.receiver, join.layer, join.purpose, join.ef) for join in joined] == [
        (alarm, 'additions', 'Tell a cook who cannot hear that the time is up.', 'Flashes a lamp when the timer runs out.')]
    work = store.work(Node_of('code.alarm.visible'), 'missing', True).results
    assert len(work) == 1 and work[0].task == f'{VALIDATE} The element is code.alarm.visible.'
    page.wait_for_function(f'() => window.metaform.look("{made.element_id}").text3d === true', timeout=8000)
    for _ in range(50):                                               # the agent is not waited for
        if said.exists() and said.read_text(encoding='utf-8').strip():
            break
        page.wait_for_timeout(100)
    calls = [json.loads(line) for line in said.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len(calls) == 1 and calls[0]['args'] == ['-p', work[0].task]
    assert Path(calls[0]['cwd']).resolve() == Path(mapped).resolve()
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
    assert len([line for line in said.read_text(encoding='utf-8').splitlines() if line.strip()]) == 1
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
    """Rich, 2026-09-29: notes where both he and an agent put notes in place."""
    from metaform.data import Store
    alarm = Store('proj').element('code.alarm.audible').element_id
    run('memory', 'add-observations', 'element:code.alarm.audible', 'The tone is 2 kHz.', cwd=mapped)  # an agent's
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.linkColors().length > 0')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 1'
    page.click('#menu button.notes')
    page.wait_for_selector('#notes:not([hidden]) .kept li')
    assert page.locator('#notes .kept li').all_inner_texts() == ['The tone is 2 kHz.']
    page.click('#notes .add')                                          # a note with no text is not written
    page.wait_for_timeout(400)
    assert page.locator('#notes .kept li').count() == 1
    page.fill('#notes textarea', 'Too quiet in a loud kitchen. Ask before changing the pitch.')
    page.click('#notes .add')
    page.wait_for_function('() => document.querySelectorAll("#notes .kept li").length === 2')
    assert page.locator('#notes .kept li').all_inner_texts() == [
        'The tone is 2 kHz.', 'Too quiet in a loud kitchen. Ask before changing the pitch.\nyou']
    assert page.input_value('#notes textarea') == ''
    # read raw, since the fixture's folder names its layers and memory is not among them
    read = json.loads(run('map', 'node', 'element:code.alarm.audible', '--raw', '--json', cwd=mapped).stdout)
    kept = [item for group in read['layers'] if group['kind'] == 'memory' for item in group['items']]
    assert [(item['value'], (item['extra'] or {}).get('by')) for item in kept] == [
        ('The tone is 2 kHz.', None), ('Too quiet in a loud kitchen. Ask before changing the pitch.', 'user')]
    page.click('#notes .close')
    page.evaluate(f'window.metaform.menu("{alarm}")')
    assert page.text_content('#menu button.notes') == 'Notes 2'
    assert problems == []


SAMPLE_BOTH = '''key => { window.samples = []; window.sampling = true;
    const tick = () => { const svg = document.querySelector("#map2d svg"), box = svg ? svg.viewBox.baseVal : null;
        const seen = window.metaform.screen3d(key);
        window.samples.push({base: svg ? svg.dataset.base === "yes" : false, o: svg ? Number(getComputedStyle(svg).opacity) : 1,
            w: box ? box.width : 0, o3: Number(getComputedStyle(document.querySelector("#stage")).opacity),
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
    remember = lambda *given: run('memory', *given, cwd=mapped)
    remember('add-observations', 'element:code.timer.kitchen', 'The countdown drifts under load.')
    remember('create-relations', 'element:code.timer.kitchen', 'drives', 'element:code.alarm.audible')     # it holds
    remember('create-relations', 'element:exterior.cook', 'waits on', 'element:code.timer.kitchen')        # held toward it
    remember('create-relations', 'element:code.alarm.audible', 'wakes', 'element:exterior.cook')           # between two of
    # its entities; and one of the alarm's own, to a node the kitchen timer's memories do not name
    remember('create-relations', 'element:code.alarm.audible', 'shown on', 'element:code.timer.kitchen.display')
    started(run)
    page, problems, _ = opened(browser, web)
    expected, at, _ = keys_of(web)
    kitchen, alarm, cook = at['code.timer.kitchen'], at['code.alarm.audible'], at['exterior.cook']
    outer = next(join['join_id'] for join in expected['joins'] if join['receiver'] == cook)
    page.wait_for_timeout(2400)  # the page fits the whole 3D map into view once, a moment after it opens
    set_layer(page, 'memory', True)  # the fixture's folder leaves memory out; it is turned on in this view
    page.keyboard.press('Escape')
    page.wait_for_function('() => window.metaform.loaded() && '
                           'window.metaform.graph().nodes.filter(node => node.layer === "memory").length === 5 && '
                           'document.querySelector("#p-object").textContent.includes("The countdown drifts")')
    entries = lambda: page.eval_on_selector_all(
        '#menu button', 'found => found.map(one => [one.className, one.textContent, one.disabled])')
    selected = lambda: page.evaluate('window.metaform.selected()')
    network = lambda: page.evaluate('window.metaform.memory()')
    base = page.evaluate('() => { const svg = document.querySelector("#map2d svg"); svg.dataset.base = "yes"; '
                         'return document.querySelectorAll("#map2d svg g.node").length; }')

    # from the 2D map: a right-click on the node's own box
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.wait_for_timeout(1200)  # both cameras settle on it
    box = page.evaluate(f'window.metaform.box2d("{kitchen}")')
    page.mouse.click(box['left'] + 6, box['top'] + 6, button='right')  # its own box, clear of the tick loop inside it
    page.wait_for_selector('#menu:not([hidden])')
    assert entries()[2] == ['memories', 'Memories 3', False]  # its observation, the relation it holds, one held toward it
    page.evaluate(SAMPLE_BOTH, kitchen)
    page.click('#menu button.memories')
    page.wait_for_function(f'() => window.metaform.memory() && window.metaform.memory().key === "{kitchen}"')
    page.wait_for_timeout(1500)  # the network fades in
    samples = page.evaluate('() => { window.sampling = false; return window.samples; }')
    going, shown = [one for one in samples if not one['memory']], [one for one in samples if one['memory']]
    assert going and shown
    assert max(one['r'] for one in going) > going[0]['r'] * 2  # the 3D view zooms into the node
    assert min(one['o3'] for one in going) < 0.5                 # as the map gives way to it
    assert shown[0]['o3'] < 0.5 and shown[-1]['o3'] == 1         # and the memory network comes in
    was = [one for one in going if one['base']]
    # the 2D view the same; the kitchen timer is a large box, holding its tick loop, so the view narrows less onto it
    assert min(one['o'] for one in was) < 0.5 and was[-1]['w'] < was[0]['w'] * 0.9
    own = [one for one in shown if not one['base']]
    assert own and own[0]['o'] < 0.5 and own[-1]['o'] == 1

    # the memory network: the node's entities and the relations between them, and nothing else, in both views
    drawn = network()
    assert sorted(drawn['nodes']) == sorted([kitchen, alarm, cook]) == sorted(drawn['nodes2d'])
    assert sorted((link['source'], link['relation'], link['target']) for link in drawn['links']) == sorted(
        [(kitchen, 'drives', alarm), (cook, 'waits on', kitchen), (alarm, 'wakes', cook)])
    words = page.evaluate('document.querySelector("#map2d svg").textContent')
    assert all(word in words for word in ('drives', 'waits on', 'wakes')) and 'shown on' not in words
    assert '3 nodes shown' in page.inner_text('#count')
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
    page.evaluate(f'window.metaform.click3d("{alarm}")')
    assert selected() == alarm and 'wakes' in page.inner_text('#p-object')
    box = page.evaluate(f'window.metaform.box2d("{cook}")')
    page.mouse.click((box['left'] + box['right']) / 2, (box['top'] + box['bottom']) / 2)
    assert selected() == cook and network()['key'] == kitchen  # a click in it selects, and stays in it

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
    assert sorted(network()['nodes']) == sorted([kitchen, alarm, cook])
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
    assert problems == []


@pytest.mark.req('VIEW-037')
def test_the_board_holds_the_tickets_in_four_columns_and_a_card_dragged_moves_its_ticket(run, web, mapped, browser):
    """Rich, 2026-10-01: an actual classic kanban window you can open that mirrors the features in a traditional
    kanban: columns with counts, cards with their kind, nodes and progress, dragging between and within columns, a
    search and a filter by kind, and adding a card."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    kitchen = Node('element', 'code.timer.kitchen')
    todo = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone', links=[kitchen])
    store.add_work(kitchen, 'enhancement', task='a second countdown', held=True)
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


@pytest.mark.req('VIEW-035')
def test_an_agents_figure_walks_from_the_de_to_its_ticket_circles_it_and_walks_back_when_it_closes(run, web, mapped, browser):
    """Rich, 2026-10-01: the agents materialize on the most primary node and navigate the mesh to the node being
    worked on; they go onto it and circle it until the ticket is closed, then navigate back; even if the agent
    finished, they still touch the node and walk back."""
    from metaform.data import Node, Store
    store = Store('proj')
    alarm = store.element('code.alarm.audible').element_id
    cook = store.element('exterior.cook').element_id
    worked = store.add_work(Node('element', 'code.alarm.audible'), 'flawed', task='a quieter tone')
    store.take_work(worked.work_id, steps=2, by='codex')
    quick = store.add_work(Node('element', 'exterior.cook'), 'enhancement', task='a second recipe')
    store.take_work(quick.work_id, by='claude')
    store.finish_work(quick.work_id, 'added')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded() && window.metaform.figures().length === 2', timeout=15000)
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
    assert node['r'] < away < node['r'] + 12, (away, node)            # on the node and around it
    page.wait_for_function(f'() => !window.metaform.figures().some(one => one.work_id === "{quick.work_id}")', timeout=20000)
    seen = page.evaluate(f'[...window.stages["{quick.work_id}"] || []]')
    assert 'touching' in seen and 'circling' not in seen, seen        # finished: it touched the node and went back
    run('map', 'work', 'op=done', f'id={worked.work_id}', 'resolution=quieter', cwd=mapped)
    page.wait_for_function(f'() => (window.stages["{worked.work_id}"] || new Set()).has("returning")', timeout=10000)
    page.wait_for_function('() => window.metaform.figures().length === 0', timeout=20000)
    assert cook and problems == []
