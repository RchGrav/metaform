"""The Metaform Node: the files init writes, the refusal to serve beyond this machine without an authorization
server, the authorization server's protocol, the scope gate, the relay's gate, and the deploy plan in --dry-run.
Nothing here reaches the network: Vultr and client metadata documents answer from recorded fixtures through httpx's
MockTransport, and no test starts an agent, a container or a server process."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import urllib.parse

import httpx
import pytest

pytestmark = pytest.mark.kind('fixture')

DOMAIN = 'metaform.example.com'
ISSUER = f'https://{DOMAIN}'
CLIENT = 'https://client.example.org/oauth/metadata.json'
REDIRECT = 'http://127.0.0.1/callback'


def spec(**given):
    from metaform.modules.node.config import NodeSpec
    return NodeSpec(**{'domain': DOMAIN, 'email': 'owner@example.com', 'projects': ('/srv/work/app',), **given})


# ---------------------------------------------------------------------------------------------------- config

def test_only_caddy_listens_and_the_page_passes_the_session_gate_first():
    from metaform.modules.node import config
    made = config.compose(spec())
    services = made['services']
    assert services['caddy']['ports'] == ['80:80', '443:443', '443:443/udp']
    for name in ('auth', 'mcp', 'web'):
        assert services[name]['network_mode'] == 'service:caddy' and 'ports' not in services[name]
        assert services[name]['read_only'] is True and services[name]['cap_drop'] == ['ALL']
    command = services['mcp']['command']
    assert command[command.index('--mcp-bind') + 1] == '127.0.0.1'
    assert command[command.index('--mcp-public-url') + 1] == ISSUER
    assert 'metaform disable dispatch' in services['mcp']['entrypoint'][2]  # write: no agent is started here
    assert '/srv/work/app:/srv/projects/app' in services['mcp']['volumes']
    caddy = config.caddyfile(spec())
    page = caddy[caddy.index('\thandle {'):]
    assert page.index('respond @foreign 403') < page.index('forward_auth 127.0.0.1:7435') \
        < page.index('reverse_proxy 127.0.0.1:7433')
    assert 'uri /node/gate' in page
    before = caddy[:caddy.index('\thandle {')]  # discovery and sign-in answer before any credential
    assert '/.well-known/oauth-authorization-server' in before and '/.well-known/oauth-protected-resource' in before
    assert '/.well-known/agent-card.json' in before and 'forward_auth' not in before
    # who is calling is the gate's word only, and the page server gets the browser's own Host and Origin
    for name in ('Account', 'Role', 'Classes', 'Gate'):
        assert page.index(f'request_header -X-Metaform-{name}') < page.index('forward_auth')
    assert 'copy_headers X-Metaform-Account X-Metaform-Role X-Metaform-Classes' in page
    assert 'header_up X-Metaform-Gate {env.METAFORM_GATE_SECRET}' in page
    assert 'header_up Host' not in caddy and 'request_header @origin' not in caddy
    gate = {'path': './gate.env', 'required': True}
    assert services['caddy']['env_file'] == services['web']['env_file'] == [gate]
    assert 'env_file' not in services['mcp'] and 'env_file' not in services['auth']
    assert services['web']['command'][-2:] == ['--origin', ISSUER]


def test_dispatch_keeps_its_module_and_relay_and_dns_modes_change_only_how_tls_is_had():
    from metaform.modules.node import config
    assert 'entrypoint' not in config.compose(spec(capability='dispatch'))['services']['mcp']
    relayed = spec(domain='alice.metaform.ing', mode='relay', relay_server='relay.metaform.ing', relay_name='alice')
    made = config.compose(relayed)
    assert 'ports' not in made['services']['caddy'] and 'frpc' in made['services']
    assert 'disable_http_challenge' in config.caddyfile(relayed) and 'protocols h1 h2\n' in config.caddyfile(relayed)
    frpc = config.frpc_toml(relayed)
    assert 'type = "https"' in frpc and 'subdomain = "alice"' in frpc and '.Envs.METAFORM_RELAY_TOKEN' in frpc
    managed = spec(domain='alice.metaform.ing', mode='dns', dns_provider='vultr', wildcard='metaform.ing')
    files = config.files(managed, None)
    assert 'caddy-dns/vultr' in files['caddy/Dockerfile']
    assert '*.metaform.ing {' in files['Caddyfile'] and '@this host alice.metaform.ing' in files['Caddyfile']
    assert 'dns vultr {env.DNS_API_TOKEN}' in files['Caddyfile']


def test_init_refuses_what_cannot_be_served_safely():
    from metaform.modules.node import config
    assert config.problems(spec()) == []
    assert config.problems(spec(domain='203.0.113.9'))  # an address cannot hold a passkey's relying party
    assert config.problems(spec(email=''))
    assert config.problems(spec(capability='root'))
    assert config.problems(spec(mode='relay', relay_server='relay.metaform.ing', relay_name='www',
                                domain='www.metaform.ing'))  # reserved for the operator
    assert config.problems(spec(projects=('relative/path',)))


def test_yaml_quotes_every_string_so_nothing_is_read_as_another_type():
    from metaform.modules.node.config import to_yaml
    assert to_yaml({'a': ['443:443', 'yes', 'null'], 'b': {}, 'c': True}) == \
        'a:\n  - "443:443"\n  - "yes"\n  - "null"\nb: {}\nc: true\n'


def test_the_owner_invite_travels_as_a_hash_and_the_link_carries_it_in_the_fragment():
    from metaform.modules.node import config
    secret, record = config.owner_invite(spec(owner='rich'))
    assert record['sha256'] == hashlib.sha256(secret.encode()).hexdigest() and secret not in json.dumps(record)
    assert config.setup_link(ISSUER, secret) == f'{ISSUER}/node/setup#invite={secret}'


# ---------------------------------------------------------------------------------------------------- exposure

def test_a_server_beyond_this_machine_refuses_to_start_without_its_authorization_server():
    from metaform.module import Stop
    from metaform.modules.mcp import oauth
    assert oauth.exposure('', '127.0.0.1') is None  # the local server it always was
    with pytest.raises(Stop, match='no authorization server'):
        oauth.exposure('', '0.0.0.0')
    with pytest.raises(Stop, match='https origin'):
        oauth.exposure('http://metaform.example.com', '127.0.0.1', credential=lambda: 'x')
    with pytest.raises(Stop, match='has not started'):
        oauth.exposure(ISSUER, '127.0.0.1', credential=lambda: None)
    found = oauth.exposure(ISSUER + '/', '0.0.0.0', credential=lambda: 'secret')
    assert found is not None and found.mcp == ISSUER + '/mcp' and found.a2a == ISSUER + '/a2a'


def test_a_tool_call_short_of_its_scope_is_challenged_to_step_up():
    from starlette.authentication import AuthCredentials

    from metaform.modules.mcp import oauth
    assert oauth.required_scope('map_where', 'read', False) == oauth.READ
    assert oauth.required_scope('memory_add', 'write', False) == oauth.WRITE
    assert oauth.required_scope('dispatch_start', 'write', True) == oauth.DISPATCH
    reached = []

    async def app(scope, receive, send):
        reached.append((await receive())['body'])
    gate = oauth.ScopeGate(app, lambda name: {'memory_add': oauth.WRITE}.get(name), ISSUER + '/.well-known/x')
    sent = []

    async def send(message):
        sent.append(message)

    def call(name, scopes):
        body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name}}).encode()
        messages = iter([{'type': 'http.request', 'body': body, 'more_body': False}])

        async def receive():
            return next(messages)
        asyncio.run(gate({'type': 'http', 'method': 'POST', 'user': object(), 'auth': AuthCredentials(scopes)},
                         receive, send))
    call('memory_add', ['mcp:read'])
    assert sent[0]['status'] == 403
    challenge = dict(sent[0]['headers'])[b'www-authenticate'].decode()
    assert 'error="insufficient_scope"' in challenge and 'scope="mcp:write"' in challenge
    assert 'resource_metadata=' in challenge and not reached
    call('memory_add', ['mcp:read', 'mcp:write'])
    assert reached and b'memory_add' in reached[0]  # the body is handed on unchanged


# ---------------------------------------------------------------------------------------------------- the server

def document(**over):
    return {'client_id': CLIENT, 'client_name': 'Example Agent', 'redirect_uris': [REDIRECT],
            'grant_types': ['authorization_code', 'refresh_token'], 'token_endpoint_auth_method': 'none', **over}


def server(tmp_path, capability='write', served=None):
    from metaform.modules.node.authserver import Node, Policy
    from metaform.modules.node.authstore import AuthStore

    def answer(request):
        assert str(request.url) == CLIENT
        return httpx.Response(200, json=served or document(), headers={'Cache-Control': 'max-age=300'})
    store = AuthStore(tmp_path / 'auth.sqlite')
    node = Node(store, Policy(ISSUER, capability), transport=httpx.MockTransport(answer))
    return node, store


def client_for(node):
    from starlette.testclient import TestClient
    return TestClient(node.app(), base_url=ISSUER, follow_redirects=False)


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    return verifier, challenge


def signed_in(store, web):
    account = store.add_account('rich', 'owner')
    session, _ = store.open_session(account, 3600)
    web.cookies.set('__Host-metaform-session', session, domain=DOMAIN)
    return account


def authorize(web, challenge, **extra):
    params = {'response_type': 'code', 'client_id': CLIENT, 'redirect_uri': REDIRECT + '', 'state': 's1',
              'code_challenge': challenge, 'code_challenge_method': 'S256', **extra}
    params = {key: value for key, value in params.items() if value is not None}
    return web.get('/oauth/authorize', params=params)


def approve(web, held):
    page = web.get(held)
    assert page.status_code == 200 and 'Example Agent' in page.text and 'localhost' in page.text
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    request_id = page.text.split('name="request" value="')[1].split('"')[0]
    return web.post('/node/consent', data={'request': request_id, 'csrf': csrf, 'decision': 'approve'},
                    headers={'Origin': ISSUER})


def test_metadata_says_what_the_july_specification_asks(tmp_path):
    node, _ = server(tmp_path, capability='read')
    meta = client_for(node).get('/.well-known/oauth-authorization-server').json()
    assert meta['issuer'] == ISSUER and meta['code_challenge_methods_supported'] == ['S256']
    assert meta['client_id_metadata_document_supported'] is True
    assert meta['authorization_response_iss_parameter_supported'] is True
    assert 'registration_endpoint' not in meta  # deprecated DCR is off unless the owner turns it on
    assert meta['scopes_supported'] == ['mcp:read']  # read grants nothing more


def test_a_metadata_document_client_signs_in_and_gets_a_token_bound_to_the_resource(tmp_path, home):
    from metaform.modules.node import authserver
    node, store = server(tmp_path)
    web = client_for(node)
    signed_in(store, web)
    verifier, challenge = pkce()
    answer = authorize(web, challenge, redirect_uri='http://127.0.0.1:53111/callback', resource=ISSUER + '/mcp',
                       scope='mcp:read mcp:write mcp:dispatch')  # loopback: any port, RFC 8252
    assert answer.status_code == 302 and answer.headers['location'].startswith(ISSUER + '/node/consent?request=')
    back = approve(web, answer.headers['location'])
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(back.headers['location']).query)
    assert back.headers['location'].startswith('http://127.0.0.1:53111/callback?')
    assert query['iss'] == [ISSUER] and query['state'] == ['s1']
    form = {'grant_type': 'authorization_code', 'code': query['code'][0], 'client_id': CLIENT,
            'redirect_uri': 'http://127.0.0.1:53111/callback', 'code_verifier': verifier, 'resource': ISSUER + '/mcp'}
    tokens = web.post('/oauth/token', data=form).json()
    assert tokens['scope'] == 'mcp:read mcp:write'  # dispatch is not this Node's to grant at write
    assert web.post('/oauth/token', data=form).json()['error'] == 'invalid_grant'  # a code works once
    authserver.introspection_secret(create=True)
    basic = base64.b64encode(f'{authserver.RESOURCE_SERVER}:{authserver.introspection_secret()}'.encode()).decode()
    looked = web.post('/oauth/introspect', data={'token': tokens['access_token']},
                      headers={'Authorization': f'Basic {basic}'}).json()
    assert looked['active'] is False  # the code's reuse revoked what it gave, OAuth 2.1 section 4.1.3
    assert web.post('/oauth/introspect', data={'token': 'x'}).status_code == 401


def test_refresh_tokens_rotate_and_a_reused_one_ends_the_family(tmp_path, home):
    from metaform.modules.node import authserver
    node, store = server(tmp_path)
    web = client_for(node)
    signed_in(store, web)
    verifier, challenge = pkce()
    back = approve(web, authorize(web, challenge, resource=ISSUER + '/a2a').headers['location'])
    code = urllib.parse.parse_qs(urllib.parse.urlsplit(back.headers['location']).query)['code'][0]
    first = web.post('/oauth/token', data={'grant_type': 'authorization_code', 'code': code, 'client_id': CLIENT,
                                           'redirect_uri': REDIRECT, 'code_verifier': verifier}).json()
    assert first['scope'] == 'a2a:tickets'  # A2A's own audience and scope, apart from MCP's
    refresh = {'grant_type': 'refresh_token', 'refresh_token': first['refresh_token'], 'client_id': CLIENT}
    second = web.post('/oauth/token', data=refresh).json()
    assert second['access_token'] != first['access_token']
    assert web.post('/oauth/token', data=refresh).json()['error'] == 'invalid_grant'
    authserver.introspection_secret(create=True)
    assert node.provider.introspect(second['access_token']) == {'active': False}


def test_a_token_for_another_server_or_an_unknown_client_is_refused(tmp_path):
    node, store = server(tmp_path)
    web = client_for(node)
    signed_in(store, web)
    _, challenge = pkce()
    elsewhere = authorize(web, challenge, resource='https://other.example.com/mcp')
    assert elsewhere.status_code == 302 and 'error=invalid_request' in elsewhere.headers['location']
    assert 'iss=' in elsewhere.headers['location']  # errors carry iss too, RFC 9207
    bad, _ = server(tmp_path / 'b', served=document(client_id='https://evil.example.org/x.json'))
    assert authorize(client_for(bad), challenge).status_code == 400  # the document must name its own URL


def test_the_gate_lets_a_session_through_and_sends_a_page_load_to_sign_in(tmp_path):
    node, store = server(tmp_path)
    web = client_for(node)
    page = web.get('/node/gate', headers={'Accept': 'text/html', 'X-Forwarded-Uri': '/map?x=1'})
    assert page.status_code == 302 and page.headers['location'] == '/node/signin?next=%2Fmap%3Fx%3D1'
    assert web.get('/node/gate', headers={'X-Forwarded-Uri': '//evil.example'}).status_code == 401
    signed_in(store, web)
    assert web.get('/node/gate').headers['x-metaform-account'] == 'rich'


def test_a_second_non_owner_account_is_refused_every_owner_route(tmp_path, home):
    """C1: behind the Node's gate the page server takes who is calling only from Caddy, by the per-deploy secret, and
    serves each route only to an account whose classes, which the gate gives, include the route's class. A member
    reads, writes at write capability only, and is refused every admin route, the page's home-global workspace
    settings among them; dispatch needs a Node at dispatch; a request that did not come through the gate, or names
    another host, is refused whatever it claims."""
    import http.client
    import threading

    from metaform.modules.node.config import page_classes
    from metaform.modules.web import server as page_server
    assert page_classes('read', 'member') == ('read',)
    assert page_classes('read', 'owner') == ('read', 'admin')
    node, store = server(tmp_path)  # capability write
    heard = {}
    for name, role in (('rich', 'owner'), ('bob', 'member')):
        web = client_for(node)
        session, _ = store.open_session(store.add_account(name, role), 3600)
        web.cookies.set('__Host-metaform-session', session, domain=DOMAIN)
        answer = web.get('/node/gate')
        assert answer.headers['x-metaform-account'] == name and answer.headers['x-metaform-role'] == role
        heard[name] = {key: answer.headers[key] for key in ('x-metaform-account', 'x-metaform-classes')}
    assert heard['bob']['x-metaform-classes'] == 'read write'
    assert heard['rich']['x-metaform-classes'] == 'read write admin'
    page = page_server.Server('127.0.0.1', 0, 'nonce', origin=ISSUER, gate='gate-secret')
    threading.Thread(target=page.serve_forever, daemon=True).start()

    def call(path, account=None, method='POST', gate='gate-secret', host=DOMAIN, body=b'{}'):
        connection = http.client.HTTPConnection('127.0.0.1', page.server_address[1], timeout=30)
        headers = {'Host': host, 'Origin': ISSUER, 'Content-Type': 'application/json', 'X-Metaform-Gate': gate,
                   **(heard[account] if account else {})}
        try:
            connection.request(method, path, body=body if method == 'POST' else None, headers=headers)
            reply = connection.getresponse()
            return reply.status, reply.read().decode()
        finally:
            connection.close()
    try:
        owner_routes = [('POST', path) for path in sorted(page_server.ADMIN_ROUTES)]
        owner_routes += [('GET', '/api/build/options'), ('GET', '/api/debug/prompts'), ('POST', '/api/not-classed')]
        for method, path in owner_routes:
            assert page_server.route_class(method, path) == 'admin', path
            status, body = call(path, 'bob', method)
            assert status == 403 and 'needs admin, which bob may not use' in body, (path, status, body)
        assert 'may not use' not in call('/api/settings', 'rich')[1]  # the owner passes; the body is then judged
        assert 'may not use' not in call('/api/note', 'bob')[1]  # a write is a member's too
        assert 'may not use' not in call('/api/settings', 'bob', 'GET')[1]  # reading the settings is a read
        assert 'may not use' not in call('/api/hints', 'bob')[1]  # each person keeps the tips they have seen
        assert 'may not use' not in call('/api/view', 'bob')[1]  # and the page's view, view.py
        for account in ('rich', 'bob'):  # dispatch is not this Node's at write, for anyone
            assert f'needs dispatch, which {account} may not use' in call('/api/dispatch-start', account)[1]
        from metaform.modules.web import view
        before = view.values('bob')
        for path in ('arrangement', 'reset', 'save', 'select', 'delete'):  # the owner's: the workspace routes
            status, body = call(f'/api/workspace/{path}', 'bob', body=json.dumps({'name': 'bob-was-here'}).encode())
            assert status == 403 and 'needs admin, which bob may not use' in body, (path, status, body)
        assert view.values('bob') == before
        heard['reader'] = {'x-metaform-account': 'bob', 'x-metaform-classes': ' '.join(page_classes('read', 'member'))}
        for path in ('/api/note', '/api/ignore'):  # at read capability a member only reads
            status, body = call(path, 'reader')
            assert status == 403 and 'needs write, which bob may not use' in body, (path, status, body)
        forged = {'x-metaform-account': 'bob', 'x-metaform-classes': 'read write dispatch admin'}
        heard['forged'] = forged
        assert call('/api/modules', 'forged', gate='guessed')[0] == 403  # not through Caddy: refused, whatever it says
        assert call('/api/modules', 'forged', gate='')[0] == 403
        assert call('/api/settings', 'rich', host='127.0.0.1:7433')[0] == 403  # Host is the public origin's only
    finally:
        page.shutdown()
        page.server_close()


def test_an_mcp_caller_cannot_change_the_five_hosting_settings(home, tmp_path):
    """H2: which folders a Node exposes, the host deploy reaches, the SSH key it uses, the key a created VM trusts
    for root, and the intake file every intake agent follows are the person's: MCP's set does not offer them and
    refuses them, stored or given for one call."""
    from metaform import loader
    from metaform.module import Stop
    from metaform.modules.mcp.server import refuse_person_only, set_schema
    loader.enabled()  # every module loaded, its settings declared, as the MCP server has them when it starts
    five = ('node_projects', 'node_host', 'node_ssh_identity', 'node_ssh_public_key', 'intake_file')
    for key in five:
        with pytest.raises(Stop, match=f'{key} is set only by the person'):
            refuse_person_only([key], tmp_path)
    assert not set(five) & set(set_schema(tmp_path)['properties'])


def test_the_auth_database_is_not_reachable_from_the_web_container(tmp_path, home, monkeypatch):
    """C1: the accounts, passkeys and keys live on the `auth` volume, which only the auth container mounts; the page
    and MCP containers, and every agent they start, share `home` without them. An older Node's accounts move there
    from the shared home on auth's first start, and the old copy is removed."""
    from metaform import home as homes
    from metaform.modules.node import authserver, config, write_project
    for made in (config.compose(spec()), config.compose(spec(role='broker', projects=()))):
        services = made['services']
        assert 'auth' in made['volumes']
        assert f'auth:{config.AUTH_IN_IMAGE}' in services['auth']['volumes']
        assert services['auth']['environment']['METAFORM_NODE_AUTH'] == config.AUTH_IN_IMAGE
        for name, service in services.items():
            if name == 'auth':
                continue
            mounts = service.get('volumes', [])
            assert not [one for one in mounts if one.split(':')[0] == 'auth' or config.AUTH_IN_IMAGE in one], name
    assert config.AUTH_IN_IMAGE in config.dockerfile()  # made the metaform user's in the image, so the volume is too
    old = homes.home() / 'node'
    (old / 'keys').mkdir(parents=True)
    (old / 'auth.sqlite').write_text('accounts', encoding='utf-8')
    (old / 'keys' / 'k1.json').write_text('key', encoding='utf-8')
    volume = tmp_path / 'auth-volume'
    monkeypatch.setenv(authserver.AUTH_FOLDER, str(volume))
    assert authserver.store_path() == volume / 'auth.sqlite' and authserver.keys_folder() == volume / 'keys'
    assert authserver.move_from_home() == ['auth.sqlite', 'keys']
    assert (volume / 'auth.sqlite').read_text(encoding='utf-8') == 'accounts' and (volume / 'keys' / 'k1.json').is_file()
    assert not old.exists() and authserver.move_from_home() == []
    folder = tmp_path / 'project'
    write_project(folder, spec())
    secret = (folder / config.GATE_FILE).read_text(encoding='utf-8')
    assert secret.startswith('METAFORM_GATE_SECRET=') and len(secret) > 40
    write_project(folder, spec())
    assert (folder / config.GATE_FILE).read_text(encoding='utf-8') == secret  # kept, so Caddy and the page agree
    if os.name != 'nt':
        assert (folder / config.GATE_FILE).stat().st_mode & 0o777 == 0o600


def test_a_setup_link_works_once_and_only_for_its_account(tmp_path):
    node, store = server(tmp_path)
    web = client_for(node)
    account = store.add_account('rich', 'owner')
    secret = store.invite(account)
    started = web.post('/node/passkey/register/options', json={'invite': secret}, headers={'Origin': ISSUER})
    options = started.json()['options']
    assert options['rp']['id'] == DOMAIN and options['authenticatorSelection']['residentKey'] == 'required'
    assert options['authenticatorSelection']['userVerification'] == 'required'
    assert web.post('/node/passkey/register/options', json={'invite': 'nope'},
                    headers={'Origin': ISSUER}).status_code == 403
    assert web.post('/node/passkey/register/options', json={'invite': secret},
                    headers={'Origin': 'https://evil.example'}).status_code == 403
    store.use_invite(secret)
    assert web.post('/node/passkey/register/options', json={'invite': secret},
                    headers={'Origin': ISSUER}).status_code == 403


def test_a_client_metadata_document_must_be_a_public_client_with_safe_redirects():
    from metaform.modules.node.authserver import _cimd_url, check_document
    assert check_document(CLIENT, document())['client_name'] == 'Example Agent'
    for wrong in (document(redirect_uris=['http://evil.example/cb']), document(token_endpoint_auth_method='client_secret_basic'),
                  document(client_name=''), ['not', 'an', 'object']):
        with pytest.raises(ValueError):
            check_document(CLIENT, wrong)
    assert not _cimd_url('https://client.example.org/') and not _cimd_url('http://client.example.org/x.json')


# ---------------------------------------------------------------------------------------------------- the relay

def test_the_relay_gate_admits_only_an_enrolled_name_under_its_own_name(tmp_path):
    from metaform.modules.node.tunnel import Enrolments, decide
    held = Enrolments(tmp_path / 'enrolments.json')
    secret = held.enrol('alice')
    enrolled = held.read()
    login = {'op': 'Login', 'content': {'user': 'alice', 'metas': {'token': secret}}}
    assert decide(login, enrolled) == {'reject': False, 'unchange': True}
    assert decide({'op': 'Login', 'content': {'user': 'alice', 'metas': {'token': 'x'}}}, enrolled)['reject']
    proxy = {'op': 'NewProxy', 'content': {'user': {'user': 'alice', 'metas': {'token': secret}},
                                           'proxy_type': 'https', 'subdomain': 'alice'}}
    assert decide(proxy, enrolled)['reject'] is False
    assert decide({**proxy, 'content': {**proxy['content'], 'subdomain': 'bob'}}, enrolled)['reject']
    assert decide({**proxy, 'content': {**proxy['content'], 'proxy_type': 'tcp'}}, enrolled)['reject']
    with pytest.raises(ValueError):
        held.enrol('relay')


# ---------------------------------------------------------------------------------------------------- deploy

def test_deploy_dry_run_prints_every_step_and_runs_none(run, tmp_path):
    made = run('node', 'init', DOMAIN, '--node-email', 'owner@example.com', cwd=tmp_path / 'here').stdout
    assert f'{ISSUER}/node/setup#invite=' in made
    folder = tmp_path / 'here' / 'metaform-node'
    assert {'compose.yaml', 'Caddyfile', 'Dockerfile', 'node.json'} <= {one.name for one in folder.iterdir()}
    assert 'sha256' in (folder / 'bootstrap' / 'owner-invite.json').read_text(encoding='utf-8')
    plan = run('node', 'deploy', '--dry-run', '--node-host', '203.0.113.9', cwd=tmp_path / 'here').stdout
    for expected in ('ssh -o BatchMode=yes', 'root@203.0.113.9', "'bash -s' < install.sh", 'metaform build kind=full',
                     'tar -C', "docker compose up -d --build", 'docker compose ps --format json',
                     f'GET {ISSUER}/mcp  -> 401'):
        assert expected in plan, expected
    assert not list((folder / 'wheels').glob('*.whl'))  # nothing was built: a dry run runs nothing


def test_the_host_script_is_idempotent_and_carries_the_hardening():
    from metaform.modules.node.plans import cloud_init, install_script
    script = install_script(relay_port=7000)
    assert script.startswith('#!/usr/bin/env bash') and 'set -euo pipefail' in script
    assert '"${ID:-}" != "ubuntu"' in script and 'fallocate -l 3G /swapfile' in script
    assert "grep -qE '^/swapfile[[:space:]]' /etc/fstab ||" in script  # never a second fstab line
    assert 'https://download.docker.com/linux/ubuntu' in script and 'pip install' not in script
    assert '/etc/sudoers.d/90-metaform' in script and '%sudo' not in script
    assert 'PasswordAuthentication no' in script and 'PermitRootLogin prohibit-password' in script
    assert 'ufw allow 7000/tcp' in script and 'fail2ban' in script and 'certbot' not in script
    assert cloud_init().startswith('#cloud-config\n') and '/usr/local/sbin/metaform-node-prepare' in cloud_init()


VULTR = {  # recorded answers, in the shapes Vultr's API v2 gives (govultr v3's structs)
    ('POST', '/v2/ssh-keys'): {'ssh_key': {'id': 'key-1', 'name': 'metaform-node', 'ssh_key': 'ssh-ed25519 AAA'}},
    ('POST', '/v2/firewalls'): {'firewall_group': {'id': 'fw-1', 'description': 'metaform-node'}},
    ('POST', '/v2/firewalls/fw-1/rules'): {'firewall_rule': {'id': 1}},
    ('POST', '/v2/instances'): {'instance': {'id': 'vm-1', 'status': 'pending', 'main_ip': '0.0.0.0'}},
    ('GET', '/v2/instances/vm-1'): {'instance': {'id': 'vm-1', 'status': 'active', 'server_status': 'ok',
                                                 'main_ip': '203.0.113.9', 'v6_main_ip': '2001:db8::9'}},
}


def test_vultr_provisioning_makes_the_recorded_calls_and_finds_the_address():
    from metaform.modules.node import vultr
    seen = []

    def answer(request):
        seen.append((request.method, request.url.path, json.loads(request.content or b'null'),
                     request.headers['authorization']))
        return httpx.Response(200 if request.method == 'GET' else 201, json=VULTR[(request.method, request.url.path)])
    steps = vultr.provision_steps(spec(), region='ewr', plan='vhf-1c-1gb', os_id=2284, public_key='ssh-ed25519 AAA',
                                  relay_port=7000, client=lambda: vultr.Vultr('test-key', httpx.MockTransport(answer)))
    shown = ''.join(step.shown for step in steps)
    assert 'POST https://api.vultr.com/v2/instances' in shown and '$VULTR_API_KEY' in shown and '#cloud-config' in shown
    state = {}
    for step in steps:
        state.update(step.run(state) or {})
    assert state['main_ip'] == '203.0.113.9'
    created = next(body for method, path, body, _ in seen if path == '/v2/instances')
    assert created['sshkey_id'] == ['key-1'] and created['firewall_group_id'] == 'fw-1'
    assert created['region'] == 'ewr' and created['os_id'] == 2284
    assert base64.b64decode(created['user_data']).decode().startswith('#cloud-config')
    rules = [body for method, path, body, _ in seen if path.endswith('/rules')]
    assert {(rule['protocol'], rule['port']) for rule in rules} == {('tcp', '22'), ('tcp', '80'), ('tcp', '443'),
                                                                     ('udp', '443'), ('tcp', '7000')}
    assert all(auth == 'Bearer test-key' for *_, auth in seen)


def test_mcp_accepts_only_a_live_token_issued_for_itself_by_its_own_issuer():
    from metaform.modules.mcp import oauth
    found = oauth.exposure(ISSUER, '127.0.0.1', credential=lambda: 'rs-secret')
    claims = {'tok-mcp': {'active': True, 'aud': ISSUER + '/mcp', 'iss': ISSUER, 'scope': 'mcp:read', 'sub': 'u1',
                          'client_id': CLIENT, 'exp': 4102444800},
              'tok-a2a': {'active': True, 'aud': ISSUER + '/a2a', 'iss': ISSUER, 'scope': 'a2a:tickets'},
              'tok-other': {'active': True, 'aud': ISSUER + '/mcp', 'iss': 'https://other.example', 'scope': 'mcp:read'}}

    def answer(request):
        assert request.headers['authorization'] == 'Basic ' + base64.b64encode(
            f'{oauth.RESOURCE_SERVER}:rs-secret'.encode()).decode()
        token = urllib.parse.parse_qs(request.content.decode())['token'][0]
        return httpx.Response(200, json=claims.get(token, {'active': False}))
    verifier = oauth.Introspection(found, found.mcp, transport=httpx.MockTransport(answer))
    accepted = asyncio.run(verifier.verify_token('tok-mcp'))
    assert accepted is not None and accepted.resource == ISSUER + '/mcp' and accepted.scopes == ['mcp:read']
    for refused in ('tok-a2a', 'tok-other', 'revoked'):
        assert asyncio.run(verifier.verify_token(refused)) is None, refused
