"""twilio: talk with your system agent by phone, and be called or texted when something needs you, through Twilio.

Your own Twilio number answers with your system agent, your mascot, speaking: you call it, and it calls or texts you
when an agent waits on you, looks stuck, or the intake finishes, as you choose. Only your own numbers are accepted or
ever called. Twilio's credentials stay in the environment of the process that runs the bridge; nothing here stores
them or shows them to the page.

  serve   run the bridge, on 127.0.0.1, reached by Twilio only through twilio_public_url
  status  configured or not and why, the webhook URLs to paste into Twilio, which credentials are present by name
  call    ring your phone now, through the running bridge
  text    text your phone now
  test    a whole call simulated on this machine: no Twilio, no voice engine, no agent

The bridge, `bridge.py`, carries the call's audio to the voice module's transcription and the system agent's answers
back through the voice module's speech; `server.py` is its ASGI app and its security; `notify.py` decides what calls
or texts you; `api.py` is Twilio's signature, TwiML and REST calls.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from importlib import resources
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from metaform import home, prompt_files, settings
from metaform.data import Store
from metaform.module import Context, Module, Noun, Stop, Subscription, Verb, child_environment

from . import api, engines, notify, simulate
from .agent import SystemAgent, verb_runner
from .server import PIN_NAME, PROOFS, Config, Lines, Phone, Seen

SUPPORTED_OS = ('linux', 'macos', 'windows')
# The ASGI server, its websocket protocol (uvicorn's websockets-sansio is in 0.35 and later), and the simulated
# call's HTTP client.
DEPENDENCIES = ('starlette>=0.40', 'uvicorn>=0.35', 'websockets>=13', 'httpx>=0.28,<1')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a bridge for the person's own phone; nothing an agent on a hosted sandbox uses

PORT = 7441
E164 = re.compile(r'^\+[1-9][0-9]{6,14}$')
PIN = re.compile(r'^[0-9]{4,12}$')
AGENT_SESSION = ('METAFORM_SESSION', 'METAFORM_ROLE', 'METAFORM_WORK')  # what dispatch's runner sets on its agents
HERE = resources.files(__name__)


def listed(value: Any) -> list[str]:
    """A list setting's or a many noun's words, as text."""
    if isinstance(value, (list, tuple)):
        return [str(one) for one in cast(list[Any], value)]
    return [] if value in (None, '') else [str(value)]


def _check_number(value: Any, folder: Path) -> list[str] | None:
    return None if value in ('', None) or E164.match(str(value)) else \
        [f'{value} is not a phone number in E.164 form, such as +15551234567.']


def _check_numbers(value: Any, folder: Path) -> list[str] | None:
    wrong = [one for one in listed(value) if not E164.match(one)]
    return [f'Phone numbers are in E.164 form, such as +15551234567; not {", ".join(wrong)}.'] if wrong else None


def _check_public(value: Any, folder: Path) -> list[str] | None:
    if value in ('', None):
        return None
    parts = urlsplit(str(value))
    if parts.scheme != 'https' or not parts.hostname or parts.query or parts.fragment or parts.path not in ('', '/'):
        return ['twilio_public_url is the https address Twilio reaches, such as https://alice.metaform.ing, with no path.']
    return None


def _check_language(value: Any, folder: Path) -> list[str] | None:
    return None if isinstance(value, str) and re.match(r'^(auto|[a-z]{2,3})$', value) else \
        ['twilio_language is auto or a language code, such as en.']


# Who may call, who is called, and where Twilio reaches the bridge decide who talks with the person's agent and who
# pays for calls, so each is the person's alone: an agent over MCP cannot change them, CLI-011.
settings.boolean('twilio_enabled', False, scope='global', person_only=True, label='Phone',
                 help='Answer your Twilio number with your system agent, and call or text you as twilio_call_when and '
                      'twilio_text_when say. Off: nothing is served, called or texted.',
                 details='On, metaform web start also starts the bridge, and metaform twilio serve runs it on its own. '
                         'Twilio\'s credentials come from TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN (or TWILIO_API_KEY '
                         'and TWILIO_API_SECRET for the calls Metaform makes) in the environment of the process that '
                         'runs the bridge; they are never stored or shown. metaform twilio status says what is missing.',
                 section='Your phone', essential=90)
settings.text('twilio_number', '', scope='global', person_only=True, check=_check_number,
              help='Your Twilio phone number, in E.164 form, such as +15551234567: it answers you and calls you.',
              label='Twilio number', section='Your phone', essential=100)
settings.items('twilio_owner_numbers', [], scope='global', person_only=True, check=_check_numbers,
               help='Your own phone numbers, in E.164 form: the only callers answered and the only numbers called or '
                    'texted.',
               details='A call from any other number hears a short refusal and is hung up; a text from one is ignored. '
                       'Calls and texts Metaform starts go to the first number.',
               label='Your own numbers', section='Your phone')
settings.text('twilio_public_url', '', scope='global', person_only=True, check=_check_public,
              help='The public https address Twilio reaches the bridge at: your Metaform Node, your relay name, or a '
                   'tunnel of your own.',
              details='Such as https://alice.metaform.ing. Twilio posts to <address>/phone/voice and /phone/sms and opens '
                      'the call audio at wss://<address>/phone/stream. The bridge itself listens on 127.0.0.1 only; '
                      'the Node\'s Caddy routes /phone/* to it. It must be https: the bridge refuses to start otherwise.',
              label='Public address', section='Your phone')
settings.choice('twilio_caller_proof', list(PROOFS), 'attested-or-pin', scope='global', person_only=True,
                label='Caller proof',
                help='What a call or text from your number must show beyond its caller ID, which can be faked: '
                     'attested-or-pin, pin, attested, or caller-id.',
                details='attested-or-pin: a call whose caller ID its carrier fully attested (STIR/SHAKEN A) is answered, '
                        'any other is asked for your PIN on the keypad. pin: every call is asked for it. attested: only '
                        'fully attested calls; no PIN. caller-id: the number alone, which anyone can fake. The PIN is '
                        f'{PIN_NAME} in the environment of the process that runs the bridge, 4 to 12 digits. A text '
                        'has no attestation, so under any choice but caller-id it starts with the PIN, which is taken '
                        'off before your agent reads it; without a PIN, texts are ignored.',
                section='Your phone')
settings.items('twilio_call_when', [], scope='global', person_only=True,
               check=lambda value, folder: notify.check(listed(value), 'twilio_call_when'),  # pyright: ignore[reportUnknownLambdaType]
               help='What calls you: waiting-for-you, stuck, budget, intake-finished, or a dispatch signal name. None '
                    'by default.',
               details='waiting-for-you: an agent waits for your permission, an answer or a login, or stopped with its '
                       'ticket open. stuck: an agent spins, falls silent or fails the same way. Calls are at least '
                       'twilio_call_gap_minutes apart, and the same signal on the same ticket calls once an hour.',
               label='Call you when', section='Calls and texts')
settings.items('twilio_text_when', [], scope='global', person_only=True,
               check=lambda value, folder: notify.check(listed(value), 'twilio_text_when'),  # pyright: ignore[reportUnknownLambdaType]
               help='What texts you, from the same list as twilio_call_when. None by default.',
               label='Text you when', section='Calls and texts')
settings.number('twilio_call_gap_minutes', 15, min=0, max=1440, scope='global', person_only=True,
                help='The least time between calls Metaform places on its own, in minutes; your own phone call never '
                     'waits.',
                label='Least time between calls', section='Calls and texts')
settings.text('twilio_voice', '', scope='global',
              help="An ElevenLabs voice id, or a voice's name on your account, for the phone; empty speaks with your "
                   "mascot character's voice.",
              details='Phone audio is made on the server, so the phone speaks with ElevenLabs: ELEVENLABS_API_KEY must be '
                      'in the environment of the process that runs the bridge, and the text spoken goes to ElevenLabs. '
                      'Empty, the phone speaks in the voice elevenlabs_voices gives your mascot character; metaform '
                      'elevenlabs voices lists your account\'s voices.',
              label='Voice on the phone', section='On the line')
settings.text('twilio_language', 'auto', scope='global', check=_check_language,
              help='The language you speak on the phone, as a code such as en, or auto.',
              label='Language on the phone', section='On the line')
settings.choice('twilio_hearing', ['server', 'elevenlabs'], 'server', scope='global', person_only=True,
                help='Who hears you on the phone: server (Whisper on this machine) or elevenlabs (Scribe).',
                details='server needs the voice extra and a downloaded Whisper model; elevenlabs SENDS THE CALL AUDIO to '
                        'ElevenLabs. Twilio carries the call either way.',
                label='Hears you on the phone with', section='On the line')
settings.number('twilio_port', PORT, min=1024, max=65535, scope='global',
                help='The loopback port the bridge listens on; the Node routes /phone/* to 7441.',
                label='Bridge port', category='advanced')
settings.text('twilio_project', '', scope='global', person_only=True,
              help="The project whose system agent answers the phone; empty is the project of the folder it runs in.",
              label='Project the phone works on', category='advanced')


# ---------------------------------------------------------------------------------------------------- reading

def run_dir() -> Path:
    return home.home() / 'run' / 'twilio'


def run_file() -> Path:
    return run_dir() / 'twilio.json'


def log_file() -> Path:
    return run_dir() / 'twilio.log'


def write_log(line: str) -> None:
    """One line of what the bridge did, with its time: never what was said, never a credential."""
    stamped = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {line}'
    with contextlib.suppress(OSError):
        home.mkdir_private(run_dir())
        descriptor = os.open(log_file(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, 'a', encoding='utf-8') as out:
            out.write(stamped + '\n')
    print(stamped, file=sys.stderr, flush=True)


def recorded() -> dict[str, Any] | None:
    try:
        found: Any = json.loads(run_file().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def answering(record: dict[str, Any]) -> bool:
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{int(record["port"])}/phone/health', timeout=1) as answer:
            return answer.status == 200
    except (OSError, ValueError, KeyError):
        return False


def running() -> dict[str, Any] | None:
    found = recorded()
    return found if found is not None and answering(found) else None


def project_of(ctx: Context) -> str | None:
    return str(ctx.setting('twilio_project') or '') or ctx.project


def mascot(ctx: Context) -> str:
    named = settings.value('web_mascot', ctx.folder) if 'web_mascot' in settings.SCHEMA else None
    return str(named) if named and named != 'none' else ''


def masked(number: str) -> str:
    return number[:2] + '•' * max(0, len(number) - 6) + number[-4:] if len(number) > 6 else number


def public(ctx: Context) -> str:
    return str(ctx.setting('twilio_public_url') or '').rstrip('/')


def pin() -> str | None:
    """The PIN from the environment, when it is set and is 4 to 12 digits; never shown."""
    found = os.environ.get(PIN_NAME, '').strip()
    return found if PIN.match(found) else None


def persons_own(ctx: Context, what: str) -> None:
    """Stop when an agent's session runs this: placing calls, sending texts and running the bridge are the person's.
    The runner names its agent's session in the environment; this is a guard against an agent's mistakes, not a
    boundary, since an agent with a shell runs as the person's account and can change its own environment."""
    if any(os.environ.get(name) for name in AGENT_SESSION):
        raise Stop(f'metaform twilio {what} is the person\'s own, never run from an agent\'s session.',
                   'Say what you need in your ticket\'s note.')


def problems(ctx: Context, project: str | None = None) -> list[tuple[str, str]]:
    """What keeps the phone from working, each with the one step that fixes it, first things first."""
    found: list[tuple[str, str]] = []
    env = api.present()
    if not ctx.setting('twilio_enabled'):
        found.append(('The phone is off.', 'metaform set --twilio-enabled'))
    if not ctx.setting('twilio_number'):
        found.append(('No Twilio number is set.', 'metaform set --twilio-number +15551234567'))
    if not ctx.setting('twilio_owner_numbers'):
        found.append(('No owner number is set, so no caller would be answered.',
                      'metaform set --twilio-owner-numbers +15557654321'))
    url = public(ctx)
    if not url.startswith('https://'):
        found.append(('twilio_public_url is not an https address Twilio can reach.',
                      'metaform set --twilio-public-url https://<your node or tunnel>'))
    if not env[api.SID]:
        found.append((f'{api.SID} is not in the environment.', f'export {api.SID}=AC... before the bridge starts'))
    if not env[api.TOKEN]:
        found.append((f'{api.TOKEN} is not in the environment; it checks every webhook Twilio signs.',
                      f'export {api.TOKEN}=... before the bridge starts'))
    if os.environ.get(PIN_NAME, '').strip() and pin() is None:
        found.append((f'{PIN_NAME} is not 4 to 12 digits.', f'export {PIN_NAME}=<4 to 12 digits> before the bridge starts'))
    elif ctx.setting('twilio_caller_proof') == 'pin' and pin() is None:
        found.append((f'twilio_caller_proof is pin, and {PIN_NAME} is not in the environment, so no call could get in.',
                      f'export {PIN_NAME}=<4 to 12 digits> before the bridge starts'))
    if engines.voice_module(ctx.folder) is None:
        found.append(("The voice module's phone speech is not here, so the call could not be heard or spoken.",
                      'metaform enable voice'))
    elif not os.environ.get('ELEVENLABS_API_KEY', '').strip():
        found.append(('ELEVENLABS_API_KEY is not in the environment; the phone speaks with ElevenLabs.',
                      'export ELEVENLABS_API_KEY=... before the bridge starts'))
    if (project or project_of(ctx)) is None:
        found.append(('No project for this folder, so no system agent to answer.', 'metaform set --twilio-project <id>'))
    return found


def lines(ctx: Context) -> Lines:
    """The phone's lines from prompts.xml, filled with the person's mascot."""
    who = mascot(ctx) or 'your system agent'

    def read(name: str, **fills: str) -> str:
        return prompt_files.required(HERE, name, mascot=who, **fills)
    return Lines(greeting=read('greeting'), calling=lambda why: read('calling', why=why), on_call=read('on_call'),
                 on_callback=lambda why: read('on_callback', why=why), on_text=read('on_text'),
                 refusal=read('refusal'), busy=read('busy'), trouble=read('trouble'), pin=read('pin'),
                 pin_wrong=read('pin_wrong'))


# ---------------------------------------------------------------------------------------------------- verbs

def status(ctx: Context) -> dict[str, Any]:
    url = public(ctx)
    found = problems(ctx)
    live = running()
    owners = listed(ctx.setting('twilio_owner_numbers'))
    return {
        'enabled': bool(ctx.setting('twilio_enabled')), 'configured': not found,
        'problems': [{'problem': problem, 'next': step} for problem, step in found],
        'running': {'pid': live.get('pid'), 'port': live.get('port'), 'project': live.get('project')} if live else None,
        'twilio_number': masked(str(ctx.setting('twilio_number') or '')) or None,
        'owners': [masked(one) for one in owners],
        'webhooks': {'voice': f'{url}/phone/voice' if url else None, 'messaging': f'{url}/phone/sms' if url else None,
                     'stream': f'wss://{urlsplit(url).netloc}/phone/stream' if url else None,
                     'method': 'HTTP POST'},
        'bind': f'127.0.0.1:{int(ctx.setting("twilio_port"))}',
        'environment': {**api.present(), 'ELEVENLABS_API_KEY': bool(os.environ.get('ELEVENLABS_API_KEY', '').strip()),
                        PIN_NAME: pin() is not None},
        'caller_proof': ctx.setting('twilio_caller_proof'),
        'call_when': listed(ctx.setting('twilio_call_when')), 'text_when': listed(ctx.setting('twilio_text_when')),
        'hearing': ctx.setting('twilio_hearing'), 'voice': ctx.setting('twilio_voice') or f'{mascot(ctx) or "default"} (mascot)',
        'project': project_of(ctx), 'log': str(log_file()),
    }


def _free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            raise Stop(f'Port {port} on 127.0.0.1 is in use.', 'metaform set --twilio-port <another port>') from None


def serve(ctx: Context) -> dict[str, Any]:
    """Run the bridge until stopped: the ASGI app on 127.0.0.1, the signals it calls and texts about heard as they
    are raised."""
    persons_own(ctx, 'serve')
    found = problems(ctx)
    if found:
        raise Stop(found[0][0], found[0][1])
    live = running()
    if live is not None:
        raise Stop(f'The phone bridge already runs, process {live.get("pid")}.', 'metaform twilio status')
    port = int(ctx.setting('twilio_port'))
    _free(port)
    project = project_of(ctx)
    token = api.auth_token()
    voice_found = engines.voice_module(ctx.folder)
    if token is None or voice_found is None:
        raise Stop('The phone bridge needs the auth token and the voice module.', 'metaform twilio status')
    owners = tuple(listed(ctx.setting('twilio_owner_numbers')))
    language = str(ctx.setting('twilio_language'))
    agent = SystemAgent(verb_runner(ctx.folder, project))
    character = mascot(ctx) or None
    config = Config(public_url=public(ctx), twilio_number=str(ctx.setting('twilio_number')), owners=owners,
                    auth_token=token, control_token=secrets.token_urlsafe(32), lines=lines(ctx),
                    call_gap=float(ctx.setting('twilio_call_gap_minutes')) * 60,
                    proof=str(ctx.setting('twilio_caller_proof')), pin=pin())
    phone = Phone(config, agent=lambda: agent,
                  voice=lambda: engines.VoicePhone(voice_found, ctx.folder, character=character,
                                                   language=None if language == 'auto' else language,
                                                   hearing=str(ctx.setting('twilio_hearing')),
                                                   voice=str(ctx.setting('twilio_voice') or '') or None),
                  client=api.Client(), log=write_log, seen=Seen(run_dir() / 'seen.txt'))
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(phone.app(), host='127.0.0.1', port=port, ws='websockets-sansio',
                                           ws_max_size=65_536, log_level='warning', lifespan='off',
                                           proxy_headers=False, server_header=False, date_header=False))
    loop_held: list[asyncio.AbstractEventLoop] = []

    def later(work: Any) -> bool:
        if not loop_held:
            work.close()
            return False
        asyncio.run_coroutine_threadsafe(work, loop_held[0])
        return True

    def place(why: str) -> bool:
        """Place a call for a signal, or say it is held back by the gap or a call in progress, so it waits."""
        if not loop_held or phone.reserve() is not None:
            return False
        return later(_logged(phone.call(why, reserved=True)))

    def texting(why: str) -> str:
        return prompt_files.required(HERE, 'texting', why=why)

    notifier = notify.Notifier(calls=listed(ctx.setting('twilio_call_when')),
                               texts=listed(ctx.setting('twilio_text_when')),
                               place=place,
                               send=lambda why: later(_logged(phone.text(owners[0], texting(why)))),
                               clock=time.monotonic, task_of=lambda work_id: _task(project, work_id))
    had_intake = [_has_intake(project)]
    lock = threading.Lock()

    def heard(payload: dict[str, Any]) -> None:
        if project is None or payload.get('project') != project:
            return
        with lock:
            signal = notify.signal_in(payload)
            if signal is not None:
                done = notifier.heard(signal)
                if done:
                    write_log(f'{" and ".join(done)} for {signal.get("signal")}')
            if not had_intake[0] and 'intake-finished' in notifier.calls | notifier.texts and _has_intake(project):
                had_intake[0] = True
                notifier.heard({'signal': 'intake-finished', 'active': True})

    async def retrying() -> None:
        while True:
            await asyncio.sleep(notify.RETRY_SECONDS)
            with lock:
                done = notifier.retry()
            if done:
                write_log(', '.join(done) + ', held back until now')

    async def main() -> None:
        loop_held.append(asyncio.get_running_loop())
        again = asyncio.ensure_future(retrying())
        try:
            await server.serve()
        finally:
            again.cancel()

    def stopped(number: int, frame: Any) -> None:
        raise KeyboardInterrupt  # SIGTERM, from systemd, docker stop or a process manager, stops it as Ctrl-C does

    home.mkdir_private(run_dir())
    record = {'pid': os.getpid(), 'port': port, 'project': project, 'folder': str(ctx.folder),
              'control': config.control_token, 'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    descriptor = os.open(run_file(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as out:
        json.dump(record, out)
    write_log(f'bridge on 127.0.0.1:{port} for {public(ctx)}, project {project}')
    listener = ctx.listen(heard)
    # uvicorn takes SIGTERM while it serves and raises it again once it stops; with the default handler that ends the
    # process before the cleanup below, so the run file and its control token would stay behind.
    previous: Any = None
    with contextlib.suppress(ValueError):  # only the main thread can take signals
        previous = signal.signal(signal.SIGTERM, stopped)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        listener.close()
        if (recorded() or {}).get('pid') == os.getpid():
            run_file().unlink(missing_ok=True)
        write_log('bridge stopped')
        if previous is not None:
            with contextlib.suppress(ValueError):
                signal.signal(signal.SIGTERM, previous)
    return {'state': 'stopped', 'port': port}


async def _logged(work: Any) -> None:
    try:
        await work
    except Exception as error:  # noqa: BLE001  a failed call or text is the log's, never the listener's
        write_log(f'could not reach the owner: {type(error).__name__}: {error}')


def _task(project: str | None, work_id: str) -> str | None:
    if project is None:
        return None
    try:
        return Store(project).ticket(work_id).work.task or None
    except Exception:  # noqa: BLE001  a ticket gone or unreadable is told without its task
        return None


def _has_intake(project: str | None) -> bool:
    if project is None:
        return False
    try:
        return bool(Store(project).has_intake())
    except Exception:  # noqa: BLE001  a project not yet readable has no intake to tell of
        return False


def _control(path: str, asked: dict[str, Any]) -> dict[str, Any]:
    live = running()
    if live is None:
        raise Stop('The phone bridge is not running, so a call could not be answered.', 'metaform twilio serve')
    request = urllib.request.Request(f'http://127.0.0.1:{int(live["port"])}{path}', data=json.dumps(asked).encode(),
                                     method='POST', headers={'Authorization': f'Bearer {live.get("control", "")}',
                                                             'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            found: Any = json.loads(answer.read() or b'{}')
    except urllib.error.HTTPError as error:
        said: Any = json.loads(error.read() or b'{}') if error.code == 400 else {'error': f'answered {error.code}'}
        raise Stop(f'The phone bridge could not: {said.get("error")}', 'metaform twilio status') from None
    except OSError as error:
        raise Stop(f'The phone bridge did not answer: {error}', 'metaform twilio status') from None
    return cast(dict[str, Any], found) if isinstance(found, dict) else {}


def _owner(ctx: Context) -> str:
    owners = listed(ctx.setting('twilio_owner_numbers'))
    chosen = str(ctx.nouns.get('to') or (owners[0] if owners else ''))
    if chosen not in owners:
        raise Stop('Calls and texts go only to the numbers in twilio_owner_numbers.',
                   'metaform set --twilio-owner-numbers +15557654321')
    return chosen


def call(ctx: Context) -> dict[str, Any]:
    persons_own(ctx, 'call')
    if not ctx.setting('twilio_enabled'):
        raise Stop('The phone is off.', 'metaform set --twilio-enabled')
    reason = ' '.join(listed(ctx.nouns.get('reason')))
    return _control('/control/call', {'to': _owner(ctx), 'reason': reason or 'you asked me to call'})


def text(ctx: Context) -> dict[str, Any]:
    persons_own(ctx, 'text')
    if not ctx.setting('twilio_enabled'):
        raise Stop('The phone is off.', 'metaform set --twilio-enabled')
    body = ' '.join(listed(ctx.nouns['text']))
    to = _owner(ctx)
    if running() is not None:
        return _control('/control/text', {'to': to, 'text': body})
    number = str(ctx.setting('twilio_number') or '')
    if not number:
        raise Stop('No Twilio number is set.', 'metaform set --twilio-number +15551234567')
    try:
        sent = api.Client().text(to=to, from_=number, body=body)
    except OSError as error:
        raise Stop(str(error), 'metaform twilio status') from None
    return {'sent': True, 'sid': sent.get('sid')}


async def test(ctx: Context) -> dict[str, Any]:
    """A whole call simulated on this machine, with what it measured."""
    found = await simulate.run(pause=_voice_pause(ctx))
    found.pop('log', None)
    return found


def _voice_pause(ctx: Context) -> float:
    found = engines.voice_module(ctx.folder)
    return float(getattr(found, 'pause', engines.PAUSE)) if found is not None else engines.PAUSE


def web_started(payload: dict[str, Any], ctx: Context) -> dict[str, Any] | None:
    """Start the bridge beside the web GUI when the person has turned the phone on and it is set up; detached, so it
    runs on as the web GUI does."""
    project = str(ctx.setting('twilio_project') or '') or payload.get('project') or None
    if not ctx.setting('twilio_enabled') or running() is not None or problems(ctx, project):
        return None
    folder = Path(str(payload.get('folder') or ctx.folder))
    home.mkdir_private(run_dir())
    options: dict[str, Any] = {'start_new_session': True} if os.name != 'nt' else \
        {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)}
    descriptor = os.open(log_file(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'ab') as written:
        process = subprocess.Popen([sys.executable, '-m', 'metaform', 'twilio', 'serve'], cwd=folder,
                                   stdin=subprocess.DEVNULL, stdout=written, stderr=written, env=child_environment(),
                                   **options)
    return {'twilio': 'starting', 'pid': process.pid}


MODULE = Module(
    id='twilio',
    summary='Talk with your system agent by phone, and be called or texted when something needs you, through Twilio.',
    purpose='Answers your own Twilio number with your system agent, your mascot, speaking, and calls or texts you when '
            'an agent waits on you or looks stuck, as you choose. Only your own numbers are answered or called; '
            "Twilio's credentials stay in the environment. Details: metaform help twilio.",
    details='Set twilio_number, twilio_owner_numbers and twilio_public_url, put TWILIO_ACCOUNT_SID, '
            'TWILIO_AUTH_TOKEN, ELEVENLABS_API_KEY and a METAFORM_TWILIO_PIN in the environment, turn on twilio_enabled, '
            'and paste the '
            'webhook URLs metaform twilio status shows into the number\'s settings in Twilio\'s console.',
    verbs=(
        Verb('status', status, "Show whether the phone is set up and why not, the webhook URLs to paste into Twilio, "
                               'and which credentials are in the environment, by name only.', effect='read', surfaces=('cli',)),
        Verb('serve', serve, 'Run the phone bridge on 127.0.0.1 until stopped, answering your Twilio number with your '
                             'system agent.',
             switches=('twilio_port', 'twilio_public_url'), surfaces=('cli',), effect='write', open_world=True),
        Verb('call', call, 'Ring your phone now through the running bridge; your system agent is on the line.',
             nouns=(Noun('to', 'One of twilio_owner_numbers; the first by default.', required=False),
                    Noun('reason', 'What the agent opens the call with.', required=False, many=True)),
             surfaces=('cli',), effect='write', open_world=True),
        Verb('text', text, 'Text your phone now.',
             nouns=(Noun('to', 'One of twilio_owner_numbers; the first by default.', required=False),
                    Noun('text', 'The text.', many=True)),
             surfaces=('cli',), effect='write', open_world=True),
        Verb('test', test, 'Simulate a whole call on this machine, with no Twilio, voice engine or agent, and show the '
                           'time from the end of your speech to the first audio back.',
             surfaces=('cli',), effect='read', task=True),
    ),
    subscriptions=(Subscription('web.started', web_started),),
    start=None,
    stop=None,
    status=None,
    tables=None,
    data=None,
    node_read=None,
    node_count=None,
    work_read=None,
    item_read=None,
    items_at=None,
    item_kinds=(),
    toolbar=(),
    panes=(),
    settings_category='phone',
)
