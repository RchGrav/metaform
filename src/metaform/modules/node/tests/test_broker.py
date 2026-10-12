"""The broker role's authorization server, in-process: the device grant's states, signed tokens checked with no store,
signing out everywhere, refresh rotation and reuse, the per-instance resource metadata, the offline answers, the limits,
and the store keeping nothing but accounts and passkeys. Nothing reaches the network: client metadata documents answer
from a MockTransport, and no server process is started (test_cloud.py runs the broker on loopback)."""
from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse

import httpx
import pytest

from metaform.data import private_database

pytestmark = pytest.mark.kind('fixture')

ISSUER = 'https://metaform.example.com'
CLIENT = 'https://client.example.org/oauth/metadata.json'
REDIRECT = 'https://client.example.org/callback'


def document():
    return {'client_id': CLIENT, 'client_name': 'Example Agent', 'redirect_uris': [REDIRECT],
            'grant_types': ['authorization_code', 'refresh_token'], 'token_endpoint_auth_method': 'none'}


def broker(tmp_path, **limits):
    from metaform.modules.node.authserver import Node, Policy
    from metaform.modules.node.authstore import BrokerStore
    from metaform.modules.node.broker import Broker, Limits
    from metaform.modules.node.tokens import Keys

    def answer(request):
        return httpx.Response(200, json=document(), headers={'Cache-Control': 'max-age=300'})
    store = BrokerStore(tmp_path / 'auth.sqlite')
    node = Node(store, Policy(ISSUER, 'write', broker=True), httpx.MockTransport(answer), keys=Keys(tmp_path / 'keys'))
    made = Broker(node, Limits(**limits))
    return made, store


def web(made, client=('testclient', 50000)):
    from starlette.testclient import TestClient
    return TestClient(made.app(), base_url=ISSUER, follow_redirects=False, client=client)


def sign_in(store, client, name='alice', role='owner'):
    account = store.add_account(name, role)
    session, _ = store.open_session(account, 3600)
    client.cookies.set('__Host-metaform-session', session, domain='metaform.example.com')
    return account


def pkce():
    verifier = secrets.token_urlsafe(48)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')


def host_tokens(client, resource=ISSUER + '/mcp', scope='mcp:read mcp:write'):
    verifier, challenge = pkce()
    held = client.get('/oauth/authorize', params={
        'response_type': 'code', 'client_id': CLIENT, 'redirect_uri': REDIRECT, 'state': 's',
        'code_challenge': challenge, 'code_challenge_method': 'S256', 'resource': resource, 'scope': scope})
    assert held.status_code == 302, held.text
    page = client.get(held.headers['location'])
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    request = page.text.split('name="request" value="')[1].split('"')[0]
    back = client.post('/node/consent', data={'request': request, 'csrf': csrf, 'decision': 'approve'},
                       headers={'Origin': ISSUER})
    code = urllib.parse.parse_qs(urllib.parse.urlsplit(back.headers['location']).query)['code'][0]
    return client.post('/oauth/token', data={'grant_type': 'authorization_code', 'code': code, 'client_id': CLIENT,
                                             'redirect_uri': REDIRECT, 'code_verifier': verifier,
                                             'resource': resource}).json()


def call(client, token, path='/mcp', method='tools/call', **extra):
    body = {'jsonrpc': '2.0', 'id': 7, 'method': method, 'params': {'name': 'map_where'}, **extra}
    return client.post(path, json=body, headers={'Authorization': f'Bearer {token}',
                                                 'Accept': 'application/json, text/event-stream'})


def dpop(key, method, url, token=None):
    from metaform.modules.cloud.login import proof
    return proof(key, method, url, token)


# ---------------------------------------------------------------------------------------------------- tokens

def test_the_store_keeps_accounts_and_passkeys_and_nothing_else(tmp_path):
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    host_tokens(client)
    tables = {row[0] for row in private_database(tmp_path / 'auth.sqlite').execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {'accounts', 'passkeys'}  # no sessions, codes, tokens, clients or challenges on disk
    assert {path.suffix for path in (tmp_path / 'keys').iterdir()} == {'.pem', '.json'}
    meta = client.get('/.well-known/oauth-authorization-server').json()
    assert meta['jwks_uri'] == ISSUER + '/.well-known/jwks.json'
    assert meta['device_authorization_endpoint'] == ISSUER + '/oauth/device_authorization'
    keys = client.get('/.well-known/jwks.json').json()['keys']
    assert keys and all(one['kty'] == 'OKP' and one['crv'] == 'Ed25519' and 'd' not in one for one in keys)


def test_a_host_token_is_signed_bound_to_its_instance_and_ends_when_the_account_signs_out(tmp_path):
    from metaform.modules.node import tokens
    made, store = broker(tmp_path)
    client = web(made)
    account = sign_in(store, client)
    issued = host_tokens(client, ISSUER + '/mcp/laptop')
    access = issued['access_token']
    assert issued['expires_in'] == tokens.ACCESS_SECONDS
    claims = made.signed.access(access, ISSUER + '/mcp/laptop')
    assert claims is not None and claims['sub'] == account.id and claims['scope'] == 'mcp:read mcp:write'
    assert made.signed.access(access, ISSUER + '/mcp') is None  # another instance's resource: refused
    assert call(client, access).status_code == 401  # the default instance is another resource
    offline = call(client, access, '/mcp/laptop').json()
    assert offline['result']['isError'] is True and 'metaform cloud connect' in offline['result']['content'][0]['text']
    client.get('/account')  # the page exists for a signed-in person
    page = client.get('/account')
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    assert client.post('/account/signout', data={'csrf': csrf}, headers={'Origin': ISSUER}).status_code == 200
    assert made.signed.access(access, ISSUER + '/mcp/laptop') is None
    refreshed = client.post('/oauth/token', data={'grant_type': 'refresh_token', 'client_id': CLIENT,
                                                  'refresh_token': issued['refresh_token']})
    assert refreshed.json()['error'] == 'invalid_grant'
    assert client.get('/account').status_code == 302  # the session ended too


def test_refresh_rotates_and_a_reused_refresh_token_ends_the_grant(tmp_path):
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    first = host_tokens(client)
    form = {'grant_type': 'refresh_token', 'client_id': CLIENT, 'refresh_token': first['refresh_token']}
    second = client.post('/oauth/token', data=form).json()
    assert second['refresh_token'] != first['refresh_token'] and made.signed.access(second['access_token'])
    assert client.post('/oauth/token', data=form).json()['error'] == 'invalid_grant'  # reused: a thief, or a fork
    later = client.post('/oauth/token', data={**form, 'refresh_token': second['refresh_token']}).json()
    assert later['error'] == 'invalid_grant'  # the whole grant ended for both holders
    assert made.signed.access(second['access_token']) is None


def test_a_second_use_of_an_authorization_code_is_refused(tmp_path):
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    verifier, challenge = pkce()
    held = client.get('/oauth/authorize', params={
        'response_type': 'code', 'client_id': CLIENT, 'redirect_uri': REDIRECT, 'state': 's',
        'code_challenge': challenge, 'code_challenge_method': 'S256'})
    page = client.get(held.headers['location'])
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    request = page.text.split('name="request" value="')[1].split('"')[0]
    assert 'default' in page.text and 'not connected now' in page.text  # the consent names the machine
    back = client.post('/node/consent', data={'request': request, 'csrf': csrf, 'decision': 'approve'},
                       headers={'Origin': ISSUER})
    code = urllib.parse.parse_qs(urllib.parse.urlsplit(back.headers['location']).query)['code'][0]
    form = {'grant_type': 'authorization_code', 'code': code, 'client_id': CLIENT, 'redirect_uri': REDIRECT,
            'code_verifier': verifier}
    first = client.post('/oauth/token', data=form).json()
    assert first['scope'] == 'mcp:read mcp:write'  # no resource asked: the default instance, dispatch left for step-up
    assert client.post('/oauth/token', data=form).json()['error'] == 'invalid_grant'
    assert made.signed.access(first['access_token']) is None  # what the first use gave is revoked


def test_revoking_one_grant_ends_it_while_the_broker_runs(tmp_path):
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    issued = host_tokens(client)
    assert client.post('/oauth/revoke', data={'token': issued['refresh_token'], 'client_id': CLIENT}).status_code == 200
    assert made.signed.access(issued['access_token']) is None


def test_a_member_is_never_granted_dispatch_unless_the_operator_allows_it(tmp_path):
    made, store = broker(tmp_path)
    client = web(made)
    from metaform.modules.node.authserver import Policy
    made.node.policy = made.policy = Policy(ISSUER, 'dispatch', broker=True)
    made.node.provider.policy = made.node.policy
    sign_in(store, client, 'bob', 'member')
    assert 'mcp:dispatch' not in host_tokens(client, scope='mcp:read mcp:write mcp:dispatch')['scope']


# ---------------------------------------------------------------------------------------------------- device grant

def test_the_device_grant_waits_slows_down_is_approved_and_binds_the_tokens_to_the_key(tmp_path):
    from metaform.modules.cloud.login import key_jwk, new_key
    from metaform.modules.node import tokens
    made, store = broker(tmp_path)
    client = web(made)
    account = sign_in(store, client)
    key = new_key()
    endpoint = ISSUER + '/oauth/device_authorization'
    assert client.post(endpoint, data={'client_id': 'metaform-cli'}).json()['error'] == 'invalid_dpop_proof'
    started = client.post(endpoint, data={'client_id': 'metaform-cli', 'scope': 'tunnel:connect',
                                          'instance': 'laptop', 'device_name': 'rich<script>'},
                          headers={'DPoP': dpop(key, 'POST', endpoint)}).json()
    assert started['interval'] == 5 and started['expires_in'] == 600 and len(started['user_code']) == 9
    token = ISSUER + '/oauth/token'
    form = {'grant_type': tokens.DEVICE_GRANT, 'device_code': started['device_code'], 'client_id': 'metaform-cli'}

    def poll(with_key=key):
        return client.post(token, data=form, headers={'DPoP': dpop(with_key, 'POST', token)}).json()
    assert poll()['error'] == 'authorization_pending'
    assert poll()['error'] == 'slow_down'  # polled again at once
    assert poll(new_key())['error'] == 'invalid_dpop_proof'  # another key cannot finish this sign-in
    page = client.get('/device', params={'user_code': started['user_code'].lower().replace('-', '')})
    assert page.status_code == 200 and 'laptop' in page.text and 'richscript' in page.text
    assert 'your own terminal' in page.text  # RFC 8628 section 5.4's warning
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    approved = client.post('/device', data={'user_code': started['user_code'], 'csrf': csrf, 'decision': 'approve'},
                           headers={'Origin': ISSUER})
    assert approved.status_code == 200
    made.node.device_grants.by_device[tokens.body_hash(started['device_code'].encode())].polled = 0
    issued = poll()
    assert issued['token_type'] == 'DPoP' and issued['scope'] == 'tunnel:connect'
    claims = made.signed.access(issued['access_token'], ISSUER + '/cloud/tunnel')
    assert claims['sub'] == account.id and claims['inst'] == 'laptop'
    assert claims['cnf']['jkt'] == tokens.thumbprint(key_jwk(key))
    assert poll()['error'] == 'expired_token'  # a device code is used once
    refresh = {'grant_type': 'refresh_token', 'client_id': 'metaform-cli', 'refresh_token': issued['refresh_token']}
    assert client.post(token, data=refresh).json()['error'] == 'invalid_dpop_proof'  # the token alone is useless
    assert client.post(token, data=refresh, headers={'DPoP': dpop(new_key(), 'POST', token)}).json()['error'] == \
        'invalid_dpop_proof'
    renewed = client.post(token, data=refresh, headers={'DPoP': dpop(key, 'POST', token)}).json()
    assert renewed['token_type'] == 'DPoP' and made.signed.access(renewed['access_token'], ISSUER + '/cloud/tunnel')


def test_a_denied_device_sign_in_is_refused_and_wrong_codes_lock_an_address_out(tmp_path):
    from metaform.modules.cloud.login import new_key
    from metaform.modules.node import tokens
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    key = new_key()
    endpoint = ISSUER + '/oauth/device_authorization'
    started = client.post(endpoint, data={'client_id': 'metaform-cli'},
                          headers={'DPoP': dpop(key, 'POST', endpoint)}).json()
    page = client.get('/device', params={'user_code': started['user_code']})
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    client.post('/device', data={'user_code': started['user_code'], 'csrf': csrf, 'decision': 'deny'},
                headers={'Origin': ISSUER})
    token = ISSUER + '/oauth/token'
    denied = client.post(token, data={'grant_type': tokens.DEVICE_GRANT, 'device_code': started['device_code'],
                                      'client_id': 'metaform-cli'}, headers={'DPoP': dpop(key, 'POST', token)})
    assert denied.json()['error'] == 'access_denied'
    for _ in range(10):
        client.get('/device', params={'user_code': 'BBBB-BBBB'})
    assert client.get('/device', params={'user_code': 'CCCC-CCCC'}).status_code == 429


def test_a_device_code_expires(tmp_path):
    from metaform.modules.cloud.login import new_key
    from metaform.modules.node import tokens
    made, _ = broker(tmp_path)
    client = web(made)
    key = new_key()
    endpoint = ISSUER + '/oauth/device_authorization'
    started = client.post(endpoint, data={'client_id': 'metaform-cli'},
                          headers={'DPoP': dpop(key, 'POST', endpoint)}).json()
    for held in made.node.device_grants.by_device.values():
        held.expires = time.time() - 1
    token = ISSUER + '/oauth/token'
    expired = client.post(token, data={'grant_type': tokens.DEVICE_GRANT, 'device_code': started['device_code'],
                                       'client_id': 'metaform-cli'}, headers={'DPoP': dpop(key, 'POST', token)})
    assert expired.json()['error'] == 'expired_token'


# ---------------------------------------------------------------------------------------------------- hosts

def test_each_instance_has_its_own_resource_metadata_and_a_401_names_it(tmp_path):
    made, _ = broker(tmp_path)
    client = web(made)
    assert client.get('/.well-known/oauth-protected-resource/mcp').json()['resource'] == ISSUER + '/mcp'
    named = client.get('/.well-known/oauth-protected-resource/mcp/laptop').json()
    assert named['resource'] == ISSUER + '/mcp/laptop' and named['authorization_servers'] == [ISSUER]
    refused = client.post('/mcp/laptop', json={})
    assert refused.status_code == 401
    assert 'resource_metadata="https://metaform.example.com/.well-known/oauth-protected-resource/mcp/laptop"' in \
        refused.headers['www-authenticate']
    assert client.post('/mcp/Not_A_Label', json={}).status_code == 404


def test_offline_answers_say_what_to_run_in_the_shape_each_request_can_carry(tmp_path):
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    access = host_tokens(client)['access_token']
    tool = call(client, access).json()
    assert tool['id'] == 7 and tool['result']['isError'] is True
    other = call(client, access, method='tools/list').json()
    assert other['error']['code'] == -32050 and other['error']['data'] == {
        'reason': 'offline', 'instance': 'default', 'next': 'metaform cloud connect'}
    note = client.post('/mcp', json={'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                       headers={'Authorization': f'Bearer {access}'})
    assert note.status_code == 503 and note.headers['retry-after'] == '30'
    assert client.get('/mcp', headers={'Authorization': f'Bearer {access}'}).status_code == 503


def test_payload_and_rate_limits(tmp_path):
    made, store = broker(tmp_path, request=1024, rate=0.001, burst=2)
    client = web(made)
    sign_in(store, client)
    access = host_tokens(client)['access_token']
    big = client.post('/mcp', content=b'x' * 2048, headers={'Authorization': f'Bearer {access}',
                                                             'Content-Type': 'application/json'})
    assert big.status_code == 413
    assert call(client, access).status_code == 200
    limited = call(client, access)
    assert limited.status_code == 429 and limited.headers['retry-after'] == '1'


def test_an_old_store_moves_its_invitations_onto_the_account_rows(tmp_path):
    from metaform.modules.node.authstore import AuthStore
    path = tmp_path / 'auth.sqlite'
    old = private_database(path)
    old.executescript("""
        CREATE TABLE accounts (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL, created REAL NOT NULL,
            disabled REAL);
        CREATE TABLE invites (hash TEXT PRIMARY KEY, account TEXT NOT NULL, expires REAL NOT NULL, used REAL);""")
    secret = 'old-secret'
    old.execute("INSERT INTO accounts VALUES ('a1', 'rich', 'owner', 0, NULL)")
    old.execute('INSERT INTO invites VALUES (?, ?, ?, NULL)', (hashlib.sha256(secret.encode()).hexdigest(), 'a1',
                                                              time.time() + 3600))
    old.commit()
    old.close()
    store = AuthStore(path)
    assert store.invited(secret).name == 'rich' and store.generation('a1') == (0, False)
    store.use_invite(secret)
    assert store.invited(secret) is None
    assert store.bump_generation('a1') == 1


def test_a_broker_runs_caddy_and_one_process_and_routes_hosts_and_machines_to_it(tmp_path):
    from metaform.modules.node import config
    spec = config.NodeSpec(domain='metaform.ing', email='ops@metaform.ing', role='broker')
    assert config.problems(spec) == []
    assert config.problems(config.NodeSpec(domain='metaform.ing', email='a@b.c', role='broker',
                                           projects=('/srv/x/app',)))  # a broker serves no project
    made = config.compose(spec)
    assert set(made['services']) == {'caddy', 'auth'}
    command = made['services']['auth']['command']
    assert command[command.index('--node-role') + 1] == 'broker'
    caddy = config.caddyfile(spec)
    for path in ('/mcp /mcp/*', '/cloud/*', '/.well-known/jwks.json', '/device', '/account'):
        assert path in caddy, path
    assert 'reverse_proxy 127.0.0.1:7435' in caddy and 'flush_interval -1' in caddy
    assert '\n\tlog' not in caddy and '7434' not in caddy and '7433' not in caddy
    folder = tmp_path / 'node'
    folder.mkdir()
    (folder / 'node.json').write_text(config.node_env(spec), encoding='utf-8')
    assert config.spec_from(folder).role == 'broker'


# ---------------------------------------------------------------------------------------------------- hardening

def test_a_revoked_key_ends_every_token_it_signed_forged_ones_too_in_the_running_server(tmp_path, monkeypatch):
    from metaform.modules.node import tokens
    monkeypatch.setattr(tokens, 'RELOAD_SECONDS', 0.0)
    made, store = broker(tmp_path)
    client = web(made)
    account = sign_in(store, client)
    issued = host_tokens(client)
    import jwt
    stolen_kid, stolen_key = made.signed.signer.keys.signing()  # a copy of the key, as a thief would hold it
    tokens.Keys(tmp_path / 'keys').rotate(revoke_old=True)  # `metaform node rotate-key revoke_old=true`, elsewhere
    made.signed.generations.bump(account.id)
    now = int(time.time())
    forged = jwt.encode({'iss': ISSUER, 'iat': now, 'exp': now + 600, 'jti': 'j', 'sub': account.id,
                         'aud': ISSUER + '/mcp', 'scope': 'mcp:read', 'fam': 'x',
                         'gen': made.signed.generations.current(account.id)[0]},  # the thief picks the generation
                        stolen_key, algorithm='EdDSA', headers={'kid': stolen_kid, 'typ': tokens.ACCESS})
    assert made.signed.access(forged, ISSUER + '/mcp') is None  # the running server dropped the key, no restart
    assert made.signed.access(issued['access_token']) is None
    assert stolen_kid not in {one['kid'] for one in client.get('/.well-known/jwks.json').json()['keys']}
    assert not (tmp_path / 'keys' / f'{stolen_kid}.pem').exists()
    assert made.signed.signer.keys.current != stolen_kid  # and it signs with the new key at once


def test_an_operator_sign_out_ends_the_running_brokers_sessions_and_its_store_stays_accounts_only(tmp_path):
    from metaform.modules.node.authstore import BrokerStore, open_store, role_file
    made, store = broker(tmp_path)
    client = web(made)
    account = sign_in(store, client)
    assert client.get('/account').status_code == 200
    role_file(store.path).write_text('broker\n', encoding='utf-8')  # as `metaform node auth` writes it
    beside = open_store(store.path)  # what `metaform node signout alice` opens, in its own process
    assert isinstance(beside, BrokerStore)
    beside.bump_generation(account.id)
    assert client.get('/account').status_code == 302  # the session named the old generation: gone
    tables = {row[0] for row in private_database(store.path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {'accounts', 'passkeys'}


def test_a_self_hosted_store_opened_as_a_brokers_keeps_only_accounts_and_passkeys(tmp_path):
    from metaform.modules.node.authstore import AuthStore, BrokerStore
    path = tmp_path / 'auth.sqlite'
    old = AuthStore(path)
    account = old.add_account('rich', 'owner')
    old.open_session(account, 3600)
    old.add_token('access', 'f', 'c', account.id, ['mcp:read'], ISSUER + '/mcp', 600)
    old.save_client(CLIENT, document(), 'cimd', time.time() + 600)
    old.save_family('f', 1, False, time.time() + 600)
    BrokerStore(path, families=False)
    tables = {row[0] for row in private_database(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {'accounts', 'passkeys'}
    assert BrokerStore(path).account('rich') is not None


def test_junk_at_the_token_endpoint_spends_its_own_sources_allowance_not_everyones_refreshes(tmp_path):
    made, store = broker(tmp_path, unknown_per_address=6.0, per_address=3.0, global_rate=5.0)
    client = web(made)
    sign_in(store, client)
    issued = host_tokens(client)
    junk = {'grant_type': 'refresh_token', 'client_id': 'x', 'refresh_token': 'x'}
    codes = [client.post('/oauth/token', data=junk).status_code for _ in range(10)]
    assert 429 in codes  # the junk source ran out of its own allowance
    token = issued['refresh_token']
    for _ in range(5):  # from the same address, a grant the server signed is still served
        answer = client.post('/oauth/token', data={'grant_type': 'refresh_token', 'client_id': CLIENT,
                                                   'refresh_token': token})
        assert answer.status_code == 200, answer.text
        token = answer.json()['refresh_token']
    pages = web(made, ('127.0.0.1', 1))
    for _ in range(5):  # one source flooding a page uses its own allowance, then the global ceiling is untouched
        pages.get('/node/signin', headers={'X-Forwarded-For': '203.0.113.7'})
    assert pages.get('/node/signin', headers={'X-Forwarded-For': '203.0.113.7'}).status_code == 429
    assert pages.get('/node/signin', headers={'X-Forwarded-For': '198.51.100.9'}).status_code == 200


def test_wrong_device_codes_lock_out_the_account_that_typed_them_from_any_address_and_a_whole_ipv6_64(tmp_path):
    from metaform.modules.node.device import group
    assert group('2001:db8:1:2::1') == group('2001:db8:1:2:ffff::9') == '2001:db8:1:2::/64'
    assert group('::ffff:203.0.113.7') == '203.0.113.7' and group('203.0.113.7') == '203.0.113.7'
    made, store = broker(tmp_path)
    client = web(made, ('127.0.0.1', 1))
    sign_in(store, client, 'mallory')
    for number in range(10):  # a new address for every guess
        client.get('/device', params={'user_code': 'BBBB-BBBB'}, headers={'X-Forwarded-For': f'198.51.100.{number}'})
    assert client.get('/device', params={'user_code': 'CCCC-CCCC'},
                      headers={'X-Forwarded-For': '192.0.2.200'}).status_code == 429


def test_a_copied_machine_refresh_token_without_its_key_decides_nothing(tmp_path):
    from metaform.modules.cloud.login import new_key
    from metaform.modules.node import tokens
    made, store = broker(tmp_path)
    client = web(made)
    sign_in(store, client)
    key = new_key()
    endpoint = ISSUER + '/oauth/device_authorization'
    started = client.post(endpoint, data={'client_id': 'metaform-cli'},
                          headers={'DPoP': dpop(key, 'POST', endpoint)}).json()
    page = client.get('/device', params={'user_code': started['user_code']})
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    client.post('/device', data={'user_code': started['user_code'], 'csrf': csrf, 'decision': 'approve'},
                headers={'Origin': ISSUER})
    token = ISSUER + '/oauth/token'
    first = client.post(token, data={'grant_type': tokens.DEVICE_GRANT, 'device_code': started['device_code'],
                                     'client_id': 'metaform-cli'}, headers={'DPoP': dpop(key, 'POST', token)}).json()
    form = {'grant_type': 'refresh_token', 'client_id': 'metaform-cli'}
    second = client.post(token, data={**form, 'refresh_token': first['refresh_token']},
                         headers={'DPoP': dpop(key, 'POST', token)}).json()
    stale = client.post(token, data={**form, 'refresh_token': first['refresh_token']})  # from a log, with no key
    assert stale.json()['error'] == 'invalid_dpop_proof'
    still = client.post(token, data={**form, 'refresh_token': second['refresh_token']},
                        headers={'DPoP': dpop(key, 'POST', token)})
    assert still.status_code == 200  # the machine's sign-in was not ended by it


def test_a_client_metadata_fetch_connects_only_to_the_public_address_it_checked(monkeypatch):
    import asyncio
    import socket

    import httpcore

    from metaform.modules.node import authserver
    answers = [[(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))],
               [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]]
    asked = []

    def resolve(host, *args, **kwargs):  # first a public address, then rebound to loopback
        asked.append(host)
        return answers[len(asked) - 1]
    monkeypatch.setattr(authserver.socket, 'getaddrinfo', resolve)

    class Recording(httpcore.AsyncNetworkBackend):
        def __init__(self):
            self.dialled = []

        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            self.dialled.append(host)
            raise httpcore.ConnectError('recorded, not dialled')

    inner = Recording()
    with pytest.raises(httpcore.ConnectError):
        asyncio.run(authserver.PublicOnly(inner).connect_tcp('rebind.example', 443))
    assert inner.dialled == ['93.184.216.34'] and asked == ['rebind.example']  # resolved once, that address used
    with pytest.raises(httpcore.ConnectError, match='not on a public address'):
        asyncio.run(authserver.PublicOnly(inner).connect_tcp('rebind.example', 443))  # the loopback answer
    assert inner.dialled == ['93.184.216.34'] and asked == ['rebind.example', 'rebind.example']


def test_the_brokers_client_cache_is_bounded(tmp_path):
    from metaform.modules.node.authstore import BrokerStore
    store = BrokerStore(tmp_path / 'auth.sqlite')
    for number in range(BrokerStore.CLIENTS_HELD + 50):
        store.save_client(f'https://c{number}.example/m.json', {}, 'cimd', time.time() + 86400)
    assert len(store.clients) == BrokerStore.CLIENTS_HELD
    assert store.client('https://c0.example/m.json') is None and store.client(f'https://c{number}.example/m.json')


def test_a_dynamically_registered_client_survives_a_restart_with_nothing_stored(tmp_path):
    from metaform.modules.node.authserver import Node, Policy
    from metaform.modules.node.authstore import BrokerStore
    from metaform.modules.node.broker import Broker, Limits
    from metaform.modules.node.tokens import Keys

    def start():
        store = BrokerStore(tmp_path / 'auth.sqlite')
        node = Node(store, Policy(ISSUER, 'write', dcr=True, broker=True), keys=Keys(tmp_path / 'keys'))
        return Broker(node, Limits()), store
    made, _ = start()
    registered = web(made).post('/oauth/register', json={
        'redirect_uris': [REDIRECT], 'client_name': 'Older Host', 'token_endpoint_auth_method': 'client_secret_post',
        'grant_types': ['authorization_code', 'refresh_token'], 'response_types': ['code']}).json()
    assert registered['client_id'].count('.') == 2 and registered['client_secret']
    again, store = start()  # a restart: nothing about the client was kept anywhere
    client = web(again)
    sign_in(store, client)
    found = asyncio_run(again.node.provider.get_client(registered['client_id']))
    assert found.client_name == 'Older Host' and found.client_secret == registered['client_secret']
    _, challenge = pkce()
    held = client.get('/oauth/authorize', params={
        'response_type': 'code', 'client_id': registered['client_id'], 'redirect_uri': REDIRECT, 'state': 's',
        'code_challenge': challenge, 'code_challenge_method': 'S256'})
    assert held.status_code == 302 and '/node/consent' in held.headers['location']


def asyncio_run(awaitable):
    import asyncio
    return asyncio.run(awaitable)


def test_a_streamed_answer_gives_its_slot_back_even_when_the_host_left_before_its_first_byte():
    import asyncio

    from metaform.modules.node.broker import Held
    ended = []

    async def never():
        raise AssertionError('the body was never meant to start')
        yield b''

    async def closed():
        ended.append(True)

    async def run():
        async def receive():
            return {'type': 'http.disconnect'}

        async def send(message):
            raise OSError('the host is gone')
        with pytest.raises(Exception):  # noqa: B017  Starlette reports it as ClientDisconnect
            await Held(never(), status_code=200, headers={}, ended=closed)({'type': 'http', 'asgi': {
                'spec_version': '2.4'}}, receive, send)
    asyncio.run(run())
    assert ended == [True]
