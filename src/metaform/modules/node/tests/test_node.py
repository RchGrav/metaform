"""The Metaform Node: the files init writes, the refusal to serve beyond this machine without an authorization
server, the authorization server's protocol, the scope gate, the relay's gate, and the deploy plan in --dry-run.
Nothing here reaches the network: Vultr and client metadata documents answer from recorded fixtures through httpx's
MockTransport, and no test starts an agent, a container or a server process."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
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
