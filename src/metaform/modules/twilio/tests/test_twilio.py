"""The phone bridge, with Twilio's side simulated on this machine: no network, no credential, no real agent or engine.
Twilio's webhooks are signed here with a made-up auth token; its REST API is a recorder; the system agent is the
scripted one, or dispatch's fake ACP agent in a test home."""
from __future__ import annotations

import asyncio
import io
import json
import secrets
import sys
import urllib.parse
import wave
from array import array
from pathlib import Path

import httpx
import pytest

from metaform.module import Stop
from metaform.modules.twilio import api, mulaw, notify, selfcheck, simulate
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
    agent = SystemAgent(verb_runner(project_folder, 'proj'), start_limit=60, turn_limit=60)

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


@pytest.mark.req('QUAL-015')
def test_the_system_agent_reads_the_thread_again_only_when_the_runner_announces_a_change(monkeypatch):
    """While the agent works and says nothing, its thread is not read again on a timer, nor for a burst of changes that
    concern other tickets or tables; the runner's map.changed naming its lines has the answer read at once."""
    import threading
    import time

    from metaform import events
    state = {'activity': 'working', 'lines': []}
    reads: list[float] = []

    def run(name, nouns):
        if name == 'system':
            return {'work_id': 'W'}
        if name == 'message':
            state['lines'].append({'session_id': 'S', 'seq': 2, 'kind': 'person', 'text': nouns['text'][0]})
            return {'sent': True}
        reads.append(time.monotonic())
        return {'sessions': [{'session_id': 'S', 'state': 'running', 'activity': state['activity']}],
                'lines': list(state['lines'])}
    handlers = []

    class Heard:
        def close(self):
            pass

    def listen(module, handler):
        handlers.append(handler)
        return Heard()
    monkeypatch.setattr(events, 'listen', listen)
    agent = SystemAgent(run, start_limit=5, turn_limit=5)

    async def answer():
        said = []
        async for so_far in agent.reply('Hello.'):
            said.append(so_far)
        return said

    def runner_answers():
        time.sleep(1.0)
        read_while_quiet.append(len(reads))
        state['lines'].append({'session_id': 'S', 'seq': 3, 'kind': 'agent_message_chunk', 'text': 'Hi there.'})
        state['activity'] = 'idle'
        for handler in handlers:  # the runner's map.changed, naming its lines, from another process
            handler({'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.lines']})
    read_while_quiet: list[int] = []
    unconcerned = [{'project': 'proj', 'tables': ['ops', 'work']},  # the map, not the agents
                   {'project': 'proj', 'tables': 'dispatch', 'dispatch_tables': ['dispatch.timers']},
                   {'project': 'proj', 'tables': 'dispatch', 'work_ids': ['other'], 'session_ids': ['T']}]

    def burst():
        time.sleep(0.5)
        for _ in range(50):  # a burst that concerns another ticket or other tables
            for payload in unconcerned:
                for handler in handlers:
                    handler(payload)
    threading.Thread(target=burst, daemon=True).start()
    threading.Thread(target=runner_answers, daemon=True).start()
    began = time.monotonic()
    said = asyncio.run(answer())
    assert read_while_quiet == [3]  # the session at start, the thread before the message, the thread after it
    assert said == ['Hi there.'] and time.monotonic() - began < 2


@pytest.mark.req('QUAL-015')
def test_the_bridge_server_says_when_it_listens_and_does_not_wake_while_nothing_happens():
    """uvicorn's own main loop wakes ten times a second to see whether it should exit; the bridge's waits for the exit
    it is told of, and says when it listens with an event rather than a flag read in a loop."""
    import uvicorn

    from metaform.modules.twilio.server import Serving
    phone, _ = bridge()
    server = Serving(uvicorn.Config(phone.app(), host='127.0.0.1', port=0, log_level='warning', lifespan='off'))
    ticks = []
    real = server.on_tick

    async def counted(counter):
        ticks.append(counter)
        return await real(counter)
    server.on_tick = counted

    async def serve():
        serving = asyncio.ensure_future(server.serve())
        await asyncio.wait_for(server.ready.wait(), 10)
        await asyncio.sleep(1.0)
        server.stop()
        await asyncio.wait_for(serving, 10)
    asyncio.run(serve())
    assert len(ticks) <= 1


def test_a_held_back_text_or_call_is_due_when_its_gap_ends_and_a_call_in_progress_holds_calls_with_no_time():
    """The bridge tries again only at `due`, or when the call in progress ends: a text when TEXT_GAP has passed since
    the last, a call when the gap between calls allows it, and no time at all while a call is in progress."""
    now, free = [0.0], [None]
    sent = []
    told = notify.Notifier(calls=['waiting-for-you'], texts=['budget'], place=lambda why: False, send=sent.append,
                           clock=lambda: now[0], call_free=lambda: free[0])
    assert told.due() is None  # nothing waits
    assert told.heard({'signal': 'budget', 'work_id': 'w1', 'active': True}) == ['text']
    now[0] = 10.0
    assert told.heard({'signal': 'budget', 'work_id': 'w2', 'active': True}) == []
    assert told.due() == notify.TEXT_GAP  # the last text went at 0
    assert told.heard({'signal': 'permission-waiting', 'work_id': 'w3', 'active': True}) == []
    assert told.due() == notify.TEXT_GAP  # the call waits on a call in progress: no time of its own
    free[0] = 30.0  # the call in progress ended, and the gap since the last call ends at 30
    assert told.due() == 30.0


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


DEAD = 'https://keen-answer-availability-marked.trycloudflare.com'  # the quick tunnel Rich's number pointed at
UNREACHED = 'it could not be reached: [Errno -2] Name or service not known'


class Twilio:
    """Twilio's REST API for one number, stubbed: what it lists for the number, and each change it was asked for."""

    def __init__(self, voice='', sms='', **more):
        self.record = {'sid': 'PN' + '3' * 32, 'phone_number': NUMBER, 'voice_url': voice, 'sms_url': sms, **more}
        self.posted = []
        self.client = api.Client(post=self.post, get=self.get, creds=lambda: ('AC' + '1' * 32, ('SK' + '2' * 32, 's')))

    def get(self, url, auth):
        assert url == f'{api.API}/Accounts/AC{"1" * 32}/IncomingPhoneNumbers.json?PhoneNumber=%2B15550100002'
        return {'incoming_phone_numbers': [dict(self.record)]}

    def post(self, url, form, auth):
        self.posted.append((url, dict(form)))
        self.record.update(voice_url=form['VoiceUrl'], sms_url=form['SmsUrl'])
        return dict(self.record)


def reach(*answering):
    """The addresses that answer; any other could not be reached, as a closed tunnel cannot."""
    return lambda url, health: None if url.startswith(answering or ('-',)) else UNREACHED


def setup(public='', running=False, enabled=True):
    return selfcheck.Setup(number=NUMBER, shown='+1•••••0002', public=public, running=running, enabled=enabled)


def said(report):
    return [(problem['problem'], problem['next']) for problem in report['problems']]


def test_the_check_says_each_thing_wrong_with_where_twilio_sends_calls_and_its_one_fix():
    """The four reports: an address that does not answer, a mismatch, the bridge not running, no public URL; and a
    temporary quick tunnel flagged. Twilio's API and every address are stubbed; the check only reads."""
    dead = Twilio(voice=f'{DEAD}/voice', sms=f'{DEAD}/sms')
    found = selfcheck.check(setup(enabled=False), dead.client, reach())  # Rich's number on 2026-10-15
    set_public = 'metaform set --twilio-public-url https://<your node or tunnel>'
    assert said(found) == [
        ((f'Your Twilio number sends its calls to {DEAD}/voice, which does not answer ({UNREACHED}), so every call '
          "hears Twilio's application error."), set_public),
        ((f'Your Twilio number sends its texts to {DEAD}/sms, which does not answer ({UNREACHED}), so your texts get '
          'no answer.'), set_public),
        ('twilio_public_url is not set, so the bridge has no address Twilio can reach.', set_public),
        ('The phone bridge is not running: the phone is off.', 'metaform set --twilio-enabled, then metaform web start')]
    assert len(found['warnings']) == 2 and all('temporary quick tunnel' in one for one in found['warnings'])
    assert not found['ok'] and not dead.posted
    assert selfcheck.headline(found).endswith(f'Next: {set_public} (3 more: metaform twilio check)')

    elsewhere = Twilio(voice='https://old.example.test/voice', sms=f'{PUBLIC}/phone/sms')
    found = selfcheck.check(setup(PUBLIC, running=True), elsewhere.client, reach(PUBLIC, 'https://old.example.test'))
    assert said(found) == [((f'Your Twilio number sends its calls to https://old.example.test/voice, not to the bridge '
                             f'at {PUBLIC}/phone/voice.'), 'metaform twilio check fix=true')]

    ours = Twilio(voice=f'{PUBLIC}/phone/voice', sms=f'{PUBLIC}/phone/sms')
    stopped = said(selfcheck.check(setup(PUBLIC), ours.client, reach()))
    assert stopped[-1] == (f'The phone bridge is not running, and {PUBLIC}/phone/health does not answer: {UNREACHED}.',
                           'metaform twilio serve')
    assert stopped[0][0].startswith(f'Your Twilio number sends its calls to {PUBLIC}/phone/voice, which does not answer')
    unrouted = said(selfcheck.check(setup(PUBLIC, running=True), ours.client, reach()))
    assert unrouted[-1][1] == 'route https://phone.example.test/phone/* to 127.0.0.1:7441, on your Node or your tunnel'

    well = selfcheck.check(setup(PUBLIC, running=True), ours.client, reach(PUBLIC))
    assert well['ok'] and well['problems'] == [] and well['warnings'] == [] and selfcheck.headline(well) is None
    app = Twilio(voice=f'{PUBLIC}/phone/voice', sms=f'{PUBLIC}/phone/sms', voice_application_sid='AP' + '4' * 32)
    assert said(selfcheck.check(setup(PUBLIC, running=True), app.client, reach(PUBLIC)))[0][0] == \
        f'Your Twilio number sends its calls to the TwiML App AP{"4" * 32}, not to the bridge.'


def test_fix_points_the_number_at_the_bridge_only_when_the_bridge_answers_there():
    dead = Twilio(voice=f'{DEAD}/voice')
    for where in (setup(), setup(PUBLIC, running=True)):  # no address; an address that does not answer
        with pytest.raises(Stop) as refused:
            selfcheck.fix(where, dead.client, reach())
        assert refused.value.message.startswith('The number was not changed') and not dead.posted
    fixed = selfcheck.fix(setup(PUBLIC, running=True), dead.client, reach(PUBLIC))
    assert dead.posted == [(f'{api.API}/Accounts/AC{"1" * 32}/IncomingPhoneNumbers/PN{"3" * 32}.json',
                            {'VoiceUrl': f'{PUBLIC}/phone/voice', 'VoiceMethod': 'POST',
                             'SmsUrl': f'{PUBLIC}/phone/sms', 'SmsMethod': 'POST'})]
    assert fixed['ok'] and fixed['fixed'] == {'changed': True, 'was': {'voice': f'{DEAD}/voice', 'sms': None},
                                              'now': {'voice': f'{PUBLIC}/phone/voice', 'sms': f'{PUBLIC}/phone/sms'}}
    assert selfcheck.fix(setup(PUBLIC, running=True), dead.client, reach(PUBLIC))['fixed']['changed'] is False
    assert len(dead.posted) == 1  # already pointed there: nothing sent

    tunnel = 'https://other-words-here.trycloudflare.com'  # a quick tunnel is set only with its warning said
    quick = Twilio(voice=f'{DEAD}/voice')
    assert any('temporary quick tunnel' in one
               for one in selfcheck.check(setup(tunnel, running=True), quick.client, reach(tunnel))['warnings'])
    fixed = selfcheck.fix(setup(tunnel, running=True), quick.client, reach(tunnel))
    assert quick.posted and fixed['warnings'] == [
        (f'twilio_public_url, {tunnel}, is a temporary quick tunnel: a number pointed there stops working when the '
         'tunnel closes. A lasting address, such as your Node, keeps working.')]
    app = Twilio(voice=f'{PUBLIC}/phone/voice', sms=f'{PUBLIC}/phone/sms', voice_application_sid='AP' + '4' * 32)
    selfcheck.fix(setup(PUBLIC, running=True), app.client, reach(PUBLIC))
    assert app.posted[0][1]['VoiceApplicationSid'] == '' and app.posted[0][1]['SmsApplicationSid'] == ''


def test_the_check_is_kept_logged_and_raised_never_printed_and_fix_waits_to_be_asked(home, tmp_path, monkeypatch,
                                                                                    capsys):
    """The verb in this process, so the stubbed API can never be left behind for a real one. The stubs go on the
    modules the verb itself uses, which the loader may have imported afresh, and nothing may open a connection. The
    findings go to the log and check.json; the terminal and the page are told nothing."""
    from metaform import module, settings
    from metaform.modules import twilio

    def no_network(*args, **kwargs):
        raise AssertionError('the check reached the network')
    monkeypatch.setattr('urllib.request.urlopen', no_network)
    dead = Twilio(voice=f'{DEAD}/voice', sms=f'{DEAD}/sms')
    monkeypatch.setattr(twilio.api, '_get', dead.get)
    monkeypatch.setattr(twilio.api, '_post', dead.post)
    monkeypatch.setattr(twilio.selfcheck, 'answers', reach())
    published = []
    monkeypatch.setattr(twilio, '_publish', lambda ctx, project, payload: published.append(payload))
    monkeypatch.setenv(api.SID, 'AC' + '1' * 32)
    monkeypatch.setenv(api.TOKEN, TOKEN)
    settings.put('twilio_number', NUMBER, tmp_path)
    ctx = module.context('twilio', tmp_path)
    assert twilio.begun(ctx) and twilio.module_status(ctx) == module.Status()  # nothing checked yet
    assert twilio.web_started({'folder': str(tmp_path)}, ctx) is None  # the phone is off: no check at all
    found = twilio.check(ctx)
    assert found['problems'][0]['problem'].startswith(f'Your Twilio number sends its calls to {DEAD}/voice')
    assert not dead.posted and not published  # a check someone asked for is theirs to read, never raised
    kept = json.loads(twilio.check_file().read_text(encoding='utf-8'))
    assert kept['problems'] == found['problems']
    logged = twilio.log_file().read_text(encoding='utf-8')
    assert f'check: Your Twilio number sends its calls to {DEAD}/voice' in logged and 'check: warning: ' in logged
    status = twilio.module_status(ctx)
    assert status.notice is None and status.lines[0].startswith('Phone: checked ')
    with pytest.raises(Stop):
        twilio.check(module.context('twilio', tmp_path, nouns={'fix': True}))  # no address to point it at
    with pytest.raises(Stop, match="the person's own step"):
        twilio.check(module.context('twilio', tmp_path, nouns={'fix': True}, surface='mcp'))
    assert not dead.posted
    settings.put('twilio_enabled', True, tmp_path)
    monkeypatch.setattr(twilio, 'project_of', lambda ctx: 'proj')
    capsys.readouterr()
    started = twilio.web_started({'folder': str(tmp_path)}, ctx)
    assert started == {'twilio': 'checked', 'ok': False, 'problems': 4}  # not set up enough to serve: checked
    printed = capsys.readouterr()
    assert printed.out == '' and printed.err == ''
    assert [one['signal'] for one in published] == ['setup-not-working']
    assert published[0]['report']['problems'] == json.loads(twilio.check_file().read_text())['problems']


def test_a_problem_goes_to_the_system_agent_once_until_its_findings_change_or_a_day_passes_untaken(
        home, tmp_path, monkeypatch):
    from metaform import module, settings
    from metaform.modules import twilio
    published = []
    monkeypatch.setattr(twilio, '_publish', lambda ctx, project, payload: published.append(payload))
    monkeypatch.setattr(twilio, 'project_of', lambda ctx: 'proj')
    settings.put('twilio_enabled', True, tmp_path)
    ctx = module.context('twilio', tmp_path)
    broken = {'ok': False, 'problems': [{'problem': 'It does not answer.', 'next': 'metaform twilio serve'}],
              'warnings': []}
    twilio.troubled(ctx, broken, asked=False)
    assert published == []  # nothing of the phone set up: not raised
    settings.put('twilio_public_url', PUBLIC, tmp_path)
    for _ in range(2):
        twilio.troubled(ctx, broken, asked=False)
    assert len(published) == 1 and published[0]['set_up'] == f'the public address {PUBLIC}'
    first = published[0]['key']
    other = {**broken, 'problems': [{'problem': 'Another thing.', 'next': 'metaform twilio check'}]}
    twilio.troubled(ctx, other, asked=False)
    assert [one.get('clear') for one in published[1:]] == [True, None]  # the old one cleared, the new one raised
    assert published[1]['key'] == first and published[2]['key'] != first
    kept = twilio.raised()
    home_file = twilio.raised_file()
    home_file.write_text(json.dumps({**kept, 'at': kept['at'] - twilio.AGAIN_SECONDS}))
    twilio.troubled(ctx, other, asked=False)  # a day on, nobody took it up, and it still stands: raised again
    assert len(published) == 4 and published[3]['key'] == published[2]['key']
    twilio.troubled(ctx, other, asked=True)  # the person asked for the check: taken up
    home_file.write_text(json.dumps({**twilio.raised(), 'at': kept['at'] - twilio.AGAIN_SECONDS}))
    twilio.troubled(ctx, other, asked=False)
    assert len(published) == 4
    twilio.troubled(ctx, {'ok': True, 'problems': [], 'warnings': []}, asked=False)
    assert published[-1] == {'signal': 'setup-not-working', 'module': 'twilio', 'key': published[2]['key'],
                             'clear': True} and not home_file.exists()


def self_signed(tmp_path, host='localhost'):
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(UTC)
    made = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False).sign(key, hashes.SHA256()))
    pem = tmp_path / 'bridge.pem'
    pem.write_bytes(made.public_bytes(serialization.Encoding.PEM) + key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return pem


def test_the_direct_route_names_a_closed_port_a_failed_handshake_and_a_wrong_certificate(tmp_path):
    """A public address that resolves to this machine, on a non-loopback bind, is probed for what keeps Twilio out;
    on loopback, or at an address that is not this machine, the route is not direct and nothing is said."""
    import contextlib
    import socket
    import ssl
    import threading

    def here():
        return {'127.0.0.1'}

    def no_nat():
        return False

    def listening(wrap=None):
        server = socket.create_server(('127.0.0.1', 0))
        port = server.getsockname()[1]

        def serve():
            with contextlib.suppress(OSError):
                client, _ = server.accept()
                with contextlib.suppress(OSError, ssl.SSLError):
                    client = wrap(client) if wrap else client
                    client.recv(1)
                client.close()
        threading.Thread(target=serve, daemon=True).start()
        return server, port

    with socket.create_server(('127.0.0.1', 0)) as taken:
        closed = taken.getsockname()[1]
    problem, step = selfcheck.direct(f'https://localhost:{closed}', '0.0.0.0', mine=here, nat=no_nat)
    assert problem.startswith(f'The port {closed} of localhost (127.0.0.1) is closed')
    assert step == f'forward TCP port {closed} on your router or firewall to port 7441 of this machine'
    assert selfcheck.direct(f'https://localhost:{closed}', '0.0.0.0', mine=here, nat=lambda: True)[1].endswith(
        'connectaddress=<WSL address>')
    assert selfcheck.direct(f'https://localhost:{closed}', '127.0.0.1', mine=here, nat=no_nat) is None
    assert selfcheck.direct(f'https://localhost:{closed}', '0.0.0.0', mine=lambda: {'203.0.113.9'}, nat=no_nat) is None

    plain, port = listening()
    with plain:
        said = selfcheck.direct(f'https://localhost:{port}', '0.0.0.0', mine=here, nat=no_nat)
    assert said is not None and 'does not speak TLS' in said[0] and 'twilio-certificate' in said[1]

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(self_signed(tmp_path))
    secured, port = listening(lambda client: context.wrap_socket(client, server_side=True))
    with secured:
        said = selfcheck.direct(f'https://localhost:{port}', '0.0.0.0', mine=here, nat=no_nat)
    assert said is not None and 'a certificate Twilio would refuse' in said[0] and 'public CA' in said[1]


def test_a_raised_problem_is_the_system_agents_turn_once_it_starts(run, home, project_folder, tmp_path, monkeypatch,
                                                                    dispatch_runners):
    """Raised while no system agent runs, it waits as an active signal; the system agent that starts takes it as its
    turn after its first message, and it is no longer waiting."""
    from metaform import module, settings
    from metaform.data import Store
    run('enable', 'dispatch')
    for agent in ('claude', 'codex', 'gemini'):
        run('set', f'--dispatch-{agent}', f'"{sys.executable}" "{FAKE}"', cwd=project_folder)
    store = Store('proj')
    store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.engine')
    from metaform.modules import dispatch
    dispatch.anchor(module.context('dispatch', project_folder, project='proj'), store, 'code.engine')
    from metaform.modules import twilio  # after the CLI ran, which may have loaded the module afresh
    from metaform.modules.dispatch.signals import rows
    settings.put('twilio_enabled', True, project_folder)
    settings.put('twilio_public_url', DEAD, project_folder)
    twilio.troubled(module.context('twilio', project_folder, project='proj'),
                    {'ok': False, 'problems': [{'problem': 'The bridge does not answer.', 'next': 'metaform twilio serve'}],
                     'warnings': []}, asked=False)
    waiting = [one for one in rows(store) if one['signal'] == 'setup-not-working']
    assert len(waiting) == 1 and waiting[0]['signal_key'] and waiting[0]['feature'] == 'the phone'
    log = tmp_path / 'fake.jsonl'
    monkeypatch.setenv('FAKE_ACP_LOG', str(log))
    monkeypatch.setenv('FAKE_ACP_MODE', 'plain')
    monkeypatch.setenv('FAKE_ACP_MASCOT', '1')  # every turn after the first is answered
    agent = SystemAgent(verb_runner(project_folder, 'proj'), start_limit=60, turn_limit=60)

    async def answer():
        return [so_far async for so_far in agent.reply('Hello.')]
    try:
        said = asyncio.run(answer())
    finally:
        if agent.started.get('pid'):
            dispatch_runners.append((agent.started, project_folder, log))
    assert said and said[-1].endswith('The fake answers: Hello.')  # after its answer to the raised problem
    prompts = [json.dumps(entry['message']) for entry in map(json.loads, log.read_text().splitlines())
               if entry.get('message', {}).get('method') == 'session/prompt']
    turns = [one for one in prompts if 'may not be working' in one]
    assert len(turns) == 1 and 'The bridge does not answer.' in turns[0] and DEAD in turns[0]
    assert not [one for one in rows(store) if one['signal'] == 'setup-not-working']


def test_calls_texts_and_the_bridge_refuse_an_agents_session(run, home, monkeypatch):
    monkeypatch.setenv('METAFORM_SESSION', 'an-agent-session')
    for verb in (('call',), ('text', 'hello'), ('serve',), ('check', 'fix=true')):
        refused = run('twilio', *verb, ok=False)
        assert refused.returncode != 0 and "never run from an agent's session" in refused.stdout + refused.stderr
