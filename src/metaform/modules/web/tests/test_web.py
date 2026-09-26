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
    licenses = ['mermaid.LICENSE', 'three/LICENSE', 'fonts/IBM-Plex.LICENSE',
                *(f'd3/{name}.LICENSE' for name in ('d3-force-3d', 'd3-binarytree', 'd3-octree', 'd3-quadtree',
                                                    'd3-dispatch', 'd3-timer'))]
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


def config_layers(run, folder):
    return next(row for row in json.loads(run('config', '--show', '--json', cwd=folder).stdout)
                if row['key'] == 'layers')['value']


@pytest.mark.req('VIEW-005')
@pytest.mark.req('VIEW-008')
@pytest.mark.req('VIEW-003')
@pytest.mark.req('VIEW-012')
def test_the_page_draws_each_join_as_a_face_and_both_views_select_together(run, web, mapped, browser):
    started(run)
    page, problems, remote = opened(browser, web)
    graph = page.evaluate('window.metaform.graph()')
    expected = api(web, '/api/graph?project=proj&limit=0')[1]
    elements = {entry['element']['element_id'] for entry in expected['elements']}
    links = graph['links']
    assert sorted(node['id'] for node in graph['nodes'] if node['t'] == 'el') == sorted(elements)
    for join in expected['joins']:
        purpose, encounter = 'p:' + join['join_id'], 'e:' + join['join_id']
        face = sorted((link['source'], link['target']) for link in links
                      if link['k'] == 'face' and link['join'] == join['join_id'])
        assert face == sorted([(join['receiver'], purpose), (purpose, encounter), (encounter, join['receiver'])])
        assert [(link['source'], link['target']) for link in links
                if link['k'] == 'tie' and link['join'] == join['join_id']] == [(encounter, join['provider'])]
    assert len([link for link in links if link['k'] == 'tree']) == len([e for e in expected['elements'] if e['parent']])
    assert not [link for link in links if link['k'] != 'tree' and {link['source'], link['target']} <= elements]
    assert len([node for node in graph['nodes'] if node['t'] == 'sub']) == sum(len(j['subtypes']) for j in expected['joins'])
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
    by_address = {entry['element']['address']: entry['element']['element_id'] for entry in expected['elements']}
    page.focus('#map2d')
    kitchen = by_address['code.timer.kitchen']
    page.evaluate(f'window.metaform.select("{kitchen}")')
    # This small map is laid out left to right, each join drawn from receiver to provider, so the alarm the kitchen
    # receives from lies to its right, and the cook and the display, which receive from it, to its left.
    page.keyboard.press('ArrowRight')
    assert page.evaluate('window.metaform.selected()') == by_address['code.alarm.audible']
    page.evaluate(f'window.metaform.select("{kitchen}")')
    page.keyboard.press('ArrowLeft')
    assert page.evaluate('window.metaform.selected()') in {by_address['exterior.cook'],
                                                           by_address['code.timer.kitchen.display']}
    page.keyboard.press('f')
    page.wait_for_timeout(300)
    assert problems == [] and remote == []


@pytest.mark.req('VIEW-007')
@pytest.mark.req('VIEW-012')
def test_toggling_layers_in_the_page_changes_only_the_view_until_apply(run, web, mapped, browser):
    started(run)
    page, problems, _ = opened(browser, web)
    before = config_layers(run, mapped)
    page.click('#layers .chip:has-text("notes")')
    page.wait_for_function('() => !document.querySelector("#apply").disabled')
    assert page.get_attribute('#layers .chip:has-text("notes")', 'aria-pressed') == 'false'
    page.wait_for_timeout(1000)
    assert config_layers(run, mapped) == before
    assert 'display' not in page.evaluate('window.metaform.graph().nodes.map(n => n.name)')
    page.click('#apply')
    page.wait_for_function('() => document.querySelector("#apply").disabled')
    assert set(config_layers(run, mapped)) == {'intake-1', 'extra'}
    assert problems == []


def stacked(store):
    """Two more correction layers on the fixture's fix-1: fix-2 moves the alarm to code.alarm.bell, fix-3 to chime."""
    for name, old, new in (('fix-2', 'code.alarm.audible', 'code.alarm.bell'), ('fix-3', 'code.alarm.bell',
                                                                                  'code.alarm.chime')):
        layer = store.layer(name, 'test', 'Corrections.', kind='correction', mutable=False, hideable=False,
                            provenance=PROVENANCE)
        store.correct(layer.name, store.element(old).element_id, {'address': new}, reason=f'it is a {new[11:]}')
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
    assert [(change['what'], change['effect'], change['detail']) for change in preview['changes']
            if change['kind'] == 'element'] == [('code.alarm.chime', 'moves back', 'from code.alarm.chime to code.alarm.bell')]
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
    for shown in ('kitchen timer', 'code.timer.kitchen', 'DE', 'broken', 'drifts', 'intake-1',
                  'provider · audible alarm', 'receiver · cook', 'receiver · display', 'tick loop', 'Advances each countdown.',
                  'MEMORY', 'drifts under load', 'Nothing recovers a hung loop. · A', 'written in C', 'notes'):
        assert shown in panel, shown
    assert problems == []


DRAW_CALLS = 12  # one per vertex kind, per edge style, the glow and the tie arrows, with room to spare


def drawn_when_loaded(page, joins):
    page.wait_for_function('([joins]) => window.metaform.loaded() && window.metaform.drawn() '
                           '&& window.metaform.drawn().ties === joins', arg=[joins], timeout=60000)
    page.wait_for_timeout(500)
    return page.evaluate('window.metaform.drawn()')


@pytest.mark.req('VIEW-010')
@pytest.mark.req('VIEW-012')
def test_every_element_and_join_is_drawn_in_a_fixed_number_of_draw_calls_whatever_the_size(run, home, web, mapped,
                                                                                          browser, tmp_path):
    from metaform.data import Store
    started(run)
    page, problems, _ = opened(browser, web)
    small = page.evaluate('window.metaform.graph()')
    counts = {kind: len([node for node in small['nodes'] if node['t'] == kind]) for kind in ('el', 'purpose', 'sub')}
    drawn = drawn_when_loaded(page, counts['purpose'])
    assert (drawn['elements'], drawn['purposes'], drawn['encounters'], drawn['faces'], drawn['subtypes']) == (
        counts['el'], counts['purpose'], counts['purpose'], counts['purpose'], counts['sub'])
    assert 0 < drawn['calls'] <= DRAW_CALLS
    folder = tmp_path / 'big'
    folder.mkdir()
    run('add', 'project', 'big', str(folder))
    big = Store('big')
    with big.atomic():
        layer = big.layer('intake-1', 'intake', 'The map.', kind='intake', mutable=False, hideable=False,
                          provenance=PROVENANCE, ready=True)
        for n in range(3000):
            big.add_element(layer.name, f'code.g{n % 30}.e{n}', role='SE')
        for n in range(3000):
            big.add_join(layer.name, f'code.g{n % 30}.e{n}', f'code.g{(n + 1) % 30}.e{(n + 1) % 3000}', purpose='p',
                         function='f', relation='r', observation='o')
    page.goto(f'http://127.0.0.1:{web}/#p=big')
    page.reload()
    drawn = drawn_when_loaded(page, 3000)
    assert (drawn['elements'], drawn['purposes'], drawn['faces'], drawn['ties']) == (3000, 3000, 3000, 3000)
    assert 0 < drawn['calls'] <= DRAW_CALLS and drawn['labels'] <= 80
    assert problems == []
