"""The phone bridge, with Twilio's side simulated on this machine: no network, no credential, no real agent or engine.
Twilio's webhooks are signed here with a made-up auth token; its REST API is a recorder; the system agent is the
scripted one, or dispatch's fake ACP agent in a test home."""
from __future__ import annotations

import asyncio
import io
import secrets
import sys
import urllib.parse
import wave
from array import array
from pathlib import Path

import httpx
import pytest

from metaform.modules.twilio import api, mulaw, notify, simulate
from metaform.modules.twilio.agent import ScriptedAgent, SystemAgent, verb_runner
from metaform.modules.twilio.engines import ScriptedVoice
from metaform.modules.twilio.server import ATTESTED, PIN_NAME, Config, Lines, Phone, Seen

pytestmark = pytest.mark.kind('simulation')

TOKEN = 'made-up-auth-token-for-tests'
PUBLIC = 'https://phone.example.test'
OWNER, NUMBER, STRANGER = '+15550100001', '+15550100002', '+15550100009'
FAKE = Path(__file__).parents[2] / 'dispatch' / 'tests' / 'fake_agent.py'


@pytest.fixture(autouse=True)
def no_real_credentials(monkeypatch):
    """Whatever the shell holds, no test sees a real Twilio or ElevenLabs credential."""
    for name in (*api.NAMES, 'ELEVENLABS_API_KEY', PIN_NAME):
        monkeypatch.delenv(name, raising=False)


class Recorder:
    def __init__(self):
        self.requests = []

    def __call__(self, url, form, auth):
        self.requests.append((url, dict(form), auth))
        return {'sid': ('CA' if url.endswith('Calls.json') else 'SM') + '0' * 32}


def bridge(agent=None, voice=None, *, clock=None, seen=None, **config):
    recorder = Recorder()
    phone = Phone(Config(public_url=PUBLIC, twilio_number=NUMBER, owners=(OWNER,), auth_token=TOKEN,
                         control_token='control', lines=Lines(on_text='(by text)', refusal='Not you.', busy='Busy.'), **config),
                  agent=lambda: agent or ScriptedAgent(['On it.']), voice=lambda: voice or ScriptedVoice(),
                  client=api.Client(post=recorder, creds=lambda: ('AC' + '1' * 32, ('SK' + '2' * 32, 'secret'))),
                  log=lambda line: None, seen=seen, **({'clock': clock} if clock else {}))
    return phone, recorder


async def post(phone, path, form, *, signed=True, token=TOKEN, headers=None):
    headers = {'Content-Type': 'application/x-www-form-urlencoded', **(headers or {})}
    if signed:
        headers['X-Twilio-Signature'] = api.signature(token, PUBLIC + path, form.items())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=phone.app()), base_url='http://127.0.0.1') as http:
        return await http.post(path, content=urllib.parse.urlencode(form), headers=headers)


def inbound(**more):
    """An owner's call, its caller ID fully attested, with a CallSid of its own."""
    return {'CallSid': 'CA' + secrets.token_hex(16), 'From': OWNER, 'To': NUMBER, 'Direction': 'inbound',
            'StirVerstat': ATTESTED, **more}


@pytest.mark.kind('fixture')
def test_the_signature_is_twilios_documented_one_and_anything_changed_fails():
    url = 'https://mycompany.com/myapp.php?foo=1&bar=2'
    params = {'CallSid': 'CA1234567890ABCDE', 'Caller': '+12349013030', 'Digits': '1234', 'From': '+12349013030',
              'To': '+18005551212'}
    expected = '0/KCTR6DLpKmkAf8muzZqo1nDgQ='  # the example in Twilio's webhook security documentation
    assert api.signature('12345', url, params.items()) == expected
    assert api.valid('12345', url, params.items(), expected)
    assert not api.valid('12345', url, {**params, 'Digits': '9999'}.items(), expected)
    assert not api.valid('54321', url, params.items(), expected)
    assert not api.valid('12345', url.replace('foo=1', 'foo=2'), params.items(), expected)
    assert not api.valid('12345', url, params.items(), None)
    ported = api.signature('12345', 'https://mycompany.com:443/myapp.php', params.items())
    assert api.valid('12345', 'https://mycompany.com/myapp.php', params.items(), ported)


def test_a_signed_owner_call_is_streamed_and_an_unsigned_or_forged_one_is_refused():
    phone, _ = bridge()
    answered = asyncio.run(post(phone, '/phone/voice', inbound()))
    assert answered.status_code == 200
    assert '<Connect><Stream url="wss://phone.example.test/phone/stream"><Parameter name="token"' in answered.text
    assert asyncio.run(post(phone, '/phone/voice', inbound(), signed=False)).status_code == 403
    assert asyncio.run(post(phone, '/phone/voice', inbound(), token='another-token')).status_code == 403
    for _ in range(3):  # five bad signatures quiet the source: its failures are answered 429
        asyncio.run(post(phone, '/phone/voice', inbound(), signed=False))
    assert asyncio.run(post(phone, '/phone/voice', inbound(), signed=False)).status_code == 429
    # but a request Twilio signed is never held back by what others sent from the same source
    assert '<Stream' in asyncio.run(post(phone, '/phone/voice', inbound())).text


def test_a_caller_not_among_the_owners_hears_a_refusal_and_is_hung_up_on():
    phone, _ = bridge()
    refused = asyncio.run(post(phone, '/phone/voice', inbound(From=STRANGER)))
    assert refused.status_code == 200
    assert '<Say>' in refused.text and '<Hangup/>' in refused.text and '<Stream' not in refused.text
    assert phone.tickets == {}
    to_another = asyncio.run(post(phone, '/phone/voice', inbound(To='+15550100003')))
    assert '<Stream' not in to_another.text


def test_a_simulated_call_from_a_wav_is_heard_answered_spoken_and_barged_in_on():
    """A local websocket client plays Twilio: mu-law frames of a wav made with the standard library go to the bridge,
    the scripted voice hears them, the scripted agent answers, the answer comes back as audio frames, and speaking
    over it makes the bridge send Twilio's clear."""
    samples = array('h', mulaw.decode(mulaw.tone(0.8, 180.0, 9000)))
    made = io.BytesIO()
    with wave.open(made, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(mulaw.RATE)
        out.writeframes(samples.tobytes())
    made.seek(0)
    with wave.open(made, 'rb') as read:
        heard = array('h')
        heard.frombytes(read.readframes(read.getnframes()))
    found = asyncio.run(simulate.run(speech=mulaw.encode(heard)))
    assert found['checks'] == {'unsigned_refused': True, 'stranger_refused': True, 'pin_asked': True,
                               'replay_refused': True, 'twiml_streams': True,
                               'forged_stream_refused': True, 'greeted': True, 'barge_in_cleared': True,
                               'agent_heard': True, 'call_ended_cleanly': True}
    assert found['barge_ins'] >= 1 and found['turns'] == 2
    assert found['spoken'][1:4] == ['Your board has three tickets waiting.', 'The first is the parser fix.',
                                    'Shall I start it?']
    # from the end of the caller's speech to the first audio back: the voice's pause, then the bridge's own time
    assert found['endpointing_pause_ms'] <= found['latency_ms'] < found['endpointing_pause_ms'] + 500
    print(f"\nsimulated latency: {found['latency_ms']} ms, of which endpointing {found['endpointing_pause_ms']} ms "
          f"and the bridge {found['bridge_ms']} ms")


def test_an_outbound_call_is_requested_as_twilio_documents_and_only_its_own_call_is_bridged():
    phone, recorder = bridge()
    placed = asyncio.run(phone.call('an agent is waiting for your permission'))
    url, form, auth = recorder.requests[0]
    assert url == f'{api.API}/Accounts/AC{"1" * 32}/Calls.json'
    assert form == {'To': OWNER, 'From': NUMBER, 'Url': f'{PUBLIC}/phone/voice', 'Method': 'POST', 'Timeout': '30'}
    assert auth == ('SK' + '2' * 32, 'secret')  # the API key, so the auth token is never sent
    assert placed == {'placed': True, 'sid': 'CA' + '0' * 32}
    assert asyncio.run(phone.call('again'))['placed'] is False  # within twilio_call_gap_minutes
    with pytest.raises(ValueError):
        asyncio.run(phone.call('to a stranger', to=STRANGER, own=True))
    ours = {'CallSid': placed['sid'], 'From': NUMBER, 'To': OWNER, 'Direction': 'outbound-api'}
    answered = asyncio.run(post(phone, '/phone/voice', ours))
    assert '<Stream' in answered.text
    ticket = next(iter(phone.tickets.values()))
    assert ticket.direction == 'outbound' and ticket.reason == 'an agent is waiting for your permission'
    assert '<Stream' not in asyncio.run(post(phone, '/phone/voice', ours)).text  # its webhook, sent again
    assert placed['sid'] not in phone.placed and len(phone.tickets) == 1
    unknown = asyncio.run(post(phone, '/phone/voice', {**ours, 'CallSid': 'CA' + 'f' * 32}))
    assert '<Stream' not in unknown.text


def test_the_owners_text_goes_to_the_agent_and_its_reply_is_texted_back():
    agent = ScriptedAgent(['Three tickets wait; the parser fix is first.'])
    phone, recorder = bridge(agent=agent, pin='4321')

    def texted(body, **more):
        return {'MessageSid': 'SM' + secrets.token_hex(16), 'From': OWNER, 'To': NUMBER, 'Body': body, **more}

    async def exchange():
        sent = texted("4321 What's waiting?")
        answered = await post(phone, '/phone/sms', sent)
        await post(phone, '/phone/sms', sent)  # the same signed webhook again: handled once
        stranger = await post(phone, '/phone/sms', texted('4321 hi', From=STRANGER))
        await post(phone, '/phone/sms', texted('no PIN at the start'))
        await post(phone, '/phone/sms', texted('9999 a wrong PIN'))
        await asyncio.gather(*phone.tasks)
        return answered, stranger
    answered, stranger = asyncio.run(exchange())
    assert answered.text.endswith('<Response></Response>') and stranger.text.endswith('<Response></Response>')
    assert agent.heard == ["(by text)\n\nWhat's waiting?"]
    assert len(recorder.requests) == 1
    url, form, _ = recorder.requests[0]
    assert url.endswith('/Messages.json')
    assert form == {'To': OWNER, 'From': NUMBER, 'Body': 'Three tickets wait; the parser fix is first.'}


def test_signals_call_or_text_as_the_person_chose_and_the_same_one_once():
    placed, sent, now = [], [], [0.0]
    told = notify.Notifier(calls=['waiting-for-you'], texts=['stuck', 'budget'],
                           place=lambda why: placed.append(why) or True,
                           send=sent.append, clock=lambda: now[0], task_of=lambda work_id: 'Fix the parser')
    asked = {'signal': 'permission-waiting', 'work_id': 'w1', 'session_id': 's1', 'active': True}
    assert told.heard(asked) == ['call']
    assert placed == ['an agent is waiting for your permission on "Fix the parser"']
    assert told.heard(asked) == []  # the same signal on the same ticket, within the hour
    assert told.heard({'signal': 'spinning-calls', 'work_id': 'w2', 'active': True}) == ['text']
    assert told.heard({'signal': 'budget', 'work_id': 'w3', 'active': True}) == []  # texts a minute apart
    now[0] = 61.0
    assert told.heard({'signal': 'budget', 'work_id': 'w3', 'active': True}) == ['text']
    assert told.heard({'signal': 'drift', 'work_id': 'w4', 'active': True}) == []
    assert told.heard({**asked, 'work_id': 'w5', 'active': False}) == []
    assert notify.check(['stuck', 'permission-waiting'], 'x') is None and notify.check(['Not One'], 'x')


def test_status_names_what_is_missing_and_the_credentials_by_name_only(run, home, monkeypatch):
    monkeypatch.setenv(api.SID, 'AC-not-a-real-sid')
    shown = run('twilio', 'status', '--json').stdout
    assert 'The phone is off.' in shown and 'AC-not-a-real-sid' not in shown
    assert '"TWILIO_ACCOUNT_SID": true' in shown and '"TWILIO_AUTH_TOKEN": false' in shown
    kept = run('set', '--twilio-public-url', 'http://not-secure.example')  # kept, with its notice, BASE-044
    assert 'https' in kept.stdout + kept.stderr
    assert 'twilio_public_url is not an https address' in run('twilio', 'status', '--json').stdout
    run('set', '--twilio-public-url', PUBLIC)
    run('set', '--twilio-owner-numbers', OWNER)
    shown = run('twilio', 'status', '--json').stdout
    assert f'{PUBLIC}/phone/voice' in shown and f'{PUBLIC}/phone/sms' in shown and OWNER not in shown
    assert run('twilio', 'serve', ok=False).returncode != 0  # off, and not set up: it refuses to start


def test_the_system_agent_answers_through_dispatch_with_the_fake_agent(run, home, project_folder, tmp_path,
                                                                        monkeypatch, dispatch_runners):
    from metaform.data import Store
    run('enable', 'dispatch')
    for agent in ('claude', 'codex', 'gemini'):  # every agent is the fake, so no real one is ever started
        run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{FAKE}"', cwd=project_folder)
    store = Store('proj')
    store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.engine')
    from metaform.module import context
    from metaform.modules import dispatch
    # a map with no intake has no roots, so the system agent's held ticket is made at a node, as dispatch's tests do
    dispatch.anchor(context('dispatch', project_folder, project='proj'), store, 'code.engine')
    log = tmp_path / 'fake.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'plain')
    monkeypatch.setenv('FAKE_ACP_MASCOT', '1')
    agent = SystemAgent(verb_runner(project_folder, 'proj'), poll=0.1, start_limit=60, turn_limit=60)

    async def answer():
        said = []
        async for so_far in agent.reply('What is on my board?'):
            said.append(so_far)
        return said
    try:
        said = asyncio.run(answer())
    finally:
        if agent.started.get('pid'):
            dispatch_runners.append((agent.started, project_folder, log))
    assert said and said[-1] == 'The fake answers: What is on my board?'


def test_a_call_held_back_by_the_gap_waits_and_is_placed_once_the_gap_allows():
    """A call twilio_call_gap_minutes or a call in progress holds back is not counted as told: it waits, is placed by
    `retry` once it may be, once, and is dropped if its signal clears first."""
    now = [0.0]
    phone, recorder = bridge(clock=lambda: now[0])

    def place(why):
        if phone.reserve() is not None:
            return False
        asyncio.run(phone.call(why, reserved=True))
        return True
    told = notify.Notifier(calls=['waiting-for-you'], texts=[], place=place, send=lambda why: None,
                           clock=lambda: now[0])
    assert told.heard({'signal': 'permission-waiting', 'work_id': 'wA', 'active': True}) == ['call']
    now[0] = 300.0
    question = {'signal': 'question-waiting', 'work_id': 'wB', 'active': True}
    assert told.heard(question) == [] and len(recorder.requests) == 1  # within the gap: held back, not told
    assert told.retry() == []
    now[0] = 1000.0  # the gap has passed
    assert told.retry() == ['call for question-waiting'] and len(recorder.requests) == 2
    assert told.retry() == [] and told.heard(question) == []  # placed once, then told for the hour
    now[0] = 1500.0
    cleared = {'signal': 'question-waiting', 'work_id': 'wC', 'active': True}
    assert told.heard(cleared) == []  # within the gap again
    told.heard({**cleared, 'active': False})
    now[0] = 3000.0
    assert told.retry() == [] and len(recorder.requests) == 2  # its signal cleared, so it is not placed


def test_a_spoofable_caller_id_is_not_enough_the_pin_or_an_attested_call_is():
    phone, _ = bridge(pin='246810')
    unattested = inbound(StirVerstat='No-TN-Validation')
    asked = asyncio.run(post(phone, '/phone/voice', unattested))
    assert '<Gather' in asked.text and 'action="https://phone.example.test/phone/pin"' in asked.text
    assert '<Stream' not in asked.text and phone.tickets == {}
    right = asyncio.run(post(phone, '/phone/pin', {**unattested, 'Digits': '246810'}))
    assert '<Stream' in right.text
    assert '<Stream' not in asyncio.run(post(phone, '/phone/pin', {**unattested, 'Digits': '246810'})).text  # once
    assert '<Stream' in asyncio.run(post(phone, '/phone/voice', inbound())).text  # attested: no PIN asked
    for _ in range(5):  # five wrong PINs within the hour, and the PIN is not taken for an hour
        call = inbound(StirVerstat='')
        asyncio.run(post(phone, '/phone/voice', call))
        assert '<Stream' not in asyncio.run(post(phone, '/phone/pin', {**call, 'Digits': '000000'})).text
    late = inbound(StirVerstat='')
    refused = asyncio.run(post(phone, '/phone/voice', late))
    assert '<Gather' not in refused.text and '<Hangup/>' in refused.text
    no_pin, _ = bridge()  # attested-or-pin with no PIN set: an unattested call cannot get in
    assert '<Hangup/>' in asyncio.run(post(no_pin, '/phone/voice', inbound(StirVerstat=''))).text
    only_id, _ = bridge(proof='caller-id')  # chosen explicitly, the number alone is enough
    assert '<Stream' in asyncio.run(post(only_id, '/phone/voice', inbound(StirVerstat=''))).text


def test_a_signed_webhook_sent_again_is_refused_even_after_the_bridge_restarts(tmp_path):
    kept = tmp_path / 'seen.txt'
    phone, _ = bridge(seen=Seen(kept))
    call = inbound()
    assert '<Stream' in asyncio.run(post(phone, '/phone/voice', call)).text
    replayed = asyncio.run(post(phone, '/phone/voice', call))
    assert '<Stream' not in replayed.text and len(phone.tickets) == 1
    again, _ = bridge(seen=Seen(kept))
    assert '<Stream' not in asyncio.run(post(again, '/phone/voice', call)).text and again.tickets == {}
    assert '<Stream' not in asyncio.run(post(again, '/phone/voice', inbound(CallSid=''))).text


def test_failures_from_every_source_together_are_quieted_and_a_busy_stream_is_not_one():
    phone, _ = bridge()
    codes = [asyncio.run(post(phone, '/phone/voice', inbound(), signed=False,
                              headers={'X-Forwarded-For': f'10.0.{n // 250}.{n % 250}'})).status_code
             for n in range(130)]
    assert codes[:120] == [403] * 120 and set(codes[120:]) == {429}  # rotating the source does not escape
    assert phone.limiter.refused('another') is True
    quiet, _ = bridge()
    assert not any(quiet.limiter.refused('twilio') for _ in range(4))
    quiet.active = object()  # a call in progress; a stream raced in for another answered call
    token = quiet.mint('CA' + 'e' * 32, OWNER, 'inbound', None)

    async def raced():
        from starlette.testclient import TestClient
        with TestClient(quiet.app()) as client, client.websocket_connect('/phone/stream') as socket:
            socket.send_json({'event': 'start', 'start': {'streamSid': 'MZ1', 'callSid': 'CA' + 'e' * 32,
                                                           'customParameters': {'token': token}}})
            with pytest.raises(Exception):  # noqa: B017  closed with 1008
                socket.receive_text()
    asyncio.run(raced())
    assert len(quiet.limiter.bad['testclient']) == 0


def test_calls_texts_and_the_bridge_refuse_an_agents_session(run, home, monkeypatch):
    monkeypatch.setenv('METAFORM_SESSION', 'an-agent-session')
    for verb in (('call',), ('text', 'hello'), ('serve',)):
        refused = run('twilio', *verb, ok=False)
        assert refused.returncode != 0 and "never run from an agent's session" in refused.stdout + refused.stderr
