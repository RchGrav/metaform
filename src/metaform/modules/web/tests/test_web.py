"""The web module: one web GUI server per Metaform home, started and stopped from any folder, VIEW-001, VIEW-002, VIEW-015."""
from __future__ import annotations

import http.client
import json
import socket
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.kind('fixture')

NOTICE = ('Before an intake, start the web GUI with metaform web, or the web_start tool, if it is not already running. '
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
    """An intake with a DE carrying a broken work record and a subtype; a knowledge layer on, one masked at code.alarm, one hidden; and a
    knowledge item orphaned when a correction removes its element, VIEW-004."""
    from metaform.data import Node
    with store.atomic():
        intake = store.layer('intake-1', 'intake', 'The functional map.', kind='intake', mutable=False,
                             hideable=False, provenance=PROVENANCE, ready=True)
        store.add_element(intake.name, 'exterior.cook', name_length=1, role='VE')
        store.add_element(intake.name, 'code.timer.kitchen', name_length=2, role='DE')
        store.add_element(intake.name, 'code.alarm.audible', name_length=2, role='SE')
        store.add_element(intake.name, 'code.gone', name_length=1, role='SE')
        outer = store.add_join(intake.name, 'exterior.cook', 'code.timer.kitchen', name='dish timer',
                               purpose='Know when food is done.',
                               function='Counts down and rings.', ef='Function', relation='The timer tells the cook.',
                               observation='One countdown per dish.')
        store.add_join(intake.name, 'code.timer.kitchen', 'code.alarm.audible', purpose='Get attention.',
                       function='Plays a tone.', ef='Encounter', relation='The alarm rings for the timer.',
                       observation='A piezo.')
        store.add_subtype(intake.name, outer.join_id, 'code.loop.tick', function='Advances each countdown.',
                          ef='Function', relation='The tick loop drives the timer.', observation='One tick a second.',
                          name='one-second tick', name_length=2, role='SE')
    store.add_work(Node('element', 'code.timer.kitchen'), 'broken', note='drifts', task='hold the tick to one second')
    for name in KNOWLEDGE:
        store.layer(name, 'test', f'What {name} says.', mutable=True, hideable=True, provenance=PROVENANCE)
    store.add_element('notes', 'code.timer.kitchen.display', name_length=1)
    store.add_join('notes', 'code.timer.kitchen.display', 'code.timer.kitchen', purpose='Show the time left.',
                   function='Reports the time left.', relation='The timer feeds the display.', observation='LCD')
    store.add_item('notes', Node('element', 'code.timer.kitchen'), 'keep the loop small')
    store.add_item('notes', Node('element', 'code.gone'), 'the loop drifts here')
    store.add_element('extra', 'code.alarm.audible.loud', name_length=1)
    store.add_item('extra', Node('element', 'code.alarm.audible'), 'louder is better')
    store.add_element('secret', 'code.secret', name_length=1)
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
        '/api/work': lambda raw: store.work(),
        '/api/work?node=element:code.timer.kitchen': lambda raw: store.work(node=kitchen),
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
                 '/api/work?project=proj', '/api/search?project=proj&text=loop', '/api/stack?project=proj',
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
    status, page, headers = request(web, '/')
    assert status == 200 and headers['Content-Security-Policy'].startswith("default-src 'self'")
    loaded = re.findall(r'(?:src|href)="([^"]+)"', page)
    assert loaded and all(path.startswith('/') and not path.startswith('//') for path in loaded)
    texts = [page]
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
                'codemirror/LICENSE']
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
    assert by_name['corrections']['checked'] and by_name['corrections']['disabled']
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


def stacked(store):
    """Two more correction layers on the fixture's fix-1: fix-2 records a bell and moves the timer's alarm join to it,
    fix-3 records a chime and moves the join on to that; an element never moves, MAP-015."""
    alarm = store.joins('code.timer.kitchen').results[0].join_id
    for name, new in (('fix-2', 'code.alarm.bell'), ('fix-3', 'code.alarm.chime')):
        layer = store.layer(name, 'test', 'Corrections.', kind='correction', mutable=False, hideable=False,
                            provenance=PROVENANCE)
        store.add_element(layer.name, new, name_length=1, role='SE')
        store.correct(layer.name, alarm, {'provider': new}, reason=f'it is a {new[11:]}')
        store.finish(layer.name)


def remove(port, layer, headers=None):
    body = json.dumps({'project': 'proj', 'layer': layer})
    return api(port, '/api/remove-correction', method='POST', body=body,
               headers=headers or {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}'})


@pytest.mark.req('VIEW-014')
@pytest.mark.req('VIEW-011')
def test_only_the_top_correction_layer_is_removed_and_a_request_for_another_changes_nothing(run, home, web, mapped):
    from metaform.data import Store
    store = Store('proj')
    stacked(store)
    started(run)
    assert [layer['name'] for layer in api(web, '/api/stack?project=proj')[1]['results']] == ['fix-1', 'fix-2', 'fix-3']
    assert api(web, '/api/peel-preview?project=proj&layer=fix-2')[1]['top'] is False
    preview = api(web, '/api/peel-preview?project=proj&layer=fix-3')[1]
    assert preview['top'] is True
    assert [(change['kind'], change['what'], change['effect'], change['detail']) for change in preview['changes']] == [
        ('element', 'code.alarm.chime', 'disappears', None),
        ('join', 'code.timer.kitchen -> code.alarm.chime', 'moves back', 'to code.timer.kitchen -> code.alarm.bell')]
    files = sorted((home / 'projects').rglob('store.sqlite3'))
    removed_id = store.layer_ref('fix-3').layer_id
    before = [path.read_bytes() for path in files]
    status, answer = remove(web, 'fix-2')
    assert status == 200 and answer['removed'] is False and 'fix-3' in answer['notices'][0]['message']
    assert [path.read_bytes() for path in files] == before
    assert remove(web, 'fix-3', {'Content-Type': 'application/json'})[0] == 403
    status, answer = remove(web, 'fix-3')
    assert status == 200 and answer['removed'] is True
    assert [layer['name'] for layer in api(web, '/api/stack?project=proj')[1]['results']] == ['fix-1', 'fix-2']
    assert store.element('code.alarm.bell') is not None and store.element('code.alarm.chime') is None
    assert 'fix-3' not in [layer.name for layer in store.layers(limit=0).results] and store.provenance('fix-2')
    from metaform.data import export_document
    rows = [row for metaform in export_document(['proj'])['projects'][0]['metaforms'] for row in metaform['provenance']]
    assert rows and removed_id not in [row['layer_id'] for row in rows]
    assert api(web, '/api/peel-preview?project=proj&layer=fix-2')[1]['top'] is True


@pytest.mark.req('VIEW-014')
@pytest.mark.req('VIEW-012')
def test_the_page_offers_removal_only_on_the_top_layer_and_warns_first(run, web, mapped, browser):
    from metaform.data import Store
    stacked(Store('proj'))
    started(run)
    page, problems, _ = opened(browser, web)
    page.click('#t-corr')
    page.wait_for_selector('#p-corr .lyr.top')
    assert page.locator('#p-corr button.remove').count() == 1
    assert page.text_content('#p-corr .lyr.top b') == 'fix-3'
    assert page.locator('#p-corr .lyr.top button.remove').count() == 1
    page.click('#p-corr button.remove')
    page.wait_for_selector('#p-corr .warn')
    warning = page.text_content('#p-corr .warn')
    assert 'code.alarm.chime' in warning and 'moves back' in warning and 'code.alarm.bell' in warning
    assert [layer.name for layer in Store('proj').stack(limit=0).results] == ['fix-1', 'fix-2', 'fix-3']
    page.click('#p-corr .warn button.confirm')
    page.wait_for_function('() => document.querySelector("#p-corr .lyr.top b")?.textContent === "fix-2"')
    assert [layer.name for layer in Store('proj').stack(limit=0).results] == ['fix-1', 'fix-2']
    assert page.locator('#p-corr button.remove').count() == 1
    assert problems == []


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
@pytest.mark.req('MAP-046')
def test_a_node_with_open_tbd_work_is_ghostly_a_broken_one_flashes_red_until_resolved_and_the_panel_lists_the_records(
        run, web, mapped, browser):
    """Rich, 2026-09-27: a TBD object is drawn ghostly, showing what it will be, and the agent that completes its task
    makes it solid; a node with an open issue flashes red; cruft keeps its look. The fixture's kitchen timer carries an
    open broken record."""
    from metaform.data import Node, Store
    store = Store('proj')
    tbd = store.add_work(Node('element', 'code.alarm.audible'), 'tbd', note='in the spec', task='build the piezo driver')
    store.add_work(Node('element', 'exterior.cook'), 'cruft', task='drop the cook')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    ids = {address: store.element(address).element_id for address in ('code.alarm.audible', 'code.timer.kitchen', 'exterior.cook')}
    look = lambda address: page.evaluate(f'window.metaform.look("{ids[address]}")')
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").opacity3d === 0.7', timeout=5000)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").opacity2d === 0.7', timeout=5000)
    alarm = look('code.alarm.audible')
    assert (alarm['work'], alarm['classes'], alarm['opacity2d'], alarm['opacity3d'], alarm['animated2d']) == (
        ['tbd'], ['work-tbd'], 0.7, 0.7, False)
    cook = look('exterior.cook')
    assert (cook['work'], cook['classes'], cook['opacity3d'], cook['animated2d'], cook['red3d']) == (
        ['cruft'], ['work-cruft'], 0.95, False, False)
    kitchen = look('code.timer.kitchen')
    assert (kitchen['work'], kitchen['classes'], kitchen['opacity2d'], kitchen['animated2d']) == (['broken'], ['work-broken'], 1, True)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.timer.kitchen"]}").red3d === true', timeout=3000)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.timer.kitchen"]}").red3d === false', timeout=3000)
    legend = page.inner_text('#legend')
    assert 'work: tbd' in legend and 'work: broken' in legend and 'work: cruft' in legend
    # The panel lists the selected node's work records.
    page.evaluate(f'window.metaform.select("{ids["code.timer.kitchen"]}")')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("hold the tick to one second")')
    panel = page.inner_text('#p-object')
    for shown in ('WORK', 'broken', 'drifts', 'hold the tick to one second', 'open'):
        assert shown in panel, shown
    # Its task done, pushed to the page, the alarm turns solid without a reload.
    run('map', 'work', 'op=done', f'id={tbd.work_id}', 'resolution=driver written', cwd=mapped)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").opacity3d === 0.95', timeout=5000)
    page.wait_for_function(f'() => window.metaform.look("{ids["code.alarm.audible"]}").opacity2d === 1', timeout=5000)
    solid = look('code.alarm.audible')
    assert (solid['work'], solid['classes'], solid['opacity2d']) == ([], [], 1)
    page.evaluate(f'window.metaform.select("{ids["code.alarm.audible"]}")')
    page.wait_for_function('() => document.querySelector("#p-object").innerText.includes("driver written")')
    assert 'done' in page.inner_text('#p-object')
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
        if join['ef']:
            assert encounter['color'] == color[join['ef'].lower()]
        else:  # a knowledge join with no word keeps its layer's color, never one of the two
            assert join['layer'] == 'notes' and encounter['color'] == color['k1']
        for subtype in join['subtypes']:
            link = next(link for link in drawn if link['target'] == 's:' + subtype['join_id'])
            assert link['color'] == color[subtype['ef'].lower()]
    assert sorted(join['ef'] or '' for join in expected['joins']) == ['', 'Encounter', 'Function']
    assert page.locator('#map2d svg .edgePaths path.ef-function').count() == 1
    assert page.locator('#map2d svg .edgePaths path.ef-encounter').count() == 1
    legend = page.inner_text('#legend')
    assert 'Function · the encounter of a functionality' in legend
    assert 'Encounter · the functionality of the encounter' in legend
    kitchen = next(entry['element']['element_id'] for entry in expected['elements']
                   if entry['element']['address'] == 'code.timer.kitchen')
    page.evaluate(f'window.metaform.select("{kitchen}")')
    assert sorted(page.evaluate('[...document.querySelectorAll("#p-object .join .ef")].map(e => e.textContent)')) \
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
    expected, at, inside = keys_of(web)
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
    page.mouse.click(box['x'] + box['w'] / 2, box['y'] + box['h'] / 2)


def inside(page):
    """The current level's node keys and the breadcrumb's words."""
    return page.evaluate('window.metaform.inside()'), page.inner_text('#crumbs') if page.is_visible('#crumbs') else ''


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
    _, at, inside = keys_of(web)
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
    regular = width()
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
    assert regular > zoomed and abs(width() - regular) < 1
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
                                purpose='p', function='f', relation='r', observation='o')
            if n < 10:
                big.add_subtype(layer.name, join.join_id, f'code.loop.s{n}', function='f', relation='r',
                                observation='o', role='SE')
        # e0 receives from e1 above; e1 also receives from e0: two joins, two paths, no loop, MAP-002.
        big.add_join(layer.name, 'code.g1.e1', 'code.g0.e0', purpose='q', function='g', relation='r', observation='o')
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
    run('intake', 'element', 'stakeholder.cook.home', 'role=VE', cwd=folder)
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
    made = json.loads(run('intake', 'join', 'stakeholder.cook.home', 'code.timer.kitchen', 'purpose=p', 'function=f',
                          'ef=Function', 'relation=r', 'verb=tells', 'observation=o', '--json', cwd=folder).stdout)
    page.wait_for_function('() => window.metaform.drawn().nodes === 3', timeout=1500)  # pushed, not waited for
    page.wait_for_function('() => document.querySelectorAll("#map2d svg g.node").length === 2', timeout=15000)
    page.wait_for_timeout(300)  # the panel's reads for the selected node settle
    assert not [text for text in page.evaluate('window.toasts') if 'Nothing for' in text]  # an unfinished layer is no error
    run('intake', 'subtype', made['join_id'], 'code.loop.tick', 'function=f', 'ef=Function', 'relation=r',
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
def test_a_module_that_writes_to_the_map_is_seen_live_as_helloworld_greetings_appear_in_3d(run, web, mapped, browser):
    """Rich, 2026-09-26: a capability added for a feature gets a demonstration in helloworld; here a greeting,
    written by a module that is not built into the map, reaches the open page through map.changed."""
    run('enable', 'helloworld')
    started(run)
    page, problems, _ = opened(browser, web)
    page.wait_for_function('() => window.metaform.loaded()')
    texts = lambda: page.evaluate('window.metaform.graph().nodes.filter(node => node.t === "item").map(node => node.text)')
    assert 'world' not in texts()
    run('helloworld', 'greet', 'world', cwd=mapped)
    page.click('#layersBtn')
    page.wait_for_selector('#layerlist input[data-layer="helloworld.greetings"]', timeout=3000)  # pushed to the page;
    set_layer(page, 'helloworld.greetings', True)  # the folder's layers leave the new layer off
    page.wait_for_function('() => window.metaform.graph().nodes.some(node => node.t === "item" && node.text === "world")',
                           timeout=3000)
    run('helloworld', 'greet', 'moon', cwd=mapped)
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
    Store('proj').add_work(Node('element', 'code.loop.tick'), 'tbd', task='count in milliseconds')
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
    assert status == 200 and answer == {
        'project': 'proj', 'metaforms': ['main', 'fresh'], 'reports': 1,
        'said': ('Cleared proj: two metaforms, main and fresh, and one report file. Its registration, folder, '
                 'settings, origins and variants stay.')}
    assert run('list', 'metaforms', cwd=mapped).stdout == ''
    assert not (home / 'projects' / 'proj' / 'metaforms').exists()
    assert not (home / 'projects' / 'proj' / 'reports').exists()
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
    reports = home / 'projects' / 'proj' / 'reports'
    (stuck,) = reports.iterdir()
    started(run)
    with unremovable(stuck):
        status, answer = clear(web, confirm=True)
        assert stuck.is_file()
    assert status == 200 and answer['said'] == CLEARED
    assert [entry['path'] for entry in answer['not_removed']] == [str(stuck)] and answer['not_removed'][0]['reason']
    assert answer['notices'] == [{'where': 'not_removed', 'message': LEFT}]
    assert run('list', 'metaforms', cwd=mapped).stdout == ''
    assert not (home / 'projects' / 'proj' / 'metaforms').exists()
    assert clear(web, confirm=True) == (200, {
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
    assert page.inner_text('header #clearBtn') == 'Clear project'
    other.click('#t-corr')  # a tab left open is redrawn by the push, not only when clicked again
    other.wait_for_selector('#p-corr .lyr.top')
    before = kept(home)
    page.click('#clearBtn')
    page.wait_for_selector('#clearbox .warn')
    assert caution in page.inner_text('#clearbox')
    page.keyboard.press('Escape')
    assert page.is_hidden('#clearbox')
    page.click('#clearBtn')
    page.click('#clearbox button.keep')
    assert page.is_hidden('#clearbox')
    assert kept(home) == before and metaform_names(run, mapped) == ['main']
    page.click('#clearBtn')
    page.click('#clearbox button.confirm')
    page.wait_for_selector('#clearbox .said')
    assert page.inner_text('#clearbox .said') == CLEARED
    assert 'Not removed' not in page.inner_text('#clearbox')
    assert metaform_names(run, mapped) == []
    for shown in (page, other):
        no_metaform_shown(shown)
    other.wait_for_function(f'() => document.querySelector("#p-corr").innerText.includes("{NO_METAFORM}")',
                            timeout=5000)
    other.click('#t-prov')
    other.wait_for_function(f'() => document.querySelector("#p-prov").innerText.includes("{NO_METAFORM}")')
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
    (stuck,) = (home / 'projects' / 'proj' / 'reports').iterdir()
    started(run)
    page, problems, _ = opened(browser, web)
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
    """A module of the user's own hears the page's clear and correction removal once each, as it hears the command's,
    and the open pages still hear each once; a write that changes nothing is not announced."""
    from metaform import home as metaform_home
    from metaform.data import Store
    log = tmp_path / 'heard.jsonl'
    user_module('watcher', WATCHER.replace('LOGPATH', repr(str(log))))
    stacked(Store('proj'))
    started(run)
    active = metaform_home.active_metaform('proj').metaform_id
    heard, first = events_on(web)
    heard_by(log)
    status, answer = remove(web, 'fix-2')  # not on top: nothing changes, nothing is announced
    assert status == 200 and answer['removed'] is False
    status, answer = clear(web)  # the caution alone: nothing changes, nothing is announced
    assert status == 400
    time.sleep(0.5)
    assert heard_by(log) == [] and heard == []
    status, answer = remove(web, 'fix-3')
    assert status == 200 and answer['removed'] is True
    assert first.wait(5)
    time.sleep(0.5)
    assert heard_by(log) == [{'project': 'proj', 'metaform_id': active, 'surface': 'web'}]
    assert heard == [{'topic': 'map.changed', 'payload': {'project': 'proj', 'metaform_id': active}}]
    heard.clear()
    status, answer = clear(web, confirm=True)
    assert status == 200 and answer['metaforms'] == ['main']
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
    run('intake', 'element', 'stakeholder.cook.home', 'role=VE', cwd=folder)
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
    assert [text for text in said if text.startswith('The intake intake-') and text.endswith(' stopped: live was cleared.')]
    assert not [text for text in said if 'finished' in text]
    run('intake', 'start', cwd=folder)
    run('intake', 'element', 'stakeholder.cook.home', 'role=VE', cwd=folder)
    page.wait_for_function('() => window.metaform.live() !== null && window.metaform.drawn().nodes === 1', timeout=15000)
    page.evaluate('window.toasts = []')
    run('intake', 'finish', cwd=folder)
    page.wait_for_function('() => window.metaform.live() === null && window.metaform.loaded()', timeout=15000)
    said = page.evaluate('window.toasts')
    assert [text for text in said if text.startswith('The intake intake-') and text.endswith(' finished.')]
    assert not [text for text in said if 'stopped' in text]
    assert problems == []


def no_metaform_shown_for(page, project):
    line = f'{project} has no metaform yet. The next intake creates one.'
    page.wait_for_function(f'() => document.querySelector("#viewport").innerText.includes("{line}") && '
                           f'document.querySelector("#p-object").innerText.includes("{line}")', timeout=5000)
    assert page.inner_text('#count') == 'no metaform yet'
