"""The cloud path end to end, on loopback only: a broker (the Node's authorization server and broker in one process)
served by uvicorn on 127.0.0.1, this machine's Metaform signed in with the device grant and connected through the
tunnel, and a simulated cloud AI host that signs in with a Client ID Metadata Document and PKCE, then initializes, lists
and calls tools through the broker. Client metadata documents answer from a MockTransport; nothing leaves the machine,
no agent is started, and every home is a temporary one."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import socket
import threading
import time
import urllib.parse

import httpx
import pytest

pytestmark = pytest.mark.kind('simulation')

CLIENT = 'https://host.example.org/oauth/metadata.json'
REDIRECT = 'https://host.example.org/callback'


def free_port():
    with socket.socket() as held:
        held.bind(('127.0.0.1', 0))
        return held.getsockname()[1]


class Broker:
    """The broker role on 127.0.0.1, in a thread of its own."""

    def __init__(self, folder, **limits):
        import uvicorn

        from metaform.modules.node.authserver import Node, Policy
        from metaform.modules.node.authstore import BrokerStore
        from metaform.modules.node.broker import Broker as Carrier
        from metaform.modules.node.broker import Limits
        from metaform.modules.node.tokens import Keys

        def document(request):
            return httpx.Response(200, json={'client_id': CLIENT, 'client_name': 'Cloud Host',
                                             'redirect_uris': [REDIRECT], 'token_endpoint_auth_method': 'none'})
        self.port = free_port()
        self.issuer = f'http://127.0.0.1:{self.port}'
        self.store = BrokerStore(folder / 'auth.sqlite')
        self.node = Node(self.store, Policy(self.issuer, 'write', broker=True), httpx.MockTransport(document),
                         keys=Keys(folder / 'keys'))
        self.carrier = Carrier(self.node, Limits(**{'per_address': 1000.0, **limits}))
        self.server = self.carrier.server(uvicorn.Config(self.carrier.app(), host='127.0.0.1', port=self.port,
                                                         log_level='warning', ws_max_size=2 * 1024 * 1024))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started and time.time() < deadline:
            time.sleep(0.02)
        assert self.server.started

    def stop(self):
        self.server.should_exit = True
        self.thread.join(10)

    def person(self, name):
        """An account and a browser signed in to it with a session, as after the passkey."""
        account = self.store.add_account(name, 'owner' if not self.store.owner_exists() else 'member')
        session, _ = self.store.open_session(account, 3600)
        browser = httpx.Client(base_url=self.issuer, follow_redirects=False, timeout=10)
        browser.cookies.set('metaform-session', session)
        return account, browser


@pytest.fixture
def broker(tmp_path, home, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker')
    yield made
    made.stop()


def login(made, browser, instance='default', replace=False, confirm=None):
    """`metaform cloud login`: the code here, approved on the page with the person's session; `replace` ticks the box
    a connected instance of the same name asks for."""
    from metaform.modules.cloud import login as signing
    with httpx.Client(timeout=10) as client:
        started = signing.start(made.issuer, instance, client, device_name='test-machine')
        page = browser.get('/device', params={'user_code': started.user_code})
        csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
        form = {'user_code': started.user_code, 'csrf': csrf, 'decision': 'approve',
                **({'replace': 'yes'} if replace else {})}
        assert browser.post('/device', data=form, headers={'Origin': made.issuer}).status_code == 200
        return signing.finish(started, client, sleep=lambda seconds: None, confirm=confirm)


class Local:
    """`metaform cloud connect` in a thread: the MCP app in-process behind the tunnel, with a spy on what reaches it."""

    def __init__(self, folder, made, allows=('mcp:read', 'mcp:write')):
        from metaform.modules.cloud import tunnel
        self.seen = []
        self.states = []
        self.error = None
        self.loop = asyncio.new_event_loop()
        self.connected = threading.Event()

        self.serving = 0  # requests the MCP app is still answering

        def spy(app):
            async def watched(scope, receive, send):
                if scope['type'] == 'http':
                    self.seen.append({name.decode(): value.decode() for name, value in scope['headers']})
                self.serving += 1
                try:
                    await app(scope, receive, send)
                finally:
                    self.serving -= 1
            return watched

        def state(record):
            self.states.append(dict(record))
            if record.get('state') == 'connected':
                self.connected.set()

        async def main():
            await tunnel.serve(folder, made, allows, say=lambda line: None, state=state, wrap=spy)

        def run():
            try:
                self.loop.run_until_complete(main())
            except BaseException as error:  # noqa: BLE001  kept for the test to read
                self.error = error
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert self.connected.wait(10), self.states

    def stop(self):
        if self.thread.is_alive():
            for task in asyncio.all_tasks(self.loop):
                self.loop.call_soon_threadsafe(task.cancel)
            self.thread.join(10)


def host_sign_in(made, browser, resource=None, scope='mcp:read mcp:write'):
    """A cloud host's sign-in: discovery from the 401, then OAuth 2.1 with PKCE S256 and a metadata document."""
    path = urllib.parse.urlsplit(resource).path if resource else '/mcp'
    refused = httpx.post(made.issuer + path, json={})
    assert refused.status_code == 401
    metadata_url = refused.headers['www-authenticate'].split('resource_metadata="')[1].split('"')[0]
    described = httpx.get(metadata_url).json()
    server = httpx.get(described['authorization_servers'][0] + '/.well-known/oauth-authorization-server').json()
    assert server['client_id_metadata_document_supported'] is True
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    asked = browser.get(server['authorization_endpoint'].removeprefix(made.issuer), params={
        'response_type': 'code', 'client_id': CLIENT, 'redirect_uri': REDIRECT, 'state': 'st',
        'code_challenge': challenge, 'code_challenge_method': 'S256', 'resource': described['resource'],
        'scope': scope})
    page = browser.get(asked.headers['location'])
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    request = page.text.split('name="request" value="')[1].split('"')[0]
    back = browser.post('/node/consent', data={'request': request, 'csrf': csrf, 'decision': 'approve'},
                        headers={'Origin': made.issuer})
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(back.headers['location']).query)
    assert query['iss'] == [made.issuer]
    return httpx.post(server['token_endpoint'], data={
        'grant_type': 'authorization_code', 'code': query['code'][0], 'client_id': CLIENT, 'redirect_uri': REDIRECT,
        'code_verifier': verifier, 'resource': described['resource']}).json()


class Host:
    """A remote MCP client speaking Streamable HTTP to the broker with its bearer token."""

    def __init__(self, made, token, path='/mcp'):
        self.url = made.issuer + path
        self.token = token
        self.session = None
        self.number = 0

    def post(self, method, params=None, notify=False):
        headers = {'Authorization': f'Bearer {self.token}', 'Accept': 'application/json, text/event-stream',
                   'Content-Type': 'application/json', 'MCP-Protocol-Version': '2025-11-25'}
        if self.session:
            headers['Mcp-Session-Id'] = self.session
        self.number += 1
        body = {'jsonrpc': '2.0', 'method': method, 'params': params or {}}
        if not notify:
            body['id'] = self.number
        answer = httpx.post(self.url, json=body, headers=headers, timeout=30)
        self.session = answer.headers.get('mcp-session-id') or self.session
        if answer.headers.get('content-type', '').startswith('text/event-stream'):
            datas = [line[5:].strip() for line in answer.text.splitlines() if line.startswith('data:')]
            return answer, json.loads(datas[-1]) if datas else None
        return answer, answer.json() if answer.content and answer.status_code < 500 else None

    def initialize(self):
        answer, said = self.post('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                                'clientInfo': {'name': 'cloud-host', 'version': '1'}})
        assert answer.status_code == 200, answer.text
        self.post('notifications/initialized', notify=True)
        return said


def test_a_cloud_host_reaches_this_machine_through_the_broker_and_its_token_stays_at_the_broker(broker, tmp_path):
    from metaform.modules.cloud import audit
    from metaform.modules.cloud import login as signing
    _, browser = broker.person('alice')
    made = login(broker, browser)
    assert signing.credentials_file().stat().st_mode & 0o777 == 0o600
    first_refresh = made.refresh_token
    local = Local(tmp_path / 'work', made)
    try:
        assert signing.load().refresh_token != first_refresh  # connecting rotated it, and the file was replaced
        issued = host_sign_in(broker, browser)
        host = Host(broker, issued['access_token'])
        assert host.initialize()['result']['serverInfo']['name'] == 'metaform'
        listed = host.post('tools/list')[1]['result']['tools']
        names = {tool['name'] for tool in listed}
        assert {'search', 'fetch', 'metaform_instructions'} <= names
        answer, said = host.post('tools/call', {'name': 'metaform_instructions', 'arguments': {}})
        assert answer.status_code == 200 and said['result'].get('isError') is not True
        assert said['result']['content'][0]['text']
        _, found = host.post('tools/call', {'name': 'search', 'arguments': {'query': 'receiving element'}})
        results = json.loads(found['result']['content'][0]['text'])['results']
        assert results and all(set(one) == {'id', 'title', 'url'} and one['id'].startswith('metaform://')
                               for one in results)
        _, read = host.post('tools/call', {'name': 'fetch', 'arguments': {'id': results[0]['id']}})
        fetched = json.loads(read['result']['content'][0]['text'])
        assert set(fetched) == {'id', 'title', 'text', 'url', 'metadata'} and fetched['text']
        # A setting only the person sets is refused over the cloud path exactly as over any MCP connection.
        _, refused = host.post('tools/call', {'name': 'metaform_set', 'arguments': {'cloud_capability': 'dispatch'}})
        assert refused['result']['isError'] is True and 'only by the person' in refused['result']['content'][0]['text']
        # The host's token never reached this machine: every request came with the broker's own assertion.
        assert local.seen
        for headers in local.seen:
            assert issued['access_token'] not in json.dumps(headers)
            token = headers['authorization'].removeprefix('Bearer ')
            assert json.loads(base64.urlsafe_b64decode(token.split('.')[0] + '=='))['typ'] == 'mf-assert+jwt'
        lines = audit.read()
        called = [line for line in lines if line.get('name') == 'metaform_instructions']
        assert called and called[0]['account'] == 'alice' and called[0]['client_id'] == CLIENT
        assert called[0]['outcome'] == 'ok' and called[0]['client_name'] == 'Cloud Host'
        assert all('arguments' not in line for line in lines)  # cloud_audit names: no arguments kept
        assert audit.path().stat().st_mode & 0o777 == 0o600
    finally:
        local.stop()


def test_this_machine_holds_cloud_tools_to_its_own_capability(broker, tmp_path):
    _, browser = broker.person('alice')
    made = login(broker, browser)
    local = Local(tmp_path / 'work', made, allows=('mcp:read',))
    try:
        host = Host(broker, host_sign_in(broker, browser)['access_token'])  # granted read and write at the broker
        host.initialize()
        answer, _ = host.post('tools/call', {'name': 'metaform_feedback', 'arguments': {'text': 'x'}})
        assert answer.status_code == 403 and 'insufficient_scope' in answer.headers['www-authenticate']
        assert 'cloud_capability' in answer.json()['error_description']  # no sign-in can give what the owner caps
        assert host.post('tools/call', {'name': 'metaform_instructions', 'arguments': {}})[0].status_code == 200
    finally:
        local.stop()


def test_one_account_never_reaches_another_accounts_machine(broker, tmp_path):
    from metaform.modules.cloud import tunnel
    from metaform.modules.node import tokens
    _, alice_browser = broker.person('alice')
    alice = login(broker, alice_browser)
    _, bob_browser = broker.person('bob')
    bob = login(broker, bob_browser)
    alice_local = Local(tmp_path / 'work', alice)
    bob_local = Local(tmp_path / 'work', bob)
    try:
        host = Host(broker, host_sign_in(broker, alice_browser)['access_token'])
        host.initialize()
        host.post('tools/list')
        assert alice_local.seen and not bob_local.seen  # both are instance "default" at the same URL
        # Were the broker ever to route Alice's request down Bob's tunnel, Bob's machine refuses it unread.
        body = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
        misrouted = broker.carrier.signed.signer.mint(tokens.ASSERTION, {
            'sub': alice.account, 'aud': bob.resource, 'client_id': CLIENT, 'scope': 'mcp:read',
            'bh': tokens.body_hash(body)}, 60)
        assert tunnel.asserted(bob, ('mcp:read',)).check(misrouted, body) is None
        meant = broker.carrier.signed.signer.mint(tokens.ASSERTION, {
            'sub': bob.account, 'aud': bob.resource, 'client_id': CLIENT, 'scope': 'mcp:read',
            'bh': tokens.body_hash(body)}, 60)
        checking = tunnel.asserted(bob, ('mcp:read',))
        assert checking.check(meant, b'{"other":"body"}') is None  # bound to its body
        assert checking.check(meant, body) is not None
        assert checking.check(meant, body) is None  # and spent once
    finally:
        alice_local.stop()
        bob_local.stop()


def test_offline_then_connected_then_back_after_the_tunnel_drops(broker, tmp_path):
    _, browser = broker.person('alice')
    made = login(broker, browser, 'laptop')
    issued = host_sign_in(broker, browser, broker.issuer + '/mcp/laptop')
    host = Host(broker, issued['access_token'], '/mcp/laptop')
    _, said = host.post('tools/call', {'name': 'metaform_instructions', 'arguments': {}})
    assert said['result']['isError'] is True
    assert 'Your Metaform named laptop is not connected' in said['result']['content'][0]['text']
    assert host.post('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                    'clientInfo': {'name': 'h', 'version': '1'}})[1]['error']['code'] == -32050
    local = Local(tmp_path / 'work', made)
    try:
        host.initialize()
        assert host.post('tools/list')[0].status_code == 200
        local.connected.clear()
        held = broker.carrier.tunnels[(made.account, 'laptop')]
        _close_on_server(broker, held)
        assert local.connected.wait(15), local.states  # reconnected by itself
        assert any(one.get('state') == 'reconnecting' for one in local.states)
        host = Host(broker, issued['access_token'], '/mcp/laptop')
        host.initialize()
        assert host.post('tools/list')[0].status_code == 200
    finally:
        local.stop()


def first_account(made):
    return next(iter(made.carrier.tunnels))[0]


def _close_on_server(made, tunnel):
    loop = made.carrier.loop
    asyncio.run_coroutine_threadsafe(tunnel.close(1011, 'dropped'), loop).result(5)


def test_signing_out_everywhere_closes_the_tunnel_and_ends_every_token(broker, tmp_path):
    from metaform.modules.cloud.tunnel import Stopped
    _, browser = broker.person('alice')
    made = login(broker, browser)
    local = Local(tmp_path / 'work', made)
    try:
        issued = host_sign_in(broker, browser)
        page = browser.get('/account')
        assert 'default' in page.text  # connected now
        csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
        browser.post('/account/signout', data={'csrf': csrf}, headers={'Origin': broker.issuer})
        local.thread.join(10)
        assert isinstance(local.error, Stopped) and local.error.next_step == 'metaform cloud login'
        assert Host(broker, issued['access_token']).post('tools/list')[0].status_code == 401
        assert httpx.post(broker.issuer + '/oauth/token', data={
            'grant_type': 'refresh_token', 'client_id': CLIENT,
            'refresh_token': issued['refresh_token']}).json()['error'] == 'invalid_grant'
    finally:
        local.stop()


def test_a_newer_connection_for_the_same_instance_takes_its_place_only_when_the_person_says_so(broker, tmp_path):
    from metaform.modules.cloud import login as signing
    from metaform.modules.cloud.tunnel import Stopped
    _, browser = broker.person('alice')
    first = Local(tmp_path / 'work', login(broker, browser))
    with httpx.Client(timeout=10) as client:  # approving another machine as "default" while it is connected
        started = signing.start(broker.issuer, 'default', client, device_name='other-machine')
        page = browser.get('/device', params={'user_code': started.user_code})
        assert 'is connected now' in page.text and 'name="replace"' in page.text
        csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
        unticked = browser.post('/device', data={'user_code': started.user_code, 'csrf': csrf, 'decision': 'approve'},
                                headers={'Origin': broker.issuer})
        assert unticked.status_code == 409 and 'Approving disconnects it' in unticked.text
        assert first.thread.is_alive() and broker.carrier.connected(first_account(broker), 'default')
    second = Local(tmp_path / 'work', login(broker, browser, replace=True))
    try:
        first.thread.join(10)
        assert isinstance(first.error, Stopped) and 'took its place' in str(first.error)
        assert second.thread.is_alive()
    finally:
        first.stop()
        second.stop()


def test_a_request_too_large_for_the_tunnel_is_refused_at_the_broker(tmp_path, home, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', request=4096)
    try:
        _, browser = made.person('alice')
        local = Local(work, login(made, browser))
        try:
            host = Host(made, host_sign_in(made, browser)['access_token'])
            host.initialize()
            answer, _ = host.post('tools/call', {'name': 'metaform_feedback', 'arguments': {'text': 'x' * 8192}})
            assert answer.status_code == 413
            assert not any('x' * 8192 in json.dumps(one) for one in local.seen)
        finally:
            local.stop()
    finally:
        made.stop()


def test_a_long_answer_flows_whole_under_a_small_credit_window(tmp_path, home, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', credit=512)
    try:
        _, browser = made.person('alice')
        local = Local(work, login(made, browser))
        try:
            host = Host(made, host_sign_in(made, browser)['access_token'])
            host.initialize()
            answer, said = host.post('tools/list')
            assert len(answer.content) > 8 * 512  # many windows' worth, each granted back as the host read it
            assert {'search', 'fetch'} <= {tool['name'] for tool in said['result']['tools']}
        finally:
            local.stop()
    finally:
        made.stop()


def test_a_tunnel_opens_only_with_the_key_its_token_is_bound_to_and_never_from_a_browser(broker, tmp_path):
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    from metaform import frames
    from metaform.modules.cloud.login import new_key, proof, refresh
    _, browser = broker.person('alice')
    made = login(broker, browser)

    async def attempt(key, origin=None):
        async with httpx.AsyncClient() as client:
            access, _ = await refresh(made, client)
        headers = {'Authorization': f'DPoP {access}', 'DPoP': proof(key, 'GET', made.tunnel_url, access)}
        if origin:
            headers['Origin'] = origin
        try:
            async with connect(made.socket_url, additional_headers=headers, subprotocols=[frames.SUBPROTOCOL],
                               open_timeout=5) as socket:
                await socket.recv()
        except ConnectionClosed as closed:
            return closed.rcvd.code if closed.rcvd else None
        except InvalidStatus as refused:
            return refused.response.status_code
    assert asyncio.run(attempt(new_key())) == frames.INVALID_TOKEN  # a copied token without its key
    assert asyncio.run(attempt(made.key, origin='https://evil.example')) == 403  # no web page opens a tunnel


def test_a_held_open_stream_is_kept_alive_and_ends_on_both_sides_when_the_host_leaves(tmp_path, home, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', keepalive=0.3)
    try:
        _, browser = made.person('alice')
        local = Local(work, login(made, browser))
        try:
            host = Host(made, host_sign_in(made, browser)['access_token'])
            host.initialize()
            headers = {'Authorization': f'Bearer {host.token}', 'Accept': 'text/event-stream',
                       'Mcp-Session-Id': host.session, 'MCP-Protocol-Version': '2025-11-25'}
            with httpx.stream('GET', host.url, headers=headers, timeout=10) as answer:
                assert answer.status_code == 200 and answer.headers['content-type'].startswith('text/event-stream')
                for line in answer.iter_lines():
                    if line.startswith(': keep-alive'):
                        break
                assert sum(made.carrier.open_streams.values()) == 1
            deadline = time.time() + 10
            while (sum(made.carrier.open_streams.values()) or local.serving) and time.time() < deadline:
                time.sleep(0.1)
            assert sum(made.carrier.open_streams.values()) == 0 and local.serving == 0  # the app was told and ended
        finally:
            local.stop()
    finally:
        made.stop()


# ---------------------------------------------------------------------------------------------------- hardening

class Rogue:
    """A machine that speaks the tunnel by hand and answers each request as `answer(socket, header)` says, credit or
    no credit: what a malicious local service could do to the broker."""

    def __init__(self, made, answer):
        from metaform import frames
        self.closed = None
        self.ready = threading.Event()

        async def run():
            from websockets.asyncio.client import connect
            from websockets.exceptions import ConnectionClosed

            from metaform.modules.cloud.login import proof, refresh
            async with httpx.AsyncClient() as client:
                access, _ = await refresh(made, client)
            headers = {'Authorization': f'DPoP {access}', 'DPoP': proof(made.key, 'GET', made.tunnel_url, access)}
            async with connect(made.socket_url, additional_headers=headers, subprotocols=[frames.SUBPROTOCOL],
                               max_size=4 * 1024 * 1024) as socket:
                await socket.send(frames.pack({'type': 'hello', 'version': 1, 'instance': made.instance,
                                               'allows': ['mcp:read', 'mcp:write']}))
                await socket.recv()
                self.ready.set()
                try:
                    while True:
                        header, _ = frames.unpack(await socket.recv())
                        if header['type'] == 'open':
                            await answer(socket, header)
                except ConnectionClosed as closed:
                    self.closed = closed.rcvd.code if closed.rcvd else 1006
        self.thread = threading.Thread(target=lambda: asyncio.run(run()), daemon=True)
        self.thread.start()
        assert self.ready.wait(10)


def test_a_machine_that_ignores_credit_is_disconnected_and_fills_no_memory_past_its_window(tmp_path, home,
                                                                                           monkeypatch):
    from metaform import frames
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', credit=64 * 1024)
    try:
        _, browser = made.person('mallory')
        creds = login(made, browser)
        peak = []

        async def flood(socket, header):
            number = header['stream']
            await socket.send(frames.pack({'type': 'head', 'stream': number, 'status': 200,
                                           'headers': {'content-type': 'text/event-stream'}}))
            for _ in range(50):  # 50 MiB offered, ignoring the 64 KiB window
                await socket.send(frames.pack({'type': 'data', 'stream': number}, b'x' * 1024 * 1024))
                held = [tunnel.buffered for tunnel in made.carrier.tunnels.values()]
                peak.append(max(held or [0]))
        rogue = Rogue(creds, flood)
        token = host_sign_in(made, browser)['access_token']
        with httpx.stream('GET', made.issuer + '/mcp', headers={'Authorization': f'Bearer {token}'}, timeout=10):
            rogue.thread.join(10)
        assert rogue.closed == frames.TOO_LARGE  # disconnected at the first byte past its credit
        assert max(peak or [0]) <= 64 * 1024 and not made.carrier.tunnels
    finally:
        made.stop()


def test_a_bad_head_or_answers_past_the_tunnels_hold_are_502_and_give_their_stream_back(tmp_path, home, monkeypatch):
    from metaform import frames
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', buffered=100 * 1024)
    try:
        _, browser = made.person('alice')
        creds = login(made, browser)
        sent = []

        async def answer(socket, header):
            number = header['stream']
            if not sent:  # first a head whose status is not a number
                sent.append(number)
                await socket.send(frames.pack({'type': 'head', 'stream': number, 'status': 'abc', 'headers': {}}))
                return
            await socket.send(frames.pack({'type': 'head', 'stream': number, 'status': 200,
                                           'headers': {'content-type': 'application/json'}}))
            for _ in range(3):  # within credit, but more than this tunnel may hold at once
                await socket.send(frames.pack({'type': 'data', 'stream': number}, b'x' * 60 * 1024))
            await socket.send(frames.pack({'type': 'end', 'stream': number}))
        Rogue(creds, answer)
        host = Host(made, host_sign_in(made, browser)['access_token'])
        assert host.post('tools/list')[0].status_code == 502
        answer = host.post('tools/list')[0]
        assert answer.status_code == 502 and 'larger than 102400 bytes' in answer.json()['error']['message']
        tunnel = next(iter(made.carrier.tunnels.values()))
        assert not tunnel.streams and tunnel.buffered == 0  # nothing kept, every slot free
        assert tunnel.slots._value == made.carrier.limits.streams
    finally:
        made.stop()


JULY = '2026-07-28'


def july_request(token, method, number):
    body = {'jsonrpc': '2.0', 'id': number, 'method': method, 'params': {'_meta': {
        'io.modelcontextprotocol/protocolVersion': JULY, 'io.modelcontextprotocol/clientCapabilities': {},
        'io.modelcontextprotocol/clientInfo': {'name': 'host', 'version': '1'}}}}
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json, text/event-stream',
               'Content-Type': 'application/json', 'MCP-Protocol-Version': JULY, 'Mcp-Method': method}
    return body, headers


def test_listen_streams_are_counted_and_never_hold_the_slots_requests_wait_for(tmp_path, home, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', streams=1, streams_per_client=2)
    try:
        _, browser = made.person('alice')
        local = Local(work, login(made, browser))
        held = []
        try:
            token = host_sign_in(made, browser)['access_token']
            for number in range(2):
                body, headers = july_request(token, 'subscriptions/listen', 900 + number)
                body['params']['notifications'] = {'toolsListChanged': True}
                client = httpx.Client(timeout=30)
                answer = client.send(client.build_request('POST', made.issuer + '/mcp', json=body, headers=headers),
                                     stream=True)
                held.append((client, answer))
                assert answer.status_code == 200 and answer.headers['content-type'].startswith('text/event-stream')
            assert sum(made.carrier.open_streams.values()) == 2
            body, headers = july_request(token, 'subscriptions/listen', 903)
            assert httpx.post(made.issuer + '/mcp', json=body, headers=headers).status_code == 429  # the third
            began = time.time()
            body, headers = july_request(token, 'tools/list', 904)
            listed = httpx.post(made.issuer + '/mcp', json=body, headers=headers, timeout=30)
            assert listed.status_code == 200 and time.time() - began < 5  # the one request slot was free
        finally:
            for client, answer in held:
                answer.close()
                client.close()
            local.stop()
        deadline = time.time() + 10
        while made.carrier.open_streams and time.time() < deadline:
            time.sleep(0.1)
        assert not made.carrier.open_streams
    finally:
        made.stop()


def test_a_restarting_broker_tells_each_machine_to_wait_before_it_comes_back(tmp_path, home, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker')
    _, browser = made.person('alice')
    local = Local(work, login(made, browser))
    try:
        made.stop()
        deadline = time.time() + 10
        while not any(one.get('state') == 'reconnecting' for one in local.states) and time.time() < deadline:
            time.sleep(0.05)
        first = next(one for one in local.states if one.get('state') == 'reconnecting')
        assert first['code'] == 1000 and first['in_seconds'] >= 1.0  # goaway arrived, and its delay was kept
    finally:
        local.stop()


def test_a_revoked_signing_key_stops_the_machine_and_its_key_set_is_replaced_from_ready(tmp_path, home, monkeypatch):
    from metaform.modules.cloud import login as signing
    from metaform.modules.cloud.tunnel import Connection, Stopped
    from metaform.modules.node import tokens
    monkeypatch.setattr(tokens, 'RELOAD_SECONDS', 0.0)
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker', watch=0.2)
    try:
        _, browser = made.person('alice')
        creds = login(made, browser)
        old = {one['kid'] for one in creds.jwks['keys']}
        local = Local(work, creds)
        try:
            issued = host_sign_in(made, browser)
            tokens.Keys(tmp_path / 'broker' / 'keys').rotate(revoke_old=True)  # the operator, in another process
            local.thread.join(15)
            assert isinstance(local.error, Stopped) and local.error.next_step == 'metaform cloud login'
            assert Host(made, issued['access_token']).post('tools/list')[0].status_code == 401
        finally:
            local.stop()
        saved = signing.load()
        Connection(saved, None, None, allows=()).adopt({'type': 'ready', 'keys': made.carrier.signed.signer.keys.jwks()})
        kept = {one['kid'] for one in signing.load().jwks['keys']}
        assert kept and not kept & old  # replaced whole: the revoked key is no longer trusted here
    finally:
        made.stop()


def test_this_machines_clock_may_be_off_the_brokers(tmp_path, home, monkeypatch):
    from metaform.modules.cloud import login as signing
    from metaform.modules.cloud import tunnel
    from metaform.modules.node import tokens
    work = tmp_path / 'work'
    work.mkdir()
    monkeypatch.chdir(work)
    made = Broker(tmp_path / 'broker')
    try:
        _, browser = made.person('alice')
        creds = login(made, browser)
        body = b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
        ahead = time.time() + 120  # the broker's clock two minutes ahead of this machine's
        statement = made.carrier.signed.signer.mint(tokens.ASSERTION, {
            'sub': creds.account, 'aud': creds.resource, 'client_id': CLIENT, 'scope': 'mcp:read',
            'bh': tokens.body_hash(body)}, 60, now=ahead)
        unaware = tunnel.asserted(creds, ('mcp:read',))
        assert unaware.check(statement, body) is None and 115 < unaware.late < 125  # refused, and why
        connection = tunnel.Connection(creds, None, None, allows=())
        connection.adopt({'type': 'ready', 'now': ahead})  # the offset the broker's ready gives
        assert tunnel.asserted(creds, ('mcp:read',)).check(statement, body) is not None
        status, said = connection.clock_refusal(b'{"jsonrpc":"2.0","id":3,"method":"tools/call"}', 120)
        assert status == 200 and 'clock is 120 seconds off' in json.loads(said)['result']['content'][0]['text']
        # A DPoP proof dated by the broker's clock is accepted though this machine's is off.
        endpoint = made.issuer + '/oauth/token'
        late = signing.proof(creds.key, 'POST', endpoint, skew=-300)
        assert tokens.dpop_key(late, 'POST', endpoint, tokens.Replay()) is None
        corrected = signing.proof(creds.key, 'POST', endpoint, skew=0.0)
        assert tokens.dpop_key(corrected, 'POST', endpoint, tokens.Replay()) is not None
        creds.skew = 0.0
        access, _ = asyncio.run(_refresh(creds))
        creds.skew = 90.0  # tokens read on the broker's time: one issued "in the future" by this clock is fine
        assert signing.read_access(creds, access)['sub'] == creds.account
    finally:
        made.stop()


async def _refresh(made):
    from metaform.modules.cloud.login import refresh
    async with httpx.AsyncClient() as client:
        return await refresh(made, client)


def test_a_login_approved_by_an_account_the_person_does_not_confirm_is_revoked_and_not_kept(broker):
    from metaform.module import Stop
    from metaform.modules.cloud import login as signing
    _, browser = broker.person('mallory')  # approves a code that is not hers
    shown = []
    with pytest.raises(Stop, match='mallory'):
        login(broker, browser, confirm=lambda account: shown.append(account) or False)
    assert shown == ['mallory'] and signing.load() is None
    assert not broker.carrier.tunnels
