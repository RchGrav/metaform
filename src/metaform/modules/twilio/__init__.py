"""twilio: talk with your system agent by phone, and be called or texted when something needs you, through Twilio.

Your own Twilio number answers with your system agent, your mascot, speaking: you call it, and it calls or texts you
when an agent waits on you, looks stuck, or the intake finishes, as you choose. Only your own numbers are accepted or
ever called. Twilio's credentials stay in the environment of the process that runs the bridge; nothing here stores
them or shows them to the page.

  serve   run the bridge, on twilio_bind (127.0.0.1 by default), reached by Twilio through twilio_public_url
  status  configured or not and why, the webhook URLs to paste into Twilio, which credentials are present by name
  call    ring your phone now, through the running bridge
  text    text your phone now
  test    a whole call simulated on this machine: no Twilio, no voice engine, no agent
  check   where Twilio sends the number's calls and texts, whether the bridge answers there, and with fix=true, asked
          by the person, the number pointed at the bridge; a problem it finds on its own goes to the person's system
          agent as dispatch's setup-not-working signal, never to the terminal or the page

The bridge, `bridge.py`, carries the call's audio to the voice module's transcription and the system agent's answers
back through the voice module's speech; `server.py` is its ASGI app and its security; `notify.py` decides what calls
or texts you; `api.py` is Twilio's signature, TwiML and REST calls; `selfcheck.py` is the check.
"""
from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import os
import re
import secrets
import signal
import socket
import ssl
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
from metaform.module import Context, Module, Noun, Status, Stop, Subscription, Verb, child_environment
from metaform.module import context as module_context

from . import api, engines, notify, selfcheck, simulate
from .agent import SystemAgent, verb_runner
from .server import PIN_NAME, PROOFS, Config, Lines, Phone, Seen, Serving

SUPPORTED_OS = ('linux', 'macos', 'windows')
# The ASGI server, its websocket protocol (uvicorn's websockets-sansio is in 0.35 and later), and the simulated
# call's HTTP client.
DEPENDENCIES = ('starlette>=0.40', 'uvicorn>=0.35', 'websockets>=13', 'httpx>=0.28,<1')
SHIPS_DISABLED = False
REMOTE_AGENT = False  # a bridge for the person's own phone; nothing an agent on a hosted sandbox uses

# The loopback port the bridge listens on. A Node's Caddy routes /phone/* to this port, node/config.py TWILIO_PORT, so
# any other value breaks calls there; settings cleanup 2026-10-15 made it fixed. A port another program holds is said
# as such when serve starts.
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


def _check_bind(value: Any, folder: Path) -> list[str] | None:
    try:
        ipaddress.ip_address(str(value))
    except ValueError:
        return [f'twilio_bind is an IP address of this machine, such as 127.0.0.1, 0.0.0.0 or 192.168.1.20; not {value}.']
    return None


def _check_certificate(value: Any, folder: Path) -> list[str] | None:
    if value in ('', None):
        return None
    try:
        ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(str(value))
    except (OSError, ssl.SSLError) as error:
        return [(f'twilio_certificate is a PEM file holding the certificate chain and its private key; {value} could '
                 f'not be loaded: {error}.')]
    return None


# Who may call, who is called, and where Twilio reaches the bridge decide who talks with the person's agent and who
# pays for calls, so each is the person's alone: an agent over MCP cannot change them, CLI-011.
settings.boolean('twilio_enabled', False, scope='global', person_only=True, label='Phone',
                 help='Answer your Twilio number with your system agent, and call or text you as twilio_call_when and '
                      'twilio_text_when say. Off: nothing is served, called or texted.',
                 details='On, metaform web start also starts the bridge, and metaform twilio serve runs it on its own. '
                         'Twilio\'s credentials come from TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN (or TWILIO_API_KEY '
                         'and TWILIO_API_SECRET for the calls Metaform makes) in the environment of the process that '
                         'runs the bridge; they are never stored or shown. metaform twilio status says what is missing.',
                 heading='Your phone', essential=90)
settings.text('twilio_number', '', scope='global', person_only=True, check=_check_number,
              help='Your Twilio phone number, in E.164 form, such as +15551234567: it answers you and calls you.',
              label='Twilio number', heading='Your phone', essential=100)
settings.items('twilio_owner_numbers', [], scope='global', person_only=True, check=_check_numbers,
               help='Your own phone numbers, in E.164 form: the only callers answered and the only numbers called or '
                    'texted.',
               details='A call from any other number hears a short refusal and is hung up; a text from one is ignored. '
                       'Calls and texts Metaform starts go to the first number.',
               label='Your own numbers', heading='Your phone')
settings.text('twilio_public_url', '', scope='global', person_only=True, check=_check_public,
              help='The public https address Twilio reaches the bridge at: your Metaform Node, your relay name, or a '
                   'tunnel of your own.',
              details='Such as https://alice.metaform.ing. Twilio posts to <address>/phone/voice and /phone/sms and opens '
                      'the call audio at wss://<address>/phone/stream. The bridge itself listens on 127.0.0.1 only; '
                      'the Node\'s Caddy routes /phone/* to it. It must be https: the bridge refuses to start otherwise.',
              label='Public address', heading='Your phone')
# A direct route: the person's router or firewall forwards a port straight to the bridge, with no Node or tunnel. Who
# can reach the bridge and with what certificate is the person's alone, as the public address is.
settings.text('twilio_bind', '127.0.0.1', scope='global', person_only=True, check=_check_bind,
              help='The address the bridge listens on, port 7441: 127.0.0.1 behind a Node or tunnel; this machine\'s '
                   'own address, or 0.0.0.0, for a port your router or firewall forwards to it.',
              details='Off loopback, Twilio reaches the bridge directly, so it serves TLS itself from twilio_certificate, '
                      'or you leave that empty behind your own TLS terminator. Every webhook must still carry Twilio\'s '
                      'signature. metaform help twilio says what to forward.',
              label='Listen on', heading='Your phone', category='advanced')
settings.text('twilio_certificate', '', scope='global', person_only=True, check=_check_certificate,
              help='A PEM file with the certificate chain and its private key, for the bridge to serve https itself on '
                   'a direct route; empty serves plain http behind your own TLS terminator.',
              details='One file, as Python\'s ssl.load_cert_chain reads it: the certificate, any intermediates, and the '
                      'key, such as Let\'s Encrypt\'s fullchain.pem and privkey.pem joined. Twilio refuses a '
                      'self-signed certificate.',
              label='TLS certificate', heading='Your phone', category='advanced')
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
                heading='Your phone')
settings.items('twilio_call_when', [], scope='global', person_only=True, choices=notify.CHOICES,
               check=lambda value, folder: notify.check(listed(value), 'twilio_call_when'),  # pyright: ignore[reportUnknownLambdaType]
               help='What calls you: waiting-for-you, stuck, budget, intake-finished, or one signal of those groups. None '
                    'by default.',
               details='waiting-for-you: an agent waits for your permission, an answer or a login, or stopped with its '
                       'ticket open. stuck: an agent spins, falls silent or fails the same way. Calls are at least '
                       'twilio_call_gap_minutes apart, and the same signal on the same ticket calls once an hour.',
               label='Call you when', heading='Calls and texts')
settings.items('twilio_text_when', [], scope='global', person_only=True, choices=notify.CHOICES,
               check=lambda value, folder: notify.check(listed(value), 'twilio_text_when'),  # pyright: ignore[reportUnknownLambdaType]
               help='What texts you, from the same list as twilio_call_when. None by default.',
               label='Text you when', heading='Calls and texts')
settings.number('twilio_call_gap_minutes', 15, min=0, max=1440, scope='global', person_only=True,
                help='The least time between calls Metaform places on its own, in minutes; your own phone call never '
                     'waits.',
                label='Least time between calls', heading='Calls and texts')
settings.text('twilio_voice', '', scope='global',
              help="An ElevenLabs voice id, or a voice's name on your account, for the phone; empty speaks with your "
                   "mascot character's voice.",
              details='Phone audio is made on the server, so the phone speaks with ElevenLabs: ELEVENLABS_API_KEY must be '
                      'in the environment of the process that runs the bridge, and the text spoken goes to ElevenLabs. '
                      'Empty, the phone speaks in the voice elevenlabs_voices gives your mascot character; metaform '
                      'elevenlabs voices lists your account\'s voices.',
              label='Voice on the phone', heading='On the line')
settings.choice('twilio_hearing', ['server', 'elevenlabs'], 'server', scope='global', person_only=True,
                help='Who hears you on the phone: server (Whisper on this machine) or elevenlabs (Scribe).',
                details='server needs the voice extra and a downloaded Whisper model; elevenlabs SENDS THE CALL AUDIO to '
                        'ElevenLabs. Twilio carries the call either way.',
                label='Hears you on the phone with', heading='On the line')
def _projects(ctx: Context) -> list[str]:
    """Empty, the project of the folder the bridge runs in, then every registered project."""
    return ['', *(record.project_id for record in home.projects())]


settings.choice('twilio_project', _projects, '',
                scope='global', person_only=True,
                help="The project whose system agent answers the phone; empty is the project of the folder it runs in.",
                label='Project the phone works on', category='advanced')


# ---------------------------------------------------------------------------------------------------- reading

def run_dir() -> Path:
    return home.home() / 'run' / 'twilio'


def run_file() -> Path:
    return run_dir() / 'twilio.json'


def log_file() -> Path:
    return run_dir() / 'twilio.log'


def write_log(line: str, *, echo: bool = True) -> None:
    """One line of what the bridge did, with its time: never what was said, never a credential. `echo` also writes it
    to standard error, for whoever runs `twilio serve` in a terminal; the check's lines are the log's alone."""
    stamped = f'{time.strftime("%Y-%m-%dT%H:%M:%S")} {line}'
    with contextlib.suppress(OSError):
        home.mkdir_private(run_dir())
        descriptor = os.open(log_file(), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(descriptor, 'a', encoding='utf-8') as out:
            out.write(stamped + '\n')
    if echo:
        print(stamped, file=sys.stderr, flush=True)


def check_file() -> Path:
    return run_dir() / 'check.json'


def raised_file() -> Path:
    """What the check last raised to the system agent: its findings' fingerprint, when, and whether anyone has asked
    for the check since, which says the person took it up."""
    return run_dir() / 'raised.json'


def recorded(path: Path | None = None) -> dict[str, Any] | None:
    try:
        found: Any = json.loads((path or run_file()).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], found) if isinstance(found, dict) else None


def local_url(record: dict[str, Any], path: str) -> str:
    """The running bridge's own address on this machine: loopback when it listens there or on every address, else the
    address it listens on; https when it serves TLS itself."""
    bind = str(record.get('bind') or '127.0.0.1')
    host = '127.0.0.1' if bind in ('0.0.0.0', '::') or selfcheck.loopback(bind) else bind
    host = f'[{host}]' if ':' in host else host
    return f'{"https" if record.get("tls") else "http"}://{host}:{int(record["port"])}{path}'


def _unverified() -> ssl.SSLContext:
    """For the bridge's own address on this machine only: its certificate names the public host, not this address."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def answering(record: dict[str, Any]) -> bool:
    try:
        with urllib.request.urlopen(local_url(record, '/phone/health'), timeout=1,
                                    context=_unverified() if record.get('tls') else None) as answer:
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


def setup_of(ctx: Context) -> selfcheck.Setup:
    """What the check compares Twilio's side with; the address is the one the running bridge serves, when it runs."""
    live = running()
    number = str(ctx.setting('twilio_number') or '')
    return selfcheck.Setup(number=number, shown=masked(number),
                           public=str((live or {}).get('public') or public(ctx)).rstrip('/'), running=live is not None,
                           enabled=bool(ctx.setting('twilio_enabled')),
                           bind=str((live or {}).get('bind') or ctx.setting('twilio_bind') or '127.0.0.1'))


def begun(ctx: Context) -> list[str]:
    """What the person has set up of the phone, in words: a number, Twilio's credentials, a public address. Empty, the
    phone is not in use, and nothing is checked or raised."""
    found: list[str] = []
    if ctx.setting('twilio_number'):
        found.append(f'the Twilio number {masked(str(ctx.setting("twilio_number")))}')
    with contextlib.suppress(OSError):
        api.credentials()
        found.append("Twilio's credentials")
    if public(ctx):
        found.append(f'the public address {public(ctx)}')
    return found


# The signal a module raises when a feature the person set up is not working, dispatch's `setup-not-working`: the
# person's system agent takes it as its next turn and brings it up with them. A raised one waits this long, untaken, before
# it is raised again on the same findings, as a problem the person let be that still stands.
TROUBLE = 'setup-not-working'
AGAIN_SECONDS = 24 * 3600


def raised() -> dict[str, Any]:
    return recorded(raised_file()) or {}


def troubled(ctx: Context, report: dict[str, Any], *, asked: bool) -> None:
    """Tell the person's system agent, by the dispatch signal TROUBLE, when the phone the person set up is not working:
    once for each set of findings, and again only when they change, or when nobody asked for the check within a day of
    raising them and they still stand. A check someone asked for, `twilio check` or `twilio_check`, is that person
    taking it up: it raises nothing and marks what was raised as taken. Findings that are gone clear the signal."""
    kept = raised()
    project = project_of(ctx)
    if report['ok'] or not report['problems']:
        if kept:
            raised_file().unlink(missing_ok=True)
            if kept.get('key') and project:
                _publish(ctx, project, {'signal': TROUBLE, 'module': 'twilio', 'key': kept['key'], 'clear': True})
        return
    key = selfcheck.findings(report)
    if asked:
        if kept.get('key') == key and not kept.get('taken'):
            home.write_private(raised_file(), json.dumps({**kept, 'taken': True}))
        return
    what = begun(ctx)
    if not what or not ctx.setting('twilio_enabled') or project is None:
        return
    now = time.time()
    if kept.get('key') == key and (kept.get('taken') or now - float(kept.get('at') or 0) < AGAIN_SECONDS):
        return
    if kept.get('key') and kept['key'] != key:
        _publish(ctx, project, {'signal': TROUBLE, 'module': 'twilio', 'key': kept['key'], 'clear': True})
    home.mkdir_private(run_dir())
    home.write_private(raised_file(), json.dumps({'key': key, 'at': now, 'taken': False}))
    write_log(f'check: raised {TROUBLE} to the system agent, findings {key}', echo=False)
    _publish(ctx, project, {
        'signal': TROUBLE, 'module': 'twilio', 'key': key, 'feature': 'the phone',
        'set_up': ', '.join(what), 'look': 'twilio_status and twilio_check, or metaform twilio status and check',
        'report': {name: report.get(name) for name in ('checked', 'number', 'number_urls', 'bridge', 'expected',
                                                        'problems', 'warnings')}})


def _publish(ctx: Context, project: str, payload: dict[str, Any]) -> None:
    """Publish to dispatch for the project whose system agent answers the phone, which may not be the folder's."""
    target = ctx if project == ctx.project else module_context('twilio', ctx.folder, project=project)
    with contextlib.suppress(Exception):  # dispatch off, or its store unreadable: the log and check.json still say it
        target.publish('signal.raised', payload)


def checked(ctx: Context, *, fix: bool = False, client: api.Client | None = None,
            probe: selfcheck.Probe | None = None, route: selfcheck.Direct | None = None,
            asked: bool = False) -> dict[str, Any]:
    """Run the check, or the fix the person asked for, and keep its report, `check.json`, for `twilio status`; each
    problem, warning and change goes to the log and nowhere else. A problem found by a check nobody asked for is raised
    to the person's system agent, `troubled`."""
    setup = setup_of(ctx)
    client = client or api.Client()
    probe = probe or selfcheck.answers
    route = route or selfcheck.direct
    report = selfcheck.fix(setup, client, probe, route) if fix else selfcheck.check(setup, client, probe, route)
    fixed = report.get('fixed')
    if fixed:
        write_log(f'check: number {setup.shown} pointed at {fixed["now"]}, was {fixed["was"]}, as the person asked'
                  if fixed['changed'] else f'check: number {setup.shown} already pointed at the bridge', echo=False)
    for problem in report['problems']:
        write_log(f'check: {problem["problem"]} Next: {problem["next"]}', echo=False)
    for warning in report['warnings']:
        write_log(f'check: warning: {warning}', echo=False)
    if report['ok']:
        write_log(f'check: number {setup.shown} sends calls and texts to the bridge at {setup.public}, which answers',
                  echo=False)
    home.mkdir_private(run_dir())
    home.write_private(check_file(), json.dumps(report))
    troubled(ctx, report, asked=asked)
    return report


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
        'bind': f'{ctx.setting("twilio_bind")}:{PORT}',
        'tls': 'served by the bridge' if ctx.setting('twilio_certificate') else
               'by your Node, tunnel or TLS terminator',
        'environment': {**api.present(), 'ELEVENLABS_API_KEY': bool(os.environ.get('ELEVENLABS_API_KEY', '').strip()),
                        PIN_NAME: pin() is not None},
        'caller_proof': ctx.setting('twilio_caller_proof'),
        'call_when': listed(ctx.setting('twilio_call_when')), 'text_when': listed(ctx.setting('twilio_text_when')),
        'hearing': ctx.setting('twilio_hearing'), 'voice': ctx.setting('twilio_voice') or f'{mascot(ctx) or "default"} (mascot)',
        'project': project_of(ctx), 'log': str(log_file()),
        'check': recorded(check_file()),  # the last `twilio check`, kept; status itself asks Twilio nothing
    }


def _free(bind: str, port: int) -> None:
    with socket.socket(socket.AF_INET6 if ':' in bind else socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((bind, port))
        except OSError as error:
            raise Stop(f'The bridge cannot listen on {bind}:{port}: {error.strerror or error}. Its port is always '
                       f'{port}, where a Node routes /phone/*.',
                       f'stop the program that holds port {port}, or metaform set --twilio-bind <an address of this '
                       'machine>, then metaform twilio serve') from None


def _certificate(ctx: Context) -> str | None:
    """The PEM the bridge serves TLS from, checked loadable before it starts, so a bad file is said as such."""
    path = str(ctx.setting('twilio_certificate') or '')
    if not path:
        return None
    said = _check_certificate(path, ctx.folder)
    if said:
        raise Stop(said[0], 'metaform set --twilio-certificate <PEM with the chain and key>')
    return path


def serve(ctx: Context) -> dict[str, Any]:
    """Run the bridge until stopped: the ASGI app on twilio_bind, 127.0.0.1 unless the person chose a direct route,
    with TLS from twilio_certificate when it is set; the signals it calls and texts about heard as they are raised."""
    persons_own(ctx, 'serve')
    found = problems(ctx)
    if found:
        raise Stop(found[0][0], found[0][1])
    live = running()
    if live is not None:
        raise Stop(f'The phone bridge already runs, process {live.get("pid")}.', 'metaform twilio status')
    port = PORT
    bind = str(ctx.setting('twilio_bind') or '127.0.0.1')
    certificate = _certificate(ctx)
    _free(bind, port)
    project = project_of(ctx)
    token = api.auth_token()
    voice_found = engines.voice_module(ctx.folder)
    if token is None or voice_found is None:
        raise Stop('The phone bridge needs the auth token and the voice module.', 'metaform twilio status')
    owners = tuple(listed(ctx.setting('twilio_owner_numbers')))
    agent = SystemAgent(verb_runner(ctx.folder, project), project=project, listening=False)  # hears the bridge's listener
    character = mascot(ctx) or None
    config = Config(public_url=public(ctx), twilio_number=str(ctx.setting('twilio_number')), owners=owners,
                    auth_token=token, control_token=secrets.token_urlsafe(32), lines=lines(ctx),
                    call_gap=float(ctx.setting('twilio_call_gap_minutes')) * 60,
                    proof=str(ctx.setting('twilio_caller_proof')), pin=pin(), bind=bind)
    phone = Phone(config, agent=lambda: agent,
                  voice=lambda: engines.VoicePhone(voice_found, ctx.folder, character=character,
                                                   language=None,  # voice's own voice_language decides
                                                   hearing=str(ctx.setting('twilio_hearing')),
                                                   voice=str(ctx.setting('twilio_voice') or '') or None),
                  client=api.Client(), log=write_log, seen=Seen(run_dir() / 'seen.txt'))
    import uvicorn
    server = Serving(uvicorn.Config(phone.app(), host=bind, port=port, ws='websockets-sansio',
                                    ws_max_size=65_536, log_level='warning', lifespan='off',
                                    proxy_headers=False, server_header=False, date_header=False,
                                    ssl_certfile=certificate))
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
                               clock=time.monotonic, task_of=lambda work_id: _task(project, work_id),
                               call_free=phone.free_at)
    had_intake = [_has_intake(project)]
    lock = threading.Lock()
    held_back: list[asyncio.Event] = []  # set when what holds a call or text back may have changed

    def stir() -> None:
        if loop_held and held_back:
            with contextlib.suppress(RuntimeError):  # the loop has closed: the bridge is stopping
                loop_held[0].call_soon_threadsafe(held_back[0].set)
    phone.ended.append(stir)  # a call in progress held the others back

    def heard(payload: dict[str, Any]) -> None:
        if project is None or payload.get('project') != project:
            return
        agent.heard(payload)
        with lock:
            signal = notify.signal_in(payload)
            if signal is not None:
                done = notifier.heard(signal)
                if done:
                    write_log(f'{" and ".join(done)} for {signal.get("signal")}')
            if not had_intake[0] and 'intake-finished' in notifier.calls | notifier.texts and _has_intake(project):
                had_intake[0] = True
                notifier.heard({'signal': 'intake-finished', 'active': True})
            if notifier.waiting:
                stir()

    async def retrying() -> None:
        """What was held back goes once it may: when the gap that held it ends, by the clock, or when the call in
        progress ends, by the phone's own event; a signal held back since wakes it to read the new time."""
        held_back.append(asyncio.Event())
        while True:
            with lock:
                due = notifier.due()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(held_back[0].wait(), None if due is None else max(0.0, due - time.monotonic()))
            held_back[0].clear()
            with lock:
                done = notifier.retry()
            if done:
                write_log(', '.join(done) + ', held back until now')

    async def checking() -> None:
        """Once the bridge listens, check that Twilio sends the number's calls and texts to it and that it answers
        there; the report goes to the log and to the page's notice. Its failure is the log's, never the bridge's."""
        await server.ready.wait()
        try:
            await asyncio.to_thread(checked, ctx)
        except Exception as error:  # noqa: BLE001
            write_log(f'check: could not run: {type(error).__name__}: {error}')

    async def main() -> None:
        loop_held.append(asyncio.get_running_loop())
        again = asyncio.ensure_future(retrying())
        first = asyncio.ensure_future(checking())
        try:
            await server.serve()
        finally:
            again.cancel()
            first.cancel()

    def stopped(number: int, frame: Any) -> None:
        raise KeyboardInterrupt  # SIGTERM, from systemd, docker stop or a process manager, stops it as Ctrl-C does

    home.mkdir_private(run_dir())
    record = {'pid': os.getpid(), 'port': port, 'bind': bind, 'tls': certificate is not None, 'project': project,
              'folder': str(ctx.folder), 'public': public(ctx), 'control': config.control_token,
              'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    descriptor = os.open(run_file(), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as out:
        json.dump(record, out)
    write_log(f'bridge on {"https" if certificate else "http"}://{bind}:{port} for {public(ctx)}, project {project}')
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
    request = urllib.request.Request(local_url(live, path), data=json.dumps(asked).encode(),
                                     method='POST', headers={'Authorization': f'Bearer {live.get("control", "")}',
                                                             'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30, context=_unverified() if live.get('tls') else None) as answer:
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


def check(ctx: Context) -> dict[str, Any]:
    """Where Twilio sends the number's calls and texts against where the bridge answers; with fix=true, the number
    pointed at the bridge, the person's own step."""
    fix = bool(ctx.nouns.get('fix'))
    if fix:
        if ctx.surface == 'mcp':  # changing where the number sends calls is the person's, as a person-only setting is
            raise Stop("Pointing the number at the bridge changes where Twilio sends the person's calls, so it is the "
                       "person's own step.", 'ask the person to run metaform twilio check fix=true')
        persons_own(ctx, 'check fix=true')
    return checked(ctx, fix=fix, asked=True)


def helps(folder: Path) -> bool:
    """Whether twilio_status and twilio_check are listed to an agent here: only once the person has begun setting up
    the phone, and only to the person's own AI tool or their system agent, who troubleshoots it with them; every other
    agent's context stays without them. Reads settings and the environment, never the network."""
    if os.environ.get('METAFORM_ROLE') not in (None, '', 'none', 'system'):
        return False
    if settings.value('twilio_number', folder) or settings.value('twilio_public_url', folder):
        return True
    env = api.present()
    return bool(env[api.SID] and env[api.TOKEN])


def module_status(ctx: Context) -> Status:
    """The last check's first problem, as `metaform status` says it to whoever asks; read from its report, so nothing
    here reaches the network. It gives the page no notice: a problem goes to the person's system agent, `troubled`. A
    report of another number than the one set now says nothing."""
    report = recorded(check_file())
    if report is None or report.get('number') != (masked(str(ctx.setting('twilio_number') or '')) or None):
        return Status()
    said = selfcheck.headline(report)
    if said is None:
        return Status(lines=(f'Phone: Twilio reaches the bridge, checked {report.get("checked")}.',))
    return Status(lines=(f'Phone: checked {report.get("checked")}: {said}',))


def _voice_pause(ctx: Context) -> float:
    found = engines.voice_module(ctx.folder)
    return float(getattr(found, 'pause', engines.PAUSE)) if found is not None else engines.PAUSE


def web_started(payload: dict[str, Any], ctx: Context) -> dict[str, Any] | None:
    """Start the bridge beside the web GUI when the person has turned the phone on and it is set up; detached, so it
    runs on as the web GUI does; the bridge checks the number once it listens. With the phone on but the bridge not
    started here, the check runs now once the person has begun setting it up. With the phone off, nothing. Either way
    nothing is printed: the findings go to the log and check.json, and a problem to the person's system agent."""
    if not ctx.setting('twilio_enabled'):
        return None
    project = str(ctx.setting('twilio_project') or '') or payload.get('project') or None
    if running() is not None or problems(ctx, project):
        if not begun(ctx):
            return None
        report = checked(ctx)
        return {'twilio': 'checked', 'ok': report['ok'], 'problems': len(report['problems'])}
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
                               'and which credentials are in the environment, by name only.', effect='read',
             needs_project=False, listed=helps),
        Verb('serve', serve, 'Run the phone bridge on twilio_bind, 127.0.0.1 by default, until stopped, answering your '
                             'Twilio number with your system agent.',
             switches=('twilio_public_url',), surfaces=('cli',), effect='write', open_world=True),
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
        Verb('check', check, "Check where Twilio sends your number's calls and texts, and that the bridge answers "
                             'there; fix=true points the number at the bridge.',
             nouns=(Noun('fix', 'true: set the number\'s voice and SMS addresses to the bridge\'s, only when it answers '
                                'there; the person\'s own step, on the command line.', kind='bool', required=False),),
             effect='write', open_world=True, needs_project=False, listed=helps),
    ),
    subscriptions=(Subscription('web.started', web_started),),
    start=None,
    stop=None,
    status=module_status,
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
